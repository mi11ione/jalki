"""Recompute saved CSV diagnostics with the exact scorers used by the submission assembler.
Requires numpy and pandas; does not train, search, resample, or write files.
"""
import sys
sys.dont_write_bytecode=True
import ast
import importlib.util
import json
from pathlib import Path
try:
    import numpy as np
    import pandas as pd
except ImportError as exc:
    print('VERIFY_SCORES NOT RUN: numpy and pandas are required (' + str(exc) + '). '
          'Install them with: python3 -m pip install numpy==2.0.2 pandas==2.3.3 (versions from requirements.txt). '
          'The app and python3 cold_start.py do not need them.')
    raise SystemExit(3)

HERE=Path(__file__).resolve().parent
SUB=HERE/'submission'; VAL=HERE/'validation'

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def main():
    scorer=load_module('official_score',VAL/'official_score.py')
    d2=load_module('d2_metric',VAL/'d2_metric.py')
    assembly=ast.parse((VAL/'original_assemble.py').read_text())
    e12=next(n for n in assembly.body if isinstance(n,ast.FunctionDef) and n.name=='e12')
    mae_expr=next(n.value for n in e12.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='mae' for t in n.targets))
    def c1(pred_path,key_path):
        pred=pd.read_csv(pred_path).rename(columns={'farm_id':'parcel_id'})
        key=pd.read_csv(key_path).rename(columns={'farm_id':'parcel_id','yield_t_ha':'yield_t_ha_true'})
        ids=['parcel_id','year','crop']
        assert not key.duplicated(ids).any() and not pred.duplicated(ids).any()
        assert set(map(tuple,key[ids].values))==set(map(tuple,pred[ids].values))
        result=scorer.score_c1(pred,key)
        review=scorer.score_c1(pred.iloc[::-1],key)
        assert result==review
        return result['score']
    scores={
        'C1':c1(SUB/'C1_dev.csv',VAL/'C1_observed_key.csv'),
        'C1_yield_e_reference':c1(VAL/'C1_yield_e_dev.csv',VAL/'C1_observed_key.csv'),
        'C3h':c1(SUB/'C3h_dev.csv',VAL/'C3h_observed_key.csv'),
    }
    pred=pd.read_csv(SUB/'C2_dev.csv');key=pd.read_csv(VAL/'C2_observed_key.csv')
    scores['C2']=scorer.score_c2(pred,key)['score']
    assert scorer.score_c2(pred.iloc[::-1],key)['score']==scores['C2']
    calls=pd.read_csv(SUB/'D2_dev.csv')
    scores['D2']=d2.metric(calls.called.tolist(),calls.flagged.tolist())['f1']
    back=pd.read_csv(SUB/'E12_dev.csv')
    scores['E12']=round(eval(compile(ast.Expression(mae_expr),'<assemble.py e12 MAE>','eval'),{'back':back}),1)
    functions=load_module('e12_functions',VAL/'e12_functions.py');functions.np=np
    series={int(y):float(v) for y,v in json.loads((VAL/'water_series.json').read_text()).items()}
    future=pd.read_csv(SUB/'E12_forecast_2026.csv')
    assert float(future.forecast_m3.iloc[0])==functions.mean_last_3(int(future.year.iloc[0]),series)
    target_checks={}
    for track,file in [('C1','C1_yields_2027_2031_submission.csv'),('C2','C2_climate_yield_risk_submission.csv')]:
        df=pd.read_csv(SUB/file); template=pd.read_csv(VAL/(track+'_target_template.csv'))
        values=['yield_t_ha_pred'] if track=='C1' else ['mean_yield_change_pct','p_bad_year']
        ids=[c for c in template.columns if c not in values]
        assert list(df.columns)==list(template.columns)
        assert df[ids].astype(str).equals(template[ids].astype(str))
        assert not df.isna().any().any() and np.isfinite(df[values].to_numpy()).all()
        if track=='C1': assert (df.yield_t_ha_pred>0).all()
        else: assert df.p_bad_year.between(0,1).all()
        target_checks[track]={'rows':len(df),'schema_ok':True,'public_answer_key_available':False,'score':None}
    # Official auto-scored tracks A1, A2, D1, E (added by step-09801-2): saved CSVs on public dev keys.
    for track,file,values in [('A1','A1_issues_submission.csv',['confidence']),('A2','A2_inventory_2025_submission.csv',['tco2e']),
                              ('D1','D1_catchment_priority_submission.csv',['apetit_p_to_water_kg','apetit_n_to_water_kg','priority_rank']),
                              ('E','E_answers_submission.csv',[])]:
        df=pd.read_csv(SUB/file); template=pd.read_csv(VAL/(track+'_target_template.csv'))
        assert list(df.columns)==list(template.columns) and not df.isna().any().any()
        assert np.isfinite(df[values].to_numpy(dtype=float)).all()
        if len(template):
            ids=[c for c in template.columns if not template[c].isna().all()]
            assert df[ids].astype(str).equals(template[ids].astype(str))
        target_checks[track]={'rows':len(df),'schema_ok':True}
    def review(fn,sub,key):
        a=fn(sub,key)['score'];assert fn(sub.iloc[::-1],key.iloc[::-1])['score']==a;return float(a)  # native float: NumPy scalars break json.dumps
    scores['A1']=review(scorer.score_a1,pd.read_csv(SUB/'A1_dev.csv'),pd.read_csv(VAL/'A1_dev_issue_labels_2023_2024.csv'))
    folds=[review(scorer.score_a2,pd.read_csv(SUB/f'A2_dev_{y}_fit_{f}.csv'),pd.read_csv(VAL/f'A2_dev_inventory_{y}.csv')) for y,f in [(2024,2023),(2023,2024)]]
    scores['A2']=round(sum(folds)/len(folds),2)
    scores['D1']=review(scorer.score_d1,pd.read_csv(SUB/'D1_catchment_priority_submission.csv'),pd.read_csv(VAL/'D1_dev_catchments_2025.csv'))
    scores['E']=review(scorer.score_e,pd.read_csv(SUB/'E_answers_submission.csv'),pd.read_csv(VAL/'E_dev_answers.csv'))
    expected=json.loads((VAL/'expected_scores.json').read_text())
    match={k:scores[k]==v for k,v in expected.items()}
    result={'scores':scores,'matches_source_bank':match,'all_match_source_bank':all(match.values()),
            'matches_ticket_C1_literal':scores['C1']==expected['C1_yield_e_reference'],
            'future_targets':target_checks,'E12_forecast_2026_m3':float(future.forecast_m3.iloc[0]),
            'row_order_hostile_checks_ok':True,'scope':'synthetic_only; diagnostic procedure replays; no hidden-test scores'}
    print(json.dumps(result,indent=2,allow_nan=False))
    assert result['all_match_source_bank']

if __name__=='__main__':main()
