#!/usr/bin/env python3
"""Facts the reconciliation rests on — each COMPUTED from raw/, never asserted.

These come from the three independent verifiers' strongest checks: the statement
bijection is a much harder completeness proof than "the totals add up", because a
missing transaction cannot survive 24 consecutive balance ties.
"""
import json, os
from collections import defaultdict
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(HERE, "raw")
M = lambda v: round(float(v or 0), 2)
j = lambda n: json.load(open(os.path.join(RAW, n)))

FY0, FY1 = "2025-04-01", "2026-04-01"


def compute():
    accounts, credit, txs, statements = j("accounts.json"), j("credit.json"), \
                                        j("transactions_all.json"), j("statements.json")
    dep = {a["id"] for a in accounts}
    cre = {c["id"] for c in credit}
    sent = [t for t in txs if t["status"] == "sent"]

    # 1. statement <-> pull bijection, per depository account
    stmt_ids, pull_ids = set(), set()
    for aid, sts in statements.items():
        if aid not in dep:
            continue
        for s in sts:
            for t in s.get("transactions", []):
                stmt_ids.add(t["id"])
    for t in sent:
        if t["accountId"] in dep:
            pull_ids.add(t["id"])
    missing = stmt_ids - pull_ids          # named on a statement, absent from our pull
    orphan  = pull_ids - stmt_ids          # in our pull, on no statement

    # 2. every statement month reproduced from the ledger, not just the 12 FY months
    ties = total = 0
    for aid, sts in statements.items():
        if aid not in dep:
            continue
        rows = sorted([t for t in sent if t["accountId"] == aid and t.get("postedAt")],
                      key=lambda x: x["postedAt"])
        for s in sts:
            end = (s.get("endDate") or "")[:10]
            run = M(sum(t["amount"] for t in rows if t["postedAt"][:10] <= end))
            total += 1
            ties += 1 if abs(run - M(s["endingBalance"])) < 0.005 else 0

    # 3. inception-to-date must equal the live balance
    itd = M(sum(t["amount"] for t in sent if t["accountId"] in dep))
    live = M(sum(a["currentBalance"] for a in accounts))

    # 4. nothing was excluded FROM THE YEAR by the status filter
    not_sent = [t for t in txs if t["status"] != "sent"]
    not_sent_in_fy = [t for t in not_sent
                      if (t.get("postedAt") or t["createdAt"])[:10] >= FY0
                      and (t.get("postedAt") or t["createdAt"])[:10] < FY1]
    sent_without_posted = [t for t in sent if not t.get("postedAt")]

    # 5. credit account: zero-sum, and every card payment mirrored on the bank side
    credit_sum = M(sum(t["amount"] for t in sent if t["accountId"] in cre))
    pays_bank = sorted((t["postedAt"][:10], M(-t["amount"])) for t in sent
                       if t["accountId"] in dep and "AUTOPAY" in
                       ((t.get("bankDescription") or "") + (t.get("counterpartyName") or "")).upper())
    pays_card = sorted((t["postedAt"][:10], M(t["amount"])) for t in sent
                       if t["accountId"] in cre and "AUTOPAY" in
                       ((t.get("bankDescription") or "") + (t.get("counterpartyName") or "")).upper())
    mirrored = sum(1 for p in pays_bank if p in pays_card)
    credit_has_statements = any(k in cre for k in statements)

    # 6. how far the FY boundary could move before any figure changes
    posted = sorted(t["postedAt"] for t in sent if t.get("postedAt"))
    import datetime
    def dt(x):
        # Mercury emits 5- and 6-digit fractional seconds; fromisoformat wants exactly 6
        import re as _re
        x = x.replace("Z", "+00:00")
        m = _re.match(r"(.*\.)(\d+)(\+00:00)$", x)
        if m:
            x = m.group(1) + (m.group(2) + "000000")[:6] + m.group(3)
        return datetime.datetime.fromisoformat(x)
    b0, b1 = dt(FY0 + "T00:00:00+00:00"), dt(FY1 + "T00:00:00+00:00")
    before = max([dt(p) for p in posted if dt(p) < b0], default=None)
    after  = min([dt(p) for p in posted if dt(p) >= b0], default=None)
    lastin = max([dt(p) for p in posted if dt(p) < b1], default=None)
    firstout = min([dt(p) for p in posted if dt(p) >= b1], default=None)
    margins = [ (b0-before).total_seconds()/3600 if before else None,
                (after-b0).total_seconds()/3600 if after else None,
                (b1-lastin).total_seconds()/3600 if lastin else None,
                (firstout-b1).total_seconds()/3600 if firstout else None ]
    tightest = min([m for m in margins if m is not None])

    return {
        "stmtIds": len(stmt_ids), "pullIds": len(pull_ids),
        "missing": len(missing), "orphan": len(orphan),
        "monthsTied": ties, "monthsTotal": total,
        "inceptionToDate": itd, "liveBalance": live,
        "itdAgrees": abs(itd - live) < 0.005,
        "notSent": len(not_sent), "notSentInFY": len(not_sent_in_fy),
        "sentWithoutPostedAt": len(sent_without_posted),
        "creditSum": credit_sum, "cardPayments": len(pays_bank), "mirrored": mirrored,
        "creditHasStatements": credit_has_statements,
        "boundaryMarginHours": round(tightest, 2),
    }


if __name__ == "__main__":
    e = compute()
    for k, v in e.items():
        print("  %-22s %s" % (k, v))
