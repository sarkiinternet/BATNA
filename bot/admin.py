"""Owner-only setup and support replies."""

from html import escape

import psycopg
from telegram.constants import ChatType
from telegram.error import TelegramError

from . import ui
from .bybit import BybitError

GUIDE = (
    "<b>Administrator controls</b>\n\n"
    "<code>/setup</code> — connection and readiness checks\n"
    "<code>/setvip CHAT_ID</code> — connect the private signals group\n"
    "You can also forward a group post from the private group to this bot.\n\n"
    "<code>/setuid BYBIT_UID</code> — set the receiving UID\n"
    "<code>/setbep20 ADDRESS</code> — set the USDT BEP20 address\n"
    "<code>/open</code> — enable checkout after reviewing the checklist\n"
    "<code>/pause</code> — stop new invoices (existing ones are still verified)\n"
    "<code>/stats</code> — real membership counts\n"
    "<code>/paid INVOICE TXID</code> — confirm a payment you verified in Bybit\n"
    "<code>/reply TELEGRAM_ID message</code> — answer a support request\n"
    "<code>/erase TELEGRAM_ID</code> — delete inactive member data\n\n"
    "<b>Before /open</b>\n"
    "• Revoke old shared private-group invite links, including any supplied "
    "during setup. Use only the bot's request-to-join links.\n"
    "• Audit existing members; the bot does not remove unknown legacy members.\n"
    "• Give this bot Invite Users and Ban/Restrict Members permissions in the group.\n"
    "• Review the less-than-0.01 USDT invoice reference fraction.\n"
    "• Telegram requires Stars for in-bot digital subscriptions. This USDT flow "
    "can lead to restrictions; /open acknowledges that operational risk.\n\n"
    "<b>Security</b>\n"
    "Only the creator of @BatnaTrades can administer this bot. "
    "This bot cannot trade, transfer, or withdraw funds."
)


async def admin(update, context):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    s = context.application.bot_data["service"]
    uid = update.effective_user.id
    if not await s.is_owner(context.bot, uid):
        await update.message.reply_text("Owner access only.")
        return
    command = update.message.text.split()[0].split("@")[0][1:]
    args = context.args
    text = ""
    try:
        if command in ("admin", "setup"):
            lines = []
            try:
                await s.check_permissions(context.bot)
                lines.append("Telegram chat permissions: ready")
            except (ValueError, TelegramError):
                lines.append("Telegram chat permissions: incomplete — see setup steps below")
            lines.append("Bybit UID: " + ("set" if s.store.get("payment_uid") else "not set"))
            lines.append("USDT BEP20 address: " + (
                "set" if s.store.get("payment_bep20") else "not set"
            ))
            lines.append("Checkout: " + ("open" if s.store.get("checkout_open") else "paused"))
            text = "<b>Connection checklist</b>\n" + "\n".join(lines) + "\n\n" + GUIDE
        elif command == "setvip":
            if not args:
                raise ValueError("Usage: /setvip CHAT_ID")
            name = await s.bind_vip(context.bot, uid, int(args[0]))
            text = f"Private signals group connected: <b>{escape(name)}</b>.\n\nCheckout is paused. Run /setup."
        elif command in ("setuid", "setbep20"):
            if len(args) != 1:
                raise ValueError(
                    "Usage: /setuid BYBIT_UID" if command == "setuid"
                    else "Usage: /setbep20 BEP20_ADDRESS"
                )
            method = "uid" if command == "setuid" else "bep20"
            s.set_payment_destination(method, args[0])
            text = (
                "Receiving Bybit UID saved. Checkout is paused; run /open when ready."
                if method == "uid" else
                "USDT BEP20 address saved. Checkout is paused; run /open when ready."
            )
        elif command == "open":
            await s.check_permissions(context.bot)
            if not s.store.get("payment_uid") or not s.store.get("payment_bep20"):
                raise ValueError("Set both receiving details with /setuid and /setbep20 first.")
            s.store.set("checkout_open", True)
            text = "Checkout is open for both USDT methods."
        elif command == "pause":
            s.store.set("checkout_open", False)
            text = "New checkout is paused. Existing invoices and paid access continue to work."
        elif command == "stats":
            stats = s.store.stats()
            text = (
                f"<b>Membership overview</b>\n\nMembers: {stats['members']}\n"
                f"Active: {stats['active']}\nVerified payments: {stats['paid']}"
            )
        elif command == "paid":
            if len(args) != 2:
                raise ValueError("Usage: /paid INVOICE TXID")
            oid, txid = args
            if len(txid) < 8 or len(txid) > 200:
                raise ValueError("Provide the transaction ID you verified in Bybit.")
            order = s.store.order(oid)
            if not order:
                raise ValueError("Invoice not found.")
            async with s.lock:
                try:
                    changed = s.store.confirm_manual_payment(oid, txid)
                except psycopg.errors.UniqueViolation:
                    raise ValueError("This transaction was already recorded.") from None
            if not changed:
                raise ValueError("This invoice is no longer pending or this transaction was already used.")
            text = "Payment recorded as verified by you in Bybit. Membership will be activated."
        elif command == "reply":
            if len(args) < 2:
                raise ValueError("Usage: /reply TELEGRAM_ID your message")
            target = int(args[0])
            s.store.member(target)
            await context.bot.send_message(
                target, ui.card("A message from Batna Trades", escape(" ".join(args[1:]))),
                parse_mode="HTML", reply_markup=ui.back(),
            )
            text = "Reply delivered."
        elif command == "erase":
            if len(args) != 1:
                raise ValueError("Usage: /erase TELEGRAM_ID. Review retention obligations before using.")
            target = int(args[0])
            member = s.store.member(target)
            if s.store.active(target):
                raise ValueError("Resolve the active membership before deleting personal data.")
            with s.store.connect() as db:
                pending_payment = db.execute(
                    "SELECT id FROM batna.orders WHERE member_key=%s "
                    "AND state='pending' AND expires_at>now() LIMIT 1",
                    (member["key"],),
                ).fetchone()
                if pending_payment:
                    raise ValueError("Resolve pending payments before deletion.")
                # Keep non-reversible deposit fingerprints as anti-replay tombstones.
                db.execute(
                    "INSERT INTO batna.members(key,user_enc) VALUES ('deleted',%s) "
                    "ON CONFLICT DO NOTHING", (s.store.vault.seal("0"),),
                )
                db.execute(
                    "UPDATE batna.orders SET destination_enc=%s,receipt_enc=NULL,member_key=%s "
                    "WHERE member_key=%s",
                    (s.store.vault.seal("deleted"), "deleted", member["key"]),
                )
                db.execute("DELETE FROM batna.members WHERE key=%s", (member["key"],))
            text = "Personal data deleted. Non-reversible transaction fingerprints remain to prevent payment replay."
        else:
            text = GUIDE
    except (ValueError, BybitError) as error:
        text = escape(str(error))
    except TelegramError:
        text = "Telegram could not complete this action. Check the chat ID and administrator permissions."
    await update.message.reply_text(text[:4096], parse_mode="HTML")
