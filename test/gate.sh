#!/usr/bin/env bash
# Full build gate. Rebuilds from raw/ and refuses to pass if the published copy in
# docs/ differs from the verified build in out/ — the "shipped a stale file" failure.
set -u
cd "$(dirname "$0")/.."
fail=0
step(){ printf '%-46s' "$1"; }
ok(){ echo "PASS"; }
bad(){ echo "FAIL  $1"; fail=1; }

step "rebuild engine";      python3 scripts/monthly.py >/dev/null 2>&1 && ok || bad "monthly.py"
step "rebuild workbook";    python3 scripts/sheets.py  >/dev/null 2>&1 && ok || bad "sheets.py"
step "rebuild page";        python3 scripts/generate.py>/dev/null 2>&1 && ok || bad "generate.py"
cp out/GCALIT-Mercury-FY2025-26.xlsx docs/ 2>/dev/null
rm -rf docs/csv && cp -r out/csv docs/csv

step "xlsx formulas recalculate"
python3 test/test_formulas.py >/dev/null 2>&1 && ok || bad "test_formulas.py"

step "xlsx opens in an independent parser"
python3 - <<'PY' >/dev/null 2>&1 && ok || bad "openpyxl round-trip"
import openpyxl, json, sys
wb=openpyxl.load_workbook("out/GCALIT-Mercury-FY2025-26.xlsx", data_only=False)
src=json.load(open("out/sheets.json"))
for s in src["sheets"]:
    ws=wb[s["name"]]
    assert ws.max_row == 1+len(s["rows"]), s["name"]
PY

step "docs/ identical to verified out/"
for f in GCALIT-Mercury-FY2025-26.xlsx csv/summary.csv csv/monthly.csv csv/ledger.csv \
         csv/cards.csv csv/reconciliation.csv csv/accounts.csv; do
  [ "$(md5sum "out/$f"|cut -d' ' -f1)" = "$(md5sum "docs/$f"|cut -d' ' -f1)" ] || { bad "stale $f"; break; }
done
[ $fail -eq 0 ] && ok

step "page data identical to workbook"
python3 - <<'PY' >/dev/null 2>&1 && ok || bad "embedded payload drift"
import json,re
d=json.loads(re.search(r'^const D = (\{.*\});$', open("docs/index.html").read(), re.M).group(1))
assert d["sheets"] == json.load(open("out/sheets.json"))["sheets"]
PY

step "Summary and Monthly agree on money out"
python3 - <<'PY' >/dev/null 2>&1 && ok || bad "the two tabs disagree"
import json
sh={s["name"]:s for s in json.load(open("out/sheets.json"))["sheets"]}
a=[r for r in sh["Summary"]["rows"] if r[0]=="TOTAL MONEY OUT"][0][3]
m=sh["Monthly"]; ci=m["columns"].index("Total money out")
b=[r for r in m["rows"] if r[0]=="FULL YEAR"][0][ci]
assert abs(a-b)<0.005, (a,b)
PY

step "balance identity holds"
python3 - <<'PY' >/dev/null 2>&1 && ok || bad "opening + net != closing"
import json
d=json.load(open("out/sheets.json"))
assert abs(d["opening"]+d["netChange"]-d["closing"])<0.005
PY

step "no secret in the tree"
python3 - <<'PY' >/dev/null 2>&1 && ok || bad "SECRET PRESENT"
import json,subprocess,sys
tok=json.load(open("/root/.config/mercury/token.json"))["token"]
raw=json.load(open("raw/accounts.json"))
needles=[tok, tok.split("mercury_production_")[1]] + \
        [a["accountNumber"] for a in raw] + [raw[0]["routingNumber"]]
files=subprocess.run(["git","ls-files"],capture_output=True,text=True).stdout.split()
blob="".join(open(f,errors="replace").read() for f in files if f)
assert "GCALIT" in blob                       # positive control
assert not any(n in blob for n in needles)
PY

echo
[ $fail -eq 0 ] && echo "GATE: PASS" || echo "GATE: FAIL"
exit $fail
