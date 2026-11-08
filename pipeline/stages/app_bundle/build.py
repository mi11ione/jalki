"""pj-data: the single data source every product build reads.  Run: python stages/app_bundle/build.py
Synthetic pack (Since AI 2026) only: no figure here is Apetit's real emissions.

Reads, never writes: stages/a2_inventory (pipeline modules, audit/, results.json, heldout.json, explain.json),
stages/b_pathways/outputs (lever catalogue, peat feasibility notes, old figures for the con2-a comparison),
stages/c3_euro_risk, stages/c2_climate_risk, stages/c1_yields, stages/d1_decide (forward views, copied as they stand), the package.
Writes: stages/app_bundle/bundle.json and stages/app_bundle/trail/.
Every inventory number is recomputed here on a-final's pipeline (k fitted once, as a-final does)."""
from ccn_paths import PACKAGE, stage_dir
import csv, json, hashlib, re, shutil, statistics, sys, time
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
T0 = time.time()
HERE = stage_dir("pipeline")
OUTROOT = HERE.parent
AF = stage_dir("a2_inventory")
BP = stage_dir("b_pathways") / "outputs"
TWIN = PACKAGE
sys.path.append(str(Path(__file__).resolve().parents[1] / "a2_inventory"))
import lib, farm, final_pipeline as P  # noqa: E402  (a-final modules, imported read-only)
from ccn_tools import factors as F  # noqa: E402
import numpy as np  # noqa: E402

SCRIPT = "python run_all.py --package <path>"
LEDGER = []


def num(key, value, unit, note=""):
    v = round(float(value), 4) if isinstance(value, (int, float, np.floating)) else value
    LEDGER.append(dict(key=key, value=v, unit=unit, script=SCRIPT, file="pipeline/bundle.json", note=note))
    return value


def rcsv(p, sep=","):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=sep))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ 0. input check (runs first, must pass)
man = json.loads((AF / "audit" / "manifest.json").read_text())
bad = [f for f, h in man["inputs"].items() if sha(TWIN / f) != h]
bad_out = [f for f, h in man["outputs"].items() if sha((AF / "audit" / f) if f != "A2_inventory_2025_submission.csv" else AF / f) != h]
assert not bad and not bad_out, ("a-final inputs or audit files changed since its manifest", bad, bad_out)
AFR = json.loads((AF / "results.json").read_text())
HD = json.loads((AF / "heldout.json").read_text())
print(f"[0] manifest: {len(man['inputs'])} twin inputs and {len(man['outputs'])} audit files match a-final's hashes; a-final facts check: {AFR['facts_check']}")

# ------------------------------------------------------------------ 1. a-final pipeline, 2023-2025
raw, c, log, rows1, truth, ks = P.prepare()
K = ks["pooled"]
assert abs(K - man["fitted_parameters"]["ORG_MAP_SCALE_K"]) < 1e-12
INV = {}
for y in (2023, 2024, 2025):
    T, rows, bio, summ = P.year_result(c, K, y)
    INV[y] = dict(T=T, rows=rows, bio=bio, summ={r["category"]: r["tco2e"] for r in summ}, summ_rows=summ)
S25 = INV[2025]["summ"]
for kk, v in AFR["inventory_2025"].items():
    if ":" not in kk:
        assert abs(S25[kk] - v) < 0.01, (kk, S25[kk], v)
EFROW = {e["ef_id"]: e for e in c["ef_library"]}
EF = {k: e["kgco2e_per_unit"] for k, e in EFROW.items()}
FS = {k: (e["flag_share"] or 0.0) for k, e in EFROW.items()}
MM = {m["material_id"]: m for m in c["materials"]}
SUP = {s["supplier_id"]: s for s in raw["suppliers"]}
print(f"[1] a-final rebuilt 2023-2025 in {time.time() - T0:.1f}s; k = {K:.4f}; 2025 matches a-final results.json")

# FLAG split (a-final has none): library flag_share on goods and services, farm FLAG parts on the farm line
E = F.FARM_EF
N2O = E["n2o_n_to_n2o"] * E["n2o_gwp"]


def z(v):
    return 0.0 if v is None else v


def parts_kg_ha(s, grid=0.03, diesel_ef=None):
    nmin, nman, yld = z(s.get("n_mineral_kg_ha")), z(s.get("n_manure_kg_ha")), s["yield_t_ha"]
    res = F.RESIDUE_N_PER_T[s["crop"]] * yld
    low = "low-carbon" in (s.get("fertiliser_product") or "")
    pk = z(s.get("p_kg_ha"))
    o = dict(fert_n=nmin * (E["fert_n_prod_lowcarbon"] if low else E["fert_n_prod"]),
             fert_pk=pk * E["fert_p_prod"] + pk * 2.2 * E["fert_k_prod"],
             n2o_dir=(nmin * E["ef1_synthetic"] + (nman + res) * E["ef1_organic"]) * N2O,
             n2o_ind=((nmin * E["frac_gasf"] + nman * E["frac_gasm"]) * E["ef4_n2o_n"] + (nmin + nman + res) * E["frac_leach"] * E["ef5_n2o_n"]) * N2O,
             diesel=z(s.get("diesel_l_ha")) * (diesel_ef if diesel_ef is not None else E["diesel_ttw"] + E["diesel_wtt"]),
             lime=z(s.get("lime_t_ha")) * E["lime"] * 1000, spray=z(s.get("sprays")) * E["spray_pass"])
    kwh = F.MGMT_NORMS[s["crop"]]["kwh_t"] * yld + (180.0 if lib.boolv(s.get("irrigated")) else 0.0)
    o["elec"] = kwh * grid
    return o


FLAGP = ("n2o_dir", "n2o_ind", "lime")
SV = {s["survey_id"]: s for s in farm.clean_survey(c, [])}
flag_frac_cy = defaultdict(list)
for s in SV.values():
    p = parts_kg_ha(s)
    tot = sum(p.values())
    if tot > 0:
        flag_frac_cy[(s["crop"], int(s["year"]))].append(sum(p[k] for k in FLAGP) / tot)
flag_frac_cy = {k: lib.median(v) for k, v in flag_frac_cy.items()}


def farm_rows_flag(frows):
    for r in frows:
        if r["survey_id"]:
            p = parts_kg_ha(SV[r["survey_id"]])
            ff = sum(p[k] for k in FLAGP) / sum(p.values())
        else:
            ff = flag_frac_cy[(r["crop"], r["year"])]
        r["t_org"] = farm.ORG_ADD * r["org_ha"] / 1000
        r["t_flag"] = ff * r["mineral_kg_ha"] * r["area_ha"] / 1000 + r["t_org"]
    return frows


def line_flag(r, frows):
    if r["category"] == "cat01_purchased_goods":
        if r["line_item"].startswith("contract_farming"):
            crop = r["line_item"].split(":")[2]
            return sum(f["t_flag"] for f in frows if f["crop"] == crop and f["year"] == r["year"])
        return r["tco2e"] * FS.get(MM[r["line_item"].split(":")[0]]["default_ef_id"], 0.0)
    if r["category"] == "cat01_purchased_services":
        return r["tco2e"] * FS.get(MM[r["line_item"]]["default_ef_id"], 0.0)
    return 0.0


for y, d in INV.items():
    fr = farm_rows_flag([f for f in d["T"]["farm_footprints"] if f["year"] == y])
    d["farm"] = fr
    for r in d["rows"]:
        r["flag_t"] = line_flag(r, fr)
    sc = defaultdict(float)
    for r in d["rows"]:
        sc[r["scope"]] += r["tco2e"]
    d["S1"], d["S2M"], d["S2L"], d["S3"] = sc["scope1"], sc["scope2_market"], sc["scope2_location"], sc["scope3"]
    d["FLAG"] = sum(r["flag_t"] for r in d["rows"] if r["scope"] == "scope3")
    d["TOT"] = d["S1"] + d["S2M"] + d["S3"]
D = INV[2025]
S1, S2M, S2L, S3, FLAG, TOT = D["S1"], D["S2M"], D["S2L"], D["S3"], D["FLAG"], D["TOT"]
rows25 = D["rows"]
farm25 = D["farm"]
FARM_T = sum(f["tco2e"] for f in farm25)
assert abs(FARM_T - AFR["farm_line_2025"]) < 0.01


def sumr(pred, field="tco2e"):
    return sum(r[field] for r in rows25 if pred(r))


# ------------------------------------------------------------------ 2. 2025 lines, frozen audit lines cross-checked
AL = rcsv(AF / "audit" / "lines.csv")
ref = {f"{r['scope']}|{r['category']}|{r['line_item']}": r for r in rows25}
worst = max(abs(float(a["tco2e"]) - ref[a["line_id"]]["tco2e"]) for a in AL if a["line_id"] in ref)
assert worst < 1e-6, worst
lines_out = []
for a in AL:
    r = ref.get(a["line_id"])
    party = None
    li = a["line_item"]
    m = re.match(r"^(M\d+):(SUP\d+)$", li)
    if m:
        party = dict(kind="supplier", id=m.group(2), name=SUP.get(m.group(2), {}).get("supplier_name"), material=m.group(1), material_name=MM[m.group(1)]["name_en"])
    elif li.startswith("contract_farming"):
        party = dict(kind="farms", id=li.split(":")[2])
    lines_out.append(dict(line_id=a["line_id"], scope=a["scope"], category=a["category"], submission_category=a["submission_category"], line_item=li,
                          tco2e=round(float(a["tco2e"]), 3), flag_t=round(r["flag_t"], 3) if r else 0.0, basis=a["basis"], n_edges=int(a["n_edges"]),
                          n_edges_corrected=int(a["n_edges_corrected"]), n_edges_estimated=int(a["n_edges_estimated"]), party=party))
by_cat = defaultdict(lambda: dict(tco2e=0.0, flag_t=0.0, lines=0))
for l in lines_out:
    b = by_cat[(l["scope"], l["submission_category"])]
    b["tco2e"] += l["tco2e"]
    b["flag_t"] += l["flag_t"]
    b["lines"] += 1
cats = [dict(scope=k[0], category=k[1], tco2e=round(v["tco2e"], 2), flag_t=round(v["flag_t"], 2), lines=v["lines"]) for k, v in sorted(by_cat.items())]
num("inv2025.scope1", S1, "t CO2e")
num("inv2025.scope2_location", S2L, "t CO2e")
num("inv2025.scope2_market", S2M, "t CO2e")
num("inv2025.scope3", S3, "t CO2e")
num("inv2025.flag", FLAG, "t CO2e", "library flag_share on goods/services + FLAG parts of the farm line (N2O, lime, organic soil)")
num("inv2025.total_market", TOT, "t CO2e", "S1 + S2 market + S3")
num("inv2025.cat01", S25["cat01_purchased_goods_services"], "t CO2e")
num("inv2025.farm_line", FARM_T, "t CO2e", "FI contract farms, k fitted")
num("inv2025.farm_line_lo", AFR["farm_line_range"][0], "t CO2e", "a-final held-out worst farm error")
num("inv2025.farm_line_hi", AFR["farm_line_range"][1], "t CO2e")
num("inv2025.biogenic_memo", D["bio"], "t CO2")
print(f"[2] 2025: S1 {S1:.2f} S2L {S2L:.2f} S2M {S2M:.2f} S3 {S3:.2f} FLAG {FLAG:.2f} total {TOT:.2f}; {len(lines_out)} audit lines match recompute (worst {worst:.1e} t)")

# ------------------------------------------------------------------ 3. chip: peat method vs current calculator
cur, by = {}, defaultdict(list)
for x in rcsv(TWIN / "data" / "03_farming" / "current_calculator_footprints.csv"):
    cur[(x["farm_id"], x["crop"], int(x["year"]))] = float(x["carbon_footprint_kgco2e_per_kg"])
    by[(x["crop"], int(x["year"]))].append(float(x["carbon_footprint_kgco2e_per_kg"]))
cmed = {kk: statistics.median(v) for kk, v in by.items()}
ORG = farm.ORG_ADD / 1000


def calc_line(rows, y):
    return sum(r["kg"] * cur.get((r["farm_id"], r["crop"], y), cmed[(r["crop"], y)]) / 1000 for r in rows)


def soil_line(rows, k, rule):
    t = oh = 0.0
    for r in rows:
        rep = 1.0 if r["reported_organic"] else 0.0
        m = min(1.0, r["map_share"] * k)
        sh = {"afinal": rep if rep else m, "map_only": m}[rule]
        t += r["mineral_kg_ha"] * r["area_ha"] / 1000 + ORG * r["area_ha"] * sh
        oh += r["area_ha"] * sh
    return t, oh


r1_25 = [r for r in rows1 if r["year"] == 2025]
CALC = calc_line(r1_25, 2025)
fl_c, oh_c = soil_line(r1_25, K, "afinal")
fl_lo, oh_lo = soil_line(r1_25, 1.0, "map_only")
assert abs(fl_c - FARM_T) < 0.01
gap_c, gap_lo, gap_hi = fl_c - CALC, fl_lo - CALC, AFR["farm_line_range"][1] - CALC
CURTOT = TOT - gap_c          # total the current calculator would have signed
ha25 = sum(r["area_ha"] for r in r1_25)
t_org_c = oh_c * ORG
top = max(farm25, key=lambda r: r["t_org"])
need_c = (gap_c - 0.05 * CURTOT) / t_org_c
need_lo = (gap_lo - 0.05 * CURTOT) / (oh_lo * ORG)
gap_by_year = {}
for y in (2023, 2024):
    ry = [r for r in rows1 if r["year"] == y]
    cy = calc_line(ry, y)
    fy, _ = soil_line(ry, K, "afinal")
    fm, _ = soil_line(ry, 1.0, "map_only")
    den = INV[y]["TOT"] - (fy - cy)
    gap_by_year[y] = dict(calc_t=cy, afinal_pct=100 * (fy - cy) / den, map_only_pct=100 * (fm - cy) / den)
peat = dict(name="Peat method vs the current calculator", denominator="current-practice total (a-final total minus this gap)", denominator_t=CURTOT,
            t=gap_c, pct=100 * gap_c / CURTOT, lo_t=gap_lo, lo_pct=100 * gap_lo / CURTOT, hi_t=gap_hi, hi_pct=100 * gap_hi / CURTOT,
            low_rule="soil map only, k = 1, farmer reports ignored: nothing fitted (lock: the honest floor)",
            central_rule="a-final: farmer-reported organic, else soil-map share x k fitted on 2023-24 dev keys",
            high_rule="a-final farm line plus its worst held-out farm error",
            farm_line_t=fl_c, farm_line_floor_t=fl_lo, current_calculator_t=CALC, peat_t=t_org_c, peat_share_of_line_pct=100 * t_org_c / fl_c,
            peat_ha=oh_c, crop_ha=ha25, peat_ha_share_pct=100 * oh_c / ha25,
            trace_top_farm=dict(farm_id=top["farm_id"], crop=top["crop"], ha=top["area_ha"], org_ha=top["org_ha"], reported_organic=top["reported_organic"],
                                map_share=top["map_share"], t_org=top["t_org"], tco2e=top["tco2e"], survey_id=top["survey_id"]),
            falsifier_share_of_peat_t_to_vanish_central_pct=100 * need_c, falsifier_share_of_peat_t_to_vanish_floor_pct=100 * need_lo,
            other_years={str(y): v for y, v in gap_by_year.items()})
for kk in ("t", "pct", "lo_t", "lo_pct", "hi_t", "hi_pct", "farm_line_floor_t", "current_calculator_t", "peat_t", "peat_share_of_line_pct", "peat_ha_share_pct",
           "falsifier_share_of_peat_t_to_vanish_central_pct", "falsifier_share_of_peat_t_to_vanish_floor_pct"):
    num(f"chip.peat.{kk}", peat[kk], "%" if "pct" in kk else "t CO2e")
num("chip.peat.denominator_t", CURTOT, "t CO2e")
num("chip.peat.trace_top_farm.t_org", top["t_org"], "t CO2e", f"{top['farm_id']} {top['crop']}")
num("chip.peat.trace_top_farm.ha", top["area_ha"], "ha")
for y, v in gap_by_year.items():
    num(f"chip.peat.{y}.map_only_pct", v["map_only_pct"], "%")
    num(f"chip.peat.{y}.afinal_pct", v["afinal_pct"], "%")
print(f"[3] peat: gap {gap_c:.1f} t = {peat['pct']:.2f}% (floor map-only k=1 {peat['lo_pct']:.2f}%, high {peat['hi_pct']:.2f}%); farm line {fl_c:.0f} vs calculator {CALC:.0f}; "
      f"peat {peat['peat_share_of_line_pct']:.1f}% of line on {peat['peat_ha_share_pct']:.2f}% of ha; top {top['farm_id']} {top['crop']} {top['area_ha']:.1f} ha {top['t_org']:.0f} t; "
      f"2023 floor {gap_by_year[2023]['map_only_pct']:.2f}% 2024 floor {gap_by_year[2024]['map_only_pct']:.2f}%")

# ------------------------------------------------------------------ 4. chip: Foodhills full year, on a-final
import pandas as pd  # noqa: E402
fh = pd.read_csv(TWIN / "data" / "03_farming" / "foodhills_odlingsdata_se.csv", sep=";", decimal=",")
fh = fh.rename(columns={"odlar_id": "farm_id", "skördeår": "year", "areal_ha": "area_ha", "levererad_mängd_ton": "t", "kvävegiva_kg_ha": "n_mineral_kg_ha"})
pea_sv = [s for s in SV.values() if s["crop"] == "pea"]
mean = lambda k: float(np.mean([z(s[k]) for s in pea_sv]))  # noqa: E731
P_, LIME_, SPR_ = mean("p_kg_ha"), mean("lime_t_ha"), mean("sprays")
a_reg, o_reg = farm.register(c)        # a-final's register: declared parcels, soil map class
fh_rows, matched = [], 0
for r in fh.to_dict("records"):
    s = dict(crop="pea", n_mineral_kg_ha=r["n_mineral_kg_ha"], n_manure_kg_ha=0.0, yield_t_ha=r["t"] / r["area_ha"], p_kg_ha=P_, lime_t_ha=LIME_,
             sprays=SPR_, diesel_l_ha=r["diesel_l_ha"], irrigated=str(r["bevattnad"]).strip().lower() == "ja", fertiliser_product="")
    p = parts_kg_ha(s, grid=0.012, diesel_ef=2.45 + E["diesel_wtt"])   # METHODOLOGY s5: Swedish grid, Swedish diesel blend
    kk = (r["farm_id"], "pea", int(r["year"]))
    share = o_reg[kk] / a_reg[kk] if a_reg.get(kk) else 0.0          # soil map only, k = 1: nothing fitted
    matched += 1 if a_reg.get(kk) else 0
    t_org = r["area_ha"] * share * farm.ORG_ADD / 1000
    t_flag = t_org + r["area_ha"] * sum(p[x] for x in FLAGP) / 1000
    t_non = r["area_ha"] * sum(v for x, v in p.items() if x not in FLAGP) / 1000
    fh_rows.append(dict(year=int(r["year"]), t=r["t"], ha=r["area_ha"], org_ha=r["area_ha"] * share, t_org=t_org, t_flag=t_flag, t_all=t_flag + t_non))
fy = defaultdict(lambda: defaultdict(float))
for r in fh_rows:
    for x in ("t", "ha", "org_ha", "t_org", "t_flag", "t_all"):
        fy[r["year"]][x] += r[x]
se = fy[2025]
lo5 = min(fy[y]["t_all"] for y in range(2021, 2026))
hi5 = max(fy[y]["t_all"] for y in range(2021, 2026))
en = [e for e in D["T"]["energy"] if e["site_id"] == "S-BJU" and e["year"] == 2025]
bj = defaultdict(float)
for e in en:
    bj[e["carrier"]] += e["mwh"]
bj_months = sorted({e["month"] for e in en})
gas12, el12 = bj["natural_gas"] * 12, bj["electricity"] * 12
bj_in = sumr(lambda r: r["line_item"].startswith("S-BJU") and r["scope"] == "scope1")
bj_rf = sumr(lambda r: r["line_item"].startswith("S-BJU") and r["category"] == "fugitive_refrigerants")
bj_s2m = sumr(lambda r: r["line_item"] == "S-BJU" and r["scope"] == "scope2_market")
bj_s2l = sumr(lambda r: r["line_item"] == "S-BJU" and r["scope"] == "scope2_location")
add_s1 = gas12 * F.FUEL_EF_T_PER_MWH["natural_gas"] + bj_rf - bj_in
add_s2m_res = el12 * F.RESIDUAL_SE[2025] - bj_s2m
add_s2l = el12 * F.GRID_SE_LB[2025] - bj_s2l
tsold = se["t"] * 0.9                                      # ASSUMPTION (b-path): 10 % processing loss
pl, bd = F.PACK_KG_PER_T["frozen_vegetables"]
sales25 = [s for s in c["sales"] if int(s["year"]) == 2025]
out_t = sumr(lambda r: r["category"] == "cat09_downstream_transport") / sum(s["t_sold"] for s in sales25 if s["product_group"] != "rapeseed_meal_expeller")
fh_parts = dict(packaging=tsold * (pl * EF["EF-PE-FILM"] + bd * EF["EF-BOARD"]) / 1000, inbound_60km=se["t"] * 60 * EF["EF-TKM-TRUCK"] / 1000,
                cat09=tsold * out_t, cat11=tsold * 1000 * F.USE_PHASE_KWH_PER_KG["frozen_vegetables"] * F.GRID_SE_LB[2025] / 1000,
                cat12=tsold * (pl / 1000 * F.EOL_PLASTIC_EF_T + bd / 1000 * F.EOL_BOARD_EF_T), cat03=(gas12 * EF["EF-WTT-NG"] + el12 * EF["EF-ELEC-UPSTREAM-SE"]) / 1000)
fh_other = sum(fh_parts.values())
fh_total = add_s1 + se["t_all"] + fh_other
fh_lo = add_s1 * 0.7 + lo5 + fh_other * 0.5
fh_hi = add_s1 * 1.3 + add_s2m_res + hi5 + fh_other * 1.5
foodhills = dict(name="Foodhills full year (Bjuv site and Swedish pea growers, 12 months)", denominator="a-final 2025 total", denominator_t=TOT,
                 t=fh_total, pct=100 * fh_total / TOT, lo_t=fh_lo, lo_pct=100 * fh_lo / TOT, hi_t=fh_hi, hi_pct=100 * fh_hi / TOT,
                 add_s1=add_s1, add_s2m_if_goo=0.0, add_s2m_residual=add_s2m_res, add_s2l=add_s2l, se_farm_t=se["t_all"], se_flag_t=se["t_flag"], se_peat_t=se["t_org"],
                 se_ha=se["ha"], se_peat_ha=se["org_ha"], se_delivered_t=se["t"], se_farm_2021_2025_min=lo5, se_farm_2021_2025_max=hi5, other_s3_proxy=fh_other,
                 other_s3_parts=fh_parts, bjuv_months_in_2025=bj_months, gas12_mwh=gas12, el12_mwh=el12, grower_rows_matched_to_register=matched, grower_rows=len(fh_rows),
                 band_rule="site +-30 %, peas at their 2021-25 min/max, non-farm proxy +-50 %, high adds residual-mix electricity",
                 assumptions=["Bjuv site = 12 x the months in the 2025 feed", "10 % processing loss", "60 km field to plant", "downstream intensity = a-final cat09 per t sold",
                              "Swedish pea P, lime, sprays = mean of Finnish pea survey rows", "peat on Swedish fields from the soil map only, k = 1"])
for kk in ("t", "pct", "lo_pct", "hi_pct", "add_s1", "se_farm_t", "se_flag_t", "se_peat_t", "other_s3_proxy"):
    num(f"chip.foodhills.{kk}", foodhills[kk], "%" if "pct" in kk else "t CO2e")
print(f"[4] Foodhills: +{fh_total:.0f} t = {foodhills['pct']:.2f}% (band {foodhills['lo_pct']:.2f}-{foodhills['hi_pct']:.2f}); S1 +{add_s1:.0f}, SE farms {se['t_all']:.0f} (FLAG {se['t_flag']:.0f}, peat {se['t_org']:.0f}), "
      f"proxy {fh_other:.0f}; Bjuv months {bj_months}; register matched {matched}/{len(fh_rows)} grower rows")

# ------------------------------------------------------------------ 5. chip: Pudasjarvi to co-packing, on a-final
PUD_ING = ("M131", "M133", "M134", "M135", "M136")
ing = [r for r in rows25 if r["category"] == "cat01_purchased_goods" and r["line_item"].split(":")[0] in PUD_ING]
ing_t, ing_flag = sum(r["tco2e"] for r in ing), sum(r["flag_t"] for r in ing)
pud_s1 = sumr(lambda r: r["line_item"].startswith("S-PUD") and r["scope"] == "scope1")
pud_s2m = sumr(lambda r: r["line_item"] == "S-PUD" and r["scope"] == "scope2_market")
pud_s2l = sumr(lambda r: r["line_item"] == "S-PUD" and r["scope"] == "scope2_location")
pud_other = sumr(lambda r: (r["line_item"].startswith("S-PUD") and r["category"] == "cat05_waste") or (r["line_item"] == "S-PUD" and r["category"] == "cat07_employee_commuting")
                 or (r["category"] == "cat03_fuel_energy" and r["line_item"] == "elec_upstream:S-PUD"))
piz = sum(s["t_sold"] for s in sales25 if s["product_group"] == "frozen_pizza")
cop = piz * EF["EF-COPACK-PIZZA"]
cop_flag = cop * FS["EF-COPACK-PIZZA"]
net_s3 = cop - (ing_t + pud_other)
net_flag = cop_flag - ing_flag
net_total = net_s3 - pud_s1 - pud_s2m
plz, bdz = F.PACK_KG_PER_T["frozen_pizza"]
pud_pack = piz * (plz * EF["EF-PE-FILM"] + bdz * EF["EF-BOARD"]) / 1000
TOT_PF = TOT + fh_total
pud = dict(name="Pudasjarvi pizza moves to a co-packer", denominator="a-final 2025 total", denominator_t=TOT, t=net_total, pct=100 * net_total / TOT,
           lo_t=net_total - pud_pack, lo_pct=100 * (net_total - pud_pack) / TOT_PF, hi_t=net_total, hi_pct=100 * net_total / TOT,
           band_rule="low: copack factor already covers packaging, on the Foodhills-restated base; high: packaging stays Apetit's, on the reported base",
           s1_out=pud_s1, s2m_out=pud_s2m, s2l_out=pud_s2l, pizza_t=piz, copack_t=cop, copack_flag_t=cop_flag, ingredients_out_t=ing_t, ingredients_out_flag_t=ing_flag,
           other_s3_out_t=pud_other, net_s3=net_s3, net_flag=net_flag, packaging_t=pud_pack, copack_ef_kg_per_kg=EF["EF-COPACK-PIZZA"],
           breakeven_copack_kg_per_kg=(ing_t + pud_other + pud_s1 + pud_s2m) / piz, trigger_copack_kg_per_kg=(0.05 * TOT_PF + ing_t + pud_other + pud_s1 + pud_s2m) / piz)
for kk in ("t", "pct", "lo_pct", "hi_pct", "s1_out", "copack_t", "ingredients_out_t", "net_flag", "breakeven_copack_kg_per_kg", "trigger_copack_kg_per_kg"):
    num(f"chip.pudasjarvi.{kk}", pud[kk], "%" if "pct" in kk else ("kg CO2e/kg" if "kg_per_kg" in kk else "t CO2e"))
print(f"[5] Pudasjarvi: net +{net_total:.0f} t = {pud['pct']:.2f}% (band {pud['lo_pct']:.2f}-{pud['hi_pct']:.2f}); S1+2 out {pud_s1 + pud_s2m:.0f}; copack {cop:.0f} vs ingredients {ing_t:.0f}; "
      f"break-even copack {pud['breakeven_copack_kg_per_kg']:.2f}, 5% trigger {pud['trigger_copack_kg_per_kg']:.2f} vs library {EF['EF-COPACK-PIZZA']:.2f} kg/kg")

# ------------------------------------------------------------------ 6. other chips: Kantvik, PCF switch, invalid PCFs, pending corrections
lfo = sum(e["mwh"] for e in D["T"]["energy"] if e["site_id"] == "S-KAN" and e["carrier"] == "light_fuel_oil" and e["year"] == 2025)
lfo_t = lfo * F.FUEL_EF_T_PER_MWH["light_fuel_oil"]
kantvik = dict(name="Kantvik steam sale: light fuel oil leaves Scope 1", denominator="a-final 2025 total", denominator_t=TOT, t=-lfo_t, pct=-100 * lfo_t / TOT,
               lo_t=-lfo_t, lo_pct=-100 * lfo_t / TOT, hi_t=0.0, hi_pct=0.0, band_rule="high 0: neutral if the buyer's steam factor passes the oil through to Scope 2", lfo_mwh=lfo)
pcf25 = {(p["supplier_id"], p["material_id"]): p["kgco2e_per_kg"] for p in c["pcf_used"] if p["year"] == 2025}
kgms = defaultdict(float)
for p_ in D["T"]["purchases"]:
    if p_["year"] == 2025 and (p_["supplier_id"], p_["material_id"]) in pcf25:
        kgms[(p_["material_id"], p_["supplier_id"])] += p_["qty_kg"]
t_pcf = defaultdict(float)
t_def = defaultdict(float)
for (mat, sup), kg in kgms.items():
    t_pcf[mat] += kg * pcf25[(sup, mat)] / 1000
    t_def[mat] += kg * EF[MM[mat]["default_ef_id"]] / 1000
rat = sum(t_pcf.values()) / sum(t_def.values())
qlo, qhi = np.percentile([t_pcf[m] / t_def[m] for m in t_pcf], [25, 75])
goods_def = sumr(lambda r: r["category"] == "cat01_purchased_goods" and not r["line_item"].startswith("contract") and r["basis"] != "supplier PCF (PACT)")
pcfswitch = dict(name="All bought goods move to supplier PCFs (method change)", denominator="a-final 2025 total", denominator_t=TOT, t=goods_def * (rat - 1), pct=100 * goods_def * (rat - 1) / TOT,
                 lo_t=goods_def * (qlo - 1), lo_pct=100 * goods_def * (qlo - 1) / TOT, hi_t=goods_def * (qhi - 1), hi_pct=100 * goods_def * (qhi - 1) / TOT,
                 band_rule="observed PCF/default ratio, central = pooled, band = interquartile range across materials", ratio=rat, uncovered_goods_t=goods_def, materials_with_pcf=len(t_pcf))
pcfbad = dict(name="Eight invalid supplier PCFs (library default used, METHODOLOGY s4)", denominator="a-final 2025 total", denominator_t=TOT, t=0.0, pct=0.0,
              lo_t=AFR["pcf_paths_t"]["stale"], lo_pct=100 * AFR["pcf_paths_t"]["stale"] / TOT, hi_t=AFR["pcf_paths_t"]["unit"], hi_pct=100 * AFR["pcf_paths_t"]["unit"] / TOT,
              band_rule="low: stale PCFs kept; high: unit-error PCFs divided by 1000 and kept (a-final results.json pcf_paths_t)")
EDG = rcsv(AF / "audit" / "edges.csv")
COR = {r["id"]: r for r in rcsv(AF / "audit" / "corrections.csv")}
head = ("scope1|", "scope2_market|", "scope3|")
eff, by_rule, ncor = defaultdict(float), defaultdict(float), defaultdict(set)
for e in EDG:
    if e["line_id"].startswith(head) and e["correction_ids"]:
        ids = [i for i in e["correction_ids"].split(";") if i]
        lev = {COR[i]["evidence_level"] for i in ids}
        key = "estimate" if "estimate" in lev else ("no_dev_labels" if "no_dev_labels" in lev else "rule_validated_on_dev_labels")
        d_ = float(e["tco2e"]) - float(e["tco2e_if_raw"])
        eff[key] += d_
        by_rule[";".join(sorted({COR[i]["rule"] for i in ids}))] += d_
        ncor[key].update(ids)
# A reviewer can plausibly reject only judgement calls: estimates and rules with no dev labels. Rejecting a validated unit fix
# (e.g. kWh read as MWh) would put raw typos into the base, so those are not sized on the meter.
jud = -(eff["estimate"] + eff["no_dev_labels"])          # base change if rejected = raw minus clean
top_rule = max(((r, v) for r, v in by_rule.items() if any(COR[i]["rule"] in r.split(";") and COR[i]["evidence_level"] != "rule_validated_on_dev_labels" for i in COR)), key=lambda x: abs(x[1]))
pending = dict(name="Judgement corrections awaiting approval (estimates and rules with no dev labels)", denominator="a-final 2025 total", denominator_t=TOT,
               t=jud, pct=100 * jud / TOT, lo_t=-eff["estimate"], lo_pct=-100 * eff["estimate"] / TOT, hi_t=jud, hi_pct=100 * jud / TOT,
               band_rule="size = base change if all of them were rejected (raw minus clean, headline scopes); low = estimates only",
               dominated_by=dict(rule=top_rule[0], raw_minus_clean_t=-top_rule[1]),
               n_judgement_corrections=len(ncor["estimate"] | ncor["no_dev_labels"]), n_corrections=len(COR),
               clean_minus_raw_by_evidence_level=dict(eff), clean_minus_raw_by_rule=dict(by_rule),
               not_sized="validated unit and duplicate fixes: rejecting them would restore raw-feed typos")
CHIPS = dict(peat=peat, foodhills=foodhills, pudasjarvi=pud, kantvik=kantvik, pcf_switch=pcfswitch, pcf_invalid=pcfbad, pending_corrections=pending)
for cid, ch in CHIPS.items():
    lo, hi = sorted((ch["lo_pct"], ch["hi_pct"]))
    ch["verdict"] = "past the line" if min(abs(lo), abs(hi)) > 5 and lo * hi > 0 else ("reaches the line in its band" if max(abs(lo), abs(hi)) > 5 else "inside the line")
    ch["inside_base"] = cid in ("pcf_invalid", "pending_corrections")
    for kk in ("t", "pct", "lo_pct", "hi_pct"):
        if cid in ("kantvik", "pcf_switch", "pcf_invalid", "pending_corrections"):
            num(f"chip.{cid}.{kk}", ch[kk], "%" if "pct" in kk else "t CO2e")
structural = foodhills["pct"] + pud["pct"] + kantvik["pct"]
num("meter.structural_cumulative_pct", structural, "%", "Foodhills + Pudasjarvi + Kantvik, central, on the a-final total")
print("[6] chips: " + "; ".join(f"{k} {v['pct']:+.2f}% [{v['lo_pct']:+.2f},{v['hi_pct']:+.2f}] {v['verdict']}" for k, v in CHIPS.items()) + f"; structural cumulative {structural:.2f}%")

# ------------------------------------------------------------------ 7. three bases and targets
RATE = dict(s12=.042, s3nf=.025, flag=.0303)
reported = dict(s12=S1 + S2M, s3nf=S3 - FLAG, flag=FLAG)
proforma = dict(s12=reported["s12"] + add_s1, s3nf=reported["s3nf"] + (se["t_all"] - se["t_flag"]) + fh_other, flag=FLAG + se["t_flag"])
recalc = dict(s12=proforma["s12"] - pud_s1 - pud_s2m, s3nf=proforma["s3nf"] + net_s3 - net_flag, flag=proforma["flag"] + net_flag)
BASES = dict(reported=reported, proforma=proforma, recalculated=recalc)
TY = {2030: "checkpoint 2030", 2032: "SBTi V2: five years from a 2027 submission", 2035: "ten-year horizon (V1.3.1)"}
targets = []
for bn, b in BASES.items():
    for y, lab in TY.items():
        for bk, rt in RATE.items():
            red = rt * (y - 2025)
            targets.append(dict(base=bn, target_year=y, option=lab, bucket=bk, rate_pct_yr=rt * 100, cut_pct=red * 100, base_t=b[bk], target_t=b[bk] * (1 - red)))
            num(f"target.{bn}.{bk}.{y}", b[bk] * (1 - red), "t CO2e")
    for bk in RATE:
        num(f"base.{bn}.{bk}", b[bk], "t CO2e")
print("[7] bases: " + "; ".join(f"{bn} " + ", ".join(f"{k} {v:.0f}" for k, v in b.items()) for bn, b in BASES.items()))

# ------------------------------------------------------------------ 8. levers re-based on a-final, and the FLAG gap
NOTES = json.loads((BP / "macc_notes.json").read_text())
LEV = {}
for r in rcsv(BP / "B2_macc.csv"):
    d = {k: (fnum(v) if k not in ("lever_id", "bucket", "cls", "note", "name", "confidence", "co_benefits", "verdict_2030", "flag", "scale_opex") else v) for k, v in r.items()}
    d["rebased"] = False
    LEV[r["lever_id"]] = d
org_t_all = t_org_c + se["t_org"]                         # peat tonnes on contract crops, FI (a-final) + SE (soil map)
feas, feas_all = NOTES["peat"]["feas"], NOTES["peat"]["feas_all"]
l11 = LEV["L11"]
l11.update(ab_low=org_t_all * feas * .5, ab_central=org_t_all * feas, ab_high=org_t_all * feas_all, rebased=True)
l12 = LEV["L12"]
c12 = min(1200.0, org_t_all - l11["ab_central"])
l12.update(ab_low=0.0, ab_central=c12, ab_high=c12 * 1.3, rebased=True)
for L in (l11, l12):
    L["eur_t_central"] = L["cost_yr_central"] / L["ab_central"] if L["ab_central"] else None
    L["eur_t_best"] = L["cost_yr_lo"] / L["ab_high"] if L["ab_high"] else None
    L["eur_t_worst"] = L["cost_yr_hi"] / L["ab_low"] if L["ab_low"] else None
sc = rcsv(TWIN / "data" / "05_scenarios" / "transition_scenarios.csv")
SCN = sorted({r["scenario"] for r in sc}, key=lambda s: [r["scenario"] for r in sc].index(s))


def interp(s, col, y):
    d = sorted((int(r["year"]), float(r[col])) for r in sc if r["scenario"] == s)
    return float(np.interp(y, [a for a, _ in d], [b for _, b in d]))


CAT = {r["scenario"]: r["ngfs_category"] for r in sc}
GRID35 = {"orderly": .7, "disorderly": .85, "too little, too late": .95, "hot house": .95}   # ASSUMPTION (b-path)
FOSSIL = {"L01": 1.0, "L02": 1.0, "L07": 1.0, "L20": .75}
ELEC = sumr(lambda r: r["category"] == "cat11_use_of_sold_products" or r["line_item"].startswith("elec_upstream"))
plan = {int(k): v for k, v in NOTES["peat"]["plan"].items()}


def ramp(y, start, r):
    return 0.0 if y < start else min(1.0, (y - start + 1) / max(r, 1))


def adopted(s, levers):
    out = {}
    for i, r in levers.items():
        if r["cls"] == "not_in_inventory" or r["eur_t_central"] is None or r["ab_central"] <= 0:
            continue
        for y in range(int(r["earliest_start"]), 2036):
            cost = r["eur_t_central"] * (interp(s, "n_fertiliser_price_index", y) if i == "L08" else 1.0) - interp(s, "eu_ets2_fuel_price_eur_t", y) * FOSSIL.get(i, 0)
            if cost <= interp(s, "carbon_price_eur_t", y):
                out[i] = y
                break
    return out


def path(s, col="ab_central", force_all=False, drop=()):
    levers = {i: r for i, r in LEV.items() if i not in drop}
    ad = {i: int(r["earliest_start"]) for i, r in levers.items() if r["cls"] != "not_in_inventory"} if force_all else adopted(s, levers)
    out = []
    for y in range(2025, 2036):
        v = interp(s, "plant_based_demand_index", y)
        b = dict(recalc) if y >= 2027 else dict(proforma)
        bau = {k: b[k] * v for k in b}
        ratio = plan.get(y, np.mean([plan[t] for t in range(2027, 2032)])) / plan[2025]
        bau["flag"] += org_t_all * (ratio - 1) * v
        g = 1 - (1 - GRID35[CAT[s]]) * (y - 2025) / 10
        bau["s3nf"] -= ELEC * (1 - g) * v
        ab = dict(s12=0.0, s3nf=0.0, flag=0.0)
        for i, st in ad.items():
            r = levers[i]
            d = r[col] * ramp(y, st, int(r["ramp_years"])) * v
            if r["bucket"] == "s12":
                ab["s12"] += d
            else:
                ab["flag"] += d * r["flag_frac"]
                ab["s3nf"] += d * (1 - r["flag_frac"])
        for k in RATE:
            t = recalc[k] * (1 - RATE[k] * (y - 2025))
            out.append(dict(scenario=s, year=y, bucket=k, bau_t=bau[k], abated_t=ab[k], pathway_t=bau[k] - ab[k], target_t=t, gap_t=bau[k] - ab[k] - t))
    return out, ad


PW, ADS = [], {}
for s in SCN:
    d, ad = path(s)
    PW += d
    ADS[s] = ad
MAIN = ["net_zero_2050", "delayed_transition", "current_policies"]
ceil = {}
for s in MAIN:
    for lab, col, drop in (("low", "ab_low", ()), ("central", "ab_central", ()), ("high", "ab_high", ()), ("central, no L11", "ab_central", ("L11",)), ("high, no L11", "ab_high", ("L11",))):
        d, _ = path(s, col, True, drop)
        ceil[f"{s}|{lab}"] = {r["bucket"]: r["gap_t"] for r in d if r["year"] == 2035}
SEED = ("M101", "M102", "M103", "M104", "M105", "M106", "M107")
seed_flag = sum(r["flag_t"] for r in rows25 if r["category"] == "cat01_purchased_goods" and r["line_item"].split(":")[0] in SEED)
best = min(v["flag"] for k, v in ceil.items() if k.endswith("|high"))
flaggap = dict(rule="every catalogue lever on at its earliest start, 2035 FLAG pathway minus the FLAG target on the recalculated base (3.03 %/yr linear)",
               central_range_t=[min(ceil[f"{s}|central"]["flag"] for s in MAIN), max(ceil[f"{s}|central"]["flag"] for s in MAIN)],
               most_favourable_t=best, ceilings_2035=ceil, seed_flag_t=seed_flag, seed_flag_share_of_recalc_flag_pct=100 * seed_flag / recalc["flag"],
               flag_target_2035_t=recalc["flag"] * (1 - RATE["flag"] * 10), flag_cut_needed_2035_t=recalc["flag"] * RATE["flag"] * 10,
               s12_2035_gap_central_range_t=[min(ceil[f"{s}|central"]["s12"] for s in MAIN), max(ceil[f"{s}|central"]["s12"] for s in MAIN)],
               cost_rule_gap_range={f"{b}_{y}": [min(r["gap_t"] for r in PW if r["bucket"] == b and r["year"] == y), max(r["gap_t"] for r in PW if r["bucket"] == b and r["year"] == y)]
                                    for b in RATE for y in (2030, 2032, 2035)},
               adopted_by_scenario=ADS, peat_t_used=org_t_all)
num("flaggap.central_lo_t", flaggap["central_range_t"][0], "t CO2e", "2035, all levers on, delayed/current policies")
num("flaggap.central_hi_t", flaggap["central_range_t"][1], "t CO2e", "2035, all levers on, net zero 2050")
num("flaggap.most_favourable_t", best, "t CO2e", "all levers at high")
num("flaggap.no_L11_central_hi_t", max(ceil[f"{s}|central, no L11"]["flag"] for s in MAIN), "t CO2e")
num("flaggap.seed_flag_share_pct", flaggap["seed_flag_share_of_recalc_flag_pct"], "%")
num("flaggap.s12_central_worst_t", flaggap["s12_2035_gap_central_range_t"][1], "t CO2e", "negative = target met")
design = sum(L["abatement_tco2e_2030_design"] for L in LEV.values())
phys = sum(L["ab_central"] for L in LEV.values() if L["cls"] == "real")
realloc = sum(L["ab_central"] for L in LEV.values() if L["cls"] == "reallocation")
num("levers.catalogue_design_t", design, "t CO2e")
num("levers.physical_central_t", phys, "t CO2e")
num("levers.reallocation_central_t", realloc, "t CO2e")
num("levers.L11_central_t", l11["ab_central"], "t CO2e")
# verdict at 2030 prices (same rule as b-path), re-run for every lever
for i, r in LEV.items():
    if r["eur_t_central"] is None:
        r["verdict_2030_rebased"] = "not costable"
        continue
    ets = [interp(s, "eu_ets2_fuel_price_eur_t", 2030) * FOSSIL.get(i, 0) for s in SCN]
    pr = [interp(s, "carbon_price_eur_t", 2030) for s in SCN]
    w = r["eur_t_worst"] if r["eur_t_worst"] is not None else float("inf")
    r["verdict_2030_rebased"] = "do in every scenario" if w - min(ets) <= min(pr) else ("skip in every scenario" if r["eur_t_best"] - max(ets) > max(pr) else "depends on scenario or evidence")
levers = []
for i, r in LEV.items():
    pros = [x for x in (r["co_benefits"], "saves money each year" if r["cost_yr_central"] < 0 else "", f"{r['confidence']} confidence" if r["confidence"] == "high" else "") if x]
    cons = [x for x in (r["note"], "moves emissions between suppliers, no physical cut" if r["cls"] == "reallocation" else "", "not counted by the inventory method" if r["cls"] == "not_in_inventory" else "",
                        f"{r['confidence']} confidence" if r["confidence"] == "low" else "", f"capex EUR {r['capex_eur']:,.0f}" if r["capex_eur"] else "") if x]
    levers.append(dict(id=i, name=r["name"], bucket=r["bucket"], cls=r["cls"], flag_frac=r["flag_frac"], t_low=r["ab_low"], t_central=r["ab_central"], t_high=r["ab_high"],
                       catalogue_t=r["abatement_tco2e_2030_design"], capex_eur=r["capex_eur"], cost_eur_yr=r["cost_yr_central"], cost_eur_yr_lo=r["cost_yr_lo"], cost_eur_yr_hi=r["cost_yr_hi"],
                       eur_per_t=r["eur_t_central"], eur_per_t_best=r["eur_t_best"], eur_per_t_worst=r["eur_t_worst"], earliest_start=int(r["earliest_start"]), ramp_years=int(r["ramp_years"]),
                       confidence=r["confidence"], verdict_2030=r["verdict_2030_rebased"], verdict_2030_bpath=r["verdict_2030"], pros=pros, cons=cons,
                       sized_on="a-final (peat tonnes re-based)" if r["rebased"] else "b-path inventory (not inventory-sensitive beyond rounding; not re-based)"))
print(f"[8] FLAG 2035 gap, all levers on: {flaggap['central_range_t'][0]:.0f} to {flaggap['central_range_t'][1]:.0f} t (most favourable {best:.0f}); bought seed {flaggap['seed_flag_share_of_recalc_flag_pct']:.1f}% of FLAG; "
      f"catalogue {design:.0f} t design, {phys:.0f} physical, {realloc:.0f} reallocation (L11 {l11['ab_central']:.0f})")

# ------------------------------------------------------------------ 9. 2023 -> 2025 comparison
def goods_fixed(y):
    g = defaultdict(float)
    for p_ in INV[y]["T"]["purchases"]:
        m = MM.get(p_["material_id"])
        if p_["year"] != y or p_["material_id"] in lib.CROP_MAT or not m or m["material_group"] in ("service", "capex") or m["default_ef_id"] not in EF:
            continue
        g[p_["material_id"]] += p_["qty_kg"] * EF[m["default_ef_id"]] / 1000
    return g


def s3_nopcf(y):
    T2 = dict(INV[y]["T"])
    T2["pcf_used"] = []
    rr, _ = lib.compute_inventory(T2, y)
    return sum(r["tco2e"] for r in rr if r["scope"] == "scope3")


years = {}
for y in (2023, 2024, 2025):
    d = INV[y]
    years[str(y)] = dict(scope1=d["S1"], scope2_location=d["S2L"], scope2_market=d["S2M"], scope3=d["S3"], flag=d["FLAG"], total_market=d["TOT"],
                         farm_line=sum(f["tco2e"] for f in d["farm"]), farm_peat_t=sum(f["t_org"] for f in d["farm"]),
                         categories={k: v for k, v in d["summ"].items() if k.startswith("cat") or k in ("fugitive_refrigerants", "stationary_and_mobile_combustion")})
    for kk in ("scope1", "scope2_market", "scope3", "flag", "total_market"):
        num(f"year.{y}.{kk}", years[str(y)][kk], "t CO2e")
decomp = {}
for a, b in ((2023, 2024), (2024, 2025)):
    tot = INV[b]["S3"] - INV[a]["S3"]
    method = INV[b]["S3"] - s3_nopcf(b)
    farm_d = years[str(b)]["farm_line"] - years[str(a)]["farm_line"]
    peat_d = years[str(b)]["farm_peat_t"] - years[str(a)]["farm_peat_t"]
    ga, gb = goods_fixed(a), goods_fixed(b)
    vol = sum(gb.values()) - sum(ga.values())
    other = tot - method - farm_d - vol
    decomp[f"{a}_{b}"] = dict(scope3_change_t=tot, volume_at_fixed_factors_t=vol, pcf_replacing_defaults_t=method, farm_line_t=farm_d, of_which_peat_t=peat_d, everything_else_t=other,
                              shares_pct=dict(volume=100 * vol / tot, pcf=100 * method / tot, farm=100 * farm_d / tot, other=100 * other / tot),
                              note="pcf term compares the later year with and without supplier PCFs; volume term is bought goods at fixed library factors")
    num(f"decomp.{a}_{b}.scope3_change_t", tot, "t CO2e")
    for kk, v in decomp[f"{a}_{b}"]["shares_pct"].items():
        num(f"decomp.{a}_{b}.{kk}_pct", v, "%")
print("[9] " + "; ".join(f"{k}: S3 {v['scope3_change_t']:+.0f} t = volume {v['shares_pct']['volume']:.1f}% + PCF {v['shares_pct']['pcf']:.1f}% + farm {v['shares_pct']['farm']:.1f}% + other {v['shares_pct']['other']:.1f}%" for k, v in decomp.items()))

# ------------------------------------------------------------------ 10. forward views (copied, labelled with their own script)
fwd = {}
for name, p, script in (("climate_eur", OUTROOT / "c3_euro_risk/results.json", "stages/c3_euro_risk/summarize.py"), ("climate_yield_risk", OUTROOT / "c2_climate_risk/results.json", "stages/c2_climate_risk/run_c2.py"),
                        ("yields", OUTROOT / "c1_yields/results.json", "stages/c1_yields/summarize.py"), ("nature_catchments", OUTROOT / "d1_decide/results.json", "stages/d1_decide/finalize.py")):
    try:
        fwd[name] = dict(source=str(p.relative_to(OUTROOT)), script=script, data=json.loads(p.read_text()), rebased="no: does not depend on the inventory")
    except Exception as ex:  # noqa: BLE001
        fwd[name] = dict(source=str(p.relative_to(OUTROOT)), error=f"{type(ex).__name__}: {ex}")
fwd["nature_catchments"]["lock_rule"] = "D1: state only CA12 first and the 'fewer Swedish catchments' claim; no named top-5"
print("[10] forward views: " + ", ".join(f"{k} {'ok' if 'data' in v else v['error']}" for k, v in fwd.items()))

# ------------------------------------------------------------------ 11. con2-a Jälki figures: old (b-path) vs new (a-final)
ST = json.loads((BP / "structure.json").read_text())
PS = json.loads((BP / "pathway_summary.json").read_text())
CK = json.loads((BP / "checks.json").read_text())
bfl = [r for r in rcsv(BP / "farm_lines.csv") if r["year"] == "2025" and r["region"].startswith("FI")]
b_fi = sum(float(r["tco2e"]) for r in bfl)
b_org = sum(float(r["t_org"]) for r in bfl)
b_ha = sum(float(r["ha"]) for r in bfl)
b_oha = sum(float(r["org_ha_del"]) for r in bfl)
b_top = max(bfl, key=lambda r: float(r["t_org"]))
b_cur = ST["reported"]["total"] - ST["measure"]["peat_gap"]
bmacc = rcsv(BP / "B2_macc.csv")
b_c = {r["lever_id"]: r for r in bmacc}
sak_old = [r for r in rcsv(BP / "corrections_log.csv") if r["record_key"] == "energy:S-SAK:2025-06:electricity"]
sak_new = [r for r in COR.values() if r["record_key"] == "energy:S-SAK:2025-06:electricity"]
dc = CK.get("decomp", {})
s3b = {}
for nm, pth in (("a2-inv", "history_a2_inv/A2_inventory_2025_submission.csv"), ("a2-inv-b", "history_a2_inv_b/A2_inventory_2025_submission.csv"), ("b-path", "b_pathways/outputs/A2_inventory_2025_submission.csv"),
                ("a-final", "a2_inventory/A2_inventory_2025_submission.csv")):
    s3b[nm] = sum(float(r["tco2e"]) for r in rcsv(OUTROOT / pth) if r["scope"] == "scope3")
try:
    s3b["e-copilot"] = json.loads((OUTROOT / "e_copilot/e_copilot_results.json").read_text())["extras"]["s3"]
except Exception:  # noqa: BLE001
    pass
M = []


def mv(item, old, new, unit, why):
    dp = 2 if unit == "%" else 0          # moves if the figure as displayed changes
    moved = None if (old is None or new is None or isinstance(old, str) or isinstance(new, str)) else round(old, dp) != round(new, dp)
    M.append(dict(item=item, old=old, new=new, unit=unit, moved=moved if moved is not None else (old != new), why=why))


mv("peat change, t", ST["measure"]["peat_gap"], gap_c, "t CO2e", "a-final farm line (register area, median fill, k fitted) replaces b-path's")
mv("peat change, % of current-practice total", ST["measure"]["peat_pct"], peat["pct"], "%", "same")
mv("peat worst case (map 12% error against us), %", 100 * (ST["measure"]["peat_gap"] - 0.12 * b_org) / b_cur, 100 * (gap_c - 0.12 * t_org_c) / CURTOT, "%",
   "lock replaces this leg with the map-only, nothing-fitted floor")
mv("peat honest floor (soil map only, k = 1), %", None, peat["lo_pct"], "%", "new: the lock's floor; con2-a had none")
mv("contract-farm line, t", b_fi, fl_c, "t CO2e", "a-final pipeline")
mv("current calculator farm line, t", ST["measure"]["cur_t"], CALC, "t CO2e", "same rows as a-final's farm line")
mv("peat share of farm line, %", 100 * b_org / b_fi, peat["peat_share_of_line_pct"], "%", "a-final")
mv("peat share of farm hectares, %", 100 * b_oha / b_ha, peat["peat_ha_share_pct"], "%", "a-final register area")
mv("trace farm", f"{b_top['farm_id']} {b_top['crop']} {float(b_top['ha']):.1f} ha, {float(b_top['t_org']):.0f} t peat",
   f"{top['farm_id']} {top['crop']} {top['area_ha']:.1f} ha, {top['t_org']:.0f} t peat", "", "largest peat row on a-final")
mv("falsifier: share of mapped peat tonnes that must be mineral for the change to fall under 5%, %", 100 * (ST["measure"]["peat_gap"] - 0.05 * b_cur) / b_org, peat["falsifier_share_of_peat_t_to_vanish_central_pct"], "%",
   "central; at the floor it is " + f"{peat['falsifier_share_of_peat_t_to_vanish_floor_pct']:.1f}%")
mv("Foodhills full year, %", ST["foodhills"]["pct"], foodhills["pct"], "%", "a-final total, a-final Bjuv lines, register-based Swedish peat")
mv("Foodhills band low, %", ST["foodhills"]["lo_pct"], foodhills["lo_pct"], "%", "same")
mv("Foodhills band high, %", ST["foodhills"]["hi_pct"], foodhills["hi_pct"], "%", "same")
mv("Pudasjarvi co-packing, %", ST["pudasjarvi"]["pct"], pud["pct"], "%", "a-final lines and total")
mv("Pudasjarvi band low, %", CK.get("pud", {}).get("pct_pf_b"), pud["lo_pct"], "%", "same")
for bk, lab in (("s12", "Scope 1+2"), ("s3nf", "Scope 3 non-FLAG"), ("flag", "FLAG")):
    mv(f"base {lab} (Foodhills pro forma), t", PS["base"][bk], proforma[bk], "t CO2e", "con2-a labels this figure a 2032 target; it is the base")
    mv(f"2032 target {lab} (recalculated base), t", PS["rc"][bk] * (1 - RATE[bk] * 7), recalc[bk] * (1 - RATE[bk] * 7), "t CO2e", "the actual 2032 target, for the screen")
mv("FLAG 2035 miss, all levers on, low end, t", PS["ceiling"]["delayed_transition|central"]["flag"], flaggap["central_range_t"][0], "t CO2e", "a-final bases, peat re-based levers")
mv("FLAG 2035 miss, all levers on, high end, t", PS["ceiling"]["net_zero_2050|central"]["flag"], flaggap["central_range_t"][1], "t CO2e", "same")
mv("bought rapeseed share of FLAG, %", 100 * PS["seed_flag"] / PS["rc"]["flag"], flaggap["seed_flag_share_of_recalc_flag_pct"], "%", "a-final FLAG split")
d0 = decomp["2023_2024"]
if dc:
    mv("Scope 3 change 2023 to 2024, t", dc["total"], d0["scope3_change_t"], "t CO2e", "a-final 2023 and 2024")
    mv("of which buying less, %", 100 * dc["volume"] / dc["total"], d0["shares_pct"]["volume"], "%", "a-final cleaned ERP")
    mv("of which supplier PCFs replacing defaults, %", 100 * dc["method"] / dc["total"], d0["shares_pct"]["pcf"], "%", "a-final PCF validity rules")
    mv("left for everything else, %", 100 * dc["other"] / dc["total"], d0["shares_pct"]["other"], "%", "same")
mv("lever catalogue at face value, t", sum(fnum(r["abatement_tco2e_2030_design"]) for r in bmacc), design, "t CO2e", "catalogue unchanged")
mv("physical abatement, central, t", sum(fnum(r["ab_central"]) for r in bmacc if r["cls"] == "real"), phys, "t CO2e", "L12 re-based on a-final peat")
mv("reallocation only (L11), t", fnum(b_c["L11"]["ab_central"]), realloc, "t CO2e", "L11 re-based on a-final peat")
mv("Saekylae June 2025 electricity log row", f"{sak_old[0]['old']} -> {sak_old[0]['new']}" if sak_old else None, f"{sak_new[0]['old']} -> {sak_new[0]['new']}" if sak_new else None,
   "", f"a-final correction {sak_new[0]['id'] if sak_new else '?'} ({sak_new[0]['rule'] if sak_new else '?'}): {sak_new[0]['reason'] if sak_new else ''}")
s3_old = [v for k, v in s3b.items() if k != "a-final"]
mv("Scope 3 spread across builds, t (new adds a-final)", max(s3_old) - min(s3_old), max(s3b.values()) - min(s3b.values()), "t CO2e", "builds: " + ", ".join(f"{k} {v:.0f}" for k, v in s3b.items()))
mv("a1-dq / b-path dev scores", "b-path inventory 94.58 / 94.22 in-sample", f"a-final held-out {AFR['a2_held_out']['2023']} / {AFR['a2_held_out']['2024']}; issues cross-year {AFR['a1_cross_year']['score']}", "",
   "a-final is the product pipeline (lock)")
mv("inventory headline range", "98.27 alone", "95.8-98.3 (lock)", "", "lock: not 98.27 alone")
nmove = sum(1 for m in M if m["moved"])
print(f"[11] con2-a reproduction: {len(M)} figures, {nmove} move")
for m in M:
    o = f"{m['old']:.2f}" if isinstance(m["old"], float) else m["old"]
    n = f"{m['new']:.2f}" if isinstance(m["new"], float) else m["new"]
    print(f"     {'MOVES' if m['moved'] else 'same '} | {m['item']} | {o} -> {n}")

# ------------------------------------------------------------------ 12. trail: line -> category -> farm/supplier -> record -> log row -> factor -> assumption
TR = HERE / "trail"
if TR.exists():
    shutil.rmtree(TR)
(TR / "l").mkdir(parents=True)
FAC = {r["factor_id"]: r for r in rcsv(AF / "audit" / "factors.csv")}
ISS = rcsv(AF / "audit" / "issues.csv")
ASSUME = {
    "A01": "Contract-farm footprint per farm row = mineral-soil kg CO2e/ha from the farm survey (METHODOLOGY s5) x parcel-register area, plus the organic-soil add-on (29.0 t CO2/ha + 13 kg N2O-N/ha) on organic area.",
    "A02": f"Organic area = whole crop area if the farmer reports organic soil, else soil-map organic share x k = {K:.4f} (fitted once on the 2023-24 dev keys; soil map about 88 % accurate). The board-facing floor uses k = 1 and the map only.",
    "A03": "Farms that did not answer the survey take the crop-year median per-ha footprint.",
    "A04": "Swedish (Foodhills) growers are outside the 2025 boundary: acquired in December 2025 (METHODOLOGY s1).",
    "A05": "Emission factor from the organisers' library (emission_factor_library.csv), as listed with its source.",
    "A06": "A supplier PCF is used only if valid (period, unit, scope); invalid ones fall back to the library default (METHODOLOGY s4).",
    "A07": "Fuel: delivered quantity less stock change x net calorific value x fossil factor; biogenic CO2 is a memo outside Scope 1.",
    "A08": "Electricity: location = MWh x grid average; market = MWh less same-vintage registry GoO, capped at consumption, x residual mix.",
    "A09": "Refrigerant: kg topped up x IPCC AR6 GWP100.",
    "A10": "Commuting: 2025 survey site mean x site headcount.",
    "A11": "Use phase and end of life: organisers' constants per product group and market.",
    "A12": "Spend-based categories: spend in EUR x EEIO factor.",
    "A13": "Correction rule validated on the 2023-24 dev labels; still pending expert approval.",
    "A14": "Correction is an estimate (no raw value to restore); pending expert approval.",
    "A15": "Correction rule has no dev labels; pending expert approval.",
}


def fac_assume(fid):
    if not fid:
        return None
    if fid.startswith("FARMROW"):
        return "A01"
    if fid.startswith(("FUEL_EF", "FUEL_BIOGENIC", "NCV")):
        return "A07"
    if fid.startswith(("GRID", "RESIDUAL", "HEAT")):
        return "A08"
    if fid.startswith("GWP"):
        return "A09"
    if fid.startswith("COMMUTE"):
        return "A10"
    if fid.startswith(("USE:", "EOL:")):
        return "A11"
    if fid.startswith("EF-SPEND"):
        return "A12"
    if fid.startswith("PCF"):
        return "A06"
    return "A05"


EVA = {"rule_validated_on_dev_labels": "A13", "estimate": "A14", "no_dev_labels": "A15"}
files = sorted({e["source_file"] for e in EDG})
fidx = {f: i for i, f in enumerate(files)}
farmmeta = {f"farm:{r['farm_id']}:{r['crop']}:{r['year']}": dict(ha=round(r["area_ha"], 2), org_ha=round(r["org_ha"], 2), map_share=round(r["map_share"], 4), reported_organic=r["reported_organic"],
                                                                  t=round(r["tco2e"], 3), t_peat=round(r["t_org"], 3), t_flag=round(r["t_flag"], 3), kg=round(r["kg"], 1), fill=r["src"], survey_id=r["survey_id"],
                                                                  assumptions=["A01", "A02"] + (["A03"] if not r["survey_id"] else [])) for r in farm25}
COLS = ["edge", "record", "file", "row", "role", "raw", "raw_unit", "clean", "clean_unit", "factor", "mult", "t", "t_if_raw", "corr", "party"]
byline = defaultdict(list)
for e in EDG:
    byline[e["line_id"]].append(e)
idx, lid2shard = [], {}
for n, (lid, es) in enumerate(sorted(byline.items())):
    sh = f"l/{n:03d}.json"
    lid2shard[lid] = sh
    scope, cat, item = lid.split("|", 2)
    parties = defaultdict(lambda: dict(t=0.0, n=0))
    rowsj = []
    for e in es:
        if e["sub_line"]:
            party = e["sub_line"]
        else:
            m = re.match(r"^(M\d+):(SUP\d+)$", item)
            party = f"supplier:{m.group(2)}" if m else f"item:{item}"
        parties[party]["t"] += float(e["tco2e"])
        parties[party]["n"] += 1
        rowsj.append([e["edge_id"], e["record_key"], fidx[e["source_file"]], int(e["source_row"]) if e["source_row"] else None, e["role"], e["raw_value"], e["raw_unit"],
                      e["clean_value"], e["clean_unit"], e["factor_id"] or None, fnum(e["multiplier"]), round(float(e["tco2e"]), 6), round(float(e["tco2e_if_raw"]), 6), e["correction_ids"] or None, party])
    pj = {}
    for p_, v in parties.items():
        meta = dict(t=round(v["t"], 4), n=v["n"])
        if p_ in farmmeta:
            meta.update(farmmeta[p_])
        elif p_.startswith("supplier:"):
            sid = p_.split(":")[1]
            meta.update(name=SUP.get(sid, {}).get("supplier_name"), country=SUP.get(sid, {}).get("country"), material=item.split(":")[0], material_name=MM[item.split(":")[0]]["name_en"])
        pj[p_] = meta
    lt = sum(float(e["tco2e"]) for e in es)
    shard = dict(line_id=lid, scope=scope, category=cat, item=item, t=round(lt, 4), cols=COLS, parties=pj, edges=rowsj)
    (TR / sh).write_text(json.dumps(shard, separators=(",", ":"), ensure_ascii=False))
    idx.append(dict(line_id=lid, scope=scope, category=cat, item=item, t=round(lt, 4), n_edges=len(es), n_parties=len(pj), shard=sh))
tree = defaultdict(lambda: defaultdict(list))
for r in idx:
    tree[r["scope"]][r["category"]].append(r["line_id"])
(TR / "index.json").write_text(json.dumps(dict(note="Synthetic pack, not Apetit's real emissions. Every correction pending expert approval.", columns=COLS, files=files, lines=idx,
                                               tree={s: dict(cs) for s, cs in tree.items()}), separators=(",", ":"), ensure_ascii=False))
corr_j = {i: dict(table=r["table"], record=r["record_key"], field=r["field"], old=r["old"], new=r["new"], rule=r["rule"], reason=r["reason"], evidence=r["evidence_level"],
                  approval=r["approval"], assumption=EVA.get(r["evidence_level"])) for i, r in COR.items()}
(TR / "corrections.json").write_text(json.dumps(corr_j, separators=(",", ":"), ensure_ascii=False))
(TR / "factors.json").write_text(json.dumps({i: dict(value=fnum(r["value"]), unit=r["unit"], source=r["source"], assumption=fac_assume(i)) for i, r in FAC.items()}, separators=(",", ":"), ensure_ascii=False))
(TR / "assumptions.json").write_text(json.dumps(ASSUME, indent=0, ensure_ascii=False))
(TR / "issues.json").write_text(json.dumps(ISS, separators=(",", ":"), ensure_ascii=False))
# self-test: every edge resolves, every line sums, every factor and correction exists, every factor has an assumption
miss_f = {e["factor_id"] for e in EDG if e["factor_id"] and e["factor_id"] not in FAC}
miss_c = {i for e in EDG for i in e["correction_ids"].split(";") if i and i not in COR}
ln_t = {l["line_id"]: l["tco2e"] for l in lines_out}
worst_t = max(abs(r["t"] - ln_t[r["line_id"]]) for r in idx if r["line_id"] in ln_t)
n_edges = sum(r["n_edges"] for r in idx)
assert n_edges == len(EDG) == man["counts"]["edges"] and not miss_f and not miss_c and worst_t < 0.01, (n_edges, miss_f, miss_c, worst_t)
trail_bytes = sum(p.stat().st_size for p in TR.rglob("*") if p.is_file())
largest = max((p.stat().st_size, p.name) for p in (TR / "l").glob("*.json"))
assert trail_bytes < 12e6
print(f"[12] trail: {n_edges} edges in {len(idx)} line shards, {trail_bytes / 1e6:.2f} MB (largest shard {largest[1]} {largest[0] / 1e3:.0f} kB); all factors, corrections resolve; line sums within {worst_t:.1e} t")
num("audit.edges", n_edges, "count")
num("audit.lines", len(idx), "count")
num("audit.corrections_pending", len(COR), "count")
num("audit.issues", len(ISS), "count")
for kk, v in (("a2_held_out_2023", AFR["a2_held_out"]["2023"]), ("a2_held_out_2024", AFR["a2_held_out"]["2024"]), ("a1_cross_year", AFR["a1_cross_year"]["score"])):
    num(f"score.{kk}", v, "points", "from a2_inventory/results.json (stages/a2_inventory/run_final.py)")

# ------------------------------------------------------------------ 13. bundle
for l in lines_out:
    l["trail_shard"] = "trail/" + lid2shard.get(l["line_id"], "")
bundle = dict(
    label="SYNTHETIC PACK (Since AI 2026). Not Apetit's real emissions. Every correction is pending expert approval.",
    built_by=SCRIPT, pipeline="stages/a2_inventory (k fitted once on dev keys)", k=K, a_final_facts_check=AFR["facts_check"],
    inventory_2025=dict(totals=dict(scope1=S1, scope2_location=S2L, scope2_market=S2M, scope3=S3, flag=FLAG, scope3_nonflag=S3 - FLAG, total_market=TOT, biogenic_memo=D["bio"]),
                        categories=cats, lines=lines_out, farm_line=dict(t=FARM_T, lo=AFR["farm_line_range"][0], hi=AFR["farm_line_range"][1])),
    bases=dict(definitions=dict(reported="a-final 2025 as reported", proforma="plus Foodhills 12 months (the base con2-a's screen shows)",
                                recalculated="pro forma plus Pudasjarvi co-packing (b-path's target convention)"),
               values=BASES, rates_pct_yr={k: v * 100 for k, v in RATE.items()}, targets=targets),
    meter=dict(line_pct=5.0, chips=CHIPS, structural_cumulative_pct=structural,
               verdict_rule="'past the line' only when the whole band sits beyond 5 %; Foodhills and Pudasjarvi get no verdict word on screen (con2-a / L12)"),
    levers=levers, lever_totals=dict(catalogue_design_t=design, physical_central_t=phys, reallocation_central_t=realloc),
    flag_gap=flaggap, pathway=[{k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()} for r in PW],
    years=years, decomposition=decomp, builds_scope3=s3b, forward=fwd, con2a_moves=M,
    numbers=LEDGER)
out = HERE / "bundle.json"
out.write_text(json.dumps(bundle, indent=0, default=float, ensure_ascii=False))
sz = out.stat().st_size
assert sz < 3e6, sz
print(f"[13] bundle.json {sz / 1e6:.2f} MB, {len(LEDGER)} ledger numbers; total build {time.time() - T0:.1f}s")
