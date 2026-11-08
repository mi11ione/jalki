"""C2 (own): weather-response yield model learned from 2012-2026 history, applied to 1991-2020 vs 2041-2060 by SSP.

Design (fixed before fitting):
* Response: relative yield r = farm-crop yield / that farm-crop's mean (removes farm skill & soil).
* Features per crop from monthly weather of the farm's nearest grid cell (crop calendar in FEATS below), plus a
  water-balance x irrigated interaction where irrigation exists, plus a linear year trend per region (technology).
* Weighted least squares with a small ridge (lambda=1 on standardised features).
* Counterfactual: technology held at its 2025 level, 2025 contract mix (area per farm, current irrigation),
  so the only thing changing between 1991-2020 and 2041-2060 is weather.
* Year-level noise: sd of leave-one-year-out region-year residuals; p_bad_year = mean over years of
  Phi((0.8*base_mean - pred_t)/sd). Expected shortfall uses the same normal closed form (no Monte Carlo).
Outputs: C2_submission.csv (template format), c2_yearly.csv (region-crop-scenario-year predicted index),
c2_backtest.csv, c2_coefs.csv.
"""
from common import *  # noqa
from math import erf, sqrt, exp, pi
import json

FEATS = {
    "pea":         ["wb_5_7", "hot_6_7", "p_5", "p_7"],
    "potato":      ["wb_7_8", "blight_7_8", "p_9", "hot_7_8"],
    "carrot":      ["wb_6_8", "hot_7_8", "p_9", "p_5"],
    "spinach":     ["wb_5_6", "hot_6_6", "p_5", "t_5_6"],
    "turnip_rape": ["wb_6_7", "t_5_5", "hot_7_7", "p_8_9", "t_4_9"],
}
IRR_FEAT = {"pea": "wb_5_7", "potato": "wb_7_8", "carrot": "wb_6_8", "spinach": "wb_5_6"}
LAM = 1.0


def features(wm):
    g = wm.set_index(["cell_id", "scenario", "year", "month"])
    out = {}
    def msum(col, a, b):
        return g[col][g.index.get_level_values("month").isin(range(a, b + 1))].groupby(level=[0, 1, 2]).sum()
    def mmean(col, a, b):
        return g[col][g.index.get_level_values("month").isin(range(a, b + 1))].groupby(level=[0, 1, 2]).mean()
    for a, b in [(5, 7), (7, 8), (6, 8), (5, 6), (6, 7)]:
        out[f"wb_{a}_{b}"] = msum("precip_mm", a, b) - msum("pet_mm", a, b)
    for a, b in [(6, 7), (7, 8), (6, 6), (7, 7)]:
        out[f"hot_{a}_{b}"] = msum("hot_days_tmax_ge_27", a, b)
    for a, b in [(5, 5), (7, 7), (9, 9), (8, 9)]:
        out[f"p_{a}" if a == b else f"p_{a}_{b}"] = msum("precip_mm", a, b)
    for a, b in [(5, 6), (5, 5), (4, 9)]:
        out[f"t_{a}_{b}"] = mmean("tmean_c", a, b)
    # late-blight pressure: rain in warm months (Jul-Aug rain x max(0, Tmean-12))
    t78 = mmean("tmean_c", 7, 8); p78 = msum("precip_mm", 7, 8)
    out["blight_7_8"] = p78 * (t78 - 12).clip(lower=0)
    F = pd.DataFrame(out).reset_index()
    return F


def history():
    sv = survey_clean(); sv = sv[~sv.dropped]
    fr = pd.read_csv(D / "01_master/farm_registry.csv")[["farm_id", "region", "lat", "lon"]]
    fi = sv[["farm_id", "crop", "year", "area_ha", "yield_t_ha", "irrigated"]].merge(fr, on="farm_id")
    fh = foodhills(); fh = fh[~fh.dropped]
    se = fh[["farm_id", "crop", "year", "area_ha", "yield_t_ha", "irrigated"]].merge(fr, on="farm_id")
    h = pd.concat([fi, se], ignore_index=True)
    n = h.groupby(["farm_id", "crop"]).yield_t_ha.transform("count")
    h = h[n >= 3].copy()
    h["r"] = h.yield_t_ha / h.groupby(["farm_id", "crop"]).yield_t_ha.transform("mean")
    h["cell_id"] = nearest_cell(h.lat, h.lon, cells())
    return h


def design(df, crop, stats=None):
    cols = FEATS[crop]
    X = df[cols].astype(float).copy()
    if crop in IRR_FEAT:
        X["irr_x_wb"] = df[IRR_FEAT[crop]] * df.irrigated.astype(float)
        X["irr"] = df.irrigated.astype(float)
    if stats is None:
        stats = (X.mean(), X.std().replace(0, 1))
    Z = (X - stats[0]) / stats[1]
    for reg in sorted(df.region.unique()) if "region" in df else []:
        pass
    return Z, stats


def fit(df, crop, regions):
    Z, st = design(df, crop)
    A = [Z.values]
    names = list(Z.columns)
    for reg in regions:
        m = (df.region == reg).values.astype(float)
        A += [m[:, None], (m * (df.year.values - 2025) / 10)[:, None]]
        names += [f"icpt_{reg}", f"trend10y_{reg}"]
    A = np.hstack(A)
    w = df.area_ha.values
    pen = np.r_[np.full(Z.shape[1], LAM), np.zeros(A.shape[1] - Z.shape[1])]
    beta = np.linalg.solve(A.T @ (A * w[:, None]) + np.diag(pen) * w.mean(), A.T @ (w * df.r.values))
    return dict(beta=beta, names=names, stats=st, nz=Z.shape[1], regions=regions)


def predict(model, df, crop, tech_year=None):
    Z, _ = design(df, crop, model["stats"])
    b = model["beta"]; nz = model["nz"]
    p = Z.values @ b[:nz]
    for i, reg in enumerate(model["regions"]):
        m = (df.region == reg).values
        yr = df.year.values if tech_year is None else np.full(len(df), tech_year)
        p = p + m * (b[nz + 2 * i] + b[nz + 2 * i + 1] * (yr - 2025) / 10)
    return np.clip(p, 0.05, 1.6)


def agg_region_year(df, pred_col):
    return df.groupby(["region", "year"]).apply(lambda g: np.average(g[pred_col], weights=g.area_ha), include_groups=False)


def Phi(z):
    return 0.5 * (1 + erf(z / sqrt(2)))


def phi(z):
    return exp(-z * z / 2) / sqrt(2 * pi)


def main():
    wm = weather_monthly()
    F = features(wm)
    h = history()
    hist = h.merge(F[F.scenario == "historical"].drop(columns="scenario"), on=["cell_id", "year"])
    # 2025 contract mix per farm x crop: area & latest irrigation status
    ca = contract_area(2025)
    mix = ca.groupby(["farm_id", "crop", "region"]).agg(area_ha=("area_ha", "sum"), lat=("lat", "mean"), lon=("lon", "mean")).reset_index()
    last_irr = h.sort_values("year").groupby(["farm_id", "crop"]).irrigated.last()
    mix["irrigated"] = [bool(last_irr.get((f, c), False)) for f, c in zip(mix.farm_id, mix.crop)]
    mix["cell_id"] = nearest_cell(mix.lat, mix.lon, cells())

    rows, yearly, bt, coefs, sd_out = [], [], [], [], {}
    for crop in CROPS:
        d = hist[hist.crop == crop].copy()
        regions = sorted(d.region.unique())
        model = fit(d, crop, regions)
        for n, b in zip(model["names"], model["beta"]):
            coefs.append(dict(crop=crop, term=n, coef_per_sd=round(float(b), 4)))
        # leave-one-year-out backtest at region-year production level
        for yr in sorted(d.year.unique()):
            tr, te = d[d.year != yr], d[d.year == yr].copy()
            m = fit(tr, crop, regions)
            te["pred"] = predict(m, te, crop)
            for reg, g in te.groupby("region"):
                fm = tr.groupby("farm_id").yield_t_ha.mean()  # comparator: farm historical mean (current practice)
                gy = g.assign(base=g.farm_id.map(fm)).dropna(subset=["base"])
                if len(gy) == 0:
                    continue
                obs = (gy.area_ha * gy.yield_t_ha).sum()
                bt.append(dict(crop=crop, region=reg, year=yr, obs_t=obs,
                               model_t=(gy.area_ha * gy.pred * gy.base).sum(),
                               compar_t=(gy.area_ha * gy.base).sum(),
                               obs_index=np.average(gy.yield_t_ha / gy.base, weights=gy.area_ha),
                               pred_index=np.average(gy.pred, weights=gy.area_ha)))
        b = pd.DataFrame([x for x in bt if x["crop"] == crop])
        b["resid"] = b.obs_index - b.pred_index
        b["resid_null"] = b.obs_index - 1.0
        # project
        mx = mix[mix.crop == crop]
        for scen, yrs in [("historical", range(1991, 2021)), ("ssp126", range(2041, 2061)), ("ssp245", range(2041, 2061)), ("ssp585", range(2041, 2061))]:
            Fs = F[(F.scenario == scen) & F.year.isin(list(yrs))].drop(columns="scenario")
            P = mx.merge(Fs, on="cell_id")
            P["pred"] = predict(model, P, crop, tech_year=2025)
            ry = agg_region_year(P, "pred").rename("index").reset_index()
            ry["crop"], ry["scenario"] = crop, scen
            yearly.append(ry)
        for reg in sorted(mx.region.unique()):
            sd = float(b[b.region == reg].resid.std(ddof=1))
            sd_out[f"{reg}|{crop}"] = sd
    Y = pd.concat(yearly, ignore_index=True)
    for (reg, crop), g in Y.groupby(["region", "crop"]):
        base = g[g.scenario == "historical"]["index"]
        mu0 = base.mean(); sd = sd_out[f"{reg}|{crop}"]
        for scen in ["ssp126", "ssp245", "ssp585"]:
            fut = g[g.scenario == scen]["index"]
            pbad = float(np.mean([Phi((0.8 * mu0 - v) / sd) for v in fut]))
            rows.append(dict(region=reg, crop=crop, scenario=scen, period="2041-2060",
                             mean_yield_change_pct=round(100 * (fut.mean() / mu0 - 1), 2), p_bad_year=round(pbad, 4)))
        pbad0 = float(np.mean([Phi((0.8 * mu0 - v) / sd) for v in base]))
        rows.append(dict(region=reg, crop=crop, scenario="historical", period="1991-2020", mean_yield_change_pct=0.0, p_bad_year=round(pbad0, 4)))
    R = pd.DataFrame(rows)
    tmpl = pd.read_csv(ROOT / "tasks/templates/C2_climate_yield_risk_submission.csv")
    sub = tmpl[["region", "crop", "scenario", "period"]].merge(R, on=["region", "crop", "scenario", "period"], how="left")
    sub.to_csv(OUT / "C2_submission.csv", index=False)
    R.to_csv(OUT / "c2_all.csv", index=False)
    Y.to_csv(OUT / "c2_yearly.csv", index=False)
    B = pd.DataFrame(bt); B.to_csv(OUT / "c2_backtest.csv", index=False)
    pd.DataFrame(coefs).to_csv(OUT / "c2_coefs.csv", index=False)
    json.dump(sd_out, open(OUT / "c2_sd.json", "w"), indent=1)
    # backtest scores (C1-style aggregate credit: full at 0 % MAPE, none at 15 %)
    B["ape_m"] = (B.model_t - B.obs_t).abs() / B.obs_t
    B["ape_c"] = (B.compar_t - B.obs_t).abs() / B.obs_t
    print("LOYO backtest, region x crop x year production (2012-2026):")
    print(B.groupby(["region", "crop"])[["ape_m", "ape_c"]].mean().round(4).to_string())
    for lbl, col in [("comparator (farm historical mean)", "ape_c"), ("weather model", "ape_m")]:
        mape = B[col].mean()
        print(f"BACKTEST {lbl}: MAPE {mape:.4f}  score {100 * max(0, 1 - mape / 0.15):.2f}")
    late = B[B.year >= 2022]
    for lbl, col in [("comparator", "ape_c"), ("weather model", "ape_m")]:
        print(f"BACKTEST 2022-2026 only {lbl}: MAPE {late[col].mean():.4f}")
    print("year-noise sd (LOYO region-year residual):", {k: round(v, 4) for k, v in sd_out.items()})
    print(sub.to_string())
    print(R[R.scenario == "historical"].to_string())


if __name__ == "__main__":
    main()
