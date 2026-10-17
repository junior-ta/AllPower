"""Train and evaluate six direct demand forecasters on a continuous hourly CSV.

Required columns: timestamp (ISO 8601 with timezone), demand_mw. See README.
"""
import argparse, csv, json, math, pickle
from datetime import datetime, timedelta
from pathlib import Path

def load(path):
    rows=[]
    with open(path,newline='') as f:
        for row in csv.DictReader(f):
            t=datetime.fromisoformat(row['timestamp'].replace('Z','+00:00'))
            if t.tzinfo is None: raise ValueError('timestamps need a timezone')
            v=float(row['demand_mw'])
            if not (0<v<200000): raise ValueError('implausible demand MW')
            rows.append((t,v))
    rows.sort()
    if len(set(t for t,_ in rows)) != len(rows): raise ValueError('duplicate timestamp')
    if len(rows)<24*35: raise ValueError('need at least 35 days of hourly data')
    for (a,_),(b,_) in zip(rows,rows[1:]):
        if b-a!=timedelta(hours=1): raise ValueError(f'missing or repeated hour: {a} to {b}')
    return rows

def features(rows, i):
    t=rows[i][0]; v=[r[1] for r in rows]
    return [v[i-lag] for lag in (1,2,3,6,12,24,48,168)]+[
        sum(v[i-24:i])/24, max(v[i-24:i]), min(v[i-24:i]),
        math.sin(2*math.pi*t.hour/24),math.cos(2*math.pi*t.hour/24),
        math.sin(2*math.pi*t.weekday()/7),math.cos(2*math.pi*t.weekday()/7),
        math.sin(2*math.pi*t.month/12),math.cos(2*math.pi*t.month/12)]

def metric(actual,pred):
    n=len(actual)
    return {'mae_mw':round(sum(abs(a-p) for a,p in zip(actual,pred))/n,2),
            'rmse_mw':round(math.sqrt(sum((a-p)**2 for a,p in zip(actual,pred))/n),2)}

def main():
    p=argparse.ArgumentParser();p.add_argument('csv');p.add_argument('--out',default='artifacts/demand');a=p.parse_args()
    rows=load(a.csv); out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    try:
        from xgboost import XGBRegressor
        build=lambda:XGBRegressor(n_estimators=180,max_depth=4,learning_rate=.06,
                                     subsample=.9,n_jobs=2,random_state=19)
        model_name='XGBoost'
    except ImportError:
        from sklearn.ensemble import HistGradientBoostingRegressor
        build=lambda:HistGradientBoostingRegressor(max_iter=180,max_leaf_nodes=20,
                                                   learning_rate=.06,random_state=19)
        model_name='HistGradientBoosting'
    # Targets never cross the six-hour separation between train, validation, test.
    end=len(rows)-6; test_start=int(end*.85); valid_start=int(end*.70)
    origins=list(range(168,end))
    train=[i for i in origins if i+6<valid_start]
    valid=[i for i in origins if valid_start<=i and i+6<test_start]
    test=[i for i in origins if i>=test_start]
    if min(map(len,(train,valid,test)))<24: raise ValueError('insufficient split coverage')
    report={'source_csv':str(Path(a.csv).resolve()),'rows':len(rows),'model':model_name,
            'selected_on_validation':{},
            'split':{'train_end':rows[train[-1]][0].isoformat(),
                     'validation_start':rows[valid[0]][0].isoformat(),
                     'test_start':rows[test[0]][0].isoformat()},'horizons':{}}
    for h in range(1,7):
        x=lambda ids:[features(rows,i) for i in ids]
        y=lambda ids:[rows[i+h][1] for i in ids]
        model=build();model.fit(x(train),y(train))
        val_pred=model.predict(x(valid)); test_pred=model.predict(x(test))
        val_res=sorted(abs(a-b) for a,b in zip(y(valid),val_pred))
        val_baseline=[rows[i+h-168][1] for i in valid]
        selected=metric(y(valid),val_pred)['mae_mw'] < metric(y(valid),val_baseline)['mae_mw']
        report['selected_on_validation'][str(h)]='candidate' if selected else 'weekly_baseline'
        q=val_res[min(len(val_res)-1,math.ceil(.9*(len(val_res)+1))-1)]
        baseline=[rows[i+h-168][1] for i in test]
        persistence=[rows[i][1] for i in test]
        coverage=sum(abs(a-b)<=q for a,b in zip(y(test),test_pred))/len(test)
        report['horizons'][str(h)]={'validation_candidate':metric(y(valid),val_pred),
                                    'validation_weekly_baseline':metric(y(valid),val_baseline),
                                    'candidate':metric(y(test),test_pred),
                                    'weekly_baseline':metric(y(test),baseline),
                                    'persistence_baseline':metric(y(test),persistence),
                                    'validation_interval_half_width_mw':round(q,1),
                                    'test_interval_coverage':round(coverage,3)}
        with open(out/f'h{h}.pkl','wb') as f:pickle.dump(model,f)
    (out/'evaluation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
