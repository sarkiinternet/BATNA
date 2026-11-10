---
name: Bybit hosting restriction
description: Hosting-dependent obstacle to enabling the Telegram bot's payment verification.
---

Bybit's public mainnet API returned HTTP 403 from this environment, on both
`api.bybit.com` and `api.bytick.com`. This happened even for the unauthenticated
server-time endpoint, so a replacement API key is not a demonstrated solution.

**Why:** Bybit's official integration guide says US and mainland-China source
IPs are restricted. The exact classification of this environment was not independently
established; do not claim an account or credential fault from HTTP 403 alone.

**How to apply:** Keep checkout paused until a permitted hosting environment
successfully verifies receiving-account metadata, read-only permissions, the
USDT/BSC address and both deposit-history endpoints. Do not use proxies or
regional API domains to bypass geographic restrictions, and do not approve
payments from screenshots as a substitute.

Reference: https://bybit-exchange.github.io/docs/v5/guide
