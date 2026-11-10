"""Safe, read-only connectivity diagnostics; never outputs credentials or deposit records."""

import asyncio
import logging

from telegram import Bot
from telegram.error import TelegramError

from .bybit import Bybit, BybitError
from .config import Config, Vault
from .store import Store

logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("httpcore").setLevel(logging.CRITICAL)


async def check():
    config = Config.load()
    store = Store(config.database_url, Vault(config.encryption_secret))
    try:
        with store.connect() as db:
            db.execute("SELECT 1").fetchone()
        print("Database: connected")
    except Exception:
        print("Database: unavailable (credentials and connection details suppressed)")
    try:
        async with Bot(config.token) as bot:
            me = await bot.get_me()
            print(f"Telegram: connected as @{me.username}")
            webhook = await bot.get_webhook_info()
            print("Existing webhook: " + ("present; polling must not start" if webhook.url else "none"))
            try:
                member = await bot.get_chat_member(config.public_channel, me.id)
                print("Public channel bot role: " + member.status)
            except TelegramError:
                print("Public channel: add the bot as administrator")
    except TelegramError:
        print("Telegram: unavailable or invalid token (details suppressed)")
    bybit = Bybit(config.bybit_key, config.bybit_secret)
    # Check read permissions without printing any financial records.
    for endpoint, name in (
        ("query-internal-record", "internal deposit records"),
        ("query-record", "on-chain deposit records"),
    ):
        try:
            await bybit.get("/v5/asset/deposit/" + endpoint, coin="USDT", limit=1)
            print("Bybit " + name + ": accessible")
        except BybitError as error:
            print("Bybit " + name + ": " + str(error))
    await bybit.close()


if __name__ == "__main__":
    asyncio.run(check())
