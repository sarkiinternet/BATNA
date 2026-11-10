"""Customer commands, membership gate, invoices and refund evidence."""

from html import escape
import time

from telegram import MessageOriginChannel
from telegram.constants import ChatMemberStatus, ChatType
from telegram.error import TelegramError

from . import ui
from .bybit import BybitError
from .store import now


async def show(update, context, text, buttons=None):
    markup, actions = buttons or ui.menu()
    context.user_data["button_actions"] = actions
    await update.effective_message.reply_text(
        text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True,
    )


async def start(update, context):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    context.application.bot_data["service"].store.member(update.effective_user.id)
    await show(update, context, ui.welcome(), ui.menu())


async def handle_action(update, context, action):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    s = context.application.bot_data["service"]
    uid = update.effective_user.id
    try:
        if action == "home":
            context.user_data.pop("refund_invoice", None)
            await show(update, context, ui.welcome(), ui.menu())
        elif action in ("plans", "joined"):
            if not await s.joined(context.bot, uid):
                await show(update, context, ui.card(
                    "Your first step is the community",
                    "Join <b>@BatnaTrades</b>, then return here and tap "
                    "<b>I've joined — verify</b>.\n\n"
                    "Membership is checked directly with Telegram before checkout.",
                ), ui.join_keyboard(s.config.public_link))
                return
            policy = await s.ready(context.bot)
            await show(update, context, ui.plan(policy), ui.payment_methods())
        elif action.startswith("buy:"):
            method = action.split(":")[1]
            if method not in ("uid", "bep20"):
                return
            policy = await s.ready(context.bot)
            if not await s.joined(context.bot, uid):
                raise ValueError("Join @BatnaTrades before subscribing.")
            order = s.store.pending_for(uid)
            if order is None:
                # The API, not a pasted wallet address, determines the recipient.
                destination = await s.bybit.destination(method)
                order = s.store.create_order(uid, method, destination, policy)
            await show(update, context, ui.invoice(order), ui.invoice_buttons(order["id"]))
        elif action.startswith("check:"):
            last = context.user_data.get("last_check", 0)
            if time.monotonic() - last < 10:
                return
            context.user_data["last_check"] = time.monotonic()
            order = s.store.order(action.split(":")[1], uid)
            if not order:
                raise ValueError("This invoice does not belong to your account.")
            if order["state"] == "paid" or await s.verify(order):
                await membership(update, context)
            elif order["expires_at"] <= now():
                await show(update, context, ui.card(
                    "Invoice expired",
                    "Do not send payment to this invoice. If you already paid, use "
                    f"<code>/paysupport {order['id']} your message</code> for manual review. "
                    "Do not send a second payment.",
                ), ui.back())
            else:
                await show(update, context, ui.card(
                    "Waiting for a confirmed deposit",
                    f"Invoice <code>{order['id']}</code> is not yet matched to a successful "
                    "Bybit deposit. It may still be processing.\n\n"
                    f"Exact net amount: <b>{order['amount']:.6f} USDT</b>\n"
                    f"Deadline: {order['expires_at']:%d %b %Y, %H:%M} UTC\n\n"
                    "If you've already sent it, do not pay again.",
                ), ui.invoice_buttons(order["id"]))
        elif action == "status":
            await membership(update, context)
        elif action == "access":
            link = await s.invite(context.bot, uid)
            await show(update, context, ui.card(
                "Your private channel is ready",
                "Request to join using the button below. Only an active paid member "
                "who is also in @BatnaTrades will be approved.\n\n"
                f'<a href="{escape(link, quote=True)}">Request entry · private signals</a>\n\n'
                "This link expires in 15 minutes. Do not share it."
            ), ui.keyboard([["My membership"], ["Home"]]))
        elif action == "promise":
            policy = s.store.get("refund_policy")
            await show(update, context, ui.card(
                "Your subscription-fee refund promise",
                escape(policy) if policy else
                "If you end your subscription month in the negative from our signals, "
                "we refund your subscription fee after reviewing your claim.\n\n"
                "The administrator is finalizing the eligibility and evidence rules. "
                "Checkout stays closed until those rules are published.\n\n"
                "<b>Trading losses are not covered. No profit is guaranteed.</b>",
            ), ui.back())
        elif action == "refund":
            await refund(update, context)
        elif action.startswith("claim:"):
            oid = action.split(":")[1]
            order = s.store.order(oid, uid)
            if not order or order["state"] != "paid" or order["period_end"] > now():
                raise ValueError("Choose a completed paid subscription month.")
            if order["refund_state"] != "none":
                raise ValueError("This period already has a refund decision or pending request.")
            context.user_data["refund_invoice"] = oid
            await show(update, context, ui.card(
                "Tell us about your completed month",
                f"Invoice: <code>{oid}</code>\n\n"
                "<b>Terms accepted for this month</b>\n"
                + escape(s.store.vault.open(order["policy_enc"]))
                + "\n\nSend a message, screenshot or document with the relevant trade "
                "history, net result and explanation. It will be sent to the administrator "
                "for review. Redact account credentials and unrelated personal information.\n\n"
                "Use /cancel to stop. The bot does not access your trading account.",
            ), ui.back())
        elif action == "privacy":
            await show(update, context, ui.card("Your data, explained", ui.PRIVACY), ui.back())
        elif action == "help":
            await show(update, context, ui.card("We're here to help", ui.HELP), ui.back())
    except (ValueError, BybitError) as error:
        await show(update, context, ui.card("One more step", escape(str(error))), ui.back())
    except TelegramError:
        await show(update, context, ui.card(
            "Connection needs attention",
            "Telegram could not verify channel access. The administrator may need to "
            "finish connecting the channels. Please try again later or use /support.",
        ), ui.back())


async def membership(update, context):
    s = context.application.bot_data["service"]
    uid = update.effective_user.id
    member = s.store.member(uid)
    await show(update, context, ui.status(member), ui.status_buttons(s.store.active(uid)))


async def refund(update, context):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    s = context.application.bot_data["service"]
    periods = s.store.periods(update.effective_user.id)
    completed = [p for p in periods if p["period_end"] <= now()]
    rows = []
    actions = {}
    for period in completed:
        if period["refund_state"] == "none":
            label = f"Review · {period['period_start']:%d %b}–{period['period_end']:%d %b}"
            rows.append([label])
            actions[label] = f"claim:{period['id']}"
    summary = "\n".join(
        f"<code>{p['id']}</code> · {escape(p['refund_state'])}" for p in completed
        if p["refund_state"] != "none"
    )
    rows.append(["Home"])
    await show(update, context, ui.card(
        "Review your completed month",
        ("Choose the subscription period you want reviewed. We refund the subscription "
         "fee for qualifying negative months under the terms you accepted. "
         "We do not reimburse trading losses.\n\n" if len(rows) > 1 else
         "You have no completed paid month available for a new claim. "
         "Claims open after the paid period ends.\n\n")
        + ("<b>Existing claims</b>\n" + summary if summary else ""),
    ), ui.keyboard(rows, actions))


async def support(update, context):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    s = context.application.bot_data["service"]
    text = update.message.text.partition(" ")[2].strip()
    if not text:
        await show(update, context, ui.card("Help & payment support", ui.HELP), ui.back())
        return
    if len(text) > 2500:
        await update.message.reply_text("Please keep your support message under 2,500 characters.")
        return
    last = context.user_data.get("support_at", 0)
    if time.monotonic() - last < 60:
        await update.message.reply_text("Please wait a minute before sending another support message.")
        return
    uid = update.effective_user.id
    s.store.member(uid)
    delivered = await s.notify_owner(
        context.bot, f"<b>Support request</b>\nMember: <code>{uid}</code>\n\n"
        f"{escape(text)}\n\nReply with <code>/reply {uid} your message</code>",
    )
    if delivered:
        context.user_data["support_at"] = time.monotonic()
    await update.message.reply_text(
        "Your message was delivered to the administrator."
        if delivered else "The administrator cannot receive messages yet. "
        "Please contact the public channel administrator directly."
    )


async def route(update, context):
    """Route normal reply-keyboard text; pass non-button text to refund submissions."""
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    text = update.effective_message.text or ""
    action = context.user_data.get("button_actions", ui.BUTTON_ACTIONS).get(text)
    if action == "check":
        order = context.application.bot_data["service"].store.pending_for(update.effective_user.id)
        if not order:
            await update.effective_message.reply_text(
                "No active invoice to check. Use /start to view your membership."
            )
            return
        action = "check:" + order["id"]
    if action:
        await handle_action(update, context, action)
    else:
        await incoming(update, context)


async def incoming(update, context):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    s = context.application.bot_data["service"]
    message = update.message
    if isinstance(message.forward_origin, MessageOriginChannel):
        if await s.is_owner(context.bot, update.effective_user.id):
            try:
                name = await s.bind_vip(
                    context.bot, update.effective_user.id, message.forward_origin.chat.id,
                )
                await message.reply_text(f"Private channel connected: {name}. Run /setup next.")
            except (ValueError, TelegramError) as error:
                await message.reply_text(str(error) if isinstance(error, ValueError)
                                         else "Check the bot's administrator permissions.")
            return
    oid = context.user_data.get("refund_invoice")
    if not oid:
        await message.reply_text(
            "Choose an option from the keyboard below, or use /start, /support or /refund."
        )
        return
    evidence = (message.text or message.caption or "").strip()
    if len(evidence) > 1800:
        await message.reply_text("Please shorten your explanation to 1,800 characters.")
        return
    if message.document:
        if message.document.file_size and message.document.file_size > 10_000_000:
            await message.reply_text("Please send a document under 10 MB.")
            return
        evidence += "\nTelegram document: " + message.document.file_id
    if message.photo:
        evidence += "\nTelegram photo: " + message.photo[-1].file_id
    if len(evidence) < 20:
        await message.reply_text("Please include your month's net result and relevant trade history.")
        return
    if not s.store.request_refund(update.effective_user.id, oid, evidence):
        context.user_data.pop("refund_invoice", None)
        await message.reply_text("This period is not eligible for a new request or already has one.")
        return
    context.user_data.pop("refund_invoice", None)
    await s.notify_owner(
        context.bot, f"<b>Refund review requested</b>\nInvoice: <code>{oid}</code>\n"
        f"Member: <code>{update.effective_user.id}</code>\n\n"
        "Use /refunds to review the evidence and the terms accepted for this invoice.",
    )
    try:
        await context.bot.copy_message(
            await s.owner(context.bot), message.chat_id, message.message_id,
        )
    except (TelegramError, ValueError):
        pass  # The encrypted claim is durable and visible in /refunds.
    await message.reply_text(
        "Refund request recorded. The administrator will review it under your invoice's "
        "published policy. This is a review request, not confirmation of a payout."
    )


async def join_request(update, context):
    s = context.application.bot_data["service"]
    request = update.chat_join_request
    if request.chat.id != s.store.get("vip_chat"):
        return
    uid = request.from_user.id
    # All join-request links, even leaked ones, enforce the paid identity.
    try:
        allowed = s.store.active(uid) and await s.joined(context.bot, uid)
        if allowed:
            await request.approve()
        else:
            await request.decline()
    except TelegramError:
        return


async def bot_membership(update, context):
    s = context.application.bot_data["service"]
    change = update.my_chat_member
    if (change.chat.type == ChatType.CHANNEL
            and change.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR
            and not change.chat.username):
        try:
            if await s.is_owner(context.bot, change.from_user.id):
                name = await s.bind_vip(context.bot, change.from_user.id, change.chat.id)
                await s.notify_owner(
                    context.bot, f"Private signals channel connected: <b>{escape(name)}</b>. "
                    "Run /setup to finish. Checkout remains paused.",
                )
        except (TelegramError, ValueError):
            pass


async def basic(update, context):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    command = update.message.text.split()[0].split("@")[0]
    s = context.application.bot_data["service"]
    if command == "/cancel":
        context.user_data.pop("refund_invoice", None)
        await update.message.reply_text("Cancelled. Your payment history and membership are unchanged.")
    elif command == "/privacy":
        await show(update, context, ui.card("Your data, explained", ui.PRIVACY), ui.back())
    elif command == "/delete":
        uid = update.effective_user.id
        delivered = await s.notify_owner(
            context.bot, f"<b>Data deletion requested</b>\nMember: <code>{uid}</code>\n"
            "Review active subscriptions, pending claims and any legal retention requirements. "
            f"Reply with /reply, then use <code>/erase {uid}</code> when resolved.",
        )
        await update.message.reply_text(
            "Your deletion request was sent to the administrator for review."
            if delivered else "The administrator is not reachable through the bot yet. "
            "Contact the public channel administrator to request deletion."
        )
    elif command == "/id":
        await update.message.reply_text(f"Your Telegram user ID: {update.effective_user.id}")
