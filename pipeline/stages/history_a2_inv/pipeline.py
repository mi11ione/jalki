"""End-to-end: raw -> clean (clean.py, farm.py) -> canonical -> ported reference calculator -> score on
public 2023/2024 truths. Used as a module by run.py; prints a farm-model comparison when run."""
import lib, clean, farm


def canonical(c, log, **fk):
    T = lib.naive_canonical(c)          # unit/format conversion of the CLEANED feeds
    T["goo"] = c["goo"]
    T["pcf_used"] = c["pcf_used"]
    T["farm_footprints"] = farm.farm_footprints(c, c["erp"], log, **fk)
    return T


def run(fk=None, years=(2023, 2024, 2025)):
    raw = lib.load_raw()
    c, log = clean.clean(raw)
    T = canonical(c, log, **(fk or {}))
    res = {}
    for y in years:
        rows, bio = lib.compute_inventory(T, y)
        summ = lib.summarise(rows, bio)
        sc = lib.score_a2(summ, lib.dev_key(y)) if y in (2023, 2024) else None
        res[y] = dict(rows=rows, bio=bio, summary=summ, score=sc)
    return res, log, T


if __name__ == "__main__":
    for name, fk in [("register area, soilmap organic x1.00", dict(org_scale=1.0)),
                     ("register area, soilmap organic x1.00, ignore reported", dict(org_scale=1.0, reported_organic=False)),
                     ("survey area, soilmap organic x1.00", dict(org_scale=1.0, area_source="survey"))]:
        res, log, T = run(fk)
        line = []
        for y in (2023, 2024):
            s, d = res[y]["score"]
            farmt = sum(r["tco2e"] for r in res[y]["rows"] if r["line_item"].startswith("contract_farming"))
            line.append(f"{y}: score {s:6.2f} cat01 err {d['cat01_purchased_goods_services'][0]:5.2f}% farm {farmt:8.1f}")
        f25 = sum(r["tco2e"] for r in res[2025]["rows"] if r["line_item"].startswith("contract_farming"))
        print(f"{name:55s} | " + " | ".join(line) + f" | 2025 farm {f25:8.1f}")
