"""Telegram UI. Main menu is a reply keyboard. Payment choices are inline."""

from html import escape

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup,
)

from .store import now


def e(emoji_id, fallback):
    """Premium animated emoji. Non-premium users see the fallback."""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


BOLT = e("5224607267797606837", "⚡")
DOLLAR = e("5409048419211682843", "💵")
CHART = e("5449683594425410231", "📈")
CHECK = e("5206607081334906820", "✅")
CROSS = e("5210952531676504517", "❌")
LINK = e("5271604874419647061", "🔗")
LOCK = e("5296369303661067030", "🔒")
STAR = e("5438496463044752972", "⭐")
CAL = e("5413879192267805083", "📅")
INFO = e("5323442290708985472", "ℹ️")

BRAND = f'{BOLT} <b>BATNA TRADES</b>\n<code>private signals · no fluff</code>'
RULE = "━━━━━━━━━━━━━━━━━━━━"

BUTTON_ACTIONS = {
    "Join Now": "plans",
    "My membership": "status",
    "Refund promise": "promise",
    "Help & support": "help",
    "Privacy": "privacy",
    "I've joined — verify": "joined",
    "I've paid · check payment": "check",
    "Payment support": "help",
    "Enter private signals group": "access",
    "Request a refund": "refund",
    "Cancel": "cancel-support",
    "Home": "home",
    "Back to home": "home",
    "Back": "home",
    "Renew / subscribe": "plans",
}


def keyboard(rows, actions=None):
    mapping = dict(BUTTON_ACTIONS)
    if actions:
        mapping.update(actions)
    markup = ReplyKeyboardMarkup(
        [[KeyboardButton(label) for label in row] for row in rows],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="tap an option",
    )
    return markup, mapping


def card(title, body):
    return f"{BRAND}\n{RULE}\n\n<b>{escape(title)}</b>\n\n{body}"


def menu():
    return keyboard([
        ["Join Now"],
        ["My membership", "Refund promise"],
        ["Help & support", "Privacy"],
    ])


def back():
    return keyboard([["Back"]])


def welcome():
    return card(
        "you’re in the right place",
        "Welcome to <b>Batna Trades</b>.\n"
        "Monthly access to the private crypto signals group. That’s it.\n\n"
        f"{DOLLAR} <b>20 USDT</b> / month\n"
        "Bybit UID or USDT on BNB Smart Chain (BEP20).\n\n"
        f"{CHART} <b>Refund promise</b>\n"
        "If the group’s public monthly ROI is negative, subscription fee back "
        "(minus network fee). Personal results don’t matter.\n\n"
        "Join the public channel first, then tap <b>Join Now</b>.",
    )


def join_required(link):
    return card(
        "join the public channel first",
        "You need to be in <a href=\"" + escape(link, quote=True) + "\">@BatnaTrades</a> "
        "before the bot unlocks.\n\n"
        "Join, then tap <b>I've joined — verify</b>.",
    )


def join_keyboard(_link=None):
    return keyboard([["I've joined — verify"], ["Back"]])


def plan(policy):
    return card(
        "one month. 20 USDT. done.",
        "Private signals group access.\n"
        "No auto-renew. You pay when you want in.\n\n"
        f"{INFO} <b>Refund policy</b>\n" + escape(policy) + "\n\n"
        f"{DOLLAR} <b>How to pay</b>\n"
        "Send exactly <b>20 USDT</b>. Then paste your "
        "<b>TXID (transaction hash)</b> here.\n"
        "Grab it from Bybit or BscScan.\n\n"
        "Pick a method below 👇",
    )


def payment_inline():
    """Inline payment choices. Back stays on the reply keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "Pay with Bybit UID",
            callback_data="buy:uid",
            icon_custom_emoji_id="5224607267797606837",
        )],
        [InlineKeyboardButton(
            "Pay with USDT BEP20",
            callback_data="buy:bep20",
            icon_custom_emoji_id="5271604874419647061",
        )],
    ])


def invoice(order):
    uid = order["method"] == "uid"
    destination_title = "Receiving Bybit UID" if uid else "Bybit deposit address · BEP20 only"
    method = "Bybit internal UID transfer" if uid else "USDT · BNB Smart Chain (BEP20)"
    extra = (
        "Use Bybit internal transfer to this UID, in USDT."
        if uid else
        "Send USDT on <b>BNB Smart Chain / BEP20 only</b>. "
        "Wrong network = not counted."
    )
    return card(
        "your invoice",
        f"<b>METHOD</b>  {method}\n\n"
        f"<b>SEND EXACTLY</b>\n<code>20</code> <b>USDT</b>\n\n"
        f"<b>{destination_title}</b>\n<code>{escape(order['destination'])}</code>\n\n"
        f"<b>Invoice</b>  <code>{order['id']}</code>\n"
        f"<b>Pay before</b>  {order['expires_at']:%d %b %Y, %H:%M} UTC\n\n"
        "Send exactly <b>20 USDT</b> before the deadline. "
        "Cover network fees yourself.\n\n"
        + extra
        + "\n\nAfter paying, paste your <b>TXID (transaction hash)</b> in this chat. "
        "Copy it from Bybit or BscScan. We match that exact hash.\n"
        "Takes more than 10 min? Hit <b>Payment support</b>. Don’t pay twice.",
    )


def invoice_buttons(oid):
    return keyboard(
        [["I've paid · check payment"], ["Payment support", "Home"]],
        {"I've paid · check payment": f"check:{oid}"},
    )


def status(member):
    active = bool(member["until_at"] and member["until_at"] > now())
    if active:
        body = (
            f"{CHECK} <b>ACTIVE</b>\n\n"
            f"Access ends <b>{member['until_at']:%d %b %Y, %H:%M} UTC</b>.\n"
            "Renew adds another calendar month on top."
        )
    else:
        body = (
            f"{CROSS} <b>NO ACTIVE MEMBERSHIP</b>\n\n"
            "Join the channel, then grab monthly access."
        )
    return card("your membership", body + "\n\nNo auto-billing. You’re in control.")


def status_buttons(active):
    rows = []
    if active:
        rows.append(["Enter private signals group"])
    rows.extend([
        ["Renew / subscribe"],
        ["Request a refund"],
        ["Home"],
    ])
    return keyboard(rows)


PRIVACY = (
    f"{INFO} <b>Trading instructions</b>\n"
    "Follow the risk management and signal instructions posted in the private group.\n\n"
    f"{LOCK} <b>Privacy</b>\n"
    "We store your Telegram ID, membership dates, payment references, and anything "
    "you send for support or refunds. The admin can see those submissions. "
    "Message Help & support if you want your data deleted."
)

HELP = (
    f"{STAR} <b>Getting started</b>\n"
    "Join the public channel → verify → pick a payment method → "
    "send exactly 20 USDT → paste your TXID (transaction hash) → "
    "enter the private group.\n\n"
    f"{CAL} <b>Payment not found?</b>\n"
    "Verification can take up to 10 minutes. If it’s longer, message us. Don’t pay twice.\n\n"
    f"{INFO} <b>Need a human?</b>\n"
    "Hit Help & support and send your message. Include the invoice id if you have one.\n\n"
    f"{CHART} <b>Refunds</b>\n"
    "Request a refund after the month ends, only if the group’s public ROI was negative."
)
