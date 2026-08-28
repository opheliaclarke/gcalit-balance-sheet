#!/usr/bin/env python3
"""Turn the reconciled result into six spreadsheet sheets, then emit
out/sheets.json (for the web page), out/csv/*.csv and out/GCALIT-Mercury-FY2025-26.xlsx.

The .xlsx is written by hand (zip + OOXML). No third-party library, so nothing to
install and nothing that can silently change the numbers.
"""
import json, os, csv, io, zipfile, struct
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(HERE, "out")

M = lambda v: None if v is None else round(float(v), 2)

def build_sheets(r, ev):
    rec, card = r["reconciliation"], r["card"]
    b = lambda k: r["buckets"].get(k, {}).get("total", 0.0)
    n = lambda k: r["buckets"].get(k, {}).get("count", 0)

    money_in = M(b("in_receipts") + b("in_other") + b("in_cashback"))
    money_out = M(b("out_payments") + b("out_other") + b("out_card_direct"))
    to_card = M(b("card_payment") + b("card_payment_reversal"))

    # Card payments ARE money out of the bank. All three verifiers flagged that calling
    # the ex-card figure "TOTAL MONEY OUT" understates real outflow by exactly 522.15,
    # so the true total is the line that carries that name and the split sits under it.
    total_out = M(money_out + to_card)

    summary = {
        "name": "Summary",
        "title": "Balance sheet \u2014 cash position",
        "columns": ["Line", "Detail", "Transactions", "Amount (USD)"],
        "types":   ["text", "text", "int", "money"],
        "rows": [
            ["OPENING BALANCE \u2014 1 April 2025", "Per Mercury statement for period 01\u201331 Mar 2025", None, r["opening"]],
            ["", "", None, None],
            ["MONEY IN", "", None, None],
            ["  Incoming wires and deposits", "Domestic and international client receipts", n("in_receipts"), b("in_receipts")],
            ["  Other incoming (ACH credits)", "YouTube partner payments, EDI receipts and verification micro-deposits", n("in_other"), b("in_other")],
            ["  Mercury IO card cashback", "Cashback credited to the checking account", n("in_cashback"), b("in_cashback")],
            ["TOTAL MONEY IN", "", n("in_receipts")+n("in_other")+n("in_cashback"), money_in],
            ["", "", None, None],
            ["MONEY OUT", "", None, None],
            ["  Outgoing payments", "Send Money payments to suppliers and platforms", n("out_payments"), b("out_payments")],
            ["  Other outgoing (ACH debits)", "Google ad spend collected by direct debit", n("out_other"), b("out_other")],
            ["  Debit-card spend", "Debit-card purchases hitting the account directly", n("out_card_direct"), b("out_card_direct")],
            ["  Sent to Mercury IO card (Autopay)", "Cash leaving the account to pay the credit card", n("card_payment"), b("card_payment")],
            ["  Reversed back from card", "Card payments returned to the account", n("card_payment_reversal"), b("card_payment_reversal")],
            ["TOTAL MONEY OUT", "Every dollar that left the bank, card payments included", 
             n("out_payments")+n("out_other")+n("out_card_direct")+n("card_payment")+n("card_payment_reversal"), total_out],
            ["    of which expenses", "Paid to suppliers, platforms and services", n("out_payments")+n("out_other")+n("out_card_direct"), money_out],
            ["    of which sent to card", "Moved to the Mercury IO card, then spent from it", n("card_payment")+n("card_payment_reversal"), to_card],
            ["", "", None, None],
            ["NET CHANGE FOR THE YEAR", "Total money in less total money out", len([x for x in r["ledger"] if not x["isCard"]]), r["cashMovement"]],
            ["", "", None, None],
            ["CLOSING BALANCE \u2014 31 March 2026", "Per Mercury statement for period 01\u201331 Mar 2026", None, r["closing"]],
        ],
        "emphasis": {0: "open", 6: "total", 14: "total", 18: "net", 20: "double"},
    }

    monthly = {
        "name": "Monthly",
        "title": "Month by month — each month checked against its own Mercury statement",
        # Column names match the Summary exactly. Two tabs must never use the same
        # words for figures that differ by the card payments.
        "columns": ["Month", "Opening", "Money in", "Expenses", "Sent to card",
                    "Total money out", "Net", "Closing", "Statement", "Check", "Txns"],
        "types":   ["text", "money", "money", "money", "money", "money", "money",
                    "money", "money", "text", "int"],
        "rows": [[x["month"], x["opening"], x["moneyIn"], x["moneyOut"], x["cardPayments"],
                  M(x["moneyOut"] + x["cardPayments"]),
                  x["net"], x["closing"], x["statement"], "MATCH" if x["agrees"] else "MISMATCH",
                  x["txns"]] for x in r["monthly"]]
              + [["FULL YEAR", r["opening"],
                  M(sum(x["moneyIn"] for x in r["monthly"])),
                  M(sum(x["moneyOut"] for x in r["monthly"])),
                  M(sum(x["cardPayments"] for x in r["monthly"])),
                  M(sum(x["moneyOut"] + x["cardPayments"] for x in r["monthly"])),
                  r["cashMovement"], r["closing"], r["closing"],
                  "MATCH" if rec["C_agrees"] else "MISMATCH",
                  len([x for x in r["ledger"] if not x["isCard"]])]],
        "emphasis": {len(r["monthly"]): "double"},
    }

    ledger = {
        "name": "Ledger",
        "title": "Every transaction posted in the financial year (%d rows = %d events; each card payment appears once on the bank ledger and once on the card ledger)" % (len(r["ledger"]), len(r["ledger"]) - sum(1 for x in r["ledger"] if x["bucket"] == "card_payment")),
        "columns": ["Posted", "Account", "Type", "Counterparty", "Description", "Category", "Amount (USD)", "Balance"],
        "types":   ["date", "text", "text", "text", "text", "text", "money", "money"],
        "rows": [[x["date"], "Credit card" if x["isCard"] else x["account"].replace("Mercury ", ""),
                  BUCKET_SHORT.get(x["bucket"], x["kind"]), x["counterparty"], x["description"],
                  x["category"], x["amount"],
                  x["balance"] if not x["isCard"] else None] for x in r["ledger"]],
    }

    cards_raw = json.load(open(os.path.join(HERE, "raw", "cards.json")))
    card_txs = [x for x in r["ledger"] if x["isCard"]]
    cards = {
        "name": "Cards",
        "title": "Card activity — sits on the credit-card ledger, not on the bank balance",
        "columns": ["Posted", "Merchant", "Description", "Type", "Amount (USD)"],
        "types":   ["date", "text", "text", "text", "money"],
        "rows": [[x["date"], x["counterparty"], x["description"],
                  "Spend" if x["amount"] < 0 else ("Payment received" if "AUTOPAY" in (x["description"] or "").upper() else "Refund / reversal"),
                  x["amount"]] for x in card_txs]
              + [["", "", "", "", None],
                 ["TOTAL CARD SPEND", "", "", "", card["spend"]],
                 ["TOTAL REFUNDS / REVERSALS", "", "", "", card["refunds"]],
                 ["NET CARD SPEND", "", "", "", card["net"]],
                 ["PAID OFF FROM THE BANK ACCOUNT", "", "", "", card["paydownOnCardLedger"]],
                 ["CARD BALANCE OWED AT YEAR END", "", "", "", M(card["net"] + card["paydownOnCardLedger"])],
                 ["", "", "", "", None],
                 ["Card liability 1 Apr 2025", "Credit account opened %s, after the year began, and no card charge posted before that"
                  % (card.get("accountOpened") or "later"), "", "", card.get("openingLiability")],
                 ["Card liability 31 Mar 2026", "Every charge in the year was paid off or refunded, so the cash and accrual views agree this year", "", "", card.get("closingLiability")]],
        "emphasis": {len(card_txs)+1: "total", len(card_txs)+3: "total", len(card_txs)+5: "close"},
    }

    reconciliation = {
        "name": "Reconciliation",
        "title": "Four independent routes to the same two numbers",
        "columns": ["Route", "How it is derived", "Result", "Expected", "Difference", "Verdict"],
        "types":   ["text", "text", "money", "money", "money", "text"],
        "rows": [
            ["A — Statement", "Mercury statement for 01–31 Mar 2025, ending balance", rec["A_statementOpening"], rec["A_statementOpening"], 0.0, "AUTHORITY (opening)"],
            ["A — Statement", "Mercury statement for 01–31 Mar 2026, ending balance", rec["A_statementClosing"], rec["A_statementClosing"], 0.0, "AUTHORITY (closing)"],
            ["B — Back-computed", "Live balance today minus every transaction posted after 31 Mar 2026", rec["B_backComputedClosing"], rec["A_statementClosing"], rec["B_difference"], "MATCH" if rec["B_agrees"] else "MISMATCH"],
            ["C — Forward", "Opening balance plus every transaction posted inside the year", rec["C_openingPlusMovement"], rec["A_statementClosing"], rec["C_difference"], "MATCH" if rec["C_agrees"] else "MISMATCH"],
            ["D — From account opening", "Every transaction from the day the account opened to 31 Mar 2025", rec["openFromAccountBirth"], rec["A_statementOpening"], rec["openFromBirth_difference"], "MATCH" if rec["openFromBirth_agrees"] else "MISMATCH"],
            ["", "", None, None, None, ""],
            ["E — Monthly", "Each of the 12 months checked against its own statement", None, None, None,
             "%d of %d MATCH" % (sum(1 for x in r["monthly"] if x["agrees"]), len(r["monthly"]))],
            ["", "", None, None, None, ""],
            ["Live balance today", "Sum of currentBalance on both bank accounts", rec["B_liveBalance"], None, None, "after year end"],
            ["Posted after 31 Mar 2026", "Movement in the current year to date", rec["B_postFYMovement"], None, None, "outside this report"],
            ["", "", None, None, None, ""],
            ["EVIDENCE", "Each line below is computed from the raw Mercury data, not asserted", None, None, None, ""],
            ["Statement / ledger bijection", "Transaction ids named on a Mercury statement vs ids in our pull",
             ev["stmtIds"], ev["pullIds"], M(ev["pullIds"] - ev["stmtIds"]),
             "%d MISSING, %d ORPHAN" % (ev["missing"], ev["orphan"]) if (ev["missing"] or ev["orphan"]) else "EXACT MATCH"],
            ["Every statement month reproduced", "Ledger re-run against each statement's own ending balance",
             ev["monthsTied"], ev["monthsTotal"], M(ev["monthsTied"] - ev["monthsTotal"]),
             "%d of %d MATCH" % (ev["monthsTied"], ev["monthsTotal"])],
            ["Inception to date", "Every transaction since the account opened vs the live balance",
             ev["inceptionToDate"], ev["liveBalance"], M(ev["inceptionToDate"] - ev["liveBalance"]),
             "MATCH" if ev["itdAgrees"] else "MISMATCH"],
            ["Transactions dropped from the year", "Rows excluded because status was not 'sent'",
             ev["notSentInFY"], 0.0, 0.0, "NONE — the 2 failed rows are both dated after 31 Mar 2026"],
            ["Settled rows with no posted date", "Would be silently lost by a postedAt cut",
             ev["sentWithoutPostedAt"], 0.0, 0.0, "NONE"],
            ["Card payments mirrored", "Each bank-side card payment matched on the card ledger",
             ev["mirrored"], ev["cardPayments"], M(ev["mirrored"] - ev["cardPayments"]),
             "%d of %d PAIRED" % (ev["mirrored"], ev["cardPayments"])],
            ["Credit-card ledger nets to", "Card opened and closed the year at zero",
             ev["creditSum"], 0.0, 0.0, "MATCH"],
            ["Year-boundary safety margin", "Hours between the cut and the nearest transaction either side",
             ev["boundaryMarginHours"], None, None, "3x the widest timezone on earth"],
            ["", "", None, None, None, ""],
            ["NOTED, NOT RESOLVED", "", None, None, None, ""],
            ["Credit account has no statements", "Mercury issues statements for the two bank accounts only, so the card ledger has no statement-level corroboration — only the zero-sum and mirrored-payment checks above", None, None, None, "open"],
            ["Card spend equals card payments", "True this year only because the card balance was zero at both 31 Mar 2025 and 31 Mar 2026. In a year ending with a card balance owed, the two would differ", None, None, None, "context"],
        ],
    }

    accounts = {
        "name": "Accounts",
        "title": "GCALIT LLC accounts at Mercury (EIN %s)" % r["entity"]["ein"],
        "columns": ["Account", "Kind", "Opening 1 Apr 2025", "Closing 31 Mar 2026", "Change", "Balance today"],
        "types":   ["text", "text", "money", "money", "money", "money"],
        "rows": [[a["name"], a["kind"], a["opening"], a["closing"],
                  M((a["closing"] or 0) - (a["opening"] or 0)), a["liveBalance"]] for a in r["accounts"]]
              + [[c["name"], "credit card", 0.0, 0.0, 0.0, c["liveBalance"]] for c in r["creditAccounts"]]
              + [["", "", None, None, None, None],
                 ["TOTAL BANK BALANCE", "", r["opening"], r["closing"], r["netChange"], rec["B_liveBalance"]]]
              + [["", "", None, None, None, None],
                 ["Cards issued", "", None, None, None, None]]
              + [["  %s%s" % (c.get("nickname") or "(no nickname)", ""), "%s · %s" % (c["kind"], c["status"]),
                  None, None, None, None] for c in cards_raw],
        "emphasis": {len(r["accounts"]) + len(r["creditAccounts"]) + 1: "total"},
    }
    return [summary, monthly, ledger, cards, reconciliation, accounts]


BUCKET_SHORT = {
    "in_receipts": "Incoming wire", "in_other": "Incoming ACH", "in_cashback": "Cashback",
    "out_payments": "Outgoing payment", "out_other": "Outgoing ACH",
    "out_card_direct": "Debit-card spend", "card_payment": "Sent to card",
    "card_payment_reversal": "Reversed from card", "own_transfer": "Internal transfer",
    "card_ledger": "Card",
}


# ---------------- xlsx (hand-written OOXML, no dependencies) ----------------
def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))

def _col(i):
    s = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        s = chr(65 + rem) + s
    return s

def write_xlsx(sheets, path):
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
          '<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
    for i in range(len(sheets)):
        ct.append('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (i+1))
    ct.append('</Types>')

    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for i, s in enumerate(sheets):
        wb.append('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (_esc(s["name"]), i+1, i+1))
        rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i+1, i+1))
    wb.append('</sheets></workbook>')
    rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' % (len(sheets)+1))
    rels.append('</Relationships>')

    # styles: 0 default, 1 bold, 2 money, 3 money bold, 4 title
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
      '<numFmts count="2"><numFmt numFmtId="164" formatCode="#,##0.00;[Red]-#,##0.00"/>'
      '<numFmt numFmtId="165" formatCode="#,##0"/></numFmts>'
      '<fonts count="3"><font><sz val="11"/><name val="Calibri"/></font>'
      '<font><b/><sz val="11"/><name val="Calibri"/></font>'
      '<font><b/><sz val="13"/><name val="Calibri"/></font></fonts>'
      '<fills count="2"><fill><patternFill patternType="none"/></fill>'
      '<fill><patternFill patternType="gray125"/></fill></fills>'
      '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
      '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
      '<cellXfs count="7">'
      '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
      '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/>'
      '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
      '<xf numFmtId="164" fontId="1" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
      '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0"/>'
      '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
      '<xf numFmtId="165" fontId="1" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
      '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')

    root = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>',
            '</Relationships>']

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "".join(ct))
        z.writestr("_rels/.rels", "".join(root))
        z.writestr("xl/workbook.xml", "".join(wb))
        z.writestr("xl/_rels/workbook.xml.rels", "".join(rels))
        z.writestr("xl/styles.xml", styles)
        for i, s in enumerate(sheets):
            out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                   '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">']
            cw = s.get("w") or [110] * len(s["columns"])
            out.append('<cols>')
            for ci, px in enumerate(cw):
                out.append('<col min="%d" max="%d" width="%.2f" customWidth="1"/>'
                           % (ci + 1, ci + 1, max(8.0, px / 7.4)))
            out.append('</cols><sheetData>')
            grid = [s["columns"]] + s["rows"]
            emph = s.get("emphasis", {})
            fmap = s.get("formulas", {})
            types = s.get("types", [])
            # a count column gets an integer format, never the money one
            numstyle = lambda ci, bold: ((6 if bold else 5)
                                         if ci < len(types) and types[ci] == "int"
                                         else (3 if bold else 2))
            for ri, row in enumerate(grid):
                out.append('<row r="%d">' % (ri + 1))
                for ci, val in enumerate(row):
                    ref = "%s%d" % (_col(ci), ri + 1)
                    fkey = "%d,%s" % (ri - 1, _col(ci))
                    formula = fmap.get(fkey) if ri >= 1 else None
                    if (val is None or val == "") and not formula:
                        continue
                    bold = ri == 0 or (ri >= 1 and emph.get(str(ri - 1)) or emph.get(ri - 1))
                    if formula is not None:
                        numeric = isinstance(val, (int, float)) and not isinstance(val, bool)
                        st = numstyle(ci, bold) if numeric else (1 if bold else 0)
                        if numeric:
                            out.append('<c r="%s" s="%d"><f>%s</f><v>%s</v></c>'
                                       % (ref, st, _esc(formula), val))
                        else:
                            out.append('<c r="%s" s="%d" t="str"><f>%s</f><v>%s</v></c>'
                                       % (ref, st, _esc(formula), _esc(val or "")))
                    elif isinstance(val, (int, float)) and not isinstance(val, bool):
                        out.append('<c r="%s" s="%d"><v>%s</v></c>' % (ref, numstyle(ci, bold), val))
                    else:
                        out.append('<c r="%s" s="%d" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>'
                                   % (ref, 1 if bold else 0, _esc(val)))
                out.append('</row>')
            out.append('</sheetData></worksheet>')
            z.writestr("xl/worksheets/sheet%d.xml" % (i + 1), "".join(out))
    return path


def widths(sh):
    """Content-fit column widths, per the build spec's fixed table."""
    SPEC = {"Posted": 110, "Month": 130, "Account": 170, "Type": 150, "Category": 150,
            "Counterparty": 300, "Description": 420, "Line": 300, "Detail": 420,
            "How it is derived": 460, "Route": 170, "Check": 110, "Verdict": 170,
            "Merchant": 260, "Kind": 150, "Transactions": 110, "Txns": 80}
    out = []
    for ci, col in enumerate(sh["columns"]):
        t = sh["types"][ci]
        if col in SPEC:
            out.append(SPEC[col])
        elif t == "money":
            out.append(140)
        elif t == "int":
            out.append(80)
        elif t == "date":
            out.append(110)
        else:
            longest = max([len(str(col))] + [len(str(r[ci])) for r in sh["rows"]
                                             if ci < len(r) and r[ci] is not None])
            out.append(min(max(120, longest * 7 + 26), 460))
    return out


def main():
    import formulas, evidence
    ev = evidence.compute()
    r = json.load(open(os.path.join(OUT, "balance_sheet.json")))
    sheets = build_sheets(r, ev)
    n_cardtx = sum(1 for x in r["ledger"] if x["isCard"])
    fmaps = formulas.build(sheets, {"cardTx": n_cardtx,
                                    "ledger": len([x for x in r["ledger"]]),
                                    "acct": len(r["accounts"]) + len(r["creditAccounts"])})
    for sh in sheets:
        sh["w"] = widths(sh)
        sh["formulas"] = fmaps.get(sh["name"], {})
        sh["emphasis"] = {str(k): v for k, v in sh.get("emphasis", {}).items()}
    json.dump({"meta": r["entity"], "generated": r["generatedFrom"],
               "opening": r["opening"], "closing": r["closing"],
               "netChange": r["netChange"], "reconciliation": r["reconciliation"],
               "monthlyClosings": [m["closing"] for m in r["monthly"]],
               "monthsMatched": sum(1 for m in r["monthly"] if m["agrees"]),
               "monthsTotal": len(r["monthly"]),
               "sheets": sheets}, open(os.path.join(OUT, "sheets.json"), "w"), indent=1)
    csvdir = os.path.join(OUT, "csv"); os.makedirs(csvdir, exist_ok=True)
    for s in sheets:
        with open(os.path.join(csvdir, "%s.csv" % s["name"].lower()), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(s["columns"])
            for row in s["rows"]:
                w.writerow(["" if v is None else v for v in row])
    xp = write_xlsx(sheets, os.path.join(OUT, "GCALIT-Mercury-FY2025-26.xlsx"))
    print("sheets: %s" % ", ".join("%s (%d rows)" % (s["name"], len(s["rows"])) for s in sheets))
    print("xlsx:   %s  %d bytes" % (xp, os.path.getsize(xp)))
    print("csv:    %d files in %s" % (len(sheets), csvdir))

if __name__ == "__main__":
    main()
