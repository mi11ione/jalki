"""Independent verification of the audit trail. Reads the written files and the raw feeds, and runs the organisers' own
pandas reference_calculator and scorer (never used by a2-inv, which assumed pandas was absent). Exits non-zero on any
failure. Prints a sha of all outputs so two runs can be compared. Synthetic pack."""
from ccn_paths import PACKAGE, stage_dir
import csv, hashlib, json, sys
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
HERE = stage_dir("a2_inventory")
import pandas as pd
import lib, final_pipeline as P
from ccn_tools import reference_calculator as RC, score as SC

AUD = Path(__import__("os").environ.get("AUDIT_DIR", HERE / "audit"))   # s13_mutate.py points this at a corrupted copy
ROOT = lib.ROOT
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail != "" else ""))
    if not ok:
        fails.append(name)


def rd(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


E, L, C, FA, I = (rd(AUD / f"{n}.csv") for n in ("edges", "lines", "corrections", "factors", "issues"))
SUB = rd(HERE / "A2_inventory_2025_submission.csv")
man = json.loads((AUD / "manifest.json").read_text())

# 1 edge arithmetic and factor join
fv = {f["factor_id"]: float(f["value"]) for f in FA}
bad = worst = 0
for e in E:
    t = float(e["tco2e"])
    if e["role"] in ("driver", "evidence", "dropped"):
        bad += t != 0          # these roles must carry exactly 0 t
        continue
    val = float(e["clean_value"]) if e["clean_value"] not in ("", None) else 0.0
    f = fv[e["factor_id"]]
    d = abs(val * f * float(e["multiplier"]) - t)
    worst = max(worst, d)
    bad += d > 1e-6
check("every edge: tonnes = clean value x factor x multiplier, factor in factors.csv", bad == 0, f"{len(E)} edges, worst {worst:.1e}")

# 2 sums up the chain
by = defaultdict(float)
for e in E:
    by[e["line_id"]] += float(e["tco2e"])
d = max(abs(by[l["line_id"]] - float(l["tco2e"])) for l in L)
check("edges sum to every line", d < 1e-6, f"{len(L)} lines, worst {d:.1e}")
cat = defaultdict(float)
sc = defaultdict(float)
for l in L:
    cat[(l["scope"], l["submission_category"])] += float(l["tco2e"])
    sc[l["scope"]] += float(l["tco2e"])
bad = []
for r in SUB:
    if r["scope"] == "total":
        v = sc[r["category"].replace("_total", "")]
    else:
        v = cat[(r["scope"], r["category"])]
    if abs(v - float(r["tco2e"])) > 0.0051:
        bad.append((r["category"], v, r["tco2e"]))
check("lines sum to every submission row, totals included", not bad, bad)

# 3 organisers' pandas calculator on the same clean tables
raw, c, log, rows1, truth, ks = P.prepare()
k = ks["pooled"]
T = P.canonical(c, k)
Tp = {n: pd.DataFrame(v) for n, v in T.items()}
off = RC.compute_inventory(Tp, 2025)
offd = {f"{r.scope}|{r.category}|{r.line_item}": r.tco2e for r in off.itertuples()}
ours = {l["line_id"]: float(l["tco2e"]) for l in L if l["scope"] != "memo"}
d = max(abs(offd[x] - ours.get(x, 0.0)) for x in offd)
check("organisers' reference_calculator agrees on every 2025 line", set(offd) == set(ours) and d < 1e-6, f"{len(offd)} lines, worst {d:.1e}")
for y, name in ((2024, "fit_2023"), (2023, "fit_2024")):
    Ty = {n: pd.DataFrame(v) for n, v in P.canonical(c, ks[name]).items()}
    s = RC.summarise(RC.compute_inventory(Ty, y))
    res = SC.score_a2(s, pd.read_csv(ROOT / "tasks" / "dev" / f"A2_dev_inventory_{y}.csv"))
    print(f"     organisers' scorer, held-out {y}: {res['score']}")
    hd = json.loads((HERE / "heldout.json").read_text())
    check(f"organisers' scorer matches the port on {y}", abs(res["score"] - hd["folds"][str(y)]["score"]) < 0.011, res["score"])

# 4 click-to-source: every edge row resolves to its raw record and raw value
cache = {}


def src(f):
    if f not in cache:
        with open(ROOT / f, newline="", encoding="utf-8") as h:
            cache[f] = list(csv.DictReader(h))
    return cache[f]


IDS = {"erp_purchase": lambda r: f"erp:{r['doc_no']}:{r['line_no']}", "energy_meter": lambda r: f"energy:{r['site_id']}:{int(r['year'])}-{int(r['month']):02d}:{r['carrier']}",
       "fuel_deliveries": lambda r: f"fuel:{r['delivery_id']}", "fuel_stock": lambda r: f"fuelstock:{r['site_id']}:{r['carrier']}:{r['year']}", "refrigerant": lambda r: f"refrigerant:{r['event_id']}",
       "waste_transfer": lambda r: f"waste:{r['transfer_note']}", "wastewater": lambda r: f"wastewater:{r['site_id']}:{r['year']}", "travel": lambda r: f"travel:{r['booking_id']}",
       "commuting": lambda r: f"commute:{r['response_id']}", "headcount": lambda r: f"headcount:{r['site_id']}:{r['year']}", "shipments": lambda r: f"ship:{r['shipment_id']}",
       "frozen_warehousing": lambda r: f"warehouse:{r['year']}", "sales_volumes": lambda r: f"sales:{r['year']}-{int(r['month']):02d}:{r['product_group']}:{r['site_id']}:{r['market']}",
       "farm_survey": lambda r: f"farm_survey:{r['survey_id']}", "parcels": lambda r: f"parcel:{r['parcel_id']}", "goo_registry": lambda r: f"gooreg:{r['cancellation_id']}", "goo_cancellations": lambda r: f"goo:{r['site_id']}:{r['year']}"}
miss = wrong = val_bad = none_row = 0
badv = []
for e in E:
    if not e["source_row"]:
        none_row += 1
        continue
    rows = src(e["source_file"])
    r = rows[int(e["source_row"]) - 2]
    fn = next(v for kk, v in IDS.items() if kk in e["source_file"])
    if fn(r) != e["record_key"]:
        wrong += 1
        continue
    rv = e["raw_value"]
    if rv in ("", None):
        continue
    try:
        x = float(rv)
    except ValueError:
        if rv not in r.values():
            val_bad += 1
        continue
    if not any(v not in ("", None) and v.replace(".", "", 1).replace("-", "", 1).isdigit() and abs(float(v) - x) < 1e-6 for v in r.values()):
        val_bad += 1
        badv.append((e["record_key"], rv))
check("every source_row resolves to the named record", wrong == 0, f"{len(E)-none_row} resolved, {none_row} without a raw row")
check("every raw_value equals the value in the source file", val_bad == 0, badv[:3])
blank = [e for e in E if not e["source_row"]]
kinds = defaultdict(int)
for e in blank:
    kinds[(e["record_key"].split(":")[0], e["role"], bool(e["correction_ids"]))] += 1
print("     edges without a raw row:", dict(kinds))
check("every edge without a raw row is a logged imputation or a PCF file", all(e["correction_ids"] for e in blank), len(blank))

# 5 corrections and issues close both ways
ek = {e["record_key"] for e in E}
ec = set()
for e in E:
    ec |= set(e["correction_ids"].split(";")) - {""}
no_line = [x for x in C if x["id"] not in ec]
tab = defaultdict(int)
for x in no_line:
    tab[x["rule"]] += 1
print("     corrections not attached to an edge:", dict(tab))
check("only coordinate and draft-report corrections sit off the inventory", set(tab) <= {"R-FARM-COORD", "R-REPORT"} , dict(tab))
check("every correction is pending expert approval", all(x["approval"] == "pending_expert_approval" for x in C), len(C))
ik = {i["record_key"] for i in I}
ck = {x["record_key"] for x in C}
check("every issue has a correction and every correction an issue", ik == ck, f"{len(ik)} issues, {len(ck)} corrected keys")
sub_rows = rd(HERE / "A1_issues_submission.csv")
check("issue list keeps the template columns", list(sub_rows[0].keys()) == ["table", "record_key", "issue_type", "confidence", "explanation"], len(sub_rows))

# 6 source files unchanged, against the organisers' manifest
mf = {f["path"]: f["sha256"] for f in json.loads((ROOT / "MANIFEST.json").read_text())["files"]}
check("every input hash matches the organisers' manifest", all(mf.get(p) == h for p, h in man["inputs"].items()), len(man["inputs"]))
h = hashlib.sha256()
for p in sorted(AUD.glob("*.csv")) + [HERE / "A2_inventory_2025_submission.csv", HERE / "A1_issues_submission.csv"]:
    h.update(p.read_bytes())
print("outputs sha256", h.hexdigest())
print("ALL AUDIT CHECKS PASS" if not fails else f"AUDIT CHECKS FAILED: {fails}")
sys.exit(1 if fails else 0)
