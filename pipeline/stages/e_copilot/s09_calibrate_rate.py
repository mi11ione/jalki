"""Cross-year test of the three-cell soil table, same protocol as s08 (the logit offset).
Rule fixed before this run: keep the model with the smaller worst held-out cat 1 error.
b_low is fitted on one year's key and tested on the other. Final b_low = mean of folds, written to soil.json."""
from ccn_paths import PACKAGE, stage_dir
import json, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
import pipeline as P
import farm as FM
from clean import ROOT
from ccn_tools import reference_calculator as RC
K = {y: pd.read_csv(ROOT / "tasks" / "dev" / f"A2_dev_inventory_{y}.csv").set_index("category").tco2e for y in (2023, 2024)}
KEY = "cat01_purchased_goods_services"


def cat1(inv, y):
    return RC.summarise(inv[y]).set_index("category").tco2e[KEY]


def fit(label_year, target_year):
    b = P.build(label_years=(label_year,), mode="rate", b_low=0.0)
    f = b["farms"][b["farms"].year == target_year]
    need = (K[target_year][KEY] - (cat1(b["inv"], target_year) - f.t_org.sum())) * 1000 / FM.ORG_KG_HA
    m = FM.contract_parcels(b["raw"]); m = m[m.year == target_year]
    p = m.parcel_id.map(b["post"].p_org).values; ar = m.area_ha.values
    free = (p == 0) & ~m.parcel_id.map(b["post"].known).values.astype(bool)
    base = float((p * ar).sum()); room = float(ar[free].sum())
    bl = (need - base) / room
    print(f"labels {label_year} -> target {target_year}: need {need:.0f} ha, table at b_low=0 gives {base:.0f} ha, free area {room:.0f} ha, b_low {bl:.4f}")
    return bl


b1 = fit(2023, 2024)
b2 = fit(2024, 2023)
errs = []
for lab_y, test_y, bl, src in ((2024, 2023, b1, "b_low fitted on 2024 key"), (2023, 2024, b2, "b_low fitted on 2023 key")):
    b = P.build(label_years=(lab_y,), mode="rate", b_low=max(bl, 0.0))
    c = cat1(b["inv"], test_y); k = K[test_y][KEY]
    errs.append(abs(c / k - 1))
    print(f"HELD-OUT cat1 {test_y} ({src}, labels {lab_y}): mine {c:.0f} key {k:.0f} err {100*(c/k-1):+.2f}%")
print("worst held-out error, rate table %.2f%% ; logit offset from s08 was 4.12%%" % (100 * max(errs)))
bl = max((b1 + b2) / 2, 0.0)
(stage_dir("e_copilot") / "soil.json").write_text(json.dumps(dict(mode="rate", b_low=bl, fold_2024=b1, fold_2023=b2)))
print("final b_low", round(bl, 4))
