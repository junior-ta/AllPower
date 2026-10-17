import argparse, os, time, traceback
from . import store
from .scenarios import scenario_output
from .backup import plan
from .demand import load_history, predict

def run(db_path):
    worker_id = os.getenv("HOSTNAME", "local-worker")
    while True:
        with store.connect(db_path) as db:
            db.execute("INSERT OR REPLACE INTO heartbeat(worker_id,at) VALUES(?,?)", (worker_id, time.time()))
        job = store.claim(db_path)
        if not job:
            time.sleep(1)
            continue
        try:
            history = load_history()
            values, version = predict(history)
            output = scenario_output(job["scenario"], history, values, version)
            output["run_id"] = job["id"]
            output["backup"] = plan(output)
            output["advisory_text"] = (
                "Prepare backup systems and review the six-hour energy plan. "
                "Confirm generator readiness and acknowledge this advisory."
                if output["risk"] == "prepare" else
                "Continue routine monitoring. No projected tight-margin hour in this scenario.")
            store.finish(db_path, job["id"], output)
        except Exception as exc:
            traceback.print_exc()
            store.fail(db_path, job["id"], exc)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=os.getenv("ALLPOWER_DB", "data/allpower.sqlite3"))
    run(p.parse_args().db)
