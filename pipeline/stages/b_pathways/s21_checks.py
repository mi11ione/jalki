"""review checks on the structural findings: knife-edge of the Pudasjärvi test, 2023->24 Scope 3 decomposition,
GoO dependence, 2019 vs 2025 base. Run: python stages/b_pathways/s21_checks.py"""
from ccn_paths import PACKAGE, stage_dir
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import json
import numpy as np, pandas as pd
HERE = stage_dir("b_pathways")
import lib_clean as L
from ccn_tools import reference_calculator as RC, factors as F
pd.set_option("display.width", 200, "display.max_columns", 30, "display.max_rows", 200)
pd.set_option("future.no_silent_downcasting", True)
OUT = HERE / "outputs"
R = json.load(open(OUT / "structure.json"))
lines = pd.read_csv(OUT / "inventory_lines_2021_2025.csv")
fl = pd.read_csv(OUT / "farm_lines.csv")
raw, T = L.load_clean()
T["farm_footprints"] = fl[["farm_id", "crop", "year", "region", "tco2e"]]
lib = T["ef_library"].set_index("ef_id"); EF = lib.kgco2e_per_unit
C = {}

# ---- Pudasjärvi knife edge
P = R["pudasjarvi"]; tot, totpf = R["reported"]["total"], R["proforma"]["total"]
pl, bd = F.PACK_KG_PER_T["frozen_pizza"]
pack = P["piz_t"] * (pl * EF["EF-PE-FILM"] + bd * EF["EF-BOARD"]) / 1000
net_a, net_b = P["net_total"], P["net_total"] - pack
print(f"PUD net {net_a:.0f}; if the copack factor also covers packaging, minus {pack:.0f} = {net_b:.0f}")
for nm, n in (("packaging stays Apetit's", net_a), ("packaging inside copack factor", net_b)):
    print(f"  {nm}: {n / tot * 100:.2f}% of reported 2025; {n / totpf * 100:.2f}% of Foodhills-restated base")
out = P["ing"] + P["s3_other_out"] + P["s1"] + P["s2m"]
trig = (0.05 * totpf + out) / P["piz_t"]
print(f"Copacker PCF where the net change hits 5 % of restated base: {trig:.2f} kg/kg; carbon-neutral at {out / P['piz_t']:.2f}; library {EF['EF-COPACK-PIZZA']:.2f}")
C["pud"] = dict(pack=pack, pct_rep_a=net_a / tot * 100, pct_rep_b=net_b / tot * 100, pct_pf_a=net_a / totpf * 100, pct_pf_b=net_b / totpf * 100, trig_kg=trig, neutral_kg=out / P["piz_t"])

# ---- Foodhills on a multi-year pea basis
F_ = R["foodhills"]
print(f"Foodhills as share of reported total at central {F_['pct']:.2f}%, band {F_['lo_pct']:.2f}-{F_['hi_pct']:.2f}")

# ---- 2023 -> 2024 Scope 3 decomposition
def s3(y, pcf=True):
    t = dict(T)
    if not pcf:
        t["pcf_used"] = T["pcf_used"].iloc[0:0]
    return RC.compute_inventory(t, y)
a23, a24, a24d = s3(2023), s3(2024), s3(2024, False)
tot23, tot24, tot24d = [x[x.scope == "scope3"].tco2e.sum() for x in (a23, a24, a24d)]
method = tot24 - tot24d
farm = fl[fl.year == 2024].tco2e.sum() - fl[fl.year == 2023].tco2e.sum()
peat = fl[fl.year == 2024].t_org.sum() - fl[fl.year == 2023].t_org.sum()
rest = tot24d - tot23 - farm
pur = T["purchases"]; mm = T["materials"].set_index("material_id")
def goods(y):
    g = pur[(pur.year == y) & ~pur.material_id.isin(L.CROP_MAT) & pur.material_id.map(mm.default_ef_id).isin(EF.index) & ~pur.material_id.map(mm.material_group).isin(["service", "capex"])]
    return (g.groupby("material_id").qty_kg.sum() * pd.Series({m: EF[mm.default_ef_id[m]] for m in g.material_id.unique()}) / 1000)
vol = (goods(2024) - goods(2023)).sum()
other = rest - vol
print(f"Scope 3 2023 {tot23:.0f} -> 2024 {tot24:.0f} = {tot24 - tot23:.0f}")
print(f"  bought-goods volume at fixed library factors {vol:.0f} ({vol / (tot24 - tot23) * 100:.1f}%)")
print(f"  supplier PCFs replacing defaults {method:.0f} ({method / (tot24 - tot23) * 100:.1f}%)")
print(f"  contract-farm line {farm:.0f} ({farm / (tot24 - tot23) * 100:.1f}%), of which peat rotation {peat:.0f}")
print(f"  everything else {other:.0f} ({other / (tot24 - tot23) * 100:.1f}%)")
C["decomp"] = dict(total=tot24 - tot23, pct=(tot24 / tot23 - 1) * 100, volume=vol, method=method, farm=farm, peat=peat, other=other)
rate = 0.025 * R["proforma"]["s3"]
print(f"  a 2.5 %/yr pace on pro forma Scope 3 is {rate:.0f} t/yr; the 2023-24 fall equals {abs(tot24 - tot23) / rate:.1f} years of it; the PCF step alone {abs(method) / rate:.1f} years")
C["decomp"]["years_of_target"] = abs(tot24 - tot23) / rate; C["decomp"]["method_years"] = abs(method) / rate

# ---- GoO dependence of the Scope 2 number
en = T["energy"]; el = en[(en.year == 2025) & (en.carrier == "electricity")].groupby("site_id").mwh.sum()
ctry = T["sites"].set_index("site_id").country
no_goo = sum(v * (F.RESIDUAL_FI if ctry[s] == "FI" else F.RESIDUAL_SE)[2025] for s, v in el.items())
no_goo_pf = no_goo + R["foodhills"]["add_s2m_res"]
cov = T["goo"].query("year==2025 and vintage_year==2025").groupby("site_id").mwh_cancelled.sum()
print(f"Electricity 2025 {el.sum():.0f} MWh; GoO-covered {sum(min(el[s], cov.get(s, 0)) for s in el.index):.0f}; S2m reported {R['reported']['s2m']:.1f}; without GoOs {no_goo:.0f} t reported, {no_goo_pf:.0f} t pro forma")
print(f"S1+2 pro forma with GoOs {R['proforma']['s1'] + R['proforma']['s2m']:.0f}; without {R['proforma']['s1'] + no_goo_pf:.0f}; location-based {R['proforma']['s1'] + R['proforma']['s2l']:.0f}")
C["goo"] = dict(no_goo_pf=no_goo_pf, mwh=float(el.sum()), s12_with=R["proforma"]["s1"] + R["proforma"]["s2m"], s12_without=R["proforma"]["s1"] + no_goo_pf, s12_loc=R["proforma"]["s1"] + R["proforma"]["s2l"])

# ---- base-year options
b = R["base2019"]; pf = R["proforma"]
s12_19 = b["s1"] + b["s2m"]; s12_25 = pf["s1"] + pf["s2m"]
for name, base, y0, r, cur in (("S1+2 2019 base", s12_19, 2019, .042, s12_25), ("S1+2 2025 base", s12_25, 2025, .042, s12_25)):
    tg = base * (1 - r * (2035 - y0))
    print(f"{name}: base {base:.0f}, 2035 target {tg:.0f}, current {cur:.0f}: {'already met' if cur <= tg else 'cut needed ' + str(round(cur - tg))}")
    C[name] = dict(base=base, target2035=tg, cut=cur - tg)
fh_s3 = pf["s3"] - R["reported"]["s3"]
for lab, v in (("low", b["s3_lo"]), ("high", b["s3_hi"])):
    base = v + fh_s3
    tg = base * (1 - .025 * 16)
    print(f"S3 2019 base ({lab}, +Foodhills): {base:.0f}, 2035 target {tg:.0f}, cut from pro forma 2025 {pf['s3'] - tg:.0f} ({(pf['s3'] - tg) / pf['s3'] * 100:.1f}%)")
    C["S3 2019 " + lab] = dict(base=base, target2035=tg, cut=pf["s3"] - tg)
tg = pf["s3"] * (1 - .25); print(f"S3 2025 base: {pf['s3']:.0f}, 2035 target {tg:.0f}, cut {pf['s3'] - tg:.0f} (25%)")
json.dump(C, open(OUT / "checks.json", "w"), indent=1, default=float)
