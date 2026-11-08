"""Facts checker: does the twin match the task's stated facts? Runs first. Prints PASS/FAIL per fact.
Stated facts (SIMULATION_DESIGN.md calibration table, SCENARIOS_AND_RISK.md 'Known 2026 contrast'):
  FI peas ~2,000 ha at ~3 t/ha; FI potato/carrot/spinach 350/200/300 ha; potato ~31, carrot ~48, turnip rape ~1.3 t/ha;
  2026: record FI pea harvest, heat/drought-hit SE peas.
Tolerances are set here before looking at results: areas +/-25 %, yields +/-25 %."""
from common import *  # noqa

res = []
def chk(name, val, target, tol):
    ok = abs(val - target) <= tol * target
    res.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} {name}: {val:.2f} vs stated {target} (tol {tol:.0%})")

ca = contract_area(2025)
a = ca.groupby(["region", "crop"]).area_ha.sum()
print("2025 contract area by region x crop (ha):"); print(a.round(0).to_string())
chk("FI pea area 2025", a[("FI_SW", "pea")], 2000, .25)
chk("FI potato area 2025", a[("FI_SW", "potato")], 350, .25)
chk("FI carrot area 2025", a[("FI_SW", "carrot")], 200, .25)
chk("FI spinach area 2025", a[("FI_SW", "spinach")], 300, .25)

sv = survey_clean()
print(f"survey rows {len(sv)}, dropped as implausible (>3x or <1/3 crop median): {int(sv.dropped.sum())}")
s = sv[~sv.dropped & sv.year.between(2022, 2024)]
ym = s.groupby("crop").apply(lambda g: np.average(g.yield_t_ha, weights=g.area_ha), include_groups=False)
chk("FI pea yield 2022-24", ym["pea"], 3.0, .25)
chk("potato yield 2022-24", ym["potato"], 31, .25)
chk("carrot yield 2022-24", ym["carrot"], 48, .25)
chk("turnip rape yield 2022-24", ym["turnip_rape"], 1.3, .25)

fh = foodhills()
print(f"foodhills rows {len(fh)}, dropped: {int(fh.dropped.sum())}")
fi = sv[~sv.dropped & (sv.crop == "pea")].groupby("year").apply(lambda g: np.average(g.yield_t_ha, weights=g.area_ha), include_groups=False)
se = fh[~fh.dropped].groupby("year").apply(lambda g: g.delivered_t.sum() / g.area_ha.sum(), include_groups=False)
fi_rank = int((fi >= fi[2026]).sum()); se_rank = int((se <= se[2026]).sum())
print(f"FI pea 2026 yield {fi[2026]:.2f} t/ha, rank {fi_rank} best of {len(fi)} years (2012-2026)")
print(f"SE pea 2026 yield {se[2026]:.2f} t/ha, rank {se_rank} worst of {len(se)} years (2018-2026)")
ok = fi_rank <= 2; res.append(ok); print(f"{'PASS' if ok else 'FAIL'} 2026 FI pea among 2 best years")
ok = se_rank <= 2; res.append(ok); print(f"{'PASS' if ok else 'FAIL'} 2026 SE pea among 2 worst years")
print(f"FACTS {'PASS' if all(res) else 'FAIL'} ({sum(res)}/{len(res)})")
