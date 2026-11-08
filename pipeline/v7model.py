"""Jälki v7 data layer, called by build.py after v6model.apply.

The board's rapeseed decision, measured: runs v7rape.py (yield and nitrogen per tonne on each Finnish contract
turnip-rape farm, from the farmers' own 2025 field records) and registers its figures as v3.n7_* keys whose drawers
name the script and open the turnip-rape inventory line. Synthetic pack only.
"""
import json, runpy
from pathlib import Path

from v5model import num

S7 = 'python3 stages/pj-v8/v7rape.py → rape7.json'


def apply(D, ROOT, HERE):
    L = []
    HERE = Path(HERE)
    runpy.run_path(str(HERE / 'v7rape.py'), run_name='v7build')
    X = json.loads((HERE / 'rape7.json').read_text())
    b, t, r = X['bottom'], X['top'], X['robust']
    # facts the copy states in words (v7rape.py asserts the ratios; these pin the comparisons the sentences make)
    assert t['y'] > b['y'] and b['n_t'] > t['n_t'] and b['flag_t_min'] > t['flag_t_min'], 'copy: higher yield, less N and FLAG per tonne'
    assert abs(b['n_ha'] - t['n_ha']) / t['n_ha'] < 0.15, 'copy: about the same nitrogen per hectare'

    def n7(k, v, unit, dp, en, fi, key, label='derivation'):
        num(D, 'n7_' + k, v, unit, dp, en, fi, S7 + '#' + key, label)
    n7('farms', X['farms'], 'n', 0, 'Finnish contract turnip-rape farms, 2025', 'Suomalaiset rypsin sopimustilat 2025', 'farms', 'data')
    n7('resp', X['respondents'], 'n', 0, 'Of them, farms that sent a 2025 field record (yield, nitrogen)', 'Niistä tilat, jotka lähettivät vuoden 2025 peltotiedot (sato, typpi)', 'respondents', 'data')
    n7('resp_pct', X['resp_pct'], 'pct', 0, 'Share of contract turnip-rape farms with a 2025 field record', 'Osuus rypsin sopimustiloista, joilla on vuoden 2025 peltotiedot', 'resp_pct', 'data')
    n7('q_n', b['n'], 'n', 0, 'Farms in each yield quarter (responding farms)', 'Tiloja kussakin satoneljänneksessä (vastanneet tilat)', 'bottom.n')
    n7('y_bot', b['y'], 'tha', 2, 'Yield, lowest-yield quarter of farms (median)', 'Sato, heikoimman satoneljänneksen tilat (mediaani)', 'bottom.y')
    n7('y_top', t['y'], 'tha', 2, 'Yield, highest-yield quarter of farms (median)', 'Sato, parhaan satoneljänneksen tilat (mediaani)', 'top.y')
    n7('nha_bot', b['n_ha'], 'kgnha', 0, 'Nitrogen per hectare, lowest-yield quarter (median)', 'Typpi hehtaarille, heikoin satoneljännes (mediaani)', 'bottom.n_ha')
    n7('nha_top', t['n_ha'], 'kgnha', 0, 'Nitrogen per hectare, highest-yield quarter (median)', 'Typpi hehtaarille, paras satoneljännes (mediaani)', 'top.n_ha')
    n7('nt_bot', b['n_t'], 'kgnt', 0, 'Nitrogen per tonne harvested, lowest-yield quarter (median)', 'Typpi korjattua tonnia kohden, heikoin satoneljännes (mediaani)', 'bottom.n_t')
    n7('nt_top', t['n_t'], 'kgnt', 0, 'Nitrogen per tonne harvested, highest-yield quarter (median)', 'Typpi korjattua tonnia kohden, paras satoneljännes (mediaani)', 'top.n_t')
    n7('fl_bot', b['flag_t_min'], 'tco2t', 2, 'Farm FLAG CO₂e per tonne harvested, lowest-yield quarter, mineral-soil farms (median)', 'Tilan FLAG-CO₂e korjattua tonnia kohden, heikoin satoneljännes, kivennäismaan tilat (mediaani)', 'bottom.flag_t_min')
    n7('fl_top', t['flag_t_min'], 'tco2t', 2, 'Farm FLAG CO₂e per tonne harvested, highest-yield quarter, mineral-soil farms (median)', 'Tilan FLAG-CO₂e korjattua tonnia kohden, paras satoneljännes, kivennäismaan tilat (mediaani)', 'top.flag_t_min')
    n7('nt_ratio', X['n_t_ratio'], 'x', 2, 'Nitrogen per tonne: lowest-yield quarter ÷ highest', 'Typpi tonnia kohden: heikoin satoneljännes ÷ paras', 'n_t_ratio')
    n7('fl_ratio', X['flag_t_ratio'], 'x', 2, 'FLAG per tonne on mineral soil: lowest-yield quarter ÷ highest', 'FLAG tonnia kohden kivennäismaalla: heikoin satoneljännes ÷ paras', 'flag_t_ratio')
    n7('rob_nt', r['n_t_ratio_thirds'], 'x', 2, 'Pessimistic re-run (thirds, mineral-soil farms only): nitrogen per tonne, lowest ÷ highest', 'Varovainen uusinta (kolmannekset, vain kivennäismaa): typpi tonnia kohden, heikoin ÷ paras', 'robust.n_t_ratio_thirds')
    n7('rob_fl', r['flag_t_ratio_thirds'], 'x', 2, 'Pessimistic re-run (thirds, mineral-soil farms only): FLAG per tonne, lowest ÷ highest', 'Varovainen uusinta (kolmannekset, vain kivennäismaa): FLAG tonnia kohden, heikoin ÷ paras', 'robust.flag_t_ratio_thirds')
    D['v7'] = {'rape': X, 'synthetic_only': True}
    L.append('rapeseed measured: %d farms, %d with field records; yield %.2f vs %.2f t/ha; N %.0f vs %.0f kg/t (x%.2f); FLAG on mineral %.2f vs %.2f t/t (x%.2f); thirds x%.2f / x%.2f' % (
        X['farms'], X['respondents'], b['y'], t['y'], b['n_t'], t['n_t'], X['n_t_ratio'], b['flag_t_min'], t['flag_t_min'], X['flag_t_ratio'], r['n_t_ratio_thirds'], r['flag_t_ratio_thirds']))
    return L
