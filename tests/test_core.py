import json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from allpower.scenarios import scenario_output, forecast, demand_history
from allpower.backup import plan
from allpower import store, demand

class CoreTests(unittest.TestCase):
    def test_forecast_uses_prior_matching_hours(self):
        rows=[{'demand_mw':float(i)} for i in range(200)]
        expected=.62*32+.28*176+.10*199
        self.assertAlmostEqual(forecast(rows,1)[0],round(expected,1))
    def test_shipped_synthetic_model_is_loaded_without_training(self):
        with patch.dict(os.environ, {'ALLPOWER_DEMAND_CSV':''}):
            values, version=demand.predict(demand_history())
        self.assertEqual(version,'synthetic-ridge-v1')
        self.assertEqual(len(values),6)
    def test_selected_weekly_baseline_matches_evaluation_method(self):
        rows=demand_history()
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'evaluation.json').write_text(json.dumps({
                'selected_on_validation':{str(i):'weekly_baseline' for i in range(1,7)},
                'model':'test'}))
            with patch.dict(os.environ, {'ALLPOWER_DEMAND_CSV':'provided.csv','ALLPOWER_MODEL_DIR':tmp}):
                values, version=demand.predict(rows)
        self.assertEqual(version,'test-mixed-v1')
        self.assertEqual(values,[float(rows[-169+h]['demand_mw']) for h in range(1,7)])
    def test_normal_and_supply_loss(self):
        normal=scenario_output('normal'); loss=scenario_output('supply-loss')
        self.assertIsNone(normal['first_deficit_hour'])
        self.assertIsNotNone(loss['first_deficit_hour'])
        self.assertGreater(loss['deficit_energy_mwh'],0)
        self.assertEqual(loss['provenance']['supply'],'simulated')
    def test_backup_constraints(self):
        result=plan(scenario_output('supply-loss'))
        self.assertLessEqual(sum(x['battery_kwh'] for x in result['hours']),720.01)
        self.assertLessEqual(sum(x['generator_kwh'] for x in result['hours']),1800.01)
        self.assertGreaterEqual(result['improvement_kwh'],-.01)
    def test_queue_and_deduplication(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'test.db');j=store.enqueue(path,'storm');claimed=store.claim(path)
            self.assertEqual(claimed['id'],j)
            record=scenario_output('storm');record['backup']=plan(record)
            store.finish(path,j,record);store.finish(path,j,record)
            run=store.get_run(path,j)
            self.assertEqual(run['status'],'done')
            self.assertTrue(store.acknowledge(path,'adv-'+j))
            self.assertEqual(store.get_run(path,j)['advisory']['status'],'acknowledged')
    def test_expired_final_lease_becomes_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'test.db');j=store.enqueue(path,'storm')
            with store.connect(path) as db:
                db.execute("UPDATE jobs SET status='running',attempts=3,lease_until=0 WHERE id=?",(j,))
            self.assertIsNone(store.claim(path))
            self.assertEqual(store.get_run(path,j)['status'],'failed')

if __name__=='__main__':unittest.main()
