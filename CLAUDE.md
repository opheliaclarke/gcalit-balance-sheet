# gcalit-balance-sheet — GCALIT LLC · Mercury Bank · FY 1 Apr 2025 → 31 Mar 2026

**Status 2026-08-23: API research DONE, read-only client BUILT + smoke-tested.
🛑 BLOCKED on ONE thing — a Mercury *Read Only* API token from Bob.**

## The ask (Bob, 2026-08-23)
Balance sheet for the GCALIT Mercury account, **1 Apr 2025 → 31 Mar 2026** (Indian FY).
Must state **Opening balance and Closing balance** explicitly. Count **card spend**, all
**incoming**, all **expenses**, and **money sent to card + reversed from card**. Then a
summary. Publish on a repo, **must look like Excel and be copyable straight into his local
Excel**. Design by Fable 5, built with ultracode.

## CONNECTION DECISION — read-only API token, NOT a webhook

**Webhooks cannot do this job.** Mercury's webhooks are forward-only push notifications
("Receive real-time notifications when resources in your Mercury account change") — they
fire when something changes *from now on*. There is no replay/backfill of a period that
ended 5 months ago. Same for the Events API. A webhook registered today would deliver
nothing about FY2025-26.

**Read Only token is the right instrument** and is the *safest* of the three tiers:
- `Read Only` — "Can fetch all available data on your Mercury account." **No IP whitelist
  required.** Cannot move money. ← this one
- `Read and Write` — can initiate transactions. Requires an IP whitelist. Not needed.
- `Custom` — scoped. Would also work but is more clicks for no gain.

Where to get it: Mercury → org name (top left) → **All Settings** → **Tokens** →
**Create an API Token** → **Read Only**. Shown once. (Needs admin permission on the account.)

⚠ **Mercury auto-deletes any token unused for 45 days** and emails admins 7 days before.
Fine for a one-off pull; if this becomes a recurring report, one call every 45 days keeps it alive.

Store at `/root/.config/mercury/token.json`, mode 600, `{"token": "secret-token:mercury_…"}`.
Never in the repo, never on the page, never in a log — `mercury.redact()` exists for that.

## API facts, verified first-hand from docs.mercury.com (mirrored in `docs/`)
- Base `https://api.mercury.com/api/v1`. Auth = **basic auth, token as username, blank
  password**; Bearer also accepted. The literal `secret-token:` prefix **is part of the
  credential**.
- Endpoints used (all GET): `/organization` · `/accounts` · `/credit` · `/cards` ·
  `/transactions` · `/account/{id}/statements` · statement PDF via `downloadUrl`.

### ⚠ FOUR TRAPS — encoded in `scripts/mercury.py`, do not undo
- **T1** `/account/{id}/transactions` defaults `start` to **"30 days before the current
  date"**. Omit it and you get a short list that reads as complete. We never use that
  endpoint for the ledger.
- **T2 (decisive)** `/transactions` `start`/`end` filter on **createdAt, not postedAt** —
  Mercury's own note: *"your Mercury transactions on your Dashboard might have their
  postedAt date displayed, as opposed to createdAt"*. A FY cut **must** use
  `postedStart`/`postedEnd`, or a txn created 31 Mar and posted 2 Apr lands in the wrong
  year and the closing balance will not tie. We pull both and measure the gap.
- **T3** `limit` maxes at 1000 **and defaults to 1000** — a full page is not proof of the
  end. Always follow the cursor to an empty page.
- **T4** 401 usually means the `secret-token:` prefix was dropped, or the token was
  auto-deleted at 45 days idle.

### Balance derivation — three independent routes, they must agree
- **A (authority)** the monthly statement whose period ends **31 Mar 2025** carries
  `endingBalance` = the **opening balance** for 1 Apr 2025. Same for 31 Mar 2026 = closing.
- **B (back-computation)** today's `currentBalance` minus every posted txn since 1 Apr 2025.
- **C (forward)** opening + FY movement = closing.
If A and B disagree, **say so on the page** — do not paper over it.

### Transaction kinds that matter to Bob's four buckets
`TransactionKind` enum (23 values) splits as:
- **IN**: incomingDomesticWire · incomingInternationalWire · checkDeposit · interestPayment
- **OUT**: outgoingPayment · externalTransfer · wireFee · *SubscriptionFee
- **CARD spend**: debitCardTransaction · creditCardTransaction · cardInternationalTransactionFee
- **CARD reversed/refunded**: debitCardCredit · creditCardCredit ·
  cardInternationalTransactionFeeRebate · …FeeReversal · …FeeRebateReversal
- **transfers between own accounts** (must NOT count as income or expense):
  internalTransfer · treasuryTransfer
`TransactionStatus`: pending · sent · cancelled · failed · reversed · blocked.
**Only `sent` moves money.** cancelled/failed/blocked must be excluded, and counted
separately so the page can show they were excluded rather than silently dropping them.

## Files
- `scripts/mercury.py` — read-only client. **Contains no write verb at all.** Smoke-tested.
- `docs/*.md` — the Mercury OpenAPI/docs pages this was built from (mirrored 2026-08-23).

## Open / next
1. **Bob: the Read Only token.** Nothing else blocks.
2. Then: `pull.py` (raw JSON to `raw/`, never re-fetch), `build.py` (the four buckets +
   3-way balance reconciliation), Fable 5 Excel-look page, publish, verify agent on numbers.
