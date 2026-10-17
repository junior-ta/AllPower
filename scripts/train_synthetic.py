"""Fit a portable six-horizon ridge model on the disclosed synthetic series."""
import json, math
from datetime import datetime
from pathlib import Path
import numpy as np
from allpower.scenarios import demand_history
from scripts.train_demand import features, metric

rows=[(datetime.fromisoformat(r['timestamp']),r['demand_mw']) for r in demand_history()]
end=len(rows)-6; valid_start=int(end*.70); test_start=int(end*.85)
train=[i for i in range(168,end) if i+6<valid_start]
valid=[i for i in range(168,end) if valid_start<=i and i+6<test_start]
test=[i for i in range(168,end) if i>=test_start]
xtrain=np.array([features(rows,i) for i in train],dtype=float)
xval=np.array([features(rows,i) for i in valid],dtype=float)
xtest=np.array([features(rows,i) for i in test],dtype=float)
mean=xtrain.mean(axis=0);std=xtrain.std(axis=0);std[std<1e-9]=1
scale=lambda x:(x-mean)/std
xt=scale(xtrain);xv=scale(xval);xs=scale(xtest)
report={'dataset':'deterministic simulated demand, seed 19','model':'ridge direct six horizons',
        'split':{'train':len(train),'validation':len(valid),'test':len(test)},
        'selection':'validation MAE only','horizons':{}}
weights={}
for h in range(1,7):
    ytrain=np.array([rows[i+h][1] for i in train]);yval=np.array([rows[i+h][1] for i in valid]);ytest=np.array([rows[i+h][1] for i in test])
    ymean=float(ytrain.mean()); ystd=float(ytrain.std())
    design=np.column_stack([np.ones(len(xt)),xt])
    penalty=np.eye(design.shape[1])*20;penalty[0,0]=0
    beta=np.linalg.solve(design.T@design+penalty,design.T@((ytrain-ymean)/ystd))
    predict=lambda x:ymean+ystd*(np.column_stack([np.ones(len(x)),x])@beta)
    valpred=predict(xv);testpred=predict(xs)
    valbase=np.array([rows[i+h-168][1] for i in valid]);testbase=np.array([rows[i+h-168][1] for i in test])
    selected='ridge' if metric(yval,valpred)['mae_mw']<metric(yval,valbase)['mae_mw'] else 'weekly_baseline'
    report['horizons'][str(h)]={'selected':selected,'validation_ridge':metric(yval,valpred),
        'validation_weekly':metric(yval,valbase),'test_ridge':metric(ytest,testpred),
        'test_weekly':metric(ytest,testbase)}
    weights[str(h)]={'beta':[float(x) for x in beta], 'y_mean':ymean,'y_std':ystd}
artifact={'version':'synthetic-ridge-v1','provenance':'simulated','feature_mean':mean.tolist(),
          'feature_std':std.tolist(),'weights':weights,'selection':{h:v['selected'] for h,v in report['horizons'].items()},
          'evaluation':report}
target=Path('artifacts/synthetic_demand_ridge.json');target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(artifact,indent=2))
print(json.dumps(report,indent=2))
