# Batna Trades Telegram Bot

A Python Telegram bot selling monthly private crypto-signal channel access, gated by public-channel membership.

## Run & Operate

- `uv run python -m bot.main` — Telegram polling worker (workflow: Batna Telegram Bot)
- `uv run python -m bot.check` — safe read-only connection diagnostics
- Bot documentation and owner command reference: `bot/README.md`
- Python dependencies are tracked in `pyproject.toml` and `uv.lock`.
- Do not enable HTTP debug logging: Telegram request URLs contain the bot token.
- Required secrets for the bot: `TELEGRAM_BOT_TOKEN`, `BYBIT_API_KEY`, `BYBIT_API_SECRET`, `SESSION_SECRET`, `DATABASE_URL`.
- Keep `SESSION_SECRET` stable: it protects persisted data; rotation requires data migration.
- The existing pnpm packages below are scaffolding, not the Telegram bot's runtime.

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

_Populate as you build — short repo map plus pointers to the source-of-truth file for DB schema, API contracts, theme files, etc._

## Architecture decisions

- The Telegram bot is Python, as requested, and uses the existing PostgreSQL database.
- Only the creator of the configured public channel can perform administrative operations.
- Verification uses a read-only Bybit key; the bot never trades, withdraws or transfers funds. Approved refunds are paid manually by the owner.
- Telegram requires Stars for in-bot digital subscriptions. The user explicitly chose Bybit UID and BEP20 USDT after being informed of restriction risk. Checkout remains paused until owner setup and explicit `/open`.
- The advertised base price is 20 USDT; the exact invoice adds a disclosed reference fraction below 0.01 USDT for safe payment attribution.

## Product

Public-channel join verification, two Bybit-verified USDT payment routes, calendar-month subscriptions, identity-gated private-channel join requests, renewal reminders, expiry removal, support and owner-reviewed subscription-fee refunds.

## User preferences

- The user requested a Python bot and a stylish, beautiful Telegram experience.
- The subscription offer is $20 monthly, with a subscription-fee refund if the subscriber ends the month negative; trading losses are not reimbursed.
- The user chose UID and BEP20 rather than Telegram Stars.

## Gotchas

_Populate as you build — sharp edges, "always run X before Y" rules._

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
