"""Read-only Bybit V5 client; this module cannot move funds or place trades."""

import hashlib
import hmac
import time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

import httpx


class BybitError(Exception):
    """Safe exception which contains neither credentials nor response bodies."""


class Bybit:
    ALLOWED_PATHS = {
        "/v5/asset/deposit/query-record",
        "/v5/asset/deposit/query-internal-record",
        "/v5/order/history",
        "/v5/execution/list",
        "/v5/position/list",
    }

    def __init__(self, key: str, secret: str):
        self.key, self.secret = key, secret
        self.client = httpx.AsyncClient(base_url="https://api.bybit.com", timeout=20)

    async def close(self):
        await self.client.aclose()

    async def get(self, path: str, **params):
        if path not in self.ALLOWED_PATHS:
            raise BybitError("This API operation is not permitted.")
        query = urlencode(sorted((key, str(value)) for key, value in params.items()))
        timestamp = str(int(time.time() * 1000))
        window = "10000"
        signature = hmac.new(
            self.secret.encode(),
            (timestamp + self.key + window + query).encode(),
            hashlib.sha256,
        ).hexdigest()
        try:
            response = await self.client.get(
                path + ("?" + query if query else ""),
                headers={
                    "X-BAPI-API-KEY": self.key,
                    "X-BAPI-TIMESTAMP": timestamp,
                    "X-BAPI-RECV-WINDOW": window,
                    "X-BAPI-SIGN": signature,
                },
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 403:
                raise BybitError(
                    "Bybit returned HTTP 403. This host may be in a restricted region. "
                    "Checkout must remain closed until a permitted host can reach Bybit."
                ) from None
            raise BybitError(
                f"Bybit returned HTTP {error.response.status_code}; no payment was verified."
            ) from None
        except (httpx.HTTPError, ValueError):
            raise BybitError("Bybit is unavailable or the API region is restricted.") from None
        if data.get("retCode") != 0:
            code = data.get("retCode", "unknown")
            raise BybitError(f"Bybit rejected the read-only request (code {code}).")
        return data["result"]

    async def deposits(self, order):
        internal = order["method"] == "uid"
        path = "/v5/asset/deposit/" + (
            "query-internal-record" if internal else "query-record"
        )
        start = int(order["created_at"].timestamp() * 1000)
        end = int(min(time.time(), order["expires_at"].timestamp()) * 1000)
        cursor = ""
        # No unbounded requests or silent truncation of a busy receiving account.
        for _ in range(50):
            params = dict(coin="USDT", startTime=start, endTime=end, limit=50)
            if cursor:
                params["cursor"] = cursor
            result = await self.get(path, **params)
            for row in result.get("rows", []):
                if matches(order, row):
                    yield row
            cursor = result.get("nextPageCursor", "")
            if not cursor:
                return
        raise BybitError("Deposit history is too large; administrator review is needed.")


def matches(order, row) -> bool:
    """Fail closed: coin, exact invoice amount, network, destination, time, success."""
    internal = order["method"] == "uid"
    try:
        if row.get("coin") != "USDT" or Decimal(row["amount"]) != order["amount"]:
            return False
        if int(row["status"]) != (2 if internal else 3):
            return False
        if not row.get("txID") or not row.get("id"):
            return False
        raw_time = int(row["createdTime" if internal else "successAt"])
        stamp = raw_time / 1000 if raw_time > 10**11 else raw_time
        if not order["created_at"].timestamp() <= stamp <= order["expires_at"].timestamp():
            return False
        if not internal:
            if row.get("chain") != "BSC":
                return False
            if row.get("toAddress", "").lower() != order["destination"].lower():
                return False
            if str(row.get("depositType", "0")) != "0":
                return False
            if str(row.get("travelRuleStatus", 0)) != "0":
                return False
        return True
    except (KeyError, ValueError, TypeError, InvalidOperation):
        return False
