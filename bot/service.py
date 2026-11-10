"""Subscription and chat operations shared by handlers and scheduled jobs."""

import asyncio
import logging
import re
from datetime import timedelta

import psycopg
from telegram import ChatMember
from telegram.constants import ChatType
from telegram.error import TelegramError

from . import ui
from .bybit import Bybit, BybitError
from .config import Config, Vault
from .store import Store, now

log = logging.getLogger("batna")
VIP_CHAT_TYPES = {ChatType.SUPERGROUP, ChatType.CHANNEL}


class Service:
    def __init__(self, config: Config):
        self.config = config
        self.store = Store(config.database_url, Vault(config.encryption_secret))
        self.bybit = Bybit(config.bybit_key, config.bybit_secret)
        self.lock = asyncio.Lock()
        self.owner_cache = None
        self.last_worker_warning = None

    async def owner(self, bot):
        # Not first-visitor ownership: only the creator of the specified public channel.
        if self.owner_cache:
            return self.owner_cache
        admins = await bot.get_chat_administrators(self.config.public_channel)
        creator = next((a.user.id for a in admins if a.status == ChatMember.OWNER), None)
        if not creator:
            raise ValueError("The public channel creator could not be verified.")
        self.owner_cache = creator
        return creator

    async def is_owner(self, bot, uid):
        try:
            return uid == await self.owner(bot)
        except (TelegramError, ValueError):
            return False

    async def joined(self, bot, uid):
        member = await bot.get_chat_member(self.config.public_channel, uid)
        return member.status in (
            ChatMember.OWNER, ChatMember.ADMINISTRATOR, ChatMember.MEMBER,
        ) or (member.status == ChatMember.RESTRICTED and member.is_member)

    async def check_permissions(self, bot):
        public = await bot.get_chat_member(self.config.public_channel, bot.id)
        if public.status != ChatMember.ADMINISTRATOR:
            raise ValueError("Add the bot as an administrator of @BatnaTrades first.")
        vip = self.store.get("vip_chat")
        if not vip:
            raise ValueError(
                "Add the bot as an administrator of the private signals group, "
                "then forward a group post here."
            )
        vip_chat = await bot.get_chat(vip)
        if vip_chat.type == ChatType.GROUP:
            raise ValueError(
                "Telegram identifies this as a basic group. Upgrade it to a "
                "supergroup so the bot can manage paid access."
            )
        if vip_chat.type not in VIP_CHAT_TYPES or vip_chat.username:
            raise ValueError("The signals group must be private.")
        admin = await bot.get_chat_member(vip, bot.id)
        if (admin.status != ChatMember.ADMINISTRATOR
                or not admin.can_invite_users or not admin.can_restrict_members):
            raise ValueError(
                "The bot needs Invite Users and Ban/Restrict Members permissions "
                "in the private signals group."
            )
        return vip

    async def ready(self, bot):
        if not self.store.get("checkout_open", False):
            raise ValueError("Membership checkout is currently unavailable.")
        await self.check_permissions(bot)
        policy = self.store.get("refund_policy")
        if not policy:
            raise ValueError("The administrator is finalizing the refund policy.")
        if not self.store.get("payment_uid") or not self.store.get("payment_bep20"):
            raise ValueError("The administrator is setting up payment details.")
        return policy

    def payment_destination(self, method):
        key = "payment_uid" if method == "uid" else "payment_bep20"
        destination = self.store.get(key)
        if not destination:
            raise ValueError("The administrator is setting up payment details.")
        return destination

    def set_payment_destination(self, method, value):
        value = value.strip()
        if method == "uid" and not re.fullmatch(r"\d{4,20}", value):
            raise ValueError("Enter a valid numeric Bybit UID.")
        if method == "bep20" and not re.fullmatch(r"0x[a-fA-F0-9]{40}", value):
            raise ValueError("Enter a valid 0x-prefixed BEP20 address.")
        key = "payment_uid" if method == "uid" else "payment_bep20"
        self.store.set(key, value)
        self.store.set("checkout_open", False)

    async def bind_vip(self, bot, uid, chat_id):
        if not await self.is_owner(bot, uid):
            raise ValueError("Only the creator of @BatnaTrades can configure this bot.")
        chat = await bot.get_chat(chat_id)
        public = await bot.get_chat(self.config.public_channel)
        if chat.id == public.id:
            raise ValueError("Choose the separate private signals group.")
        if chat.type == ChatType.GROUP:
            raise ValueError(
                "Telegram identifies this as a basic group. Upgrade it to a "
                "supergroup so the bot can manage paid access."
            )
        if chat.type not in VIP_CHAT_TYPES:
            raise ValueError("Choose a private signals supergroup.")
        if chat.username:
            raise ValueError("The signals group must be private for paid access control.")
        admin = await bot.get_chat_member(chat.id, bot.id)
        human = await bot.get_chat_member(chat.id, uid)
        if human.status not in (ChatMember.OWNER, ChatMember.ADMINISTRATOR):
            raise ValueError("You must administer the private signals group.")
        if (admin.status != ChatMember.ADMINISTRATOR
                or not admin.can_invite_users or not admin.can_restrict_members):
            raise ValueError("Give the bot Invite Users and Ban/Restrict Members permissions.")
        previous = self.store.get("vip_chat")
        if previous and previous != chat.id and self.store.stats()["active"]:
            raise ValueError("Close checkout and migrate active members before changing the signals group.")
        self.store.set("vip_chat", chat.id)
        self.store.set("checkout_open", False)
        return chat.title

    async def invite(self, bot, uid):
        if not self.store.active(uid):
            raise ValueError("You need an active membership to enter the signals group.")
        if not await self.joined(bot, uid):
            raise ValueError("Please rejoin @BatnaTrades before accessing the private group.")
        vip = await self.check_permissions(bot)
        member = await bot.get_chat_member(vip, uid)
        if member.status == ChatMember.BANNED:
            await bot.unban_chat_member(vip, uid, only_if_banned=True)
        link = await bot.create_chat_invite_link(
            vip, creates_join_request=True, expire_date=now() + timedelta(minutes=15),
            name="Paid member access",
        )
        return link.invite_link

    async def verify(self, order):
        async with self.lock:
            current = self.store.order(order["id"])
            if current["state"] == "paid":
                return True
            if current["state"] != "pending":
                return False
            if current["expires_at"] <= now() or not current.get("payment_evidence"):
                return False
            async for receipt in self.bybit.deposits(current):
                if (current["payment_evidence_type"] == "txid"
                        and receipt.get("txID", "").lower()
                        != current["payment_evidence"].lower()):
                    continue
                try:
                    return self.store.settle(current["id"], receipt)
                except psycopg.errors.UniqueViolation:
                    # A duplicate transaction must never add a second month.
                    return False
        return False

    async def notify_owner(self, bot, text, markup=None):
        try:
            owner = await self.owner(bot)
            await bot.send_message(owner, text, parse_mode="HTML", reply_markup=markup)
            return True
        except (TelegramError, ValueError):
            log.warning("Administrator notification could not be delivered.")
            return False

    async def tick(self, context):
        """Durable outbox retries delivery; failures never become successful payments."""
        for order in self.store.all_pending():
            try:
                await self.verify(order)
            except BybitError:
                log.warning("Deposit verification unavailable; no payment was credited.")
                # Avoid repeatedly messaging the owner during provider outages.
                if not self.last_worker_warning or now() - self.last_worker_warning > timedelta(hours=1):
                    await self.notify_owner(
                        context.bot,
                        "Deposit verification is unavailable. No payments are being auto-approved. "
                        "Use /setup to inspect the connection; do not ask members to pay again.",
                    )
                    self.last_worker_warning = now()
                break
        for delivery in self.store.pending_deliveries():
            uid = int(self.store.vault.open(delivery["user_enc"]))
            order = self.store.order(delivery["id"])
            try:
                await context.bot.send_message(
                    uid, ui.card(
                        "Payment confirmed. Welcome inside.",
                        f"We received <b>{order['amount']:.6f} USDT</b>.\n\n"
                        f"<b>Your paid month</b>\n{order['period_start']:%d %b %Y} → "
                        f"{order['period_end']:%d %b %Y, %H:%M} UTC\n\n"
                        "Your access is ready. Tap below to request entry into the private group.",
                    ), parse_mode="HTML",
                    reply_markup=ui.keyboard([
                        ["Enter private signals group"],
                        ["My membership"],
                    ])[0],
                )
                self.store.mark_delivered(order["id"])
            except TelegramError:
                log.warning("Membership confirmation delivery deferred.")

    async def maintain(self, context):
        vip = self.store.get("vip_chat")
        if not vip:
            return
        async with self.lock:
            for member in self.store.maintenance_members():
                uid = self.store.user_id(member)
                try:
                    if member["removal_due"]:
                        current = self.store.member(uid)
                        if current["until_at"] and current["until_at"] > now():
                            continue
                        await context.bot.ban_chat_member(vip, uid)
                        # Keep the ban in place until a new paid subscription.
                        self.store.mark_removed(member["key"])
                        try:
                            await context.bot.send_message(
                                uid, ui.card(
                                    "Your membership has ended",
                                    "Private-group access has expired. Thank you for being "
                                    "part of Batna Trades.\n\nRenew when you're ready, "
                                "or choose Request a refund if your completed month qualifies.",
                                ), parse_mode="HTML", reply_markup=ui.menu(),
                            )
                        except TelegramError:
                            pass
                    else:
                        await context.bot.send_message(
                            uid, ui.card(
                                "Your next month is up to you",
                                f"Your access ends <b>{member['until_at']:%d %b %Y, %H:%M} UTC</b>.\n\n"
                                "Renew now to keep access. No automatic charges.",
                            ), parse_mode="HTML", reply_markup=ui.menu(),
                        )
                        self.store.mark_reminded(member["key"])
                except TelegramError:
                    log.warning("Group membership maintenance deferred; check bot permissions.")
