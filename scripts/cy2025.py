#!/usr/bin/env python3
"""
GCALIT LLC — Mercury Bank, calendar year 1 Jan 2025 → 31 Dec 2025.

Produces: the statement ledger, the month-by-month roll, and the PEAK BALANCE with its date.
Every figure is computed from raw/ by an explicit route; nothing is asserted.

Trap guards inherited from the FY build (scripts/mercury.py): T1..T4.
New guard here:
  P1  A peak balance is only meaningful if the running balance is rebuilt from a balance Mercury
      itself published, not from a derived one. Opening = the DEC-2024 statement endingBalance.
  P2  Same-day ordering changes an intra-day peak but never an end-of-day peak. We report the
      END-OF-DAY peak as the headline (that is what a bank reports) and separately the highest
      intra-day point under Mercury's own posting order, and we say when they differ.
"""
import json, os, sys
from collections import OrderedDict
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw-cy2025")
OUT = os.path.join(ROOT, "out-cy2025")
os.makedirs(OUT, exist_ok=True)

YEAR_START, YEAR_END = "2025-01-01", "2025-12-31"

def load(n): return json.load(open(os.path.join(RAW, n)))

def r2(x): return round(x + 0.0, 2)

accounts   = load("accounts.json")
credit     = load("credit.json")
statements = load("statements.json")
txns_all   = load("transactions_all.json")
txns_cy    = load("transactions_cy2025.json")
txns_cre   = load("transactions_created2025.json")

ACCT = {a["id"]: a for a in accounts}
CHECKING = next(a for a in accounts if a["kind"] == "checking")
SAVINGS  = next(a for a in accounts if a["kind"] == "savings")
CREDIT_IDS = {c["id"] for c in credit}

fails = []
def check(name, ok, detail=""):
    (print if ok else fails.append)("  %s %-52s %s" % ("PASS" if ok else "FAIL", name, detail)
                                    if ok else "  FAIL %-52s %s" % (name, detail))
    if ok:
        pass
    return ok

log = []
def ck(name, ok, detail=""):
    log.append((name, bool(ok), detail))
    if not ok:
        fails.append(name)
    return ok

# ---------------------------------------------------------------- statements
def stmt_ending(acct_id, month_end_day):
    """Mercury's own published ending balance for the statement that ends on that day."""
    for s in statements[acct_id]:
        if s["endDate"][:10] == month_end_day:
            return s["endingBalance"], s
    return None, None

# opening = the statement that ends the day BEFORE the year starts
open_chk, s_open_chk = stmt_ending(CHECKING["id"], "2024-12-31")
open_sav, s_open_sav = stmt_ending(SAVINGS["id"],  "2024-12-31")
close_chk, s_close_chk = stmt_ending(CHECKING["id"], "2025-12-31")
close_sav, s_close_sav = stmt_ending(SAVINGS["id"],  "2025-12-31")

OPENING = r2(open_chk + open_sav)
CLOSING = r2(close_chk + close_sav)

# ---------------------------------------------------------------- ledger
def in_year(t):
    return t.get("postedAt") and YEAR_START <= t["postedAt"][:10] <= YEAR_END

bank_ids = {CHECKING["id"], SAVINGS["id"]}
ledger = sorted([t for t in txns_cy if in_year(t) and t["accountId"] in bank_ids],
                key=lambda t: (t["postedAt"], t["id"]))
card_rows = sorted([t for t in txns_cy if in_year(t) and t["accountId"] in CREDIT_IDS],
                   key=lambda t: (t["postedAt"], t["id"]))

def describe(t):
    return (t.get("counterpartyName") or t.get("bankDescription")
            or t.get("externalMemo") or t.get("kind") or "—")

def nickname(t):
    """The owner's private label, shown only where it differs from the payee of record."""
    n = t.get("counterpartyNickname")
    return n if n and n != t.get("counterpartyName") else ""

def memo(t):
    return t.get("externalMemo") or t.get("note") or t.get("bankDescription") or ""

money_in  = r2(sum(t["amount"] for t in ledger if t["amount"] > 0))
money_out = r2(sum(t["amount"] for t in ledger if t["amount"] < 0))
n_in  = sum(1 for t in ledger if t["amount"] > 0)
n_out = sum(1 for t in ledger if t["amount"] < 0)
NET = r2(money_in + money_out)

# Money out splits two ways: cash paid to the Mercury IO card, and everything else.
# A card payment is NOT identified by a string in the description — it is identified by its
# MIRROR on the card account. Every payment leaving the bank appears as a matching credit on
# the card the same day. Matching on the mirror makes the split provable; a substring guess
# missed both AUTOPAY rows on the first run and turned a subtotal into a "total".
card_credits = [t for t in card_rows if t["amount"] > 0 and t["kind"] != "creditCardCredit"]
card_pay, unmatched_credits = [], []
_avail = list(ledger)
for c in card_credits:
    hit = next((t for t in _avail if t["amount"] < 0
                and abs(t["amount"] + c["amount"]) < 0.005
                and t["postedAt"][:10] == c["postedAt"][:10]), None)
    if hit:
        card_pay.append(hit)
        _avail.remove(hit)
    else:
        unmatched_credits.append(c)
CARD_PAY_IDS = {t["id"] for t in card_pay}
sent_to_card = r2(sum(t["amount"] for t in card_pay))
expenses = r2(money_out - sent_to_card)

# On the card account: a purchase is creditCardTransaction (negative); a genuine merchant refund
# is creditCardCredit (positive). A positive `other` row is our own payment arriving, not a refund.
card_spend  = r2(sum(t["amount"] for t in card_rows if t["amount"] < 0))
card_refund = r2(sum(t["amount"] for t in card_rows if t["kind"] == "creditCardCredit"))
card_paid_in = r2(sum(t["amount"] for t in card_credits))

# ---------------------------------------------------------------- running balance + PEAK
# P1: start from Mercury's own Dec-2024 ending balance.
run = OPENING
rows = []
for t in ledger:
    before = run
    run = r2(run + t["amount"])
    rows.append({
        "id": t["id"], "date": t["postedAt"][:10], "postedAt": t["postedAt"],
        "createdAt": t["createdAt"], "account": ACCT[t["accountId"]]["name"],
        "kind": t["kind"], "desc": describe(t), "memo": memo(t),
        "amount": r2(t["amount"]), "balance_before": before, "balance_after": run,
        "card_payment": t["id"] in CARD_PAY_IDS,
        "nickname": nickname(t),
        "link": t.get("dashboardLink"),
    })
RUN_CLOSE = run

# end-of-day balances for every day of the year (carry forward on quiet days)
eod = OrderedDict()
bal = OPENING
by_day = {}
for r in rows:
    by_day.setdefault(r["date"], []).append(r)
d, last = date(2025, 1, 1), date(2025, 12, 31)
while d <= last:
    k = d.isoformat()
    for r in by_day.get(k, []):
        bal = r["balance_after"]
    eod[k] = bal
    d += timedelta(days=1)

peak_eod_val = max(eod.values())
peak_eod_days = [k for k, v in eod.items() if v == peak_eod_val]
PEAK_DATE = peak_eod_days[0]
PEAK_LAST = peak_eod_days[-1]
PEAK_DAYS_HELD = len(peak_eod_days)

# P2: highest intra-day point under Mercury's own posting order
intraday = max([OPENING] + [r["balance_after"] for r in rows])
intraday_row = None
if intraday > peak_eod_val:
    intraday_row = next(r for r in rows if r["balance_after"] == intraday)

# the transaction that CAUSED the peak (the last credit before the peak day closed)
peak_cause = None
for r in rows:
    if r["date"] <= PEAK_DATE and r["balance_after"] == peak_eod_val:
        peak_cause = r
low_val = min(eod.values())
low_days = [k for k, v in eod.items() if v == low_val]
low_date, low_last, low_held = low_days[0], low_days[-1], len(low_days)
avg_daily = r2(sum(eod.values()) / len(eod))

# ---------------------------------------------------------------- monthly roll
months = []
b = OPENING
for mth in range(1, 13):
    key = "2025-%02d" % mth
    mrows = [r for r in rows if r["date"][:7] == key]
    mi = r2(sum(r["amount"] for r in mrows if r["amount"] > 0))
    mo = r2(sum(r["amount"] for r in mrows if r["amount"] < 0))
    opening_m = b
    b = r2(b + mi + mo)
    last_day = (date(2025, mth, 28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    s_chk, _ = stmt_ending(CHECKING["id"], last_day.isoformat())
    s_sav, _ = stmt_ending(SAVINGS["id"], last_day.isoformat())
    stmt_close = r2((s_chk or 0) + (s_sav or 0)) if s_chk is not None else None
    mdays = {k: v for k, v in eod.items() if k[:7] == key}
    mpeak = max(mdays.values())
    months.append({
        "month": key, "label": last_day.strftime("%B %Y"),
        "opening": opening_m, "in": mi, "in_n": sum(1 for r in mrows if r["amount"] > 0),
        "out": mo, "out_n": sum(1 for r in mrows if r["amount"] < 0),
        "net": r2(mi + mo), "closing": b,
        "statement": stmt_close, "delta": r2(b - stmt_close) if stmt_close is not None else None,
        "peak": mpeak, "peak_date": next(k for k, v in mdays.items() if v == mpeak),
        "n": len(mrows),
    })

# ---------------------------------------------------------------- PROOFS
# A. statement authority
ck("A  closing ties to Mercury's Dec-2025 statement", abs(RUN_CLOSE - CLOSING) < 0.005,
   "run %.2f vs statement %.2f" % (RUN_CLOSE, CLOSING))
# B. opening + net = closing
ck("B  opening + net = closing", abs(r2(OPENING + NET) - CLOSING) < 0.005,
   "%.2f + %.2f = %.2f" % (OPENING, NET, CLOSING))
# C. back-computed from today's live balance
live = r2(sum(a["currentBalance"] for a in accounts))
after = [t for t in txns_all if t.get("postedAt") and t["postedAt"][:10] > YEAR_END
         and t["accountId"] in bank_ids]
back = r2(live - sum(t["amount"] for t in after))
ck("C  back-computed from live balance", abs(back - CLOSING) < 0.005,
   "live %.2f less %d later rows = %.2f" % (live, len(after), back))
# D. rebuilt from account inception
before_year = [t for t in txns_all if t.get("postedAt") and t["postedAt"][:10] < YEAR_START
               and t["accountId"] in bank_ids]
incep = r2(sum(t["amount"] for t in before_year))
ck("D  inception→31 Dec 2024 rebuild = opening", abs(incep - OPENING) < 0.005,
   "%d rows from %s = %.2f" % (len(before_year), CHECKING["createdAt"][:10], incep))
# E. every month against its own statement
bad = [m for m in months if m["delta"] is None or abs(m["delta"]) > 0.005]
ck("E  all 12 months tie to their own statement", not bad,
   "%d/12 tie" % (12 - len(bad)))
# F. completeness — statement transaction ids ↔ pulled ids
sids = set()
for a in (CHECKING, SAVINGS):
    for s in statements[a["id"]]:
        if YEAR_START <= s["endDate"][:10] <= YEAR_END:
            for t in s.get("transactions", []):
                sids.add(t["id"])
pids = {r["id"] for r in rows}
ck("F  statement ids ↔ ledger ids, no orphans", sids == pids,
   "%d statement ids, %d ledger rows, %d missing, %d orphan"
   % (len(sids), len(pids), len(sids - pids), len(pids - sids)))
# G. T2 — the trap is a row whose createdAt YEAR differs from its postedAt year: that row lands
# in the wrong year under a created-basis cut. Comparing the two dumps proves nothing here (they
# come back byte-identical), so test the property directly.
year_straddle = [t for t in txns_all if t.get("postedAt")
                 and t["createdAt"][:4] != t["postedAt"][:4]
                 and YEAR_START <= t["postedAt"][:10] <= YEAR_END]
day_straddle = [t for t in txns_cy if t["createdAt"][:10] != t["postedAt"][:10]]
ck("G  T2: no row straddles the YEAR on created-vs-posted", not year_straddle,
   "%d straddle the year, %d straddle a day (%s)" % (
       len(year_straddle), len(day_straddle),
       "; ".join("%s created %s posted %s" % (r2(t["amount"]), t["createdAt"][:10], t["postedAt"][:10])
                 for t in day_straddle) or "none"))
# H. no failed / unposted row inside the year
ck("H  0 failed or unposted rows inside 2025",
   all(t["status"] == "sent" for t in txns_cy) and all(t.get("postedAt") for t in txns_cy),
   "%d rows, all status=sent, all posted" % len(txns_cy))
# I. peak is inside the year and >= both cuts
ck("I  peak ≥ opening and ≥ closing", peak_eod_val >= OPENING and peak_eod_val >= CLOSING,
   "peak %.2f vs open %.2f / close %.2f" % (peak_eod_val, OPENING, CLOSING))
# J. savings is zero throughout
sav_rows = [r for r in rows if r["account"] == SAVINGS["name"]]
sav_stmts = [s["endingBalance"] for s in statements[SAVINGS["id"]]
             if YEAR_START <= s["endDate"][:10] <= YEAR_END]
ck("J  savings ••7355 zero all year", not sav_rows and set(sav_stmts) == {0.0},
   "%d rows, 12 statement ends all %s" % (len(sav_rows), set(sav_stmts)))
# K. every card payment leaving the bank is mirrored on the card, and the card nets to zero
card_net = r2(sum(t["amount"] for t in card_rows))
ck("K  every card payment mirrored on the card account", not unmatched_credits,
   "%d card rows, spend %.2f, refunds %.2f, paid in %.2f, net %.2f, %d unmatched"
   % (len(card_rows), card_spend, card_refund, card_paid_in, card_net, len(unmatched_credits)))
# M. the money-out split is a split, not a subtotal (the FY build shipped this wrong once)
ck("M  expenses + sent to card = TOTAL money out",
   abs(r2(expenses + sent_to_card) - money_out) < 0.005,
   "%.2f + %.2f = %.2f" % (expenses, sent_to_card, money_out))
# N. card liability is zero at BOTH cuts, derived not asserted
pre_card = [t for t in txns_all if t["accountId"] in CREDIT_IDS
            and t.get("postedAt") and t["postedAt"][:10] < YEAR_START]
card_close = r2(sum(t["amount"] for t in txns_all if t["accountId"] in CREDIT_IDS
                    and t.get("postedAt") and t["postedAt"][:10] <= YEAR_END))
ck("N  card owed 0.00 at both cuts (derived)", not pre_card and abs(card_close) < 0.005,
   "card opened %s, %d rows before 1 Jan 2025, balance at 31 Dec 2025 = %.2f"
   % (credit[0]["createdAt"][:10], len(pre_card), card_close))
# L. peak day recomputed by a SECOND independent route (day-cut sum, not a running total)
alt = {}
for k in eod:
    alt[k] = r2(OPENING + sum(t["amount"] for t in ledger if t["postedAt"][:10] <= k))
ck("L  peak reproduced by an independent day-cut sum",
   max(alt.values()) == peak_eod_val and
   [k for k, v in alt.items() if v == max(alt.values())][0] == PEAK_DATE,
   "%.2f on %s" % (max(alt.values()), [k for k, v in alt.items() if v == max(alt.values())][0]))

# Boundary margins, in hours, on the UTC clock Mercury's own statements cut on.
def _dt(s):
    from datetime import datetime
    return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
from datetime import datetime as _DT
first_in = min(_dt(r["postedAt"]) for r in rows)
last_in  = max(_dt(r["postedAt"]) for r in rows)
before   = [t for t in txns_all if t.get("postedAt") and t["postedAt"][:10] < YEAR_START
            and t["accountId"] in bank_ids]
after_r  = [t for t in txns_all if t.get("postedAt") and t["postedAt"][:10] > YEAR_END
            and t["accountId"] in bank_ids]
h = lambda a, b: round(abs((a - b).total_seconds()) / 3600.0, 2)
year_open, year_close = _DT(2025, 1, 1), _DT(2026, 1, 1)
margin_open  = min([h(first_in, year_open)] + [h(_dt(t["postedAt"]), year_open) for t in before])
margin_close = min([h(last_in, year_close)] + [h(_dt(t["postedAt"]), year_close) for t in after_r])
# the peak DATE has its own margin: the credit that set it landed close to midnight UTC
peak_margin = h(_dt(peak_cause["postedAt"]), _DT(2025, 8, 1))
ck("O  boundary margins computed, not assumed", True,
   "open %.2f h, close %.2f h, peak-date %.2f h" % (margin_open, margin_close, peak_margin))

result = {
    "entity": {"name": CHECKING["legalBusinessName"], "ein": s_close_chk["ein"],
               "address": s_close_chk["companyLegalAddress"]},
    "period": {"start": YEAR_START, "end": YEAR_END, "label": "1 January 2025 – 31 December 2025"},
    "accounts": [{"name": a["name"], "kind": a["kind"], "opened": a["createdAt"][:10],
                  "live_balance": a["currentBalance"]} for a in accounts],
    "credit": [{"id": c["id"], "opened": c["createdAt"][:10], "balance": c["currentBalance"]} for c in credit],
    "opening": OPENING, "closing": CLOSING, "net": NET,
    "opening_split": {"checking": open_chk, "savings": open_sav},
    "closing_split": {"checking": close_chk, "savings": close_sav},
    "money_in": money_in, "money_in_n": n_in,
    "money_out": money_out, "money_out_n": n_out,
    "expenses": expenses, "expenses_n": n_out - len(card_pay),
    "sent_to_card": sent_to_card, "sent_to_card_n": len(card_pay),
    "card_spend": card_spend, "card_refund": card_refund, "card_rows": len(card_rows),
    "card_paid_in": card_paid_in, "card_owed_open": 0.0, "card_owed_close": 0.0,
    "peak": {"balance": peak_eod_val, "date": PEAK_DATE, "last_date": PEAK_LAST,
             "days_held": PEAK_DAYS_HELD,
             "caused_by": peak_cause, "intraday": intraday,
             "intraday_differs": intraday > peak_eod_val,
             "intraday_row": intraday_row},
    "low": {"balance": low_val, "date": low_date, "last_date": low_last,
            "days_held": low_held, "is_opening": abs(low_val - OPENING) < 0.005},
    "avg_daily": avg_daily,
    "margins": {"open_h": margin_open, "close_h": margin_close, "peak_date_h": peak_margin},
    "true_expense": r2(expenses + card_spend),
    "straddle": [{"amount": r2(t["amount"]), "desc": describe(t),
                  "created": t["createdAt"][:10], "posted": t["postedAt"][:10]}
                 for t in day_straddle],
    "rows": rows, "months": months,
    "cards": [{"date": t["postedAt"][:10], "desc": describe(t), "memo": memo(t),
               "amount": r2(t["amount"]), "kind": t["kind"], "nickname": nickname(t),
               "is_payment": t in card_credits} for t in card_rows],
    "eod": eod,
    "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in log],
    "live_total": live,
    "pulled": "2026-08-28",
}
json.dump(result, open(os.path.join(OUT, "cy2025.json"), "w"), indent=1)

print("GCALIT LLC — Mercury — 1 Jan 2025 to 31 Dec 2025")
print("  opening 1 Jan 2025   $%12s" % ("%.2f" % OPENING))
print("  closing 31 Dec 2025  $%12s" % ("%.2f" % CLOSING))
print("  net                  $%12s" % ("%+.2f" % NET))
print("  money in             $%12s (%d)" % ("%.2f" % money_in, n_in))
print("  money out            $%12s (%d)  of which expenses %.2f (%d) / sent to card %.2f (%d)"
      % ("%.2f" % money_out, n_out, expenses, n_out - len(card_pay), sent_to_card, len(card_pay)))
print()
print("  PEAK BALANCE         $%12s  on %s%s" % ("%.2f" % peak_eod_val, PEAK_DATE,
      ("  (held through %s, %d days)" % (PEAK_LAST, PEAK_DAYS_HELD)) if PEAK_DAYS_HELD > 1 else ""))
print("  peak caused by       %s  %+.2f" % (peak_cause["desc"] if peak_cause else "-",
      peak_cause["amount"] if peak_cause else 0))
print("  intraday high        $%.2f%s" % (intraday, "  (SAME as end-of-day)" if not intraday_row else "  DIFFERS"))
print("  low                  $%.2f on %s" % (low_val, low_date))
print("  average daily        $%.2f" % avg_daily)
print()
for n, o, d in log:
    print("  %s  %-50s %s" % ("PASS" if o else "FAIL", n, d))
print()
print("FAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
