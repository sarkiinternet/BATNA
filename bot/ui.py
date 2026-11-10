"""Telegram-native presentation with buttons in the normal reply keyboard."""

from html import escape

from telegram import KeyboardButton, ReplyKeyboardMarkup

from .store import now

BRAND = "<b>BATNA TRADES</b>\n<code>P R E M I U M   S I G N A L S</code>"
RULE = "━━━━━━━━━━━━━━━━━━━━"

BUTTON_ACTIONS = {
    "Join Now": "plans",
    "My membership": "status",
    "Refund promise": "promise",
    "Help & support": "help",
    "Privacy": "privacy",
    "I've joined — verify": "joined",
    "Agree & pay · Bybit UID": "buy:uid",
    "Agree & pay · USDT BEP20": "buy:bep20",
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
    """Put options beneath the composer; persist the keyboard across screens."""
    mapping = dict(BUTTON_ACTIONS)
    if actions:
        mapping.update(actions)
    markup = ReplyKeyboardMarkup(
        [[KeyboardButton(label) for label in row] for row in rows],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Choose an option below",
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
    return keyboard([["Back to home"]])


def welcome():
    return card(
        "A clearer plan. A more disciplined trade.",
        "Welcome to <b>Batna Trades</b>.\n"
        "Your monthly membership unlocks our private crypto trading signals group.\n\n"
        "<b>ONE MONTH</b>  /  <b>20 USDT</b>\n"
        "Bybit UID transfer or USDT on BNB Smart Chain (BEP20).\n\n"
        "<b>Our subscription-fee refund promise</b>\n"
        "If you finish your subscription month in the negative from our signals, "
        "we refund your subscription fee after reviewing your claim under the "
        "published policy.\n\n"
        "Join the public community before subscribing.",
    )


def join_required(link):
    return card(
        "Join the public community",
        "Joining <a href=\"" + escape(link, quote=True) + "\">@BatnaTrades</a> is required "
        "before using the membership service.\n\n"
        "After joining, tap <b>I've joined — verify</b> below.",
    )


def join_keyboard(_link=None):
    return keyboard([["I've joined — verify"]])


def plan(policy):
    return card(
        "One membership. One focused community.",
        "<b>20 USDT · one calendar month</b>\n"
        "Private signals group access. Manual renewal; no automatic charges.\n\n"
        "<b>Refund policy</b>\n" + escape(policy) + "\n\n"
        "<b>Important payment detail</b>\n"
        "Your invoice adds a unique reference fraction of less than 0.01 USDT. "
        "Send the exact displayed amount, including all six decimal places. "
        "Send the transaction ID or a payment screenshot here after paying.",
    )


def payment_methods():
    return keyboard([
        ["Agree & pay · Bybit UID"],
        ["Agree & pay · USDT BEP20"],
        ["Back"],
    ])


def invoice(order):
    uid = order["method"] == "uid"
    destination_title = "Receiving Bybit UID" if uid else "Bybit deposit address · BEP20 only"
    return card(
        "Your secure payment reference",
        f"<b>METHOD</b>  {'Bybit internal UID transfer' if uid else 'USDT · BNB Smart Chain (BEP20)'}\n\n"
        f"<b>SEND EXACTLY</b>\n<code>{order['amount']:.6f}</code> <b>USDT</b>\n\n"
        f"<b>{destination_title}</b>\n<code>{escape(order['destination'])}</code>\n\n"
        f"<b>Invoice</b>  <code>{order['id']}</code>\n"
        f"<b>Pay before</b>  {order['expires_at']:%d %b %Y, %H:%M} UTC\n\n"
        "The exact <b>net deposit amount</b> must arrive before this deadline. "
        "Cover any sending/network fee separately. Do not round the amount.\n\n"
        + ("Use Bybit's internal transfer to this UID, in USDT."
           if uid else "Send USDT on <b>BNB Smart Chain / BEP20 only</b>. "
           "Other assets and networks will not activate your membership.")
        + "\n\nAfter paying, send your transaction ID or a screenshot in this chat. "
        "We'll verify it against the Bybit account. If it takes more than 10 minutes, "
        "choose <b>Payment support</b> and contact the admin. Do not pay twice.",
    )


def invoice_buttons(oid):
    return keyboard(
        [["I've paid · check payment"], ["Payment support", "Home"]],
        {"I've paid · check payment": f"check:{oid}"},
    )


def status(member):
    active = bool(member["until_at"] and member["until_at"] > now())
    return card(
        "Your membership",
        ("<b>ACTIVE</b>\n\n"
         f"Access ends <b>{member['until_at']:%d %b %Y, %H:%M} UTC</b>.\n"
         "Renewal adds a calendar month to your current expiry."
         if active else "<b>NO ACTIVE MEMBERSHIP</b>\n\n"
         "Join the community, then choose your monthly access.")
        + "\n\nNo automatic billing. You stay in control.",
    )


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
    "<b>Trading instructions</b>\n"
    "Follow the risk management and signal instructions posted in the private group. "
    "Follow each signal's instructions exactly as posted in the private group.\n\n"
    "<b>Privacy</b>\n"
    "The bot stores your Telegram ID, membership dates, payment references, and any "
    "payment evidence, support or refund information you submit. These submissions "
    "are shared with the service administrator for review. Send a Help & support "
    "message to request data deletion."
)

HELP = (
    "<b>Getting started</b>\n"
    "Join the public channel → verify membership → choose a payment method → "
    "send the exact invoice amount and your transaction ID or screenshot → "
    "enter the private group.\n\n"
    "<b>Payment not found?</b>\n"
    "Payment verification can take up to 10 minutes. If it takes longer, send a "
    "message here to contact the administrator. Do not pay twice.\n\n"
    "<b>Need a person?</b>\n"
    "Choose Help & support and send your message. Include your invoice reference if applicable.\n\n"
    "<b>Refunds</b>\n"
    "Choose Request a refund after your subscription month ends."
)
