"""Crop-weather process features per (climate cell, season, crop, soil class), and raw monthly
weather per (cell, season) for the gradient-boosted alternative.

Weather: historical for 2012-2026, scenario ssp245 for 2027-2031 (TASKS_AND_SCORING.md C1 setting).
Process model (own parameters, fixed before any yield was read; agronomic round numbers):
  * sowing: first day from 10 Apr whose 5-day mean T >= crop threshold (fallback 15 Jun);
  * phenology: growing degree days, base 5 C, to flowering/sensitive stage and maturity;
  * soil water: daily bucket per soil class, full on 1 Apr; AET = PET*Kc*min(1, S/(0.5*cap));
  * stress indices: drought (1 - AET/ETc) in vegetative and reproductive stages, heat days
    (Tmax >= 27 C) around flowering, waterlogging (rain 20 d after sowing), rain before harvest,
    immaturity at the crop deadline, late-blight days (Jul-Aug T>=15 & rain), May warmth (pollen beetle).
Writes $CCN_OUT/c1_yields/out/feat_process.parquet and out/feat_monthly.parquet.
"""
import sys, os; sys.path.append(os.path.dirname(os.path.abspath(__file__))); import boot
from pathlib import Path
import numpy as np
import pandas as pd

D = Path(boot.DATA)
OUT = Path(boot.HERE) / "out"
OUT.mkdir(exist_ok=True)
YEARS = list(range(2012, 2032))

# crop: sow threshold C, GDD to sensitive stage, GDD to maturity, deadline (day index from 1 Mar)
CROP = {
    "pea":         dict(thr=7.0, gflo=420, gmat=780,  dead=183),   # 31 Aug (vining pea)
    "turnip_rape": dict(thr=6.0, gflo=500, gmat=1150, dead=213),   # 30 Sep
    "potato":      dict(thr=8.0, gflo=450, gmat=1250, dead=213),
    "carrot":      dict(thr=7.0, gflo=600, gmat=1400, dead=228),   # 15 Oct
    "spinach":     dict(thr=6.0, gflo=250, gmat=450,  dead=152),   # 31 Jul
}
SOIL_CAP = {"sand": 60.0, "fine_sand": 110.0, "silt": 170.0, "clay": 140.0, "organic": 200.0}  # plant-available mm
APR1, EARLY, LATE = 31, 40, 106   # day indices from 1 Mar: 1 Apr, 10 Apr, 15 Jun

w = pd.read_parquet(D / "data/04_climate/weather_daily_1991_2060.parquet",
                    columns=["cell_id", "date", "tmean_c", "tmax_c", "precip_mm", "pet_mm", "scenario"])
w["year"] = w.date.dt.year
w = w[((w.scenario == "historical") & w.year.between(2012, 2026)) | ((w.scenario == "ssp245") & w.year.between(2027, 2031))]
w["d"] = (w.date - pd.to_datetime(w.year.astype(str) + "-03-01")).dt.days
w = w[(w.d >= 0) & (w.d < 245)]
cells = sorted(w.cell_id.unique())
cy = pd.MultiIndex.from_product([cells, YEARS], names=["cell_id", "year"])
w = w.set_index(["cell_id", "year", "d"]).sort_index()
assert len(w) == len(cy) * 245, (len(w), len(cy) * 245)
T = w.tmean_c.values.reshape(len(cy), 245)
TX = w.tmax_c.values.reshape(len(cy), 245)
P = w.precip_mm.values.reshape(len(cy), 245)
PET = w.pet_mm.values.reshape(len(cy), 245)
N, ND = T.shape
dd = np.arange(ND)[None, :]


def first_true(mask, default):
    has = mask.any(1)
    return np.where(has, mask.argmax(1), default)


rows = []
roll5 = pd.DataFrame(T.T).rolling(5).mean().T.values
for crop, cp in CROP.items():
    ok = (roll5 >= cp["thr"]) & (dd >= EARLY)
    sow = np.minimum(first_true(ok, LATE), LATE)
    gdd_d = np.where(dd > sow[:, None], np.maximum(T - 5.0, 0.0), 0.0)
    gdd = np.cumsum(gdd_d, 1)
    flo = first_true(gdd >= cp["gflo"], cp["dead"])
    flo = np.minimum(flo, cp["dead"])
    gdd_dead = gdd[:, cp["dead"]]
    mat = np.minimum(first_true(gdd >= cp["gmat"], cp["dead"]), cp["dead"])
    imm = np.clip(1 - gdd_dead / cp["gmat"], 0, 1)
    # crop coefficient: 0.3 bare soil before sowing, ramps to 1.05 at flowering, 1.05 to maturity, then 0.4
    ramp = np.clip((dd - sow[:, None]) / np.maximum(flo - sow, 1)[:, None], 0, 1)
    kc = np.where(dd < sow[:, None], 0.3, 0.3 + 0.75 * ramp)
    kc = np.where(dd > mat[:, None], 0.4, kc)
    etc = PET * kc
    heat_win = (dd >= (flo - 5)[:, None]) & (dd <= (flo + 20)[:, None])
    heat = ((TX >= 27) & heat_win).sum(1)
    heat_season = ((TX >= 27) & (dd > sow[:, None]) & (dd <= mat[:, None])).sum(1)
    wlog_rain = (P * ((dd > sow[:, None]) & (dd <= (sow + 20)[:, None]))).sum(1)
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
            wet[:, d] = S > cap + 5          # drainage day: soil at capacity with surplus
            S = np.clip(S, 0, cap)
            stress[:, d] = np.where(e > 0.05, 1 - aet / np.maximum(e, 1e-9), 0.0)
        vs = (stress * veg).sum(1) / np.maximum(veg.sum(1), 1)
        rs = (stress * rep).sum(1) / np.maximum(rep.sum(1), 1)
        wetdays = (wet & (dd > sow[:, None]) & (dd <= (sow + 30)[:, None])).sum(1)
        df = pd.DataFrame(dict(cell_id=cy.get_level_values(0), year=cy.get_level_values(1), crop=crop, soil=soil,
                               sow_doy=sow + 60, flo_d=flo, mat_d=mat, imm=imm, gdd_season=gdd_dead,
                               dstress_veg=vs, dstress_rep=rs, heat_flo=heat, heat_season=heat_season,
                               wlog_rain=wlog_rain, wet_days=wetdays, harvest_rain=hrain,
                               blight_days=blight, may_tmax=may_tx))
        rows.append(df)
fp = pd.concat(rows, ignore_index=True)
fp.to_parquet(OUT / "feat_process.parquet", index=False)
print("process features", fp.shape)
print(fp.groupby(["crop"])[["sow_doy", "flo_d", "mat_d", "imm", "dstress_veg", "dstress_rep", "heat_flo", "wet_days"]].mean().round(2))
print("year means (pea, clay):")
print(fp[(fp.crop == "pea") & (fp.soil == "clay")].groupby("year")[["dstress_rep", "heat_flo", "imm", "gdd_season"]].mean().round(2).T)

mo = pd.read_csv(D / "data/04_climate/weather_monthly_1991_2060.csv")
mo = mo[((mo.scenario == "historical") & mo.year.between(2012, 2026)) | ((mo.scenario == "ssp245") & mo.year.between(2027, 2031))]
mo = mo[mo.month.between(4, 9)]
mo["cwb"] = mo.precip_mm - mo.pet_mm
wide = mo.pivot_table(index=["cell_id", "year"], columns="month",
                      values=["tmean_c", "tmax_c_max", "precip_mm", "pet_mm", "hot_days_tmax_ge_27", "cwb"])
wide.columns = [f"{a}_m{b}" for a, b in wide.columns]
wide = wide.reset_index()
wide.to_parquet(OUT / "feat_monthly.parquet", index=False)
print("monthly features", wide.shape)
