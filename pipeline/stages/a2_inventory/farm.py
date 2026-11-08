"""Contract-farm footprint (cat01, FI contract crops) from cleaned public data.
Per farm x crop x year with deliveries in ERP (M100, M110-M113):
  emissions = mineral-soil footprint per ha (METHODOLOGY s.5, farm survey inputs) x crop area
            + organic-soil add-on (29.0 t CO2/ha + 13 kg N2O-N/ha) x organic crop area
Crop area and organic area come from the parcel register (crop history x parcels, soil map).
Survey cleaning rules R-SV-* are logged. Swedish (Foodhills) growers are excluded in 2025 (METHODOLOGY s.1)."""
from collections import defaultdict
import lib
from ccn_tools import factors as F

E = F.FARM_EF
ORG_ADD = E["org_soil_co2_t_ha"] * 1000 + E["org_soil_n2o_n_kg_ha"] * E["n2o_n_to_n2o"] * E["n2o_gwp"]   # kg CO2e/ha


def clean_survey(raw, log):
    sv = [dict(s) for s in raw["farm_survey"]]
    by = defaultdict(list)
    for s in sv:
        by[s["crop"]].append(s)
    medn = {c: lib.median([x["n_mineral_kg_ha"] for x in v if x["n_mineral_kg_ha"] is not None]) for c, v in by.items()}
    medy = {c: lib.median([x["yield_t_ha"] for x in v]) for c, v in by.items()}
    for s in sv:
        k = f"farm_survey:{s['survey_id']}"
        n, c = s["n_mineral_kg_ha"], s["crop"]
        if n is not None and medn[c] and medn[c] > 0:
            if n > 5 * medn[c]:
                log.append(dict(table="farm_survey", record_key=k, field="n_mineral_kg_ha", old=n, new=round(n / 10, 2), rule="R-SV-1",
                                reason=f"mineral N {n} > 5x crop median {medn[c]}: decimal shift"))
                s["n_mineral_kg_ha"] = n / 10
            elif n < medn[c] / 5 and n > 0:
                log.append(dict(table="farm_survey", record_key=k, field="n_mineral_kg_ha", old=n, new=round(n * 10, 2), rule="R-SV-1",
                                reason=f"mineral N {n} < 1/5 of crop median {medn[c]}: decimal shift"))
                s["n_mineral_kg_ha"] = n * 10
        if s["yield_t_ha"] > 3 * medy[c]:
            log.append(dict(table="farm_survey", record_key=k, field="yield_t_ha", old=s["yield_t_ha"], new=round(s["yield_t_ha"] / 10, 3), rule="R-SV-2",
                            reason=f"yield {s['yield_t_ha']} t/ha > 3x crop median {medy[c]}: implausible, decimal shift"))
            s["yield_t_ha"] /= 10
    return sv


def register(raw):
    par = {p["parcel_id"]: p for p in raw["parcels"]}
    area, org = defaultdict(float), defaultdict(float)
    for c in raw["crop_history"]:
        if c["status"] != "declared":
            continue
        p = par.get(c["parcel_id"])
        if not p:
            continue
        k = (c["farm_id"], c["crop"], int(c["year"]))
        area[k] += p["area_ha"]
        if p["soil_class_soilmap"] == "organic":
            org[k] += p["area_ha"]
    return area, org


def mineral_kg_ha(s):
    r = dict(s); r["organic_soil"] = False
    return lib.farm_kg_ha(r)


SOILMAP_ACC = 0.88   # docs/DATA_DICTIONARY.md: soil map ~88 % accurate -> mapped organic area ~ 0.88 x true
ORG_SCALE = 1 / SOILMAP_ACC


def farm_footprints(raw, erp_clean, log, org_scale=ORG_SCALE, reported_organic=True, area_source="register", fill="median"):
    sv = clean_survey(raw, log)
    area, org = register(raw)
    svk = {(s["farm_id"], s["crop"], int(s["year"])): s for s in sv}
    deliv = defaultdict(float)
    for e in erp_clean:
        if e["material_id"] in lib.CROP_MAT:
            q = e["quantity"] * (1000 if e["uom"] == "TO" else (1 if e["uom"] == "KG" else 0))
            deliv[(e["supplier_id"], lib.CROP_MAT[e["material_id"]], int(e["posting_date"][:4]))] += q
    med = defaultdict(list)
    for k, s in svk.items():
        med[(k[1], k[2])].append(mineral_kg_ha(s))
    med = {k: (lib.median(v) if fill == "median" else sum(v) / len(v)) for k, v in med.items()}
    out = []
    for (farm, crop, y), kg in deliv.items():
        if not farm.startswith("F"):
            continue   # Swedish growers: outside the 2025 boundary
        s = svk.get((farm, crop, y))
        mk = mineral_kg_ha(s) if s else med[(crop, y)]
        a = area[(farm, crop, y)] if area_source == "register" or not s else s["area_ha"]
        if a == 0 and s:
            a = s["area_ha"]
        share = org[(farm, crop, y)] / area[(farm, crop, y)] if area[(farm, crop, y)] else 0.0
        a_org = min(a, share * a * org_scale)          # soil-map organic area, scaled for map under-detection
        if reported_organic and s and s["soil_type_reported"].lower().startswith("organic"):
            a_org = a                                   # farmer reports organic soil: whole crop area organic
        t = (mk * a + ORG_ADD * a_org) / 1000
        rep = bool(reported_organic and s and s["soil_type_reported"].lower().startswith("organic"))
        out.append(dict(farm_id=farm, crop=crop, year=y, region="FI_SW", tco2e=t, kg=kg, area_ha=a, org_ha=a_org,
                        mineral_kg_ha=mk, map_share=share, reported_organic=rep, survey_id=s["survey_id"] if s else None,
                        src="survey" if s else f"crop-year {fill} (non-respondent)"))
    return out
