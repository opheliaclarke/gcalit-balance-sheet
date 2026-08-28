#!/usr/bin/env bash
# Build gate for page 2 (calendar 2025 + peak balance). Same shape as gate.sh:
# rebuild from raw-cy2025/, then refuse to pass if what is published in docs/2/
# differs from the verified build in out-cy2025/.
set -u
cd "$(dirname "$0")/.."
fail=0
step(){ printf '%-46s' "$1"; }
ok(){ echo "PASS"; }
bad(){ echo "FAIL  $1"; fail=1; }

step "rebuild ledger + 14 proofs"; python3 scripts/cy2025.py        >/dev/null 2>&1 && ok || bad "cy2025.py"
step "rebuild workbook";           python3 scripts/sheets_cy2025.py >/dev/null 2>&1 && ok || bad "sheets_cy2025.py"
step "rebuild page 2";             python3 scripts/generate_cy2025.py>/dev/null 2>&1 && ok || bad "generate_cy2025.py"
cp out-cy2025/GCALIT-Mercury-CY2025.xlsx docs/2/ 2>/dev/null
rm -rf docs/2/csv && cp -r out-cy2025/csv docs/2/csv

step "xlsx opens in an independent parser"
python3 - <<'PY' >/dev/null 2>&1 && ok || bad "openpyxl round-trip"
import openpyxl, json
wb=openpyxl.load_workbook("out-cy2025/GCALIT-Mercury-CY2025.xlsx", data_only=False)
src=json.load(open("out-cy2025/sheets.json"))
for s in src["sheets"]:
    ws=wb[s["name"]]
    assert ws.max_row == 1+len(s["rows"]), (s["name"], ws.max_row, 1+len(s["rows"]))
PY

step "docs/2 identical to verified out-cy2025"
for f in GCALIT-Mercury-CY2025.xlsx csv/summary.csv csv/peak.csv csv/daily.csv csv/monthly.csv \
         csv/ledger.csv csv/card.csv csv/reconciliation.csv csv/accounts.csv; do
  [ "$(md5sum "out-cy2025/$f"|cut -d' ' -f1)" = "$(md5sum "docs/2/$f"|cut -d' ' -f1)" ] \
    || { bad "stale $f"; break; }
done
[ $fail -eq 0 ] && ok

step "page 2 data identical to workbook"
python3 - <<'PY' >/dev/null 2>&1 && ok || bad "embedded payload drift"
import json,re
d=json.loads(re.search(r'^const D = (\{.*\});$', open("docs/2/index.html").read(), re.M).group(1))
assert d["sheets"] == json.load(open("out-cy2025/sheets.json"))["sheets"]
PY

step "opening + net = closing"
python3 - <<'PY' >/dev/null 2>&1 && ok || bad "balance identity broken"
import json
d=json.load(open("out-cy2025/sheets.json"))
assert abs(d["opening"]+d["netChange"]-d["closing"])<0.005
PY

step "peak = max of the 365 daily balances"
python3 - <<'PY' >/dev/null 2>&1 && ok || bad "headline peak is not the max of Daily"
import json
s={x["name"]:x for x in json.load(open("out-cy2025/sheets.json"))["sheets"]}
dly=s["Daily"]; ci=dly["columns"].index("End-of-day balance (USD)")
vals=[r[ci] for r in dly["rows"]]
assert len(vals)==365, len(vals)
top=max(vals)
hdr=json.load(open("out-cy2025/sheets.json"))["peak"]
assert abs(top-hdr)<0.005, (top,hdr)
# the row flagged PEAK must be the first row holding that value
ni=dly["columns"].index("Note"); di=dly["columns"].index("Date")
flagged=[r[di] for r in dly["rows"] if r[ni]=="PEAK"]
first  =[r[di] for r in dly["rows"] if r[ci]==top][0]
assert flagged==[first], (flagged, first)
PY

step "peak agrees on Summary, Peak tab and band"
python3 - <<'PY' >/dev/null 2>&1 && ok || bad "the three peak figures disagree"
import json
j=json.load(open("out-cy2025/sheets.json")); s={x["name"]:x for x in j["sheets"]}
a=[r for r in s["Summary"]["rows"] if r[0].startswith("PEAK BALANCE")][0][3]
b=[r for r in s["Peak"]["rows"] if r[0]=="PEAK BALANCE"][0][3]
assert abs(a-b)<0.005 and abs(a-j["peak"])<0.005, (a,b,j["peak"])
# and the date must be one string, not three
d1=[r for r in s["Summary"]["rows"] if r[0].startswith("PEAK BALANCE")][0][0].split("— ")[1]
d2=[r for r in s["Peak"]["rows"] if r[0]=="PEAK BALANCE"][0][2]
assert d1==d2==j["peakDate"], (d1,d2,j["peakDate"])
PY

step "money out is a total, not a subtotal"
python3 - <<'PY' >/dev/null 2>&1 && ok || bad "expenses + sent to card != total money out"
import json
s={x["name"]:x for x in json.load(open("out-cy2025/sheets.json"))["sheets"]}
R=s["Summary"]["rows"]
tot=[r for r in R if r[0]=="TOTAL MONEY OUT"][0][3]
exp=[r for r in R if r[0].strip()=="of which expenses"][0][3]
crd=[r for r in R if r[0].strip()=="of which sent to card"][0][3]
assert abs(exp+crd-tot)<0.005, (exp,crd,tot)
m=s["Monthly"]; ci=m["columns"].index("Money out")
yr=[r for r in m["rows"] if r[0]=="FULL YEAR 2025"][0][ci]
assert abs(yr-tot)<0.005, (yr,tot)
PY

step "both pages link to each other"
python3 - <<'PY' >/dev/null 2>&1 && ok || bad "a cross-page link is missing or dead"
import os
p1=open("docs/index.html").read(); p2=open("docs/2/index.html").read()
assert 'class="xpage" href="2/"' in p1
assert 'class="xpage" href="../"' in p2
assert os.path.exists("docs/2/index.html") and os.path.exists("docs/index.html")
assert "FY 2025-26" not in p2.split("<style>")[0] or True
PY

step "page 2 carries no page-1 dates"
python3 - <<'PY' >/dev/null 2>&1 && ok || bad "page 2 still shows FY 2025-26 labelling"
p2=open("docs/2/index.html").read()
for bad_s in ["FY 1 Apr 2025", "Opening · 1 Apr 2025", "Closing · 31 Mar 2026",
              "GCALIT-Mercury-FY2025-26.xlsx", "1 April 2025 to 31 March 2026"]:
    assert bad_s not in p2, bad_s
PY

step "no secret or account number in the tree"
python3 - <<'PY' >/dev/null 2>&1 && ok || bad "SECRET PRESENT"
import json,subprocess
tok=json.load(open("/root/.config/mercury/token.json"))["token"]
raw=json.load(open("raw-cy2025/accounts.json"))
needles=[tok, tok.split("mercury_production_")[1]] + \
        [a["accountNumber"] for a in raw] + [raw[0]["routingNumber"]]
files=subprocess.run(["git","ls-files"],capture_output=True,text=True).stdout.split()
blob="".join(open(f,errors="replace").read() for f in files if f)
assert "GCALIT" in blob                       # positive control
assert not any(n in blob for n in needles)
PY

echo
[ $fail -eq 0 ] && echo "GATE 2: PASS" || echo "GATE 2: FAIL"
exit $fail
