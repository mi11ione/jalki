"""The one merged pipeline. Raw feeds -> clean.py (a2-inv rules + registry anchor) -> farm.py (register area, crop-year
median for non-respondents, reported organic = 1, others min(1, k x map share)) -> reference method (lib.py port).
Only k is fitted. Module only; run_final.py writes the outputs. Synthetic pack, not Apetit's real emissions.

Fill rule: the mean was tried first, as the textbook estimator of a total. The median beat it on both held-out folds
(s14_explain.py), so the median stands. That choice used the same folds, so held-out scores carry one selection."""
import sys

sys.dont_write_bytecode = True
import lib, clean, farm

FARM_FILL = "median"


def nonfarm_t(rows):
    return sum(r["tco2e"] for r in rows if r["category"] in ("cat01_purchased_goods", "cat01_purchased_services")
               and not r["line_item"].startswith("contract_farming"))


def farm_rows(c, k, log=None):
    return farm.farm_footprints(c, c["erp"], [] if log is None else log, org_scale=k, fill=FARM_FILL)


def farm_total(rows, y, k):
    """Same arithmetic as farm.py, re-evaluated for another k from one k=1 pass, so fitting needs no re-run."""
    t = 0.0
    for r in rows:
        if r["year"] != y:
            continue
        a = r["area_ha"]
        ao = a if r["reported_organic"] else min(a, r["map_share"] * a * k)
        t += (r["mineral_kg_ha"] * a + farm.ORG_ADD * ao) / 1000
    return t


def fit_k(rows, truth, years):
    lo, hi = 0.5, 3.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if sum(farm_total(rows, y, mid) for y in years) < sum(truth[y] for y in years):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def canonical(c, k, log=None):
    T = lib.naive_canonical(c)
    T["goo"] = c["goo"]
    T["pcf_used"] = c["pcf_used"]
    T["farm_footprints"] = farm_rows(c, k, log)
    return T


def prepare():
    """Returns cleaned tables, the correction log, the k=1 farm rows, implied farm truths and the fitted k values."""
    raw = lib.load_raw()
    c, log = clean.clean(raw)
    rows1 = farm_rows(c, 1.0, log)
    T = canonical(c, 1.0)
    truth = {}
    for y in (2023, 2024):
        inv_rows, _ = lib.compute_inventory(T, y)
        truth[y] = lib.dev_key(y)["cat01_purchased_goods_services"] - nonfarm_t(inv_rows)
    ks = {"fit_2023": fit_k(rows1, truth, [2023]), "fit_2024": fit_k(rows1, truth, [2024]), "pooled": fit_k(rows1, truth, [2023, 2024])}
    return raw, c, log, rows1, truth, ks


def year_result(c, k, y):
    T = canonical(c, k)
    rows, bio = lib.compute_inventory(T, y)
    summ = lib.summarise(rows, bio)
    return T, rows, bio, summ
