#!/usr/bin/env python3
"""Pull everything needed for the calendar-year 2025 statement + peak balance.

Read-only. Uses the same client (and therefore the same four trap guards) as the FY build.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mercury import Mercury, redact

RAW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "raw-cy2025")
os.makedirs(RAW, exist_ok=True)

def dump(name, obj):
    p = os.path.join(RAW, name)
    with open(p, "w") as fh:
        json.dump(obj, fh, indent=1)
    print("  wrote %s (%d bytes)" % (name, os.path.getsize(p)))

m = Mercury()
print("token:", redact(m.token))

print("organization")
dump("organization.json", m.organization())

print("accounts")
accts = m.accounts()
dump("accounts.json", accts)
for a in accts:
    print("   %-28s %-9s current=%s available=%s" % (a["name"], a["kind"], a["currentBalance"], a["availableBalance"]))

print("credit accounts")
credit = m.credit_accounts()
dump("credit.json", credit)

print("statements (every account, all time)")
stmts = {}
for a in accts:
    s = m.statements(a["id"])
    stmts[a["id"]] = s
    print("   %s: %d statements %s .. %s" % (a["name"], len(s),
          s[0]["startDate"] if s else "-", s[-1]["endDate"] if s else "-"))
dump("statements.json", stmts)

# T2: postedStart/postedEnd, not start/end.
print("transactions posted 2025-01-01..2025-12-31 (CY2025)")
cy = m.transactions(posted_start="2025-01-01", posted_end="2025-12-31")
dump("transactions_cy2025.json", cy)
print("   %d rows" % len(cy))

print("transactions posted inception..today (full, for independent reconstruction)")
allt = m.transactions(posted_start="2024-01-01", posted_end="2026-12-31")
dump("transactions_all.json", allt)
print("   %d rows" % len(allt))

print("transactions by createdAt 2025 (to MEASURE the T2 gap, not to use)")
created = m.transactions(created_start="2025-01-01", created_end="2025-12-31")
dump("transactions_created2025.json", created)
print("   %d rows" % len(created))

print("API calls:", m.calls)
