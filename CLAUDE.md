# gcalit-balance-sheet — GCALIT LLC · Mercury Bank

**TWO PAGES ON ONE SITE.** Repo `opheliaclarke/gcalit-balance-sheet`, Pages from `main` `/docs`,
`robots.txt` disallow-all + `noindex` on both. They link to each other from the toolbar.

| | |
|---|---|
| **Page 1 — FY 1 Apr 2025 → 31 Mar 2026** | https://opheliaclarke.github.io/gcalit-balance-sheet/ |
| **Page 2 — calendar year 1 Jan → 31 Dec 2025 + PEAK BALANCE** | https://opheliaclarke.github.io/gcalit-balance-sheet/2/ |

**Status 2026-08-23: page 1 DELIVERED. 2026-08-28: page 2 DELIVERED.**

## PAGE 2 — THE ANSWER (calendar 2025)
| | |
|---|---|
| **Opening balance, 1 January 2025** | **$11,053.84** |
| **Closing balance, 31 December 2025** | **$32,120.51** |
| Net change | **+$21,066.67** |
| **PEAK BALANCE** | **$35,157.93** |
| **Date of peak** | **31 July 2025** (held 4 days, to 3 Aug) |
| Money in | $36,730.05 (22) |
| Money out (all of it) | −$15,663.38 (11) — expenses −$15,341.23 (9), sent to card −$322.15 (2) |
| Lowest balance | $11,053.84 on 1 Jan 2025 · average daily $26,110.17 |
| Card | spend −$322.15, refunds $0.00, owed at both cuts $0.00 |

Peak was caused by a **$750.00 incoming international wire from CLICKSTACK LTD.** on 31 Jul 2025,
on top of $34,407.93. It broke on 4 Aug when Google CL took −$6,600.54 → $28,557.39.
33 bank transactions in the year (38 rows pulled, 5 of them on the card ledger).

**Eight sheets:** Summary · Peak · **Daily (all 365 end-of-day balances — the peak is the max of
that column)** · Monthly · Ledger · Card · Reconciliation · Accounts.

### How page 2 is built — DO NOT hand-edit it
`scripts/pull_cy2025.py` (read-only pull → `raw-cy2025/`, gitignored) → `scripts/cy2025.py`
(ledger, running balance, peak, **14 proofs — exits 1 on any failure**) → `scripts/sheets_cy2025.py`
(8 sheets + xlsx + csv, reusing `sheets.py`'s OOXML writer) → `scripts/generate_cy2025.py`.
⚠ **Page 2 is GENERATED FROM `scripts/page.html`**, page 1's template, by seven **asserted**
substitutions. Change a substituted line on page 1 and page 2's build fails loudly instead of
shipping with page 1's dates on it.

### ⚠ THE DEFECT THIS BUILD SHIPPED AND FIXED — the FY build's defect #1, repeating
The first pass classified card payments by looking for `"credit card"` in the description. The two
real ones are counterparty **`Mercury Credit`, memo `IO AUTOPAY`** — so both were missed, "sent to
card" read **$0.00**, and TOTAL MONEY OUT became a subtotal again. Now a payment is identified by
its **mirror on the card ledger** (same day, equal and opposite), which is provable; check M
asserts `expenses + sent to card == total money out`, and check K asserts every card credit found
its bank-side row. **Never go back to a substring.**

### ⚠ ADVERSARIAL VERIFICATION 2026-08-28 — all 14 figures CONFIRMED, 10 defects fixed
An independent agent recomputed every published figure from `raw-cy2025/` by its own routes.
**Nothing disputed on the numbers.** It also proved things the build did not: **all 24 statements
Aug-2024→Jul-2026 reconcile, not just the 12**; the intra-day upper bound over *every possible*
within-day ordering is 35,157.93, so no ordering can beat the end-of-day peak; and only 4 days in
2025 had more than one transaction, none near the peak.
🛑 **The defect that mattered: the counterparty column was showing the account owner's PRIVATE
NICKNAME as the payee** — `Google LLC` published as **`Google CL`** on 8 rows carrying **$15,251.23
= 99.4% of the expense figure**, and `Books & Counts LLC` as `Raunac CA`. Page 1 had them right, so
page 2 contradicted it. `describe()` takes **`counterpartyName`**, never `counterpartyNickname`;
the nickname, where it differs, goes in the description as *"your label: …"*. **Gated, with a
vacuity guard** (the check asserts it examined 38 rows).
🛑 **The workbook had ZERO formulas, so its MATCH verdicts were static text that could not fail.**
It now carries **503 live formulas** — the peak reads **`=MAX(Daily!E2:E366)`**, the whole 365-row
daily column, the ledger running balance and the monthly roll are live, and every Check is
`=IF(F=G,"MATCH","MISMATCH")`. `test/test_formulas.py` takes a workbook path now and proves all
503 recalculate, with two controls (a wrong formula, and MAX over an empty range).
Other fixes: counts were formatted as money (`33.00` beside `32,120.51`) — **`int` columns now get
`#,##0`, which fixes page 1 too** (values unchanged, format only) · the money-out split was listed
twice so reading the column down double-counted · route letters ran A,A,B,C,D,E,**L** → now A–G ·
the createdAt-vs-postedAt evidence compared two dumps that come back **byte-identical**, so it
could not fail — it now tests the property directly and names the 5 rows that straddle a day ·
"Caused by" overstated the $750 wire (the balance was already at its running high) → "Tipped to
the peak by" · the card's opening balance is blank, not `0.00`, for an account that did not exist
on 1 January · a **"Total expense incurred"** line separates what was SPENT ($15,663.38, bank +
card) from what was MOVED to settle the card.
⚠ **A build assertion caps our own prose at 140 characters** — text cells are `white-space:pre`, so
one long sentence widened its column and pushed the money columns off a 1600px screen. Mercury's
own memo text on the Ledger is data and is exempt.
⚠ **A negative control caught a real bug in a check of my own**: an over-escaped regex inside a
shell heredoc (`\\d` became a literal backslash) made the nickname check match nothing and pass
vacuously. The `assert checked==38` line is what exposed it. Every check needs one.

### ⚠ THE CLOCK — stated, not assumed
Every date is **UTC**, the basis all 24 of Mercury's own statements reconcile on. Margins are
computed, not asserted: **163.57 h** at the start of the year, **12.01 h** at the end — but only
**2.03 h on the PEAK DATE**. The peak AMOUNT is clock-independent; read on a clock more than 2.03 h
ahead of UTC — **India (+5:30) among them** — the same credit falls on **1 August**. Said plainly
on both the Peak and Reconciliation sheets.

### PEAK — the two guards that make the figure meaningful
- **P1** the running balance starts from **Mercury's own Dec-2024 statement `endingBalance`**, not
  from a derived opening.
- **P2** the headline is the **end-of-day** peak, because that is what a bank reports. The
  intra-day high in Mercury's own posting order is computed separately and is the **same figure**
  this year, so the distinction changes nothing — but it is stated on the page rather than assumed.
- ⚠ A count must not sit in a money column: the "days at or above $X" rows carry the **threshold**
  in Amount and the **day count as words** in the Date column. First pass rendered `4.00` under
  "Amount (USD)".

### BUILD GATE — `./test/gate_cy2025.sh` (16 checks, every one proven able to fail)
rebuild → xlsx opens in openpyxl → **docs/2 byte-identical to out-cy2025/** → page payload
identical to the workbook → opening+net=closing → **peak = max of the 365 daily balances and the
row flagged PEAK is the first day holding it** → the peak agrees on Summary, the Peak tab and the
band → money out is a total not a subtotal → both pages link to each other → **page 2 carries no
page-1 dates** → **503 formulas recalculate** → **counterparty is the payee of record, not a
nickname** → **no bare count in a money column** → no secret or account number in the tree.
Run it **and `./test/gate.sh`** before any publish.

⚠ Page 1 was left alone: its embedded payload is byte-identical, and the only HTML diff is
**9 added lines** — the link to page 2, its stylesheet, and `.fbar{overflow-x:auto}` so the widened
toolbar can scroll on a phone. Its workbook changed in exactly one way, verified cell by cell with
openpyxl: **0 value changes**, and the count columns moved from money format to `#,##0`.

---

## PAGE 1 — FY 1 Apr 2025 → 31 Mar 2026

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
`reference/` Mercury API docs as mirrored 2026-08-23. `test/` the gates and the formula evaluator.

## PAGE 2 FILES
`pull_cy2025.py` · `cy2025.py` · `sheets_cy2025.py` · `generate_cy2025.py` · `test/gate_cy2025.sh`.
Raw pull in `raw-cy2025/` and the intermediate `out-cy2025/cy2025.json` are **gitignored** (account
and routing numbers, Mercury dashboard links). The published workbook and CSVs carry neither.

## OPEN
1. Bob's call on the login gate for the live URL.
2. If this becomes a recurring report, one GET every 45 days keeps the token alive.
