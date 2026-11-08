"""B1 targets and pathways under all seven transition scenarios, gap to target per year, against a recalculated 2025 base.
Run: python stages/b_pathways/s40_pathway.py"""
from ccn_paths import PACKAGE, stage_dir
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import json
import numpy as np, pandas as pd
HERE = stage_dir("b_pathways")
import lib_clean as L
pd.set_option("display.width", 220, "display.max_columns", 40, "display.max_rows", 300, "display.max_colwidth", 40)
OUT = HERE / "outputs"
R = json.load(open(OUT / "structure.json")); N = json.load(open(OUT / "macc_notes.json")); C = json.load(open(OUT / "checks.json"))
m = pd.read_csv(OUT / "B2_macc.csv").set_index("lever_id")
sc = pd.read_csv(L.DATA / "data" / "05_scenarios" / "transition_scenarios.csv")
RATE = dict(s12=.042, s3nf=.025, flag=.0303)
pf, P, K = R["proforma"], R["pudasjarvi"], R["kantvik"]

base = dict(s12=pf["s1"] + pf["s2m"], s3nf=pf["s3"] - pf["flag"], flag=pf["flag"])
rc = dict(s12=base["s12"] - P["s1"] - P["s2m"], s3nf=base["s3nf"] + P["net_s3"] - P["net_flag"], flag=base["flag"] + P["net_flag"])
print("Reported 2025:", {k: round(v) for k, v in dict(s12=R["reported"]["s1"] + R["reported"]["s2m"], s3nf=R["reported"]["s3"] - R["reported"]["flag"], flag=R["reported"]["flag"]).items()})
print("Pro forma (Foodhills 12 months):", {k: round(v) for k, v in base.items()})
print("Recalculated (plus Pudasjärvi outsourcing; Kantvik neutral if the steam EF passes LFO through):", {k: round(v) for k, v in rc.items()})

# ---- targets
rows = []
for name, y in (("checkpoint 2030", 2030), ("V2, five years from a 2027 submission", 2032), ("V1.3.1, ten-year horizon", 2035)):
    for b in RATE:
        red = RATE[b] * (y - 2025)
        rows.append(dict(option=name, target_year=y, bucket=b, rate_pct_yr=RATE[b] * 100, cut_pct=red * 100, base_t=rc[b], target_t=rc[b] * (1 - red), cut_t=rc[b] * red))
tg = pd.DataFrame(rows); tg.round(2).to_csv(OUT / "B1_targets.csv", index=False)
print(tg.round(1).to_string())

# ---- scenario helpers
def interp(s, col, y):
    d = sc[sc.scenario == s].sort_values("year")
    return float(np.interp(y, d.year, d[col]))
GRID35 = {"orderly": .7, "disorderly": .85, "too little, too late": .95, "hot house": .95}   # ASSUMPTION
FOSSIL = {"L01": 1.0, "L02": 1.0, "L07": 1.0, "L20": .75}                                     # ETS2-exposed share of the tonnes saved
lines = pd.read_csv(OUT / "inventory_lines_2021_2025.csv"); q = lines[lines.year == 2025]
ELEC_LINES = float(q[q.category == "cat11_use_of_sold_products"].tco2e.sum() + q[q.line_item.str.startswith("elec_upstream")].tco2e.sum())
plan = {int(k): v for k, v in N["peat"]["plan"].items()}
peat25 = N["peat"]["org_t"]

def ramp(y, start, r):
    return 0.0 if y < start else min(1.0, (y - start + 1) / max(r, 1))

def adopted(s, levers):
    out = {}
    for i, r in levers.iterrows():
        if r.cls == "not_in_inventory" or pd.isna(r.eur_t_central) or r.ab_central <= 0:
            continue
        for y in range(int(r.earliest_start), 2036):
            cost = r.eur_t_central * (interp(s, "n_fertiliser_price_index", y) if i == "L08" else 1.0) - interp(s, "eu_ets2_fuel_price_eur_t", y) * FOSSIL.get(i, 0)
            if cost <= interp(s, "carbon_price_eur_t", y):
                out[i] = y
                break
    return out

def path(s, col="ab_central", force_all=False, drop=()):
    cat = sc[sc.scenario == s].ngfs_category.iloc[0]
    levers = m[~m.index.isin(drop)]
    ad = {i: int(r.earliest_start) for i, r in levers.iterrows() if r.cls != "not_in_inventory"} if force_all else adopted(s, levers)
    rec = []
    for y in range(2025, 2036):
        v = interp(s, "plant_based_demand_index", y)
        b = dict(rc) if y >= 2027 else dict(base)
        bau = {k: b[k] * v for k in b}
        ratio = plan.get(y, np.mean([plan[t] for t in range(2027, 2032)])) / plan[2025]
        bau["flag"] += peat25 * (ratio - 1) * v
        g = 1 - (1 - GRID35[cat]) * (y - 2025) / 10
        bau["s3nf"] -= ELEC_LINES * (1 - g) * v
        ab = dict(s12=0.0, s3nf=0.0, flag=0.0)
        for i, st in ad.items():
            r = levers.loc[i]
            d = r[col] * ramp(y, st, int(r.ramp_years)) * v
            if r.bucket == "s12":
                ab["s12"] += d
            else:
                ab["flag"] += d * r.flag_frac
                ab["s3nf"] += d * (1 - r.flag_frac)
        for k in RATE:
            t = rc[k] * (1 - RATE[k] * (y - 2025))
            rec.append(dict(scenario=s, year=y, bucket=k, bau_t=bau[k], abated_t=ab[k], pathway_t=bau[k] - ab[k], target_t=t, gap_t=bau[k] - ab[k] - t))
    return pd.DataFrame(rec), ad

allp, ads = [], {}
for s in sc.scenario.unique():
    d, ad = path(s)
    allp.append(d); ads[s] = ad
PW = pd.concat(allp); PW.round(1).to_csv(OUT / "B1_pathway.csv", index=False)
show = PW[PW.year.isin([2030, 2032, 2035])].pivot_table(index=["scenario", "bucket"], columns="year", values="gap_t").round(0)
print("Gap to target, t (positive = above target), cost-rule portfolio:\n", show.to_string())
for s, ad in ads.items():
    print(s, "levers adopted", len(ad), "price 2030", interp(s, "carbon_price_eur_t", 2030), "ETS2 2030", interp(s, "eu_ets2_fuel_price_eur_t", 2030), "|", ", ".join(f"{k}:{v}" for k, v in sorted(ad.items())))

MAIN = ["net_zero_2050", "delayed_transition", "current_policies"]
print(PW[(PW.scenario.isin(MAIN)) & (PW.bucket == "flag")].pivot_table(index="year", columns="scenario", values=["pathway_t", "target_t"]).round(0).to_string())
print(PW[(PW.scenario.isin(MAIN)) & (PW.bucket == "s12")].pivot_table(index="year", columns="scenario", values=["pathway_t", "target_t"]).round(0).to_string())

# ---- ceilings: the whole catalogue, every lever on, three bands, with and without the peat reallocation
res = {}
for s in MAIN:
    for lab, col, drop in (("low", "ab_low", ()), ("central", "ab_central", ()), ("high", "ab_high", ()), ("central, no L11", "ab_central", ("L11",)), ("high, no L11", "ab_high", ("L11",))):
        d, _ = path(s, col, True, drop)
        x = d[d.year == 2035].set_index("bucket").gap_t
        res[(s, lab)] = x.to_dict()
ce = pd.DataFrame(res).T.round(0)
print("2035 gap, every catalogue lever on:\n", ce.to_string())
ce.to_csv(OUT / "B1_ceiling_gaps_2035.csv")

# ---- what closes FLAG
mats = ["M101", "M102", "M103", "M104", "M105", "M106", "M107"]
seed_flag = float(q[q.material_id.isin(mats)].flag_t.sum())
g = res[("net_zero_2050", "central")]["flag"]; g2 = res[("net_zero_2050", "central, no L11")]["flag"]; gc = res[("current_policies", "central")]["flag"]
print(f"Bought seed FLAG {seed_flag:.0f} t = {seed_flag / rc['flag'] * 100:.1f}% of recalculated FLAG base")
print(f"FLAG 2035 gap with every lever: {g:.0f} t net zero, {gc:.0f} t current policies; without L11 {g2:.0f} t. As share of bought-seed FLAG: {g / seed_flag * 100:.1f}% to {g2 / seed_flag * 100:.1f}%")

# ---- crush sensitivity: the base-year level matters more than most levers
V = R["volatility"]; rk = {int(k): v for k, v in V["rape_kt"].items()}
r25 = float(q[q.material_id.isin(mats + ["M100"])].tco2e.sum())
for y in (2023, 2024):
    print(f"Crush at the {y} level ({rk[y]:.0f} t vs {rk[2025]:.0f} t): rapeseed lines move {r25 * (rk[y] / rk[2025] - 1):.0f} t, of which FLAG ~{r25 * (rk[y] / rk[2025] - 1) * .86:.0f}")
print(f"Crush mean 2021-25 {np.mean(list(rk.values())):.0f} t; 2025 is {(rk[2025] / np.mean(list(rk.values())) - 1) * 100:.1f}% above it")

# ---- recommended portfolio (cost rule under the lowest price path, then decision levers)
core = adopted("current_policies", m)
print("Adopted even under current policies:", sorted(core))
pp = m.loc[sorted(core)]
print(f"core levers: central {pp.ab_central.sum():.0f} t ({pp[pp.bucket == 's12'].ab_central.sum():.0f} S1+2), net cost {pp.cost_yr_central.sum():.0f} EUR/yr, capex {pp.capex_eur.sum():.0f} EUR")
rec = ["L01", "L03", "L07", "L09", "L11", "L12", "L13", "L16", "L20", "L21", "L22", "L23", "L25", "L28", "L30", "L08", "L19"]
pp = m.loc[rec]
print(f"recommended 17: central {pp.ab_central.sum():.0f} t; low {pp.ab_low.sum():.0f}; high {pp.ab_high.sum():.0f}; EUR/yr {pp.cost_yr_central.sum():.0f}; capex {pp.capex_eur.sum():.0f}; EUR/t {pp.cost_yr_central.sum() / pp.ab_central.sum():.1f}")
print(pp.groupby("bucket")[["ab_low", "ab_central", "ab_high", "cost_yr_central"]].sum().round(0).to_string())

# robust verdict per lever at 2030 prices, across the seven scenarios
verd = []
for i, r in m.iterrows():
    if pd.isna(r.eur_t_central):
        verd.append((i, "not costable")); continue
    ets = [interp(s, "eu_ets2_fuel_price_eur_t", 2030) * FOSSIL.get(i, 0) for s in sc.scenario.unique()]
    pr = [interp(s, "carbon_price_eur_t", 2030) for s in sc.scenario.unique()]
    worst = r.eur_t_worst if pd.notna(r.eur_t_worst) else np.inf
    if worst - min(ets) <= min(pr):
        v = "do in every scenario"
    elif r.eur_t_best - max(ets) > max(pr):
        v = "skip in every scenario"
    else:
        v = "depends on scenario or evidence"
    verd.append((i, v))
vd = pd.DataFrame(verd, columns=["lever_id", "verdict_2030"]).set_index("lever_id")
m2 = m.join(vd); m2.to_csv(OUT / "B2_macc.csv")
print(m2.groupby("verdict_2030").ab_central.agg(["count", "sum"]).round(0).to_string())
print(m2[["verdict_2030", "eur_t_best", "eur_t_central", "eur_t_worst"]].round(0).to_string())
# ---- review tests on the FLAG gap
best = min(v["flag"] for k, v in res.items() if k[1] == "high")
crush24 = r25 * (rk[2024] / rk[2025] - 1) * .86
needed_share = .86 - (best / (RATE["flag"] * 10)) / (seed_flag / .86)
print(f"Most favourable FLAG gap 2035 (all levers at high, L11 counted): {best:.0f} t; with crush also held at the 2024 low {best + crush24 * (1 - RATE['flag'] * 10):.0f} t")
print(f"Bought-seed FLAG share would have to be {needed_share:.3f} instead of 0.86 for that most favourable gap to close")
nz = PW[(PW.scenario == "net_zero_2050") & (PW.year == 2035)].set_index("bucket"); cp = PW[(PW.scenario == "current_policies") & (PW.year == 2035)].set_index("bucket")
print(f"2035 BAU FLAG: net zero {nz.bau_t['flag']:.0f}, current policies {cp.bau_t['flag']:.0f}; abated {nz.abated_t['flag']:.0f} vs {cp.abated_t['flag']:.0f}; demand index {interp('net_zero_2050', 'plant_based_demand_index', 2035):.3f} vs {interp('current_policies', 'plant_based_demand_index', 2035):.3f}")
rng = lambda b, y: (PW[(PW.bucket == b) & (PW.year == y)].gap_t.min(), PW[(PW.bucket == b) & (PW.year == y)].gap_t.max())
g = {f"{b}_{y}": rng(b, y) for b in RATE for y in (2030, 2032, 2035)}
print("Gap range over seven scenarios:", {k: (round(a), round(b)) for k, (a, b) in g.items()})
pp = m.loc[rec]
json.dump(dict(base=base, rc=rc, seed_flag=seed_flag, ceiling={f"{k[0]}|{k[1]}": v for k, v in res.items()}, adopted=ads, best_flag_gap=best, best_flag_gap_low_crush=best + crush24 * (1 - RATE["flag"] * 10), needed_share=needed_share,
               gap_range=g, bau35=dict(nz=nz.bau_t["flag"], cp=cp.bau_t["flag"]), gap35=dict(nz=nz.gap_t["flag"], cp=cp.gap_t["flag"]), demand=dict(nz=interp("net_zero_2050", "plant_based_demand_index", 2035), cp=interp("current_policies", "plant_based_demand_index", 2035)),
               rec=dict(ids=rec, central=pp.ab_central.sum(), low=pp.ab_low.sum(), high=pp.ab_high.sum(), eur_yr=pp.cost_yr_central.sum(), capex=pp.capex_eur.sum(), eur_t=pp.cost_yr_central.sum() / pp.ab_central.sum()),
               crush=dict(y2024=r25 * (rk[2024] / rk[2025] - 1), y2023=r25 * (rk[2023] / rk[2025] - 1), pct_vs_mean=(rk[2025] / np.mean(list(rk.values())) - 1) * 100)), open(OUT / "pathway_summary.json", "w"), indent=1, default=float)
