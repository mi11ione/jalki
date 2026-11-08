"""D1 model: parcel-level export-coefficient model for P and N to water, calibrated on monitored outlet loads.

Run: python stages/d1_model_a/model.py [VARIANT]
VARIANT (default 'primary') is one of VARIANTS below. Writes $CCN_OUT/d1_model_a/pred_<VARIANT>.csv and,
for 'primary', D1_catchment_priority_submission.csv + detail_primary.csv. Does NOT read the dev key.

Structure (per parcel i in catchment c, year y):
  field_P_i = P_idx_i  (soil-P test, clay, slope, erosion-prone crop, buffer strip, catch crop, drainage, rain)
  field_N_i = N_idx_i  (N surplus from applied N - crop N removal, catch crop, soil texture, drainage, rain)
  delivered_i = field_i * exp(-dist_to_water_i / L)
  to_water_c = s_{region,year} * (1 - retention_c) * sum_i area_i * delivered_i
Calibration (monitored catchments only, 2019-2025):
  load_cy = (1 - ret_c) * s_{r,y} * [ sum_{contract parcels} area*idx*deliv + noncontract_ha_c * ibar_c ] + bg * km2_c
  where ibar_c = per-ha mean of idx*deliv over contract-farm parcels in c (shrunk to region mean),
  i.e. non-contract farmland is assumed to look like the contract farms' own farmland.
  bg (natural background, kg/km2) is one pooled value per nutrient; s_{r,2025} is used for the 2025 estimate.
Apetit = parcels whose 2025 declared crop is a contract crop (pea, potato, carrot, spinach, turnip_rape),
same definition as the organisers' baseline (ccn_tools/baselines.py::d1_area).
"""
import math, sys, collections
from d1lib import rd, DATA, WORK, APETIT_CROPS, STATE_WEIGHT, median, write_csv

# ---------------------------------------------------------------- priors (set before any dev scoring)
MGMT_N = {'pea': 25, 'potato': 95, 'carrot': 100, 'spinach': 130, 'turnip_rape': 95, 'barley': 95, 'oats': 85,
          'wheat': 120, 'grass_ley': 150, 'fallow': 0}            # ccn_tools/factors.py MGMT_NORMS
N_PER_T = {'pea': 10, 'potato': 3.5, 'carrot': 1.5, 'spinach': 4.0, 'turnip_rape': 33, 'barley': 17, 'oats': 17,
           'wheat': 19, 'grass_ley': 25, 'fallow': 0}             # kg N removed per t product (standard tables)
YIELD = {'pea': 3.4, 'potato': 30, 'carrot': 50, 'spinach': 24, 'turnip_rape': 1.5, 'barley': 4.0, 'oats': 4.0,
         'wheat': 5.0, 'grass_ley': 6.0, 'fallow': 0}             # typical t/ha (survey medians for contract crops)
VARIANTS = {
    # name: (L_m, erosion factors on, N-surplus on, p-test exponent, extra)
    'primary':    dict(L=560, ero=True,  surplus=True,  pexp=0.5, attrs=True),
    'no_crop':    dict(L=560, ero=False, surplus=False, pexp=0.5, attrs=True),
    'strong_crop': dict(L=560, ero=True, surplus=True, pexp=0.5, attrs=True, strong=True),
    'L300':       dict(L=300, ero=True,  surplus=True,  pexp=0.5, attrs=True),
    'L1000':      dict(L=1000, ero=True, surplus=True,  pexp=0.5, attrs=True),
    'area_only':  dict(L=1e12, ero=False, surplus=False, pexp=0.0, attrs=False),
}
V = sys.argv[1] if len(sys.argv) > 1 else 'primary'
cfg = VARIANTS[V]
ERO = {'potato': 1.6, 'carrot': 1.6, 'spinach': 1.3, 'grass_ley': 0.5, 'fallow': 0.6}
if cfg.get('strong'):
    ERO = {'potato': 2.5, 'carrot': 2.5, 'spinach': 2.0, 'pea': 1.3, 'turnip_rape': 1.3, 'grass_ley': 0.4, 'fallow': 0.5}

# ---------------------------------------------------------------- data
par = {r["parcel_id"]: r for r in rd(DATA / "01_master" / "parcels.csv")}
cat = {r["catchment_id"]: r for r in rd(DATA / "06_nature" / "catchments.csv")}
hist = [r for r in rd(DATA / "03_farming" / "parcel_crop_history_and_plan.csv") if 2019 <= int(r["year"]) <= 2025]
mon = rd(DATA / "06_nature" / "monitored_catchment_loads.csv")
log = []   # data corrections, written to corrections_<V>.csv

# farm-reported N (FI survey) and SE grower N; implausible values replaced by the crop norm (logged)
fs_n = {}
for r in rd(DATA / "03_farming" / "farm_survey_fi.csv"):
    n = float(r["n_mineral_kg_ha"]) + float(r["n_manure_kg_ha"]); y = float(r["yield_t_ha"])
    key = (r["farm_id"], r["crop"], int(r["year"]))
    if n > 3 * MGMT_N[r["crop"]] + 50:
        log.append(dict(source="farm_survey_fi", record=r["survey_id"], field="n_mineral_kg_ha", value=r["n_mineral_kg_ha"],
                        action="replaced by crop norm", reason="> 3x crop N norm + 50 (implausible; likely unit/decimal error)"))
        n = MGMT_N[r["crop"]]
    if y > 3 * YIELD[r["crop"]]:
        log.append(dict(source="farm_survey_fi", record=r["survey_id"], field="yield_t_ha", value=r["yield_t_ha"],
                        action="replaced by typical yield", reason="> 3x typical yield (implausible)"))
        y = YIELD[r["crop"]]
    fs_n[key] = (n, y)
for r in rd(DATA / "03_farming" / "foodhills_odlingsdata_se.csv", ";"):
    a = float(r["areal_ha"]); y = float(r["levererad_mängd_ton"]) / a if a > 0 else YIELD['pea']
    fs_n[(r["odlar_id"], "pea", int(r["skördeår"]))] = (float(r["kvävegiva_kg_ha"]), min(y, 3 * YIELD['pea']))

# rainfall: nearest grid cell, annual precip of year y relative to region-year mean (temporal part -> s_{r,y})
cells = {r["cell_id"]: r for r in rd(DATA / "01_master" / "climate_grid_cells.csv")}
prec = collections.defaultdict(float)
import csv
with open(DATA / "04_climate" / "weather_monthly_1991_2060.csv", newline="") as f:
    for r in csv.DictReader(f):
        if r["scenario"] == "historical" and 2019 <= int(r["year"]) <= 2025:
            prec[(r["cell_id"], int(r["year"]))] += float(r["precip_mm"])
def nearest(lat, lon, region):
    best = None
    for c in cells.values():
        if c["region"] != region:
            continue
        d = (float(c["lat"]) - lat) ** 2 + ((float(c["lon"]) - lon) * math.cos(math.radians(lat))) ** 2
        if best is None or d < best[0]:
            best = (d, c["cell_id"])
    return best[1]
reg_year_prec = collections.defaultdict(list)
for (cid, y), v in prec.items():
    reg_year_prec[(cells[cid]["region"], y)].append(v)
reg_year_prec = {k: sum(v) / len(v) for k, v in reg_year_prec.items()}

# parcel lat/lon are reliable (registry has swapped coords, parcels.csv does not); assign cell once
pcell = {}
for pid, p in par.items():
    region = cat[p["catchment_id"]]["region"]
    pcell[pid] = nearest(float(p["lat"]), float(p["lon"]), region)

# soil-P test: missing (18 %) -> median of same catchment x soil class, else region median (logged as imputation count)
pt_groups = collections.defaultdict(list)
for p in par.values():
    if p["p_test_mgl_latest"]:
        pt_groups[(p["catchment_id"], p["soil_class_soilmap"])].append(float(p["p_test_mgl_latest"]))
        pt_groups[cat[p["catchment_id"]]["region"]].append(float(p["p_test_mgl_latest"]))
PT_REF = 14.0
n_imp = 0
def ptest(p):
    global n_imp
    if p["p_test_mgl_latest"]:
        return float(p["p_test_mgl_latest"])
    n_imp += 1
    g = pt_groups.get((p["catchment_id"], p["soil_class_soilmap"]))
    return median(g) if g and len(g) >= 5 else median(pt_groups[cat[p["catchment_id"]]["region"]])

PT = {pid: ptest(p) for pid, p in par.items()}

def idx(pid, crop, catch, year):
    p = par[pid]; a = cfg['attrs']
    region = cat[p["catchment_id"]]["region"]
    rain = prec[(pcell[pid], year)] / reg_year_prec[(region, year)] if a else 1.0
    clay = float(p["clay_pct_soilmap"]); slope = float(p["slope_pct"]); soil = p["soil_class_soilmap"]
    # ---- P
    fp = (PT[pid] / PT_REF) ** cfg['pexp']
    if a:
        fp *= (0.7 + 0.3 * clay / 25.0) * (1 + 0.08 * slope) / (1 + 0.08 * 2.1)
        fp *= 0.75 if p["buffer_strip"] == "True" else 1.0
        fp *= 0.85 if catch == "True" else 1.0
        fp *= 1.15 if p["drainage"] == "open_ditch" else 1.0
        fp *= rain
    if cfg['ero']:
        fp *= ERO.get(crop, 1.0)
    # ---- N
    fn = 1.0
    if cfg['surplus']:
        n_app, yld = fs_n.get((p["farm_id"], crop, year), (MGMT_N[crop], YIELD[crop]))
        surplus = n_app - yld * N_PER_T[crop]
        k = 0.5 if cfg.get('strong') else 0.25
        fn = (8.0 + k * max(surplus, 0.0)) / 13.0
    if a:
        fn *= 0.7 if catch == "True" else 1.0
        fn *= {'sand': 1.3, 'fine_sand': 1.2, 'organic': 1.4, 'silt': 1.0, 'clay': 0.85}[soil]
        fn *= 1.1 if p["drainage"] == "subsurface" else 1.0
        fn *= rain
    deliv = math.exp(-float(p["dist_to_water_m"]) / cfg['L'])
    return fp * deliv, fn * deliv

# ---------------------------------------------------------------- aggregate per catchment-year
F = collections.defaultdict(lambda: [0.0, 0.0])      # all contract-farm parcels: sum area*idx*deliv
A = collections.defaultdict(float)                   # contract-farm area
AP = collections.defaultdict(lambda: [0.0, 0.0, 0.0])  # Apetit-crop parcels: P, N, area
parcel_out = []
for r in hist:
    pid = r["parcel_id"]; p = par[pid]; c = p["catchment_id"]; y = int(r["year"]); a = float(p["area_ha"])
    ip, inn = idx(pid, r["crop"], r["catch_crop"], y)
    F[(c, y)][0] += a * ip; F[(c, y)][1] += a * inn; A[(c, y)] += a
    if r["crop"] in APETIT_CROPS:
        AP[(c, y)][0] += a * ip; AP[(c, y)][1] += a * inn; AP[(c, y)][2] += a
        if y == 2025:
            parcel_out.append((pid, c, r["crop"], a, ip, inn))

def ibar(c, y, j):
    region = cat[c]["region"]
    rs = [(F[(cc, y)][j], A[(cc, y)]) for cc in cat if cat[cc]["region"] == region]
    rmean = sum(x for x, _ in rs) / sum(a for _, a in rs)
    w = A[(c, y)] / (A[(c, y)] + 500.0)
    own = F[(c, y)][j] / A[(c, y)] if A[(c, y)] > 0 else rmean
    return w * own + (1 - w) * rmean

def field_term(c, y, j):
    nc = float(cat[c]["field_area_total_ha"]) - A[(c, y)]
    return F[(c, y)][j] + max(nc, 0.0) * ibar(c, y, j)

# ---------------------------------------------------------------- calibration
cal = {}
for j, col in ((0, "total_p_load_kg"), (1, "total_n_load_kg")):
    rows = []
    for m in mon:
        c = m["catchment_id"]; y = int(m["year"]); ret = float(cat[c]["nutrient_retention_frac_estimate"])
        rows.append((c, y, cat[c]["region"], float(m[col]) / (1 - ret), field_term(c, y, j), float(cat[c]["catchment_area_km2"])))
    # step 1: pooled s and bg (relative-error weights) -> bg
    def fit2(rr):
        w = [1 / r[3] ** 2 for r in rr]
        s11 = sum(wi * r[4] ** 2 for wi, r in zip(w, rr)); s22 = sum(wi * r[5] ** 2 for wi, r in zip(w, rr))
        s12 = sum(wi * r[4] * r[5] for wi, r in zip(w, rr))
        t1 = sum(wi * r[4] * r[3] for wi, r in zip(w, rr)); t2 = sum(wi * r[5] * r[3] for wi, r in zip(w, rr))
        det = s11 * s22 - s12 ** 2
        return (t1 * s22 - t2 * s12) / det, (s11 * t2 - s12 * t1) / det
    s_pool, bg = fit2(rows)
    # step 2: region-year scale with bg fixed
    s_ry = {}
    for region in ("FI_SW", "SE_SKANE"):
        for y in range(2019, 2026):
            rr = [r for r in rows if r[2] == region and r[1] == y]
            w = [1 / r[3] ** 2 for r in rr]
            s_ry[(region, y)] = sum(wi * r[4] * (r[3] - bg * r[5]) for wi, r in zip(w, rr)) / sum(wi * r[4] ** 2 for wi, r in zip(w, rr))
    res = [(r[3] - s_ry[(r[2], r[1])] * r[4] - bg * r[5]) / r[3] for r in rows]
    # leave-one-catchment-out check of the field term: predict catchment's 2025 load without it
    loo = []
    for c in sorted({r[0] for r in rows}):
        rr = [r for r in rows if r[0] != c]
        s_p, b_p = fit2(rr)
        r25 = [r for r in rows if r[0] == c and r[1] == 2025][0]
        loo.append(abs(math.log10((s_p * r25[4] + b_p * r25[5]) / r25[3])))
    cal[j] = dict(s_pool=s_pool, bg=bg, s_ry=s_ry, rel_resid_sd=math.sqrt(sum(x * x for x in res) / len(res)),
                  loo_mae_log10=sum(loo) / len(loo))
    nm = "P" if j == 0 else "N"
    print(f"[{V}] {nm}: s_pool={s_pool:.4g} bg={bg:.4g} kg/km2  s_2025 FI={s_ry[('FI_SW', 2025)]:.4g} SE={s_ry[('SE_SKANE', 2025)]:.4g}"
          f"  rel.resid.sd={cal[j]['rel_resid_sd']:.3f}  LOO-catchment MAE log10(total load 2025)={cal[j]['loo_mae_log10']:.4f}")

# ---------------------------------------------------------------- 2025 estimate + priority
out = []
for c, k in cat.items():
    ret = float(k["nutrient_retention_frac_estimate"]); region = k["region"]
    p = cal[0]["s_ry"][(region, 2025)] * (1 - ret) * AP[(c, 2025)][0]
    n = cal[1]["s_ry"][(region, 2025)] * (1 - ret) * AP[(c, 2025)][1]
    out.append(dict(catchment_id=c, region=region, apetit_p_to_water_kg=round(p, 2), apetit_n_to_water_kg=round(n, 1),
                    apetit_area_ha=round(AP[(c, 2025)][2], 1), state=k["ecological_status_class"], p_sens=float(k["p_sensitivity"])))
act = [o for o in out if o["apetit_p_to_water_kg"] > 1.0]
mP = median([o["apetit_p_to_water_kg"] for o in act]); mN = median([o["apetit_n_to_water_kg"] for o in act])
for o in out:
    o["priority_score"] = round((o["apetit_p_to_water_kg"] / mP + 0.5 * o["apetit_n_to_water_kg"] / mN) * STATE_WEIGHT[o["state"]] * o["p_sens"], 4)
order = sorted(out, key=lambda o: -o["priority_score"])
for i, o in enumerate(order):
    o["priority_rank"] = i + 1
cols = ["catchment_id", "region", "apetit_p_to_water_kg", "apetit_n_to_water_kg", "priority_rank"]
write_csv(WORK / f"pred_{V}.csv", out, cols)
if V == "primary":
    write_csv(WORK / "D1_catchment_priority_submission.csv", out, cols)
    write_csv(WORK / "detail_primary.csv", out, cols[:4] + ["apetit_area_ha", "state", "p_sens", "priority_score", "priority_rank"])
    write_csv(WORK / "corrections_primary.csv", log, ["source", "record", "field", "value", "action", "reason"])
    # parcel-level 2025 hot spots: share of Apetit delivered P from the top-10 % parcels
    pp = sorted([(cal[0]["s_ry"][(cat[c]["region"], 2025)] * (1 - float(cat[c]["nutrient_retention_frac_estimate"])) * a * ip, pid, c, crop, a)
                 for pid, c, crop, a, ip, inn in parcel_out], reverse=True)
    tot = sum(x[0] for x in pp); k10 = len(pp) // 10
    print(f"parcel hot spots: top 10 % of Apetit parcels ({k10} of {len(pp)}, {sum(x[4] for x in pp[:k10]):.0f} of {sum(x[4] for x in pp):.0f} ha) "
          f"deliver {100 * sum(x[0] for x in pp[:k10]) / tot:.1f} % of Apetit P to water")
    write_csv(WORK / "parcels_2025_primary.csv",
              [dict(parcel_id=x[1], catchment_id=x[2], crop=x[3], area_ha=x[4], p_to_water_kg=round(x[0], 3)) for x in pp],
              ["parcel_id", "catchment_id", "crop", "area_ha", "p_to_water_kg"])
import json
json.dump({("P" if j == 0 else "N"): dict(s_pool=round(v["s_pool"], 4), bg_kg_km2=round(v["bg"], 3),
           s_2025_FI=round(v["s_ry"][("FI_SW", 2025)], 4), s_2025_SE=round(v["s_ry"][("SE_SKANE", 2025)], 4),
           rel_resid_sd=round(v["rel_resid_sd"], 4), loo_mae_log10_total_load_2025=round(v["loo_mae_log10"], 4))
           for j, v in cal.items()} | dict(L_m=cfg["L"], corrections=len(log), ptest_imputed=n_imp),
          open(WORK / f"cal_{V}.json", "w"), indent=1)
print(f"[{V}] corrections logged: {len(log)}; soil-P tests imputed: {n_imp}")
print(f"[{V}] total Apetit P to water 2025 = {sum(o['apetit_p_to_water_kg'] for o in out):.0f} kg, N = {sum(o['apetit_n_to_water_kg'] for o in out):.0f} kg; top-5: {[o['catchment_id'] for o in order[:5]]}")
