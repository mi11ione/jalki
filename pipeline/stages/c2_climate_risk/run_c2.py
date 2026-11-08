"""C2 main run: calibration printout, primary (delta) estimates, realisation cross-check, submission CSV.
Writes $CCN_OUT/c2_climate_risk/C2_climate_yield_risk_submission.csv and out/c2_detail.csv."""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import c2lib as C  # noqa: E402
import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
mix = C.parcel_mix_2025()
print(f"2025 contract-parcel mix: {len(mix)} parcels, {mix.area_ha.sum():.0f} ha")
print(mix.groupby(["region", "crop"]).agg(parcels=("parcel_id", "size"), ha=("area_ha", "sum"), irr_share=("irr", "mean")).round(3).to_string())
print("irrigation source:", mix.irr_source.value_counts().to_dict())

df = C.observed()
sc = C.scale_estimates(df)
print("\nR2 sensitivity scale on observed history (s=1: fixed process parameters):")
print(sc.round(3).to_string())
s_used = sc.s_used.to_dict()
sig = C.year_noise(df, s_used)
print("\nR3 year-level noise (log units):")
print(sig.round(4).to_string())

feat = pd.read_parquet(C.OUT / "feat_c2.parquet")
Y = C.index_series(mix, s_used, feat)
Y.to_csv(C.OUT / "index_series.csv", index=False)
prim = C.summarise(Y, sig, fut_prefix="delta_")
real = C.summarise(Y, sig, fut_prefix="real_")
det = prim.merge(real[["region", "crop", "scenario", "mean_yield_change_pct", "p_bad_year"]],
                 on=["region", "crop", "scenario"], suffixes=("", "_real"))
det.to_csv(C.OUT / "c2_detail.csv", index=False)
print("\nPRIMARY (delta method, 30 yrs) with realisation cross-check (20 yrs):")
print(det.round(3).to_string(index=False))
d = det.mean_yield_change_pct - det.mean_yield_change_pct_real
print(f"\ndelta - realisation: mean change MAD {d.abs().mean():.2f} pp (max {d.abs().max():.2f}); "
      f"p_bad MAD {(det.p_bad_year - det.p_bad_year_real).abs().mean():.3f}")

tpl = pd.read_csv(C.D / "tasks/templates/C2_climate_yield_risk_submission.csv")
sub = tpl.drop(columns=["mean_yield_change_pct", "p_bad_year"]).merge(
    prim[["region", "crop", "scenario", "mean_yield_change_pct", "p_bad_year"]], on=["region", "crop", "scenario"], how="left")
sub["mean_yield_change_pct"] = sub.mean_yield_change_pct.round(2)
sub["p_bad_year"] = sub.p_bad_year.round(3)
assert len(sub) == 18 and sub.notna().all().all() and list(sub.columns) == list(tpl.columns)
sub.to_csv(os.path.join(C.HERE, "C2_climate_yield_risk_submission.csv"), index=False)
print(f"\nwrote C2_climate_yield_risk_submission.csv ({len(sub)} rows, columns {list(sub.columns)})")
print(sub.to_string(index=False))
