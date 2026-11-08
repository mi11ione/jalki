"""C2 shipped model, rebuilt: c2-risk-3 variant PC (ticket step-00323-5, promoted there by its frozen rule).

PC = sensitivity scale s per region x crop shrunk (empirical Bayes) toward the precision-weighted pooled mean of
s_hat ("P"), plus one pooled additive offset on p_bad_year = mean(observed bad-year share - model in-sample p_bad)
over the calibration seasons ("C"). For the submission, everything is fitted on all observed seasons 2012-2026,
exactly as c2r3.py rows18("PC"). The functions below are c2r3.py's, verbatim except that they read this run's own
stage outputs. There is no random step. c2r3.py's bootstrap, scramble test and rolling windows only decided and
checked the promotion; they never touch the file, so they are not re-run here (compute policy).

Writes $CCN_OUT/c2_climate_risk/ship/C2_climate_yield_risk_submission.csv and ship/pc.json (official F1 dev score:
calibration <= 2021, dev 2022-2026, 6 rows). Does NOT touch $CCN_OUT/c2_climate_risk/C2_climate_yield_risk_submission.csv
(c2-risk-2): the ported cited figures SHA-check that file as their c2-risk-2 input. Synthetic pack only."""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import c2lib as C  # noqa: E402
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from ccn_tools.baselines import c2_null
from ccn_tools.score import score_c2

D = str(C.D)
ROWS = [("FI_SW", c) for c in ["carrot", "pea", "potato", "spinach", "turnip_rape"]] + [("SE_SKANE", "pea")]
SHIP = Path(C.HERE) / "ship"
SHIP.mkdir(exist_ok=True)


def rd(rel, sep=","):
    with open(os.path.join(D, rel), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=sep))


def fnum(s):
    return float(s.replace(",", "."))


# ---- labels (c2r3.py section 1)
par, ch = rd("data/01_master/parcels.csv"), rd("data/03_farming/parcel_crop_history_and_plan.csv")
sv, fh = rd("data/03_farming/farm_survey_fi.csv"), rd("data/03_farming/foodhills_odlingsdata_se.csv", ";")
reg = rd("data/01_master/farm_registry.csv")
region_of = {r["farm_id"]: r["region"] for r in reg}
par_area = {r["parcel_id"]: float(r["area_ha"]) for r in par}
med_all = {c: statistics.median(float(r["yield_t_ha"]) for r in sv if r["crop"] == c) for c in {r["crop"] for r in sv}}
fi = [dict(farm_id=r["farm_id"], crop=r["crop"], year=int(r["year"]), y=float(r["yield_t_ha"]))
      for r in sv if float(r["yield_t_ha"]) <= 2.5 * med_all[r["crop"]]]
se = [dict(farm_id=r["odlar_id"], crop="pea", year=int(r["skördeår"]), y=fnum(r["levererad_mängd_ton"]) / fnum(r["areal_ha"])) for r in fh]
dec_area = defaultdict(float)
for r in ch:
    if r["status"] == "declared" and r["parcel_id"] in par_area and r["farm_id"] in region_of:
        dec_area[(r["farm_id"], r["crop"], int(r["year"]))] += par_area[r["parcel_id"]]
rec = []
for r in fi + se:
    k = (r["farm_id"], r["crop"], r["year"])
    if r["farm_id"] in region_of and r["year"] <= 2026 and k in dec_area and r["y"] > 0:
        rec.append(dict(r, region=region_of[r["farm_id"]], area=dec_area[k], ly=math.log(r["y"])))


def season_effects(records):
    fm = defaultdict(list)
    for r in records:
        fm[(r["farm_id"], r["crop"])].append(r["ly"])
    fmean = {k: statistics.mean(v) for k, v in fm.items()}
    acc = defaultdict(lambda: [0.0, 0.0, []])
    for r in records:
        k = (r["region"], r["crop"], r["year"])
        res = r["ly"] - fmean[(r["farm_id"], r["crop"])]
        acc[k][0] += r["area"] * res
        acc[k][1] += r["area"]
        acc[k][2].append(res)
    return ({k: v[0] / v[1] for k, v in acc.items()},
            {k: (statistics.variance(v[2]) / len(v[2]) if len(v[2]) > 1 else None) for k, v in acc.items()})


E, SAMP = season_effects(rec)

# ---- model pieces (c2r3.py section 2)
mix = C.parcel_mix_2025()
df = C.observed()
feat = pd.read_parquet(C.OUT / "feat_c2.parquet")
feat_hist = feat[feat.series == "hist"]
T975 = {2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201,
        12: 2.179, 13: 2.160, 14: 2.145}


def s_table(d):
    n_seasons = d.groupby(["region", "crop"]).year.nunique()
    keep = [k for k, v in n_seasons.items() if v >= 3]
    d = d[[k in keep for k in zip(d.region, d.crop)]].reset_index(drop=True)
    sc = C.scale_estimates(d)
    out = {}
    for k, r in sc.iterrows():
        G = int(n_seasons[k])
        se_ = (r.s_hat - r.lo) / {8: 2.306, 14: 2.145}.get(G - 1, 2.2)
        out[k] = dict(G=G, s_hat=float(r.s_hat), se=float(se_), lo=float(r.s_hat - T975[G - 1] * se_),
                      hi=float(r.s_hat + T975[G - 1] * se_), max_year=int(d[(d.region == k[0]) & (d.crop == k[1])].year.max()))
    return out


def s_ebpool(t):
    w = {k: 1 / v["se"] ** 2 for k, v in t.items()}
    m = sum(w[k] * v["s_hat"] for k, v in t.items()) / sum(w.values())
    tau2 = max(0.0, statistics.mean((v["s_hat"] - m) ** 2 - v["se"] ** 2 for v in t.values()))
    return {k: float(np.clip(m + tau2 / (tau2 + v["se"] ** 2) * (v["s_hat"] - m), 0, 1.5)) for k, v in t.items()}, dict(target=m, tau2=tau2)


def index_of(s, fe=feat_hist):
    y = C.index_series(mix, s, fe)
    return {(r.region, r.crop, int(r.year)): float(r.Y) for r in y.itertuples()}


def fitted(cal_end):
    dcal = df[df.year <= cal_end]
    t = s_table(dcal)
    assert max(v["max_year"] for v in t.values()) <= cal_end, "dev season reached the s fit"
    s, info = s_ebpool(t)
    Ec, Sc = season_effects([r for r in rec if r["year"] <= cal_end])
    assert max(k[2] for k in Ec) <= cal_end
    return index_of(s), Ec, Sc


def phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def linfit(t, v):
    tm, vm = statistics.mean(t), statistics.mean(v)
    b = sum((a - tm) * (c - vm) for a, c in zip(t, v)) / sum((a - tm) ** 2 for a in t)
    return vm - b * tm, b


def p_model(Y, mY, sig, years):
    if sig > 0:
        return statistics.mean(phi((math.log(0.8 * mY) - math.log(Y[y])) / sig) for y in years)
    return sum(Y[y] < 0.8 * mY for y in years) / len(years)


def fold_pc(cal_end, dev_years, rows=ROWS):
    """c2r3.py fold('PC', ...): predictions use only the weather index Y and calibration-season labels."""
    Yall, Ec, Sc = fitted(cal_end)
    out = []
    for reg_, crop in rows:
        seasons = sorted(y for (a, b, y) in E if a == reg_ and b == crop)
        cal = [y for y in seasons if y <= cal_end]
        dev = [y for y in seasons if y in dev_years]
        if len(cal) < 3 or not dev:
            continue
        I = {y: math.exp(E[(reg_, crop, y)]) for y in seasons}
        mI = statistics.mean(I[y] for y in cal)
        chg_t = 100 * (statistics.mean(I[y] for y in dev) / mI - 1)
        pb_t = sum(I[y] < 0.8 * mI for y in dev) / len(dev)
        Y = {y: Yall[(reg_, crop, y)] for y in seasons}
        mY = statistics.mean(Y[y] for y in cal)
        chg_m = 100 * (statistics.mean(Y[y] for y in dev) / mY - 1)
        u = [Ec[(reg_, crop, y)] - math.log(Y[y]) for y in cal]
        a, b = linfit(cal, u)
        v_tot = sum((ui - (a + b * y)) ** 2 for ui, y in zip(u, cal)) / (len(cal) - 2)
        sv_ = [Sc[(reg_, crop, y)] for y in cal if Sc[(reg_, crop, y)] is not None]
        sig = math.sqrt(max(0.0, v_tot - (statistics.mean(sv_) if sv_ else 0.0)))
        pb_m = p_model(Y, mY, sig, dev)
        Ic = {y: math.exp(Ec[(reg_, crop, y)]) for y in cal}
        mIc = statistics.mean(Ic.values())
        obs_cal = sum(Ic[y] < 0.8 * mIc for y in cal) / len(cal)
        pin_cal = p_model(Y, mY, sig, cal)
        out.append(dict(region=reg_, crop=crop, chg_true=chg_t, pb_true=pb_t, chg_pred=chg_m, pb_pred=pb_m,
                        obs_cal=obs_cal, pin_cal=pin_cal, sigma=sig))
    delta = statistics.mean(r["obs_cal"] - r["pin_cal"] for r in out)
    for r in out:
        r["pb_pred"] = min(1.0, max(0.0, r["pb_pred"] + delta))
        r["delta"] = delta
    return out


def frames(rows):
    key = pd.DataFrame(dict(region=[r["region"] for r in rows], crop=[r["crop"] for r in rows], scenario="dev", period="dev",
                            mean_yield_change_pct=[r["chg_true"] for r in rows], p_bad_year=[r["pb_true"] for r in rows]))
    sub = key.copy()
    sub["mean_yield_change_pct"] = [r["chg_pred"] for r in rows]
    sub["p_bad_year"] = [r["pb_pred"] for r in rows]
    return sub, key


# ---- official F1 dev score (cal <= 2021, dev 2022-2026), as c2r3.py reported it
F1 = fold_pc(2021, set(range(2022, 2027)))
assert len(F1) == 6
dev = score_c2(*frames(F1))
null = score_c2(c2_null(frames(F1)[1]), frames(F1)[1])
print(f"PC F1 official dev score {dev}; null {null}")

# ---- submission (c2r3.py rows18('PC')): all observed seasons
s_full, info = s_ebpool(s_table(df))
p = C.summarise(C.index_series(mix, s_full, feat), C.year_noise(df, s_full), fut_prefix="delta_")
tpl = pd.read_csv(C.D / "tasks/templates/C2_climate_yield_risk_submission.csv")
o = tpl[["region", "crop", "scenario", "period"]].merge(p, on=["region", "crop", "scenario"], how="left")
dlt = fold_pc(2026, set(range(2012, 2027)))[0]["delta"]
o["p_bad_year"] = (o.p_bad_year + dlt).clip(0, 1)
o = o[["region", "crop", "scenario", "period", "mean_yield_change_pct", "p_bad_year"]].copy()
o["mean_yield_change_pct"] = o.mean_yield_change_pct.round(2)
o["p_bad_year"] = o.p_bad_year.round(3)
assert len(o) == 18 and o.notna().all().all() and list(o.columns) == list(tpl.columns)
outp = SHIP / "C2_climate_yield_risk_submission.csv"
o.to_csv(outp, index=False)
res = dict(model="c2-risk-3 PC: EB-pooled sensitivity scale + pooled p_bad offset", source_ticket="step-00323-5",
           dev_split="F1: calibration <= 2021, dev 2022-2026, 6 rows, official ccn_tools.score.score_c2",
           dev_score=dev["score"], dev=dev, null_score=null["score"], submission_offset_delta=dlt,
           pooled_target=info["target"], tau2=info["tau2"], s={f"{k[0]}|{k[1]}": v for k, v in s_full.items()},
           note="synthetic pack only")
(SHIP / "pc.json").write_text(json.dumps(res, indent=1, default=float))
print(f"submission offset delta {dlt:+.4f}; s {({f'{k[0][:2]}/{k[1]}': round(v, 3) for k, v in s_full.items()})}")
print(f"wrote ship/C2_climate_yield_risk_submission.csv: 18 rows")
