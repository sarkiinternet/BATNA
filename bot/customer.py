"""Customer commands, membership gate, invoices and refund evidence."""

from html import escape
import time
import re

from telegram import MessageOriginChannel, MessageOriginChat
from telegram.constants import ChatMemberStatus, ChatType
from telegram.error import TelegramError

from . import ui, signals
from .bybit import BybitError
from .store import now


async def show(update, context, text, buttons=None, inline=None):
    markup, actions = buttons or ui.menu()
    context.user_data["button_actions"] = actions
    message = update.effective_message or update.callback_query.message
    if inline is not None:
        # Reply keyboard (Back) and inline payment buttons can't share one message.
        await message.reply_text(
            "use the buttons on the message · Back is below",
            reply_markup=markup,
        )
        await message.reply_text(
            text, parse_mode="HTML", reply_markup=inline, disable_web_page_preview=True,
        )
        return
    await message.reply_text(
        text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True,
    )


async def require_public_membership(update, context):
    s = context.application.bot_data["service"]
    if await s.joined(context.bot, update.effective_user.id):
        return True
    await show(
        update, context, ui.join_required(s.config.public_link),
        ui.join_keyboard(s.config.public_link),
    )
    return False


async def start(update, context):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    s = context.application.bot_data["service"]
    s.store.member(update.effective_user.id)
    if not await require_public_membership(update, context):
        return
    await show(update, context, ui.welcome(), ui.menu())


async def handle_action(update, context, action):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    s = context.application.bot_data["service"]
    uid = update.effective_user.id
    try:
        if action != "joined" and not await require_public_membership(update, context):
            return
        if action == "home":
            context.user_data.pop("refund_invoice", None)
            context.user_data.pop("support_pending", None)
            await show(update, context, ui.welcome(), ui.menu())
        elif action in ("plans", "joined"):
            if not await s.joined(context.bot, uid):
                await show(
                    update, context, ui.join_required(s.config.public_link),
                    ui.join_keyboard(s.config.public_link),
                )
                return
            policy = await s.ready(context.bot)
            await show(update, context, ui.plan(policy), ui.back(), inline=ui.payment_inline())
        elif action.startswith("buy:"):
            method = action.split(":")[1]
            if method not in ("uid", "bep20"):
                return
            policy = await s.ready(context.bot)
            if not await s.joined(context.bot, uid):
                raise ValueError("Join @BatnaTrades before subscribing.")
            order = s.store.pending_for(uid)
            if order is None:
                destination = s.payment_destination(method)
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
            if not order.get("payment_evidence"):
                await show(update, context, ui.card(
                    "Send your payment details",
                    "After paying, send the TXID (transaction hash) here. "
                    "If verification takes more than 10 minutes, contact the admin "
                    "through Help & support. Do not pay twice.",
                ), ui.invoice_buttons(order["id"]))
                return
            if order["state"] == "paid" or await s.verify(order):
                await membership(update, context)
            elif order["expires_at"] <= now():
                await show(update, context, ui.card(
                    "Invoice expired",
                    "Do not send payment to this invoice. If you already paid, use "
                    "Help & support and include this invoice reference for manual review: "
                    f"<code>{order['id']}</code>. Do not send a second payment.",
                ), ui.back())
            else:
                await show(update, context, ui.card(
                    "Payment verification in progress",
                    f"Invoice <code>{order['id']}</code> is being checked against Bybit.\n\n"
                    "If it takes more than 10 minutes, choose Help & support to contact "
                    "the admin. Do not pay again.",
                ), ui.invoice_buttons(order["id"]))
        elif action == "status":
            await membership(update, context)
        elif action == "access":
            link = await s.invite(context.bot, uid)
            await show(update, context, ui.card(
                "Your private group is ready",
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
                "we refund your subscription fee after reviewing your claim.",
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
                "for review.",
            ), ui.back())
        elif action == "privacy":
            await show(update, context, ui.card("Your data, explained", ui.PRIVACY), ui.back())
        elif action == "help":
            context.user_data["support_pending"] = True
            await show(
                update, context,
                ui.card("Help & support", ui.HELP + "\n\nSend your message now."),
                ui.keyboard([["Cancel", "Home"]]),
            )
        elif action == "cancel-support":
            context.user_data.pop("support_pending", None)
            await show(update, context, ui.welcome(), ui.menu())
    except BybitError:
        await show(
            update, context,
            ui.card(
                "Payment verification is taking longer",
                "If it is not confirmed within 10 minutes, choose Help & support "
                "to contact the admin. Do not pay again.",
            ),
            ui.back(),
        )
    except ValueError as error:
        await show(update, context, ui.card("One more step", escape(str(error))), ui.back())
    except TelegramError:
        await show(update, context, ui.card(
            "Connection needs attention",
                "Telegram could not verify private-group access. The administrator may "
                "need to finish connecting the group. Please try again later.",
        ), ui.back())


async def membership(update, context):
    if not await require_public_membership(update, context):
        return
    s = context.application.bot_data["service"]
    uid = update.effective_user.id
    member = s.store.member(uid)
    await show(update, context, ui.status(member), ui.status_buttons(s.store.active(uid)))


async def refund(update, context):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    if not await require_public_membership(update, context):
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
         "fee for qualifying negative months under the terms you accepted.\n\n" if len(rows) > 1 else
         "You have no completed paid month available for a new claim. "
         "Claims open after the paid period ends.\n\n")
        + ("<b>Existing claims</b>\n" + summary if summary else ""),
    ), ui.keyboard(rows, actions))


async def support(update, context):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    if not await require_public_membership(update, context):
        return
    s = context.application.bot_data["service"]
    text = update.message.text.partition(" ")[2].strip()
    if not text:
        context.user_data["support_pending"] = True
        await show(
            update, context, ui.card("Help & support", ui.HELP + "\n\nSend your message now."),
            ui.keyboard([["Cancel", "Home"]]),
        )
        return
    await submit_support(update, context, text)


async def submit_support(update, context, text):
    s = context.application.bot_data["service"]
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
        f"{escape(text)}",
    )
    if delivered:
        context.user_data["support_at"] = time.monotonic()
        context.user_data.pop("support_pending", None)
    await update.message.reply_text(
        "Your message was delivered to the administrator."
        if delivered else "The administrator cannot receive messages yet. "
        "Please contact the public channel administrator directly."
    )


async def route(update, context):
    """Route normal reply-keyboard text; pass non-button text to refund submissions."""
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    # Owner chart for pending limit signal
    if await signals.handle_owner_chart(update, context):
        return
    if not await require_public_membership(update, context):
        return
    text = update.effective_message.text or ""
    action = context.user_data.get("button_actions", ui.BUTTON_ACTIONS).get(text)
    if action == "check":
        order = context.application.bot_data["service"].store.pending_for(update.effective_user.id)
        if not order:
            await update.effective_message.reply_text(
                "No active invoice to check. Choose Join Now to view membership."
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
    origin = message.forward_origin
    if isinstance(origin, MessageOriginChannel):
        forwarded_chat_id = origin.chat.id
    elif isinstance(origin, MessageOriginChat):
        forwarded_chat_id = origin.sender_chat.id
    else:
        forwarded_chat_id = None
    if forwarded_chat_id is not None:
        if await s.is_owner(context.bot, update.effective_user.id):
            try:
                name = await s.bind_vip(
                    context.bot, update.effective_user.id, forwarded_chat_id,
                )
                await message.reply_text(
                    f"Private signals group connected: {name}. "
                    "Checkout remains paused until setup is complete."
                )
            except (ValueError, TelegramError) as error:
                await message.reply_text(str(error) if isinstance(error, ValueError)
                                         else "Check the bot's administrator permissions.")
            return
    if context.user_data.get("support_pending"):
        text = (message.text or message.caption or "").strip()
        if not text:
            await message.reply_text("Please send your support message as text.")
            return
        await submit_support(update, context, text)
        return
    order = s.store.pending_for(update.effective_user.id)
    if order:
        evidence_type = None
        evidence = ""
        candidate = (message.text or "").strip()
        if re.fullmatch(r"[A-Za-z0-9_-]{8,200}", candidate):
            evidence_type, evidence = "txid", candidate
        if not evidence_type:
            await message.reply_text(
                "Send your TXID (transaction hash) for this invoice. "
                "You can copy it from Bybit or from BscScan."
            )
            return
        if not s.store.submit_payment(
            update.effective_user.id, order["id"], evidence_type, evidence,
        ):
            await message.reply_text("This invoice has expired. Choose Help & support for assistance.")
            return
        await s.notify_owner(
            context.bot,
            "<b>Payment evidence received</b>\n"
            f"Invoice: <code>{escape(order['id'])}</code>\n"
            f"Member: <code>{update.effective_user.id}</code>\n"
            f"Method: {escape(order['method'])} · {order['amount']:.6f} USDT\n"
            + f"TXID: <code>{escape(evidence)}</code>",
        )
        try:
            owner_id = await s.owner(context.bot)
            await context.bot.copy_message(
                owner_id, message.chat_id, message.message_id,
            )
        except (TelegramError, ValueError):
            pass
        verified = False
        try:
            verified = await s.verify(s.store.order(order["id"]))
        except BybitError:
            pass
        await message.reply_text(
            "Payment verified. Membership will activate shortly."
            if verified else
            "Payment details sent for verification. If it takes more than 10 minutes, "
            "choose Help & support to contact the admin. Do not pay again."
        )
        return
    oid = context.user_data.get("refund_invoice")
    if not oid:
        await message.reply_text(
            "Choose an option from the keyboard below."
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
        "published policy."
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
    if (change.chat.type in (ChatType.SUPERGROUP, ChatType.CHANNEL)
            and change.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR
            and not change.chat.username):
        try:
            if await s.is_owner(context.bot, change.from_user.id):
                name = await s.bind_vip(context.bot, change.from_user.id, change.chat.id)
                await s.notify_owner(
                    context.bot, f"Private signals group connected: <b>{escape(name)}</b>. "
                    "Checkout remains paused until the remaining setup is complete.",
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


async def on_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if data.startswith("buy:"):
        await handle_action(update, context, data)
