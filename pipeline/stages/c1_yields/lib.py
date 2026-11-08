"""Shared data assembly and models for C1 (imported by backtest.py, forecast.py, recovery.py).

All hyperparameters are fixed here, before any backtest was run, and are not tuned on held-out seasons.
"""
import sys, os; sys.path.append(os.path.dirname(os.path.abspath(__file__))); import boot
from pathlib import Path
import numpy as np
import pandas as pd

D = Path(boot.DATA)
OUT = Path(boot.HERE) / "out"
CROPS = ["pea", "potato", "carrot", "spinach", "turnip_rape"]
SOILS = ["clay", "silt", "fine_sand", "sand", "organic"]
IRR_RELIEF = 0.7          # irrigation removes 70 % of drought stress (process assumption)
OUTLIER_RATIO = 2.5       # survey yield > 2.5 x crop median = planted outlier / unit slip (A1 dev labels show 6-7x)
SHRINK_K = 2.0            # farm effect = sum(resid) / (n + k)
RIDGE_LAMBDA = 20.0
GBM_PARAMS = dict(n_rounds=300, lr=0.03, depth=3, min_leaf=30, nbins=32, subsample=0.8, seed=7)

PROC_FEATS = ["dstress_veg", "dstress_rep", "heat_flo", "heat_season", "imm", "wet_days", "harvest_rain",
              "blight_days", "may_tmax", "gdd_season", "sow_doy"]


# ------------------------------------------------------------------ data
def parcel_cells():
    par = pd.read_csv(D / "data/01_master/parcels.csv")
    reg = pd.read_csv(D / "data/01_master/farm_registry.csv")[["farm_id", "region"]]
    grid = pd.read_csv(D / "data/01_master/climate_grid_cells.csv")
    par = par.merge(reg, on="farm_id")
    out = []
    for r, g in par.groupby("region"):
        gc = grid[grid.region == r].reset_index(drop=True)
        coslat = np.cos(np.deg2rad(g.lat.values.mean()))
        d2 = (g.lat.values[:, None] - gc.lat.values[None]) ** 2 + ((g.lon.values[:, None] - gc.lon.values[None]) * coslat) ** 2
        gg = g.copy()
        gg["cell_id"] = gc.cell_id.values[d2.argmin(1)]
        gg["cell_dist_deg"] = np.sqrt(d2.min(1))
        out.append(gg)
    return pd.concat(out, ignore_index=True)


def pure_process_logw(f: pd.DataFrame, irr) -> np.ndarray:
    """Fixed-parameter multiplicative stress model (no fitting): log W."""
    relief = 1 - IRR_RELIEF * irr
    clayish = f.soil.isin(["clay", "silt"]).astype(float).values if "soil" in f else 0.0
    terms = [
        1 - 0.25 * f.dstress_veg.values * relief,
        1 - 0.50 * f.dstress_rep.values * relief,
        1 - 0.03 * np.minimum(f.heat_flo.values, 10),
        1 - f.imm.values,
        1 - 0.03 * np.minimum(f.wet_days.values, 10) * clayish,
        1 - 0.001 * np.maximum(f.harvest_rain.values - 30, 0),
        1 - np.where(f.crop.values == "potato", 0.004 * f.blight_days.values, 0.0),
        1 - np.where(f.crop.values == "turnip_rape", 0.02 * np.maximum(f.may_tmax.values - 15, 0), 0.0),
    ]
    return np.sum([np.log(np.clip(t, 0.05, 1.0)) for t in terms], axis=0)


def parcel_features(pc: pd.DataFrame, irr_col="irr") -> pd.DataFrame:
    """pc: rows with parcel_id, year, crop, cell_id, soil_class_soilmap, irr (0..1). Adds process + monthly features."""
    fp = pd.read_parquet(OUT / "feat_process.parquet")
    fm = pd.read_parquet(OUT / "feat_monthly.parquet")
    x = pc.merge(fp, left_on=["cell_id", "year", "crop", "soil_class_soilmap"], right_on=["cell_id", "year", "crop", "soil"], how="left")
    assert x.dstress_rep.notna().all(), "missing process features"
    irr = x[irr_col].values
    x["logw_pure"] = pure_process_logw(x, irr)
    for c in ("dstress_veg", "dstress_rep"):
        x[c] = x[c] * (1 - IRR_RELIEF * irr)
    for s in SOILS:
        x[f"soil_{s}"] = (x.soil_class_soilmap == s).astype(float)
    x = x.merge(fm, on=["cell_id", "year"], how="left")
    return x


def training_records():
    """Farm x crop x season yields: FI survey (cleaned) + SE Foodhills deliveries/area.
    Returns (records, parcel-level feature rows linked by rec_id)."""
    reg = pd.read_csv(D / "data/01_master/farm_registry.csv")[["farm_id", "region", "organic_certified"]]
    sv = pd.read_csv(D / "data/03_farming/farm_survey_fi.csv")
    med = sv.groupby("crop").yield_t_ha.transform("median")
    n0 = len(sv)
    sv = sv[sv.yield_t_ha <= OUTLIER_RATIO * med]
    n_drop = n0 - len(sv)
    fi = sv[["farm_id", "crop", "year", "yield_t_ha", "irrigated"]].assign(irr=lambda d: d.irrigated.astype(float)).drop(columns="irrigated")
    fh = pd.read_csv(D / "data/03_farming/foodhills_odlingsdata_se.csv", sep=";", decimal=",")
    se = pd.DataFrame(dict(farm_id=fh.odlar_id, crop="pea", year=fh["skördeår"],
                           yield_t_ha=fh["levererad_mängd_ton"] / fh["areal_ha"], irr=(fh.bevattnad == "ja").astype(float)))
    rec = pd.concat([fi, se], ignore_index=True).merge(reg, on="farm_id")
    rec = rec[rec.year <= 2026].reset_index(drop=True)
    rec["rec_id"] = np.arange(len(rec))
    ch = pd.read_csv(D / "data/03_farming/parcel_crop_history_and_plan.csv")
    ch = ch[ch.status == "declared"][["parcel_id", "farm_id", "year", "crop"]]
    pc = parcel_cells()[["parcel_id", "area_ha", "cell_id", "soil_class_soilmap", "clay_pct_soilmap"]]
    lk = rec[["rec_id", "farm_id", "crop", "year", "irr"]].merge(ch, on=["farm_id", "crop", "year"]).merge(pc, on="parcel_id")
    px = parcel_features(lk)
    area = px.groupby("rec_id").area_ha.sum()
    rec = rec[rec.rec_id.isin(area.index)].copy()
    rec["area_ha"] = rec.rec_id.map(area)
    return rec.reset_index(drop=True), px, n_drop


def aggregate(px: pd.DataFrame, cols) -> pd.DataFrame:
    """Area-weighted mean of parcel features per rec_id (or any id in column 'rec_id')."""
    w = px.area_ha.values[:, None]
    num = pd.DataFrame(px[cols].values * w, columns=cols)
    num["rec_id"] = px.rec_id.values
    num["_w"] = px.area_ha.values
    s = num.groupby("rec_id").sum()
    return s[cols].div(s["_w"], axis=0)


MONTHLY_COLS = None


def monthly_cols(df):
    return [c for c in df.columns if any(c.startswith(p) for p in ("tmean_c_m", "tmax_c_max_m", "precip_mm_m", "pet_mm_m", "hot_days_tmax_ge_27_m", "cwb_m"))]


# ------------------------------------------------------------------ gradient boosting (numpy, histogram trees)
class GBM:
    def __init__(self, n_rounds=300, lr=0.03, depth=3, min_leaf=30, nbins=32, subsample=0.8, seed=7):
        self.p = dict(n_rounds=n_rounds, lr=lr, depth=depth, min_leaf=min_leaf, nbins=nbins, subsample=subsample)
        self.rng = np.random.default_rng(seed)

    def _bin(self, X):
        return np.stack([np.searchsorted(self.edges[j], X[:, j], side="right") for j in range(X.shape[1])], 1).astype(np.int32)

    def fit(self, X, y):
        X = np.asarray(X, float)
        nb = self.p["nbins"]
        self.edges = [np.unique(np.quantile(X[:, j], np.linspace(0, 1, nb + 1)[1:-1])) for j in range(X.shape[1])]
        Xb = self._bin(X)
        self.F = X.shape[1]
        self.off = (np.arange(self.F) * (nb + 1))[None, :]
        self.base = float(np.mean(y))
        pred = np.full(len(y), self.base)
        self.trees = []
        for _ in range(self.p["n_rounds"]):
            r = y - pred
            idx = np.where(self.rng.random(len(y)) < self.p["subsample"])[0]
            tree = self._grow(Xb, r, idx, 0)
            self.trees.append(tree)
            pred += self.p["lr"] * self._pred_tree(tree, Xb)
        return self

    def _grow(self, Xb, r, idx, depth):
        m = len(idx)
        val = float(r[idx].mean()) if m else 0.0
        if depth >= self.p["depth"] or m < 2 * self.p["min_leaf"]:
            return ("leaf", val)
        nb1 = self.p["nbins"] + 1
        codes = (Xb[idx] + self.off).ravel()
        rs = np.tile(r[idx][:, None], (1, self.F)).ravel()
        S = np.bincount(codes, weights=rs, minlength=self.F * nb1).reshape(self.F, nb1)
        C = np.bincount(codes, minlength=self.F * nb1).reshape(self.F, nb1).astype(float)
        SL, CL = np.cumsum(S, 1)[:, :-1], np.cumsum(C, 1)[:, :-1]
        ST, CT = S.sum(1, keepdims=True), C.sum(1, keepdims=True)
        SR, CR = ST - SL, CT - CL
        ok = (CL >= self.p["min_leaf"]) & (CR >= self.p["min_leaf"])
        gain = np.where(ok, SL ** 2 / np.maximum(CL, 1) + SR ** 2 / np.maximum(CR, 1) - ST ** 2 / CT, -np.inf)
        j, b = np.unravel_index(np.argmax(gain), gain.shape)
        if not np.isfinite(gain[j, b]) or gain[j, b] <= 0:
            return ("leaf", val)
        left = idx[Xb[idx, j] <= b]
        right = idx[Xb[idx, j] > b]
        return ("split", j, b, self._grow(Xb, r, left, depth + 1), self._grow(Xb, r, right, depth + 1))

    def _pred_tree(self, t, Xb, mask=None):
        out = np.zeros(len(Xb))
        stack = [(t, np.ones(len(Xb), bool))]
        while stack:
            node, msk = stack.pop()
            if node[0] == "leaf":
                out[msk] = node[1]
            else:
                _, j, b, l, rr = node
                go = Xb[:, j] <= b
                stack.append((l, msk & go))
                stack.append((rr, msk & ~go))
        return out

    def predict(self, X):
        Xb = self._bin(np.asarray(X, float))
        return self.base + self.p["lr"] * np.sum([self._pred_tree(t, Xb) for t in self.trees], axis=0)


class Ridge:
    def __init__(self, lam=RIDGE_LAMBDA):
        self.lam = lam

    def fit(self, X, y):
        X = np.asarray(X, float)
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        Z = (X - self.mu) / self.sd
        self.b0 = float(y.mean())
        self.b = np.linalg.solve(Z.T @ Z + self.lam * np.eye(Z.shape[1]), Z.T @ (y - self.b0))
        return self

    def predict(self, X):
        return self.b0 + ((np.asarray(X, float) - self.mu) / self.sd) @ self.b


# ------------------------------------------------------------------ yield models
def design(df, kind):
    """Feature matrix for the weather/soil component g(x)."""
    soil = [f"soil_{s}" for s in SOILS]
    if kind == "proc_cal":
        return df[PROC_FEATS + soil].values
    if kind == "gbm_raw":
        mc = monthly_cols(df)
        crop = np.stack([(df.crop == c).astype(float) for c in CROPS], 1)
        reg = (df.region == "SE_SKANE").astype(float).values[:, None]
        return np.hstack([df[mc + soil + ["clay_pct_soilmap", "irr"]].values, crop, reg])
    if kind == "gbm_proc":
        crop = np.stack([(df.crop == c).astype(float) for c in CROPS], 1)
        reg = (df.region == "SE_SKANE").astype(float).values[:, None]
        return np.hstack([df[PROC_FEATS + soil + ["clay_pct_soilmap", "irr"]].values, crop, reg])
    raise ValueError(kind)


TREND_PEN = 25.0   # ridge penalty on the per-(crop,region) slope; np.inf = no trend (level only)


def fit_predict(tr: pd.DataFrame, te: pd.DataFrame, kind: str, n_iter=3, trend_pen=None, trend_mode="cell"):
    if kind == "ens":   # geometric mean of the calibrated process model and GBM-on-process-indices
        a = fit_predict(tr, te, "proc_cal", n_iter, trend_pen, trend_mode)
        b = fit_predict(tr, te, "gbm_proc", n_iter, trend_pen, trend_mode)
        return np.sqrt(a * b)
    return _fit_predict(tr, te, kind, n_iter, trend_pen, trend_mode)


def _fit_predict(tr, te, kind, n_iter, trend_pen, trend_mode):
    """tr/te: farm-crop-season frames with features, region, crop, year, farm_id, yield_t_ha (tr).
    Returns predicted yield (t/ha) for te.  Kinds:
      baseline   : package C1 baseline - farm mean yield of training seasons >= 2016, else crop x region mean
      trend_farm : log y = level + trend (crop x region) + shrunk farm effect          (no weather)
      proc_pure  : trend_farm + fixed-parameter process stress log W (no weather coefficients fitted)
      proc_cal   : trend_farm + ridge on process indices, per crop
      gbm_raw    : trend_farm + gradient-boosted trees on raw monthly weather + soil, pooled
      gbm_proc   : trend_farm + gradient-boosted trees on process indices + soil, pooled
    """
    if kind == "baseline":
        t16 = tr[tr.year >= 2016]
        fm = t16.groupby(["farm_id", "crop"]).yield_t_ha.mean()
        cm = t16.groupby(["region", "crop"]).yield_t_ha.mean()
        v = pd.Series(list(zip(te.farm_id, te.crop))).map(fm).values
        c = pd.Series(list(zip(te.region, te.crop))).map(cm).values
        return np.where(np.isnan(v), c, v)
    y = np.log(tr.yield_t_ha.values)
    # copies: proc_scaled rewrites off_tr in place, which must never touch the caller's frame
    off_tr = tr.logw_pure.to_numpy(copy=True) if kind in ("proc_pure", "proc_scaled") else np.zeros(len(tr))
    off_te = te.logw_pure.to_numpy(copy=True) if kind in ("proc_pure", "proc_scaled") else np.zeros(len(te))
    scale = {}
    g_tr = np.zeros(len(tr))
    u_tr = np.zeros(len(tr))
    keys = ["region", "crop"]
    models = {}
    for it in range(n_iter):
        # level + trend per crop x region
        base_tr = np.zeros(len(tr))
        coef = {}
        tp = TREND_PEN if trend_pen is None else trend_pen
        groups = tr.groupby(keys).indices
        if trend_mode == "pooled":
            # one technology slope shared by all crops and regions, levels per crop x region
            num = den = 0.0
            for k, idx in groups.items():
                t = tr.year.values[idx] - 2020.0
                r = y[idx] - off_tr[idx] - g_tr[idx] - u_tr[idx]
                num += np.sum((t - t.mean()) * (r - r.mean()))
                den += np.sum((t - t.mean()) ** 2)
            slope = num / (den + tp)
        for k, idx in groups.items():
            t = tr.year.values[idx] - 2020.0
            r = y[idx] - off_tr[idx] - g_tr[idx] - u_tr[idx]
            A = np.vstack([np.ones_like(t), t]).T
            if trend_mode == "none" or np.isinf(tp):
                beta = np.array([r.mean(), 0.0])
            elif trend_mode == "pooled":
                beta = np.array([r.mean() - slope * t.mean(), slope])
            else:
                # per crop x region slope, ridge-lite so short series do not explode
                beta = np.linalg.solve(A.T @ A + np.diag([0, tp]), A.T @ r)
            coef[k] = beta
            base_tr[idx] = A @ beta
        res = y - off_tr - g_tr - base_tr
        fe = pd.DataFrame(dict(farm_id=tr.farm_id.values, crop=tr.crop.values, r=res)).groupby(["farm_id", "crop"]).r.agg(["sum", "count"])
        fe = fe["sum"] / (fe["count"] + SHRINK_K)
        u_tr = pd.Series(list(zip(tr.farm_id, tr.crop))).map(fe).fillna(0).values
        if kind == "proc_scaled":
            # one sensitivity scale per crop x region on the fixed process log W (repair for over-sensitivity)
            lw = tr.logw_pure.values
            for k, idx in groups.items():
                # base was fitted on y - off - u, so y - base - u still contains the weather signal
                # (FIX 2026-11-06: an earlier version added off_tr back a second time -> scale ~2, clipped)
                r = y[idx] - base_tr[idx] - u_tr[idx]
                x = lw[idx] - lw[idx].mean()
                s = float(np.sum(x * (r - r.mean())) / max(np.sum(x * x), 1e-9))
                scale[k] = float(np.clip(s, 0.0, 1.5))
                off_tr[idx] = scale[k] * lw[idx]
            continue
        if kind in ("trend_farm", "proc_pure"):
            continue
        target = y - off_tr - base_tr - u_tr
        if kind == "proc_cal":
            g_tr = np.zeros(len(tr))
            for c, idx in tr.groupby("crop").indices.items():
                m = Ridge().fit(design(tr.iloc[idx], kind), target[idx])
                models[c] = m
                g_tr[idx] = m.predict(design(tr.iloc[idx], kind))
        else:
            m = GBM(**GBM_PARAMS).fit(design(tr, kind), target)
            models["all"] = m
            g_tr = m.predict(design(tr, kind))
    if kind == "proc_scaled":
        off_te = np.array([scale.get(k, 1.0) for k in zip(te.region, te.crop)]) * te.logw_pure.values
    resid = y - off_tr - base_tr - u_tr - g_tr
    smear = float(np.mean(np.exp(resid)))
    base_te = np.array([np.array([1.0, yr - 2020.0]) @ coef.get(k, np.zeros(2)) for k, yr in zip(zip(te.region, te.crop), te.year)])
    u_te = pd.Series(list(zip(te.farm_id, te.crop))).map(fe).fillna(0).values
    g_te = np.zeros(len(te))
    if kind == "proc_cal":
        for c, idx in te.groupby("crop").indices.items():
            g_te[idx] = models[c].predict(design(te.iloc[idx], kind))
    elif kind.startswith("gbm"):
        g_te = models["all"].predict(design(te, kind))
    out = np.exp(base_te + u_te + g_te + off_te) * smear
    _fit_predict.last = dict(models=models, coef=coef, smear=smear, farm_effects=fe, scale=scale)
    return out


KINDS = ["baseline", "trend_farm", "proc_pure", "proc_cal", "gbm_raw", "gbm_proc"]
