#!/usr/bin/env python3
"""The formula map — ONE definition, used by both the web page (formula bar) and the
.xlsx writer (<f> elements). Defining it twice is how the two drift apart.

Addressing: in the workbook, row 1 is the column headers and data row i (0-based)
lives at spreadsheet row i+2.
"""

def R(i):        # data row index -> spreadsheet row number
    return i + 2


def summary(rows):
    f = {}
    # (data row index, column letter) -> formula
    f[(6,  "D")] = "SUM(D5:D7)"          # TOTAL MONEY IN            -> row 8
    f[(6,  "C")] = "SUM(C5:C7)"
    f[(14, "D")] = "SUM(D11:D15)"        # TOTAL MONEY OUT           -> row 16
    f[(14, "C")] = "SUM(C11:C15)"
    f[(15, "D")] = "SUM(D11:D13)"        #   of which expenses       -> row 17
    f[(15, "C")] = "SUM(C11:C13)"
    f[(16, "D")] = "SUM(D14:D15)"        #   of which sent to card   -> row 18
    f[(16, "C")] = "SUM(C14:C15)"
    f[(18, "D")] = "D8+D16"              # NET CHANGE                -> row 20
    f[(20, "D")] = "D2+D20"              # CLOSING = opening + net   -> row 22
    return f


def monthly(rows):
    f = {}
    n = len(rows) - 1                    # 12 month rows, last row is FULL YEAR
    for i in range(n):
        r = R(i)
        f[(i, "F")] = "C%d+D%d+E%d" % (r, r, r)          # Net
        f[(i, "G")] = "B%d+F%d" % (r, r)                 # Closing
        if i > 0:
            f[(i, "B")] = "G%d" % (r - 1)                # Opening = last month's closing
        f[(i, "I")] = 'IF(G%d=H%d,"MATCH","MISMATCH")' % (r, r)
    last = R(n)
    f[(n, "B")] = "B2"
    for col in ("C", "D", "E", "F"):
        f[(n, col)] = "SUM(%s2:%s%d)" % (col, col, R(n - 1))
    f[(n, "G")] = "B%d+F%d" % (last, last)
    f[(n, "J")] = "SUM(J2:J%d)" % R(n - 1)
    return f


def cards(rows, n_tx):
    f = {}
    lo, hi = 2, R(n_tx - 1)
    base = n_tx + 1                      # index of the first total row
    f[(base,     "E")] = 'SUMIF($D$%d:$D$%d,"Spend",$E$%d:$E$%d)' % (lo, hi, lo, hi)
    f[(base + 1, "E")] = 'SUMIF($D$%d:$D$%d,"Refund / reversal",$E$%d:$E$%d)' % (lo, hi, lo, hi)
    f[(base + 2, "E")] = "E%d+E%d" % (R(base), R(base + 1))
    f[(base + 3, "E")] = "-Summary!D18"
    f[(base + 4, "E")] = "E%d+E%d" % (R(base + 2), R(base + 3))
    return f


def reconciliation(rows, n_ledger):
    f = {}
    f[(2, "C")] = "C10-C11"                                        # B back-computed
    f[(3, "C")] = "Summary!D2+SUM(Ledger!G2:G%d)" % R(n_ledger - 1)  # C forward
    for i in (2, 3, 4):
        r = R(i)
        f[(i, "E")] = "C%d-D%d" % (r, r)
        f[(i, "F")] = 'IF(E%d=0,"MATCH","MISMATCH")' % r
    return f


def accounts(rows, n_acct):
    f = {}
    for i in range(n_acct):
        r = R(i)
        f[(i, "E")] = "D%d-C%d" % (r, r)
    tot = n_acct + 1                      # blank row then TOTAL
    lo, hi = 2, R(n_acct - 1)
    for col in ("C", "D", "E", "F"):
        f[(tot, col)] = "SUM(%s%d:%s%d)" % (col, lo, col, hi)
    return f


def build(sheets, counts):
    """counts: {'cardTx':int,'ledger':int,'acct':int}"""
    out = {}
    for s in sheets:
        n = s["name"]
        if n == "Summary":        m = summary(s["rows"])
        elif n == "Monthly":      m = monthly(s["rows"])
        elif n == "Cards":        m = cards(s["rows"], counts["cardTx"])
        elif n == "Reconciliation": m = reconciliation(s["rows"], counts["ledger"])
        elif n == "Accounts":     m = accounts(s["rows"], counts["acct"])
        else:                     m = {}
        out[n] = {"%d,%s" % (k[0], k[1]): v for k, v in m.items()}
    return out
