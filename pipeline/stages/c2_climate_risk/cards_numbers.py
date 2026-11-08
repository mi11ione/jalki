"""Prints every number used in the C2 cards and writes $CCN_OUT/c2_climate_risk/results.json.
Reads outputs of: signals.py (out/pet_ratio.csv), run_c2.py (out/c2_detail.csv, submission CSV),
checks2.py (out/drivers_ssp585.csv). Run those first (order: facts, signals, feat2, run_c2, checks2)."""
import json
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import c2lib as C  # noqa: E402
import numpy as np
import pandas as pd

det = pd.read_csv(C.OUT / "c2_detail.csv")
pr = pd.read_csv(C.OUT / "pet_ratio.csv")
drv = pd.read_csv(C.OUT / "drivers_ssp585.csv").set_index(["region", "crop"])
sub = pd.read_csv(os.path.join(C.HERE, "C2_climate_yield_risk_submission.csv"))
mix = C.parcel_mix_2025()
r = lambda reg, crop, s: det[(det.region == reg) & (det.crop == crop) & (det.scenario == s)].iloc[0]

print("CARD c2_01 FI turnip rape")
ha = mix.groupby("crop").area_ha.sum()
print(f"  turnip rape 2025 contract area {ha['turnip_rape']:.0f} ha = {ha['turnip_rape'] / mix.area_ha.sum():.3f} of {mix.area_ha.sum():.0f} ha")
for s in C.SSPS:
    x = r("FI_SW", "turnip_rape", s)
    print(f"  {s}: change {x.mean_yield_change_pct:+.2f}% [{x.ci_lo:+.2f}, {x.ci_hi:+.2f}]  p_bad {x.p_bad_year:.3f} vs 1991-2020 {x.p_bad_1991_2020:.3f}"
          f" (x{x.p_bad_year / x.p_bad_1991_2020:.2f}); realisation {x.mean_yield_change_pct_real:+.2f}% / {x.p_bad_year_real:.3f}")
others = det[(det.crop != "turnip_rape") & (det.scenario == "ssp245")]
print(f"  next-worst ssp245 change among other rows: {others.mean_yield_change_pct.min():+.2f}%")

print("CARD c2_02 single realisation vs stated signal")
g = pr[pr.month.between(4, 9)].groupby(["scenario", "region"])[["dT_real", "dT_sig", "pf_real", "pf_sig"]].mean()
print(g.round(3).to_string())
d = det.mean_yield_change_pct - det.mean_yield_change_pct_real
print(f"  delta-vs-realisation |diff| mean {d.abs().mean():.2f} pp, max {d.abs().max():.2f} pp; as share of the 5 pp zero-credit band {d.abs().mean() / 5:.2f}")
flips = det[np.sign(det.mean_yield_change_pct) != np.sign(det.mean_yield_change_pct_real)]
print(f"  sign flips: {len(flips)} of {len(det)} rows")
print(flips[["region", "crop", "scenario", "mean_yield_change_pct", "mean_yield_change_pct_real"]].round(2).to_string(index=False))

print("CARD c2_03 drivers at ssp585 (pp, delta method)")
print(drv[["heat_flower", "drought_rep", "drought_veg", "immaturity", "pollen_beetle", "blight"]].round(2).to_string())
nonsp = drv.drop(index=("FI_SW", "spinach"))
print(f"  heat range excl. spinach {nonsp.heat_flower.min():.2f}..{nonsp.heat_flower.max():.2f}; drought_rep range {nonsp.drought_rep.min():.2f}..{nonsp.drought_rep.max():.2f}")
print(f"  heat loss > reproductive-drought loss in {int((drv.heat_flower < drv.drought_rep).sum())}/{len(drv)} rows")
se_irr = mix[(mix.region == "SE_SKANE")].irr.mean()
print(f"  SE pea 2025 irrigated share {se_irr:.3f}; SE heat {drv.loc[('SE_SKANE', 'pea'), 'heat_flower']:.2f} vs drought_rep {drv.loc[('SE_SKANE', 'pea'), 'drought_rep']:.2f}")

print("CARD c2_05 tail grows faster than the mean")
for reg, crop in (("FI_SW", "pea"), ("SE_SKANE", "pea"), ("FI_SW", "potato")):
    for s in ("ssp245", "ssp585"):
        x = r(reg, crop, s)
        print(f"  {reg} {crop} {s}: change {x.mean_yield_change_pct:+.2f}%  p_bad {x.p_bad_1991_2020:.3f} -> {x.p_bad_year:.3f}")
rise = det.p_bad_year - det.p_bad_1991_2020
print(f"  rows with p_bad rising: {int((rise > 0.0005).sum())}/{len(det)}; mean change all rows {det.mean_yield_change_pct.mean():+.2f}%")
nullp = (sub.p_bad_year - 0.10).abs()
print(f"  null p_bad=0.10 vs ours: |diff| mean {nullp.mean():.3f}; rows where ours < 0.05: {int((sub.p_bad_year < 0.05).sum())}/18")

res = dict(
    task="C2", note="Synthetic Apetit twin (since AI 2026 package). Not Apetit's real yields or risks.",
    method=dict(model="stages/c1_yields fixed-parameter process model (lib.pure_process_logw), management fixed at 2025",
                weather_primary="delta method: stated 2041-2060 signals on 1991-2020 daily weather (30 years)",
                weather_crosscheck="single given SSP realisation 2041-2060 (20 years)",
                parcel_mix="2025 declared contract parcels (2410 parcels)",
                rules=["R1 delta primary", "R2 scale s only if season-clustered CI excludes 1", "R3 sigma_y = year noise beyond sampling", "R4 area weights"]),
    submission_file="submission/C2_climate_yield_risk_submission.csv",
    submission=sub.to_dict(orient="records"),
    detail=det.round(4).to_dict(orient="records"),
    crosscheck=dict(delta_vs_realisation_mad_pp=round(float(d.abs().mean()), 3), sign_flips=int(len(flips))),
)
with open(os.path.join(C.HERE, "results.json"), "w") as f:
    json.dump(res, f, indent=1)
print("wrote results.json")
