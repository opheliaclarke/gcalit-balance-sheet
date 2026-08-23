#!/usr/bin/env python3
"""Month-by-month cash view. Each month's computed closing is checked against that
month's own Mercury statement endingBalance — 12 independent checks, not one."""
import json, os, sys
from collections import OrderedDict
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "scripts"))
from build import money, classify_cash, main as build_main, FY_START, FY_END_EXCL

MONTHS = ["2025-04","2025-05","2025-06","2025-07","2025-08","2025-09",
          "2025-10","2025-11","2025-12","2026-01","2026-02","2026-03"]
NAME = {"01":"January","02":"February","03":"March","04":"April","05":"May","06":"June",
        "07":"July","08":"August","09":"September","10":"October","11":"November","12":"December"}

def run():
    r = build_main()
    accounts = json.load(open(os.path.join(HERE,"raw","accounts.json")))
    statements = json.load(open(os.path.join(HERE,"raw","statements.json")))
    dep_ids = {a["id"] for a in accounts}

    # statement ending balance per month, summed across depository accounts
    stmt_end = {}
    for aid, sts in statements.items():
        if aid not in dep_ids:
            continue
        for s in sts:
            key = (s.get("endDate") or "")[:7]
            stmt_end[key] = money(stmt_end.get(key, 0) + money(s["endingBalance"]))

    rows, opening = [], r["opening"]
    for m in MONTHS:
        txs = [t for t in r["ledger"] if not t["isCard"] and t["date"][:7] == m]
        mi  = money(sum(t["amount"] for t in txs if t["amount"] > 0))
        mo  = money(sum(t["amount"] for t in txs if t["amount"] < 0 and t["bucket"] != "card_payment"))
        mc  = money(sum(t["amount"] for t in txs if t["bucket"] == "card_payment"))
        closing = money(opening + mi + mo + mc)
        st = stmt_end.get(m)
        rows.append(OrderedDict([
            ("month", "%s %s" % (NAME[m[5:7]], m[:4])),
            ("key", m), ("opening", opening), ("moneyIn", mi), ("moneyOut", mo),
            ("cardPayments", mc), ("net", money(mi+mo+mc)), ("closing", closing),
            ("statement", st), ("txns", len(txs)),
            ("agrees", st is not None and abs(closing - st) < 0.005),
            ("difference", money(closing - st) if st is not None else None),
        ]))
        opening = closing
    r["monthly"] = rows
    json.dump(r, open(os.path.join(HERE,"out","balance_sheet.json"),"w"), indent=1)
    return r

if __name__ == "__main__":
    r = run()
    print("%-16s %11s %11s %11s %10s %11s %11s  %s" %
          ("MONTH","OPENING","MONEY IN","MONEY OUT","TO CARD","CLOSING","STATEMENT","CHECK"))
    print("-"*104)
    ok = 0
    for x in r["monthly"]:
        ok += 1 if x["agrees"] else 0
        print("%-16s %11s %11s %11s %10s %11s %11s  %s" % (
            x["month"], f"{x['opening']:,.2f}", f"{x['moneyIn']:,.2f}", f"{x['moneyOut']:,.2f}",
            f"{x['cardPayments']:,.2f}", f"{x['closing']:,.2f}",
            f"{x['statement']:,.2f}" if x["statement"] is not None else "—",
            "OK" if x["agrees"] else "*** MISMATCH %s ***" % x["difference"]))
    print("-"*104)
    print("%d of %d months tie to their own Mercury statement." % (ok, len(r["monthly"])))
