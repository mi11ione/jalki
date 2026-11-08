"""C3: price C2 yield risk in EUR, add replacement-import emissions, value adaptation options.

Money rule (SCENARIOS_AND_RISK.md): shortfall volume x contract price x replacement premium = the EXTRA cost of
buying frozen/processed import instead of contract crop (the contract price itself is not paid for undelivered t).
Plan volume = 2025 contract area x plan yield (area-weighted 2022-2026 mean = Apetit's current planning practice).
Comparator = current practice: plan on the historical mean and assume today's climate ('no change' C2 null), i.e.
the same cost computed on the 1991-2020 climate. Climate-driven extra = SSP cost - comparator cost.
Shortfall for year t: max(0, plan - Y_t); Y_t ~ N(pred_t, sd) in index units; closed-form expected shortfall.
Interval: jackknife over leave-one-year-out refits (15 refits, all crops dropped the same year). No Monte Carlo.
Prices: 2026 contract prices, nominal, held flat (no price scenario).
"""
from common import *  # noqa
import json
import c2_model as M
from math import sqrt

SCEN = ["historical", "ssp126", "ssp245", "ssp585"]
YRS = {"historical": range(1991, 2021), "ssp126": range(2041, 2061), "ssp245": range(2041, 2061), "ssp585": range(2041, 2061)}
PRICE_ITEM = {("FI_SW", "pea"): "pea", ("SE_SKANE", "pea"): "pea_SE", ("FI_SW", "potato"): "potato",
              ("FI_SW", "carrot"): "carrot", ("FI_SW", "spinach"): "spinach", ("FI_SW", "turnip_rape"): "turnip_rape"}


def exp_short(mu, sd, a):
    """E[max(0, a - X)], X ~ N(mu, sd)."""
    z = (a - mu) / sd
    return (a - mu) * M.Phi(z) + sd * M.phi(z)


def project(models, F, mix, irr_override=None):
    out = []
    for crop, model in models.items():
        mx = mix[mix.crop == crop].copy()
        if irr_override is not None:
            mx["irrigated"] = irr_override(mx)
        for scen in SCEN:
            Fs = F[(F.scenario == scen) & F.year.isin(list(YRS[scen]))].drop(columns="scenario")
            P = mx.merge(Fs, on="cell_id")
            P["pred"] = M.predict(model, P, crop, tech_year=2025)
            ry = M.agg_region_year(P, "pred").rename("index").reset_index()
            ry["crop"], ry["scenario"] = crop, scen
            out.append(ry)
    return pd.concat(out, ignore_index=True)


def costs(Y, sd, vol, price, prem, base_Y=None):
    """Per region-crop-scenario: expected shortfall t/yr, EUR/yr, 1-in-10-year shortfall t.
    The plan level is the 1991-2020 mean index of base_Y (current practice), so irrigation scenarios keep the same plan."""
    base_Y = Y if base_Y is None else base_Y
    rows = []
    for (reg, crop), g in Y.groupby(["region", "crop"]):
        mu0 = base_Y[(base_Y.region == reg) & (base_Y.crop == crop) & (base_Y.scenario == "historical")]["index"].mean()
        s = sd[f"{reg}|{crop}"]
        V = vol[(reg, crop)]; p = price[(reg, crop)]; q = prem[(reg, crop)]
        for scen in SCEN:
            v = g[g.scenario == scen]["index"].values
            es = np.mean([exp_short(x, s, mu0) for x in v]) / mu0          # expected shortfall, share of plan
            # 1-in-10 bad year: 10th percentile of the year-mixture of normals, by bisection
            lo, hi = 0.0, 2.0
            for _ in range(50):
                mid = (lo + hi) / 2
                cdf = np.mean([M.Phi((mid - x) / s) for x in v])
                lo, hi = (mid, hi) if cdf < 0.1 else (lo, mid)
            p10 = max(0.0, 1 - lo / mu0)
            rows.append(dict(region=reg, crop=crop, scenario=scen, plan_t=V, exp_short_t=es * V, eur_yr=es * V * p * q,
                             p10_short_t=p10 * V, p10_eur=p10 * V * p * q, mean_index_rel=float(v.mean() / mu0)))
    return pd.DataFrame(rows)


def main():
    F = M.features(weather_monthly())
    h = M.history()
    hist = h.merge(F[F.scenario == "historical"].drop(columns="scenario"), on=["cell_id", "year"])
    sd = json.load(open(OUT / "c2_sd.json"))

    ca = contract_area(2025)
    mix = ca.groupby(["farm_id", "crop", "region"]).agg(area_ha=("area_ha", "sum"), lat=("lat", "mean"), lon=("lon", "mean")).reset_index()
    last_irr = h.sort_values("year").groupby(["farm_id", "crop"]).irrigated.last()
    mix["irrigated"] = [bool(last_irr.get((f, c), False)) for f, c in zip(mix.farm_id, mix.crop)]
    mix["cell_id"] = nearest_cell(mix.lat, mix.lon, cells())

    # plan yields & volumes (current practice: recent mean yield x contracted area)
    sv = survey_clean(); sv = sv[~sv.dropped & sv.year.between(2022, 2026)]
    fh = foodhills(); fh = fh[~fh.dropped & fh.year.between(2022, 2026)]
    plan_y = {("FI_SW", c): np.average(g.yield_t_ha, weights=g.area_ha) for c, g in sv.groupby("crop")}
    plan_y[("SE_SKANE", "pea")] = fh.delivered_t.sum() / fh.area_ha.sum()
    area = ca.groupby(["region", "crop"]).area_ha.sum().to_dict()
    vol = {k: area[k] * plan_y[k] for k in area}
    pr = prices(); pr26 = pr[pr.year == 2026].set_index("item")
    price = {k: float(pr26.loc[PRICE_ITEM[k], "contract_price_eur_t"]) for k in area}
    prem = {k: float(pr26.loc[PRICE_ITEM[k], "replacement_import_premium_frac"]) for k in area}
    print("Plan (2025 area x 2022-26 mean yield, 2026 price):")
    for k in sorted(area):
        print(f"  {k[0]:9s} {k[1]:12s} area {area[k]:7.0f} ha  plan yield {plan_y[k]:6.2f} t/ha  plan {vol[k]:8.0f} t  "
              f"price {price[k]:6.1f} EUR/t  premium {prem[k]:.2f}  contract value {vol[k] * price[k] / 1e6:5.2f} MEUR")

    # cross-check plan volume against ERP 2025 receipts of contract materials (raw, tonnes converted)
    erp = pd.read_csv(D / "02_raw_feeds/erp_purchase_lines_2021_2025.csv")
    erp = erp[erp.material_id.isin(["M100", "M110", "M111", "M112", "M113", "M114"]) & erp.posting_date.str.startswith("2025")]
    erp["t"] = np.where(erp.uom == "TO", erp.quantity, erp.quantity / 1000.0)
    print("ERP 2025 net receipts, raw (t):", erp.groupby("material_id").t.sum().round(0).to_dict())

    models = {c: M.fit(hist[hist.crop == c].copy(), c, sorted(hist[hist.crop == c].region.unique())) for c in CROPS}
    Y = project(models, F, mix)
    C = costs(Y, sd, vol, price, prem)

    # jackknife intervals over leave-one-year-out refits
    years = sorted(hist.year.unique())
    jk = []
    for yr in years:
        mods = {c: M.fit(hist[(hist.crop == c) & (hist.year != yr)].copy(), c, sorted(hist[hist.crop == c].region.unique())) for c in CROPS}
        Cj = costs(project(mods, F, mix), sd, vol, price, prem); Cj["drop"] = yr
        jk.append(Cj)
    J = pd.concat(jk)
    n = len(years)
    def jk_se(col, reg, crop, scen):
        v = J[(J.region == reg) & (J.crop == crop) & (J.scenario == scen)][col].values
        return sqrt((n - 1) / n * ((v - v.mean()) ** 2).sum())

    # climate-driven extra vs comparator, per row; total with jackknife on the total
    C["extra_eur_vs_today"] = C.eur_yr - C.merge(C[C.scenario == "historical"][["region", "crop", "eur_yr"]], on=["region", "crop"], suffixes=("", "_h")).eur_yr_h.values
    C["eur_yr_se"] = [jk_se("eur_yr", r.region, r.crop, r.scenario) for r in C.itertuples()]
    C["mean_index_rel_se"] = [jk_se("mean_index_rel", r.region, r.crop, r.scenario) for r in C.itertuples()]
    pd.set_option("display.width", 250)
    print("\nEUR risk by region x crop x climate (EUR/yr, 2026 prices):")
    show = C[["region", "crop", "scenario", "plan_t", "mean_index_rel", "mean_index_rel_se", "exp_short_t", "eur_yr", "eur_yr_se", "extra_eur_vs_today", "p10_short_t", "p10_eur"]]
    print(show.round(3).to_string(index=False))
    tot = C.groupby("scenario")[["exp_short_t", "eur_yr", "p10_eur"]].sum()
    Jt = J.groupby(["drop", "scenario"]).eur_yr.sum().unstack()
    tot["eur_yr_se"] = [sqrt((n - 1) / n * ((Jt[s] - Jt[s].mean()) ** 2).sum()) for s in tot.index]
    Jx = Jt.sub(Jt["historical"], axis=0)
    tot["extra_vs_today"] = tot.eur_yr - tot.loc["historical", "eur_yr"]
    tot["extra_se"] = [sqrt((n - 1) / n * ((Jx[s] - Jx[s].mean()) ** 2).sum()) for s in tot.index]
    print("\nTOTAL across crops (EUR/yr):"); print(tot.round(0).to_string())
    for s in ["ssp126", "ssp245", "ssp585"]:
        print(f"TOTAL {s}: expected premium cost {tot.loc[s, 'eur_yr']:.0f} EUR/yr (95% ~ {tot.loc[s, 'eur_yr'] - 1.96 * tot.loc[s, 'eur_yr_se']:.0f}..{tot.loc[s, 'eur_yr'] + 1.96 * tot.loc[s, 'eur_yr_se']:.0f}); "
              f"climate extra vs today {tot.loc[s, 'extra_vs_today']:.0f} (95% ~ {tot.loc[s, 'extra_vs_today'] - 1.96 * tot.loc[s, 'extra_se']:.0f}..{tot.loc[s, 'extra_vs_today'] + 1.96 * tot.loc[s, 'extra_se']:.0f})")
    print(f"TOTAL today's climate (comparator): {tot.loc['historical', 'eur_yr']:.0f} EUR/yr; 1-in-10 year {tot.loc['historical', 'p10_eur']:.0f} (sum of per-crop P10s, conservative)")

    # emissions of replacement imports (gross import EF; net depends on own processing footprint, not in the pack per kg)
    ef = pd.read_csv(D / "01_master/emission_factor_library.csv").set_index("ef_id").kgco2e_per_unit
    ts = pd.read_csv(D / "05_scenarios/transition_scenarios.csv")
    imp_ef = {"pea": ef["EF-FROZ-CAUL-NL"], "potato": ef["EF-FROZ-CAUL-NL"], "carrot": ef["EF-FROZ-CAUL-NL"], "spinach": ef["EF-FROZ-CAUL-NL"],
              "turnip_rape": float(np.mean([ef[f"EF-RAP-{c}"] for c in ["EE", "LV", "LT", "PL", "DK", "SE"]]))}
    dom_ef = {("FI_SW", "pea"): ef["EF-VEG-PEA-FI"], ("SE_SKANE", "pea"): ef["EF-VEG-PEA-SE"], ("FI_SW", "potato"): ef["EF-VEG-POT-FI"],
              ("FI_SW", "carrot"): ef["EF-VEG-CAR-FI"], ("FI_SW", "spinach"): ef["EF-VEG-SPI-FI"], ("FI_SW", "turnip_rape"): ef["EF-RAP-FI"]}
    print("\nReplacement-import emissions (t CO2e/yr, expected) and shadow cost at 2050 carbon price of the SSP's NGFS scenarios:")
    for s in ["historical", "ssp126", "ssp245", "ssp585"]:
        g = C[C.scenario == s]
        gross = sum(r.exp_short_t * imp_ef[r.crop] for r in g.itertuples())
        net_fg = sum(r.exp_short_t * (imp_ef[r.crop] - dom_ef[(r.region, r.crop)]) for r in g.itertuples())
        line = f"  {s:10s} gross {gross:7.0f} t  (minus avoided domestic farm-gate: {net_fg:7.0f} t)"
        if s != "historical":
            cp = ts[(ts.physical_pathway_proxy == s) & (ts.year == 2050)][["scenario", "carbon_price_eur_t"]]
            line += "  shadow EUR at 2050 price: " + ", ".join(f"{r.scenario} {r.carbon_price_eur_t:.0f}/t -> {gross * r.carbon_price_eur_t:,.0f}" for r in cp.itertuples())
        print(line)

    # ---------------- adaptation 1: irrigation, at the share actually observed ----------------
    print("\nIrrigation coefficients (per sd of feature):")
    for c in ["potato", "carrot", "spinach", "pea"]:
        m = models[c]
        print(f"  {c}: " + ", ".join(f"{n} {b:+.4f}" for n, b in zip(m["names"], m["beta"]) if n.startswith(("irr", "wb"))))
    obs = pd.concat([survey_clean().query("~dropped").assign(region="FI_SW")[["region", "crop", "year", "area_ha", "irrigated"]],
                     foodhills().assign(region="SE_SKANE")[["region", "crop", "year", "area_ha", "irrigated"]]])
    share = obs.groupby(["region", "crop", "year"]).apply(lambda g: g.area_ha[g.irrigated].sum() / g.area_ha.sum(), include_groups=False)
    smax = share.groupby(level=[0, 1]).max(); scur = mix.groupby(["region", "crop"]).apply(lambda g: g.area_ha[g.irrigated].sum() / g.area_ha.sum(), include_groups=False)
    print("irrigated area share: current (2025 mix) vs max observed in any year:")
    for k in smax.index:
        print(f"  {k}: current {scur.get(k, 0):.3f}  max observed {smax[k]:.3f}")
    # raise share to max observed by switching the largest non-irrigated farms (deterministic)
    def irr_to_max(mx):
        irr = mx.irrigated.copy()
        for (reg, crop), g in mx.groupby(["region", "crop"]):
            target = smax.get((reg, crop), 0.0) * g.area_ha.sum()
            have = g.area_ha[g.irrigated].sum()
            for idx in g[~g.irrigated].sort_values("area_ha", ascending=False).index:
                if have >= target:
                    break
                irr[idx] = True; have += g.area_ha[idx]
        return irr
    Yi = project(models, F, mix, irr_override=irr_to_max)
    Ci = costs(Yi, sd, vol, price, prem, base_Y=Y)
    ji = []
    for yr in years:
        mods = {c: M.fit(hist[(hist.crop == c) & (hist.year != yr)].copy(), c, sorted(hist[hist.crop == c].region.unique())) for c in CROPS}
        Yb = project(mods, F, mix)
        a = costs(Yb, sd, vol, price, prem); b = costs(project(mods, F, mix, irr_override=irr_to_max), sd, vol, price, prem, base_Y=Yb)
        ji.append(a.set_index(["region", "crop", "scenario"]).eur_yr - b.set_index(["region", "crop", "scenario"]).eur_yr)
    JI = pd.concat(ji, axis=1)
    gain = C.set_index(["region", "crop", "scenario"]).eur_yr - Ci.set_index(["region", "crop", "scenario"]).eur_yr
    added_ha = (mix.assign(new=irr_to_max(mix)).query("new and not irrigated").groupby(["region", "crop"]).area_ha.sum())
    print("\nIrrigation to max observed share: avoided premium cost EUR/yr (jackknife se), added irrigated ha:")
    for k, v in gain.items():
        if abs(v) < 1 or k[:2] not in added_ha.index:
            continue
        se = sqrt((n - 1) / n * ((JI.loc[k] - JI.loc[k].mean()) ** 2).sum())
        print(f"  {k[0]:9s} {k[1]:8s} {k[2]:10s} avoided {v:9.0f} EUR/yr (se {se:7.0f})  over {added_ha[k[:2]]:6.0f} added ha -> {v / added_ha[k[:2]]:6.1f} EUR/ha/yr")
    lev = pd.read_csv(D / "05_scenarios/decarbonisation_levers.csv").set_index("lever_id")
    print(f"  comparator lever L24 (irrigation scheduling & drip, carrots/potatoes): opex {lev.loc['L24', 'opex_delta_eur_per_yr']:.0f} EUR/yr")

    # ---------------- adaptation 2: FI+SE pea pooling (wider sourcing area) ----------------
    B = pd.read_csv(OUT / "c2_backtest.csv"); B = B[B.crop == "pea"]
    B["res"] = B.obs_index - B.pred_index
    w = B.pivot(index="year", columns="region", values="res").dropna()
    o = B.pivot(index="year", columns="region", values="obs_index").dropna()
    rho = float(w.corr().iloc[0, 1]); rho_obs = float(o.corr().iloc[0, 1]); k = len(w)
    zf = np.arctanh(rho); lo, hi = np.tanh(zf - 1.96 / sqrt(k - 3)), np.tanh(zf + 1.96 / sqrt(k - 3))
    print(f"\nFI-SE pea: observed yield-index correlation {rho_obs:+.3f}; model-residual correlation {rho:+.3f} (95% {lo:+.2f}..{hi:+.2f}, n={k} years {w.index.min()}-{w.index.max()})")
    shared_bad = int(((o["FI_SW"] < 0.9) & (o["SE_SKANE"] < 0.9)).sum()); any_bad = int(((o["FI_SW"] < 0.9) | (o["SE_SKANE"] < 0.9)).sum())
    print(f"FI-SE pea: years either region <90 % of its mean: {any_bad}; both at once: {shared_bad} of {k}")
    # Pooled shortfall: a deficit in one region is covered by the other's surplus, capped by the max volume that
    # region ever delivered (processing capacity actually used). Gauss-Hermite quadrature, 40x40 nodes (deterministic).
    gh_x, gh_w = np.polynomial.hermite_e.hermegauss(40); gh_w = gh_w / gh_w.sum()
    fi_hist = survey_clean().query("~dropped and crop=='pea'")
    cap = {"FI_SW": None, "SE_SKANE": float(foodhills().groupby("year").delivered_t.sum().max())}
    print(f"SE max delivered pea volume in any year 2018-2026: {cap['SE_SKANE']:.0f} t vs plan {vol[('SE_SKANE', 'pea')]:.0f} t; "
          f"FI survey covers only respondents, so FI surplus cap = plan x (max/mean of FI pea yield index 2012-2026) "
          f"= {float(o['FI_SW'].max()) if 'FI_SW' in o else float('nan'):.3f} on overlap years")
    fi_idx_max = float(B[B.region == "FI_SW"].obs_index.max())
    cap["FI_SW"] = vol[("FI_SW", "pea")] * fi_idx_max
    for rr in [rho, max(rho, hi)]:
        for s in ["historical", "ssp126", "ssp245", "ssp585"]:
            res = {}
            for reg in ["FI_SW", "SE_SKANE"]:
                mu0 = Y[(Y.region == reg) & (Y.crop == "pea") & (Y.scenario == "historical")]["index"].mean()
                res[reg] = (Y[(Y.region == reg) & (Y.crop == "pea") & (Y.scenario == s)].sort_values("year")["index"].values / mu0, sd[f"{reg}|pea"] / mu0)
            sep, pool = 0.0, 0.0
            Vf, Vs = vol[("FI_SW", "pea")], vol[("SE_SKANE", "pea")]
            pf, ps = price[("FI_SW", "pea")] * prem[("FI_SW", "pea")], price[("SE_SKANE", "pea")] * prem[("SE_SKANE", "pea")]
            for t in range(len(res["FI_SW"][0])):
                mf, sf = res["FI_SW"][0][t], res["FI_SW"][1]; ms, ss = res["SE_SKANE"][0][t], res["SE_SKANE"][1]
                for i in range(40):
                    for j in range(40):
                        z1 = gh_x[i]; z2 = rr * gh_x[i] + sqrt(1 - rr * rr) * gh_x[j]
                        qf = Vf * (mf + sf * z1); qs = Vs * (ms + ss * z2)
                        qf, qs = min(max(qf, 0), cap["FI_SW"]), min(max(qs, 0), cap["SE_SKANE"])
                        df_, ds_ = Vf - qf, Vs - qs
                        wgt = gh_w[i] * gh_w[j]
                        sep += wgt * (max(df_, 0) * pf + max(ds_, 0) * ps)
                        # pooled: surplus of one covers deficit of the other
                        if df_ > 0 and ds_ < 0:
                            cover = min(df_, -ds_); pool += wgt * ((df_ - cover) * pf)
                        elif ds_ > 0 and df_ < 0:
                            cover = min(ds_, -df_); pool += wgt * ((ds_ - cover) * ps)
                        else:
                            pool += wgt * (max(df_, 0) * pf + max(ds_, 0) * ps)
            T = len(res["FI_SW"][0])
            print(f"  rho={rr:+.2f} {s:10s}: separate {sep / T:9.0f} EUR/yr  pooled {pool / T:9.0f} EUR/yr  -> hedge value {(sep - pool) / T:9.0f} EUR/yr ({100 * (sep - pool) / sep:4.1f} %)")
    C.to_csv(OUT / "c3_eur_risk.csv", index=False)
    json.dump({"plan_t": {f"{a}|{b}": v for (a, b), v in vol.items()}, "total": tot.round(1).reset_index().to_dict("records")},
              open(OUT / "c3_summary.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
