"""Run with: uv run python -m bot.main"""

import logging
import time
import os
import signal
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Conflict, TelegramError
from telegram.ext import (
    Application, ChatJoinRequestHandler, ChatMemberHandler,
    CallbackQueryHandler, CommandHandler, MessageHandler, filters,
)

from . import admin, customer, ui
from .config import Config
from .service import Service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
# HTTP request URLs contain Telegram credentials. Never enable wire/request logging.
for logger_name in ("httpx", "httpcore", "telegram", "apscheduler"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)
log = logging.getLogger("batna")


def start_health_server():
    """Tiny HTTP server so Render free web services stay alive."""
    port = int(os.environ.get("PORT", 10000))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, format, *args):
            pass  # silence request logs

    server = HTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info("Health server listening on port %s", port)


async def error_handler(update, context):
    error = context.error
    if isinstance(error, BadRequest) and "Message is not modified" in str(error):
        return
    # No exception values, tracebacks, update bodies, headers or request URLs.
    log.error("Bot operation failed (%s); sensitive details suppressed.", type(error).__name__)
    if isinstance(error, Conflict):
        log.error("Another bot instance is polling. Stop the other instance before restarting.")
    if isinstance(update, Update) and update.effective_chat and update.effective_chat.type == "private":
        try:
            await context.bot.send_message(
                update.effective_chat.id,
                ui.card(
                    "Please try again",
                    "This action could not be completed. No unverified payment has been "
                    "credited. Choose My membership to check your access or Help & support "
                    "if you already sent funds. Do not pay again.",
                ), parse_mode=ParseMode.HTML, reply_markup=ui.back(),
            )
        except TelegramError:
            pass


async def post_init(application):
    s = application.bot_data["service"]
    # Do not alter another service's bot configuration or silently remove its webhook.
    webhook = await application.bot.get_webhook_info()
    if webhook.url:
        raise RuntimeError(
            "An existing webhook is configured. Disconnect that service explicitly "
            "before starting this polling bot."
        )
    await application.bot.set_my_commands([])
    await application.bot.set_my_short_description(
        "Batna Trades membership · Crypto signals · 20 USDT/month."
    )
    await application.bot.set_my_description(
        "Join Batna Trades, verify your public-channel membership and subscribe to "
        "our private crypto signals group. 20 USDT per calendar month. "
        "Negative-month subscription-fee refunds under published terms."
    )
    application.job_queue.run_repeating(s.tick, interval=45, first=10, name="deposit-verification")
    application.job_queue.run_repeating(s.maintain, interval=300, first=30, name="subscription-expiry")
    log.info("Telegram connected: @%s. Checkout is controlled by the owner.",
             application.bot.username)


async def post_shutdown(application):
    await application.bot_data["service"].bybit.close()


def build(config):
    s = Service(config)
    s.store.init()
    application = (
        Application.builder().token(config.token)
        .concurrent_updates(False)
        .post_init(post_init).post_shutdown(post_shutdown)
        .build()
    )
    application.bot_data["service"] = s
    application.add_handler(CallbackQueryHandler(customer.on_callback))
    application.add_handler(CommandHandler("start", customer.start))
    application.add_handler(CommandHandler(
        ["admin", "setup", "setvip", "policy", "open", "pause", "stats",
         "setuid", "setbep20", "paid", "refunds", "approve", "reject", "refunded",
         "reply", "erase"], admin.admin,
    ))
    application.add_handler(ChatJoinRequestHandler(customer.join_request))
    application.add_handler(ChatMemberHandler(customer.bot_membership, ChatMemberHandler.MY_CHAT_MEMBER))
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT, customer.route,
    ))
    application.add_error_handler(error_handler)
    return application


def main():
    config = Config.load()
    start_health_server()
    # Wait for the previous deploy to release the lock instead of crashing.
    s = Service(config)
    lease = s.store.connect()
    lease.autocommit = True
    acquired = False
    for attempt in range(30):
        acquired = lease.execute(
            "SELECT pg_try_advisory_lock(720207) AS acquired"
        ).fetchone()["acquired"]
        if acquired:
            break
        log.info("Previous bot instance still shutting down. Retrying lock (%s/30).", attempt + 1)
        time.sleep(3)
    if not acquired:
        lease.close()
        raise RuntimeError("A Batna bot worker is already running.")
    try:
        application = build(config)
        application.run_polling(
            allowed_updates=["message", "callback_query", "chat_join_request", "my_chat_member"],
            drop_pending_updates=False,
            stop_signals=(signal.SIGINT, signal.SIGTERM),
        )
    finally:
        lease.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        log.error("Bot startup stopped (%s). Run uv run python -m bot.check for safe diagnostics.",
                  type(error).__name__)
        raise SystemExit(1) from None
