"""Customer commands, membership gate, invoices and support."""

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
            context.user_data.pop("support_pending", None)
            await show(update, context, ui.welcome(), ui.menu())
        elif action == "joined":
            if not await s.joined(context.bot, uid):
                await show(
                    update, context, ui.join_required(s.config.public_link),
                    ui.join_keyboard(s.config.public_link),
                )
                return
            await show(update, context, ui.welcome(), ui.menu())
        elif action == "plans":
            if not await s.joined(context.bot, uid):
                await show(
                    update, context, ui.join_required(s.config.public_link),
                    ui.join_keyboard(s.config.public_link),
                )
                return
            await s.ready(context.bot)
            await show(update, context, ui.plan(), ui.back(), inline=ui.payment_inline())
        elif action.startswith("buy:"):
            method = action.split(":")[1]
            if method not in ("uid", "bep20"):
                return
            await s.ready(context.bot)
            if not await s.joined(context.bot, uid):
                raise ValueError("Join @BatnaTrades before subscribing.")
            order = s.store.pending_for(uid)
            if order is None:
                destination = s.payment_destination(method)
                order = s.store.create_order(uid, method, destination)
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
    """Route normal reply-keyboard text and payment evidence."""
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    # Owner reply for pending limit signal (both / private)
    if await signals.handle_owner_reply(update, context):
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
            "Payment received. Verification is in progress. "
            "If it takes more than 10 minutes, use Help & support. Do not pay again."
        )
        return
    await message.reply_text("Use the buttons below.")


async def join_request(update, context):
    s = context.application.bot_data["service"]
    request = update.chat_join_request
    if not s.store.active(request.from_user.id):
        await request.decline()
        return
    if not await s.joined(context.bot, request.from_user.id):
        await request.decline()
        return
    await request.approve()


async def bot_membership(update, context):
    s = context.application.bot_data["service"]
    result = update.my_chat_member
    if result.new_chat_member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
        try:
            await s.bind_vip(context.bot, result.from_user.id, result.chat.id)
        except (ValueError, TelegramError):
            pass


async def on_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if data.startswith("buy:"):
        await handle_action(update, context, data)
