"""Shared loaders for C3. All paths relative to the repo; nothing here reads answer keys or truth files."""
from ccn_paths import PACKAGE, stage_dir
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = PACKAGE
D = PACKAGE / "data"
OUT = stage_dir("c3_euro_risk")
CROPS = ["pea", "potato", "carrot", "spinach", "turnip_rape"]


def survey_clean():
    """FI survey yields. Planted decimal/unit slips (e.g. pea 43.1 t/ha) are dropped with the same rule the
    organisers' baseline uses (> 3 x crop median); the count dropped is printed by facts_check.py."""
    sv = pd.read_csv(D / "03_farming/farm_survey_fi.csv")
    med = sv.groupby("crop").yield_t_ha.transform("median")
    bad = (sv.yield_t_ha > 3 * med) | (sv.yield_t_ha < med / 3)
    sv = sv.assign(dropped=bad)
    return sv


def foodhills():
    fh = pd.read_csv(D / "03_farming/foodhills_odlingsdata_se.csv", sep=";", decimal=",")
    fh = fh.rename(columns={"odlar_id": "farm_id", "skördeår": "year", "areal_ha": "area_ha",
                            "levererad_mängd_ton": "delivered_t", "bevattnad": "irr"})
    fh["crop"] = "pea"
    fh["irrigated"] = fh.irr.eq("ja")
    fh["yield_t_ha"] = fh.delivered_t / fh.area_ha
    med = fh.yield_t_ha.median()
    fh["dropped"] = (fh.yield_t_ha > 3 * med) | (fh.yield_t_ha < med / 3) | (fh.area_ha <= 0)
    return fh


def contract_area(year=2025):
    """Contract-crop area by region x crop from declared crop history x parcel area."""
    ch = pd.read_csv(D / "03_farming/parcel_crop_history_and_plan.csv")
    par = pd.read_csv(D / "01_master/parcels.csv")
    fr = pd.read_csv(D / "01_master/farm_registry.csv")[["farm_id", "region", "segment"]]
    ch = ch[(ch.year == year) & ch.crop.isin(CROPS)].merge(par[["parcel_id", "area_ha", "lat", "lon"]], on="parcel_id")
    ch = ch.merge(fr, on="farm_id")
    return ch


def cells():
    return pd.read_csv(D / "01_master/climate_grid_cells.csv")


def nearest_cell(lat, lon, cg):
    d = (cg.lat.values[None, :] - np.asarray(lat)[:, None]) ** 2 + ((cg.lon.values[None, :] - np.asarray(lon)[:, None]) * 0.5) ** 2
    return cg.cell_id.values[d.argmin(1)]


def weather_monthly():
    return pd.read_csv(D / "04_climate/weather_monthly_1991_2060.csv")


def prices():
    return pd.read_csv(D / "05_scenarios/contract_prices_and_replacement_premiums.csv")
