"""Locked inventory 2021-2025 (variant D: delivered kg, soil-map OR farmer-reported organic soil), dev score,
A2 submission, line-level FLAG split, corrections log, and the pools the pathway and MACC read.
Run: python stages/b_pathways/s10_inventory.py"""
from ccn_paths import PACKAGE, stage_dir
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import json
import numpy as np, pandas as pd
HERE = stage_dir("b_pathways")
import lib_clean as L
from ccn_tools import reference_calculator as RC, score as SC, factors as F
pd.set_option("display.width", 200, "display.max_columns", 30, "display.max_rows", 200)
pd.set_option("future.no_silent_downcasting", True)
OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)

raw, T = L.load_clean()
erp = T["purchases"]
PARTS = L.FLAG_PARTS + L.NONFLAG_PARTS


def farm_lines():
    s = L.clean_survey(raw)
    c = L.components(s)
    s = pd.concat([s, c], axis=1)
    s["low_c"] = s.fertiliser_product.fillna("").str.contains("low-carbon")
    os_ = L.organic_share(raw).rename(columns={"area_ha": "decl_ha"})
    d = erp[erp.material_id.isin(L.CROP_MAT)].copy()
    d["crop"] = d.material_id.map(L.CROP_MAT)
    d = d.groupby(["supplier_id", "crop", "year"]).qty_kg.sum().reset_index().rename(columns={"supplier_id": "farm_id"})
    b = d.merge(os_, on=["farm_id", "crop", "year"], how="left")
    keep = ["farm_id", "crop", "year", "yield_t_ha", "soil_type_reported", "n_mineral_kg_ha", "low_c"] + PARTS
    b = b.merge(s[keep], on=["farm_id", "crop", "year"], how="left")
    b["surveyed"] = b.yield_t_ha.notna()
    ky = pd.Series(list(zip(b.crop, b.year)))
    for col in PARTS + ["n_mineral_kg_ha"]:
        b[col] = b[col].fillna(ky.map(s.groupby(["crop", "year"])[col].mean()))
    b["yield_t_ha"] = b.yield_t_ha.fillna(ky.map(s.groupby(["crop", "year"]).yield_t_ha.median()))
    b["low_c"] = b.low_c.fillna(False).astype(bool)
    b["ha"] = b.qty_kg / (b.yield_t_ha * 1000)
    b["share_map"] = (b.org_ha / b.decl_ha).fillna(0)
    b["share"] = np.maximum(b.share_map, b.soil_type_reported.fillna("").str.startswith("Organic").astype(float))
    b["org_ha_del"] = b.ha * b.share
    b["t_org"] = b.org_ha_del * L.ORG_KG_HA / 1000
    for col in PARTS:
        b["t_" + col] = b.ha * b[col] / 1000
    b["t_flag"] = b.t_org + b[["t_" + c for c in L.FLAG_PARTS]].sum(axis=1)
    b["t_nonflag"] = b[["t_" + c for c in L.NONFLAG_PARTS]].sum(axis=1)
    b["tco2e"] = b.t_flag + b.t_nonflag
    b["region"] = "FI_SW"
    return b


fl = farm_lines()
T["farm_footprints"] = fl[["farm_id", "crop", "year", "region", "tco2e"]]

# ---- dev score
res = {}
for y in (2023, 2024):
    key = pd.read_csv(L.DATA / "tasks" / "dev" / f"A2_dev_inventory_{y}.csv")
    inv = RC.compute_inventory(T, y)
    r = SC.score_a2(RC.summarise(inv), key)
    res[y] = dict(score=r["score"], detail={k: v["error_pct"] for k, v in r["detail"].items()})
    # dev-implied error of the farm line: everything else in cat 1 is near-exact
    ours = inv[inv.category.isin(["cat01_purchased_goods", "cat01_purchased_services"])].tco2e.sum()
    tr = key.set_index("category").tco2e["cat01_purchased_goods_services"]
    farm = fl[fl.year == y].tco2e.sum()
    res[y]["farm_t_ours"] = round(float(farm), 1)
    res[y]["farm_t_dev_implied"] = round(float(farm - (ours - tr)), 1)
    res[y]["farm_err_pct"] = round(float((ours - tr) / (farm - (ours - tr)) * 100), 2)
    print(y, "A2 dev score", r["score"], "| farm ours", round(farm), "dev-implied", res[y]["farm_t_dev_implied"], "err%", res[y]["farm_err_pct"])

# ---- line-level FLAG split
lib = T["ef_library"].set_index("ef_id")
mm = T["materials"].set_index("material_id")
frames = []
for y in range(2021, 2026):
    inv = RC.compute_inventory(T, y)
    inv["flag_t"] = 0.0
    inv["material_id"] = None
    g = inv.category == "cat01_purchased_goods"
    for i, r in inv[g].iterrows():
        li = r.line_item
        if li.startswith("contract_farming"):
            crop = li.split(":")[2]
            q = fl[(fl.year == y) & (fl.crop == crop)]
            inv.at[i, "flag_t"] = q.t_flag.sum()
            inv.at[i, "material_id"] = {v: k for k, v in L.CROP_MAT.items()}[crop]
        else:
            mat = li.split(":")[0]
            inv.at[i, "material_id"] = mat
            inv.at[i, "flag_t"] = r.tco2e * lib.flag_share[mm.default_ef_id[mat]]
    frames.append(inv)
    print(y, "biogenic memo", round(inv.attrs["biogenic_co2_t"], 1))
lines = pd.concat(frames, ignore_index=True)
lines.to_csv(OUT / "inventory_lines_2021_2025.csv", index=False)

summ = {}
for y in range(2021, 2026):
    q = lines[lines.year == y]
    s3 = q[q.scope == "scope3"]
    summ[y] = dict(s1=q[q.scope == "scope1"].tco2e.sum(), s2m=q[q.scope == "scope2_market"].tco2e.sum(), s2l=q[q.scope == "scope2_location"].tco2e.sum(),
                   s3=s3.tco2e.sum(), flag=s3.flag_t.sum(), s3_nonflag=s3.tco2e.sum() - s3.flag_t.sum(),
                   cat1=s3[s3.category.str.startswith("cat01")].tco2e.sum())
S = pd.DataFrame(summ).T.round(1)
S["flag_share_of_s3"] = (S.flag / S.s3).round(4)
print(S.to_string())
print(lines[(lines.year == 2025)].groupby(["scope", "category"]).tco2e.sum().round(1).to_string())

# ---- 2025 submission in the A2 template format
inv25 = RC.compute_inventory(T, 2025)
s25 = RC.summarise(inv25).drop_duplicates("category").set_index("category").tco2e   # the two purchased_electricity rows are overwritten below
tmpl = pd.read_csv(L.DATA / "tasks" / "templates" / "A2_inventory_2025_submission.csv")
notes = {"cat01_purchased_goods_services": "cleaned ERP; valid PCFs else library; farm footprints with soil-map organic soils", "cat02_capital_goods": "capex project register",
         "scope2_market_total": "registry GoOs, own-vintage, capped at site consumption"}
assert set(tmpl.category) <= set(s25.index) | {"purchased_heat_steam"}
tmpl["tco2e"] = tmpl.category.map(s25).round(2)
tmpl.loc[(tmpl.scope == "scope2_location") & (tmpl.category == "purchased_electricity"), "tco2e"] = round(inv25[(inv25.scope == "scope2_location")].tco2e.sum(), 2)
tmpl.loc[(tmpl.scope == "scope2_market") & (tmpl.category == "purchased_electricity"), "tco2e"] = round(inv25[(inv25.scope == "scope2_market")].tco2e.sum(), 2)
tmpl["method_note"] = tmpl.category.map(notes).fillna("cleaned raw feeds; see corrections_log.csv")
tmpl.to_csv(OUT / "A2_inventory_2025_submission.csv", index=False)
print(tmpl[["category", "tco2e"]].to_string())

pd.DataFrame(L.LOG).drop_duplicates().to_csv(OUT / "corrections_log.csv", index=False)
print("corrections logged", len(pd.DataFrame(L.LOG).drop_duplicates()))
print(pd.DataFrame(L.LOG).drop_duplicates().query("year==2025").groupby(["table", "rule", "reason"]).size().to_string())

# ---- comparator: current calculator (mineral soil assumed) on the same delivered kg
cc = pd.read_csv(L.DATA / "data" / "03_farming" / "current_calculator_footprints.csv")
x = fl.merge(cc[["farm_id", "crop", "year", "carbon_footprint_kgco2e_per_kg"]], on=["farm_id", "crop", "year"], how="left")
ky = pd.Series(list(zip(x.crop, x.year)))
x["cf"] = x.carbon_footprint_kgco2e_per_kg.fillna(ky.map(cc.groupby(["crop", "year"]).carbon_footprint_kgco2e_per_kg.median()))
x["t_cur"] = x.qty_kg * x.cf / 1000
comp = x.groupby("year").agg(current_calc_t=("t_cur", "sum"), ours_t=("tco2e", "sum"), org_t=("t_org", "sum"), org_ha=("org_ha_del", "sum"), ha=("ha", "sum"), flag_t=("t_flag", "sum"))
comp["org_share_ha"] = comp.org_ha / comp.ha
comp["org_share_t"] = comp.org_t / comp.ours_t
print(comp.round(3).to_string())

# ---- pools for the pathway and MACC
y = 2025
q = fl[fl.year == y]
print(q.groupby("crop")[["qty_kg", "ha", "org_ha_del", "tco2e", "t_flag", "t_org", "t_fert_n", "t_n2o_dir", "t_n2o_ind", "t_diesel"]].sum().round(0).to_string())
lc = q.assign(nkg=q.n_mineral_kg_ha * q.ha)
pools = dict(
    farm_t=float(q.tco2e.sum()), farm_flag_t=float(q.t_flag.sum()), farm_org_t=float(q.t_org.sum()), farm_org_ha=float(q.org_ha_del.sum()), farm_ha=float(q.ha.sum()),
    farm_fert_n_t=float(q.t_fert_n.sum()), farm_n2o_mineral_t=float(q.t_n2o_dir.sum() + q.t_n2o_ind.sum()),
    n_kg_total=float(lc.nkg.sum()), n_kg_lowc=float(lc[lc.low_c].nkg.sum()), n_kg_conventional=float(lc[~lc.low_c].nkg.sum()),
    org_kg_ha=float(L.ORG_KG_HA))
json.dump(dict(dev=res, pools=pools, summary={int(k): v for k, v in S.T.to_dict().items()}), open(OUT / "inventory_summary.json", "w"), indent=1, default=float)
fl.to_csv(OUT / "farm_lines.csv", index=False)
print(json.dumps(pools, indent=0))
