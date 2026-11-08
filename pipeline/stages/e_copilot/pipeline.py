"""Canonical tables -> reference calculator. build(label_years) returns everything the answer script needs."""
from __future__ import annotations
import numpy as np
import pandas as pd
import clean as C
import farm as FM
from clean import IO, ROOT, F
from ccn_tools import reference_calculator as RC

SEA = {"EF-TKM-SHIP-BULK": ["M102", "M103", "M104", "M105", "M106", "M107"],
       "EF-TKM-SHIP-REEFER": ["M125", "M130", "M137", "M141"]}


def fill_missing_legs(sh, erp):
    """A doc whose material always travels with a sea leg but has none: add it at that material's median sea distance."""
    s = sh.copy()
    ib = s[s.direction == "inbound"]
    add = []
    for ef, mats in SEA.items():
        docs = erp[erp.material_id.isin(mats) & (erp.movement_type == 101)]
        have = set(ib[ib.ef_id == ef].ref_doc)
        km = ib[ib.ef_id == ef].merge(erp[["doc_no", "material_id"]], left_on="ref_doc", right_on="doc_no").groupby("material_id").km.median()
        road = ib.groupby("ref_doc").t.max()
        for _, r in docs[~docs.doc_no.isin(have) & docs.doc_no.isin(road.index)].iterrows():
            t = road[r.doc_no]
            k = km[r.material_id]
            add.append(dict(shipment_id="FILL", year=r.year, direction="inbound", ref_doc=r.doc_no, ef_id=ef, mode="sea", t=t, km=k, tkm=t * k))
            C.log("shipments", f"ship:{r.doc_no}:{ef}", r.year, "missing_leg", "tkm", None, round(t * k, 1), f"{r.material_id} lot has road leg only; sea leg added at material median {k} km")
    return pd.concat([s, pd.DataFrame(add)], ignore_index=True)


def clean_commuting(c):
    c = c.copy()
    c["mode"] = c["mode"].replace({"Car": "car", "auto": "car", "henkilöauto": "car", "linja-auto": "bus"})
    for i, r in c[c.one_way_km > 1000].iterrows():
        c.loc[i, "one_way_km"] = r.one_way_km / 1000
        C.log("commuting_survey", f"commute:{r.response_id}", 2025, "unit_error", "one_way_km", r.one_way_km, r.one_way_km / 1000, "metres keyed as km")
    return c


def build(label_years=(2023, 2024), years=(2023, 2024, 2025), delta=0.0, mode="rate", b_low=0.0):
    C.LOG.clear()
    raw = IO.load_raw(ROOT)
    R = ROOT / "data" / "02_raw_feeds"
    reg = pd.read_csv(R / "goo_registry_statement.csv")
    sh = pd.read_csv(R / "shipments.csv", dtype={"ref_doc": str})
    lab = pd.read_csv(ROOT / "tasks" / "dev" / "A1_dev_issue_labels_2023_2024.csv")
    T = {k: raw[k] for k in ("sites", "materials", "ef_library", "heat_suppliers", "headcount", "warehousing", "wastewater", "sales")}
    en = C.clean_energy(raw["energy_meter"])
    fu = C.clean_fuels(raw["fuel_deliveries"], raw["fuel_stock"])
    T["energy"] = pd.concat([en, fu[["site_id", "year", "month", "carrier", "mwh"]]], ignore_index=True)
    T["goo"] = C.clean_goo(reg, raw["goo"])
    T["refrigerants"] = C.clean_refrigerants(raw["refrigerants"])[["site_id", "year", "refrigerant", "kg_added"]]
    erp = C.clean_erp(raw["erp"], raw["suppliers"], sh, pd.read_csv(R / "capex_projects.csv"))
    T["purchases"] = erp
    T["pcf_used"] = C.valid_pcfs(raw["pcfs"])
    T["shipments"] = fill_missing_legs(sh, erp)
    T["waste"] = C.clean_waste(raw["waste"])
    T["travel"] = C.clean_travel(raw["travel"])
    T["commuting_survey"] = clean_commuting(raw["commuting"])
    sv = FM.clean_survey(raw["farm_survey"], raw["farm_registry"])
    post, beta, known = FM.soil_posterior(raw, lab, label_years, delta, mode, b_low)
    farms = pd.concat([FM.farm_table(raw, erp, sv, post, y) for y in years], ignore_index=True)
    T["farm_footprints"] = farms[["farm_id", "crop", "year", "region", "tco2e"]]
    inv = {y: RC.compute_inventory(T, y) for y in years}
    return dict(raw=raw, T=T, erp=erp, sv=sv, post=post, beta=beta, known=known, farms=farms, inv=inv, fuels=fu, lab=lab, log=pd.DataFrame(C.LOG))
