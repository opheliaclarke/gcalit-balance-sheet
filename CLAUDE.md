# gcalit-balance-sheet — GCALIT LLC · Mercury Bank · FY 1 Apr 2025 → 31 Mar 2026

**Status 2026-08-23: DELIVERED.**
LIVE: **https://opheliaclarke.github.io/gcalit-balance-sheet/** (repo
`opheliaclarke/gcalit-balance-sheet`, Pages from `main` `/docs`, `robots.txt` disallow-all +
`noindex` so it cannot be found by search).

## THE ANSWER
| | |
|---|---|
| **Opening balance, 1 April 2025** | **$16,985.40** |
| **Closing balance, 31 March 2026** | **$30,420.88** |
| Net change | **+$13,435.48** |
| Money in | $33,264.06 (24) |
| Money out (all of it) | −$19,828.58 (14) — of which expenses −$19,306.43 (11), sent to card −$522.15 (3) |
| Card spend / refunds | −$622.15 (5) / +$100.00 (1) |

Accounts: Checking ••6538 (all the activity) · Savings ••7355 (zero throughout) ·
Mercury IO credit card account (opened 2025-05-11, zero at both year ends).

## CONNECTION — read-only API token, NOT a webhook
Mercury webhooks are forward-only push notifications; they cannot backfill a year that ended
five months ago, and neither can the Events API. A **Read Only** token can fetch everything,
cannot move money, and needs no IP whitelist (Read-and-Write does).
Token lives at `/root/.config/mercury/token.json` (600). **Never in the repo** —
`scripts/mercury.py` has `redact()` and `test/gate.sh` sweeps every tracked file for it.
⚠ Mercury auto-deletes a token unused for 45 days; one GET keeps it alive.

## ⚠ FOUR MERCURY TRAPS — encoded in `scripts/mercury.py`, do not undo
- **T1** `/account/{id}/transactions` defaults `start` to **30 days before today**. Omit it and
  you get a short list that reads as complete. Not used for the ledger.
- **T2 (decisive)** `/transactions` `start`/`end` filter **createdAt, not postedAt**, while the
  dashboard shows postedAt. A FY cut must use `postedStart`/`postedEnd`.
- **T3** `limit` maxes at 1000 **and defaults to 1000** — a full page is not the end. Follow the
  cursor to an empty page.
- **T4** the literal `secret-token:` prefix **is part of the credential**; a 401 usually means it
  was dropped, or the token was auto-deleted at 45 days idle.

## HOW THE TWO NUMBERS ARE PROVEN (all computed, none asserted)
- **A — statement (authority):** Mercury's own Mar-2025 / Mar-2026 statement `endingBalance`.
- **B — back-computed:** live balance today less everything posted after 31 Mar 2026.
- **C — forward:** opening + every transaction posted inside the year.
- **D — from account birth:** every transaction from 2024-08-07 to 31 Mar 2025.
- **E — monthly:** each of the 12 FY months against its own statement.
All agree to **$0.00**. Wider evidence in `scripts/evidence.py`, shown on the Reconciliation tab:
**48 of 48 statement-months tie**; **73 statement transaction ids ↔ 73 pulled rows, 0 missing,
0 orphans**; inception-to-date equals the live balance; **0** rows dropped from the year by the
status filter; 4 of 4 card payments mirrored; boundary safety margin **43.65 h** (3× the widest
timezone on earth).

## VERIFICATION (ultracode, 8 agents — 3 Fable 5 designs + judge, 3 verifiers + adjudicator)
Every dollar figure CONFIRMED by three independent recomputes plus a fourth adjudication, each
working from `raw/` by its own path. **Five real defects found and fixed — all labelling, none
arithmetic:**
1. **"TOTAL MONEY OUT −19,306.43" was a subtotal, not a total.** Card payments are real cash
   leaving the bank. True total **−19,828.58**; the split now sits under it as "of which".
   Subtracting the two old headline lines gave 13,957.63 — **$522.15 wrong**.
2. **Monthly and Summary used "Money out" for figures $522.15 apart.** Monthly now carries
   Expenses · Sent to card · **Total money out**, matching Summary word for word.
3. **`excluded[].postedAt` fabricated a posting date** for two rows that never posted
   (`postedAt or createdAt`). Now null, with `createdAt` as its own labelled field.
   Also: "2 excluded" read as *from the year* — **0** were; both failed rows are dated after FY end.
4. **"Card balance owed at year end = 0.00" was unaudited.** Now derived: the credit account
   opened 2025-05-11 and no card row posted before the FY, so opening liability is zero by
   construction. Stated on the Cards tab, with the caveat that cash and accrual coincide
   **this year only** because the card is zero at both cuts.
5. **Descriptions promised things not in the year** ("wires and wire fees" — there are none).
⚠ A verifier itself was wrong and was overruled: the 4 `GOOGLE; YOUTUBE_PA` credits ($639.74)
are **YouTube partner revenue, not refunds**. **Zero dollars of money-in are refunds**; only the
$7.82 cashback is non-revenue. Do not repeat that error.
⚠ Summing the whole Ledger amount column happens to give the right answer **only because the
card ledger nets to zero this year** — the forward-route formula now uses
`SUMIF(...,"<>Credit card",...)` so the control stays a control.

## THE PAGE
Fable 5, 3 directions → judged → "Precision Workbook". Real spreadsheet: column letters, row
numbers, frozen panes, ghost columns and rows to the fold, corner select-all, crosshair headers,
sheet tabs with row counts (Ctrl+PgUp/PgDn), live SUM·AVG·COUNT·MIN·MAX status bar, print
stylesheet. **The formula bar shows the real formula** on every derived cell — including the
cross-sheet reconciliation `=Summary!D2+SUMIF(Ledger!B2:B48,"<>Credit card",Ledger!G2:G48)`.
**Copying:** click / shift-click / drag / Ctrl+A, then Ctrl+C. Two clipboard payloads —
`text/plain` raw TSV (no `$`, no separators, ASCII hyphen, so Excel parses numbers) and
`text/html` typed table. Plus `Copy sheet`, `Copy all`, `.xlsx`, `.csv`.
⚠ Screen shows U+2212 minus; the clipboard always uses ASCII hyphen. Do not unify them.
⚠ Text cells are `white-space:pre` — the Summary indents sub-lines with leading spaces so they
indent in Excel too, and `nowrap` collapses them.

## THE .XLSX
Hand-written OOXML (zip + XML, no library). Six sheets, content-fit column widths, and **97 live
formulas** so the file recalculates in Excel instead of being frozen values.
`test/test_formulas.py` evaluates every one against the published value — **97/97**, with a
negative control proving the evaluator can fail.

## BUILD GATE — `./test/gate.sh`
rebuild → formulas recalculate → xlsx opens in openpyxl → **docs/ byte-identical to out/** →
page payload identical to the workbook → Summary and Monthly agree → opening+net=closing →
no secret in any tracked file (with a positive control). **Every check proven able to fail.**
Run it before every publish; the stale-artifact check exists because a stale `site/` nearly
shipped the $522.15-short total.

## SECURITY
- `raw/` is **gitignored** — it carries the full account and routing numbers. The page and the
  workbook carry neither (only the ••last-4 names Mercury itself uses).
- `.gstack/` is gitignored — gstack browse writes a live terminal token there.
- GitHub push protection blocked the first push over **Mercury's own example tokens** in the
  mirrored docs; they were redacted rather than allow-listed. Our token was never in the tree.
- ⚠ **The live URL is public to anyone who has it.** It is `noindex` + `robots: Disallow: /`, but
  a public GitHub Pages site is not access-controlled. Raised with Bob; a Cloudflare Worker
  login gate (as on snow-safari) is ~15 minutes if he wants one.

## FILES
`scripts/mercury.py` read-only client · `build.py` engine + 4-route reconciliation ·
`monthly.py` month-by-month · `evidence.py` completeness proofs · `sheets.py` workbook + xlsx ·
`formulas.py` the single formula map shared by page and xlsx · `generate.py` + `page.html` the page.
`reference/` Mercury API docs as mirrored 2026-08-23. `test/` the gate and the formula evaluator.

## OPEN
1. Bob's call on the login gate for the live URL.
2. If this becomes a recurring report, one GET every 45 days keeps the token alive.
