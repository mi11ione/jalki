"""Shared helpers for D1 (stdlib only).

score_d1() is a line-by-line port of <package>/tools/ccn_tools/score.py::score_d1.
Port is validated by reproducing the documented baseline dev score (12.0) in check_scorer.py.
"""
from ccn_paths import PACKAGE, stage_dir
import csv, math
from pathlib import Path

TWIN = PACKAGE
DATA = TWIN / "data"
WORK = stage_dir("d1_model_a")
CODE = Path(__file__).resolve().parent
APETIT_CROPS = {"pea", "potato", "carrot", "spinach", "turnip_rape"}
STATE_WEIGHT = {"good": 1.0, "moderate": 1.2, "poor": 1.5, "bad": 1.8}


def rd(p, delim=","):
    with open(p, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=delim))
    if delim == ";":
        rows = [{k: v.replace(",", ".") for k, v in r.items()} for r in rows]
    return rows


def median(x):
    s = sorted(x); n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def rank_avg(vals, ascending=True):
    """pandas Series.rank(method='average')."""
    idx = sorted(range(len(vals)), key=lambda i: vals[i], reverse=not ascending)
    r = [0.0] * len(vals); i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and vals[idx[j + 1]] == vals[idx[i]]:
            j += 1
        for k in range(i, j + 1):
            r[idx[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def pearson(a, b):
    n = len(a); ma = sum(a) / n; mb = sum(b) / n
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    sa = math.sqrt(sum((x - ma) ** 2 for x in a)); sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return sab / (sa * sb) if sa > 0 and sb > 0 else float("nan")


def score_d1(sub, key):
    """sub/key: lists of dict rows (strings or numbers). Mirrors ccn_tools.score.score_d1."""
    K = [dict(cid=r["catchment_id"], p=float(r["apetit_p_to_water_kg"]), n=float(r["apetit_n_to_water_kg"]),
              ps=float(r["priority_score"]) if r.get("priority_score") not in (None, "") else None) for r in key]
    if any(k["ps"] is None for k in K):  # dev key: loads only -> rank part scored on loads
        mp_ = median([k["p"] for k in K]); mn_ = median([k["n"] for k in K])
        for k in K:
            k["ps"] = k["p"] / mp_ + 0.5 * k["n"] / mn_
    S = {r["catchment_id"]: r for r in sub}
    def f(v):
        return float(v) if v not in (None, "") else None
    pr = [f(S.get(k["cid"], {}).get("priority_rank")) for k in K]
    pr = [len(K) if v is None else v for v in pr]
    rk_true = rank_avg([-k["ps"] for k in K])  # rank(ascending=False)
    rho = pearson(rank_avg(rk_true), rank_avg(pr)) if len(K) > 2 else float("nan")
    kk = min(5, len(K))
    top_t = {K[i]["cid"] for i in range(len(K)) if rk_true[i] <= kk}
    order = sorted(range(len(K)), key=lambda i: pr[i])  # stable like pandas sort_values default (quicksort ~ ok for distinct)
    top_p = {K[i]["cid"] for i in order[:kk]}
    overlap = len(top_t & top_p) / kk
    act = [k["p"] > 1.0 for k in K]
    def mae(col):
        errs = []
        for k, a in zip(K, act):
            if not a:
                continue
            t = math.log10(max(k[col], 0.1))
            pv = f(S.get(k["cid"], {}).get("apetit_%s_to_water_kg" % col))
            pv = 0.1 if pv is None else pv
            errs.append(abs(t - math.log10(max(pv, 0.1))))
        return sum(errs) / len(errs) if errs else 0.0
    mp, mn = mae("p"), mae("n")
    rr = 0 if math.isnan(rho) else max(0, rho)
    sc = 100 * (0.1 * rr + 0.1 * overlap + 0.4 * max(0, 1 - mp / 0.15) + 0.4 * max(0, 1 - mn / 0.15))
    return dict(score=round(sc, 2), spearman=round(rho, 4), top5_overlap=round(overlap, 3),
                mae_log10_p=round(mp, 4), mae_log10_n=round(mn, 4))


def dev_key():
    return rd(TWIN / "tasks" / "dev" / "D1_dev_catchments_2025.csv")


def write_csv(path, rows, cols):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r[c] for c in cols})
