"""Jälki v8 data layer, called by build.py after v7model.apply.

The phosphorus contract clause for lake catchments: runs v8clause.py (recomputed from the pack; cross-checked against
the Pelto build that first proposed it) and registers its figures as v3.n8_* keys. Synthetic pack only.
"""
import json, runpy
from pathlib import Path

from v5model import num

S8 = 'python3 stages/pj-v8/v8clause.py → clause8.json'


def apply(D, ROOT, HERE):
    L = []
    HERE = Path(HERE)
    runpy.run_path(str(HERE / 'v8clause.py'), run_name='v8build')
    X = json.loads((HERE / 'clause8.json').read_text())
    n6 = D['v3']['numbers']
    # the clause line and the nature card share one denominator: contract phosphorus to water
    assert abs(X['p_total_kg'] - n6['n6_p_kg']['v']) < 0.05, (X['p_total_kg'], n6['n6_p_kg']['v'])
    assert X['ca12_parcels'] > 0, 'copy: CA12 is in the clause'

    def n8(k, v, unit, dp, en, fi, key, label='derivation'):
        num(D, 'n8_' + k, v, unit, dp, en, fi, S8 + '#' + key, label)
    n8('cl_dmax', X['dmax_m'], 'n', 0, 'Clause reach: parcels within this many metres of water', 'Lausekkeen ulottuvuus: lohkot tämän metrimäärän päässä vedestä', 'dmax_m', 'assumption')
    n8('cl_parcels', X['parcels'], 'n', 0, 'Contract parcels the clause covers: no buffer strip, near water, catchment below good status', 'Lausekkeen piiriin tulevat sopimuslohkot: ei suojakaistaa, lähellä vettä, valuma-alue hyvää huonommassa tilassa', 'parcels', 'data')
    n8('cl_farms', X['farms'], 'n', 0, 'Contract farms the clause covers', 'Lausekkeen piiriin tulevat sopimustilat', 'farms', 'data')
    n8('cl_kg', X['kg'], 'n', 0, 'Phosphorus to water avoided a year by the clause, kg (model A buffer-strip effect)', 'Lausekkeella vältetty fosfori vesiin vuodessa, kg (mallin A suojakaistavaikutus)', 'kg')
    n8('cl_pct', X['pct'], 'pct', 1, 'Clause saving as a share of contract phosphorus to water', 'Lausekkeen säästö osuutena sopimuspeltojen vesiin päätyvästä fosforista', 'pct')
    n8('cl_half_kg', X['half_effect_kg'], 'n', 0, 'Pessimistic re-run: half the model\'s buffer-strip effect, kg a year', 'Varovainen uusinta: puolet mallin suojakaistavaikutuksesta, kg vuodessa', 'half_effect_kg')
    n8('cl_ca12_parcels', X['ca12_parcels'], 'n', 0, 'Of them, parcels in CA12', 'Niistä lohkot CA12:lla', 'ca12_parcels', 'data')
    D['v8'] = {'clause': X, 'synthetic_only': True}
    L.append('phosphorus clause: %d parcels on %d farms, %.1f kg P a year = %.1f%% of %.1f kg; CA12 %d parcels; half effect %.1f kg; %s' % (
        X['parcels'], X['farms'], X['kg'], X['pct'], X['p_total_kg'], X['ca12_parcels'], X['half_effect_kg'], X.get('cross_check', '')))
    return L
