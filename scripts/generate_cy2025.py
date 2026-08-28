#!/usr/bin/env python3
"""Write docs/2/index.html — page 2, the calendar-2025 statement and peak balance.

Page 2 is generated FROM page.html, never by hand-editing it: same grid mechanics,
same clipboard TSV, same tabs, same print stylesheet. Every substitution below is
asserted, so a change to page 1 that moves one of these lines fails the build loudly
instead of silently shipping page 2 with page 1's dates on it.
"""
import json, os, datetime

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(HERE, "out-cy2025")
SITE = os.path.join(HERE, "docs", "2")

def sub(s, old, new, label):
    assert s.count(old) == 1, "page.html no longer contains exactly one %s" % label
    return s.replace(old, new)

def main():
    d = json.load(open(os.path.join(OUT, "sheets.json")))
    tpl = open(os.path.join(HERE, "scripts", "page.html")).read()

    tpl = sub(tpl,
      "<title>GCALIT LLC — Mercury balance sheet — FY 2025-26</title>",
      "<title>GCALIT LLC — Mercury bank statement — 1 Jan to 31 Dec 2025</title>", "title")
    tpl = sub(tpl,
      '<meta name="description" content="Cash position for GCALIT LLC\'s Mercury bank account, 1 April 2025 to 31 March 2026.">',
      '<meta name="description" content="Bank statement and peak balance for GCALIT LLC\'s Mercury account, 1 January 2025 to 31 December 2025.">', "description")
    tpl = sub(tpl,
      '<a id="dlx" href="GCALIT-Mercury-FY2025-26.xlsx" download>Download .xlsx</a>',
      '<a id="dlx" href="GCALIT-Mercury-CY2025.xlsx" download>Download .xlsx</a>', "xlsx link")
    tpl = sub(tpl,
      '<a class="xpage" href="2/">Page 2 &middot; 2025 &amp; peak balance &rarr;</a>',
      '<a class="xpage" href="../">&larr; Page 1 &middot; FY 2025-26</a>', "cross-page link")
    tpl = sub(tpl,
      '  +" Bank · FY 1 Apr 2025 – 31 Mar 2026";',
      '  +" Bank · 1 Jan 2025 – 31 Dec 2025";', "identity line")
    tpl = sub(tpl,
      '$("#note").textContent = D.txns+" transactions · "+D.monthsMatched+"/"+D.monthsTotal\n  +" months tie to statement · 4 derivation routes agree to $0.00";',
      '$("#note").textContent = D.txns+" transactions · "+D.monthsMatched+"/"+D.monthsTotal\n'
      '  +" months tie to statement · peak balance reached "+D.peakDate+" · 6 derivation routes agree to $0.00";', "note line")
    tpl = sub(tpl,
      '  fig("Opening · 1 Apr 2025", cash(D.opening), "") +\n'
      '  fig("Closing · 31 Mar 2026", cash(D.closing), " fig--close") +\n'
      '  fig("Net change", (D.netChange<0?MINUS:"+")+"$"+grp(D.netChange), "");',
      '  fig("Opening · 1 Jan 2025", cash(D.opening), "") +\n'
      '  fig("Closing · 31 Dec 2025", cash(D.closing), " fig--close") +\n'
      '  fig("Net change", (D.netChange<0?MINUS:"+")+"$"+grp(D.netChange), "") +\n'
      '  fig("Peak balance · "+D.peakDate, cash(D.peak), " fig--peak");', "figure row")

    # page-2-only styling: the peak is the second thing Bob asked for, so it gets its own mark.
    # The .xpage rule itself lives in page.html and is inherited.
    tpl = sub(tpl, "</style>\n</head>",
      "\n/* page 2 */\n"
      ".fig--peak .fig__v{color:var(--accent);border-bottom:3px solid var(--accent);padding-bottom:3px}\n"
      ".fig--peak .fig__k{color:var(--accent)}\n"
      "@media (max-width:1100px){\n"
      "  .figs{flex-wrap:wrap}\n"
      "  .fig{flex:1 1 50%;min-width:0;border-bottom:1px solid var(--grid)}\n"
      "  .fig:nth-child(2n){border-right:0}\n"
      "}\n"
      "</style>\n</head>", "style close")

    payload = json.dumps({
        "sheets": d["sheets"], "meta": d["meta"],
        "opening": d["opening"], "closing": d["closing"], "netChange": d["netChange"],
        "peak": d["peak"], "peakDate": d["peakDate"],
        "closings": d["monthlyClosings"], "monthsMatched": d["monthsMatched"],
        "monthsTotal": d["monthsTotal"], "txns": d["txns"],
    }, separators=(",", ":"))
    gen = datetime.datetime.utcnow().strftime("%d %B %Y")
    os.makedirs(SITE, exist_ok=True)
    with open(os.path.join(SITE, "index.html"), "w") as fh:
        fh.write(tpl.replace("__DATA__", payload).replace("__GEN__", gen))
    print("wrote docs/2/index.html  %d bytes" % os.path.getsize(os.path.join(SITE, "index.html")))

if __name__ == "__main__":
    main()
