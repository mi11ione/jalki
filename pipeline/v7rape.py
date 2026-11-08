"""Jälki v7: the rapeseed plan's own measurement, computed from today's field records.

The board decided to grow rapeseed with contract farmers, on the belief that helping them raise yield is better for them,
for Apetit and for the climate. The measurement that proves it pays is yield and nitrogen per tonne on each contract farm.
This script computes what that measurement already shows on the pack's 2025 records.

Inputs (synthetic pack only):
  stages/pj-data/trail/l/108.json   a-final 2025 contract-farm line for Finnish turnip rape: one party per farm, with parcel
                                  hectares, mapped peat share, farm CO2e and FLAG CO2e, and the survey row it used
  twin/data/data/03_farming/farm_survey_fi.csv   the farmer's own field record: yield t/ha, mineral and manure N kg/ha
Metric per responding farm: yield (t/ha), nitrogen per tonne harvested (kg N / t = (mineral N + manure N) / yield),
FLAG per tonne harvested (t CO2e / t = farm FLAG / (yield x parcel ha)).
Farms are split into yield quarters among respondents; "mineral" = no mapped peat on the farm's turnip-rape parcels.
Run: python3 stages/pj-v8/v7rape.py      Writes stages/pj-v8/rape7.json. Stdlib only.
"""
import csv, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parents[1]
DATA = R / 'twin/data/data'


def med(v):
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


idx = json.load(open(R / 'stages/pj-data/trail/index.json'))
line = [l for l in idx['lines'] if l['item'] == 'contract_farming:FI_SW:turnip_rape']
assert len(line) == 1, line
s = json.load(open(R / 'stages/pj-data/trail' / line[0]['shard']))
sv = {r['survey_id']: r for r in csv.DictReader(open(DATA / '03_farming/farm_survey_fi.csv', newline='', encoding='utf-8-sig'))}

parties = s['parties']
n_all = len(parties)
t_line = sum(v['t'] for v in parties.values())
assert abs(t_line - line[0]['t']) < 0.5, (t_line, line[0]['t'])
rows = []
for k, v in parties.items():
    if v.get('fill') != 'survey' or not v.get('survey_id'):
        continue
    q = sv[v['survey_id']]
    assert q['crop'] == 'turnip_rape' and q['year'] == '2025', q
    y = float(q['yield_t_ha'])
    n_ha = float(q['n_mineral_kg_ha']) + float(q['n_manure_kg_ha'])
    if y <= 0 or v['ha'] <= 0:
        continue
    rows.append(dict(farm=k.split(':')[1], y=y, n_ha=n_ha, n_t=n_ha / y, flag_t=v['t_flag'] / (y * v['ha']), ha=v['ha'],
                     peat=v.get('map_share', 0.0) > 0, flag=v['t_flag'], harvest=y * v['ha']))
n_resp = len(rows)
rows.sort(key=lambda r: r['y'])
q = n_resp // 4
bot, top = rows[:q], rows[-q:]
mid = rows[q:-q]


def summ(rs):
    m = [r for r in rs if not r['peat']]
    return dict(n=len(rs), y=round(med([r['y'] for r in rs]), 2), n_ha=round(med([r['n_ha'] for r in rs]), 1), n_t=round(med([r['n_t'] for r in rs]), 1),
                n_min=len(m), flag_t_min=round(med([r['flag_t'] for r in m]), 3) if m else None)


B, T, M = summ(bot), summ(top), summ(mid)
allm = [r for r in rows if not r['peat']]
# pessimistic re-run: thirds instead of quarters, and mineral farms only
rm = sorted(allm, key=lambda r: r['y'])
t3 = len(rm) // 3
rob = dict(min_bot_third_n_t=round(med([r['n_t'] for r in rm[:t3]]), 1), min_top_third_n_t=round(med([r['n_t'] for r in rm[-t3:]]), 1),
           min_bot_third_flag_t=round(med([r['flag_t'] for r in rm[:t3]]), 3), min_top_third_flag_t=round(med([r['flag_t'] for r in rm[-t3:]]), 3))
rob['n_t_ratio_thirds'] = round(rob['min_bot_third_n_t'] / rob['min_top_third_n_t'], 2)
rob['flag_t_ratio_thirds'] = round(rob['min_bot_third_flag_t'] / rob['min_top_third_flag_t'], 2)
out = dict(
    synthetic_only=True, script='python3 stages/pj-v8/v7rape.py',
    inputs=['stages/pj-data/trail/l/108.json', 'twin/data/data/03_farming/farm_survey_fi.csv'],
    farms=n_all, respondents=n_resp, resp_pct=round(100.0 * n_resp / n_all, 1),
    n_mineral=len(allm),
    y_med=round(med([r['y'] for r in rows]), 2), n_ha_med=round(med([r['n_ha'] for r in rows]), 1), n_t_med=round(med([r['n_t'] for r in rows]), 1),
    bottom=B, top=T, middle=M,
    y_ratio=round(T['y'] / B['y'], 2), n_ha_ratio=round(B['n_ha'] / T['n_ha'], 2), n_t_ratio=round(B['n_t'] / T['n_t'], 2),
    flag_t_ratio=round(B['flag_t_min'] / T['flag_t_min'], 2),
    robust=rob,
)
(HERE / 'rape7.json').write_text(json.dumps(out, indent=1))
# asserts on what the copy says in words
assert out['n_t_ratio'] > 1.3, 'copy says the low-yield quarter uses much more N per tonne'
assert abs(out['n_ha_ratio'] - 1) < 0.15, 'copy says nitrogen per hectare is about the same'
assert out['flag_t_ratio'] > 1.15, 'copy says a low-yield tonne carries more FLAG'
assert rob['n_t_ratio_thirds'] > 1.25 and rob['flag_t_ratio_thirds'] > 1.15, 'pessimistic re-run (thirds, mineral only) must keep the direction'
if __name__ == '__main__':
    print(json.dumps(out, indent=1))
else:
    print('RAPE7: %d farms, %d field records; N per tonne %.1f vs %.1f kg (x%.2f); thirds x%.2f' % (
        out['farms'], out['respondents'], B['n_t'], T['n_t'], out['n_t_ratio'], rob['n_t_ratio_thirds']))
