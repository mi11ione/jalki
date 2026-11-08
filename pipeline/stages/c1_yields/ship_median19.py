"""C1 shipped model, rebuilt: median19 (ticket step-05150-8, promoted there by its pre-registered rule).

median19 = elementwise median of 19 forecasts: the 18 library bases {trend_farm, proc_pure, proc_cal, gbm_proc,
gbm_raw, ens} x trend {none, pooled, cell} from lib.fit_predict, plus mean3 (mean of the farm x crop's last 3
training seasons, region x crop fallback; verbatim from step-00318-3/c1nested.py). No tuned parameter.
The only random step is the GBM row subsample, seeded per model (lib.GBM_PARAMS seed=7), so this is deterministic.
The promotion bootstrap of step-05150-8 (B=2000) decided only WHETHER to ship; it never touched the forecast,
so it is not re-run here (compute policy).

Writes $CCN_OUT/c1_yields/ship/C1_yields_2027_2031_submission.csv (what the submission folder ships) and
$CCN_OUT/c1_yields/ship/median19.json (official dev score on F1: fit <= 2021, score 2022-2026).
Does NOT touch $CCN_OUT/c1_yields/C1_yields_2027_2031_submission.csv (proc_pure, c1-yield-b): the ported cited
figures SHA-check that file as their c1-yield-b input. Synthetic pack only; not Apetit's real yields or emissions."""
import sys, os; sys.path.append(os.path.dirname(os.path.abspath(__file__))); import boot
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
from ccn_tools import score as SC
import lib

T0 = time.time()
D = Path(boot.DATA)
SHIP = Path(boot.HERE) / "ship"
SHIP.mkdir(exist_ok=True)
KINDS = ["trend_farm", "proc_pure", "proc_cal", "gbm_proc", "gbm_raw", "ens"]
MODES = ["none", "pooled", "cell"]


def mean3(tr, te):
    t = tr.sort_values("year")
    fc = t.groupby(["farm_id", "crop"]).tail(3).groupby(["farm_id", "crop"]).yield_t_ha.mean()
    yrs = sorted(t.year.unique())[-3:]
    rc = t[t.year.isin(yrs)].groupby(["region", "crop"]).yield_t_ha.mean()
    v = pd.Series(list(zip(te.farm_id, te.crop))).map(fc).values.astype(float)
    c = pd.Series(list(zip(te.region, te.crop))).map(rc).values.astype(float)
    ra = t.groupby(["region", "crop"]).yield_t_ha.mean()
    ca = t.groupby("crop").yield_t_ha.mean()
    c = np.where(np.isnan(c), pd.Series(list(zip(te.region, te.crop))).map(ra).values.astype(float), c)
    c = np.where(np.isnan(c), te.crop.map(ca).values.astype(float), c)
    return np.where(np.isnan(v), c, v)


def med19(tr, te):
    bp = {}
    for m in MODES:
        for k in KINDS:
            bp[k, m] = (np.sqrt(bp["proc_cal", m] * bp["gbm_proc", m]) if k == "ens"
                        else lib.fit_predict(tr, te, k, trend_mode=m))
    return np.median(np.stack([bp[k, m] for m in MODES for k in KINDS] + [mean3(tr, te)]), axis=0)


def official(d, p):
    key = pd.DataFrame(dict(parcel_id=d.farm_id.values, year=d.year.values, crop=d.crop.values, region=d.region.values,
                            area_ha=d.area_ha.values, yield_t_ha_true=d.yield_t_ha.values))
    return SC.score_c1(key[["parcel_id", "year", "crop"]].assign(yield_t_ha_pred=np.asarray(p)), key)


rec, px, _ = lib.training_records()
cols = lib.PROC_FEATS + [f"soil_{s}" for s in lib.SOILS] + ["clay_pct_soilmap", "logw_pure"] + lib.monthly_cols(px)
df = rec.join(lib.aggregate(px, cols), on="rec_id").reset_index(drop=True)

# dev score: F1 (fit <= 2021, score 2022-2026), official scorer, as step-05150-8 reported it
tr, te = df[df.year <= 2021], df[df.year >= 2022].reset_index(drop=True)
dev = official(te, med19(tr, te))
base = official(te, lib.fit_predict(tr, te, "baseline"))
print(f"median19 F1 official dev score {dev['score']} (mape {dev['aggregate_mape']}, nrmse {dev['parcel_nrmse']}); "
      f"package baseline {base['score']}  [{time.time() - T0:.0f}s]")

# forecast: refit on all observed seasons <= 2026, template rows, forecast.py's irrigation rule
tpl = pd.read_csv(D / "tasks/templates/C1_yields_2027_2031_submission.csv")
last = rec.sort_values("year").groupby(["farm_id", "crop"]).irr.last()
share = rec[rec.year >= 2024].groupby(["region", "crop"]).irr.mean()
pc = lib.parcel_cells()[["parcel_id", "cell_id", "soil_class_soilmap", "clay_pct_soilmap"]]
t = tpl.merge(pc, on="parcel_id", how="left")
assert t.cell_id.notna().all()
irr = pd.Series(list(zip(t.farm_id, t.crop))).map(last)
t["irr"] = np.where(irr.notna().values, irr.values, pd.Series(list(zip(t.region, t.crop))).map(share).values)
t["rec_id"] = np.arange(len(t))
tx = lib.parcel_features(t).sort_values("rec_id").reset_index(drop=True)
assert len(tx) == len(tpl)
fc = med19(df, tx)
assert np.isfinite(fc).all() and (fc > 0).all()
sub = tpl.copy()
sub["yield_t_ha_pred"] = np.round(fc, 3)
outp = SHIP / "C1_yields_2027_2031_submission.csv"
sub.to_csv(outp, index=False)
info = dict(model="median19: elementwise median of 18 library bases + mean3", source_ticket="step-05150-8",
            dev_split="F1: fit <= 2021, score 2022-2026, official ccn_tools.score.score_c1",
            dev_score=dev["score"], dev_aggregate_mape=dev["aggregate_mape"], dev_parcel_nrmse=dev["parcel_nrmse"],
            baseline_score=base["score"], rows=len(sub),
            mean_pred_by_crop={c: round(float(v), 3) for c, v in sub.groupby("crop").yield_t_ha_pred.mean().items()},
            note="synthetic pack only")
(SHIP / "median19.json").write_text(json.dumps(info, indent=1))   # no timing inside: the file must be byte-stable
print(f"wrote {outp.relative_to(Path(boot.HERE).parent)}: {len(sub)} rows; mean by crop {info['mean_pred_by_crop']}  [{time.time() - T0:.1f}s]")
