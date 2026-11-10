# Batna Trades · Python Telegram bot

A Telegram-native membership bot for Batna Trades. The service is written in
Python, not TypeScript. The original workspace's API and mockup packages are not
part of the bot.

All menu and action buttons use Telegram's persistent reply keyboard below the
chat composer. Invite links are clickable text in the message: Telegram reply
keyboards do not support URL buttons. The bot does not use popup inline buttons.

## Run

```sh
uv sync --locked
uv run python -m bot.check
uv run python -m bot.main
```

The **Batna Telegram Bot** workflow runs the last command. Only one instance may
poll this token. An existing webhook is not silently removed.

Required secrets: `TELEGRAM_BOT_TOKEN`, `BYBIT_API_KEY`, `BYBIT_API_SECRET`,
`SESSION_SECRET`, and the existing `DATABASE_URL`. Never put their values in code.
Keep `SESSION_SECRET` stable: rotating it without migrating encrypted data makes
stored identities and receipts unreadable. Back up the database and encryption
key separately, with access restricted to the operator.

## Finish setup inside Telegram

1. Add the bot to **@BatnaTrades** as an administrator.
2. From the public channel **creator's account**, start the bot and send `/setup`.
   Ownership is verified with Telegram; the first visitor cannot claim ownership.
3. Add the bot as an administrator of the private signals group with **Invite
   Users** and **Ban/Restrict Members** enabled. The bot can connect when added
   by the public-channel creator, when the creator forwards a group post to the
   bot, or with `/setvip CHAT_ID`. The group must be private and Telegram must
   report it as a supergroup; upgrade a basic group in Telegram before connecting
   it so paid access can be managed.
4. Revoke all previous private invite links, including the shared setup link.
   Audit legacy members. The bot can control its paid members and join requests;
   it cannot prevent direct admission by another administrator or retroactively
   discover every existing member.
5. Publish a policy with `/policy your complete rules`. Define "negative month",
   which signals/trades count, whether trading fees count, evidence needed,
   any filing deadline, and the time to process approved claims. The bot stores a
   snapshot with each invoice; later changes do not rewrite accepted terms.
6. Review `/setup` and run `/open` to enable both payment methods.

Checkout starts paused and stays paused if group permissions, the read-only
Bybit receiving account, deposit address or refund terms are missing.

## Pricing and payments

- Base fee: **20 USDT per calendar month**, not a guaranteed $20 exchange value.
- Each invoice adds a random six-decimal reference fraction of **0.000001 to
  0.009999 USDT**, clearly shown before payment. The exact net amount is required.
  This prevents a public transaction hash or a generic 20-USDT deposit from being
  claimed by the wrong subscriber. Do not remove the reference without replacing
  payment attribution with a comparably secure mechanism.
- A single invoice remains reserved per member for one hour. Existing pending
  invoices are reused rather than encouraging duplicate payments.
- The receiver UID and BEP20 address are obtained from the authenticated Bybit
  API, never from customer input. BEP20 payments must arrive in that same account.
- UID deposits must be successful (`status=2`); on-chain deposits must be credited
  (`status=3`), USDT/BSC, and match the destination, amount, and invoice window.
- Successful transactions and record IDs are uniquely fingerprinted and settled
  atomically with the new subscription period. A deposit cannot buy two months.
- A background job checks every 45 seconds. The user's check button is rate
  limited. Bybit failures never result in payment approval.
- Late, incorrectly sized or wrong-network payments are **not automatically
  credited**. They require owner review and resolution through `/paysupport`.
  There is deliberately no unrestricted "approve payment" command.
- The API client has only an explicit allowlist of GET operations. It cannot
  trade, withdraw, or transfer. It refuses non-read-only API keys.

### Telegram payment-policy warning

Telegram's Bot Developer Terms require Stars for digital services sold inside
bots, including signal-channel subscriptions. The owner explicitly requested
USDT after this was explained. **This USDT checkout may result in Telegram
restricting or terminating the bot.** It is not presented as compliant.
`/open` acknowledges this warning. Do not enable it without reviewing current
Telegram terms and applicable laws.

Source: https://telegram.org/tos/bot-developers#6-2-digital-goods-and-services

## Membership and refunds

The membership month starts on confirmation, or at the previous paid period's
end for renewals. It ends at the same UTC time one calendar month later,
clamping to the last valid day for shorter months. No automatic billing.

Private-group links expire after 15 minutes and require a join request. Approval checks
the requesting Telegram identity's paid status and public-channel membership.
Expired members are banned within approximately five minutes and unbanned on
their next valid access request. Renewal reminders are sent in the final three
days. Keep bot permissions enabled.

`/refund` shows completed paid months and accepts text, a photo, or a document.
Claims and accepted policy snapshots are encrypted. Owners review `/refunds`,
then `/approve INVOICE` or `/reject INVOICE reason`. Approval does not transfer
money. The owner pays manually, then records the reference using
`/refunded INVOICE transaction_reference`. The bot reports it as an
**administrator-recorded** payment, not an independently verified payout.

Only subscription fees are covered, not trading losses. The bot cannot determine
a customer's personal trading performance from the receiver's Bybit API.

## Privacy and operations

Personal Telegram IDs, recipients, receipts, evidence, settings and payout
references are application-encrypted using a key derived from `SESSION_SECRET`.
Member keys and transaction fingerprints are HMAC indexes. No passwords, trading
credentials, identity documents or private wallet keys are requested from members.
HTTP request logging is disabled to prevent Telegram token exposure.

`/privacy` explains collection and `/delete` sends a deletion request to the owner.
After resolving subscriptions, payments, claims and retention obligations,
`/erase TELEGRAM_ID` removes personal fields while retaining non-reversible
transaction fingerprints to prevent reuse. Also handle any copies retained in
the administrator's Telegram chat and backups according to the published policy.
The operator should configure an appropriate privacy policy in BotFather.

Postgres schema: `batna`, isolated from the workspace's existing application.
There is no local-file subscription database to lose on restarts. The delivery
outbox retries confirmation messages after payment. Scheduled tasks recover
from stored subscriptions and invoices; unsubmitted refund drafts do not survive
process restarts.

Diagnostics are safe summaries only. Never enable HTTP debug logging or print
API responses containing deposit history or key metadata. A trading API key
must be replaced with a read-only key, not worked around.

For continuous availability, run a single persistent worker; this development
workflow is not a promise of 24/7 hosting. The existing web artifact publish
configuration does not automatically deploy this Python worker.
