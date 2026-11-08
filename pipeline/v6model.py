"""Jälki v6 data layer, called by build.py after v5model.apply.

1. Ask the frameworks: runs v6ask.py (answer bank + citation check) and ships the bank as D.v6.ask.
2. Nature: runs v6nature.py (phosphorus to water per tonne harvested, by farm and catchment) and registers its figures.
Every figure is a registry key v3.n6_* whose drawer names the script. Synthetic pack only.
"""
import json, runpy
from pathlib import Path

from v5model import num

S6N = 'python3 stages/pj-v8/v6nature.py → nature6.json'
S6A = 'python3 stages/pj-v8/v6ask.py → ask6.json'


def apply(D, ROOT, HERE):
    L = []
    HERE = Path(HERE)
    runpy.run_path(str(HERE / 'v6ask.py'), run_name='__main__')
    A = json.loads((HERE / 'ask6.json').read_text())
    runpy.run_path(str(HERE / 'v6nature.py'), run_name='v6build')
    N6 = json.loads((HERE / 'nature6.json').read_text())

    # facts the copy states in words: the build fails if the data stops saying them
    assert N6['overlap_top_t_top_p'] == 0, 'copy says the two top-10 lists share no farm'
    assert N6['top3_idx_in_top3_t'] == 0, 'copy says none of the three highest-index catchments is among the three highest-emission ones'
    ca = N6['ca12']
    assert ca['status'] == 'poor' and ca['water'] == 'river', 'copy says CA12 is a river in poor status'
    assert max(r['p_kg'] for r in N6['catchments']) == ca['p_kg'], 'copy says CA12 sends the most contract phosphorus'
    assert N6['parcels_without_p'] == 0 and abs(N6['farm_t'] - N6['line_t']) < 0.5

    def n6(k, v, unit, dp, en, fi, key):
        num(D, 'n6_' + k, v, unit, dp, en, fi, S6N + '#' + key)
    n6('top_n', N6['top_n'], 'n', 0, 'Farms compared in each list', 'Verrattavat tilat kummassakin listassa', 'top_n')
    n6('top_t_t_pct', N6['top_t_t_pct'], 'pct', 1, 'Share of contract-farm CO₂e on the 10 highest-emitting farms', 'Sopimustilojen CO₂e-osuus 10 suurimmalla päästäjällä', 'top_t_t_pct')
    n6('top_t_p_pct', N6['top_t_p_pct'], 'pct', 1, 'Share of contract phosphorus to water from the 10 highest-emitting farms (model A)', 'Sopimuspeltojen vesiin päätyvän fosforin osuus 10 suurimmalta päästäjältä (malli A)', 'top_t_p_pct')
    n6('top_p_p_pct', N6['top_p_p_pct'], 'pct', 1, 'Share of contract phosphorus to water from the 10 highest-phosphorus farms', 'Fosforiosuus 10 eniten fosforia päästävältä tilalta', 'top_p_p_pct')
    n6('top_p_t_pct', N6['top_p_t_pct'], 'pct', 1, 'Share of contract-farm CO₂e on the 10 highest-phosphorus farms', 'CO₂e-osuus 10 eniten fosforia päästävällä tilalla', 'top_p_t_pct')
    n6('overlap', N6['overlap_top_t_top_p'], 'n', 0, 'Farms on both top-10 lists (emissions, phosphorus)', 'Tilat molemmilla top 10 -listoilla (päästöt, fosfori)', 'overlap_top_t_top_p')
    n6('overlap20', N6['robust']['overlap_top20'], 'n', 0, 'Farms on both top-20 lists', 'Tilat molemmilla top 20 -listoilla', 'robust.overlap_top20')
    n6('half_t', N6['robust']['half_t_farms'], 'n', 0, 'Fewest farms holding half of contract-farm CO₂e', 'Pienin tilamäärä, jolla on puolet sopimustilojen CO₂e:stä', 'robust.half_t_farms')
    n6('half_p', N6['robust']['half_p_farms'], 'n', 0, 'Fewest farms delivering half of contract phosphorus to water', 'Pienin tilamäärä, joka päästää puolet sopimusfosforista vesiin', 'robust.half_p_farms')
    n6('half_overlap', N6['robust']['half_overlap'], 'n', 0, 'Farms in both half-sets', 'Tilat kummassakin puolikasjoukossa', 'robust.half_overlap')
    n6('farms', N6['farms'], 'n', 0, 'Finnish contract farms with 2025 parcels', 'Suomalaiset sopimustilat, joilla lohkoja 2025', 'farms')
    n6('p_kg', N6['p_kg'], 'n', 0, 'Contract phosphorus to water 2025, kg (model A)', 'Sopimuspeltojen fosfori vesiin 2025, kg (malli A)', 'p_kg')
    n6('idx_lo', N6['idx_spread'][0], 'x', 2, 'Lowest catchment index: phosphorus per tonne against the same crops', 'Pienin valuma-alueindeksi: fosfori tonnia kohden samoihin kasveihin nähden', 'idx_spread[0]')
    n6('idx_hi', N6['idx_spread'][1], 'x', 2, 'Highest catchment index: phosphorus per tonne against the same crops', 'Suurin valuma-alueindeksi: fosfori tonnia kohden samoihin kasveihin nähden', 'idx_spread[1]')
    n6('n_catch', N6['n_catch'], 'n', 0, 'Catchments ranked (at least 3 delivering farms)', 'Järjestetyt valuma-alueet (vähintään 3 toimittavaa tilaa)', 'n_catch')
    n6('min_farms', N6['min_farms'], 'n', 0, 'Minimum delivering farms for a catchment to be ranked', 'Järjestettävän valuma-alueen toimittavien tilojen vähimmäismäärä', 'min_farms')
    n6('ca12_p', ca['p_kg'], 'n', 0, 'CA12: contract phosphorus to water 2025, kg (model A)', 'CA12: sopimuspeltojen fosfori vesiin 2025, kg (malli A)', 'ca12.p_kg')
    n6('ca12_idx', ca['idx'], 'x', 2, 'CA12: phosphorus per tonne against the same crops', 'CA12: fosfori tonnia kohden samoihin kasveihin nähden', 'ca12.idx')
    n6('ca12_rank_idx', ca['rank_idx'], 'n', 0, 'CA12: rank on phosphorus per tonne', 'CA12: sija fosforissa tonnia kohden', 'ca12.rank_idx')
    for r in N6['catchments']:
        n6('c_' + r['id'], r['idx'], 'x', 2, '%s: phosphorus to water per tonne harvested against the same crops (1.0 = typical); %s kg P, %s t harvested, %d farms, %s %s' % (r['id'], r['p_kg'], r['tons'], r['farms'], r['status'], r['water']),
           '%s: vesiin päätyvä fosfori korjattua tonnia kohden samoihin kasveihin nähden (1,0 = tyypillinen); %s kg P, %s t, %d tilaa' % (r['id'], r['p_kg'], r['tons'], r['farms']), 'catchments[%s].idx' % r['id'])
    num(D, 'n6_ask_n', A['n'], 'n', 0, 'Framework answers in the bank', 'Viitekehysvastauksia pankissa', S6A + '#n')
    num(D, 'n6_ask_quotes', A['n_quotes'], 'n', 0, 'Quoted passages, each found word for word in its file', 'Lainatut kohdat, kukin löydetty sanasta sanaan tiedostostaan', S6A + '#n_quotes')
    D['v6'] = {'ask': A['bank'], 'ask_check': A['check'],
               'catch': [{k: r[k] for k in ('id', 'idx', 'status', 'water', 'p_kg', 'tons', 'farms', 'rank_t')} for r in N6['catchments']],
               'synthetic_only': True}
    L.append('ask: %d answers, %d quotes verified (%s)' % (A['n'], A['n_quotes'], S6A))
    L.append('nature: %d farms, %d catchments ranked; top-10 emitters send %.1f%% of P (%.1f%% of CO2e); overlap %d; CA12 %s kg P, index %.2f, rank %d' % (
        N6['farms'], N6['n_catch'], N6['top_t_p_pct'], N6['top_t_t_pct'], N6['overlap_top_t_top_p'], ca['p_kg'], ca['idx'], ca['rank_idx']))
    return L
