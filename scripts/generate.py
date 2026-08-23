#!/usr/bin/env python3
"""Generate site/index.html — one self-contained spreadsheet page.

Design tokens live in TOKENS and the CSS below; the grid mechanics (selection,
clipboard TSV, tabs, keyboard nav) are design-independent so the look can be
swapped without touching behaviour.
"""
import json, os, html, datetime

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT, SITE = os.path.join(HERE, "out"), os.path.join(HERE, "docs")


def colname(i):
    s = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        s = chr(65 + rem) + s
    return s


def main():
    d = json.load(open(os.path.join(OUT, "sheets.json")))
    full = json.load(open(os.path.join(OUT, "balance_sheet.json")))
    gen = datetime.datetime.utcnow().strftime("%d %B %Y")
    payload = json.dumps({
        "sheets": d["sheets"], "meta": d["meta"],
        "opening": d["opening"], "closing": d["closing"], "netChange": d["netChange"],
        "closings": d["monthlyClosings"], "monthsMatched": d["monthsMatched"],
        "monthsTotal": d["monthsTotal"],
        "txns": len([x for x in full["ledger"] if not x["isCard"]]),
        "txnsAll": len(full["ledger"]),
    }, separators=(",", ":"))
    os.makedirs(SITE, exist_ok=True)
    with open(os.path.join(SITE, "index.html"), "w") as fh:
        tpl = open(os.path.join(HERE, "scripts", "page.html")).read()
        fh.write(tpl.replace("__DATA__", payload).replace("__GEN__", gen))
    print("wrote docs/index.html  %d bytes" % os.path.getsize(os.path.join(SITE, "index.html")))

if __name__ == "__main__":
    main()
