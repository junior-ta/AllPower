import csv
from pathlib import Path
from allpower.scenarios import demand_history

target=Path('data/demo_demand_simulated.csv');target.parent.mkdir(exist_ok=True)
rows=demand_history()
with target.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['timestamp','demand_mw','provenance']);w.writeheader();w.writerows(rows)
print(target, len(rows), 'rows; SIMULATED')
