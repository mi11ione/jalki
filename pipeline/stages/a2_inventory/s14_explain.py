"""Numbers behind the write-up: which earlier explanations hold, the fill rule test, the reported-organic test, a walked
click-to-source example and the top issues by tonnes. Writes explain.json. Synthetic pack."""
from ccn_paths import PACKAGE, stage_dir
import csv, json, sys, statistics
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
HERE = stage_dir("a2_inventory")
import lib, final_pipeline as P, farm

raw, c, log, rows1, truth, ks = P.prepare()
out = {}

# 2 mean v median fill, k refitted each way (the mean was tried first; test whether it earned its place)
chosen_fill = P.FARM_FILL
for fill in ("mean", "median"):
    P.FARM_FILL = fill
    r1 = P.farm_rows(c, 1.0)
    kk = {"2023": P.fit_k(r1, truth, [2023]), "2024": P.fit_k(r1, truth, [2024]), "pooled": P.fit_k(r1, truth, [2023, 2024])}
    e24 = P.farm_total(r1, 2024, kk["2023"]) - truth[2024]
    e23 = P.farm_total(r1, 2023, kk["2024"]) - truth[2023]
    f25 = P.farm_total(r1, 2025, kk["pooled"])
    print(f"fill {fill:6s}: k {kk['2023']:.4f}/{kk['2024']:.4f}/pooled {kk['pooled']:.4f}; held-out err 2024 {e24:+.1f}, 2023 {e23:+.1f}; 2025 farm {f25:.1f}")
    out[f"fill_{fill}"] = dict(k=kk, err_2024=e24, err_2023=e23, farm_2025=f25)
    for ty, name in ((2024, "2023"), (2023, "2024")):
        T_, rw, bio_, sm = P.year_result(c, kk[name], ty)
        print(f"   {fill} held-out {ty} score {lib.score_a2(sm, lib.dev_key(ty))[0]}")
        out[f"fill_{fill}"][f"score_{ty}"] = lib.score_a2(sm, lib.dev_key(ty))[0]
P.FARM_FILL = chosen_fill
rows1 = P.farm_rows(c, 1.0)

# 3 reported organic = 1? what is left for unlabelled, unreported rows under each assumption, against their map organic ha
labels = lib.read(lib.ROOT / "tasks" / "dev" / "A1_dev_issue_labels_2023_2024.csv")
share = {l["record_key"].split(":")[1]: float(l["true_value"].split()[-1]) for l in labels if l["issue_type"] == "soil_misreport"}
for y in (2023, 2024):
    rows = [r for r in rows1 if r["year"] == y]
    M = sum(r["mineral_kg_ha"] * r["area_ha"] for r in rows) / 1000
    O = (truth[y] - M) * 1000 / farm.ORG_ADD
    rep = [r for r in rows if r["reported_organic"]]
    lab = [r for r in rows if r["survey_id"] in share]
    lab_ha = sum(r["area_ha"] * share[r["survey_id"]] for r in lab)
    rest = [r for r in rows if not r["reported_organic"] and r["survey_id"] not in share]
    rest_map = sum(r["map_share"] * r["area_ha"] for r in rest)
    r1_ = (O - sum(r["area_ha"] for r in rep) - lab_ha) / rest_map
    r2_ = (O - sum(r["map_share"] * r["area_ha"] for r in rep) - lab_ha) / rest_map
    print(f"{y}: implied organic {O:.1f} ha; other rows hold {rest_map:.1f} map ha; ratio if reported=1 {r1_:.3f}; if reported=map share {r2_:.3f}")
    out[f"reported_test_{y}"] = dict(implied_ha=O, ratio_reported_1=r1_, ratio_reported_map=r2_)
k = ks["pooled"]
r25 = [r for r in rows1 if r["year"] == 2025]
rep = [r for r in r25 if r["reported_organic"]]
gap = sum(r["area_ha"] * (1 - r["map_share"]) for r in rep) * farm.ORG_ADD / 1000
oh = sum(r["area_ha"] if r["reported_organic"] else min(r["area_ha"], r["map_share"] * r["area_ha"] * k) for r in r25)
crop = sum(r["area_ha"] for r in r25)
org_t = oh * farm.ORG_ADD / 1000
print(f"2025: if the 4 reported rows were map share only: {-gap:+.1f} t. Organic {oh:.1f} ha of {crop:.1f} ha ({100*oh/crop:.2f} %), {org_t:.0f} t = {100*org_t/P.farm_total(rows1, 2025, k):.1f} % of the farm line")
out["org_2025"] = dict(ha=oh, crop_ha=crop, t=org_t, reported_at_map_t=-gap)

# 4 a walked example, straight from the written trail
def rd(n):
    with open(HERE / "audit" / n, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
E, C, I = rd("edges.csv"), {x["id"]: x for x in rd("corrections.csv")}, rd("issues.csv")
e = next(x for x in E if x["record_key"] == "erp:4500006858:10" and x["role"] == "activity")
print("\nwalked example:", {k_: e[k_] for k_ in ("edge_id", "line_id", "source_file", "source_row", "raw_value", "raw_unit", "clean_value", "factor_id", "factor_value", "tco2e", "tco2e_if_raw", "correction_ids")})
print("correction:", {k_: C[e["correction_ids"].split(";")[0]][k_] for k_ in ("id", "rule", "field", "old", "new", "reason", "evidence_level", "approval")})

# 5 what the corrections did, by rule, on headline scopes
top = sorted((i for i in I if i["tco2e_effect"]), key=lambda i: -abs(float(i["tco2e_effect"])))
print("\ntop issues by |effect| t:")
for i in top[:6]:
    print(" ", i["issue_id"], i["record_key"], i["issue_type"], i["tco2e_effect"])
tr = defaultdict(int)
for i in I:
    tr[i["treatment"].split(":")[0]] += 1
print("treatments", dict(tr))
print("validated types", sum(1 for i in I if i["validated_on_dev"] == "True"), "of", len(I))
est = [x for x in C.values() if x["evidence_level"] == "estimate"]
lvl = defaultdict(int)
for x in C.values():
    lvl[x["evidence_level"]] += 1
print("evidence levels", dict(lvl))
(HERE / "explain.json").write_text(json.dumps(out, indent=1))
