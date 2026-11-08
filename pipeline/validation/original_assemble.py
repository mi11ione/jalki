"""Replay frozen banked procedures, export their existing values, validate, and rescore.
Run exactly: python3 stages/step-05135-2/assemble.py
All exports are synthetic-only. C3h/D2 are internal diagnostics, not official auto-scored tracks.
No bootstrap, Monte Carlo, candidate sweep, or earlier-directory write is run.
"""
import os
import sys
sys.dont_write_bytecode = True
for variable in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[variable] = '1'

from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
os.chdir(ROOT)
if not os.environ.get('UM_SUBMISSION_PANDAS'):
    result = subprocess.run(['/usr/bin/python3', '-B', str(Path(__file__).resolve())],
                            env=dict(os.environ, UM_SUBMISSION_PANDAS='1'))
    sys.exit(result.returncode)

import contextlib
import csv
import hashlib
import io
import json
import math
import runpy
import time
import traceback
from datetime import datetime, timezone
import numpy as np
import pandas as pd

def guard(event, args):
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, (str, bytes, os.PathLike)):
            p = Path(os.fsdecode(path)).resolve()
            writing = (isinstance(mode, str) and any(x in mode for x in 'wax+')) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
            if writing and HERE != p and HERE not in p.parents:
                raise PermissionError('Write outside ticket: ' + str(p))
            if any(x in str(p).lower() for x in ['quarantin', '/local/field_raw/', '/truth/', '/hidden/']):
                raise PermissionError('Forbidden input: ' + str(p))

sys.addaudithook(guard)
SUB = HERE / 'submission'
SUB.mkdir(exist_ok=True)

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def load(p):
    return json.loads(Path(p).read_text())

def execute_prefix(path, marker, label):
    p = ROOT / path
    src = p.read_text()
    assert marker in src
    prefix = src.split(marker)[0]
    (HERE / ('source_' + label + '.py')).write_text(prefix)
    scope = {'__file__': str(p), '__name__': label + '_readonly'}
    exec(compile(prefix, str(p), 'exec'), scope)
    return scope

def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False, default=lambda x: x.item()) + '\n')

def read_strings(p):
    with Path(p).open(newline='') as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames), list(reader)

def schema(p, expected_columns, ids, expected_ids, numeric, positive=(), fixed=None):
    cols, rows = read_strings(p)
    got_ids = [tuple(r[k] for k in ids) for r in rows]
    expected_ids = [tuple(str(v) for v in row) for row in expected_ids]
    finite = all(r.get(c, '').strip().lower() not in ('', 'nan', 'none', 'null', 'na', 'n/a') for r in rows for c in cols)
    for r in rows:
        for c in numeric:
            try:
                finite = finite and math.isfinite(float(r[c]))
            except (ValueError, KeyError):
                finite = False
    checks = dict(columns=cols == expected_columns, row_count=len(rows) == len(expected_ids),
                  unique_ids=len(set(got_ids)) == len(rows), ids_and_order=got_ids == expected_ids,
                  no_nan=finite, positive=all(float(r[c]) > 0 for r in rows for c in positive))
    if fixed:
        checks['unchanged_template_values'] = all(all(r[k] == e[k] for k in fixed[0]) for r,e in zip(rows,fixed[1]))
    return dict(ok=all(checks.values()), checks=checks, columns=cols, rows=len(rows), ids=ids)

def file_record(path, sources, kind, validation):
    return dict(path=str(Path(path).relative_to(ROOT)), sha256=digest(path), bytes=Path(path).stat().st_size,
                source_files=[dict(path=str(Path(p)), sha256=digest(p)) for p in sources],
                kind=kind, schema=validation)

def c1():
    # Existing e script ends its deterministic score section before any resampling.
    g = execute_prefix('stages/step-02435-8/run.py', '\ndef per_year(p):', 'C1')
    bank = load('stages/step-02435-8/scores.json')
    assert round(g['beta'], 4) == bank['c1-yield-e.beta']
    # Verbatim existing in-memory future table construction; no change to rounding or values.
    src = Path('stages/step-02435-8/run.py').read_text()
    start = src.index('# ---------------------------------------------------------------- 5. shipped_is_model')
    stop = src.index('nparts = math.ceil', start)
    exec(compile(src[start:stop], 'stages/step-02435-8/run.py', 'exec'), g)
    sub = g['sub']
    p = SUB / 'C1_yields_2027_2031_submission.csv'
    sub.to_csv(p, index=False)
    raw = g['_rc']
    tpl = raw(g['TPL'])
    columns, expected = read_strings(g['TPL'])
    key = ['parcel_id','year','crop']
    valid = schema(p, columns, key, [[r[k] for k in key] for r in expected], ['year','area_ha','yield_t_ha_pred'],
                   ['yield_t_ha_pred'], (columns[:-1], expected))
    back = raw(p)
    assert np.array_equal(back.yield_t_ha_pred.values, sub.yield_t_ha_pred.values)
    dev = g['F1te']
    devout = dev[['farm_id','year','crop','region','area_ha']].copy()
    devout['yield_t_ha_pred'] = g['p_e']
    dp = SUB / 'C1_dev.csv'
    devout.to_csv(dp,index=False)
    db = raw(dp)
    recomputed = g['official'](dev, db.yield_t_ha_pred.values)['score']
    # The target CSV has future years, so the dev replay is a separate, explicit file.
    return dict(source_ticket_id='step-02435-8', banked_version='c1-yield-e', schema_ok=valid['ok'],
                score_recomputed=recomputed, score_banked=bank['c1-yield-e.dev_score'],
                match=recomputed == bank['c1-yield-e.dev_score'], metric='official C1 formula on observed farm-season F1 proxy, 2022-2026',
                official_hidden_test_score=None, csv_score_direct=False,
                note='Promoted e had no saved CSV. Materialized its existing in-memory sub unchanged; checked future refit against existing c parts before applying unchanged e calibration. No model selection or bootstrap rerun.',
                files=[file_record(p,['stages/step-02435-8/run.py','stages/step-02435-8/scores.json'],'official target schema; materialized frozen procedure',valid),
                       file_record(dp,['stages/step-02435-8/run.py'],'dev predictions, internal',
                                   schema(dp,list(devout.columns),['farm_id','year','crop'],devout[['farm_id','year','crop']].itertuples(index=False,name=None),['year','area_ha','yield_t_ha_pred']))])

def c2():
    src = Path('stages/step-01626-6/c2_r5.py')
    g = execute_prefix(str(src), '# ---------------------------------------------------------------- B. G2 channel size', 'C2')
    state = g['State'](g['SV0'],g['FH0'],None)
    R = g['build'](state,2021,set(range(2022,2027)))
    ix = np.arange(len(g['ROWS']))[None,:]
    change, bad = g['predict']('PC',R,ix)
    dev = pd.DataFrame([dict(region=r,crop=c,scenario='dev',period='dev',mean_yield_change_pct=change[0,i],p_bad_year=bad[0,i])
                        for i,(r,c) in enumerate(g['ROWS'])])
    key = dev.copy()
    key['mean_yield_change_pct'],key['p_bad_year'] = R['L']['chg_t'],R['L']['pb_t']
    dp=SUB/'C2_dev.csv'
    dev.to_csv(dp,index=False)
    res = g['score_c2'](pd.read_csv(dp),key)
    original=Path('stages/step-00323-5/C2_climate_yield_risk_submission.csv')
    p=SUB/original.name
    p.write_bytes(original.read_bytes())
    cols,tpl=read_strings('twin/data/tasks/templates/C2_climate_yield_risk_submission.csv')
    ids=['region','crop','scenario','period']
    valid=schema(p,cols,ids,[[r[k] for k in ids] for r in tpl],['mean_yield_change_pct','p_bad_year'])
    target=pd.read_csv(p)
    valid['checks']['probability_in_range']=bool(target.p_bad_year.between(0,1).all())
    valid['ok']=all(valid['checks'].values())
    bank=load('stages/step-00323-5/scores.json')
    return dict(source_ticket_id='step-00323-5',latest_bank_ticket_id='step-04394-8',review_audit_ticket_id='step-04783-11',
                banked_version='PC incumbent; risk-5 promotion void and risk-6/7/8 not promoted',schema_ok=valid['ok'],
                score_recomputed=res['score'],score_banked=bank['c2-risk-3.dev_score'],match=res['score']==bank['c2-risk-3.dev_score'],
                metric='official C2 formula on six pseudo-exam region-crop rows, calibration through 2021, evaluation 2022-2026',
                official_hidden_test_score=None,csv_score_direct=False,
                note='Target CSV copied byte-for-byte. Dev score is a replay of the frozen procedure on history, not a score of the 2041-2060 target CSV. Internal diagnostic; superiority not established.',
                files=[file_record(p,[original],'official target schema; exact copy',valid),
                       file_record(dp,[src],'dev predictions, internal',schema(dp,list(dev.columns),ids,dev[ids].itertuples(index=False,name=None),['mean_yield_change_pct','p_bad_year']))])

def c3h():
    # C3h prefix contains the exact frozen fold_g implementation, no sweep or bootstrap.
    g = execute_prefix('stages/step-04403-9/c3h.py','# [1] forward-blind pick','C3h')
    prior=load('stages/step-01329-10/c3-g.json')
    parts=[]
    for year,pick in prior['procedure']['dev_picks'].items():
        y=int(year)
        lam,H=next((l,h) for n,l,h in g['CANDS'] if n==pick)
        parts.append(g['split'](g['hist'],lam,H,lambda x,y=y:x.year != y,lambda x,y=y:x.year==y))
    frame=pd.concat(parts,ignore_index=True)
    dev=frame[['farm_id','year','crop','region','area_ha']].copy()
    dev['yield_t_ha_pred']=frame.p_model.values
    p=SUB/'C3h_dev.csv'
    dev.to_csv(p,index=False)
    back=pd.read_csv(p)
    score=g['V'].sc(frame.assign(p_model=back.yield_t_ha_pred.values))
    bank=load('stages/step-04403-9/scores.json')['scores']['c3h.banked_dev_score']
    valid=schema(p,list(dev.columns),['farm_id','year','crop'],dev[['farm_id','year','crop']].itertuples(index=False,name=None),['year','area_ha','yield_t_ha_pred'])
    return dict(source_ticket_id='step-04403-9',prediction_source_ticket_id='step-01329-10',
                banked_version='nested procedure P dev, retained by c3h with survives=false',schema_ok=valid['ok'],
                score_recomputed=score,score_banked=bank,match=score==bank,
                metric='official C1 yield-score formula used by the C3 internal nested LOYO diagnostic; not an official C3 score',
                official_schema_available=False,official_scorer_available=False,official_submission_ready=False,csv_score_direct=True,
                note='C3 is a rubric track. No C3h target CSV/template exists; this exports the exact banked nested dev predictions using the persisted per-fold choices. No new candidate selected. Forward survival remains false.',
                files=[file_record(p,['stages/step-04403-9/c3h.py','stages/step-01329-10/c3-g.json'],'internal dev schema only',valid)])

def d2():
    g=execute_prefix('stages/step-04763-7/evaluate.py','# review check: held-out label mutation','D2')
    bank=load('stages/step-04763-7/scores.json')
    calls=bank['d2-r5.calls']
    assert g['c_calls']==[r['called'] for r in calls]
    assert g['labels']==[r['flagged'] for r in calls]
    for r,c in zip(g['rows'],calls):
        assert (r['material_id'],r['erp_origin'],r['material_group'])==(c['material_id'],c['origin'],c['group'])
    p=SUB/'D2_dev.csv'
    with p.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(calls[0]))
        writer.writeheader(); writer.writerows(calls)
    cols,rows=read_strings(p)
    result=g['metric']([r['called']=='True' for r in rows],[r['flagged']=='True' for r in rows])
    valid=schema(p,list(calls[0]),['material_id','origin'],[[r['material_id'],r['origin']] for r in calls],[])
    return dict(source_ticket_id='step-04763-7',banked_version='d2-r5 repaired diagnostic; promoted=0',schema_ok=valid['ok'],
                score_recomputed=result['f1'],score_banked=bank['d2-r5.f1'],match=result['f1']==bank['d2-r5.f1'],
                metric='conventional F1, leave-one-material-group-out concordance with public HIC/EUDR flags; not ecological accuracy',
                official_schema_available=False,official_scorer_available=False,official_submission_ready=False,csv_score_direct=True,
                note='D2 is a rubric track. Calls copied unchanged from the latest kept bank diagnostic and independently replayed with the existing threshold scorer. No new operating point, bootstrap, or promotion.',
                files=[file_record(p,['stages/step-04763-7/scores.json','stages/step-04763-7/evaluate.py'],'internal dev schema only',valid)])

def e12():
    src='stages/step-00630-3/e12_nested.py'
    g=execute_prefix(src,'# ---- 1. code tests','E12')
    bank=load('stages/step-04024-8/scores.json')
    years=[2023,2024,2025]
    dev=pd.DataFrame([dict(year=y,actual_m3=g['y'][y],forecast_m3=g['mean_last_3'](y,g['y']),naive_m3=g['seasonal_naive_annual'](y,g['y'])) for y in years])
    p=SUB/'E12_dev.csv'
    dev.to_csv(p,index=False)
    back=pd.read_csv(p)
    mae=float((back.forecast_m3-back.actual_m3).abs().mean())
    valid=schema(p,list(dev.columns),['year'],[[y] for y in years],list(dev.columns))
    # Exact existing mean3 forecast. The official E12 question instead asks for
    # actual 2024 consumption, so this forecast must never use an E question id.
    future=g['mean_last_3'](2026,g['y'])
    ap=SUB/'E12_forecast_2026.csv'
    with ap.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['year','forecast_m3']);w.writeheader();w.writerow(dict(year=2026,forecast_m3=future))
    av=schema(ap,['year','forecast_m3'],['year'],[[2026]],['year','forecast_m3'])
    wrong=SUB/'E12_answers_submission.csv'
    if wrong.exists():
        wrong.unlink()
    return dict(source_ticket_id='step-04024-8',latest_hostile_audit_ticket_id='step-04774-9',
                banked_version='mean_last_3, shipped; descriptive only',schema_ok=valid['ok'] and av['ok'],
                score_recomputed=round(mae,1),score_recomputed_unrounded=mae,score_banked=bank['shipped_mae'],
                match=round(mae,1)==bank['shipped_mae'],metric='MAE m3/year, 2023-2025 origins, annual net water excluding S-BJU',
                forecast_2026_m3=future,official_hidden_test_score=None,csv_score_direct=True,
                official_schema_available=False,official_scorer_available=False,official_submission_ready=False,
                note='No saved mean3 CSV existed. Materialized unchanged forecasts from the banked function; comparison uses bank precision of one decimal. This forecast diagnostic is distinct from official E12, which asks for actual 2024 consumption. Forecast superiority was rejected by subsequent year audits.',
                files=[file_record(p,[src,'stages/step-04024-8/scores.json'],'internal dev predictions, exact existing mean3 function',valid),
                       file_record(ap,[src,'stages/step-04024-8/scores.json'],'internal next-year forecast; not an E12 answer',av)])

track=os.environ.get('UM_SUBMISSION_TRACK')
if track:
    start=time.monotonic()
    # The unchanged generic checker and the task-specific checker both precede scoring.
    runpy.run_path(str(HERE/'gate.py'),run_name='__main__')
    try:
        result=globals()[track.lower()]()
        result['runtime_seconds']=round(time.monotonic()-start,3)
        dump(HERE/(track+'_result.json'),result)
        print(json.dumps({track:result},indent=2))
    except Exception:
        traceback.print_exc()
        sys.exit(1)
else:
    runpy.run_path(str(HERE/'gate.py'),run_name='__main__')
    results={}
    for name in ['C1','C2','C3h','D2','E12']:
        print('REPLAY',name,flush=True)
        completed=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve())],
                                 env=dict(os.environ,UM_SUBMISSION_TRACK=name),capture_output=True,text=True)
        (HERE/(name+'_replay.log')).write_text(completed.stdout+completed.stderr)
        if completed.returncode:
            print(name,'FAILED',completed.stderr[-2500:],flush=True)
            results[name]=dict(schema_ok=False,score_recomputed=None,score_banked=None,match=False,error='See '+name+'_replay.log')
        else:
            results[name]=load(HERE/(name+'_result.json'))
            print(name,'schema_ok',results[name]['schema_ok'],'score_recomputed',results[name]['score_recomputed'],
                  'score_banked',results[name]['score_banked'],'match',results[name]['match'],flush=True)
    dump(HERE/'scores.json',results)
    dump(HERE/'submission_manifest.json',dict(ticket='step-05135-2',created_utc=datetime.now(timezone.utc).isoformat(),
          script='python3 stages/step-05135-2/assemble.py',synthetic_only=True,
          run_state_note='RUN.json and LEDGER.md absent from run/; no replacements written; domain inferred from run/brief.md',
          facts_gate='Unchanged checker: 127/128 manifest files, no hash mismatches, 15/15 facts. Sole omitted workbook accepted under explicit decisions.md rule.',
          no_values_changed=True,official_five_track_submission_possible=False,
          limitations='C3 and D2 are rubric tracks without official schemas/scorers; E12 MAE concerns an internal forecast rather than official E12 actual-2024 consumption. C1/C2 target years have no public dev key. CSVs distinguish future target submissions from internal dev replays.',
          tracks=results))
    print('MANIFEST',str((HERE/'submission_manifest.json').relative_to(ROOT)))
