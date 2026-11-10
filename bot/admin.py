"""Owner-only setup, support replies and auditable manual refunds."""

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
    "<code>/policy your refund eligibility rules</code> — publish terms\n"
    "<code>/open</code> — enable checkout after reviewing the checklist\n"
    "<code>/pause</code> — stop new invoices (existing ones are still verified)\n"
    "<code>/stats</code> — real membership counts\n\n"
    "<code>/refunds</code> — review claims\n"
    "<code>/paid INVOICE TXID</code> — confirm a payment you verified in Bybit\n"
    "<code>/approve INVOICE</code> — approve a claim, without moving money\n"
    "<code>/reject INVOICE reason</code> — reject with an explanation\n"
    "<code>/refunded INVOICE transaction_reference</code> — record a manual payout\n"
    "<code>/reply TELEGRAM_ID message</code> — answer a support request\n"
    "<code>/erase TELEGRAM_ID</code> — delete inactive member data\n\n"
    "<b>Before /open</b>\n"
    "• Revoke old shared private-group invite links, including any supplied "
    "during setup. Use only the bot's request-to-join links.\n"
    "• Audit existing members; the bot does not remove unknown legacy members.\n"
    "• Give this bot Invite Users and Ban/Restrict Members permissions in the group.\n"
    "• Define how a negative month is measured, trading fees, evidence required, "
    "claim deadlines (if any), and refund processing times.\n"
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
            lines.append("Refund policy: " + ("published" if s.store.get("refund_policy") else "not set"))
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
        elif command == "policy":
            policy = update.message.text.partition(" ")[2].strip()
            if len(policy) < 80 or len(policy) > 1800:
                raise ValueError("Provide refund rules between 80 and 1,800 characters. "
                                 "Define a negative month, required evidence and processing time.")
            s.store.set("refund_policy", policy)
            s.store.set("checkout_open", False)
            text = "Refund policy saved. Existing invoices retain their original terms. Review /setup, then /open."
        elif command == "open":
            await s.check_permissions(context.bot)
            if not s.store.get("refund_policy"):
                raise ValueError("Publish your refund rules first with /policy.")
            if not s.store.get("payment_uid") or not s.store.get("payment_bep20"):
                raise ValueError("Set both receiving details with /setuid and /setbep20 first.")
            s.store.set("checkout_open", True)
            text = "Checkout is open for both USDT methods."
        elif command == "pause":
            s.store.set("checkout_open", False)
            text = "New checkout is paused. Existing invoices, paid access and refunds continue to work."
        elif command == "stats":
            stats = s.store.stats()
            text = (
                f"<b>Membership overview</b>\n\nMembers: {stats['members']}\n"
                f"Active: {stats['active']}\nVerified payments: {stats['paid']}"
            )
        elif command == "refunds":
            claims = s.store.refund_requests()
            if not claims:
                text = "No pending or approved refund claims."
            else:
                for claim in claims:
                    evidence = s.store.vault.open(claim["refund_enc"])
                    policy = s.store.vault.open(claim["policy_enc"])
                    await update.message.reply_text(
                        f"<b>Refund · {claim['refund_state'].upper()}</b>\n"
                        f"Invoice: <code>{claim['id']}</code>\n"
                        f"Member: <code>{s.store.user_id(claim)}</code>\n"
                        f"Subscription received: {claim['amount']:.6f} USDT\n"
                        f"Period: {claim['period_start']:%d %b %Y} → {claim['period_end']:%d %b %Y}\n\n"
                        f"<b>Evidence</b>\n{escape(evidence[:1500])}\n\n"
                        f"<b>Terms accepted</b>\n{escape(policy[:1800])}",
                        parse_mode="HTML",
                    )
                    try:
                        if "\nTelegram photo: " in evidence:
                            await context.bot.send_photo(
                                uid, evidence.rsplit("\nTelegram photo: ", 1)[1],
                                caption="Refund evidence · " + claim["id"],
                            )
                        elif "\nTelegram document: " in evidence:
                            await context.bot.send_document(
                                uid, evidence.rsplit("\nTelegram document: ", 1)[1],
                                caption="Refund evidence · " + claim["id"],
                            )
                    except TelegramError:
                        await update.message.reply_text(
                            "The evidence attachment is no longer available from Telegram. "
                            "Ask the member to resend it; the claim text is still stored."
                        )
                return
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
        elif command in ("approve", "reject", "refunded"):
            if not args:
                raise ValueError(f"Usage: /{command} INVOICE" + (
                    " transaction_reference" if command == "refunded" else
                    " reason" if command == "reject" else ""
                ))
            oid = args[0]
            order = s.store.order(oid)
            if not order:
                raise ValueError("Invoice not found.")
            with s.store.connect() as db:
                member = db.execute(
                    "SELECT * FROM batna.members WHERE key=%s", (order["member_key"],),
                ).fetchone()
            target = s.store.user_id(member)
            if command == "approve":
                changed = s.store.change_refund(oid, "requested", "approved")
                message = (
                    f"Your subscription-fee refund for invoice <code>{oid}</code> has been approved. "
                    "The administrator will arrange the payout. No trading losses are reimbursed."
                )
                text = "Claim approved. No funds moved. Pay the member manually, then use /refunded INVOICE transaction_reference."
            elif command == "reject":
                reason = " ".join(args[1:])
                if len(reason) < 10:
                    raise ValueError("Include a clear rejection reason of at least 10 characters.")
                changed = s.store.change_refund(oid, "requested", "rejected", reason)
                message = f"Refund review for <code>{oid}</code>:\n\n{escape(reason)}\n\nUse /support to discuss this decision."
                text = "Decision recorded."
            else:
                ref = " ".join(args[1:])
                if len(ref) < 8:
                    raise ValueError("Include the actual payout transaction reference.")
                changed = s.store.change_refund(oid, "approved", "paid", ref)
                message = (
                    f"Your subscription-fee refund for <code>{oid}</code> has been marked paid "
                    f"by the administrator.\n\nPayout reference:\n<code>{escape(ref)}</code>\n\n"
                    "Please verify receipt. Use /paysupport if it has not arrived."
                )
                text = "Manual payout reference recorded. The bot did not execute or independently verify this payout."
            if not changed:
                raise ValueError("This claim is not in the required state, or was already processed.")
            try:
                await context.bot.send_message(target, message, parse_mode="HTML")
            except TelegramError:
                text += "\nThe member could not be notified. Follow up directly."
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
                open_claim = db.execute(
                    "SELECT id FROM batna.orders WHERE member_key=%s AND "
                    "(refund_state IN ('requested','approved') OR "
                    "(state='pending' AND expires_at>now())) LIMIT 1",
                    (member["key"],),
                ).fetchone()
                if open_claim:
                    raise ValueError("Resolve pending payments or refund claims before deletion.")
                # Keep non-reversible deposit fingerprints as anti-replay tombstones.
                db.execute(
                    "INSERT INTO batna.members(key,user_enc) VALUES ('deleted',%s) "
                    "ON CONFLICT DO NOTHING", (s.store.vault.seal("0"),),
                )
                db.execute(
                    "UPDATE batna.orders SET destination_enc=%s,receipt_enc=NULL,refund_enc=NULL,"
                    "refund_reference_enc=NULL,member_key=%s WHERE member_key=%s",
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
