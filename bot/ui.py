"""Telegram-native presentation with buttons in the normal reply keyboard."""

from html import escape

from telegram import KeyboardButton, ReplyKeyboardMarkup

from .store import now

BRAND = "<b>BATNA TRADES</b>\n<code>P R E M I U M   S I G N A L S</code>"
RULE = "━━━━━━━━━━━━━━━━━━━━"

BUTTON_ACTIONS = {
    "Explore membership · 20 USDT": "plans",
    "My membership": "status",
    "Refund promise": "promise",
    "Help & support": "help",
    "Privacy": "privacy",
    "I've joined — verify": "joined",
    "Agree & pay · Bybit UID": "buy:uid",
    "Agree & pay · USDT BEP20": "buy:bep20",
    "I've paid · check payment": "check",
    "Payment support": "help",
    "Enter private signals channel": "access",
    "Request a refund": "refund",
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
        ["Explore membership · 20 USDT"],
        ["My membership", "Refund promise"],
        ["Help & support", "Privacy"],
    ])


def back():
    return keyboard([["Back to home"]])


def welcome():
    return card(
        "A clearer plan. A more disciplined trade.",
        "Welcome to <b>Batna Trades</b>.\n"
        "Your monthly membership unlocks our private crypto trading signals channel.\n\n"
        "<b>ONE MONTH</b>  /  <b>20 USDT</b>\n"
        "Bybit UID transfer or USDT on BNB Smart Chain (BEP20).\n\n"
        "<b>Our subscription-fee refund promise</b>\n"
        "If you finish your subscription month in the negative from our signals, "
        "we refund your subscription fee after reviewing your claim under the "
        "published policy. Trading losses are not covered.\n\n"
        '<i>Start by <a href="https://t.me/BatnaTrades">joining our public community</a>. '
        "Trading involves risk; signals do not guarantee a profit.</i>",
    )


def join_keyboard(_link):
    # Reply keyboards cannot carry URL buttons; the chat message contains a clickable link.
    return keyboard([["I've joined — verify"], ["Back"]])


def plan(policy):
    return card(
        "One membership. One focused community.",
        "<b>20 USDT · one calendar month</b>\n"
        "Private signals channel access. Manual renewal; no automatic charges.\n\n"
        "<b>Refund policy</b>\n" + escape(policy) + "\n\n"
        "<b>Important payment detail</b>\n"
        "Your invoice adds a unique reference fraction of less than 0.01 USDT. "
        "Send the exact displayed amount, including all six decimal places. "
        "This links the deposit to you without relying on screenshots or public hashes.\n\n"
        "<i>Crypto prices, network fees and USDT's dollar value can vary. "
        "Only the subscription fee is refundable, not trading losses or network fees. "
        "Never trade money you cannot afford to lose.</i>",
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
        + "\n\nWe verify the successful deposit directly with Bybit. "
        "No transaction hash, wallet connection, or account password is needed.\n\n"
        "<i>Already sent but not credited? Do not send again. Contact payment support "
        "with this invoice reference. Late or incorrect payments need manual review.</i>",
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
        rows.append(["Enter private signals channel"])
    rows.extend([
        ["Renew / subscribe"],
        ["Request a refund"],
        ["Home"],
    ])
    return keyboard(rows)


PRIVACY = (
    "We store your Telegram user ID, invoice and subscription dates, payment references, "
    "and refund/support information you submit. These are used to verify payments, "
    "manage channel access and handle disputes. Personal fields and deposit receipts "
    "are encrypted in the database.\n\n"
    "Telegram processes messages and channel membership. Bybit processes payments and "
    "supplies deposit records; the bot does not request your Bybit password, API keys, "
    "seed phrase, or wallet connection.\n\n"
    "Support and refund evidence is shared with the service administrator for review. "
    "Do not submit passwords, API keys, identity documents or unrelated trade history.\n\n"
    "Use /delete to request deletion. Active subscriptions or legally required "
    "transaction records may need to be resolved or retained; the administrator "
    "will explain any retention requirement."
)

HELP = (
    "<b>Getting started</b>\n"
    "Join the public channel → verify membership → choose a payment method → "
    "send the exact invoice amount → enter the private channel.\n\n"
    "<b>Payment not found?</b>\n"
    "Wait for Bybit to credit the deposit, then check your invoice again. "
    "Do not pay twice. Late, short or wrong-network payments need administrator review.\n\n"
    "<b>Need a person?</b>\n"
    "Send <code>/support your message</code>. Include your invoice reference if applicable. "
    "For payment issues, use <code>/paysupport your message</code>.\n\n"
    "<b>Refunds</b>\n"
    "Use /refund after your subscription month ends. "
    "We cannot read your trading account or determine your personal P&amp;L automatically."
)
