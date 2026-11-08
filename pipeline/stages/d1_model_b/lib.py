"""Stdlib-only helpers for D1 (this Python has no pandas/numpy).

score_d1() is a line-by-line port of <package>/tools/ccn_tools/score.py::score_d1.
Its fidelity is checked by baseline.py, which must reproduce the documented baseline dev score (12.0).
"""
from ccn_paths import PACKAGE, stage_dir
import csv
import math
from collections import defaultdict
from pathlib import Path

ROOT = PACKAGE
HERE = stage_dir("d1_model_b")
STATE_WEIGHT = {"good": 1.0, "moderate": 1.2, "poor": 1.5, "bad": 1.8}
APETIT_CROPS = ["pea", "potato", "carrot", "spinach", "turnip_rape"]


def read(rel, delim=","):
    with open(ROOT / rel, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=delim))


def fnum(x, default=None):
    if x is None or x == "":
        return default
    return float(str(x).replace(",", "."))


def median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return float("nan")
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def rank_avg(vals, ascending=True):
    """pandas Series.rank(method='average')."""
    idx = sorted(range(len(vals)), key=lambda i: vals[i] if ascending else -vals[i])
    r = [0.0] * len(vals)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and vals[idx[j + 1]] == vals[idx[i]]:
            j += 1
        for k in range(i, j + 1):
            r[idx[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((x - mb) ** 2 for x in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa and sb else float("nan")


def spearman(a, b):
    return pearson(rank_avg(a), rank_avg(b))


def score_d1(sub, key):
    """sub: {cid: (p, n, rank)}; key: {cid: (p, n)} or (p, n, priority_score)."""
    ids = list(key)
    P = [key[c][0] for c in ids]
    N = [key[c][1] for c in ids]
    if len(key[ids[0]]) > 2:
        pr = [key[c][2] for c in ids]
    else:
        mp_, mn_ = median(P), median(N)
        pr = [p / mp_ + 0.5 * n / mn_ for p, n in zip(P, N)]
    rk_true = rank_avg(pr, ascending=False)
    prk = [sub[c][2] if c in sub and sub[c][2] is not None else len(ids) for c in ids]
    rho = spearman(rk_true, prk) if len(ids) > 2 else float("nan")
    k = min(5, len(ids))
    top_t = {c for c, r in zip(ids, rk_true) if r <= k}
    order = sorted(ids, key=lambda c: (prk[ids.index(c)], ids.index(c)))
    top_p = set(order[:k])
    overlap = len(top_t & top_p) / k
    act = [c for c in ids if key[c][0] > 1.0]

    def mae(j):
        if not act:
            return 0.0
        e = []
        for c in act:
            t = math.log10(max(key[c][j], 0.1))
            pv = sub[c][j] if c in sub and sub[c][j] is not None else 0.1
            e.append(abs(t - math.log10(max(pv, 0.1))))
        return sum(e) / len(e)

    mp, mn = mae(0), mae(1)
    rr = rho if not math.isnan(rho) else 0
    sc = 100 * (0.1 * max(0, rr) + 0.1 * overlap + 0.4 * max(0, 1 - mp / 0.15) + 0.4 * max(0, 1 - mn / 0.15))
    return dict(score=round(sc, 2), spearman=round(rho, 4), top5_overlap=round(overlap, 3),
                mae_log10_p=round(mp, 4), mae_log10_n=round(mn, 4))


def solve(A, b):
    """Gaussian elimination with partial pivoting."""
    n = len(A)
    M = [list(map(float, A[i])) + [float(b[i])] for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i]))
        M[i], M[p] = M[p], M[i]
        if abs(M[i][i]) < 1e-300:
            raise ValueError("singular")
        for r in range(n):
            if r != i:
                f = M[r][i] / M[i][i]
                for k in range(i, n + 1):
                    M[r][k] -= f * M[i][k]
    return [M[i][n] / M[i][i] for i in range(n)]


def lstsq(X, y, w=None):
    """Weighted least squares via normal equations. X: rows of features."""
    k = len(X[0])
    w = w or [1.0] * len(y)
    A = [[sum(wi * r[i] * r[j] for r, wi in zip(X, w)) for j in range(k)] for i in range(k)]
    b = [sum(wi * r[i] * yi for r, yi, wi in zip(X, y, w)) for i in range(k)]
    return solve(A, b)


def monitored():
    from collections import defaultdict as dd
    m = dd(dict)
    for r in read("data/06_nature/monitored_catchment_loads.csv"):
        m[r["catchment_id"]][int(r["year"])] = (float(r["total_p_load_kg"]), float(r["total_n_load_kg"]))
    return m


def weather_annual(scenario="historical"):
    """{(cell, year): dict(precip, precip_ond, pet, tmean)}; also returns cell coords."""
    from collections import defaultdict as dd
    acc = dd(lambda: dict(precip=0.0, pet=0.0, precip_nongrow=0.0))
    with open(ROOT / "data/04_climate/weather_monthly_1991_2060.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r["scenario"] != scenario:
                continue
            y, m = int(r["year"]), int(r["month"])
            a = acc[(r["cell_id"], y)]
            pr = float(r["precip_mm"])
            a["precip"] += pr
            a["pet"] += float(r["pet_mm"])
            if m in (1, 2, 3, 4, 10, 11, 12):
                a["precip_nongrow"] += pr
    cells = {r["cell_id"]: (float(r["lat"]), float(r["lon"])) for r in read("data/01_master/climate_grid_cells.csv")}
    return dict(acc), cells


def nearest_cell(cells, lat, lon):
    return min(cells, key=lambda c: (cells[c][0] - lat) ** 2 + ((cells[c][1] - lon) * math.cos(math.radians(lat))) ** 2)


def load_dev():
    return {r["catchment_id"]: (float(r["apetit_p_to_water_kg"]), float(r["apetit_n_to_water_kg"]))
            for r in read("tasks/dev/D1_dev_catchments_2025.csv")}


def catchments():
    return {r["catchment_id"]: r for r in read("data/06_nature/catchments.csv")}


def priority_ranks(cat, P, N):
    """Official formula over all catchments; rank 1 = highest priority (ties: first)."""
    ids = list(cat)
    mp = median([P[c] for c in ids])
    mn = median([N[c] for c in ids])
    pr = {c: (P[c] / max(mp, 1e-6) + 0.5 * N[c] / max(mn, 1e-6)) * STATE_WEIGHT[cat[c]["ecological_status_class"]]
          * float(cat[c]["p_sensitivity"]) for c in ids}
    order = sorted(ids, key=lambda c: (-pr[c], ids.index(c)))
    return {c: i + 1 for i, c in enumerate(order)}, pr


def write_submission(path, cat, P, N, rk):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["catchment_id", "region", "apetit_p_to_water_kg", "apetit_n_to_water_kg", "priority_rank"])
        for c in cat:
            w.writerow([c, cat[c]["region"], round(P[c], 2), round(N[c], 1), rk[c]])
