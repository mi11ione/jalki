"""Farm layer: parcel organic-soil posterior + cradle-to-gate footprint by farm x crop x year.
Soil evidence: soil map, clay estimate, the farm's other parcels, farmers' 'Organic soil' reports, and the public 2023-24
soil_misreport labels (dev data, published with the task). Labels of any year can be excluded for held-out tests."""
from __future__ import annotations
import itertools
import numpy as np
import pandas as pd
from clean import F, log
from ccn_tools.farm_calculator import farm_footprint_per_ha

CROPS = ["pea", "potato", "carrot", "spinach", "turnip_rape"]
CROP_MAT = {"M100": "turnip_rape", "M110": "pea", "M111": "potato", "M112": "carrot", "M113": "spinach"}
E = F.FARM_EF
N2O = E["n2o_n_to_n2o"] * E["n2o_gwp"]
ORG_KG_HA = E["org_soil_co2_t_ha"] * 1000 + E["org_soil_n2o_n_kg_ha"] * N2O
DELIVERED_SHARE = 0.98     # median delivered/(area x yield) printed by s04; only used to turn deliveries into yield


def contract_parcels(raw):
    ch, pc = raw["crop_history"], raw["parcels"]
    return ch[ch.crop.isin(CROPS) & ch.farm_id.str.startswith("F")].merge(pc, on=["parcel_id", "farm_id"])


def solve_labels(raw, lab, years):
    """Exact parcel soils where a label's share has one subset-sum solution; parcels >=30% of a no-label Mineral row are mineral."""
    sv, m = raw["farm_survey"], contract_parcels(raw)
    sl = lab[(lab.issue_type == "soil_misreport") & lab.year.isin(years)].copy()
    sl["survey_id"] = sl.record_key.str.split(":").str[1]
    sl["share"] = sl.true_value.str.extract(r"([0-9.]+)").astype(float)
    sl = sl.merge(sv[["survey_id", "farm_id", "crop"]], on="survey_id")
    known = {}
    for _, r in sl.iterrows():
        g = m[(m.farm_id == r.farm_id) & (m.crop == r.crop) & (m.year == r.year)]
        ar, ids = g.area_ha.values, g.parcel_id.tolist()
        sols = [c for c in itertools.product([0, 1], repeat=len(ids)) if abs(np.dot(c, ar) / ar.sum() - r.share) <= 0.006]
        if len(sols) == 1:
            known.update(dict(zip(ids, sols[0])))
    t = sv[sv.year.isin(years) & (sv.soil_type_reported == "Mineral soil") & ~sv.survey_id.isin(sl.survey_id)]
    k = t.merge(m[["farm_id", "crop", "year", "parcel_id", "area_ha"]], on=["farm_id", "crop", "year"], suffixes=("_s", ""))
    k["sh"] = k.area_ha / k.groupby("survey_id").area_ha.transform("sum")
    for pid in k[k.sh >= 0.3].parcel_id:
        known.setdefault(pid, 0)
    return known


def reported_parcels(raw):
    """Parcels on rows the farmer reported as organic. Those rows are a positive signal for the parcels on them."""
    sv, m = raw["farm_survey"], contract_parcels(raw)
    r = sv[sv.soil_type_reported == "Organic soil"].merge(m[["farm_id", "crop", "year", "parcel_id"]], on=["farm_id", "crop", "year"])
    return set(r.parcel_id)


def features(raw, known):
    p = raw["parcels"]
    p = p[p.farm_id.str.startswith("F")].copy()
    rep = reported_parcels(raw)
    p["map_org"] = (p.soil_class_soilmap == "organic").astype(float)
    p["rep"] = p.parcel_id.isin(rep).astype(float)
    p["ev"] = p.parcel_id.map(known).fillna(np.maximum(p.map_org, p.rep * 0.5))
    tot = p.groupby("farm_id").area_ha.transform("sum")
    org = (p.ev * p.area_ha).groupby(p.farm_id).transform("sum")
    p["other"] = ((org - p.ev * p.area_ha) / (tot - p.area_ha).clip(lower=0.1)).clip(0, 1)
    consistent = np.where(p.soil_class_soilmap == "clay", p.clay_pct_soilmap >= 30, p.clay_pct_soilmap < 30)
    p["clay_off"] = (~consistent & (p.map_org == 0)).astype(float)
    p["low_clay"] = (p.clay_pct_soilmap <= 30).astype(float)
    return p


def design(p):
    return np.c_[np.ones(len(p)), p.map_org, p.other, p.map_org * p.other, p.low_clay, p.rep]


def fit_logit(X, y, ridge=1.0):
    b = np.zeros(X.shape[1])
    for _ in range(50):
        q = 1 / (1 + np.exp(-X @ b))
        W = q * (1 - q) + 1e-6
        H = X.T @ (X * W[:, None]) + ridge * np.eye(X.shape[1])
        b = b + np.linalg.solve(H, X.T @ (y - q) - ridge * b)
    return b


P_MAP_ORG = 0.90      # solved parcels: map-organic parcels that are organic (printed by s05: 39 of 43)
P_CLUSTER = 0.40      # map-mineral parcel on a farm whose other parcels are >=40 % organic; below the biased 14/24 in s05


def soil_posterior(raw, lab, years, delta=0.0, mode="rate", b_low=0.0):
    """mode 'logit': delta is a logit offset for unknown parcels (known parcels over-sample organic farms).
    mode 'rate': three-cell table; b_low = P(organic | map mineral, no cluster), the only fitted number (s08)."""
    known = solve_labels(raw, lab, years)
    p = features(raw, known)
    tr = p[p.parcel_id.isin(known)]
    b = fit_logit(design(tr), tr.parcel_id.map(known).values.astype(float))
    p["logit"] = design(p) @ b
    if mode == "logit":
        p["p_org"] = 1 / (1 + np.exp(-(p.logit + delta)))
    else:
        p["p_org"] = np.where(p.map_org == 1, P_MAP_ORG, np.where(p.other >= 0.4, P_CLUSTER, b_low))
        p.loc[p.rep == 1, "p_org"] = np.maximum(p.loc[p.rep == 1, "p_org"], np.where(p.loc[p.rep == 1, "map_org"] == 1, 0.98, 0.5))
    isk = p.parcel_id.isin(known)
    p.loc[isk, "p_org"] = p.parcel_id.map(known)
    p["known"] = isk
    return p.set_index("parcel_id"), b, known


def clean_survey(sv, registry):
    s = sv.copy()
    orgc = s.farm_id.map(registry.set_index("farm_id").organic_certified).fillna(False)
    med = s.groupby(["crop", "year"]).n_mineral_kg_ha.transform("median")
    fm = s.groupby(["farm_id", "crop"]).n_mineral_kg_ha.transform("median")
    ref = np.where(fm > 0, fm, med)
    hi = (s.n_mineral_kg_ha > 4 * med) & (s.n_mineral_kg_ha > 200)
    lo = (s.n_mineral_kg_ha > 0) & (s.n_mineral_kg_ha < 0.2 * ref) & (ref > 20) & ~orgc
    for i in s.index[hi | lo]:
        old = s.at[i, "n_mineral_kg_ha"]
        new = old / 10 if hi[i] else old * 10
        s.at[i, "n_mineral_kg_ha"] = new
        log("farm_survey", f"farm_survey:{s.at[i, 'survey_id']}", s.at[i, "year"], "decimal_shift", "n_mineral_kg_ha", old, new, "N rate 10x off the farm/crop norm")
    ymed = s.groupby("crop").yield_t_ha.transform("median")
    for i in s.index[s.yield_t_ha > 3 * ymed]:
        old = s.at[i, "yield_t_ha"]
        s.at[i, "yield_t_ha"] = old / 10
        log("farm_survey", f"farm_survey:{s.at[i, 'survey_id']}", s.at[i, "year"], "outlier_implausible", "yield_t_ha", old, old / 10, "yield >3x crop median; 10x keying")
    return s


def comps(df):
    """FLAG and non-FLAG kg CO2e/ha on mineral soil. Same formulas as farm_calculator, split by METHODOLOGY s5 FLAG definition."""
    nmin, nman, P, y = df.n_mineral_kg_ha.values, df.n_manure_kg_ha.values, df.p_kg_ha.values, df.yield_t_ha.values
    res = df.crop.map(F.RESIDUE_N_PER_T).values * y
    fert = df.lowcarbon.values * E["fert_n_prod_lowcarbon"] + (1 - df.lowcarbon.values) * E["fert_n_prod"]
    c_fert = nmin * fert + P * E["fert_p_prod"] + P * 2.2 * E["fert_k_prod"]
    c_dir = (nmin * E["ef1_synthetic"] + (nman + res) * E["ef1_organic"]) * N2O
    c_ind = ((nmin * E["frac_gasf"] + nman * E["frac_gasm"]) * E["ef4_n2o_n"] + (nmin + nman + res) * E["frac_leach"] * E["ef5_n2o_n"]) * N2O
    c_dsl = df.diesel_l_ha.values * (E["diesel_ttw"] + E["diesel_wtt"])
    c_lime = df.lime_t_ha.values * E["lime"] * 1000
    c_spr = df.sprays.values * E["spray_pass"]
    kwh = df.crop.map({c: v["kwh_t"] for c, v in F.MGMT_NORMS.items()}).values * y + 180.0 * df.irr.values
    return c_dir + c_ind + c_lime, c_fert + c_dsl + c_spr + kwh * 0.03


def farm_table(raw, erp, sv, post, year):
    """One row per FI farm x crop with deliveries in `year`: area, kg, FLAG/non-FLAG mineral and organic tCO2e."""
    m = contract_parcels(raw)
    m = m[m.year == year].copy()
    m["p"] = m.parcel_id.map(post.p_org).fillna(0.0)
    m["org"] = m.area_ha * m.p
    a = m.groupby(["farm_id", "crop"]).agg(area=("area_ha", "sum"), org_area=("org", "sum")).reset_index()
    d = erp[erp.material_id.isin(CROP_MAT) & (erp.year == year)].copy()
    d["crop"] = d.material_id.map(CROP_MAT)
    d = d.groupby(["supplier_id", "crop"]).qty_kg.sum().reset_index().rename(columns={"supplier_id": "farm_id", "qty_kg": "kg"})
    t = a.merge(d, on=["farm_id", "crop"], how="outer")
    s = sv[sv.year == year].copy()
    s["lowcarbon"] = s.fertiliser_product.fillna("").str.contains("low-carbon").astype(float)
    s["irr"] = s.irrigated.fillna(False).astype(float)
    cols = ["n_mineral_kg_ha", "n_manure_kg_ha", "p_kg_ha", "diesel_l_ha", "lime_t_ha", "sprays", "lowcarbon", "irr"]
    t = t.merge(s[["farm_id", "crop", "survey_id"] + cols], on=["farm_id", "crop"], how="left")
    t["respondent"] = t.survey_id.notna()
    for c in cols:
        t[c] = t[c].fillna(t.crop.map(s.groupby("crop")[c].mean()))
    t["yield_t_ha"] = t.kg / 1000 / t.area / DELIVERED_SHARE
    fl, nf = comps(t)
    t["min_share"] = 1.0
    t["t_flag_min"] = fl * t.area / 1000
    t["t_nonflag"] = nf * t.area / 1000
    t["t_org"] = t.org_area * ORG_KG_HA / 1000
    t["tco2e"] = t.t_flag_min + t.t_nonflag + t.t_org
    t["year"] = year
    t["region"] = "FI_SW"
    return t


def count_ge30(raw, post, year):
    """Expected number of FI farms with >=30 % of contract-crop area organic, from parcel posteriors (exact DP on 0.1 % bins)."""
    m = contract_parcels(raw)
    m = m[m.year == year].copy()
    m["p"] = m.parcel_id.map(post.p_org).fillna(0.0)
    tot, n_exp, hard = 0.0, 0, 0
    per = {}
    for f, g in m.groupby("farm_id"):
        ar = g.groupby("parcel_id").agg(a=("area_ha", "sum"), p=("p", "first"))
        w = np.rint(1000 * ar.a.values / ar.a.sum()).astype(int)
        dist = np.zeros(w.sum() + 1); dist[0] = 1
        for wi, pi in zip(w, ar.p.values):
            nd = dist * (1 - pi)
            nd[wi:] += dist[:len(dist) - wi] * pi
            dist = nd
        pr = dist[int(np.ceil(0.3 * w.sum())):].sum()
        per[f] = pr
        tot += pr
        hard += int((ar.a * ar.p).sum() / ar.a.sum() >= 0.3)
    return tot, hard, per
