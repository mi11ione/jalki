"""Full backtest table: model x trend mode x split, with the selection rule stated before the run.

Splits: LOYO (leave one season out, 2012-2026), F1 (train <=2021, test 2022-2026), F2 (train <=2018, test 2019-2023).
Trend modes: cell (slope per crop x region), pooled (one shared technology slope), none.
SELECTION RULE (fixed before this script was first run, logged in FIXLOG.md):
  the submission model = argmax over (model, trend mode) of mean(F1, F2) score; ties (<0.5) -> higher LOYO.
  Rationale: the C1 test is a forecast 1-5 seasons past the last observed one; forward blocks are its analogue.
Writes out/grid.json and out/grid_season_scores.parquet."""
import sys, os; sys.path.append(os.path.dirname(os.path.abspath(__file__))); import boot
import json
import time
import numpy as np
import pandas as pd
from ccn_tools import score as SC
import lib

t0 = time.time()
rec, px, n_drop = lib.training_records()
cols = lib.PROC_FEATS + [f"soil_{s}" for s in lib.SOILS] + ["clay_pct_soilmap", "logw_pure"] + lib.monthly_cols(px)
df = rec.join(lib.aggregate(px, cols), on="rec_id").reset_index(drop=True)
KINDS = ["baseline", "trend_farm", "proc_pure", "proc_cal", "gbm_raw", "gbm_proc"]
MODES = ["cell", "pooled", "none"]


def score(d, p):
    key = pd.DataFrame(dict(parcel_id=d.farm_id.values, year=d.year.values, crop=d.crop.values, region=d.region.values,
                            area_ha=d.area_ha.values, yield_t_ha_true=d.yield_t_ha.values))
    return SC.score_c1(key[["parcel_id", "year", "crop"]].assign(yield_t_ha_pred=p), key)


CACHE = lib.OUT / "grid_cache"
CACHE.mkdir(exist_ok=True)
BUDGET_S = 40.0   # CPU cap kills long processes: compute in resumable chunks, re-run the same command


def run_split(name, folds):
    """folds: list of (train_mask, test_mask). Returns {(kind,mode): pred array over df (nan outside test)}.
    Each (split, mode, kind) is cached; exits early (code 3) when over budget so the command can be re-run."""
    P = {}
    for mode in MODES:
        for k in KINDS:
            if k == "baseline" and mode != "cell":
                continue
            f = CACHE / f"{name}_{mode}_{k}.npy"
            if f.exists():
                P[(k, mode)] = np.load(f)
                continue
            if time.time() - t0 > BUDGET_S:
                print(f"PARTIAL: budget reached before {name}/{mode}/{k}; re-run the same command to continue")
                sys.exit(3)
            p = np.full(len(df), np.nan)
            for trm, tem in folds:
                p[tem] = lib.fit_predict(df[trm], df[tem], k, trend_mode=mode)
            np.save(f, p)
            P[(k, mode)] = p
            print(f"  computed {name}/{mode}/{k} at {time.time()-t0:.0f}s")
        P[("ens", mode)] = np.sqrt(P[("proc_cal", mode)] * P[("gbm_proc", mode)])
    return P


years = sorted(df.year.unique())
splits = {
    "LOYO": [(df.year.values != Y, df.year.values == Y) for Y in years],
    "F1": [(df.year.values <= 2021, df.year.values >= 2022)],
    "F2": [(df.year.values <= 2018, (df.year.values >= 2019) & (df.year.values <= 2023))],
}
allp, table, season = {}, [], []
for sname, folds in splits.items():
    P = run_split(sname, folds)
    allp[sname] = P
    tm = np.zeros(len(df), bool)
    for _, te in folds:
        tm |= te
    for (k, mode), p in P.items():
        r = score(df[tm], p[tm])
        table.append(dict(split=sname, model=k, trend=mode, score=r["score"], mape=r["aggregate_mape"], nrmse=r["parcel_nrmse"]))
        for Y in sorted(df[tm].year.unique()):
            m = tm & (df.year.values == Y)
            season.append(dict(split=sname, model=k, trend=mode, year=int(Y), score=score(df[m], p[m])["score"]))
T = pd.DataFrame(table)
S = pd.DataFrame(season)
S.to_parquet(lib.OUT / "grid_season_scores.parquet", index=False)
W = T.pivot_table(index=["model", "trend"], columns="split", values="score")[["LOYO", "F1", "F2"]]
W["fwd_mean"] = (W.F1 + W.F2) / 2
W = W.sort_values(["fwd_mean", "LOYO"], ascending=False)
print("\nScore by model x trend mode x split (C1 scorer, farm level):")
print(W.round(2).to_string())
best = W.index[0]
cand = W[(W.fwd_mean >= W.fwd_mean.iloc[0] - 0.5)]
best = cand.LOYO.idxmax()
print(f"\nSELECTED (rule: max mean forward score, tie<0.5 -> LOYO): model={best[0]} trend={best[1]}  "
      f"F1 {W.loc[best,'F1']:.2f}  F2 {W.loc[best,'F2']:.2f}  LOYO {W.loc[best,'LOYO']:.2f}")


def paired(split, a, b):
    sa = S[(S.split == split) & (S.model == a[0]) & (S.trend == a[1])].set_index("year").score
    sb = S[(S.split == split) & (S.model == b[0]) & (S.trend == b[1])].set_index("year").score
    d = (sa - sb).dropna()
    se = d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else np.nan
    return dict(mean=round(float(d.mean()), 2), lo=round(float(d.mean() - 1.96 * se), 2), hi=round(float(d.mean() + 1.96 * se), 2),
                better=int((d > 0).sum()), n=int(len(d)))


out = {"table": table, "selected": {"model": best[0], "trend": best[1]}, "paired": {}}
B = ("baseline", "cell")
print("\nPaired per-season differences (mean [95% CI], seasons better/n):")
for split in ("LOYO", "F1", "F2"):
    for a, b, lab in ((best, B, "selected vs baseline"),
                      (("proc_cal", best[1]), ("gbm_raw", best[1]), "proc_cal vs gbm_raw (same trend)"),
                      (("gbm_proc", best[1]), ("gbm_raw", best[1]), "gbm_proc vs gbm_raw (features, same learner)"),
                      (("proc_cal", best[1]), ("gbm_proc", best[1]), "proc_cal vs gbm_proc (learner, same features)"),
                      (("proc_cal", best[1]), ("trend_farm", best[1]), "proc_cal vs trend_farm (weather value)")):
        r = paired(split, a, b)
        out["paired"][f"{split}|{lab}"] = r
        print(f"  {split:4s} {lab:48s} {r['mean']:+6.2f} [{r['lo']:+.2f}, {r['hi']:+.2f}]  {r['better']}/{r['n']}")
# process vs GBM across all 9 (split x trend) cells
wins = []
for split in ("LOYO", "F1", "F2"):
    for mode in MODES:
        wins.append(dict(split=split, trend=mode, proc_cal=W.loc[("proc_cal", mode), split], gbm_raw=W.loc[("gbm_raw", mode), split],
                         gbm_proc=W.loc[("gbm_proc", mode), split], proc_pure=W.loc[("proc_pure", mode), split]))
Wn = pd.DataFrame(wins)
Wn["proc_cal_beats_gbm_raw"] = Wn.proc_cal > Wn.gbm_raw
Wn["gbm_proc_beats_gbm_raw"] = Wn.gbm_proc > Wn.gbm_raw
print("\nProcess vs GBM in every split x trend cell:")
print(Wn.round(2).to_string(index=False))
print(f"proc_cal > gbm_raw in {int(Wn.proc_cal_beats_gbm_raw.sum())}/9 cells; gbm_proc > gbm_raw in {int(Wn.gbm_proc_beats_gbm_raw.sum())}/9 cells")
out["wins"] = Wn.to_dict("records")
json.dump(out, open(lib.OUT / "grid.json", "w"), indent=1, default=float)
print(f"done {time.time()-t0:.0f}s")
