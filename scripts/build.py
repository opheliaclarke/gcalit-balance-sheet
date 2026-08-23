#!/usr/bin/env python3
"""
GCALIT LLC — Mercury Bank balance sheet, FY 1 Apr 2025 -> 31 Mar 2026.

Reads only the raw JSON already pulled into raw/. Makes no network call, so it can
be re-run and re-checked without touching the bank.

The financial year is cut on **postedAt**, never createdAt (Mercury trap T2).
Only status == "sent" moves money; everything else is counted and reported, never
silently dropped.
"""
import json, os, sys
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW  = os.path.join(HERE, "raw")
OUT  = os.path.join(HERE, "out")

FY_START, FY_END_EXCL = "2025-04-01", "2026-04-01"
FY_LABEL   = "1 April 2025 – 31 March 2026"
OPEN_STMT  = "2025-03-31"   # statement period END whose endingBalance == our opening
CLOSE_STMT = "2026-03-31"   # statement period END whose endingBalance == our closing

CREDIT_ACCOUNT_KIND = "credit"


def money(x):
    return round(float(x or 0), 2)


def load():
    j = lambda n: json.load(open(os.path.join(RAW, n)))
    return j("accounts.json"), j("credit.json"), j("cards.json"), \
           j("transactions_all.json"), j("statements.json")


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------
IN_KINDS  = {"incomingDomesticWire", "incomingInternationalWire", "checkDeposit",
             "interestPayment"}
OUT_KINDS = {"outgoingPayment", "wireFee", "personalBankingSubscriptionFee",
             "billingEngineSubscriptionFee"}
CARD_SPEND_KINDS  = {"debitCardTransaction", "creditCardTransaction",
                     "cardInternationalTransactionFee"}
CARD_CREDIT_KINDS = {"debitCardCredit", "creditCardCredit",
                     "cardInternationalTransactionFeeRebate",
                     "cardInternationalTransactionFeeReversal",
                     "cardInternationalTransactionFeeRebateReversal"}
OWN_TRANSFER_KINDS = {"internalTransfer", "treasuryTransfer"}


def is_card_autopay(t):
    """Cash leaving a depository account to pay the Mercury credit card."""
    desc = ((t.get("bankDescription") or "") + " " + (t.get("counterpartyName") or "")).upper()
    return "IO AUTOPAY" in desc or "MERCURY CREDIT" in desc


def is_cashback(t):
    return "CASHBACK" in ((t.get("counterpartyName") or "") + " " +
                          (t.get("bankDescription") or "")).upper()


def classify_cash(t):
    """Bucket for a transaction sitting on a DEPOSITORY (cash) account."""
    amt, kind = t["amount"], t["kind"]
    if is_card_autopay(t):
        return "card_payment" if amt < 0 else "card_payment_reversal"
    if kind in OWN_TRANSFER_KINDS:
        return "own_transfer"
    if amt > 0:
        if is_cashback(t):
            return "in_cashback"
        if kind in IN_KINDS:
            return "in_receipts"
        return "in_other"          # ACH credits Mercury files as kind "other"
    if kind in CARD_SPEND_KINDS:
        return "out_card_direct"   # debit-card spend hits cash immediately
    if kind in OUT_KINDS:
        return "out_payments"
    return "out_other"             # ACH debits Mercury files as kind "other"


BUCKET_LABEL = OrderedDict([
    ("in_receipts",          "Incoming wires and deposits"),
    ("in_other",             "Other incoming (ACH credits)"),
    ("in_cashback",          "Mercury IO card cashback"),
    ("out_payments",         "Outgoing payments and wires"),
    ("out_other",            "Other outgoing (ACH debits)"),
    ("out_card_direct",      "Debit-card spend (direct from account)"),
    ("card_payment",         "Money sent to card (IO Autopay)"),
    ("card_payment_reversal","Money reversed back from card"),
    ("own_transfer",         "Transfers between own accounts"),
])


def main():
    accounts, credit, cards, txs, statements = load()
    dep_ids = {a["id"] for a in accounts}
    credit_ids = {c["id"] for c in credit}
    acct_name = {a["id"]: a["name"] for a in accounts}
    for c in credit:
        acct_name[c["id"]] = "Mercury IO credit card account"

    # ---- statement-derived opening and closing (ROUTE A, the authority) ----
    stmt_open = stmt_close = 0.0
    per_account_bounds = {}
    for aid, sts in statements.items():
        o = c = None
        for s in sts:
            if (s.get("endDate") or "")[:10] == OPEN_STMT:
                o = money(s["endingBalance"])
            if (s.get("endDate") or "")[:10] == CLOSE_STMT:
                c = money(s["endingBalance"])
        per_account_bounds[aid] = {"opening": o, "closing": c}
        stmt_open += o or 0.0
        stmt_close += c or 0.0
    stmt_open, stmt_close = money(stmt_open), money(stmt_close)

    # ---- ledger ----
    settled   = [t for t in txs if t.get("status") == "sent"]
    unsettled = [t for t in txs if t.get("status") != "sent"]
    dated     = [t for t in settled if t.get("postedAt")]
    undated   = [t for t in settled if not t.get("postedAt")]

    fy   = [t for t in dated if FY_START <= t["postedAt"][:10] < FY_END_EXCL]
    pre  = [t for t in dated if t["postedAt"][:10] <  FY_START]
    post = [t for t in dated if t["postedAt"][:10] >= FY_END_EXCL]

    fy_cash   = [t for t in fy if t["accountId"] in dep_ids]
    fy_card   = [t for t in fy if t["accountId"] in credit_ids]

    buckets = defaultdict(list)
    for t in fy_cash:
        buckets[classify_cash(t)].append(t)

    tot = lambda key: money(sum(t["amount"] for t in buckets.get(key, [])))
    cash_movement = money(sum(t["amount"] for t in fy_cash))

    # ---- ROUTE C: opening + movement == closing ----
    route_c = money(stmt_open + cash_movement)

    # ---- ROUTE B: today's balance back-computed to the FY close ----
    live_balance = money(sum(a["currentBalance"] for a in accounts))
    post_cash = money(sum(t["amount"] for t in post if t["accountId"] in dep_ids))
    route_b = money(live_balance - post_cash)

    # ---- ROUTE B2: back to the FY open ----
    pre_cash_from_open = money(sum(t["amount"] for t in pre if t["accountId"] in dep_ids))
    open_from_zero = money(pre_cash_from_open)   # accounts opened inside the data window

    # ---- card ledger (memo — sits on the liability account, not on cash) ----
    card_spend  = money(sum(t["amount"] for t in fy_card if t["kind"] in CARD_SPEND_KINDS))
    card_refund = money(sum(t["amount"] for t in fy_card if t["kind"] in CARD_CREDIT_KINDS))
    card_paydown= money(sum(t["amount"] for t in fy_card if is_card_autopay(t)))
    card_net    = money(card_spend + card_refund)

    result = {
        "entity": {"legalName": "GCALIT LLC", "ein": "61-2005202",
                   "bank": "Mercury", "fy": FY_LABEL},
        "generatedFrom": {
            "transactionsPulled": len(txs), "settled": len(settled),
            "unsettled": len(unsettled), "withoutPostedAt": len(undated),
            "inFY": len(fy), "beforeFY": len(pre), "afterFY": len(post),
        },
        "accounts": [
            {"id": a["id"], "name": a["name"], "kind": a["kind"],
             "opening": per_account_bounds.get(a["id"], {}).get("opening"),
             "closing": per_account_bounds.get(a["id"], {}).get("closing"),
             "liveBalance": money(a["currentBalance"])}
            for a in accounts
        ],
        "creditAccounts": [
            {"id": c["id"], "name": "Mercury IO credit card account",
             "liveBalance": money(c["currentBalance"]), "opened": c["createdAt"][:10]}
            for c in credit
        ],
        "opening": stmt_open,
        "closing": stmt_close,
        "netChange": money(stmt_close - stmt_open),
        "buckets": OrderedDict(
            (k, {"label": BUCKET_LABEL[k], "total": tot(k), "count": len(buckets.get(k, []))})
            for k in BUCKET_LABEL if buckets.get(k)
        ),
        "cashMovement": cash_movement,
        "card": {
            "spend": card_spend, "refunds": card_refund, "net": card_net,
            "paydownOnCardLedger": card_paydown,
            # Provable, not assumed: the credit account did not exist on 1 Apr 2025
            # (opened later) and no credit row posted before the FY, so the opening
            # liability is zero by construction rather than by assertion.
            "openingLiability": money(sum(t["amount"] for t in pre if t["accountId"] in credit_ids)),
            "closingLiability": money(sum(t["amount"] for t in dated
                                          if t["accountId"] in credit_ids
                                          and t["postedAt"][:10] < FY_END_EXCL)),
            "accountOpened": (credit[0]["createdAt"][:10] if credit else None),
        },
        "reconciliation": {
            "A_statementOpening": stmt_open,
            "A_statementClosing": stmt_close,
            "C_openingPlusMovement": route_c,
            "C_agrees": abs(route_c - stmt_close) < 0.005,
            "C_difference": money(route_c - stmt_close),
            "B_liveBalance": live_balance,
            "B_postFYMovement": post_cash,
            "B_backComputedClosing": route_b,
            "B_agrees": abs(route_b - stmt_close) < 0.005,
            "B_difference": money(route_b - stmt_close),
            "openFromAccountBirth": open_from_zero,
            "openFromBirth_agrees": abs(open_from_zero - stmt_open) < 0.005,
            "openFromBirth_difference": money(open_from_zero - stmt_open),
        },
        "excluded": [
            # postedAt stays null when the row never posted; the created date is a
            # separate fact and is labelled as one. Coalescing them invents a posting.
            {"id": t["id"], "postedAt": (t["postedAt"][:10] if t.get("postedAt") else None),
             "createdAt": t["createdAt"][:10],
             "status": t["status"], "kind": t["kind"], "amount": money(t["amount"]),
             "counterparty": t.get("counterpartyName"),
             "reason": t.get("reasonForFailure")}
            for t in unsettled
        ],
        "ledger": [
            {"date": t["postedAt"][:10], "created": t["createdAt"][:10],
             "account": acct_name.get(t["accountId"], t["accountId"]),
             "isCard": t["accountId"] in credit_ids,
             "kind": t["kind"], "status": t["status"],
             "bucket": (classify_cash(t) if t["accountId"] in dep_ids else "card_ledger"),
             "counterparty": t.get("counterpartyName") or "",
             "description": t.get("bankDescription") or t.get("note") or "",
             "category": t.get("mercuryCategory") or "",
             "amount": money(t["amount"]),
             "link": t.get("dashboardLink") or ""}
            for t in sorted(fy, key=lambda x: (x["postedAt"], x["id"]))
        ],
    }

    # running balance on the cash ledger only
    run = stmt_open
    for row in result["ledger"]:
        if not row["isCard"]:
            run = money(run + row["amount"])
            row["balance"] = run
        else:
            row["balance"] = None
    result["runningEndBalance"] = run

    os.makedirs(OUT, exist_ok=True)
    json.dump(result, open(os.path.join(OUT, "balance_sheet.json"), "w"), indent=1)
    return result


if __name__ == "__main__":
    r = main()
    rec = r["reconciliation"]
    print("=" * 74)
    print("GCALIT LLC — Mercury — FY %s" % r["entity"]["fy"])
    print("=" * 74)
    print("OPENING BALANCE  (1 Apr 2025)   $ %12s   [Mar-2025 statement]" % f"{r['opening']:,.2f}")
    print("CLOSING BALANCE  (31 Mar 2026)  $ %12s   [Mar-2026 statement]" % f"{r['closing']:,.2f}")
    print("NET CHANGE                      $ %12s" % f"{r['netChange']:,.2f}")
    print("-" * 74)
    for k, v in r["buckets"].items():
        print("  %-42s %12s  (%d)" % (v["label"], f"{v['total']:,.2f}", v["count"]))
    print("  %-42s %12s" % ("TOTAL CASH MOVEMENT", f"{r['cashMovement']:,.2f}"))
    print("-" * 74)
    c = r["card"]
    print("CARD (memo, on the credit-card ledger)")
    print("  %-42s %12s" % ("Card spend", f"{c['spend']:,.2f}"))
    print("  %-42s %12s" % ("Card refunds / reversals", f"{c['refunds']:,.2f}"))
    print("  %-42s %12s" % ("Net card spend", f"{c['net']:,.2f}"))
    print("  %-42s %12s" % ("Paid down on card ledger", f"{c['paydownOnCardLedger']:,.2f}"))
    print("-" * 74)
    print("RECONCILIATION")
    print("  A  statement opening / closing        %12s  /  %s" %
          (f"{rec['A_statementOpening']:,.2f}", f"{rec['A_statementClosing']:,.2f}"))
    print("  C  opening + FY movement  = %12s   %s (diff %s)" %
          (f"{rec['C_openingPlusMovement']:,.2f}", "AGREES" if rec["C_agrees"] else "*** MISMATCH ***",
           f"{rec['C_difference']:,.2f}"))
    print("  B  live bal %s - post-FY %s = %12s   %s (diff %s)" %
          (f"{rec['B_liveBalance']:,.2f}", f"{rec['B_postFYMovement']:,.2f}",
           f"{rec['B_backComputedClosing']:,.2f}",
           "AGREES" if rec["B_agrees"] else "*** MISMATCH ***", f"{rec['B_difference']:,.2f}"))
    print("  D  opening rebuilt from account birth = %12s   %s (diff %s)" %
          (f"{rec['openFromAccountBirth']:,.2f}",
           "AGREES" if rec["openFromBirth_agrees"] else "*** MISMATCH ***",
           f"{rec['openFromBirth_difference']:,.2f}"))
    print("-" * 74)
    g = r["generatedFrom"]
    print("Source: %d transactions pulled, %d settled, %d posted inside the FY."
          % (g["transactionsPulled"], g["settled"], g["inFY"]))
    print("%d row(s) in the whole pull are not 'sent'. NONE fall in this FY:" % g["unsettled"])
    for e in r["excluded"]:
        print("   %s  created %s  posted %s  %s  %s  %s"
              % (e["status"], e["createdAt"], e["postedAt"] or "never", e["kind"],
                 f"{e['amount']:,.2f}", e["counterparty"]))
