"""Process stress features for C2, same fixed crop-process definitions as stages/c1_yields/features.py
(copied logic, unchanged parameters), over these weather series:
  hist          : historical 1991-2026 (baseline 1991-2020; 2012-2026 used for calibration)
  real_<ssp>    : the single given SSP realisation, 2041-2060
  delta_<ssp>   : historical 1991-2020 daily weather + stated 2041-2060 signals (climate_change_signals.csv):
                  tmean/tmax + delta_tmean_c(month); precip x precip_factor(month);
                  PET x (1 + K * delta_tmean_c), K (per degC) fitted on the realisations (signals.py out/pet_ratio.csv).
Writes out/feat_c2.parquet with column 'series'."""
from ccn_paths import PACKAGE, stage_dir
import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "c1_yields"))
import boot  # noqa: E402
from pathlib import Path
import numpy as np
import pandas as pd

D = Path(boot.DATA)
OUT = stage_dir("c2_climate_risk") / "out"
OUT.mkdir(exist_ok=True)
CROP = {
    "pea":         dict(thr=7.0, gflo=420, gmat=780,  dead=183),
    "turnip_rape": dict(thr=6.0, gflo=500, gmat=1150, dead=213),
    "potato":      dict(thr=8.0, gflo=450, gmat=1250, dead=213),
    "carrot":      dict(thr=7.0, gflo=600, gmat=1400, dead=228),
    "spinach":     dict(thr=6.0, gflo=250, gmat=450,  dead=152),
}
SOIL_CAP = {"sand": 60.0, "fine_sand": 110.0, "silt": 170.0, "clay": 140.0, "organic": 200.0}
APR1, EARLY, LATE, ND = 31, 40, 106, 245

pr = pd.read_csv(OUT / "pet_ratio.csv")
K = float(np.sum((pr.pet_ratio - 1) * pr.dT_real) / np.sum(pr.dT_real ** 2))
print(f"PET sensitivity K = {K:.4f} per degC (through-origin fit on {len(pr)} realisation region x scenario x months)")
sg = pd.read_csv(D / "data/04_climate/climate_change_signals.csv")

w = pd.read_parquet(D / "data/04_climate/weather_daily_1991_2060.parquet",
                    columns=["cell_id", "date", "tmean_c", "tmax_c", "precip_mm", "pet_mm", "scenario"])
w["year"] = w.date.dt.year
w["month"] = w.date.dt.month
w["d"] = (w.date - pd.to_datetime(w.year.astype(str) + "-03-01")).dt.days
w = w[(w.d >= 0) & (w.d < ND)]

series = {"hist": w[w.scenario == "historical"].copy()}
for s in ("ssp126", "ssp245", "ssp585"):
    series[f"real_{s}"] = w[(w.scenario == s) & w.year.between(2041, 2060)].copy()
    h = w[(w.scenario == "historical") & w.year.between(1991, 2020)].copy()
    g = sg[sg.scenario == s].set_index("month")
    dT = h.month.map(g.delta_tmean_c).values
    h["tmean_c"] = h.tmean_c + dT
    h["tmax_c"] = h.tmax_c + dT
    h["precip_mm"] = h.precip_mm * h.month.map(g.precip_factor).values
    h["pet_mm"] = h.pet_mm * (1 + K * dT)
    series[f"delta_{s}"] = h


def first_true(mask, default):
    return np.where(mask.any(1), mask.argmax(1), default)


def features(wx: pd.DataFrame, name: str) -> pd.DataFrame:
    wx = wx.set_index(["cell_id", "year", "d"]).sort_index()
    cy = wx.index.droplevel(2).unique()
    assert len(wx) == len(cy) * ND
    T = wx.tmean_c.values.reshape(len(cy), ND)
    TX = wx.tmax_c.values.reshape(len(cy), ND)
    P = wx.precip_mm.values.reshape(len(cy), ND)
    PET = wx.pet_mm.values.reshape(len(cy), ND)
    N = len(cy)
    dd = np.arange(ND)[None, :]
    roll5 = pd.DataFrame(T.T).rolling(5).mean().T.values
    rows = []
    for crop, cp in CROP.items():
        ok = (roll5 >= cp["thr"]) & (dd >= EARLY)
        sow = np.minimum(first_true(ok, LATE), LATE)
        gdd = np.cumsum(np.where(dd > sow[:, None], np.maximum(T - 5.0, 0.0), 0.0), 1)
        flo = np.minimum(first_true(gdd >= cp["gflo"], cp["dead"]), cp["dead"])
        gdd_dead = gdd[:, cp["dead"]]
        mat = np.minimum(first_true(gdd >= cp["gmat"], cp["dead"]), cp["dead"])
        imm = np.clip(1 - gdd_dead / cp["gmat"], 0, 1)
        ramp = np.clip((dd - sow[:, None]) / np.maximum(flo - sow, 1)[:, None], 0, 1)
        kc = np.where(dd < sow[:, None], 0.3, 0.3 + 0.75 * ramp)
        kc = np.where(dd > mat[:, None], 0.4, kc)
        etc = PET * kc
        heat_win = (dd >= (flo - 5)[:, None]) & (dd <= (flo + 20)[:, None])
        heat = ((TX >= 27) & heat_win).sum(1)
        hrain = (P * ((dd > (mat - 10)[:, None]) & (dd <= mat[:, None]))).sum(1)
        blight = ((T >= 15) & (P >= 0.5) & (dd >= 122) & (dd <= 183)).sum(1)
        may_tx = TX[:, 61:92].mean(1)
        veg = (dd > sow[:, None]) & (dd <= flo[:, None])
        rep = (dd > flo[:, None]) & (dd <= mat[:, None])
        for soil, cap in SOIL_CAP.items():
            S = np.full(N, cap)
            stress = np.zeros((N, ND))
            wet = np.zeros((N, ND), bool)
            for d in range(APR1, ND):
                e = etc[:, d]
                aet = e * np.minimum(1.0, S / (0.5 * cap))
                S = S + P[:, d] - aet
                wet[:, d] = S > cap + 5
                S = np.clip(S, 0, cap)
                stress[:, d] = np.where(e > 0.05, 1 - aet / np.maximum(e, 1e-9), 0.0)
            rows.append(pd.DataFrame(dict(
                series=name, cell_id=cy.get_level_values(0), year=cy.get_level_values(1), crop=crop, soil=soil,
                imm=imm, gdd_season=gdd_dead,
                dstress_veg=(stress * veg).sum(1) / np.maximum(veg.sum(1), 1),
                dstress_rep=(stress * rep).sum(1) / np.maximum(rep.sum(1), 1),
                heat_flo=heat, wet_days=(wet & (dd > sow[:, None]) & (dd <= (sow + 30)[:, None])).sum(1),
                harvest_rain=hrain, blight_days=blight, may_tmax=may_tx)))
    return pd.concat(rows, ignore_index=True)


allf = pd.concat([features(v, k) for k, v in series.items()], ignore_index=True)
allf.to_parquet(OUT / "feat_c2.parquet", index=False)
print("features", allf.shape)
print(allf[allf.soil == "clay"].groupby(["series", "crop"])[["imm", "dstress_rep", "heat_flo", "blight_days"]].mean().unstack("crop").round(2).to_string())

# consistency: hist 2012-2026 features must equal c1-yield-b's (same code path) -> guards against a copy slip
c1 = pd.read_parquet(Path(boot.HERE) / "out/feat_process.parquet")
c1 = c1[c1.year <= 2026]
m = c1.merge(allf[allf.series == "hist"], on=["cell_id", "year", "crop", "soil"], suffixes=("_c1", ""))
dif = max(float((m[f"{c}_c1"] - m[c]).abs().max()) for c in ("imm", "dstress_veg", "dstress_rep", "heat_flo", "wet_days", "blight_days"))
print(f"max |feature diff| vs c1-yield-b on {len(m)} shared rows: {dif:.2e}")
assert dif < 1e-9
