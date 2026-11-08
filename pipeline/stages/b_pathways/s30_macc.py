"""B2 MACC: every lever recomputed from the inventory, with overlaps removed, feasibility checked against what the data
shows, and analytic low/central/high bands (no Monte Carlo, per compute policy).
Run: python stages/b_pathways/s30_macc.py"""
from ccn_paths import PACKAGE, stage_dir
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import json
import numpy as np, pandas as pd
HERE = stage_dir("b_pathways")
import lib_clean as L
from ccn_tools import factors as F
pd.set_option("display.width", 240, "display.max_columns", 40, "display.max_rows", 200, "display.max_colwidth", 46)
pd.set_option("future.no_silent_downcasting", True)
OUT = HERE / "outputs"
R = json.load(open(OUT / "structure.json")); C = json.load(open(OUT / "checks.json")); J = json.load(open(OUT / "inventory_summary.json"))
lines = pd.read_csv(OUT / "inventory_lines_2021_2025.csv"); fl = pd.read_csv(OUT / "farm_lines.csv")
raw, T = L.load_clean()
lev = pd.read_csv(L.DATA / "data" / "05_scenarios" / "decarbonisation_levers.csv").set_index("lever_id")
lib = T["ef_library"].set_index("ef_id"); EF = lib.kgco2e_per_unit
q = lines[lines.year == 2025]
Pz, FH, K = R["pudasjarvi"], R["foodhills"], R["kantvik"]

# ---- test: the catalogue's indicative cost is straight-line (capex/life + opex)/design abatement
chk = lev[lev.abatement_tco2e_2030_design > 0].copy()
chk["recalc"] = (chk.capex_eur / chk.lifetime_yr + chk.opex_delta_eur_per_yr) / chk.abatement_tco2e_2030_design
d = (chk.recalc - chk.indicative_cost_eur_per_tco2e).abs()
print(f"catalogue cost formula reproduced on {int((d < 1).sum())} of {len(chk)} levers; max diff {d.max():.1f}; off: {chk[d >= 1][['recalc', 'indicative_cost_eur_per_tco2e']].round(1).to_dict('index')}")

def line(prefix, scope=None):
    m = q.line_item.str.startswith(prefix)
    if scope: m &= q.scope == scope
    return float(q[m].tco2e.sum())

# ---- peat: can contract crops move to mineral parcels on the same farm?
ch = raw["crop_history"].merge(raw["parcels"][["parcel_id", "area_ha", "soil_class_soilmap"]], on="parcel_id")
CONTRACT = ["pea", "potato", "carrot", "spinach", "turnip_rape"]
y = ch[ch.year == 2025]
peat_c = y[(y.soil_class_soilmap == "organic") & y.crop.isin(CONTRACT)].groupby("farm_id").area_ha.sum()
min_free = y[(y.soil_class_soilmap != "organic") & y.crop.isin(["barley", "oats", "wheat", "fallow"])].groupby("farm_id").area_ha.sum()
fr = pd.DataFrame(dict(peat=peat_c)).join(min_free.rename("free")).fillna(0)
fr["moved"] = np.minimum(fr.peat, fr.free * 0.5)    # ASSUMPTION: at most half a farm's mineral cereal/fallow area can take the swap, keeps rotation
feas = fr.moved.sum() / fr.peat.sum()
fr_all = np.minimum(fr.peat, fr.free).sum() / fr.peat.sum()
print(f"Peat parcels with contract crops 2025: {fr.peat.sum():.0f} ha on {len(fr)} farms; movable on same farm {feas * 100:.1f}% (half of free mineral area), {fr_all * 100:.1f}% (all of it)")
plan = ch[ch.crop.isin(CONTRACT) & (ch.soil_class_soilmap == "organic")].groupby("year").area_ha.sum()
print("Soil-map peat under contract crops by year:", plan.loc[2021:2031].round(0).to_dict())
rot = float(plan.loc[2027:2031].mean() / plan.loc[2025]); hist = float(plan.loc[2021:2025].mean() / plan.loc[2025])
print(f"Planned 2027-31 mean / 2025 = {rot:.3f}; 2021-25 mean / 2025 = {hist:.3f}")
# same fields, other crops: the drained parcel stays in cultivation after the swap
stay = y[y.soil_class_soilmap == "organic"].groupby("crop").area_ha.sum()
print(f"Soil-map peat under all crops 2025 {stay.sum():.0f} ha, of which contract crops {stay[stay.index.isin(CONTRACT)].sum():.0f} ha")
ys = pd.concat([L.clean_survey(raw)]).assign(org=lambda d: d.soil_type_reported.str.startswith("Organic"))
yl = ys[ys.year.between(2019, 2026)].groupby(["crop", "org"]).yield_t_ha.median().unstack()
print("Median reported yield by soil:\n", yl.round(2).to_string())

# ---- rapeseed
mats = {"M102": "EE", "M103": "LV", "M104": "LT", "M105": "SE", "M106": "DK", "M107": "PL", "M101": "FI"}
pur = T["purchases"]
rp = pur[pur.material_id.isin(mats)].groupby(["year", "material_id"]).qty_kg.sum().unstack(0) / 1000
r25 = q[q.material_id.isin(mats)].groupby("material_id").tco2e.sum()
eff = (r25 / rp[2025]).rename("kg_per_kg")
print(pd.concat([rp.round(0), eff.round(3)], axis=1).to_string())
print("origin shares by year:\n", (rp / rp.sum()).round(3).to_string())
hi_mats, lo_mats = ["M103", "M104", "M107"], ["M105", "M106"]
ef_hi = r25[hi_mats].sum() / rp[2025][hi_mats].sum(); ef_lo = r25[lo_mats].sum() / rp[2025][lo_mats].sum()
head = sum(rp.loc[m].max() - rp.loc[m, 2025] for m in lo_mats)
delta = ef_hi - ef_lo
need = lev.abatement_tco2e_2030_design["L14"] / delta
print(f"L14: high-EF origins {ef_hi:.3f}, SE+DK {ef_lo:.3f}, delta {delta:.3f} kg/kg. SE+DK 2025 {rp[2025][lo_mats].sum():.0f} t, max-year headroom {head:.0f} t -> {head * delta:.0f} t CO2e; design {lev.abatement_tco2e_2030_design['L14']} t needs {need:.0f} t switched = {need / rp[2025][lo_mats].sum() * 100:.0f}% more than 2025 SE+DK purchases")
bought_t = float(r25.sum()); flag_b = float(q[q.material_id.isin(mats)].flag_t.sum()); non_b = bought_t - flag_b
f = fl[(fl.year == 2025) & (fl.crop == "turnip_rape")]
conv_fert = float((f.ha * f.n_mineral_kg_ha * 3.7 / 1000).sum())
nonflag_parts = conv_fert + f.t_fert_pk.sum() + f.t_diesel.sum() + f.t_spray.sum() + f.t_elec.sum()
fert_frac = conv_fert / nonflag_parts
sup = raw["suppliers"]; s_stat = sup[sup.material_id.isin(mats)]
kg_s = pur[(pur.year == 2025) & pur.material_id.isin(mats)].groupby("supplier_id").qty_kg.sum()
s_stat = s_stat.drop_duplicates("supplier_id").set_index("supplier_id").join(kg_s).fillna({"qty_kg": 0})
print(s_stat.groupby("sbti_status").qty_kg.sum().div(s_stat.qty_kg.sum()).round(3).to_dict(), "provides_pcf kg share", round(float(s_stat[s_stat.provides_pcf].qty_kg.sum() / s_stat.qty_kg.sum()), 3))
tgt_share = float(s_stat[s_stat.sbti_status.isin(["targets_set", "committed"])].qty_kg.sum() / s_stat.qty_kg.sum())
pool13 = non_b * fert_frac * (1 - 0.9 / 3.7)
print(f"L13: bought seed {bought_t:.0f} t, non-FLAG {non_b:.0f} t, fertiliser share of non-FLAG {fert_frac:.3f} -> ceiling {pool13:.0f} t at 100 % adoption; share with SBTi status {tgt_share:.3f}; design 14000 = {14000 / pool13 * 100:.0f}% of ceiling; design flag=True but fertiliser manufacture is non-FLAG")
# FI contract rape vs imports
cr = fl[(fl.year == 2025) & (fl.crop == "turnip_rape")]
kgk_all = cr.tco2e.sum() / (cr.qty_kg.sum() / 1000); kgk_min = (cr.tco2e.sum() - cr.t_org.sum()) / (cr.qty_kg.sum() / 1000)
imp = r25[["M102", "M103", "M104", "M105", "M106", "M107"]].sum() / rp[2025][["M102", "M103", "M104", "M105", "M106", "M107"]].sum()
m100 = fl[fl.crop == "turnip_rape"].groupby("year").qty_kg.sum() / 1e6 * 1000
head15 = m100.max() - m100[2025]
print(f"L15: FI contract rape {kgk_all:.2f} kg/kg with peat, {kgk_min:.2f} on mineral; imports {imp:.2f}. M100 delivered t by year {m100.round(0).to_dict()}; headroom {head15:.0f} t. Mineral-only {head15 * (imp - kgk_min):.0f} t saved; at the current peat mix {head15 * (imp - kgk_all):.0f} t")

# ---- other pools
s1_sak = line("S-SAK:lng", "scope1") + line("S-SAK:lpg", "scope1")
print("Säkylä fossil t", round(s1_sak), "| biogas MWh by year", T["energy"].query("site_id=='S-SAK' and carrier=='biogas'").groupby("year").mwh.sum().round(0).to_dict())
need_mwh = (T["energy"].query("site_id=='S-SAK' and carrier in ['lng','lpg'] and year==2025").mwh.sum())
bg = T["energy"].query("site_id=='S-SAK' and carrier=='biogas'").groupby("year").mwh.sum()
print(f"LNG+LPG MWh to replace {need_mwh:.0f} on top of biogas {bg[2025]:.0f}; last year's biogas growth {bg[2025] - bg[2024]:.0f} MWh = {(bg[2025] - bg[2024]) / need_mwh * 100:.0f}% of the need")
rf = T["refrigerants"].assign(gwp=lambda d: d.refrigerant.map(F.REFRIGERANT_GWP), t=lambda d: d.kg_added * d.refrigerant.map(F.REFRIGERANT_GWP) / 1000)
print(rf[rf.t > 0].pivot_table(index=["site_id", "system", "refrigerant"], columns="year", values="t", aggfunc="sum").round(0).to_string())
r404 = rf[(rf.refrigerant == "R404A")].groupby("year").t.sum().reindex(range(2019, 2026)).fillna(0)
r404_m = float(r404.loc[2023:2025].mean())
other_hfc = float(rf[(rf.year == 2025) & (rf.refrigerant != "R404A") & (rf.site_id != "S-PUD")].t.sum())
fleet = line("FLEET:diesel", "scope1")
truck = q[q.line_item.isin(["inbound:EF-TKM-TRUCK", "inbound:EF-TKM-TRUCK-REEFER", "outbound:EF-TKM-TRUCK", "outbound:EF-TKM-TRUCK-REEFER"])].tco2e.sum()
hvo_cut = 1 - EF["EF-TKM-TRUCK-HVO"] / EF["EF-TKM-TRUCK"]
sh = T["shipments"]; sh = sh[(sh.year == 2025) & (sh.direction == "inbound")].copy(); sh["ref_doc"] = sh.ref_doc.astype(str)
doc = pur.dropna(subset=["doc_no"]).drop_duplicates("doc_no").set_index("doc_no").material_id
sh["mat"] = sh.ref_doc.map(doc)
seed_truck = float(sh[sh.mat.isin(["M102", "M103", "M104", "M105", "M106", "M107"]) & (sh.ef_id == "EF-TKM-TRUCK")].tkm.sum() * EF["EF-TKM-TRUCK"] / 1000)
print(f"road pool {truck:.0f} t; HVO cut {hvo_cut:.3f}; imported-seed truck legs {seed_truck:.0f} t; fleet diesel {fleet:.0f} t")
wh = line("frozen_warehousing"); reefer_out = line("outbound:EF-TKM-TRUCK-REEFER")
cred = raw["erp"][(raw["erp"].movement_type == 122) & raw["erp"].material_id.isin(L.CROP_MAT)].assign(y=lambda d: d.posting_date.str[:4].astype(int)).query("y==2025").quantity.sum()
deliv = pur[(pur.year == 2025) & pur.material_id.isin(L.CROP_MAT)].qty_kg.sum()
farm_t = J["pools"]["farm_t"] + FH["se_all"]
# credit notes barely exist on farm crops, so rejection is read from harvest (declared ha x reported yield) against delivered kg, surveyed rows only
sv_ = fl[fl.surveyed & (fl.year >= 2021)].assign(harv=lambda d: d.decl_ha * d.yield_t_ha * 1000)
rj = sv_.groupby("year").apply(lambda d: 1 - d.qty_kg.sum() / d.harv.sum(), include_groups=False)
rj_med = float((1 - sv_.qty_kg / sv_.harv).median())
print(f"credit notes = {abs(cred) / deliv * 100:.3f}% of delivered kg; harvest-vs-delivered gap by year {rj.round(3).to_dict()}; median row {rj_med:.3f}")
rej = max(rj_med, 0.0)
print(f"rejection rate used {rej * 100:.2f}%; farm t incl SE {farm_t:.0f}")
elec_t = float(fl[fl.year == 2025].t_elec.sum())
compost = T["waste"].query("year==2025 and treatment=='composting'").t.sum()
film = q[q.material_id == "M152"].tco2e.sum(); pet_kg = float(pur[(pur.year == 2025) & (pur.material_id == "M150")].qty_kg.sum())
soy_kg = float(pur[(pur.year == 2025) & (pur.material_id == "M130")].qty_kg.sum()); soy_t = float(q[q.material_id == "M130"].tco2e.sum())
pack_ing = float(q[q.material_id.isin(["M150", "M151", "M152", "M153", "M154"])].tco2e.sum())
org_t = J["pools"]["farm_org_t"] + FH["se_org"]; org_ha = J["pools"]["farm_org_ha"] + FH["se_org_ha"]
n_all = J["pools"]["n_kg_total"] + FH["se_n_kg"]
n2o_per_kgN = (0.016 + 0.05 * 0.014 + 0.24 * 0.011) * F.FARM_EF["n2o_n_to_n2o"] * F.FARM_EF["n2o_gwp"]
fert_fi = J["pools"]["farm_fert_n_t"]; conv_share = (fert_fi * 1000 / J["pools"]["n_kg_total"] - 0.9) / 2.8
pool08 = (J["pools"]["n_kg_total"] * conv_share + FH["se_n_kg"]) * 2.8 / 1000
print(f"L08: conventional N share FI {conv_share:.3f}; pool {pool08:.0f} t. N all {n_all:.0f} kg, N2O {n2o_per_kgN:.2f} kg CO2e/kg N. peat {org_t:.0f} t on {org_ha:.0f} ha")

kan = T["energy"].query("site_id=='S-KAN' and year==2025").groupby("carrier").mwh.sum()
lfo_share = kan["light_fuel_oil"] / kan[["light_fuel_oil", "wood_chips", "oilseed_sidestream"]].sum()
bj_t = FH["gas12"] * F.FUEL_EF_T_PER_MWH["natural_gas"]
cat6 = float(q[q.category == "cat06_business_travel"].tco2e.sum()); cat7 = float(q[q.category == "cat07_employee_commuting"].tco2e.sum())
print(f"Kantvik LFO share of steam fuel {lfo_share:.4f}; Bjuv gas t {bj_t:.0f}; cat6 {cat6:.1f} cat7 {cat7:.1f}")
BAND_A = {"high": .15, "medium": .35, "low": .60}
BAND_C = {"high": .15, "medium": .30, "low": .50}
# id: low, central, high t; FLAG share; bucket; class; note; opex scales with tonnes?
def row(i, lo, ce, hi, flag, bucket, cls, note, scale):
    return dict(lever_id=i, ab_low=lo, ab_central=ce, ab_high=hi, flag_frac=flag, bucket=bucket, cls=cls, note=note, scale_opex=scale)
b = BAND_A
l11 = org_t * feas
pool08 = pool08 * .9            # overlap: L09 removes 10 % of the N that L08 would have treated
truck = truck - seed_truck * .3  # overlap: L21 takes these truck legs off the road before L20 treats them
l08 = pool08 * .75
l03 = r404_m * .95
rows = [
 row("L01", s1_sak * (bg[2025] - bg[2024]) / need_mwh, s1_sak * .6, s1_sak, 0, "s12", "real", f"Needs {need_mwh:.0f} MWh more biogas; low = last year's observed growth", True),
 row("L02", fleet * .3, fleet * .6, fleet * .9, 0, "s12", "real", "Pool is FLEET diesel only; Pudasjärvi LPG leaves with the plant", False),
 row("L03", r404_m * .8, l03, r404_m, 0, "s12", "real", "R404A 2023-25 mean after gas-code fixes", False),
 row("L04", other_hfc * .15, other_hfc * .25, other_hfc * .4, 0, "s12", "real", "Only HFC left after L03; catalogue double-counts the cold store", False),
 row("L06", 0, lev.abatement_tco2e_2030_design["L06"] * lfo_share, lev.abatement_tco2e_2030_design["L06"], 0, "s12", "real", "Heat saved displaces the steam fuel mix pro rata, so only the LFO share is fossil. After the sale it is Scope 2 at the supplier EF", False),
 row("L07", bj_t * .5, bj_t, bj_t * 1.3, 0, "s12", "real", "Full-year Bjuv gas is 12 x December; only 1/12 of it is in the 2025 inventory", False),
 row("L08", pool08 * .5, l08, pool08, 0, "s3nf", "real", "Only conventional N counts; low-carbon AN already adopted", True),
 row("L09", n_all * .05 * n2o_per_kgN / 1000, n_all * .10 * n2o_per_kgN / 1000, n_all * .15 * n2o_per_kgN / 1000, 1, "flag", "real", "5/10/15 % less mineral N, FI+SE contract area; field N2O only", False),
 row("L10", 0, 0, 600, 1, "flag", "not_in_inventory", "No term in the calculator; removals need LSR monitoring", False),
 row("L11", org_t * feas * .5, l11, org_t * fr_all, 1, "flag", "reallocation", "Falls in Scope 3 only; drained parcels stay farmed unless retired", False),
 row("L12", 0, min(1200, org_t - l11), min(1200, org_t - l11) * 1.3, 1, "flag", "real", "Real on-land change; only on hectares L11 did not move", False),
 row("L13", pool13 * .1, pool13 * tgt_share, pool13 * .7, 0, "s3nf", "real", "Fertiliser part only, reclassified non-FLAG; the PCF part is L27 measurement", True),
 row("L14", head * delta, head * delta, lev.abatement_tco2e_2030_design["L14"], .86, "flag", "real", "Central = SE+DK at their highest observed volume", True),
 row("L15", 0, head15 * (imp - kgk_min), lev.abatement_tco2e_2030_design["L15"], .86, "flag", "real", f"Mineral soil only; on the current peat mix it adds {head15 * (kgk_all - imp):.0f} t", True),
 row("L16", Pz["cheese_ham_t"] * .1, Pz["cheese_ham_t"] * .16, Pz["cheese_ham_t"] * .25, .85, "flag", "real", "Needs recipe control and copacker PCF after Pudasjärvi; library copack factor cannot show it", False),
 row("L17", soy_kg / 1000 * 1.5, soy_t - soy_kg * 2.0 / 1000, 380, .7, "flag", "real", "Assumes faba protein ~2.0 kg/kg (4 kg beans per kg)", False),
 row("L18", pet_kg * .85 / 1000 * .5, pet_kg * .85 / 1000 * .75, pet_kg * .85 / 1000, 0, "s3nf", "real", "2.70 to 1.85 kg/kg on 2025 PET", True),
 row("L19", film * .08, film * .15, film * .2, 0, "s3nf", "real", "Assumes 15 % less film mass", False),
 row("L20", truck * hvo_cut * .3, truck * hvo_cut * .55, truck * hvo_cut * .8, 0, "s3nf", "real", "Road pool supports the design; feedstock risk", True),
 row("L21", seed_truck * .15, seed_truck * .3, seed_truck * .5, 0, "s3nf", "real", "Pool is the truck legs of imported seed", False),
 row("L22", (wh + reefer_out) * .03, (wh + reefer_out) * .10, 700, 0, "s3nf", "real", "Needs an industry coalition; Apetit cannot do it alone", False),
 row("L23", farm_t * rej * .25, farm_t * rej * .5, farm_t * rej * .75, .85, "flag", "real", "Halves credit-note rejections", False),
 row("L24", elec_t * .1, elec_t * .3, 120, 0, "s3nf", "real", "Calculator sees only pump electricity; catalogue flag=True is wrong", False),
 row("L25", pack_ing * .15 * .3, pack_ing * .15 * .6, 1300, 0, "s3nf", "real", "Assumes 15 % of packaging footprint is electricity", False),
 row("L28", cat6 * .15, cat6 * .27, cat6 * .4, 0, "s3nf", "real", "27 % of 2025 category 6, the share the catalogue implies", False),
 row("L29", cat7 * .1, cat7 * .18, cat7 * .28, 0, "s3nf", "real", "18 % of 2025 category 7, the share the catalogue implies", False),
 row("L30", compost * .035 * .5, compost * .035, compost * .035 * 1.2, 0, "s3nf", "real", "Composted t x (95 - 60) kg/t", False),
]
m = pd.DataFrame(rows).set_index("lever_id")
m = m.join(lev[["name", "abatement_tco2e_2030_design", "capex_eur", "opex_delta_eur_per_yr", "lifetime_yr", "earliest_start", "ramp_years", "confidence", "co_benefits", "indicative_cost_eur_per_tco2e", "flag"]])
WACC = .08
crf = WACC / (1 - (1 + WACC) ** -m.lifetime_yr)
scale = np.where(m.scale_opex, m.ab_central / m.abatement_tco2e_2030_design, 1.0)
m["cost_yr_central"] = m.capex_eur * crf + m.opex_delta_eur_per_yr * scale
bc = m.confidence.map(BAND_C)
pos = m.cost_yr_central >= 0
m["cost_yr_lo"] = np.where(pos, m.cost_yr_central * (1 - bc), m.cost_yr_central * (1 + bc))
m["cost_yr_hi"] = np.where(pos, m.cost_yr_central * (1 + bc), m.cost_yr_central * (1 - bc))
safe = m.ab_central.replace(0, np.nan)
m["eur_t_central"] = m.cost_yr_central / safe
# Interval = extremes over the four corners, so negative-cost levers order correctly. Worst is undefined where the low case is zero tonnes.
# Levers whose opex scales with tonnes keep a unit cost: tonnes do not move their EUR/t, only the cost band does.
lo_t = m.ab_low.replace(0, np.nan); hi_t = m.ab_high.replace(0, np.nan)
corners = pd.concat([m.cost_yr_lo / hi_t, m.cost_yr_lo / lo_t, m.cost_yr_hi / hi_t, m.cost_yr_hi / lo_t], axis=1)
m["eur_t_best"] = corners.min(axis=1)
m["eur_t_worst"] = corners.max(axis=1).where(m.ab_low > 0)
m.loc[m.scale_opex, "eur_t_best"] = (m.cost_yr_lo / safe)
m.loc[m.scale_opex, "eur_t_worst"] = (m.cost_yr_hi / safe)
m["design_ratio"] = m.ab_central / m.abatement_tco2e_2030_design
m = m.sort_values("eur_t_central", na_position="last")
m["cum_central"] = m.ab_central.cumsum()
show = m[["name", "bucket", "cls", "abatement_tco2e_2030_design", "ab_low", "ab_central", "ab_high", "design_ratio", "indicative_cost_eur_per_tco2e", "eur_t_central", "eur_t_best", "eur_t_worst"]].copy()
show["name"] = show.name.str[:40]
print(show.round(2).to_string())
excl = lev.loc[["L05", "L26", "L27"], ["name", "lever_type", "opex_delta_eur_per_yr"]]
print(excl.to_string())
print("Design sum (real levers)", int(m.abatement_tco2e_2030_design.sum()), "central", round(m.ab_central.sum()), "low", round(m.ab_low.sum()), "high", round(m.ab_high.sum()))
print(m.groupby("bucket")[["abatement_tco2e_2030_design", "ab_low", "ab_central", "ab_high"]].sum().round(0).to_string())
print(m.groupby("cls")[["ab_low", "ab_central", "ab_high"]].sum().round(0).to_string())
m.round(3).to_csv(OUT / "B2_macc.csv")
json.dump(dict(peat=dict(ha=float(fr.peat.sum()), farms=int(len(fr)), feas=float(feas), feas_all=float(fr_all), rot=rot, hist=hist, org_t=org_t, org_ha=org_ha, all_peat_ha=float(stay.sum()), plan={int(k): float(v) for k, v in plan.items()}),
               l13=dict(pool=pool13, share=tgt_share, fert_frac=fert_frac), l14=dict(head=head, delta=delta, need=need, pct=need / rp[2025][lo_mats].sum() * 100),
               l15=dict(kgk_all=kgk_all, kgk_min=kgk_min, imp=imp, head=head15), r404=r404_m, rej=rej,
               biogas=dict(need_mwh=need_mwh, growth_pct=(bg[2025] - bg[2024]) / need_mwh * 100), formula=dict(ok=int((d < 1).sum()), n=int(len(chk)))), open(OUT / "macc_notes.json", "w"), indent=1, default=float)
