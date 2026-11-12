"""Detect new Bybit trades and post formatted signals to channels."""

import logging
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from telegram import InputFile
from telegram.error import TelegramError

log = logging.getLogger("batna.signals")

# In-memory: orderId -> pending details for limit orders waiting for chart
PENDING_LIMITS: dict[str, dict] = {}
SEEN_ORDERS: set[str] = set()


def format_signal(order: dict) -> str:
    """Exact style used in the channel."""
    symbol = order["symbol"]
    base = symbol.replace("USDT", "").replace("USDC", "")
    side = "LONG" if order["side"] == "Buy" else "SHORT"
    order_type = order.get("orderType", "Market").upper()
    price = order.get("avgPrice") or order.get("price") or "0"
    try:
        price_f = float(price)
        price_str = f"{price_f:g}"
    except ValueError:
        price_str = price

    lev = order.get("leverage", "75")
    tp_pct = order.get("tp_pct")
    sl_pct = order.get("sl_pct")

    lines = [
        f"${base}/USDT",
        "",
        f"{side}: {order_type} [{price_str}]",
        f"LEVERAGE: {lev}X",
    ]
    if tp_pct is not None:
        lines.append(f"TP: +{tp_pct}%")
    if sl_pct is not None:
        lines.append(f"SL: {sl_pct}%")
    return "\n".join(lines)


def calc_pct(entry: float, target: float, leverage: float, is_short: bool) -> int | None:
    if not entry or not target:
        return None
    diff = (entry - target) if is_short else (target - entry)
    pct = (diff / entry) * leverage * 100
    return int(round(abs(pct)))


async def fetch_recent_orders(bybit):
    """Return open linear orders plus recent filled ones."""
    orders = []
    try:
        # Open / unfilled orders (limits waiting to fill)
        open_result = await bybit.get(
            "/v5/order/realtime",
            category="linear",
            settleCoin="USDT",
            openOnly=0,
            limit=20,
        )
        orders.extend(open_result.get("list", []))
    except Exception as e:
        log.warning("Could not fetch open orders: %s", e)
    try:
        # Recently filled orders
        hist = await bybit.get(
            "/v5/order/history",
            category="linear",
            orderStatus="Filled",
            limit=20,
        )
        orders.extend(hist.get("list", []))
    except Exception as e:
        log.warning("Could not fetch order history: %s", e)
    return orders


def enrich_order(order: dict) -> dict:
    """Add tp_pct / sl_pct from prices and leverage."""
    try:
        entry = float(order.get("avgPrice") or order.get("price") or 0)
        lev = float(order.get("leverage") or 1)
        tp = float(order.get("takeProfit") or 0)
        sl = float(order.get("stopLoss") or 0)
        is_short = order.get("side") == "Sell"
        order["tp_pct"] = calc_pct(entry, tp, lev, is_short) if tp else None
        order["sl_pct"] = calc_pct(entry, sl, lev, is_short) if sl else None
        order["leverage"] = str(int(lev)) if lev == int(lev) else str(lev)
    except (ValueError, TypeError):
        order["tp_pct"] = order["sl_pct"] = None
    return order


async def post_signal(bot, text: str, image_bytes: bytes | None, public: bool, private: bool, vip_chat):
    targets = []
    if public:
        targets.append("@BatnaTrades")
    if private and vip_chat:
        targets.append(vip_chat)
    for chat in targets:
        try:
            if image_bytes:
                await bot.send_photo(
                    chat,
                    photo=InputFile(BytesIO(image_bytes), filename="signal.png"),
                    caption=text,
                )
            else:
                await bot.send_message(chat, text)
        except TelegramError as e:
            log.warning("Failed to post signal to %s: %s", chat, e)


async def scan_and_handle(context):
    """Job: look for new filled orders and handle them."""
    s = context.application.bot_data["service"]
    bot = context.bot
    vip = s.store.get("vip_chat")

    orders = await fetch_recent_orders(s.bybit)
    # First run: just remember existing orders so we don't flood old trades
    if not SEEN_ORDERS:
        for raw in orders:
            if raw.get("orderId"):
                SEEN_ORDERS.add(raw["orderId"])
        log.info("Seeded %s existing orders", len(SEEN_ORDERS))
        return

    for raw in orders:
        oid = raw.get("orderId")
        if not oid or oid in SEEN_ORDERS:
            continue
        SEEN_ORDERS.add(oid)

        order = enrich_order(raw)
        order_type = (order.get("orderType") or "").lower()
        text = format_signal(order)
        log.info("New order %s type=%s symbol=%s", oid, order_type, order.get("symbol"))

        try:
            owner = await s.owner(bot)
            await bot.send_message(
                owner,
                f"Detected new {order_type or 'order'}.\n\n{text}\n\n"
                "If this is a limit, send the chart with caption <b>both</b> or <b>private</b>.\n"
                "Market orders are posted automatically.",
                parse_mode="HTML",
            )
        except Exception as e:
            log.warning("Could not notify owner: %s", e)

        if order_type == "market":
            await post_signal(bot, text, None, public=True, private=True, vip_chat=vip)
            log.info("Auto-posted market signal %s", oid)
        else:
            PENDING_LIMITS[oid] = {"text": text, "order": order}
            log.info("Limit order %s waiting for chart", oid)


async def handle_owner_chart(update, context):
    """Called when owner sends a photo. Caption decides both/private."""
    if not update.message or not update.message.photo:
        return False
    caption = (update.message.caption or "").strip().lower()
    if caption not in ("both", "private"):
        return False

    s = context.application.bot_data["service"]
    # Must be owner
    if not await s.is_owner(context.bot, update.effective_user.id):
        return False

    if not PENDING_LIMITS:
        await update.message.reply_text(
            "Got the chart, but no pending limit order right now.\n"
            "Place the order first, wait a few seconds, then send the chart with both/private."
        )
        return True

    # Take the most recent pending
    oid = next(reversed(PENDING_LIMITS))
    data = PENDING_LIMITS.pop(oid)
    text = data["text"]
    vip = s.store.get("vip_chat")

    photo = update.message.photo[-1]
    file = await photo.get_file()
    bio = BytesIO()
    await file.download_to_memory(bio)
    image_bytes = bio.getvalue()

    public = caption == "both"
    await post_signal(
        context.bot, text, image_bytes,
        public=public, private=True, vip_chat=vip,
    )
    await update.message.reply_text(
        f"Signal posted to {'both channels' if public else 'private channel only'}."
    )
    return True
