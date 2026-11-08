"""B1 base year and recalculation: 2019 rebuild, Foodhills 12-month pro forma, Pudasjärvi outsourcing, Kantvik steam,
measurement effects, and the 5 % significance test for each. Reads s10 outputs.
Run: python stages/b_pathways/s20_structure.py"""
from ccn_paths import PACKAGE, stage_dir
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import json, copy
import numpy as np, pandas as pd
HERE = stage_dir("b_pathways")
import lib_clean as L
from ccn_tools import reference_calculator as RC, factors as F
pd.set_option("display.width", 200, "display.max_columns", 30, "display.max_rows", 200)
pd.set_option("future.no_silent_downcasting", True)
OUT = HERE / "outputs"
lines = pd.read_csv(OUT / "inventory_lines_2021_2025.csv")
fl = pd.read_csv(OUT / "farm_lines.csv")
J = json.load(open(OUT / "inventory_summary.json"))
raw, T = L.load_clean()
T["farm_footprints"] = fl[["farm_id", "crop", "year", "region", "tco2e"]]
lib = T["ef_library"].set_index("ef_id")
EF = lib.kgco2e_per_unit
q25 = lines[lines.year == 2025]
S1 = q25[q25.scope == "scope1"].tco2e.sum(); S2M = q25[q25.scope == "scope2_market"].tco2e.sum(); S2L = q25[q25.scope == "scope2_location"].tco2e.sum()
S3 = q25[q25.scope == "scope3"].tco2e.sum(); FLAG = q25.flag_t.sum()
TOT = S1 + S2M + S3
print(f"2025 as reported boundary: S1 {S1:.0f} S2m {S2M:.0f} S2l {S2L:.0f} S3 {S3:.0f} FLAG {FLAG:.0f} total {TOT:.0f}")
R = {}

# ---- 2019 rebuild: Scope 1 and 2 only; ERP starts in 2021
pub = pd.read_csv(L.DATA / "data" / "05_scenarios" / "published_inventory_history.csv").set_index("year")
inv19 = RC.compute_inventory(dict(T, purchases=T["purchases"].iloc[0:0], farm_footprints=T["farm_footprints"].iloc[0:0], shipments=T["shipments"].iloc[0:0]), 2019)
s1_19 = inv19[inv19.scope == "scope1"].tco2e.sum(); s2m_19 = inv19[inv19.scope == "scope2_market"].tco2e.sum(); s2l_19 = inv19[inv19.scope == "scope2_location"].tco2e.sum()
print(f"2019 rebuilt S1 {s1_19:.0f} (published {pub.scope1[2019]}) S2m {s2m_19:.0f} (published {pub.scope2_market[2019]}) S2l {s2l_19:.0f}")
s3_21 = lines[(lines.year == 2021) & (lines.scope == "scope3")].tco2e.sum()
gap21 = pub.scope3[2021] - s3_21
print(f"Scope 3: published 2021 {pub.scope3[2021]} vs canonical continuing ops 2021 {s3_21:.0f}: gap {gap21:.0f} = grain trade + method + synthetic deviation (not separable)")
s3_19_lo, s3_19_hi = s3_21, pub.scope3[2019] - gap21
print(f"2019 Scope 3 continuing-ops range: {min(s3_19_lo, s3_19_hi):.0f} to {max(s3_19_lo, s3_19_hi):.0f}; published incl. grain {pub.scope3[2019]}")
R["base2019"] = dict(s1=s1_19, s2m=s2m_19, s2l=s2l_19, s3_lo=min(s3_19_lo, s3_19_hi), s3_hi=max(s3_19_lo, s3_19_hi), gap21=gap21)

# ---- Foodhills: Swedish peas from the grower file, Bjuv site at 12 x December
fh = pd.read_csv(L.DATA / "data" / "03_farming" / "foodhills_odlingsdata_se.csv", sep=";", decimal=",")
fh = fh.rename(columns={"odlar_id": "farm_id", "skördeår": "year", "areal_ha": "area_ha", "levererad_mängd_ton": "t", "kvävegiva_kg_ha": "n_mineral_kg_ha", "diesel_l_ha": "diesel_l_ha"})
fh["yield_t_ha"] = fh.t / fh.area_ha
print(fh.groupby("year").yield_t_ha.describe(percentiles=[.5]).round(2).to_string())
print("N max", fh.n_mineral_kg_ha.max(), "diesel max", fh.diesel_l_ha.max(), "yield max", fh.yield_t_ha.max().round(2), "dups", fh.duplicated(["farm_id", "year"]).sum())
sv = L.clean_survey(raw)
fi = sv[(sv.crop == "pea")]
fh["crop"] = "pea"; fh["n_manure_kg_ha"] = 0.0; fh["p_kg_ha"] = fi.p_kg_ha.mean(); fh["lime_t_ha"] = fi.lime_t_ha.mean(); fh["sprays"] = fi.sprays.mean()
fh["irrigated"] = fh.bevattnad.eq("ja"); fh["fertiliser_product"] = ""
c = L.components(fh, grid=0.012)
c["diesel"] = fh.diesel_l_ha * (2.45 + F.FARM_EF["diesel_wtt"])     # METHODOLOGY s5: Swedish blend 2.45
os_ = L.organic_share(raw)
se_os = os_[(os_.crop == "pea")].rename(columns={"area_ha": "decl_ha"})
fh = pd.concat([fh, c], axis=1).merge(se_os, on=["farm_id", "crop", "year"], how="left")
fh["share"] = (fh.org_ha / fh.decl_ha).fillna(0)
fh["t_org"] = fh.area_ha * fh.share * L.ORG_KG_HA / 1000
fh["t_flag"] = fh.t_org + fh.area_ha * fh[L.FLAG_PARTS].sum(axis=1) / 1000
fh["t_non"] = fh.area_ha * fh[L.NONFLAG_PARTS].sum(axis=1) / 1000
fh["t_fert"] = fh.area_ha * fh.fert_n / 1000
fh["t_all"] = fh.t_flag + fh.t_non
g = fh.groupby("year").agg(t_delivered=("t", "sum"), ha=("area_ha", "sum"), org_ha=("share", lambda s: float((s * fh.loc[s.index, "area_ha"]).sum())), t_all=("t_all", "sum"), t_flag=("t_flag", "sum"), t_org=("t_org", "sum"), t_non=("t_non", "sum"), n_kg=("n_mineral_kg_ha", lambda s: float((s * fh.loc[s.index, "area_ha"]).sum())))
g["kg_per_kg"] = g.t_all / g.t_delivered
print(g.round(3).to_string())
se = g.loc[2025]
lo5, hi5 = g.loc[2021:2025].t_all.min(), g.loc[2021:2025].t_all.max()
lib_se = se.t_delivered * EF["EF-VEG-PEA-SE"]
print(f"SE peas 2025: {se.t_all:.0f} t (FLAG {se.t_flag:.0f}, peat {se.t_org:.0f}); 2021-25 range {lo5:.0f}-{hi5:.0f}; library regional-average route {lib_se:.0f} t")
# Bjuv site
en = T["energy"]; b = en[(en.site_id == "S-BJU") & (en.year == 2025)].groupby("carrier").mwh.sum()
gas12, el12 = b["natural_gas"] * 12, b["electricity"] * 12
goo_log = raw["goo"].query("site_id=='S-BJU' and year==2025").mwh_cancelled.sum()
print(f"Bjuv Dec gas {b['natural_gas']:.0f} el {b['electricity']:.0f} MWh; x12 gas {gas12:.0f} el {el12:.0f}; internal GoO log {goo_log:.0f}; lever note says ~7300 gas")
bj_s1_12 = gas12 * F.FUEL_EF_T_PER_MWH["natural_gas"]
bj_rf = q25[q25.line_item.str.startswith("S-BJU") & (q25.scope == "scope1") & (q25.category == "fugitive_refrigerants")].tco2e.sum()
bj_in = q25[q25.line_item.str.startswith("S-BJU") & (q25.scope == "scope1")].tco2e.sum()
bj_s2m_in = q25[(q25.line_item == "S-BJU") & (q25.scope == "scope2_market")].tco2e.sum()
bj_s2l_in = q25[(q25.line_item == "S-BJU") & (q25.scope == "scope2_location")].tco2e.sum()
add_s1 = bj_s1_12 + bj_rf - bj_in
add_s2m_goo, add_s2m_res = 0.0, el12 * F.RESIDUAL_SE[2025] - bj_s2m_in
add_s2l = el12 * F.GRID_SE_LB[2025] - bj_s2l_in
print(f"Bjuv in 2025 reported S1 {bj_in:.1f}, S2m {bj_s2m_in:.1f}. Pro forma adds S1 {add_s1:.0f}; S2m {add_s2m_goo:.0f} if GoOs cover all, {add_s2m_res:.0f} at residual mix; S2l {add_s2l:.0f}")
# Foodhills non-farm Scope 3: proxy, the pack has no C400 ERP rows and no S-BJU sales
print("ERP rows C400:", (raw["erp"].company_code == "C400").sum(), "| ERP plant S-BJU:", (raw["erp"].plant == "S-BJU").sum(), "| sales S-BJU:", (raw["sales"].site_id == "S-BJU").sum())
tsold = se.t_delivered * 0.9       # ASSUMPTION: 10 % processing loss
pl, bd = F.PACK_KG_PER_T["frozen_vegetables"]
pack = tsold * (pl * EF["EF-PE-FILM"] + bd * EF["EF-BOARD"]) / 1000
inb = se.t_delivered * 60 * EF["EF-TKM-TRUCK"] / 1000                  # ASSUMPTION: 60 km field to plant
sal = raw["sales"].query("year==2025"); out_t = q25[q25.category == "cat09_downstream_transport"].tco2e.sum() / sal[~sal.product_group.isin(["rapeseed_meal_expeller"])].t_sold.sum()
c9 = tsold * out_t
c11 = tsold * 1000 * F.USE_PHASE_KWH_PER_KG["frozen_vegetables"] * F.GRID_SE_LB[2025] / 1000
c12 = tsold * (pl / 1000 * F.EOL_PLASTIC_EF_T + bd / 1000 * F.EOL_BOARD_EF_T)
c3 = (gas12 * EF["EF-WTT-NG"] + el12 * EF["EF-ELEC-UPSTREAM-SE"]) / 1000
fh_other = pack + inb + c9 + c11 + c12 + c3
print(f"Foodhills non-farm Scope 3 proxy {fh_other:.0f} t: packaging {pack:.0f}, inbound {inb:.0f}, cat9 {c9:.0f}, cat11 {c11:.0f}, cat12 {c12:.0f}, cat3 {c3:.0f}")
fh_s3 = se.t_all + fh_other
fh_total = add_s1 + add_s2m_goo + fh_s3
print(f"Foodhills addition: S1+2 +{add_s1 + add_s2m_goo:.0f} S3 +{fh_s3:.0f} (FLAG +{se.t_flag:.0f}) total +{fh_total:.0f} = {fh_total / TOT * 100:.2f}% of 2025 total; S1+2 {100 * (add_s1 + add_s2m_goo) / (S1 + S2M):.1f}% ; FLAG {100 * se.t_flag / FLAG:.2f}%")
lo_tot = add_s1 * 0.7 + lo5 + fh_other * 0.5
hi_tot = add_s1 * 1.3 + add_s2m_res + hi5 + fh_other * 1.5
print(f"Foodhills band (site +-30 %, peas at 2021-25 min/max, proxy +-50 %): {lo_tot:.0f} to {hi_tot:.0f} = {lo_tot / TOT * 100:.2f}% to {hi_tot / TOT * 100:.2f}%")
R["foodhills"] = dict(add_s1=add_s1, add_s2m_res=add_s2m_res, add_s2l=add_s2l, se_all=se.t_all, se_flag=se.t_flag, se_org=se.t_org, se_non=se.t_non, se_ha=se.ha, se_org_ha=se.org_ha, se_n_kg=se.n_kg, other_s3=fh_other, total=fh_total, pct=fh_total / TOT * 100, lo_pct=lo_tot / TOT * 100, hi_pct=hi_tot / TOT * 100, gas12=gas12, el12=el12, delivered_t=se.t_delivered, se_fert=float(fh[fh.year == 2025].t_fert.sum()), se_lo=lo5, se_hi=hi5)

# ---- Pudasjärvi: outsourcing
pud_ing = ["M131", "M133", "M134", "M135", "M136"]
ing = q25[q25.material_id.isin(pud_ing)]
print(ing.groupby("material_id")[["tco2e", "flag_t"]].sum().round(0).to_string())
pud_s1 = q25[q25.line_item.str.startswith("S-PUD") & (q25.scope == "scope1")].tco2e.sum()
pud_s2m = q25[(q25.line_item == "S-PUD") & (q25.scope == "scope2_market")].tco2e.sum(); pud_s2l = q25[(q25.line_item == "S-PUD") & (q25.scope == "scope2_location")].tco2e.sum()
pud_wst = q25[q25.line_item.str.startswith("S-PUD") & (q25.category == "cat05_waste")].tco2e.sum()
pud_comm = q25[(q25.line_item == "S-PUD") & (q25.category == "cat07_employee_commuting")].tco2e.sum()
pud_c3 = q25[(q25.category == "cat03_fuel_energy") & (q25.line_item == "elec_upstream:S-PUD")].tco2e.sum()
piz = raw["sales"].query("year==2025 and product_group=='frozen_pizza'").t_sold.sum()
cop = piz * EF["EF-COPACK-PIZZA"]; cop_flag = cop * lib.flag_share["EF-COPACK-PIZZA"]
out_s3 = ing.tco2e.sum() + pud_wst + pud_comm + pud_c3
net_s3 = cop - out_s3; net_flag = cop_flag - ing.flag_t.sum()
print(f"PUD S1 {pud_s1:.0f} S2m {pud_s2m:.1f} S2l {pud_s2l:.0f}; pizza {piz:.0f} t; copack cat1 +{cop:.0f} (FLAG {cop_flag:.0f}); ingredient cat1 out {ing.tco2e.sum():.0f} (FLAG {ing.flag_t.sum():.0f}); other S3 out {pud_wst + pud_comm + pud_c3:.0f}")
print(f"PUD net: S1+2 {-(pud_s1 + pud_s2m):.0f} ({100 * (pud_s1 + pud_s2m) / (S1 + S2M):.1f}% of S1+2) ; S3 +{net_s3:.0f} ; FLAG +{net_flag:.0f}; total +{net_s3 - pud_s1 - pud_s2m:.0f} = {(net_s3 - pud_s1 - pud_s2m) / TOT * 100:.2f}% of 2025 total")
be = (out_s3 + pud_s1 + pud_s2m) / piz
print(f"Copacker PCF that makes the move carbon-neutral: {be:.2f} kg/kg vs library 3.40; pizza with ingredients only is {ing.tco2e.sum() / piz:.2f} kg/kg")
R["pudasjarvi"] = dict(s1=pud_s1, s2m=pud_s2m, s2l=pud_s2l, piz_t=piz, copack=cop, copack_flag=cop_flag, ing=ing.tco2e.sum(), ing_flag=ing.flag_t.sum(), s3_other_out=pud_wst + pud_comm + pud_c3, net_s3=net_s3, net_flag=net_flag, net_total=net_s3 - pud_s1 - pud_s2m, pct=(net_s3 - pud_s1 - pud_s2m) / TOT * 100, breakeven_kg=be, cheese_ham_t=float(q25[q25.material_id.isin(["M133", "M134"])].tco2e.sum()))

# ---- Kantvik steam
fuels = en[(en.site_id == "S-KAN")].groupby(["carrier", "year"]).mwh.sum().unstack(0).round(0)
print(fuels.to_string())
lfo = en[(en.site_id == "S-KAN") & (en.carrier == "light_fuel_oil") & (en.year == 2025)].mwh.sum()
lfo_t = lfo * F.FUEL_EF_T_PER_MWH["light_fuel_oil"]
bio_mwh = en[(en.site_id == "S-KAN") & en.carrier.isin(["wood_chips", "oilseed_sidestream"]) & (en.year == 2025)].mwh.sum()
kan_bio = en[(en.site_id == "S-KAN") & (en.year == 2025)].assign(b=lambda d: d.mwh * d.carrier.map(F.FUEL_BIOGENIC_T_PER_MWH).fillna(0)).b.sum()
steam = (bio_mwh + lfo) * 0.85  # ASSUMPTION: boiler efficiency 85 %
print(f"Kantvik 2025: LFO {lfo:.0f} MWh = {lfo_t:.0f} t S1 ({100 * lfo_t / (S1 + S2M):.1f}% of S1+2); bio fuels {bio_mwh:.0f} MWh; biogenic memo {kan_bio:.0f} t; steam ~{steam:.0f} MWh; EF if LFO passes through {lfo_t / steam:.3f} t/MWh; 0 if supplier reports biogenic only")
c3k = steam * EF["EF-HEAT-UPSTREAM"] / 1000
R["kantvik"] = dict(lfo_mwh=lfo, lfo_t=lfo_t, biomemo=kan_bio, steam=steam, ef=lfo_t / steam, pct_total=lfo_t / TOT * 100)

# ---- measurement effects
T2 = dict(T); T2["pcf_used"] = T["pcf_used"].iloc[0:0]
meas = {}
for y in (2024, 2025):
    a = RC.compute_inventory(T, y); b_ = RC.compute_inventory(T2, y)
    A, B = a[a.scope == "scope3"].tco2e.sum(), b_[b_.scope == "scope3"].tco2e.sum()
    meas[y] = dict(with_pcf=A, default_only=B, effect=A - B)
    print(f"{y}: Scope 3 with valid PCFs {A:.0f}, default factors only {B:.0f}, PCF effect {A - B:.0f}")
pc = T["pcf_used"].query("year==2025")
pur = T["purchases"].query("year==2025")
kg = pur.groupby(["material_id", "supplier_id"]).qty_kg.sum().reset_index().merge(pc, on=["material_id", "supplier_id"])
mm = T["materials"].set_index("material_id")
kg["dflt"] = kg.material_id.map(mm.default_ef_id).map(EF)
kg["t_pcf"] = kg.qty_kg * kg.kgco2e_per_kg / 1000; kg["t_def"] = kg.qty_kg * kg.dflt / 1000
rat = kg.t_pcf.sum() / kg.t_def.sum()
goods_def = q25[(q25.category == "cat01_purchased_goods") & ~q25.line_item.str.startswith("contract") & (q25.basis != "supplier PCF (PACT)")].tco2e.sum()
goods_pcf = q25[(q25.basis == "supplier PCF (PACT)")].tco2e.sum()
print(f"PCF coverage of bought goods {goods_pcf:.0f} t, default-factor goods {goods_def:.0f} t; PCF/default ratio on covered kg {rat:.4f}")
lo_r, hi_r = kg.groupby("material_id").apply(lambda d: d.t_pcf.sum() / d.t_def.sum(), include_groups=False).quantile([.25, .75])
print(f"If the uncovered goods moved to PCFs at the observed ratio: apparent change {goods_def * (rat - 1):.0f} t; IQR ratios {lo_r:.3f}-{hi_r:.3f} -> {goods_def * (lo_r - 1):.0f} to {goods_def * (hi_r - 1):.0f} t")
cur = pd.read_csv(L.DATA / "data" / "03_farming" / "current_calculator_footprints.csv")
x = fl.merge(cur[["farm_id", "crop", "year", "carbon_footprint_kgco2e_per_kg"]], on=["farm_id", "crop", "year"], how="left")
ky = pd.Series(list(zip(x.crop, x.year)))
x["cf"] = x.carbon_footprint_kgco2e_per_kg.fillna(ky.map(cur.groupby(["crop", "year"]).carbon_footprint_kgco2e_per_kg.median()))
x["t_cur"] = x.qty_kg * x.cf / 1000
y25 = x[x.year == 2025]
peat_gap = y25.tco2e.sum() - y25.t_cur.sum()
print(f"Peat method change 2025 FI: ours {y25.tco2e.sum():.0f} vs current calculator {y25.t_cur.sum():.0f}: +{peat_gap:.0f} t = {peat_gap / (TOT - peat_gap) * 100:.2f}% of a current-practice total; ratio {y25.tco2e.sum() / y25.t_cur.sum():.2f}")
R["measure"] = dict(pcf_effect=meas, ratio=rat, uncovered=goods_def, apparent=goods_def * (rat - 1), apparent_lo=goods_def * (lo_r - 1), apparent_hi=goods_def * (hi_r - 1), peat_gap=peat_gap, peat_pct=peat_gap / (TOT - peat_gap) * 100, cur_t=y25.t_cur.sum())

# ---- what moves Scope 3 year to year: volume versus factors
rape = ["M100", "M101", "M102", "M103", "M104", "M105", "M106", "M107"]
kgy = T["purchases"][T["purchases"].material_id.isin(rape)].groupby("year").qty_kg.sum() / 1000
s3y = lines[lines.scope == "scope3"].groupby("year").tco2e.sum()
rp = lines[lines.material_id.isin(rape)].groupby("year").tco2e.sum()
d = pd.DataFrame(dict(rapeseed_t=kgy, rape_tco2e=rp, s3=s3y)).round(0)
d["ex_rape"] = d.s3 - d.rape_tco2e
print(d.to_string())
cov = float(np.std(d.s3, ddof=1) / d.s3.mean())
print(f"Scope 3 2021-25: mean {d.s3.mean():.0f}, sd {np.std(d.s3, ddof=1):.0f} (CV {cov * 100:.1f}%); 2023->2024 {d.s3[2024] - d.s3[2023]:.0f} t ({100 * (d.s3[2024] / d.s3[2023] - 1):.1f}%) of which rapeseed lines {d.rape_tco2e[2024] - d.rape_tco2e[2023]:.0f}")
R["volatility"] = dict(s3_mean=d.s3.mean(), s3_sd=float(np.std(d.s3, ddof=1)), d2324=d.s3[2024] - d.s3[2023], rape2324=d.rape_tco2e[2024] - d.rape_tco2e[2023], rape_share_2025=d.rape_tco2e[2025] / d.s3[2025], rape_kt=d.rapeseed_t.to_dict(), int_2023=d.s3[2023] / d.rapeseed_t[2023], int_2024=d.s3[2024] / d.rapeseed_t[2024])
r = np.corrcoef(d.rapeseed_t, d.s3)[0, 1]
print(f"corr(rapeseed t, Scope 3) over 5 years {r:.3f}")

# ---- category screen
s3cat = q25[q25.scope == "scope3"].assign(c=lambda d: d.category.str[:5]).groupby("c").tco2e.sum()
print((s3cat / s3cat.sum() * 100).round(2).to_string())
sold = raw["sales"].query("year==2025").groupby("product_group").t_sold.sum()
c10 = (sold["rapeseed_oil_bulk"] * 150 + sold["rapeseed_meal_expeller"] * 50) / 1000 * 0.2  # ASSUMPTION: 150 / 50 kWh per t at 0.2 t/MWh
print(f"Cat 10 screen (assumed energy intensity): {c10:.0f} t = {c10 / S3 * 100:.2f}% of Scope 3")
R["cat10"] = dict(t=c10, pct=c10 / S3 * 100); R["cat_share"] = (s3cat / s3cat.sum() * 100).to_dict()

# ---- significance table and base options
tests = [("Grain trade divestment (2019 base only)", gap21, gap21 / (pub.scope1[2019] + pub.scope2_market[2019] + pub.scope3[2019]) * 100, "yes, if 2019 is kept; upper bound, mixes method and synthetic deviation"),
         ("Foodhills 12-month pro forma", fh_total, fh_total / TOT * 100, ""),
         ("Pudasjärvi to contract manufacturing", R["pudasjarvi"]["net_total"], R["pudasjarvi"]["pct"], ""),
         ("Kantvik steam sale, LFO leaves Scope 1", -lfo_t, -lfo_t / TOT * 100, "S1+2 neutral if EF passes LFO through"),
         ("Peat method change vs current calculator", peat_gap, R["measure"]["peat_pct"], "method change"),
         ("All goods to PCFs at observed ratio (L27)", R["measure"]["apparent"], R["measure"]["apparent"] / TOT * 100, "method change")]
tb = pd.DataFrame(tests, columns=["event", "tco2e", "pct_of_base", "note"])
tb["over_5pct"] = tb.pct_of_base.abs() > 5
print(tb.round(2).to_string())
tb.round(2).to_csv(OUT / "B1_recalculation_tests.csv", index=False)
R["reported"] = dict(s1=S1, s2m=S2M, s2l=S2L, s3=S3, flag=FLAG, total=TOT)
R["proforma"] = dict(s1=S1 + add_s1, s2m=S2M + add_s2m_goo, s2l=S2L + add_s2l, s3=S3 + fh_s3, flag=FLAG + se.t_flag, total=TOT + fh_total)
print(R["proforma"])
json.dump(R, open(OUT / "structure.json", "w"), indent=1, default=float)
