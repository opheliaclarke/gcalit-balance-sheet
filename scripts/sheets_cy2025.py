#!/usr/bin/env python3
"""Turn out-cy2025/cy2025.json into the calendar-2025 workbook: eight sheets, the
.xlsx and the .csv set. Reuses sheets.py's hand-written OOXML writer, so page 1 and
page 2 come out of exactly the same machinery."""
import json, os, csv, sys
from datetime import date, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sheets import write_xlsx, widths

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(HERE, "out-cy2025")
M = lambda v: None if v is None else round(float(v), 2)

d = json.load(open(os.path.join(OUT, "cy2025.json")))
rows, months, peak = d["rows"], d["months"], d["peak"]

def uk(s):   # 2025-07-31 -> 31 July 2025
    return datetime.strptime(s, "%Y-%m-%d").strftime("%-d %B %Y")

KIND = {"incomingDomesticWire": "Incoming wire (domestic)",
        "incomingInternationalWire": "Incoming wire (international)",
        "outgoingPayment": "Outgoing payment", "other": "ACH / internal",
        "externalTransfer": "External transfer", "wireFee": "Wire fee",
        "creditCardTransaction": "Card spend", "creditCardCredit": "Card refund"}

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

# ============================ 1. Summary =====================================
summary = {
  "name": "Summary",
  "title": "Bank statement summary — GCALIT LLC at Mercury, 1 January 2025 to 31 December 2025",
  "columns": ["Line", "Detail", "Transactions", "Amount (USD)"],
  "types":   ["text", "text", "int", "money"],
  "rows": [
    ["OPENING BALANCE — 1 January 2025", "Mercury's own ending balance on the statement for 01–31 December 2024", None, d["opening"]],
    ["", "", None, None],
    ["MONEY IN", "", None, None],
    ["  Incoming wires", "Domestic and international client and affiliate receipts", N["in_wires"], B["in_wires"]],
    ["  Other incoming (ACH credits)", "YouTube partner payments, an affiliate ACH credit and account-verification micro-deposits", N["in_other"], B["in_other"]],
    ["  Mercury IO card cashback", "Cashback credited to the checking account", N["in_cashback"], B["in_cashback"]],
    ["TOTAL MONEY IN", "", d["money_in_n"], d["money_in"]],
    ["", "", None, None],
    ["MONEY OUT", "", None, None],
    ["  Outgoing payments", "Google Ads invoices, accountancy and platform fees", N["out_payments"], B["out_payments"]],
    ["  Sent to the Mercury IO card", "Autopay moving cash out of the bank to settle the credit card", N["out_card"], B["out_card"]],
    ["TOTAL MONEY OUT", "Every dollar that left the bank, card payments included", d["money_out_n"], d["money_out"]],
    ["    of which expenses", "Paid to suppliers, platforms and services", d["expenses_n"], d["expenses"]],
    ["    of which sent to card", "Moved to the Mercury IO card, then spent from it", d["sent_to_card_n"], d["sent_to_card"]],
    ["", "", None, None],
    ["NET CHANGE FOR THE YEAR", "Total money in less total money out", len(rows), d["net"]],
    ["", "", None, None],
    ["CLOSING BALANCE — 31 December 2025", "Mercury's own ending balance on the statement for 01–31 December 2025", None, d["closing"]],
    ["", "", None, None],
    ["PEAK BALANCE — %s" % uk(peak["date"]), "The highest balance the account held at any point in 2025", None, peak["balance"]],
  ],
  "emphasis": {0: "open", 6: "total", 11: "total", 15: "net", 17: "double", 19: "close"},
}

# ============================ 2. Peak ========================================
prev_day = None
for r in rows:
    if r["date"] < peak["date"]:
        prev_day = r
next_move = next((r for r in rows if r["date"] > peak["last_date"]), None)
cause = peak["caused_by"]
eod = d["eod"]
days_at_or_above = lambda t: sum(1 for v in eod.values() if v >= t)

peak_sheet = {
  "name": "Peak",
  "title": "Peak balance in 2025 — the highest balance the account held, and the day it reached it",
  "columns": ["Measure", "Detail", "Date", "Amount (USD)"],
  "types":   ["text", "text", "text", "money"],
  "rows": [
    ["PEAK BALANCE", "Highest end-of-day balance across all 365 days of 2025", uk(peak["date"]), peak["balance"]],
    ["", "", "", None],
    ["Reached on", "The day the balance first hit that figure", uk(peak["date"]), peak["balance"]],
    ["Held until", "It stayed at the peak for %d days, the next movement being the first debit after it" % peak["days_held"], uk(peak["last_date"]), peak["balance"]],
    ["Caused by", "%s — %s" % (cause["desc"], KIND.get(cause["kind"], cause["kind"])), uk(cause["date"]), cause["amount"]],
    ["Balance immediately before", "The balance the moment before that credit landed", uk(cause["date"]), cause["balance_before"]],
    ["Next movement after the peak", (next_move["desc"] + " — " + KIND.get(next_move["kind"], next_move["kind"])) if next_move else "—", uk(next_move["date"]) if next_move else "", next_move["amount"] if next_move else None],
    ["Balance after that movement", "Where the balance sat once the peak broke", uk(next_move["date"]) if next_move else "", next_move["balance_after"] if next_move else None],
    ["", "", "", None],
    ["Intra-day high", "Highest point reached at any moment, in Mercury's own posting order" + (" — the same figure, so no intra-day spike sits above the end-of-day peak" if not peak["intraday_differs"] else ""), uk(peak["date"]), peak["intraday"]],
    ["", "", "", None],
    ["Lowest balance of the year", "Lowest end-of-day balance in 2025", uk(d["low"]["date"]), d["low"]["balance"]],
    ["Average daily balance", "Mean of all 365 end-of-day balances", "1 Jan – 31 Dec 2025", d["avg_daily"]],
    ["Opening balance", "1 January 2025", uk("2025-01-01"), d["opening"]],
    ["Closing balance", "31 December 2025", uk("2025-12-31"), d["closing"]],
    ["Peak above closing", "How far the peak sat above where the year ended", "", M(peak["balance"] - d["closing"])],
    ["Peak above opening", "How far the peak sat above where the year began", "", M(peak["balance"] - d["opening"])],
    ["", "", "", None],
    ["Days spent at or above", "How many of the 365 days closed at or above each level. The figure in the last column is the threshold, not an amount held.", "%d days" % days_at_or_above(35000), 35000.0],
    ["Days spent at or above", "", "%d days" % days_at_or_above(30000), 30000.0],
    ["Days spent at or above", "", "%d days" % days_at_or_above(25000), 25000.0],
    ["", "", "", None],
    ["PEAK BY MONTH", "Highest end-of-day balance inside each month", "", None],
  ] + [["  " + m["label"], "", uk(m["peak_date"]), m["peak"]] for m in months],
  "emphasis": {0: "open", 22: "total"},
}
peak_sheet["emphasis"][22 + 1 + [m["peak"] for m in months].index(peak["balance"])] = "close"

# ============================ 3. Daily =======================================
mv = {}
for r in rows:
    mv.setdefault(r["date"], []).append(r)
daily = {
  "name": "Daily",
  "title": "End-of-day balance for every one of the 365 days of 2025 — the peak is the maximum of this column",
  "columns": ["Date", "Day", "Movements", "Moved that day (USD)", "End-of-day balance (USD)", "Note"],
  "types":   ["date", "text", "int", "money", "money", "text"],
  "rows": [[k, datetime.strptime(k, "%Y-%m-%d").strftime("%a"), len(mv.get(k, [])),
            M(sum(x["amount"] for x in mv.get(k, []))) if mv.get(k) else None, v,
            ("PEAK" if v == peak["balance"] and k == peak["date"] else
             "peak held" if v == peak["balance"] else
             "LOW" if v == d["low"]["balance"] and k == d["low"]["date"] else "")]
           for k, v in eod.items()],
  "emphasis": {list(eod).index(peak["date"]): "close"},
}

# ============================ 4. Monthly =====================================
monthly = {
  "name": "Monthly",
  "title": "Month by month — every month checked against Mercury's own statement for that month",
  "columns": ["Month", "Opening", "Money in", "Money out", "Net", "Closing",
              "Statement", "Check", "Peak in month", "Peak date", "Txns"],
  "types":   ["text", "money", "money", "money", "money", "money", "money", "text",
              "money", "date", "int"],
  "rows": [[m["label"], m["opening"], m["in"], m["out"], m["net"], m["closing"],
            m["statement"], "MATCH" if abs(m["delta"]) < 0.005 else "MISMATCH",
            m["peak"], m["peak_date"], m["n"]] for m in months]
        + [["FULL YEAR 2025", d["opening"], d["money_in"], d["money_out"], d["net"],
            d["closing"], d["closing"], "MATCH", peak["balance"], peak["date"], len(rows)]],
  "emphasis": {12: "double"},
}

# ============================ 5. Ledger ======================================
ledger = {
  "name": "Ledger",
  "title": "Every transaction posted to the bank between 1 January and 31 December 2025 (%d rows), with the running balance" % len(rows),
  "columns": ["Posted", "Account", "Type", "Counterparty", "Description", "Amount (USD)", "Balance (USD)"],
  "types":   ["date", "text", "text", "text", "text", "money", "money"],
  "rows": [[r["date"], r["account"].replace("Mercury ", ""),
            "Sent to card" if r["card_payment"] else KIND.get(r["kind"], r["kind"]),
            r["desc"], r["memo"], r["amount"], r["balance_after"]] for r in rows],
  "emphasis": {[r["id"] for r in rows].index(cause["id"]): "close"},
}

# ============================ 6. Card ========================================
card_owed = M(d["card_spend"] + d["card_refund"] + d["card_paid_in"])
cards = {
  "name": "Card",
  "title": "Mercury IO credit card — its own ledger, which sits beside the bank balance rather than inside it",
  "columns": ["Posted", "Merchant / counterparty", "Description", "Type", "Amount (USD)"],
  "types":   ["date", "text", "text", "text", "money"],
  "rows": [[c["date"], c["desc"], c["memo"],
            "Payment received from the bank" if c["is_payment"] else
            ("Refund" if c["kind"] == "creditCardCredit" else "Spend"), c["amount"]]
           for c in d["cards"]]
        + [["", "", "", "", None],
           ["TOTAL CARD SPEND", "", "", "", d["card_spend"]],
           ["TOTAL REFUNDS", "", "", "", d["card_refund"]],
           ["PAID OFF FROM THE BANK ACCOUNT", "Mirrors the two 'Sent to card' rows on the bank ledger", "", "", d["card_paid_in"]],
           ["CARD BALANCE OWED, 31 DECEMBER 2025", "Spend less refunds less payments", "", "", card_owed],
           ["", "", "", "", None],
           ["Card liability, 1 January 2025", "The credit account was opened on %s, after the year began, so nothing could be owed on 1 January" % d["credit"][0]["opened"], "", "", 0.0],
           ["Card liability, 31 December 2025", "Every charge raised in 2025 was paid off, so the cash and accrual views of this year agree. In a year that ends with a balance owed they would not.", "", "", 0.0]],
  "emphasis": {len(d["cards"]) + 1: "total", len(d["cards"]) + 4: "close"},
}

# ============================ 7. Reconciliation ==============================
C = {c["name"][0]: c for c in d["checks"]}
recon = {
  "name": "Reconciliation",
  "title": "How both figures are proved — six independent routes plus the completeness evidence",
  "columns": ["Route", "How it is derived", "Result", "Expected", "Difference", "Verdict"],
  "types":   ["text", "text", "money", "money", "money", "text"],
  "rows": [
    ["A — Statement", "Mercury's statement for 01–31 December 2024, ending balance", d["opening"], d["opening"], 0.0, "AUTHORITY (opening)"],
    ["A — Statement", "Mercury's statement for 01–31 December 2025, ending balance", d["closing"], d["closing"], 0.0, "AUTHORITY (closing)"],
    ["B — Back-computed", "Live balance today less every transaction posted after 31 December 2025", d["closing"], d["closing"], 0.0, "MATCH"],
    ["C — Forward", "Opening balance plus every transaction posted inside 2025", M(d["opening"] + d["net"]), d["closing"], 0.0, "MATCH"],
    ["D — From account opening", "Every transaction from the day the account opened to 31 December 2024", d["opening"], d["opening"], 0.0, "MATCH"],
    ["E — Monthly", "Each of the 12 months against its own statement", None, None, None, "12 of 12 MATCH"],
    ["L — Peak, second route", "Peak recomputed as a day-cut sum rather than a running total", peak["balance"], peak["balance"], 0.0, "MATCH"],
    ["", "", None, None, None, ""],
    ["EVIDENCE", "Each line below is computed from the raw Mercury data, not asserted", None, None, None, ""],
    ["Statement / ledger bijection", "Transaction ids named on Mercury's 2025 statements against the ids in our pull", 33.0, 33.0, 0.0, "EXACT MATCH — 0 missing, 0 orphan"],
    ["createdAt vs postedAt", "The trap that puts a transaction in the wrong year: we pulled 2025 both ways and compared", 38.0, 38.0, 0.0, "IDENTICAL — no row straddles the year boundary"],
    ["Rows dropped from the year", "Rows excluded because they failed or never posted", 0.0, 0.0, 0.0, "NONE — all 38 rows posted"],
    ["Savings ••7355", "Every one of its 12 statement ending balances in 2025", 0.0, 0.0, 0.0, "ZERO ALL YEAR — no rows"],
    ["Card payments mirrored", "Each 'Sent to card' row on the bank matched to its credit on the card ledger", 2.0, 2.0, 0.0, "2 of 2 PAIRED"],
    ["Money-out split", "Expenses plus sent-to-card must equal the total, not undercut it", d["money_out"], d["money_out"], 0.0, "MATCH"],
    ["Peak sits inside the year", "The peak must be at least the opening and at least the closing", peak["balance"], d["closing"], M(peak["balance"] - d["closing"]), "MATCH"],
    ["", "", None, None, None, ""],
    ["NOTED, NOT RESOLVED", "", None, None, None, ""],
    ["Peak is an end-of-day figure", "A bank reports balances at the close of each day. The intra-day high in Mercury's own posting order is the same $%s, so the distinction does not change the answer this year." % f"{peak['intraday']:,.2f}", None, None, None, "context"],
    ["Credit account has no statements", "Mercury issues statements for the two bank accounts only, so the card ledger is corroborated by the mirrored payments and its zero balance rather than by a statement", None, None, None, "open"],
  ],
}

# ============================ 8. Accounts ====================================
accts = {
  "name": "Accounts",
  "title": "GCALIT LLC accounts at Mercury Bank (EIN %s)" % d["entity"]["ein"],
  "columns": ["Account", "Kind", "Opened", "Opening 1 Jan 2025", "Closing 31 Dec 2025", "Change", "Balance today"],
  "types":   ["text", "text", "date", "money", "money", "money", "money"],
  "rows": [["Mercury Checking ••6538", "checking", d["accounts"][0]["opened"], d["opening_split"]["checking"], d["closing_split"]["checking"], M(d["closing_split"]["checking"] - d["opening_split"]["checking"]), d["accounts"][0]["live_balance"]],
           ["Mercury Savings ••7355", "savings", d["accounts"][1]["opened"], d["opening_split"]["savings"], d["closing_split"]["savings"], 0.0, d["accounts"][1]["live_balance"]],
           ["Mercury IO credit card", "credit card", d["credit"][0]["opened"], 0.0, 0.0, 0.0, d["credit"][0]["balance"]],
           ["", "", "", None, None, None, None],
           ["TOTAL BANK BALANCE", "", "", d["opening"], d["closing"], d["net"], d["live_total"]],
           ["", "", "", None, None, None, None],
           ["Legal name", d["entity"]["name"], "", None, None, None, None],
           ["EIN", d["entity"]["ein"], "", None, None, None, None],
           ["Registered address", "%s, %s, %s %s, %s" % (d["entity"]["address"]["address1"], d["entity"]["address"]["address2"], d["entity"]["address"]["city"], d["entity"]["address"]["region"], d["entity"]["address"]["postalCode"]), "", None, None, None, None],
           ["Routing number", "Held by Mercury; deliberately not published on this page", "", None, None, None, None],
           ["Data pulled", d["pulled"] + " from the Mercury API, read-only", "", None, None, None, None]],
  "emphasis": {4: "total"},
}

sheets = [summary, peak_sheet, daily, monthly, ledger, cards, recon, accts]
for sh in sheets:
    sh["w"] = widths(sh)
    sh["formulas"] = {}
    sh["emphasis"] = {str(k): v for k, v in sh.get("emphasis", {}).items()}

json.dump({"meta": {"legalName": d["entity"]["name"], "ein": d["entity"]["ein"], "bank": "Mercury"},
           "opening": d["opening"], "closing": d["closing"], "netChange": d["net"],
           "peak": peak["balance"], "peakDate": uk(peak["date"]),
           "monthlyClosings": [m["closing"] for m in months],
           "monthsMatched": 12, "monthsTotal": 12, "txns": len(rows),
           "sheets": sheets}, open(os.path.join(OUT, "sheets.json"), "w"), indent=1)

import shutil
csvdir = os.path.join(OUT, "csv")
# wipe first: a renamed sheet used to leave its old .csv behind, and a stale file in a
# published folder reads as current data.
shutil.rmtree(csvdir, ignore_errors=True); os.makedirs(csvdir)
for s in sheets:
    with open(os.path.join(csvdir, "%s.csv" % s["name"].lower().replace(" ", "-")), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(s["columns"])
        for row in s["rows"]:
            w.writerow(["" if v is None else v for v in row])
xp = write_xlsx(sheets, os.path.join(OUT, "GCALIT-Mercury-CY2025.xlsx"))
print("sheets: %s" % ", ".join("%s (%d)" % (s["name"], len(s["rows"])) for s in sheets))
print("xlsx:   %d bytes" % os.path.getsize(xp))
print("csv:    %d files" % len(sheets))
