"""Configuration and encryption. Secret values must never enter logs."""

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass

from cryptography.fernet import Fernet


@dataclass(frozen=True)
class Config:
    token: str
    database_url: str
    encryption_secret: str
    bybit_key: str
    bybit_secret: str
    public_channel: str = "@BatnaTrades"
    public_link: str = "https://t.me/BatnaTrades"

    @classmethod
    def load(cls):
        names = (
            "TELEGRAM_BOT_TOKEN", "DATABASE_URL", "SESSION_SECRET",
            "BYBIT_API_KEY", "BYBIT_API_SECRET",
        )
        missing = [name for name in names if not os.environ.get(name)]
        if missing:
            raise RuntimeError("Missing configuration: " + ", ".join(missing))
        return cls(*(os.environ[name] for name in names))


class Vault:
    def __init__(self, secret: str):
        self.key = hashlib.sha256(secret.encode()).digest()
        self.cipher = Fernet(base64.urlsafe_b64encode(self.key))

    def seal(self, value) -> str:
        return self.cipher.encrypt(str(value).encode()).decode()

    def open(self, value: str) -> str:
        return self.cipher.decrypt(value.encode()).decode()

    def index(self, value) -> str:
        return hmac.new(self.key, str(value).encode(), hashlib.sha256).hexdigest()
