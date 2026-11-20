"""Detect new Bybit trades and post Cornix-compatible signals to channels."""

import logging
import time
from io import BytesIO

from telegram import InputFile
from telegram.error import TelegramError

log = logging.getLogger("batna.signals")

# In-memory state
PENDING_LIMITS: dict[str, dict] = {}
SEEN_ORDERS: set[str] = set()
# (symbol, side) -> unix timestamp of last posted signal
POSTED_RECENT: dict[tuple[str, str], float] = {}
DEDUP_WINDOW = 30 * 60  # 30 minutes – ignore same symbol+side again


def format_signal(order: dict) -> str:
    """Return a Cornix free-text signal.

    Follows https://help.cornix.io/en/articles/5814956-signal-posting
    """
    raw_symbol = order.get("symbol", "")
    if "/" in raw_symbol:
        symbol = raw_symbol
    else:
        base = raw_symbol.replace("USDT", "").replace("USDC", "")
        symbol = f"{base}/USDT"

    side_raw = order.get("side", "Buy")
    is_long = side_raw == "Buy"
    side = "Long" if is_long else "Short"

    order_type = (order.get("orderType") or "Market").lower()

    # Price (used for limit entries)
    price = order.get("avgPrice") or order.get("price") or "0"
    try:
        price_str = f"{float(price):g}"
    except (ValueError, TypeError):
        price_str = str(price)

    # Leverage
    lev = order.get("leverage", "1")
    try:
        lev_f = float(lev)
        lev_str = str(int(lev_f)) if lev_f == int(lev_f) else str(lev_f)
    except (ValueError, TypeError):
        lev_str = "1"

    # Absolute TP / SL prices (Cornix wants prices, not percentages)
    tp = order.get("takeProfit") or ""
    sl = order.get("stopLoss") or ""

    lines = [
        f"#{symbol}",
        "",
        "Exchanges: Bybit USDT",
        f"Signal Type: Regular ({side})",
        f"Leverage: Cross ({lev_str}x)",
        "",
    ]

    # Entry
    if order_type == "market":
        # Cornix recommended form for market entries (works for both long & short)
        lines.append("Entry: Buy at current price")
    else:
        lines.append(f"Entry: {price_str}")

    lines.append("")

    # Take-profit
    try:
        if tp and float(tp) > 0:
            lines.append("Take-Profit Targets:")
            lines.append(f"1) {float(tp):g}")
            lines.append("")
    except (ValueError, TypeError):
        pass

    # Stop-loss
    try:
        if sl and float(sl) > 0:
            lines.append("Stop Targets:")
            lines.append(f"1) {float(sl):g}")
            lines.append("")
    except (ValueError, TypeError):
        pass

    # Optional simple trailing (uncomment / extend if you want it by default)
    # lines.append("Trailing Configuration:")
    # lines.append("Stop: Breakeven - Trigger: Target (1)")

    return "\n".join(lines).strip()


def calc_pct(entry: float, target: float, leverage: float, is_short: bool) -> int | None:
    """Kept for possible future use; Cornix format uses absolute prices."""
    if not entry or not target:
        return None
    diff = (entry - target) if is_short else (target - entry)
    pct = (diff / entry) * leverage * 100
    return int(round(abs(pct)))


async def fetch_recent_orders(bybit):
    """Return open linear orders plus recent filled ones."""
    orders = []
    try:
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


async def get_leverage(bybit, symbol: str) -> float:
    """Real position leverage for the symbol."""
    try:
        result = await bybit.get(
            "/v5/position/list",
            category="linear",
            symbol=symbol,
        )
        for pos in result.get("list", []):
            lev = pos.get("leverage")
            if lev and float(lev) > 0:
                return float(lev)
    except Exception as e:
        log.warning("Could not get leverage for %s: %s", symbol, e)
    return 1.0


async def enrich_order(bybit, order: dict) -> dict:
    """Add real leverage (and keep tp/sl fields as-is for the Cornix formatter)."""
    try:
        lev = await get_leverage(bybit, order.get("symbol", ""))
        if lev <= 1:
            try:
                lev = float(order.get("leverage") or 1)
            except (ValueError, TypeError):
                lev = 1
        order["leverage"] = str(int(lev)) if lev == int(lev) else str(lev)
    except Exception as e:
        log.warning("enrich failed: %s", e)
    return order


async def post_signal(bot, text: str, image_bytes: bytes | None, public: bool, private: bool, vip_chat):
    """Post plain-text Cornix signal (optionally with chart)."""
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
                    # No parse_mode – Cornix needs plain text
                )
            else:
                await bot.send_message(chat, text)  # plain text
        except TelegramError as e:
            log.warning("Failed to post signal to %s: %s", chat, e)


def _is_opening_order(order: dict) -> bool:
    """Skip TP/SL / reduce-only legs so we only signal the actual entry."""
    if order.get("reduceOnly") in (True, "true", "True", 1, "1"):
        return False
    if order.get("closeOnTrigger") in (True, "true", "True", 1, "1"):
        return False
    # Some Bybit responses use "ReduceOnly" as string
    if str(order.get("reduceOnly", "")).lower() == "true":
        return False
    return True


async def scan_and_handle(context):
    """Job: look for new opening orders and handle them."""
    s = context.application.bot_data["service"]
    bot = context.bot
    vip = s.store.get("vip_chat")

    orders = await fetch_recent_orders(s.bybit)

    # First run: seed existing orders so we don't flood old trades
    if not SEEN_ORDERS:
        for raw in orders:
            if raw.get("orderId"):
                SEEN_ORDERS.add(raw["orderId"])
        log.info("Seeded %s existing orders", len(SEEN_ORDERS))
        return

    now = time.time()

    for raw in orders:
        oid = raw.get("orderId")
        if not oid or oid in SEEN_ORDERS:
            continue
        SEEN_ORDERS.add(oid)

        # Ignore closing / TP / SL orders
        if not _is_opening_order(raw):
            log.info("Skipping reduce-only / closing order %s", oid)
            continue

        order = await enrich_order(s.bybit, raw)
        symbol = order.get("symbol", "")
        side = order.get("side", "")
        key = (symbol, side)

        # Strong dedup: same symbol + side already posted recently
        last = POSTED_RECENT.get(key, 0)
        if now - last < DEDUP_WINDOW:
            log.info("Skipping duplicate signal for %s %s (posted %.0fs ago)", symbol, side, now - last)
            continue

        order_type = (order.get("orderType") or "").lower()
        text = format_signal(order)
        log.info("New opening order %s type=%s symbol=%s", oid, order_type, symbol)

        # Notify owner (plain text preview)
        try:
            owner = await s.owner(bot)
            await bot.send_message(
                owner,
                f"Detected new {order_type or 'order'}.\n\n{text}\n\n"
                "If this is a limit, send the chart with caption both or private.\n"
                "Market orders are posted automatically.",
            )
        except Exception as e:
            log.warning("Could not notify owner: %s", e)

        if order_type == "market":
            await post_signal(bot, text, None, public=True, private=True, vip_chat=vip)
            POSTED_RECENT[key] = now
            log.info("Auto-posted market signal %s", oid)
        else:
            PENDING_LIMITS[oid] = {"text": text, "order": order, "key": key}
            log.info("Limit order %s waiting for chart", oid)


async def handle_owner_chart(update, context):
    """Called when owner sends a photo. Caption decides both/private."""
    if not update.message or not update.message.photo:
        return False
    caption = (update.message.caption or "").strip().lower()
    if caption not in ("both", "private"):
        return False

    s = context.application.bot_data["service"]
    if not await s.is_owner(context.bot, update.effective_user.id):
        return False

    if not PENDING_LIMITS:
        await update.message.reply_text(
            "Got the chart, but no pending limit order right now.\n"
            "Place the order first, wait a few seconds, then send the chart with both/private."
        )
        return True

    # Most recent pending
    oid = next(reversed(PENDING_LIMITS))
    data = PENDING_LIMITS.pop(oid)
    text = data["text"]
    key = data.get("key")
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

    # Mark as posted so the later fill does not create a second signal
    if key:
        POSTED_RECENT[key] = time.time()

    await update.message.reply_text(
        f"Signal posted to {'both channels' if public else 'private channel only'}."
    )
    return True
