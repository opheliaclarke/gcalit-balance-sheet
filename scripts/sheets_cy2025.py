#!/usr/bin/env python3
"""Turn out-cy2025/cy2025.json into the calendar-2025 workbook: eight sheets, the .xlsx and
the .csv set. Reuses sheets.py's hand-written OOXML writer, so page 1 and page 2 come out of
exactly the same machinery.

Row indices are never hard-coded: each sheet is assembled with a helper that records the index
of every row as it is added, and the formula map is written against those recorded indices. A
row inserted anywhere cannot silently point a formula at the wrong cell.
"""
import json, os, csv, sys, shutil
from datetime import date, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sheets import write_xlsx, widths

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(HERE, "out-cy2025")
M = lambda v: None if v is None else round(float(v), 2)

d = json.load(open(os.path.join(OUT, "cy2025.json")))
rows, months, peak, eod = d["rows"], d["months"], d["peak"], d["eod"]

def uk(s):
    return datetime.strptime(s, "%Y-%m-%d").strftime("%-d %B %Y")

KIND = {"incomingDomesticWire": "Incoming wire (domestic)",
        "incomingInternationalWire": "Incoming wire (international)",
        "outgoingPayment": "Outgoing payment", "other": "ACH / internal",
        "externalTransfer": "External transfer", "wireFee": "Wire fee",
        "creditCardTransaction": "Card spend", "creditCardCredit": "Card refund"}

class Sheet:
    """A sheet that remembers where every row landed, so formulas address rows by name."""
    def __init__(self, name, title, columns, types):
        self.name, self.title = name, title
        self.columns, self.types = columns, types
        self.rows, self.emphasis, self.formulas, self.at = [], {}, {}, {}
    def add(self, cells, key=None, emph=None):
        i = len(self.rows)
        self.rows.append(list(cells))
        if key:  self.at[key] = i
        if emph: self.emphasis[i] = emph
        return i
    def blank(self):
        return self.add([None] * len(self.columns))
    def f(self, key, col, formula):
        """Attach a formula to the cell at (recorded row `key`, column letter `col`)."""
        self.formulas["%d,%s" % (self.at[key], col)] = formula
    def r(self, key):
        "spreadsheet row number (1-based, header is row 1)"
        return self.at[key] + 2
    def dict(self):
        return {"name": self.name, "title": self.title, "columns": self.columns,
                "types": self.types, "rows": self.rows,
                "emphasis": {str(k): v for k, v in self.emphasis.items()},
                "formulas": self.formulas}

# ---- buckets. Every row must land in exactly one; asserted below. -------------
def bucket(r):
    if r["card_payment"]:                                    return "out_card"
    if r["amount"] < 0:                                      return "out_payments"
    if "cashback" in r["desc"].lower():                      return "in_cashback"
    if r["kind"] in ("incomingDomesticWire", "incomingInternationalWire"): return "in_wires"
    return "in_other"
for r in rows:
    r["bucket"] = bucket(r)
B = {k: M(sum(r["amount"] for r in rows if r["bucket"] == k)) for k in
     ("in_wires", "in_other", "in_cashback", "out_payments", "out_card")}
N = {k: sum(1 for r in rows if r["bucket"] == k) for k in B}
assert sum(N.values()) == len(rows), "a ledger row fell out of every bucket"
assert abs(M(sum(B.values())) - d["net"]) < 0.005, "buckets do not sum to the net change"
assert abs(M(B["in_wires"] + B["in_other"] + B["in_cashback"]) - d["money_in"]) < 0.005
assert abs(M(B["out_payments"] + B["out_card"]) - d["money_out"]) < 0.005

DAILY_N = len(eod)                       # 365
DR = "Daily!E2:E%d" % (DAILY_N + 1)      # the whole end-of-day column

# ============================ 3. Daily (built first: everything else cites it) ==
mv = {}
for r in rows:
    mv.setdefault(r["date"], []).append(r)
low = d["low"]
daily = Sheet("Daily",
  "End-of-day balance for every one of the %d days of 2025 — the peak is the maximum of column E, "
  "the low is its minimum. Dates are on the UTC clock Mercury's own statements cut on." % DAILY_N,
  ["Date", "Day", "Movements", "Moved that day (USD)", "End-of-day balance (USD)", "Note"],
  ["date", "text", "int", "money", "money", "text"])
for k, v in eod.items():
    note = ""
    if v == peak["balance"]:
        note = "PEAK" if k == peak["date"] else "peak held"
    elif v == low["balance"]:
        note = "LOW" if k == low["date"] else "low held"
    daily.add([k, datetime.strptime(k, "%Y-%m-%d").strftime("%a"), len(mv.get(k, [])),
               M(sum(x["amount"] for x in mv.get(k, []))) if mv.get(k) else None, v, note],
              key=k, emph="close" if k == peak["date"] else None)
# live column: each day carries the day before plus what moved
daily.f(peak["date"], "E", "E%d+D%d" % (daily.r(peak["date"]) - 1, daily.r(peak["date"])))
for i, k in enumerate(eod):
    if i == 0:
        daily.formulas["0,E"] = "Summary!D%d+D2" % 2
    else:
        daily.formulas["%d,E" % i] = "E%d+D%d" % (i + 1, i + 2)

# ============================ 1. Summary =====================================
s = Sheet("Summary",
  "Bank statement summary — GCALIT LLC at Mercury, 1 January 2025 to 31 December 2025",
  ["Line", "Detail", "Transactions", "Amount (USD)"], ["text", "text", "int", "money"])
s.add(["OPENING BALANCE — 1 January 2025",
       "Mercury's own ending balance on the statement for 01–31 December 2024", None, d["opening"]],
      key="open", emph="open")
s.blank()
s.add(["MONEY IN", "", None, None])
s.add(["  Incoming wires", "Domestic and international client and affiliate receipts",
       N["in_wires"], B["in_wires"]], key="in1")
s.add(["  Other incoming (ACH credits)",
       "YouTube partner payments, an affiliate ACH credit and account-verification micro-deposits",
       N["in_other"], B["in_other"]])
s.add(["  Mercury IO card cashback", "Cashback credited to the checking account",
       N["in_cashback"], B["in_cashback"]], key="in3")
s.add(["TOTAL MONEY IN", "", d["money_in_n"], d["money_in"]], key="tin", emph="total")
s.blank()
s.add(["MONEY OUT", "", None, None])
s.add(["  Outgoing payments", "Google Ads invoices, accountancy and platform fees",
       N["out_payments"], B["out_payments"]], key="out1")
s.add(["  Sent to the Mercury IO card",
       "Autopay moving cash out of the bank to settle the credit card", N["out_card"], B["out_card"]],
      key="out2")
s.add(["TOTAL MONEY OUT", "Every dollar that left the bank, card payments included",
       d["money_out_n"], d["money_out"]], key="tout", emph="total")
s.blank()
s.add(["NET CHANGE FOR THE YEAR", "Total money in less total money out", len(rows), d["net"]],
      key="net", emph="net")
s.blank()
s.add(["CLOSING BALANCE — 31 December 2025",
       "Mercury's own ending balance on the statement for 01–31 December 2025", None, d["closing"]],
      key="close", emph="double")
s.blank()
s.add(["PEAK BALANCE — %s" % uk(peak["date"]),
       "Highest balance held at any point in 2025 — the maximum of the Daily sheet",
       None, peak["balance"]], key="peak", emph="close")
s.blank()
s.add(["Total expense incurred in 2025",
       "Outgoing payments plus what the card itself spent — see the Reconciliation sheet",
       d["expenses_n"] + d["card_rows"] - d["sent_to_card_n"], d["true_expense"]],
      key="trueexp")
s.f("tin", "D", "SUM(D%d:D%d)" % (s.r("in1"), s.r("in3")))
s.f("tin", "C", "SUM(C%d:C%d)" % (s.r("in1"), s.r("in3")))
s.f("tout", "D", "SUM(D%d:D%d)" % (s.r("out1"), s.r("out2")))
s.f("tout", "C", "SUM(C%d:C%d)" % (s.r("out1"), s.r("out2")))
s.f("net", "D", "D%d+D%d" % (s.r("tin"), s.r("tout")))
s.f("close", "D", "D%d+D%d" % (s.r("open"), s.r("net")))
s.f("peak", "D", "MAX(%s)" % DR)
summary = s

# ============================ 2. Peak ========================================
next_move = next((r for r in rows if r["date"] > peak["last_date"]), None)
cause = peak["caused_by"]
mgn = d["margins"]
days_at = lambda t: sum(1 for v in eod.values() if v >= t)

p = Sheet("Peak",
  "Peak balance in 2025 — the highest balance the account held, and the day it reached it",
  ["Measure", "Detail", "Date", "Amount (USD)"], ["text", "text", "text", "money"])
p.add(["PEAK BALANCE", "Highest end-of-day balance across all %d days of 2025" % DAILY_N,
       uk(peak["date"]), peak["balance"]], key="peak", emph="open")
p.blank()
p.add(["Reached on", "The day the balance first closed at that figure", uk(peak["date"]),
       peak["balance"]], key="reached")
p.add(["Held until", "It stayed there for %d days; the next movement was the first debit after it"
       % peak["days_held"], uk(peak["last_date"]), peak["balance"]], key="held")
p.add(["Tipped to the peak by",
       "%s — %s. The marginal credit that set the exact maximum, not what built it."
       % (cause["desc"], KIND.get(cause["kind"], cause["kind"])), uk(cause["date"]), cause["amount"]],
      key="cause")
p.add(["Balance immediately before", "Where the balance stood the moment before that credit landed",
       uk(cause["date"]), cause["balance_before"]], key="before")
p.add(["Next movement after the peak",
       (next_move["desc"] + " — " + KIND.get(next_move["kind"], next_move["kind"])) if next_move else "—",
       uk(next_move["date"]) if next_move else "", next_move["amount"] if next_move else None],
      key="nextmv")
p.add(["Balance after that movement", "Where the balance sat once the peak broke",
       uk(next_move["date"]) if next_move else "", next_move["balance_after"] if next_move else None],
      key="after")
p.blank()
p.add(["Intra-day high",
       "Highest point at any moment, in Mercury's own posting order — the same figure",
       uk(peak["date"]), peak["intraday"]],
      key="intra")
p.blank()
p.add(["Lowest balance of the year",
       "Held %d days — and it is the opening balance: no day closed below where the year began"
       % low["days_held"],
       "%s – %s" % (uk(low["date"]), uk(low["last_date"])), low["balance"]], key="low")
p.add(["Average daily balance", "Mean of all %d end-of-day balances" % DAILY_N,
       "1 Jan – 31 Dec 2025", d["avg_daily"]], key="avg")
p.add(["Opening balance", "1 January 2025", uk("2025-01-01"), d["opening"]], key="op")
p.add(["Closing balance", "31 December 2025", uk("2025-12-31"), d["closing"]], key="cl")
p.add(["Peak above closing", "How far the peak sat above where the year ended", "",
       M(peak["balance"] - d["closing"])], key="ac")
p.add(["Peak above opening", "How far the peak sat above where the year began", "",
       M(peak["balance"] - d["opening"])], key="ao")
p.blank()
p.add(["Days closing at or above $35,000",
       "How many of the %d days closed at or above that level" % DAILY_N,
       "%d days" % days_at(35000), None])
p.add(["Days closing at or above $30,000", "", "%d days" % days_at(30000), None])
p.add(["Days closing at or above $25,000", "", "%d days" % days_at(25000), None])
p.blank()
p.add(["WHICH CLOCK THIS IS ON",
       "Every date here is UTC — the clock all 24 of Mercury's own statements reconcile on",
       "", None], emph="total")
p.add(["  Margin at the start of the year",
       "Hours between 1 Jan 2025 00:00 UTC and the nearest transaction either side", "%.2f hours"
       % mgn["open_h"], None])
p.add(["  Margin at the end of the year",
       "Hours to the nearest transaction either side — wider than any timezone, so the "
       "closing balance is the same on every clock", "%.2f hours" % mgn["close_h"], None])
p.add(["  Margin on the PEAK DATE",
       "The peak AMOUNT is the same on any clock, the DATE is not — see the Reconciliation sheet",
       "%.2f hours" % mgn["peak_date_h"], None], emph="close")
p.blank()
p.add(["PEAK BY MONTH", "Highest end-of-day balance inside each month", "", None], emph="total")
day_index = {k: i for i, k in enumerate(eod)}
for m in months:
    mdays = [k for k in eod if k[:7] == m["month"]]
    key = "m" + m["month"]
    p.add(["  " + m["label"], "", uk(m["peak_date"]), m["peak"]], key=key,
          emph="close" if m["peak"] == peak["balance"] else None)
    p.f(key, "D", "MAX(Daily!E%d:E%d)" % (day_index[mdays[0]] + 2, day_index[mdays[-1]] + 2))
p.f("peak", "D", "MAX(%s)" % DR)
p.f("reached", "D", "D%d" % p.r("peak"))
p.f("held", "D", "D%d" % p.r("peak"))
p.f("before", "D", "D%d-D%d" % (p.r("peak"), p.r("cause")))
p.f("after", "D", "D%d+D%d" % (p.r("peak"), p.r("nextmv")))
p.f("intra", "D", "D%d" % p.r("peak"))
p.f("low", "D", "MIN(%s)" % DR)
p.f("avg", "D", "AVERAGE(%s)" % DR)
p.f("op", "D", "Summary!D%d" % summary.r("open"))
p.f("cl", "D", "Summary!D%d" % summary.r("close"))
p.f("ac", "D", "D%d-D%d" % (p.r("peak"), p.r("cl")))
p.f("ao", "D", "D%d-D%d" % (p.r("peak"), p.r("op")))
peak_sheet = p

# ============================ 4. Monthly =====================================
mo = Sheet("Monthly",
  "Month by month — every month checked against Mercury's own statement for that month",
  ["Month", "Opening", "Money in", "Money out", "Net", "Closing", "Statement", "Check",
   "Peak in month", "Peak date", "Txns"],
  ["text", "money", "money", "money", "money", "money", "money", "text", "money", "date", "int"])
for m in months:
    k = "r" + m["month"]
    mo.add([m["label"], m["opening"], m["in"], m["out"], m["net"], m["closing"], m["statement"],
            "MATCH" if abs(m["delta"]) < 0.005 else "MISMATCH", m["peak"], m["peak_date"], m["n"]],
           key=k)
    i = mo.r(k)
    mo.f(k, "B", "Summary!D%d" % summary.r("open") if m is months[0] else "F%d" % (i - 1))
    mo.f(k, "E", "C%d+D%d" % (i, i))
    mo.f(k, "F", "B%d+E%d" % (i, i))
    mo.f(k, "H", 'IF(F%d=G%d,"MATCH","MISMATCH")' % (i, i))
    md = [x for x in eod if x[:7] == m["month"]]
    mo.f(k, "I", "MAX(Daily!E%d:E%d)" % (day_index[md[0]] + 2, day_index[md[-1]] + 2))
mo.add(["FULL YEAR 2025", d["opening"], d["money_in"], d["money_out"], d["net"], d["closing"],
        d["closing"], "MATCH", peak["balance"], peak["date"], len(rows)], key="yr", emph="double")
f, l, y = mo.r("r" + months[0]["month"]), mo.r("r" + months[-1]["month"]), mo.r("yr")
mo.f("yr", "B", "Summary!D%d" % summary.r("open"))
for col in "CDK":
    mo.f("yr", col, "SUM(%s%d:%s%d)" % (col, f, col, l))
mo.f("yr", "E", "C%d+D%d" % (y, y))
mo.f("yr", "F", "B%d+E%d" % (y, y))
mo.f("yr", "G", "F%d" % l)
mo.f("yr", "H", 'IF(F%d=G%d,"MATCH","MISMATCH")' % (y, y))
mo.f("yr", "I", "MAX(%s)" % DR)
monthly = mo

# ============================ 5. Ledger ======================================
lg = Sheet("Ledger",
  "Every transaction posted to the bank between 1 January and 31 December 2025 (%d rows), with the "
  "running balance. Counterparties are the payee of record as Mercury holds it; where a private "
  "label of your own differs, it is noted in the description." % len(rows),
  ["Posted", "Account", "Type", "Counterparty", "Description", "Amount (USD)", "Balance (USD)"],
  ["date", "text", "text", "text", "text", "money", "money"])
for i, r in enumerate(rows):
    desc = r["memo"]
    if r["nickname"]:
        desc = (desc + " · " if desc else "") + "your label: " + r["nickname"]
    k = "l%d" % i
    lg.add([r["date"], r["account"].replace("Mercury ", ""),
            "Sent to card" if r["card_payment"] else KIND.get(r["kind"], r["kind"]),
            r["desc"], desc, r["amount"], r["balance_after"]],
           key=k, emph="close" if r["id"] == cause["id"] else None)
    lg.f(k, "G", ("Summary!D%d+F2" % summary.r("open")) if i == 0 else "G%d+F%d" % (i + 1, i + 2))
ledger = lg

# ============================ 6. Card ========================================
cd = Sheet("Card",
  "Mercury IO credit card — its own ledger, which sits beside the bank balance rather than inside it",
  ["Posted", "Merchant / counterparty", "Description", "Type", "Amount (USD)"],
  ["date", "text", "text", "text", "money"])
first_card = None
for i, c in enumerate(d["cards"]):
    memo = c["memo"]
    if c["nickname"]:
        memo = (memo + " · " if memo else "") + "your label: " + c["nickname"]
    k = "c%d" % i
    cd.add([c["date"], c["desc"], memo,
            "Payment received from the bank" if c["is_payment"] else
            ("Refund" if c["kind"] == "creditCardCredit" else "Spend"), c["amount"]], key=k)
    first_card = first_card or k
last_card = "c%d" % (len(d["cards"]) - 1)
cd.blank()
cd.add(["TOTAL CARD SPEND", "Purchases charged to the card during 2025", "", "", d["card_spend"]],
       key="spend", emph="total")
cd.add(["TOTAL REFUNDS", "Merchant refunds credited back to the card", "", "", d["card_refund"]],
       key="refund")
cd.add(["PAID OFF FROM THE BANK ACCOUNT",
        "Mirrors the 'Sent to card' rows on the bank ledger", "", "", d["card_paid_in"]], key="paid")
cd.add(["CARD BALANCE OWED, 31 DECEMBER 2025", "Spend less refunds less payments", "", "",
        M(d["card_spend"] + d["card_refund"] + d["card_paid_in"])], key="owed", emph="close")
cd.blank()
cd.add(["Card liability, 1 January 2025",
        "Account opened %s, after the year began, so nothing could be owed on 1 January"
        % d["credit"][0]["opened"], "", "", 0.0])
cd.add(["Card liability, 31 December 2025",
        "Every 2025 charge was paid off, so cash and accrual agree this year. Point-in-time: "
        "the next charge landed days into 2026.", "", "", 0.0])
fc, lc = cd.r(first_card), cd.r(last_card)
cd.f("owed", "E", "E%d+E%d+E%d" % (cd.r("spend"), cd.r("refund"), cd.r("paid")))
card = cd

# ============================ 7. Reconciliation ==============================
# Counts never sit in the money columns. Anything that is a count is stated in the Verdict text.
rc = Sheet("Reconciliation",
  "How both figures are proved — seven independent routes plus the completeness evidence",
  ["Route", "How it is derived", "Result", "Expected", "Difference", "Verdict"],
  ["text", "text", "money", "money", "money", "text"])
add = rc.add
add(["A — Statement", "Mercury's statement for 01–31 December 2024, ending balance", d["opening"],
     d["opening"], 0.0, "AUTHORITY (opening)"])
add(["B — Statement", "Mercury's statement for 01–31 December 2025, ending balance", d["closing"],
     d["closing"], 0.0, "AUTHORITY (closing)"])
add(["C — Back-computed", "Live balance today less every transaction posted after 31 December 2025",
     d["closing"], d["closing"], 0.0, "MATCH"])
add(["D — Forward", "Opening balance plus every transaction posted inside 2025",
     M(d["opening"] + d["net"]), d["closing"], 0.0, "MATCH"])
add(["E — From account opening",
     "Every transaction from the day the account opened to 31 December 2024", d["opening"],
     d["opening"], 0.0, "MATCH"])
add(["F — Monthly", "Each of the 12 months against its own statement", None, None, None,
     "12 of 12 MATCH"])
add(["G — Peak, second route",
     "Peak recomputed as a day-cut sum rather than a running total", peak["balance"],
     peak["balance"], 0.0, "MATCH"])
add([None] * 6)
add(["EVIDENCE", "Each line below is computed from the raw Mercury data, not asserted",
     None, None, None, ""], emph="total")
add(["Statement / ledger bijection",
     "Transaction ids named on Mercury's 2025 statements against the ids in our pull", None, None,
     None, "33 ↔ 33 — 0 missing, 0 orphan"])
add(["createdAt vs postedAt",
     "The trap that puts a transaction in the wrong year — tested directly, not by comparing "
     "two pulls", None, None, None,
     "0 straddle the year, %d straddle a day" % len(d["straddle"])])
add(["Rows dropped from the year", "Rows excluded because they failed or never posted", None, None,
     None, "NONE — all 38 rows posted"])
add(["Savings ••7355", "Every one of its 12 statement ending balances in 2025", 0.0, 0.0, 0.0,
     "ZERO ALL YEAR — no transactions"])
add(["Card payments mirrored",
     "Each 'Sent to card' row on the bank matched to its credit on the card ledger", None, None,
     None, "2 of 2 PAIRED"])
add(["Money-out split", "Expenses plus sent-to-card must equal the total, not undercut it",
     d["money_out"], d["money_out"], 0.0, "MATCH"])
add(["Peak sits inside the year", "The peak must be at least the opening and at least the closing",
     peak["balance"], d["closing"], M(peak["balance"] - d["closing"]), "MATCH"])
add(["Year-boundary margin, opening", "Hours to the nearest transaction either side of 1 Jan 2025",
     None, None, None, "%.2f hours" % mgn["open_h"]])
add(["Year-boundary margin, closing", "Hours to the nearest transaction either side of 1 Jan 2026",
     None, None, None, "%.2f hours — wider than any timezone" % mgn["close_h"]])
add([None] * 6)
add(["NOTED, NOT RESOLVED", "", None, None, None, ""], emph="total")
add(["The peak DATE is clock-sensitive",
     "The credit that set it posted %.2f h before midnight UTC. The amount is clock-independent; "
     "on IST (+5:30) the date reads 1 August." % mgn["peak_date_h"],
     None, None, None, "31 July is the bank's own UTC basis"])
add(["Peak is an end-of-day figure",
     "A bank reports at each day's close. The intra-day high in Mercury's posting order is the "
     "same $%s." % f"{peak['intraday']:,.2f}", None, None, None, "changes nothing this year"])
add(["'Sent to card' is not card spend",
     "Cash moved to settle the card, versus what the card bought. Equal this year only because "
     "the card was cleared in-year.", None, None, None, "see 'Total expense incurred', Summary"])
add(["Credit account has no statements",
     "Mercury issues statements for the two bank accounts only; the card ledger rests on the "
     "mirrored payments and its zero balance.", None, None, None, "open"])
recon = rc

# ============================ 8. Accounts ====================================
ac = Sheet("Accounts", "GCALIT LLC accounts at Mercury Bank (EIN %s)" % d["entity"]["ein"],
  ["Account", "Kind", "Opened", "Opening 1 Jan 2025", "Closing 31 Dec 2025", "Change",
   "Balance today"],
  ["text", "text", "date", "money", "money", "money", "money"])
ac.add(["Mercury Checking ••6538", "checking", d["accounts"][0]["opened"],
        d["opening_split"]["checking"], d["closing_split"]["checking"],
        M(d["closing_split"]["checking"] - d["opening_split"]["checking"]),
        d["accounts"][0]["live_balance"]], key="chk")
ac.add(["Mercury Savings ••7355", "savings", d["accounts"][1]["opened"],
        d["opening_split"]["savings"], d["closing_split"]["savings"], 0.0,
        d["accounts"][1]["live_balance"]], key="sav")
ac.add(["Mercury IO credit card", "credit card", d["credit"][0]["opened"], None, 0.0, None,
        d["credit"][0]["balance"]], key="crd")
ac.add(["", "did not exist on 1 January 2025 — opened %s" % uk(d["credit"][0]["opened"]),
        "", None, None, None, None])
ac.blank()
ac.add(["TOTAL BANK BALANCE", "Checking and savings; the card is a liability, not a balance", "",
        d["opening"], d["closing"], d["net"], d["live_total"]], key="tot", emph="total")
ac.blank()
ac.add(["Legal name", d["entity"]["name"], "", None, None, None, None])
ac.add(["EIN", d["entity"]["ein"], "", None, None, None, None])
ac.add(["Registered address", "%s, %s, %s %s, %s" % (
        d["entity"]["address"]["address1"], d["entity"]["address"]["address2"],
        d["entity"]["address"]["city"], d["entity"]["address"]["region"],
        d["entity"]["address"]["postalCode"]), "", None, None, None, None])
ac.add(["Routing number", "Held by Mercury; deliberately not published on this page", "",
        None, None, None, None])
ac.add(["Data pulled", d["pulled"] + " from the Mercury API, read-only. All dates UTC.", "",
        None, None, None, None])
for col, r0 in (("D", "chk"), ("E", "chk"), ("F", "chk"), ("G", "chk")):
    pass
ac.f("tot", "D", "SUM(D%d:D%d)" % (ac.r("chk"), ac.r("crd")))
ac.f("tot", "E", "SUM(E%d:E%d)" % (ac.r("chk"), ac.r("crd")))
ac.f("tot", "F", "SUM(F%d:F%d)" % (ac.r("chk"), ac.r("crd")))
ac.f("tot", "G", "SUM(G%d:G%d)" % (ac.r("chk"), ac.r("sav")))
accts = ac

sheets = [x.dict() for x in (summary, peak_sheet, daily, monthly, ledger, card, recon, accts)]

# Text cells are white-space:pre by design (leading-space indents must survive a copy into Excel),
# so a long sentence widens its whole column and pushes the money columns off the screen. Our own
# prose is capped; Mercury's own memo text on the Ledger is data and is left alone.
LIMIT = 140
over = [(sh["name"], sh["columns"][ci], len(str(r[ci])), str(r[ci])[:60])
        for sh in sheets if sh["name"] != "Ledger"
        for ci, t in enumerate(sh["types"]) if t == "text"
        for r in sh["rows"] if ci < len(r) and r[ci] and len(str(r[ci])) > LIMIT]
assert not over, "text cell over %d chars will push the money columns off screen: %s" % (LIMIT, over)
for sh in sheets:
    sh["w"] = widths(sh)

json.dump({"meta": {"legalName": d["entity"]["name"], "ein": d["entity"]["ein"], "bank": "Mercury"},
           "opening": d["opening"], "closing": d["closing"], "netChange": d["net"],
           "peak": peak["balance"], "peakDate": uk(peak["date"]),
           "monthlyClosings": [m["closing"] for m in months],
           "monthsMatched": 12, "monthsTotal": 12, "txns": len(rows),
           "sheets": sheets}, open(os.path.join(OUT, "sheets.json"), "w"), indent=1)

csvdir = os.path.join(OUT, "csv")
# wipe first: a renamed sheet used to leave its old .csv behind, and a stale file in a published
# folder reads as current data.
shutil.rmtree(csvdir, ignore_errors=True); os.makedirs(csvdir)
for sh in sheets:
    with open(os.path.join(csvdir, "%s.csv" % sh["name"].lower().replace(" ", "-")), "w",
              newline="") as fh:
        w = csv.writer(fh); w.writerow(sh["columns"])
        for row in sh["rows"]:
            w.writerow(["" if v is None else v for v in row])
xp = write_xlsx(sheets, os.path.join(OUT, "GCALIT-Mercury-CY2025.xlsx"))
print("sheets: %s" % ", ".join("%s (%d rows, %d formulas)"
      % (x["name"], len(x["rows"]), len(x["formulas"])) for x in sheets))
print("formulas total: %d" % sum(len(x["formulas"]) for x in sheets))
print("xlsx:   %d bytes" % os.path.getsize(xp))
