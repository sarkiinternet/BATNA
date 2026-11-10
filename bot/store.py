"""Postgres persistence, encrypted personal fields, atomic invoice settlement."""

import calendar
import json
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

from .config import Vault

UTC = timezone.utc


def now():
    return datetime.now(UTC)


def next_month(start):
    year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


class Store:
    def __init__(self, url: str, vault: Vault):
        self.url, self.vault = url, vault

    def connect(self):
        return psycopg.connect(self.url, row_factory=dict_row, connect_timeout=10)

    def init(self):
        with self.connect() as db:
            db.execute("""
                CREATE SCHEMA IF NOT EXISTS batna;
                CREATE TABLE IF NOT EXISTS batna.settings (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS batna.members (
                    key TEXT PRIMARY KEY, user_enc TEXT NOT NULL,
                    until_at TIMESTAMPTZ, removal_due BOOLEAN NOT NULL DEFAULT FALSE,
                    reminded_for TIMESTAMPTZ
                );
                CREATE TABLE IF NOT EXISTS batna.orders (
                    id TEXT PRIMARY KEY, member_key TEXT NOT NULL REFERENCES batna.members(key),
                    method TEXT NOT NULL CHECK (method IN ('uid','bep20')),
                    amount NUMERIC(18,6) NOT NULL, destination_enc TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending',
                    policy_enc TEXT NOT NULL,
                    tx_key TEXT UNIQUE, record_key TEXT UNIQUE,
                    receipt_enc TEXT, period_start TIMESTAMPTZ, period_end TIMESTAMPTZ,
                    refund_state TEXT NOT NULL DEFAULT 'none', refund_enc TEXT,
                    refund_reference_enc TEXT
                );
                CREATE INDEX IF NOT EXISTS batna_orders_member
                    ON batna.orders(member_key, created_at DESC);
                CREATE UNIQUE INDEX IF NOT EXISTS batna_one_pending
                    ON batna.orders(member_key) WHERE state='pending';
                CREATE TABLE IF NOT EXISTS batna.deliveries (
                    order_id TEXT PRIMARY KEY REFERENCES batna.orders(id),
                    delivered BOOLEAN NOT NULL DEFAULT FALSE
                );
            """)

    def get(self, key, default=None):
        with self.connect() as db:
            row = db.execute("SELECT value FROM batna.settings WHERE key=%s", (key,)).fetchone()
        return json.loads(self.vault.open(row["value"])) if row else default

    def set(self, key, value):
        encoded = self.vault.seal(json.dumps(value))
        with self.connect() as db:
            db.execute(
                "INSERT INTO batna.settings VALUES (%s,%s) "
                "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", (key, encoded),
            )

    def member(self, uid):
        key = self.vault.index(f"user:{uid}")
        with self.connect() as db:
            db.execute(
                "INSERT INTO batna.members(key,user_enc) VALUES (%s,%s) "
                "ON CONFLICT DO NOTHING", (key, self.vault.seal(uid)),
            )
            return db.execute("SELECT * FROM batna.members WHERE key=%s", (key,)).fetchone()

    def user_id(self, member):
        return int(self.vault.open(member["user_enc"]))

    def active(self, uid):
        member = self.member(uid)
        return bool(member["until_at"] and member["until_at"] > now())

    def order(self, order_id, uid=None):
        with self.connect() as db:
            row = db.execute("SELECT * FROM batna.orders WHERE id=%s", (order_id,)).fetchone()
        if row and (uid is None or row["member_key"] == self.vault.index(f"user:{uid}")):
            row["destination"] = self.vault.open(row["destination_enc"])
            return row
        return None

    def pending_for(self, uid):
        key = self.vault.index(f"user:{uid}")
        with self.connect() as db:
            row = db.execute(
                "SELECT id FROM batna.orders WHERE member_key=%s AND state='pending' "
                "AND expires_at>now()", (key,),
            ).fetchone()
        return self.order(row["id"], uid) if row else None

    def create_order(self, uid, method, destination, policy):
        member = self.member(uid)
        stamp = now()
        with self.connect() as db:
            # Serialize reservations so two workers cannot assign the same amount.
            db.execute("SELECT pg_advisory_xact_lock(720206)")
            db.execute("UPDATE batna.orders SET state='expired' WHERE state='pending' AND expires_at<=now()")
            existing = db.execute(
                "SELECT id FROM batna.orders WHERE member_key=%s AND state='pending'",
                (member["key"],),
            ).fetchone()
            if existing:
                return self.order(existing["id"], uid)
            used = {row["amount"] for row in db.execute(
                "SELECT amount FROM batna.orders WHERE created_at>now()-interval '2 days'"
            ).fetchall()}
            available = list(set(range(1, 10000)) - {
                int((amount - Decimal(20)) * 1_000_000) for amount in used
            })
            if not available:
                raise ValueError("Checkout is busy. Please try again later.")
            amount = Decimal(20) + Decimal(secrets.choice(available)) / Decimal(1_000_000)
            oid = secrets.token_hex(6)
            db.execute(
                "INSERT INTO batna.orders(id,member_key,method,amount,destination_enc,"
                "created_at,expires_at,policy_enc) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (oid, member["key"], method, amount, self.vault.seal(destination),
                 stamp, stamp + timedelta(hours=1), self.vault.seal(policy)),
            )
        return self.order(oid, uid)

    def settle(self, order_id, receipt):
        """At most one credit per invoice, deposit record, and transaction hash."""
        with self.connect() as db:
            order = db.execute(
                "SELECT * FROM batna.orders WHERE id=%s FOR UPDATE", (order_id,),
            ).fetchone()
            if not order or order["state"] != "pending":
                return False
            member = db.execute(
                "SELECT * FROM batna.members WHERE key=%s FOR UPDATE", (order["member_key"],),
            ).fetchone()
            start = max(now(), member["until_at"] or now())
            end = next_month(start)
            tx_key = self.vault.index("tx:" + receipt["txID"].lower())
            record_key = self.vault.index(f"record:{order['method']}:{receipt['id']}")
            db.execute(
                "UPDATE batna.orders SET state='paid',tx_key=%s,record_key=%s,"
                "receipt_enc=%s,period_start=%s,period_end=%s WHERE id=%s",
                (tx_key, record_key, self.vault.seal(json.dumps(receipt)), start, end, order_id),
            )
            db.execute(
                "UPDATE batna.members SET until_at=%s,removal_due=FALSE,reminded_for=NULL WHERE key=%s",
                (end, order["member_key"]),
            )
            db.execute("INSERT INTO batna.deliveries(order_id) VALUES (%s)", (order_id,))
        return True

    def all_pending(self):
        with self.connect() as db:
            rows = db.execute(
                "SELECT id FROM batna.orders WHERE state='pending' AND expires_at>now() "
                "ORDER BY created_at LIMIT 100"
            ).fetchall()
        return [self.order(row["id"]) for row in rows]

    def pending_deliveries(self):
        with self.connect() as db:
            return db.execute(
                "SELECT o.id,m.user_enc FROM batna.deliveries d "
                "JOIN batna.orders o ON o.id=d.order_id "
                "JOIN batna.members m ON m.key=o.member_key WHERE NOT d.delivered LIMIT 100"
            ).fetchall()

    def mark_delivered(self, oid):
        with self.connect() as db:
            db.execute("UPDATE batna.deliveries SET delivered=TRUE WHERE order_id=%s", (oid,))

    def periods(self, uid):
        key = self.vault.index(f"user:{uid}")
        with self.connect() as db:
            return db.execute(
                "SELECT * FROM batna.orders WHERE member_key=%s AND state='paid' "
                "ORDER BY period_end DESC LIMIT 12", (key,),
            ).fetchall()

    def request_refund(self, uid, oid, evidence):
        with self.connect() as db:
            row = db.execute(
                "UPDATE batna.orders SET refund_state='requested',refund_enc=%s "
                "WHERE id=%s AND member_key=%s AND state='paid' AND period_end<=now() "
                "AND refund_state='none' RETURNING id",
                (self.vault.seal(evidence), oid, self.vault.index(f"user:{uid}")),
            ).fetchone()
        return bool(row)

    def refund_requests(self):
        with self.connect() as db:
            return db.execute(
                "SELECT o.*,m.user_enc FROM batna.orders o "
                "JOIN batna.members m ON m.key=o.member_key "
                "WHERE refund_state IN ('requested','approved') ORDER BY period_end LIMIT 20"
            ).fetchall()

    def change_refund(self, oid, old, new, reference=""):
        with self.connect() as db:
            return bool(db.execute(
                "UPDATE batna.orders SET refund_state=%s,refund_reference_enc=%s "
                "WHERE id=%s AND refund_state=%s RETURNING id",
                (new, self.vault.seal(reference), oid, old),
            ).fetchone())

    def maintenance_members(self):
        with self.connect() as db:
            db.execute(
                "UPDATE batna.members SET removal_due=TRUE "
                "WHERE until_at<=now() AND NOT removal_due"
            )
            return db.execute(
                "SELECT * FROM batna.members WHERE removal_due OR "
                "(until_at>now() AND until_at<now()+interval '3 days' "
                "AND reminded_for IS DISTINCT FROM until_at) LIMIT 100"
            ).fetchall()

    def mark_removed(self, key):
        with self.connect() as db:
            db.execute(
                "UPDATE batna.members SET removal_due=FALSE,until_at=NULL WHERE key=%s", (key,),
            )

    def mark_reminded(self, key):
        with self.connect() as db:
            db.execute("UPDATE batna.members SET reminded_for=until_at WHERE key=%s", (key,))

    def stats(self):
        with self.connect() as db:
            return {
                "members": db.execute(
                    "SELECT count(*) n FROM batna.members WHERE key<>'deleted'"
                ).fetchone()["n"],
                "active": db.execute(
                    "SELECT count(*) n FROM batna.members WHERE until_at>now()"
                ).fetchone()["n"],
                "paid": db.execute(
                    "SELECT count(*) n FROM batna.orders WHERE state='paid'"
                ).fetchone()["n"],
            }
