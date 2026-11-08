"""D1 independent attempt (d1-nature-b): export-coefficient + soil-erosion index per parcel,
calibrated on the 15 monitored catchments, separating natural background and non-contract farmland.

  python stages/d1_model_b/model.py [variant]

Structure (per nutrient X in {P, N}, catchment c, year y):
  monitored_load[c,y] = (1-ret_c) * ( s * SUM_{parcels i of contract farms in c} I_i,y            # contract farms, every crop
                                      + s*kappa * (F_c - A_c) * mean_index_c,y                    # non-contract farmland
                                      + b * nonfield_km2_c )                                       # natural background
  -> (s, s*kappa, b) by weighted least squares on relative error (105 catchment-years).
  Apetit load[c] = (1-ret_c) * s * SUM_{parcels growing the farm's contract crop in 2025} I_i,2025
Indices I are area x literature-shaped multipliers (below); only the three linear terms are fitted.
Model variant choice uses leave-one-catchment-out (LOCO) error on the monitored loads, NOT the dev key.
"""
import sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collections import defaultdict
from lib import (read, catchments, monitored, lstsq, weather_annual, nearest_cell, load_dev, score_d1,
                 priority_ranks, write_submission, median, HERE)
import importlib.util
from lib import ROOT
_spec = importlib.util.spec_from_file_location("ccn_factors", ROOT / "tools/ccn_tools/factors.py")  # stdlib-only module
_F = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_F)
MGMT_NORMS, RESIDUE_N_PER_T = _F.MGMT_NORMS, _F.RESIDUE_N_PER_T

VARIANT = sys.argv[1] if len(sys.argv) > 1 else "full"
FLAGS = set(VARIANT.split("+"))   # e.g. full+k1+noC ; k1 = kappa fixed at 1 (non-contract farmland = contract-farm mean)
YEARS = list(range(2019, 2026))

# ---------------------------------------------------------------- a-priori multipliers (literature-shaped, not fitted)
# crop cover factor for erosion (C): row crops > spring cereals/pea/rape > ley; fallow = green fallow
C_CROP = {"potato": 1.8, "carrot": 1.8, "spinach": 1.5, "pea": 1.0, "turnip_rape": 1.0, "barley": 1.0,
          "oats": 1.0, "wheat": 1.0, "grass_ley": 0.25, "fallow": 0.4}
# soil erodibility (K) relative; Finnish clays and silts erode most, organic least
K_SOIL = {"clay": 1.0, "silt": 1.1, "fine_sand": 0.7, "sand": 0.4, "organic": 0.3}
# N leaching susceptibility by soil (coarse soils leach, organic soils mineralise)
LEACH_SOIL = {"clay": 0.8, "silt": 1.0, "fine_sand": 1.2, "sand": 1.5, "organic": 1.6}
# harvested N removal, kg N per t of harvested product (typical table values)
N_REMOVAL_PER_T = {"pea": 10.0, "potato": 3.5, "carrot": 1.5, "spinach": 4.0, "turnip_rape": 33.0,
                   "barley": 17.0, "oats": 16.0, "wheat": 20.0, "grass_ley": 25.0, "fallow": 0.0}
TYPICAL_YIELD = {"pea": 3.3, "potato": 30.0, "carrot": 50.0, "spinach": 25.0, "turnip_rape": 1.4,
                 "barley": 4.0, "oats": 3.8, "wheat": 4.5, "grass_ley": 6.0, "fallow": 0.0}
CATCH_P, CATCH_N = 0.8, 0.7          # catch crop: erosion x0.8, N leaching x0.7
BUFFER_PP = 0.7                       # buffer strip traps particulate P
DRAIN = {"open_ditch": 1.15, "subsurface": 0.95}
LAMBDA_M = 400.0                      # delivery decay length; DR = 0.35 + 0.65*exp(-d/LAMBDA)
RAIN_EXP = 0.0                        # monitored loads show ~0 elasticity to annual rain (calib0.py)


_CACHE = {}


def load_inputs():
    if "x" not in _CACHE:
        _CACHE["x"] = _load_inputs()
    return _CACHE["x"]


def _load_inputs():
    cat = catchments(); mon = monitored()
    par = {r["parcel_id"]: r for r in read("data/01_master/parcels.csv")}
    reg = {r["farm_id"]: r for r in read("data/01_master/farm_registry.csv")}
    ch = defaultdict(dict)
    for r in read("data/03_farming/parcel_crop_history_and_plan.csv"):
        y = int(r["year"])
        if 2019 <= y <= 2025:
            ch[r["parcel_id"]][y] = (r["crop"], r["catch_crop"] == "True")
    # farm x crop x year N (FI survey; SE grower file is peas only)
    nfarm = {}
    for r in read("data/03_farming/farm_survey_fi.csv"):
        n = float(r["n_mineral_kg_ha"]) + float(r["n_manure_kg_ha"])
        yl = float(r["yield_t_ha"])
        if n < 400:
            nfarm[(r["farm_id"], r["crop"], int(r["year"]))] = (n, yl)
    for r in read("data/03_farming/foodhills_odlingsdata_se.csv", ";"):
        a = float(r["areal_ha"].replace(",", ".")); t = float(r["levererad_mängd_ton"].replace(",", "."))
        nfarm[(r["odlar_id"], "pea", int(r["skördeår"]))] = (float(r["kvävegiva_kg_ha"]), t / a if a > 0 else 3.3)
    # P test imputation: farm median, else soil-class median
    pt_farm = defaultdict(list); pt_soil = defaultdict(list)
    for p in par.values():
        if p["p_test_mgl_latest"] != "":
            pt_farm[p["farm_id"]].append(float(p["p_test_mgl_latest"])); pt_soil[p["soil_class_soilmap"]].append(float(p["p_test_mgl_latest"]))
    for p in par.values():
        if p["p_test_mgl_latest"] != "":
            p["ptest"] = float(p["p_test_mgl_latest"])
        else:
            p["ptest"] = median(pt_farm[p["farm_id"]]) if pt_farm[p["farm_id"]] else median(pt_soil[p["soil_class_soilmap"]])
    W, cells = weather_annual()
    cellcache = {}
    for p in par.values():
        k = (round(float(p["lat"]), 2), round(float(p["lon"]), 2))
        if k not in cellcache:
            cellcache[k] = nearest_cell(cells, *k)
        p["cell"] = cellcache[k]
    return cat, mon, par, reg, ch, nfarm, W


def n_rate(nfarm, farm, crop, y):
    v = nfarm.get((farm, crop, y))
    if v:
        return v
    return (MGMT_NORMS[crop]["n"], TYPICAL_YIELD[crop])


def indices(p, crop, cc, y, nfarm, W, variant):
    a = float(p["area_ha"])
    if "area" in FLAGS:
        return a, a
    soil = p["soil_class_soilmap"]; slope = float(p["slope_pct"]); clay = float(p["clay_pct_soilmap"])
    d = float(p["dist_to_water_m"])
    rain = W[(p["cell"], y)]["precip"] / 600.0
    rf = rain ** RAIN_EXP
    DR = 1.0 if "noDR" in FLAGS else 0.35 + 0.65 * math.exp(-d / LAMBDA_M)
    # --- P: particulate (erosion) + dissolved
    LS = 1.0 if "noLS" in FLAGS else (max(slope, 0.3) / 1.7) ** 0.7
    K = 1.0 if "noK" in FLAGS else K_SOIL[soil] * (0.6 + clay / 50.0)
    C = (1.0 if "noC" in FLAGS else C_CROP[crop]) * (CATCH_P if cc and "noCC" not in FLAGS else 1.0)
    erosion = rf * K * LS * C * (1.0 if "noDrain" in FLAGS else DRAIN[p["drainage"]])
    pt = 14.0 if "noPt" in FLAGS else p["ptest"]
    pp = erosion * (pt / 14.0) ** 0.3 * (BUFFER_PP if p["buffer_strip"] == "True" and "noBuf" not in FLAGS else 1.0)
    drp = rf * (pt / 14.0) * (0.5 if crop == "grass_ley" and "noC" not in FLAGS else 1.0)
    iP = a * DR * (0.75 * pp + 0.25 * drp)
    if "Parea" in FLAGS:
        iP = a
    # --- N: leaching from surplus
    n_app, yl = n_rate(nfarm, p["farm_id"], crop, y)
    removal = N_REMOVAL_PER_T[crop] * yl
    surplus = max(0.0, n_app + RESIDUE_N_PER_T[crop] * yl * 0.5 - removal)
    leach = LEACH_SOIL[soil] * (10.0 + 0.4 * surplus) * (CATCH_N if cc else 1.0) * rf
    iN = a * (0.6 + 0.4 * DR) * leach
    if "Narea" in FLAGS:
        iN = a
    return iP, iN


def build(variant):
    cat, mon, par, reg, ch, nfarm, W = load_inputs()
    farmI = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0])); farmA = defaultdict(float)
    contractI = defaultdict(lambda: [0.0, 0.0]); contractA = defaultdict(float)
    for pid, p in par.items():
        c = p["catchment_id"]; farmA[c] += float(p["area_ha"])
        ccs = reg[p["farm_id"]]["contract_crops"].split(";") if reg[p["farm_id"]]["contract_crops"] else []
        for y in YEARS:
            crop, cc = ch[pid][y]
            iP, iN = indices(p, crop, cc, y, nfarm, W, variant)
            farmI[c][y][0] += iP; farmI[c][y][1] += iN
            if y == 2025 and crop in ccs:
                contractI[c][0] += iP; contractI[c][1] += iN; contractA[c] += float(p["area_ha"])
    return cat, mon, farmI, farmA, contractI, contractA


def design(cat, farmI, farmA, c, y, j):
    k = cat[c]; F = float(k["field_area_total_ha"]); A = farmA[c]
    nonfield = float(k["catchment_area_km2"]) - F / 100.0
    I = farmI[c][y][j]
    mean_i = I / A if A > 0 else 1.0
    q = 1 - float(k["nutrient_retention_frac_estimate"])
    return [q * I, q * max(F - A, 0.0) * mean_i, q * nonfield]


def fit(cat, mon, farmI, farmA, j, exclude=()):
    """Returns (s, s*kappa, b). With flag k1, kappa is fixed at 1 and (s, b) are fitted."""
    X, Y = [], []
    for c in mon:
        if c in exclude:
            continue
        for y in YEARS:
            x = design(cat, farmI, farmA, c, y, j)
            X.append([x[0] + x[1], x[2]] if "k1" in FLAGS else x); Y.append(mon[c][y][j])
    co = lstsq(X, Y, [1 / v ** 2 for v in Y])
    return (co[0], co[0], co[1]) if "k1" in FLAGS else tuple(co)


def main():
    cat, mon, farmI, farmA, contractI, contractA = build(VARIANT)
    out = {"variant": VARIANT}
    coefs = {}
    for j, nut in ((0, "P"), (1, "N")):
        s, sk, b = fit(cat, mon, farmI, farmA, j)
        coefs[nut] = (s, sk, b)
        # in-sample and LOCO relative error on 7-year mean monitored loads
        ins, loco = [], []
        for c in mon:
            obs = sum(mon[c][y][j] for y in YEARS) / 7
            pr = sum(sum(w * x for w, x in zip((s, sk, b), design(cat, farmI, farmA, c, y, j))) for y in YEARS) / 7
            s2, sk2, b2 = fit(cat, mon, farmI, farmA, j, exclude=(c,))
            pl = sum(sum(w * x for w, x in zip((s2, sk2, b2), design(cat, farmI, farmA, c, y, j))) for y in YEARS) / 7
            ins.append(abs(math.log10(pr / obs))); loco.append(abs(math.log10(pl / obs)))
        kappa = sk / s if s else float("nan")
        # load split at monitored catchments (2025): contract farms / non-contract farmland / background
        split = [0.0, 0.0, 0.0]
        for c in mon:
            x = design(cat, farmI, farmA, c, 2025, j)
            for i in range(3):
                split[i] += (s, sk, b)[i] * x[i]
        tot = sum(split)
        out[nut] = dict(s=round(s, 5), kappa=round(kappa, 3), background_kg_per_km2=round(b, 2),
                        mae_log10_monitored_insample=round(sum(ins) / len(ins), 4),
                        mae_log10_monitored_LOCO=round(sum(loco) / len(loco), 4),
                        share_2025_contract_farms_all_crops=round(split[0] / tot, 3),
                        share_2025_noncontract_farmland=round(split[1] / tot, 3),
                        share_2025_background=round(split[2] / tot, 3))
    P = {c: (1 - float(cat[c]["nutrient_retention_frac_estimate"])) * coefs["P"][0] * contractI[c][0] for c in cat}
    N = {c: (1 - float(cat[c]["nutrient_retention_frac_estimate"])) * coefs["N"][0] * contractI[c][1] for c in cat}
    rk, pr = priority_ranks(cat, P, N)
    fn = HERE / f"D1_submission_{VARIANT}.csv"
    write_submission(fn, cat, P, N, rk)
    sub = {c: (round(P[c], 2), round(N[c], 1), rk[c]) for c in cat}
    out["dev"] = score_d1(sub, load_dev())
    out["totals_2025"] = dict(P_kg=round(sum(P.values())), N_kg=round(sum(N.values())), contract_ha=round(sum(contractA.values())))
    out["top5"] = sorted(cat, key=lambda c: rk[c])[:5]
    print(json.dumps(out, indent=1))
    with open(HERE / "devlog.txt", "a") as f:
        f.write(json.dumps({"variant": VARIANT, "dev": out["dev"], "P_loco": out["P"]["mae_log10_monitored_LOCO"],
                            "N_loco": out["N"]["mae_log10_monitored_LOCO"]}) + "\n")


if __name__ == "__main__":
    main()
