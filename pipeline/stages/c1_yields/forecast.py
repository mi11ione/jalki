"""C1 forecast 2027-2031 (SSP2-4.5 weather realisation) with the selected model (grid.py rule):
proc_pure, trend none, fitted on all observed seasons (FI 2012-2026, SE 2018-2026).
Irrigation: each farm x crop keeps its latest observed status (no new irrigation assumed); farms with no
record get the crop x region irrigated share of 2024-2026 as an expectation.
Writes $CCN_OUT/c1_yields/C1_yields_2027_2031_submission.csv (template format) and out/forecast_compare.csv."""
import sys, os; sys.path.append(os.path.dirname(os.path.abspath(__file__))); import boot
from pathlib import Path
import numpy as np
import pandas as pd
import lib

D = Path(boot.DATA)
tpl = pd.read_csv(D / "tasks/templates/C1_yields_2027_2031_submission.csv")
rec, px, _ = lib.training_records()
cols = lib.PROC_FEATS + [f"soil_{s}" for s in lib.SOILS] + ["clay_pct_soilmap", "logw_pure"] + lib.monthly_cols(px)
df = rec.join(lib.aggregate(px, cols), on="rec_id").reset_index(drop=True)

# irrigation status for the plan
last = rec.sort_values("year").groupby(["farm_id", "crop"]).irr.last()
share = rec[rec.year >= 2024].groupby(["region", "crop"]).irr.mean()
pc = lib.parcel_cells()[["parcel_id", "cell_id", "soil_class_soilmap", "clay_pct_soilmap"]]
t = tpl.merge(pc, on="parcel_id", how="left")
assert t.cell_id.notna().all()
irr = pd.Series(list(zip(t.farm_id, t.crop))).map(last)
known = irr.notna().values
t["irr"] = np.where(known, irr.values, pd.Series(list(zip(t.region, t.crop))).map(share).values)
t["rec_id"] = np.arange(len(t))
tx = lib.parcel_features(t)
tx = tx.sort_values("rec_id").reset_index(drop=True)
assert len(tx) == len(tpl)

hist_fc = set(zip(rec.farm_id, rec.crop))
has_hist = np.array([(f, c) in hist_fc for f, c in zip(tx.farm_id, tx.crop)])
print(f"template rows {len(tx)}; with farm x crop yield history {has_hist.mean():.3f}; irrigation status known {known.mean():.3f}")
print("cold-start rows by region x crop:", tx.assign(cold=~has_hist).groupby(["region", "crop"]).cold.mean().round(3).to_dict())

preds = {}
for k in ("proc_pure", "proc_cal", "gbm_raw", "gbm_proc", "trend_farm"):
    preds[k] = lib.fit_predict(df, tx, k, trend_mode="none")
preds["baseline"] = lib.fit_predict(df, tx, "baseline")
sel = preds["proc_pure"]
assert np.isfinite(sel).all() and (sel > 0).all()

sub = tpl.copy()
sub["yield_t_ha_pred"] = np.round(sel, 3)
outp = Path(boot.HERE) / "C1_yields_2027_2031_submission.csv"
sub.to_csv(outp, index=False)
print(f"wrote {outp.name}: {len(sub)} rows, columns {list(sub.columns)}, NaN {int(sub.yield_t_ha_pred.isna().sum())}")

# production comparison by region x crop x year (t), selected vs alternatives
cmp = tx[["region", "crop", "year", "area_ha"]].copy()
for k, v in preds.items():
    cmp[k] = v * tx.area_ha.values
g = cmp.groupby(["region", "crop", "year"]).sum()
for k in preds:
    g[f"{k}_t_ha"] = g[k] / g.area_ha
g.round(3).to_csv(lib.OUT / "forecast_compare.csv")
print("\nForecast yield t/ha by region x crop x season (selected proc_pure), with package baseline:")
show = g[["proc_pure_t_ha", "baseline_t_ha", "gbm_raw_t_ha"]].unstack("year")
print(show.round(2).to_string())
pct = (g.proc_pure / g.baseline - 1) * 100
print("\nSelected vs package baseline, production difference % by region x crop x season:")
print(pct.unstack("year").round(1).to_string())
pr = (g.proc_pure / g.gbm_raw - 1) * 100
print(f"\nSelected vs gbm_raw production difference: mean abs {pr.abs().mean():.1f} %, max abs {pr.abs().max():.1f} %")
tot = g.groupby(level=[0, 1])[["proc_pure", "baseline"]].sum()
tot["diff_pct"] = (tot.proc_pure / tot.baseline - 1) * 100
print("\n5-season production totals (t), selected vs baseline:")
print(tot.round(1).to_string())
hist = df.assign(p=df.yield_t_ha * df.area_ha).groupby(["region", "crop"]).apply(lambda x: x.p.sum() / x.area_ha.sum(), include_groups=False)
print("\nobserved area-weighted mean yield 2012-2026 (t/ha):", hist.round(2).to_dict())
yr = g.groupby("year")[["proc_pure"]].sum()
print("pea FI+SE worst forecast season:", g.loc[(slice(None), "pea", slice(None)), "proc_pure_t_ha"].round(2).to_dict())
