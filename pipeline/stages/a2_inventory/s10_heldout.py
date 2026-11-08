"""Held-out score of the merged pipeline, and the same fold for a2-inv and a2-inv-b. Fold rule: k is fitted on one dev
year and scored on the other. Also: PCF either-path sizes for 2025 and the 2025 score scenarios (exhaustive grid of named
cases; no sampling). Writes heldout.json. Synthetic pack; scores are on the public dev truths."""
from ccn_paths import PACKAGE, stage_dir
import json, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = stage_dir("a2_inventory")
import lib, final_pipeline as P

raw, c, log, rows1, truth, ks = P.prepare()
print("implied farm truth", {y: round(v, 2) for y, v in truth.items()})
print("k", {a: round(b, 4) for a, b in ks.items()})
res = {"k": ks, "folds": {}}
for ty, name in ((2024, "fit_2023"), (2023, "fit_2024")):
    T, rows, bio, summ = P.year_result(c, ks[name], ty)
    s, d = lib.score_a2(summ, lib.dev_key(ty))
    farm_t = P.farm_total(rows1, ty, ks[name])
    print(f"\nHELD-OUT {ty} (k {ks[name]:.4f} from the other year): score {s}, farm err {farm_t-truth[ty]:+.1f} t")
    for kk, v in d.items():
        print(f"   {kk:34s} err {v[0]:6.2f}% credit {v[1]:.3f}")
    res["folds"][str(ty)] = dict(score=s, k=ks[name], farm_err_t=farm_t - truth[ty], lines={kk: dict(err_pct=v[0], credit=v[1], ours=v[2], truth=v[3]) for kk, v in d.items()})
for ty in (2023, 2024):
    T, rows, bio, summ = P.year_result(c, ks["pooled"], ty)
    s, d = lib.score_a2(summ, lib.dev_key(ty))
    print(f"IN-SAMPLE {ty} pooled k: score {s}, cat01 err {d['cat01_purchased_goods_services'][0]}%")
    res["folds"][str(ty)]["in_sample_score"] = s

# 2025 point and PCF paths
k = ks["pooled"]
T, rows, bio, summ = P.year_result(c, k, 2025)
S = {r["category"]: r["tco2e"] for r in summ}
kg = {}
for p in T["purchases"]:
    if p["year"] == 2025:
        kg[(p["supplier_id"], p["material_id"])] = kg.get((p["supplier_id"], p["material_id"]), 0.0) + p["qty_kg"]
EF = {e["ef_id"]: e["kgco2e_per_unit"] for e in raw["ef_library"]}
mm = {m["material_id"]: m for m in raw["materials"]}
unit = stale = 0.0
per = []
for p in raw["pcfs"]:
    if p["year"] != 2025:
        continue
    d = EF[mm[p["material_id"]]["default_ef_id"]]
    q = kg.get((p["supplier_id"], p["material_id"]), 0.0)
    if p["value"] > 50 * d:
        x = (p["value"] / 1000 - d) * q / 1000
        unit += x
        per.append((f"pcf:{p['supplier_id']}:{p['material_id']}:2025", "unit", round(x, 1)))
    elif p["ref_start"][:4] != "2025":
        x = (p["value"] - d) * q / 1000
        stale += x
        per.append((f"pcf:{p['supplier_id']}:{p['material_id']}:2025", "stale", round(x, 1)))
print("\nPCF paths vs default factor, t:", per)
print(f"unit /1000 {unit:+.1f} t; stale kept {stale:+.1f} t; both {unit+stale:+.1f} t")
c1, s3 = S["cat01_purchased_goods_services"], S["scope3_total"]
worst = max(abs(res["folds"][y]["farm_err_t"]) for y in res["folds"])
print(f"2025 cat01 {c1:.2f}; farm {P.farm_total(rows1, 2025, k):.2f}; worst held-out farm error {worst:.1f} t")


def credit(e_t, base):
    return max(0.0, 1 - abs(e_t / base) / 0.05)


# Non-farm, non-PCF lines carry the mean held-out credit of the two folds, excluding S2 market 2024 (its head-office fill
# has no 2025 counterpart: no 2025 electricity month needs filling), which is taken as 1.0 on that reasoning.
base = {}
for kk, w in lib.A2_WEIGHTS.items():
    if kk in ("cat01_purchased_goods_services", "scope3_total"):
        continue
    v = [res["folds"][y]["lines"][kk]["credit"] for y in res["folds"]]
    base[kk] = 1.0 if kk == "scope2_market_total" else sum(v) / 2
fixed = sum(lib.A2_WEIGHTS[kk] * base[kk] for kk in base)
paths = {"PCF default (method text)": 0.0, "unit fixed /1000": unit, "stale kept": stale, "both repaired": unit + stale}
print("\n2025 score if the hidden truth took each path (rows) and our farm error were (columns)")
print(f"{'path':28s} {'farm 0':>8} {'farm +worst':>12} {'farm -worst':>12}")
scen = {}
for name, dpath in paths.items():
    r = []
    for fe in (0.0, worst, -worst):
        # our number minus truth: truth = ours + dpath - fe
        err = fe - dpath
        sc = 100 * (fixed + 0.20 * credit(err, c1 + dpath) + 0.20 * credit(err, s3 + dpath))
        r.append(round(sc, 2))
    scen[name] = r
    print(f"{name:28s} {r[0]:8.2f} {r[1]:12.2f} {r[2]:12.2f}")
res["pcf"] = dict(unit_t=unit, stale_t=stale, per=per)
res["score_2025_scenarios"] = scen
res["worst_farm_err_t"] = worst
res["fixed_credit_lines"] = base
(HERE / "heldout.json").write_text(json.dumps(res, indent=1, default=str))

# the earlier pipelines' own published dev scores, read from their results files
