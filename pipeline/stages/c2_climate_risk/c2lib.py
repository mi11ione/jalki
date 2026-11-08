"""C2 core: 2025 contract-parcel mix, calibration on observed history, aggregate yield-index series.

Model (reused from stages/c1_yields, selected there by a pre-registered rule): fixed-parameter multiplicative
stress model, log W = lib.pure_process_logw(features, irrigation). Management fixed at 2025 (no technology
trend, 2025 irrigation status), as the C2 truth definition states ("2025 contract-parcel mix and current
irrigation and management").

Rules fixed BEFORE any C2 output was computed (logged in output.md):
  R1 primary weather = delta method (stated signals on 1991-2020); single realisation = cross-check only.
  R2 sensitivity scale s per region x crop: use the observed-history estimate (clipped 0..1.5) only if its 95 % CI
     excludes 1; otherwise s = 1 (the fixed process parameters).
  R3 year-level noise sigma_y = sqrt(max(0, var(detrended year effects) - mean sampling variance)), per region x crop.
     p_bad_year = mean over years of Phi((log(0.8 m) - log Y_t) / sigma_y)  (indicator if sigma_y = 0).
  R4 aggregation weight = parcel area (2025 declared contract parcels).
"""
from ccn_paths import PACKAGE, stage_dir
import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "c1_yields"))
import boot  # noqa: E402
from math import erf, sqrt
from pathlib import Path
import numpy as np
import pandas as pd
import lib  # stages/c1_yields/lib.py

D = Path(boot.DATA)
HERE = str(stage_dir("c2_climate_risk"))
OUT = Path(HERE) / "out"
OUT.mkdir(exist_ok=True)
CROPS = ["pea", "potato", "carrot", "spinach", "turnip_rape"]
SSPS = ["ssp126", "ssp245", "ssp585"]


def phi(z):
    return 0.5 * (1 + np.vectorize(erf)(np.asarray(z, float) / sqrt(2)))


def parcel_mix_2025():
    ch = pd.read_csv(D / "data/03_farming/parcel_crop_history_and_plan.csv")
    ch = ch[(ch.status == "declared") & (ch.year == 2025) & ch.crop.isin(CROPS)][["parcel_id", "farm_id", "crop"]]
    pc = lib.parcel_cells()[["parcel_id", "region", "area_ha", "cell_id", "soil_class_soilmap"]]
    m = ch.merge(pc, on="parcel_id")
    m = m[(m.region == "FI_SW") | (m.crop == "pea")].copy()
    # irrigation: 2025 farm x crop status -> latest earlier status -> 2025 region x crop share
    sv = pd.read_csv(D / "data/03_farming/farm_survey_fi.csv")[["farm_id", "crop", "year", "irrigated"]]
    fh = pd.read_csv(D / "data/03_farming/foodhills_odlingsdata_se.csv", sep=";", decimal=",")
    se = pd.DataFrame(dict(farm_id=fh.odlar_id, crop="pea", year=fh["skördeår"], irrigated=fh.bevattnad == "ja"))
    st = pd.concat([sv, se], ignore_index=True)
    st = st[st.year <= 2025].sort_values("year")
    st["irr"] = st.irrigated.astype(float)
    exact = st[st.year == 2025].groupby(["farm_id", "crop"]).irr.mean()
    last = st.groupby(["farm_id", "crop"]).irr.last()
    key = pd.Series(list(zip(m.farm_id, m.crop)))
    a, b = key.map(exact).values, key.map(last).values
    reg = pd.read_csv(D / "data/01_master/farm_registry.csv")[["farm_id", "region"]]
    share = st[st.year == 2025].merge(reg, on="farm_id").groupby(["region", "crop"]).irr.mean()
    c = pd.Series(list(zip(m.region, m.crop))).map(share).values
    m["irr"] = np.where(~np.isnan(a), a, np.where(~np.isnan(b), b, c))
    m["irr_source"] = np.where(~np.isnan(a), "2025", np.where(~np.isnan(b), "latest", "share"))
    return m.reset_index(drop=True)


def observed():
    rec, px, _ = lib.training_records()
    df = rec.join(lib.aggregate(px, ["logw_pure"]), on="rec_id").reset_index(drop=True)
    return df


def scale_estimates(df):
    """Per region x crop: s from within-farm regression of log-yield on fixed log W (as c1-yield-b checks.py)."""
    ly = np.log(df.yield_t_ha.values)
    g = [df.farm_id.values, df.crop.values]
    r = ly - pd.Series(ly).groupby(g).transform("mean").values
    x = df.logw_pure.values - pd.Series(df.logw_pure.values).groupby(g).transform("mean").values
    rows = []
    for k, idx in df.groupby(["region", "crop"]).indices.items():
        xs, rs = x[idx], r[idx] - r[idx].mean()
        s = np.sum(xs * rs) / np.sum(xs * xs)
        # FIX 2026-11-06: SE clustered by season. Records of one region x crop x season share the season's weather
        # and year shock, so the iid SE (first version) was far too narrow; recovery.py copy A showed CIs missing
        # the planted s in 2/6 rows. Cluster-robust (CR1) with G = number of seasons, t(G-1) quantile ~ 2.1-2.3.
        e = rs - s * xs
        yrs = df.year.values[idx]
        sc_ = pd.Series(xs * e).groupby(yrs).sum().values
        G = len(sc_)
        se = np.sqrt(G / (G - 1) * np.sum(sc_ ** 2)) / np.sum(xs * xs)
        tq = {8: 2.306, 14: 2.145}.get(G - 1, 2.2)
        lo, hi = s - tq * se, s + tq * se
        use = float(np.clip(s, 0, 1.5)) if (hi < 1 or lo > 1) else 1.0
        rows.append(dict(region=k[0], crop=k[1], n=len(idx), s_hat=s, lo=lo, hi=hi, s_used=use))
    return pd.DataFrame(rows).set_index(["region", "crop"])


def year_noise(df, s_used):
    """sigma_y per region x crop: variance of detrended year effects beyond what survey sampling explains."""
    ly = np.log(df.yield_t_ha.values)
    s = np.array([s_used.get(k, 1.0) for k in zip(df.region, df.crop)])
    g = [df.farm_id.values, df.crop.values]
    r = ly - s * df.logw_pure.values
    r = r - pd.Series(r).groupby(g).transform("mean").values
    d = df.assign(r=r)
    rows = []
    for k, gg in d.groupby(["region", "crop"]):
        ye = gg.groupby("year").r.agg(["mean", "var", "count"])
        t = ye.index.values.astype(float)
        b = np.polyfit(t, ye["mean"].values, 1)
        resid = ye["mean"].values - np.polyval(b, t)
        v_tot = np.var(resid, ddof=2)
        # FIX 2026-11-06: seasons with a single record have var=NaN, which made v_samp NaN and sigma_y 0
        # (FI carrot). Sampling variance of a 1-record season = pooled within-season variance / 1.
        pooled = float(np.nansum(ye["var"] * (ye["count"] - 1)) / max(1, np.sum(ye["count"] - 1)))
        vv = ye["var"].fillna(pooled).values
        v_samp = float(np.mean(vv / ye["count"].values))
        rows.append(dict(region=k[0], crop=k[1], years=len(ye), sd_year_effect=np.sqrt(v_tot),
                         sd_sampling=np.sqrt(v_samp), sigma_y=np.sqrt(max(0.0, v_tot - v_samp))))
    return pd.DataFrame(rows).set_index(["region", "crop"])


def index_series(mix, s_used, feat=None, weight="area"):
    """Aggregate yield index Y_t (production / area, relative units) per series x region x crop x year."""
    if feat is None:
        feat = pd.read_parquet(OUT / "feat_c2.parquet")
    x = mix.merge(feat, left_on=["cell_id", "crop", "soil_class_soilmap"], right_on=["cell_id", "crop", "soil"])
    s = np.array([s_used.get(k, 1.0) for k in zip(x.region, x.crop)])
    x["w"] = x.area_ha if weight == "area" else x.area_ha * x[weight]
    x["y"] = np.exp(s * lib.pure_process_logw(x, x.irr.values)) * x.w
    a = x.groupby(["series", "region", "crop", "year"])[["y", "w"]].sum()
    return (a.y / a.w).rename("Y").reset_index()


def summarise(Y, sig, base_series="hist", fut_prefix="delta_"):
    rows = []
    for (reg, crop), g in Y.groupby(["region", "crop"]):
        b = g[(g.series == base_series) & g.year.between(1991, 2020)].Y.values
        m = b.mean()
        sy = float(sig.loc[(reg, crop), "sigma_y"]) if sig is not None else 0.0
        for ssp in SSPS:
            f = g[g.series == fut_prefix + ssp].Y.values
            if sy > 0:
                pb = float(np.mean(phi((np.log(0.8 * m) - np.log(f)) / sy)))
                pb_base = float(np.mean(phi((np.log(0.8 * m) - np.log(b)) / sy)))
            else:
                pb, pb_base = float(np.mean(f < 0.8 * m)), float(np.mean(b < 0.8 * m))
            ch = 100 * (f.mean() / m - 1)
            se = 100 * f.std(ddof=1) / np.sqrt(len(f)) / m
            rows.append(dict(region=reg, crop=crop, scenario=ssp, n_years=len(f), mean_yield_change_pct=ch,
                             ci_lo=ch - 1.96 * se, ci_hi=ch + 1.96 * se, p_bad_year=pb, p_bad_1991_2020=pb_base))
    return pd.DataFrame(rows)
