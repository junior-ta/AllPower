"""Load validated hourly demand and select the evaluated inference method."""
import csv, json, os, pickle
from pathlib import Path
from .scenarios import demand_history, forecast

def load_history():
    file=os.getenv('ALLPOWER_DEMAND_CSV')
    if not file: return demand_history()
    rows=[]
    with open(file,newline='') as f:
        for row in csv.DictReader(f):
            rows.append({'timestamp':row['timestamp'],'demand_mw':float(row['demand_mw']),
                         'provenance':os.getenv('ALLPOWER_DEMAND_PROVENANCE','observed public data')})
    if len(rows)<168: raise ValueError('Demand CSV needs at least 168 rows')
    return rows

def predict(history):
    baseline=forecast(history)
    if not os.getenv('ALLPOWER_DEMAND_CSV'):
        synthetic=Path('artifacts/synthetic_demand_ridge.json')
        if synthetic.exists():
            from scripts.train_demand import features
            from datetime import datetime
            artifact=json.loads(synthetic.read_text())
            rows=[(datetime.fromisoformat(r['timestamp']),r['demand_mw']) for r in history]
            values=features(rows,len(rows)-1)
            standardized=[(v-m)/s for v,m,s in zip(values,artifact['feature_mean'],artifact['feature_std'])]
            result=[]
            for h in range(1,7):
                if artifact['selection'][str(h)]=='ridge':
                    w=artifact['weights'][str(h)]
                    value=w['y_mean']+w['y_std']*(w['beta'][0]+sum(b*x for b,x in zip(w['beta'][1:],standardized)))
                    result.append(round(value,1))
                else:result.append(baseline[h-1])
            return result,artifact['version']
    directory=Path(os.getenv('ALLPOWER_MODEL_DIR','artifacts/demand'))
    report_file=directory/'evaluation.json'
    if not report_file.exists(): return baseline,'seasonal-benchmark-v1'
    report=json.loads(report_file.read_text())
    # Selection uses the validation window only. Test metrics remain untouched.
    if not report.get('selected_on_validation'):
        return baseline,'seasonal-benchmark-v1'
    try:
        from scripts.train_demand import features
        from datetime import datetime
        rows=[(datetime.fromisoformat(r['timestamp']),r['demand_mw']) for r in history]
        x=[features(rows,len(rows)-1)]
        result=[]
        selected=report['selected_on_validation']
        for h in range(1,7):
            if selected[str(h)]=='candidate':
                with open(directory/f'h{h}.pkl','rb') as f: model=pickle.load(f)
                result.append(round(float(model.predict(x)[0]),1))
            else: result.append(baseline[h-1])
        return result,report['model']+'-mixed-v1'
    except Exception:
        return baseline,'seasonal-benchmark-v1'
