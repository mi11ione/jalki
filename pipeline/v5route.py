"""v5 route: the v4 route model (v4model.gaps, unchanged) re-run with L07 out of the recommended route.

Why: L01 left the route because the pack does not show the biogas it needs. L07 (Bjuv gas to biogas) rests on the same
missing evidence: the pack's lever catalogue sizes it on a "full-year volume ~7,300 MWh" of Swedish biogas
(05_scenarios/decarbonisation_levers.csv), and Bjuv's 2025 meters show natural gas only. Same rule, same outcome (L7).
Cost split: the v4 split (model-b2 metrics, same lever set, checked in v4) minus L07's own catalogue line:
capex 80,000 x CRF(8 %, 10 y) + opex 140,000, which equals L07's cost in the bundle to the cent.
Everything else is v4model.compute's arithmetic, unchanged, on the reduced set. Synthetic pack only.
"""
import csv, json
from pathlib import Path

import v4model
from v4model import gaps, rng

OUT_V5 = {'L07': 'the pack sizes it on ~7,300 MWh a year of Swedish biogas; Bjuv\'s 2025 meters show natural gas only'}


def crf(r, n):
    return r / (1 - (1 + r) ** -n)


def compute(D, ROOT):
    RT, P, V4 = D['route'], D['promise'], D['v4']
    lv = {L['id']: L for L in D['rlev']}
    ids = [L['id'] for L in D['rlev']]
    cap_out = dict(v4model.CAPACITY_OUT, **OUT_V5)
    rec = [i for i in V4['rec_before'] if i not in cap_out]
    sav = [i for i in V4['sav_before'] if i not in cap_out]
    assert sorted(set(RT['rec']) - set(rec)) == ['L07'] and sav == RT['sav'], (RT['rec'], rec)
    cat = {r['lever_id']: r for r in csv.DictReader(open(Path(ROOT) / 'twin/data/data/05_scenarios/decarbonisation_levers.csv', encoding='utf-8'))}
    c7 = cat['L07']
    cap7 = float(c7['capex_eur']) * crf(0.08, int(c7['lifetime_yr']))
    op7 = float(c7['opex_delta_eur_per_yr'])
    assert abs(cap7 + op7 - lv['L07']['cost']) < 0.01, (cap7 + op7, lv['L07']['cost'])
    assert '7,300 MWh' in c7['trade_offs'], c7
    RT['rec'], RT['sav'] = rec, sav
    cost = sum(lv[i]['cost'] for i in rec)
    capex = sum(lv[i]['capex'] for i in rec)
    assert abs(V4['rec_eur'] - lv['L07']['cost'] - cost) < 0.01 and abs(V4['rec_capex'] - lv['L07']['capex'] - capex) < 0.01
    out = dict(V4)
    out.update(script='python3 stages/pj-v5/build.py (v5route.py on v4model.gaps)', capacity_out=cap_out, rec_eur=cost, rec_capex=capex,
               rec_annual_capital=V4['rec_annual_capital'] - cap7, rec_cash_opex=V4['rec_cash_opex'] - op7,
               l07_out={'capital_eur_yr': cap7, 'opex_eur_yr': op7, 'cost_eur_yr': cap7 + op7, 'capex_eur': lv['L07']['capex'],
                        'catalogue_trade_off': c7['trade_offs']},
               v4_rec_eur=V4['rec_eur'], v4_rec_capex=V4['rec_capex'])
    P['rec_eur'], P['rec_capex'] = cost, capex
    for y in (2032, 2035):
        j = y - 2025
        cuts = [100 * gaps(D, rec, y, s)[0]['flag'] / (RT['seed'] * RT['v'][s][j]) for s in RT['main']]
        assert abs(min(cuts) - V4['cutphys%d_lo' % y]) < 1e-9 and abs(max(cuts) - V4['cutphys%d_hi' % y]) < 1e-9  # L07 is not FLAG
        for k in ('s12', 's3nf', 'flag'):
            out['route%d_%s_lo' % (y, k)], out['route%d_%s_hi' % (y, k)] = rng(D, rec, y, k)
            out['pause%d_%s_lo' % (y, k)], out['pause%d_%s_hi' % (y, k)] = rng(D, [i for i in rec if i != 'L20'], y, k)
        assert abs(out['route%d_flag_lo' % y] - V4['route%d_flag_lo' % y]) < 1e-9 and abs(out['route%d_flag_hi' % y] - V4['route%d_flag_hi' % y]) < 1e-9
        out['routelow%d_flag_hi' % y] = rng(D, rec, y, 'flag', 'low')[1]
        d = [gaps(D, [i for i in rec if i != 'L20'], y, s)[0]['s3nf'] - gaps(D, rec, y, s)[0]['s3nf'] for s in RT['main']]
        out['pausedelta%d_lo' % y], out['pausedelta%d_hi' % y] = min(d), max(d)
        out['worst%d_flag_lo' % y] = rng(D, ids, y, 'flag', 'high')[0]
        assert out['worst%d_flag_lo' % y] > 0
    out['hvo_share_pct'] = 100 * lv['L20']['cost'] / cost
    g35, _ = gaps(D, rec, 2035, 'current_policies')
    out['route2035_cp'] = g35
    out['pause_s3nf_delta_2035_cp'] = gaps(D, [i for i in rec if i != 'L20'], 2035, 'current_policies')[0]['s3nf'] - g35['s3nf']
    # rapeseed plan: only the ratios to the route cost move; the premium is reported over both scenarios (review R7)
    R = json.loads(json.dumps(V4['rape']))
    for Y in ('2032', '2035'):
        r = R[Y]
        for s in ('current_policies', 'net_zero_2050'):
            r[s]['x_route'] = [r[s]['eur_central'][0] / cost, r[s]['eur_central'][1] / cost]
        r['x_lo'] = min(r['current_policies']['x_route'][0], r['net_zero_2050']['x_route'][0])
        r['x_hi'] = max(r['current_policies']['x_route'][1], r['net_zero_2050']['x_route'][1])
        r['pilot']['cap_pct_route'] = 100 * r['pilot']['cap_eur'] / cost
        r['prem_lo'] = min(r['current_policies']['premium_pct_paid'][0], r['net_zero_2050']['premium_pct_paid'][0])
        r['prem_hi'] = max(r['current_policies']['premium_pct_paid'][1], r['net_zero_2050']['premium_pct_paid'][1])
    R['source'] = 'method of the rapeseed plan (plan.md), re-run by python3 stages/pj-v5/build.py on the route gap shown'
    out['rape'] = R
    return out
