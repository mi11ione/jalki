"""Shared: read-only import of the e-copilot pipeline and the answer functions copied from
stages/e_copilot/s11_answers.py (numeric, flag_total, deliveries). Nothing is written to stages/e_copilot."""
from ccn_paths import PACKAGE, stage_dir
import sys, json, warnings
sys.dont_write_bytecode = True
warnings.filterwarnings("ignore")
from pathlib import Path
HERE = stage_dir("e_copilot")
W = HERE.parent
import numpy as np, pandas as pd
import pipeline as P
import farm as FM
from clean import ROOT, F
from ccn_tools import reference_calculator as RC, score as SC
D = ROOT / "data"
SOIL = json.loads((HERE / "soil.json").read_text())
KEY1 = "cat01_purchased_goods_services"
RAPE = ["M101", "M102", "M103", "M104", "M105", "M106", "M107"]
IMP = RAPE[1:]


def build(pm=0.90, pc=0.40, b_low=None):
    FM.P_MAP_ORG, FM.P_CLUSTER = pm, pc
    b = P.build(mode="rate", b_low=SOIL["b_low"] if b_low is None else b_low)
    FM.P_MAP_ORG, FM.P_CLUSTER = 0.90, 0.40
    return b


def flag_total(b, y=2025):
    inv = b["inv"][y]; T = b["T"]
    ef = T["ef_library"].set_index("ef_id").flag_share
    mm = T["materials"].set_index("material_id").default_ef_id
    g = inv[(inv.category == "cat01_purchased_goods") & ~inv.line_item.str.startswith("contract_farming")].copy()
    g["fs"] = g.line_item.str.split(":").str[0].map(mm).map(ef)
    f = b["farms"][b["farms"].year == y]
    return float((g.tco2e * g.fs).sum()), float(f.t_flag_min.sum() + f.t_org.sum())


def pea_series(b):
    raw, sv, erp = b["raw"], b["sv"], b["erp"]
    m = FM.contract_parcels(raw); pea = m[m.crop == "pea"].groupby(["farm_id", "year"]).area_ha.sum().rename("area").reset_index()
    s = sv[sv.crop == "pea"][["farm_id", "year", "yield_t_ha"]]
    prod, act = {}, {}
    for y in range(2021, 2027):
        a = pea[pea.year == y].merge(s[s.year == y], on=["farm_id", "year"], how="left")
        r = a[a.yield_t_ha.notna()]
        yw = (r.yield_t_ha * r.area).sum() / r.area.sum()
        prod[y] = (a.yield_t_ha.fillna(yw) * a.area).sum()
        if y < 2026:
            act[y] = erp[(erp.material_id == "M110") & (erp.year == y)].qty_kg.sum() / 1000
    return prod, act


def numeric(b):
    inv = b["inv"][2025]; T = b["T"]; A = {}
    s = RC.summarise(inv).set_index("category").tco2e
    en = T["energy"]; e25 = en[en.year == 2025]
    item = lambda sc, it: float(inv[(inv.scope == sc) & inv.line_item.isin(it)].tco2e.sum())
    A["E01"] = item("scope1", ["S-SAK:lng", "S-SAK:lpg"])
    A["E02"] = float(s["scope2_market_total"])
    A["E03"] = float(inv[(inv.scope == "scope2_location") & (inv.line_item == "S-KAN")].tco2e.sum())
    c1 = inv[inv.category == "cat01_purchased_goods"]
    mat = c1.line_item.str.split(":").str[0]
    A["E04"] = float(c1[mat.isin(IMP)].tco2e.sum())
    f = b["farms"][b["farms"].year == 2025]
    tr = f[f.crop == "turnip_rape"]; pea = f[f.crop == "pea"]
    A["E05"] = 100 * (float(c1[mat.isin(RAPE)].tco2e.sum()) + float(tr.tco2e.sum())) / float(s[KEY1])
    total = float(s["scope1_total"] + s["scope2_market_total"] + s["scope3_total"])
    fp, ff = flag_total(b)
    flag = fp + ff
    A["E06"] = 100 * flag / total
    A["E07"] = 100 * float(f.t_org.sum() / f.tco2e.sum())
    tot, hard, _ = FM.count_ge30(b["raw"], b["post"], 2025)
    A["E08"] = float(tot)
    k = e25[e25.site_id == "S-KAN"].groupby("carrier").mwh.sum()
    A["E09"] = float(sum(k.get(c, 0) * F.FUEL_BIOGENIC_T_PER_MWH.get(c, 0) for c in k.index))
    sk = e25[e25.site_id == "S-SAK"].groupby("carrier").mwh.sum()
    A["E10"] = float(sk["electricity"])
    goo = T["goo"]; g = float(goo[(goo.year == 2025) & (goo.site_id == "S-SAK") & (goo.vintage_year == 2025)].mwh_cancelled.sum())
    A["E11"] = 100 * float((sk.get("biogas", 0) + min(g, sk["electricity"])) / sk.sum())
    w = b["raw"]["water"]; w = w[w.year == 2024]
    wd = w[(w.flow == "withdrawal") & (w.source_or_destination != "reused_water")].m3.sum(); dc = w[w.flow == "discharge"].m3.sum()
    A["E12"] = float(wd - dc)
    A["E13"] = float(inv[(inv.category == "fugitive_refrigerants") & inv.line_item.str.startswith("S-SAK:")].tco2e.sum())
    A["E14"] = float(inv[inv.line_item.isin(["inbound:EF-TKM-SHIP-BULK", "inbound:EF-TKM-SHIP-REEFER"])].tco2e.sum())
    e = b["erp"]; A["E15"] = float(e[(e.year == 2025) & (e.material_id == "M130")].qty_kg.sum() / 1000)
    A["E16"] = float(pea.tco2e.sum() * 1000 / pea.kg.sum())
    A["E17"] = float(tr.tco2e.sum() * 1000 / tr.kg.sum())
    prod, act = pea_series(b)
    A["E18"] = float(100 * (prod[2026] * np.mean([act[y] / prod[y] for y in act]) / act[2025] - 1))
    fh = pd.read_csv(D / "03_farming" / "foodhills_odlingsdata_se.csv", sep=";", decimal=",")
    t = fh.groupby("skördeår")["levererad_mängd_ton"].sum()
    A["E19"] = float(100 * (t[2026] / t[2025] - 1))
    s12 = float(s["scope1_total"] + s["scope2_market_total"])
    A["E20"] = s12 * (1 - 0.042 * 7)
    A["E21"] = flag * (1 - 0.0303 * 7)
    s24 = RC.summarise(b["inv"][2024]).set_index("category").tco2e
    A["E90"], A["E91"], A["E92"] = float(s24["scope1_total"]), float(s24["scope2_market_total"]), float(s24[KEY1])
    X = dict(s=s, flag=flag, total=total, wd=float(wd), dc=float(dc), reused=float(w[(w.flow == "withdrawal") & (w.source_or_destination == "reused_water")].m3.sum()), prod=prod, act=act)
    return A, X
