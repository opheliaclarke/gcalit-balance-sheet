#!/usr/bin/env python3
"""Prove every formula written into the .xlsx recalculates to the value we published.

If a formula is wrong, Excel recalculates on open and silently shows a DIFFERENT
number from the one on the web page. That is the worst failure mode this project
has, so it gets its own evaluator rather than a spot check.
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(HERE, "out", "sheets.json")))
BOOK = {s["name"]: s for s in D["sheets"]}

def col_i(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1

def cell(sheet, ref):
    m = re.fullmatch(r"\$?([A-Z]+)\$?(\d+)", ref)
    c, r = col_i(m.group(1)), int(m.group(2))
    s = BOOK[sheet]
    if r == 1:
        return s["columns"][c]
    v = s["rows"][r - 2][c] if r - 2 < len(s["rows"]) and c < len(s["rows"][r - 2]) else None
    return 0 if v is None or v == "" else v

def rng(sheet, a, b):
    m1 = re.fullmatch(r"\$?([A-Z]+)\$?(\d+)", a); m2 = re.fullmatch(r"\$?([A-Z]+)\$?(\d+)", b)
    c0, r0 = col_i(m1.group(1)), int(m1.group(2)); c1, r1 = col_i(m2.group(1)), int(m2.group(2))
    out = []
    for r in range(min(r0, r1), max(r0, r1) + 1):
        for c in range(min(c0, c1), max(c0, c1) + 1):
            out.append(cell(sheet, "%s%d" % (chr(65 + c) if c < 26 else "A" + chr(65 + c - 26), r)))
    return out

TOKEN = re.compile(r"""(?P<sheet>[A-Za-z]+)!(?P<sref>\$?[A-Z]+\$?\d+(?::\$?[A-Z]+\$?\d+)?)|(?P<ref>\$?[A-Z]+\$?\d+(?::\$?[A-Z]+\$?\d+)?)""")

def evaluate(sheet, f):
    f = f.strip()
    # IF(cond,"A","B")
    m = re.fullmatch(r'IF\((.+?)=(.+?),"(.*?)","(.*?)"\)', f)
    if m:
        a, b = evaluate(sheet, m.group(1)), evaluate(sheet, m.group(2))
        return m.group(3) if abs(float(a) - float(b)) < 0.005 else m.group(4)
    # SUMIF($D$2:$D$10,"Spend",$E$2:$E$10)
    m = re.fullmatch(r'SUMIF\((.+?),"(.*?)",(.+?)\)', f)
    if m:
        crit = rng(sheet, *m.group(1).split(":"))
        vals = rng(sheet, *m.group(3).split(":"))
        return round(sum(v for c, v in zip(crit, vals) if c == m.group(2) and isinstance(v, (int, float))), 2)
    # SUM(A1:A9)  — may be one term inside a larger expression, handled below
    def sub(mo):
        sh = mo.group("sheet") or sheet
        ref = mo.group("sref") or mo.group("ref")
        if ":" in ref:
            return "0"
        v = cell(sh, ref)
        return repr(float(v)) if isinstance(v, (int, float)) else "0"
    expr = f
    # expand SUM(...) first
    while True:
        m = re.search(r"SUM\(([^()]+)\)", expr)
        if not m:
            break
        arg = m.group(1)
        if "!" in arg:
            sh, arg = arg.split("!")
        else:
            sh = sheet
        a, b = arg.split(":")
        tot = sum(v for v in rng(sh, a, b) if isinstance(v, (int, float)))
        expr = expr[:m.start()] + repr(round(tot, 2)) + expr[m.end():]
    expr = TOKEN.sub(sub, expr)
    expr = re.sub(r"[A-Za-z]+!", "", expr)
    return round(eval(expr, {"__builtins__": {}}, {}), 2)

def main():
    total = ok = 0
    fails = []
    for name, s in BOOK.items():
        for key, formula in s.get("formulas", {}).items():
            ri, cl = key.split(",")
            ri = int(ri)
            stated = s["rows"][ri][col_i(cl)]
            got = evaluate(name, formula)
            total += 1
            if isinstance(stated, (int, float)) and isinstance(got, (int, float)):
                good = abs(float(stated) - float(got)) < 0.005
            else:
                good = str(stated) == str(got)
            if good:
                ok += 1
            else:
                fails.append((name, "%s%d" % (cl, ri + 2), formula, stated, got))
    print("FORMULA RECALCULATION TEST")
    print("  %d formulas written into the .xlsx" % total)
    print("  %d recalculate to exactly the published value" % ok)
    for f in fails:
        print("  *** %s!%s  =%s  published=%r  recalculates to=%r" % f)
    # positive control: the evaluator must be able to fail
    ci = BOOK["Summary"]["columns"].index("Amount (USD)")
    ri = next(i for i, r in enumerate(BOOK["Summary"]["rows"])
              if str(r[0]).startswith("CLOSING BALANCE"))
    bad = evaluate("Summary", "D2+D%d+1" % (ri, ))
    published = BOOK["Summary"]["rows"][ri][ci]
    print("  control: a deliberately wrong formula gives %.2f vs published %.2f -> %s"
          % (bad, published, "detected" if abs(bad - published) > 0.005 else "*** EVALUATOR IS BLIND ***"))
    return 0 if not fails else 1

if __name__ == "__main__":
    sys.exit(main())
