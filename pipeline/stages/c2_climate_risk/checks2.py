"""review checks on the C2 estimates.
 H1 history: observed 2012-2026 bad seasons (aggregate region x crop yield < 80 % of its 2012-26 mean) vs model
    expectation for the same seasons (2025 mix, hist weather, sigma_y), and observed vs modelled anomaly sd.
 H2 parameter sensitivity: s = 1 everywhere (pure fixed process parameters) instead of the R2 rule.
 H3 aggregation sensitivity: production-weighted (area x farm mean-yield ratio) instead of area.
 H4 scenario ordering: loss ssp126 <= ssp245 <= ssp585 per row (delta and realisation).
 H5 drivers: change in each stress term's mean log-factor, delta_ssp585 vs hist 1991-2020, per region x crop.
 H6 comparator: package null ('no change', p_bad 0.10) and a history-only rule (observed 2012-26 bad-season share)."""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import c2lib as C  # noqa: E402
import lib  # noqa: E402
import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
mix = C.parcel_mix_2025()
df = C.observed()
sc = C.scale_estimates(df)
s_used = sc.s_used.to_dict()
sig = C.year_noise(df, s_used)
feat = pd.read_parquet(C.OUT / "feat_c2.parquet")
Y = C.index_series(mix, s_used, feat)
prim = C.summarise(Y, sig)

# H1
obs = df.assign(p=df.yield_t_ha * df.area_ha).groupby(["region", "crop", "year"])[["p", "area_ha"]].sum()
obs["y"] = obs.p / obs.area_ha
rows = []
for (reg, crop), g in obs.groupby(level=[0, 1]):
    yo = g.y.values
    yrs = g.index.get_level_values(2).values
    bad_obs = int(np.sum(yo < 0.8 * yo.mean()))
    ym = Y[(Y.series == "hist") & (Y.region == reg) & (Y.crop == crop) & Y.year.isin(yrs)].sort_values("year").Y.values
    sy = float(sig.loc[(reg, crop), "sigma_y"])
    exp_bad = float(np.sum(C.phi((np.log(0.8 * ym.mean()) - np.log(ym)) / sy)))
    rows.append(dict(region=reg, crop=crop, seasons=len(yo), bad_observed=bad_obs, bad_expected_model=round(exp_bad, 2),
                     sd_log_obs=np.std(np.log(yo), ddof=1), sd_log_model=np.sqrt(np.var(np.log(ym), ddof=1) + sy ** 2),
                     corr_obs_model=np.corrcoef(np.log(yo), np.log(ym))[0, 1]))
h1 = pd.DataFrame(rows)
print("H1 history 2012-2026 (FI) / 2018-2026 (SE):")
print(h1.round(3).to_string(index=False))
print(f"  total bad seasons observed {h1.bad_observed.sum()} vs model-expected {h1.bad_expected_model.sum():.2f} over {h1.seasons.sum()} region-crop-seasons")

# H2
Y1 = C.index_series(mix, {}, feat)
sig1 = C.year_noise(df, {})
p1 = C.summarise(Y1, sig1)
d2 = prim.merge(p1, on=["region", "crop", "scenario"], suffixes=("", "_s1"))
d2["d_change"] = d2.mean_yield_change_pct_s1 - d2.mean_yield_change_pct
d2["d_pbad"] = d2.p_bad_year_s1 - d2.p_bad_year
print("\nH2 s=1 everywhere minus R2 rule:")
print(d2[["region", "crop", "scenario", "mean_yield_change_pct", "mean_yield_change_pct_s1", "p_bad_year", "p_bad_year_s1"]].round(3).to_string(index=False))
print(f"  MAD change {d2.d_change.abs().mean():.2f} pp (max {d2.d_change.abs().max():.2f}); MAD p_bad {d2.d_pbad.abs().mean():.3f}")

# H3
fm = df.groupby(["farm_id", "crop"]).yield_t_ha.mean()
cm = df.groupby(["region", "crop"]).yield_t_ha.mean()
mix3 = mix.copy()
fr = pd.Series(list(zip(mix3.farm_id, mix3.crop))).map(fm).values / pd.Series(list(zip(mix3.region, mix3.crop))).map(cm).values
mix3["fw"] = np.where(np.isnan(fr), 1.0, fr)
Y3 = C.index_series(mix3, s_used, feat, weight="fw")
p3 = C.summarise(Y3, sig)
d3 = (p3.mean_yield_change_pct - prim.mean_yield_change_pct)
print(f"\nH3 production- vs area-weighted: MAD change {d3.abs().mean():.3f} pp (max {d3.abs().max():.3f}); "
      f"MAD p_bad {(p3.p_bad_year - prim.p_bad_year).abs().mean():.4f}")

# H4
real = C.summarise(Y, sig, fut_prefix="real_")
for lab, t in (("delta", prim), ("realisation", real)):
    piv = t.pivot_table(index=["region", "crop"], columns="scenario", values="mean_yield_change_pct")
    ok = ((piv.ssp126 >= piv.ssp245) & (piv.ssp245 >= piv.ssp585))
    print(f"H4 {lab}: monotone loss ssp126>=ssp245>=ssp585 in {int(ok.sum())}/{len(ok)} region x crop rows")

# H5
x = mix.merge(feat[feat.series.isin(["hist", "delta_ssp585"])], left_on=["cell_id", "crop", "soil_class_soilmap"],
              right_on=["cell_id", "crop", "soil"])
x = x[(x.series == "delta_ssp585") | x.year.between(1991, 2020)]
relief = 1 - lib.IRR_RELIEF * x.irr.values
clayish = x.soil.isin(["clay", "silt"]).astype(float).values
terms = dict(
    drought_veg=1 - 0.25 * x.dstress_veg.values * relief, drought_rep=1 - 0.50 * x.dstress_rep.values * relief,
    heat_flower=1 - 0.03 * np.minimum(x.heat_flo.values, 10), immaturity=1 - x.imm.values,
    waterlog=1 - 0.03 * np.minimum(x.wet_days.values, 10) * clayish, harvest_rain=1 - 0.001 * np.maximum(x.harvest_rain.values - 30, 0),
    blight=1 - np.where(x.crop.values == "potato", 0.004 * x.blight_days.values, 0.0),
    pollen_beetle=1 - np.where(x.crop.values == "turnip_rape", 0.02 * np.maximum(x.may_tmax.values - 15, 0), 0.0))
s = np.array([s_used.get(k, 1.0) for k in zip(x.region, x.crop)])
for k, v in terms.items():
    x[k] = s * np.log(np.clip(v, 0.05, 1.0)) * x.area_ha
t5 = x.groupby(["region", "crop", "series"])[list(terms) + ["area_ha"]].sum()
t5 = t5[list(terms)].div(t5.area_ha, axis=0)
dlt = (t5.xs("delta_ssp585", level=2) - t5.xs("hist", level=2)) * 100
print("\nH5 change in mean log-factor x100 (~% points), delta_ssp585 vs hist 1991-2020 (negative = more loss):")
print(dlt.round(2).to_string())
dlt.to_csv(C.OUT / "drivers_ssp585.csv")

# H6
null_change, null_p = 0.0, 0.10
hist_rule = h1.set_index(["region", "crop"]).eval("bad_observed / seasons")
cmp = prim[["region", "crop", "scenario", "mean_yield_change_pct", "p_bad_year"]].copy()
cmp["p_hist_rule"] = [hist_rule[(r, c)] for r, c in zip(cmp.region, cmp.crop)]
print("\nH6 comparators: null (0 %, 0.10) and history rule (observed 2012-26 bad-season share):")
print(cmp.round(3).to_string(index=False))
print(f"  model vs null: mean |change| {cmp.mean_yield_change_pct.abs().mean():.2f} pp; mean |p_bad - 0.10| {(cmp.p_bad_year - null_p).abs().mean():.3f}")
pe = prim.assign(pe=prim.p_bad_year - prim.p_bad_1991_2020)
print(f"  p_bad rise vs own 1991-2020 rate: mean {pe.pe.mean():.3f}, range {pe.pe.min():.3f}..{pe.pe.max():.3f}")
fi_pea = prim[(prim.crop == "pea")].set_index(["region", "scenario"]).mean_yield_change_pct
print("  pea change FI vs SE by SSP:", {s_: (round(fi_pea[("FI_SW", s_)], 2), round(fi_pea[("SE_SKANE", s_)], 2)) for s_ in C.SSPS})
