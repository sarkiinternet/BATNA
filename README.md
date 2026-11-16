# Batna Trades Telegram Bot

A Python Telegram bot selling monthly private crypto-signal group access, gated by public-channel membership.

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
- The paid signals destination is a private Telegram group. The Bot API must report it as a supergroup for the bot's paid-member access lifecycle; do not describe the user's signals group as a channel.
- Verification uses a read-only Bybit key; the bot never trades, withdraws or transfers funds.
- Telegram requires Stars for in-bot digital subscriptions. The user explicitly chose Bybit UID and BEP20 USDT after being informed of restriction risk. Checkout must remain closed until the current host can retrieve the verified Bybit receiving details and deposit records, and owner setup is complete.
- The advertised base price is 20 USDT; the exact invoice adds a disclosed reference fraction below 0.01 USDT for safe payment attribution.

## Product

Public-channel join verification, two Bybit-verified USDT payment routes, calendar-month subscriptions, identity-gated private-group join requests, renewal reminders, expiry removal and support.

## User preferences

- The user requested a Python bot and a stylish, beautiful Telegram experience.
- Keep every menu and action button in Telegram's regular reply keyboard, never inline/popup buttons. Put links in message text.
- Require public-channel membership before a new user can access bot features; label the subscription entry button "Join Now".
- Keep customer copy concise and limited to the service's actual terms. The trading instruction is a 10% maximum account-balance risk per trade, with members following each private-group signal exactly.
- Clear Telegram's slash-command menu. Keep customer actions in the reply keyboard.
- The subscription offer is $20 monthly. Access is subscription-based, with no automatic billing.
- The user chose UID and BEP20 rather than Telegram Stars.

## Gotchas

_Populate as you build — sharp edges, "always run X before Y" rules._

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
