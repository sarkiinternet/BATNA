---
name: Bybit hosting restriction
description: Hosting-dependent obstacle to enabling the Telegram bot's payment verification.
---

Bybit's public mainnet API returned HTTP 403 from this environment, on both
`api.bybit.com` and `api.bytick.com`. This happened even for the unauthenticated
server-time endpoint, so a replacement API key is not a demonstrated solution.
The project owner attributes the rejection to the Replit workflow's US host; this
is consistent with Bybit's documented regional restrictions, though the egress
location has not been independently resolved from inside the workflow.

Replit's published-app geography is selected in the Publishing UI before the first
publish and becomes permanent afterward. That setting is not a code-level way to
relocate the running workspace workflow.

**Why:** Bybit's official integration guide says US and mainland-China source
IPs are restricted. The exact classification of this environment was not independently
established; do not claim an account or credential fault from HTTP 403 alone.

**How to apply:** Receiving UID and BEP20 address are entered manually by the
owner; Bybit API calls are only for deposit-record verification. If that API is
unavailable, the owner can verify a submitted payment in Bybit and record it
through the owner-only payment confirmation. Do not use proxies or regional API
domains to bypass geographic restrictions.

References:
- https://bybit-exchange.github.io/docs/v5/guide
- https://docs.replit.com/features/publishing/project-geography
