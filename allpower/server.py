from __future__ import annotations
import argparse, hmac, json, mimetypes, os, platform, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from . import store
from .scenarios import SCENARIOS

ROOT = Path(__file__).resolve().parent.parent
MAX_BODY = 2_000_000
FACILITIES = [
    {"id":"insulator-01","name":"Bayou line · glass insulator","location":"Houston area",
     "state":"Functional","confidence":0.94,"inspected_at":"Illustrative record","live_demo":True},
    {"id":"substation-02","name":"Gulf Coast substation","location":"Galveston area",
     "state":"Not functional","confidence":0.87,"inspected_at":"Illustrative record","live_demo":False},
    {"id":"feeder-03","name":"Brazos distribution feeder","location":"Brazoria area",
     "state":"Functional","confidence":0.91,"inspected_at":"Illustrative record","live_demo":False},
]

class Handler(BaseHTTPRequestHandler):
    def json(self, data, status=200):
        payload = json.dumps(data, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers(); self.wfile.write(payload)

    def authorized(self, scope=None):
        provided = self.headers.get("X-AllPower-Token", "")
        master = os.getenv("ALLPOWER_TOKEN", "")
        hospital = os.getenv("ALLPOWER_HOSPITAL_TOKEN", "")
        supplier = os.getenv("ALLPOWER_SUPPLIER_TOKEN", "")
        if not any((master, hospital, supplier)): return True
        if master and hmac.compare_digest(provided, master): return True
        if scope == "hospital":
            return bool(hospital and hmac.compare_digest(provided, hospital))
        if scope == "supplier":
            return bool(supplier and hmac.compare_digest(provided, supplier))
        return bool((hospital and hmac.compare_digest(provided, hospital)) or
                    (supplier and hmac.compare_digest(provided, supplier)))

    def access_error(self, scope=None):
        return self.json({"error":"Access token required or invalid for this portal"}, 401)

    def do_GET(self):
        path = urlparse(self.path).path
        scope = "hospital" if path.startswith("/api/hospital/") else ("supplier" if path.startswith("/api/supplier/") or path == "/api/inspection" else None)
        if path.startswith("/api/") and not self.authorized(scope):
            return self.access_error(scope)
        if path == "/api/status":
            latest = store.latest_run(self.server.db_path)
            record = latest.get('result', {}) if latest else {}
            return self.json({"runtime_arch": platform.machine(),
                              "model_version": record.get('model_version', 'No completed run'),
                              "data_freshness": record.get('input_timestamp'),
                              "mode": record.get('provenance', {}).get('demand_history', 'No completed run'),
                              **store.status(self.server.db_path)})
        if path == "/api/runs/latest":
            return self.json(store.latest_run(self.server.db_path))
        if path == "/api/runs":
            return self.json({"runs": store.list_runs(self.server.db_path)})
        if path == "/api/hospital/acknowledgments":
            return self.json({"acknowledgments": store.acknowledgments(self.server.db_path)})
        if path == "/api/supplier/facilities":
            return self.json({"facilities": FACILITIES})
        match = re.fullmatch(r"/api/hospital/runs/([0-9a-f-]{36})/advice", path)
        if match:
            run = store.get_run(self.server.db_path, match.group(1))
            if not run or run["status"] != "done": return self.json({"error":"completed run not found"},404)
            return self.json({"messages": store.advice_history(self.server.db_path, run["id"])})
        if path == "/api/scenarios":
            return self.json({"scenarios":[{"id": k, **v, "provenance":"simulated"} for k,v in SCENARIOS.items()]})
        match = re.fullmatch(r"/api/runs/([0-9a-f-]{36})", path)
        if match:
            run = store.get_run(self.server.db_path, match.group(1))
            return self.json(run if run else {"error":"unknown run"}, 200 if run else 404)
        if path == "/": path = "/index.html"
        target = (ROOT / "web" / path.lstrip("/")).resolve()
        if not target.is_relative_to((ROOT / "web").resolve()) or not target.is_file():
            return self.json({"error":"not found"}, 404)
        payload = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers(); self.wfile.write(payload)

    def do_POST(self):
        path = urlparse(self.path).path
        scope = "hospital" if path.startswith("/api/hospital/") else ("supplier" if path == "/api/inspection" else None)
        if not self.authorized(scope): return self.access_error(scope)
        size = int(self.headers.get("Content-Length", "0"))
        if size > MAX_BODY: return self.json({"error":"request too large"}, 413)
        body = self.rfile.read(size) if size else b''
        match = re.fullmatch(r"/api/scenarios/([a-z-]+)/run", path)
        if match:
            scenario = match.group(1)
            if scenario not in SCENARIOS: return self.json({"error":"unknown scenario"}, 404)
            job_id = store.enqueue(self.server.db_path, scenario)
            return self.json({"run_id":job_id,"status":"queued"}, 202)
        match = re.fullmatch(r"/api/advisories/(adv-[0-9a-f-]{36})/acknowledge", path)
        if match:
            if not self.authorized("hospital"): return self.access_error("hospital")
            found = store.acknowledge(self.server.db_path, match.group(1))
            return self.json(found if found else {"error":"unknown advisory"}, 200 if found else 404)
        if path == "/api/hospital/advice":
            if size > 8_000: return self.json({"error":"question too long"},413)
            try: request = json.loads(body)
            except (ValueError, UnicodeDecodeError): return self.json({"error":"invalid JSON"},400)
            if not isinstance(request, dict): return self.json({"error":"invalid request"},400)
            run_id = request.get("run_id")
            question = request.get("question", "")
            if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f-]{36}", run_id):
                return self.json({"error":"invalid run ID"},400)
            if not isinstance(question, str) or len(question) > 500:
                return self.json({"error":"question must be under 500 characters"},400)
            run = store.get_run(self.server.db_path, run_id)
            if not run or run["status"] != "done": return self.json({"error":"completed run not found"},404)
            from . import advice
            history = store.advice_history(self.server.db_path, run_id)
            if not question.strip() and any(x['role']=='assistant' for x in history):
                last = next(x for x in reversed(history) if x['role']=='assistant')
                return self.json({"answer":last['content'],"provider":last['provider'],
                                  "fallback":last['provider']==advice.CHECKLIST_VERSION,"cached":True})
            if len(history) >= 30: return self.json({"error":"Conversation limit reached for this run"},429)
            result = advice.generate(run, question.strip(), history)
            store.save_advice(self.server.db_path, run_id, question.strip(),result['answer'],result['provider'])
            return self.json(result)
        if path == "/api/inspection":
            if self.headers.get('Content-Type','').split(';')[0] not in ('image/jpeg','image/png'):
                return self.json({'error':'Only JPEG or PNG is accepted'},415)
            try:
                from .vision import classify
                return self.json(classify(body))
            except FileNotFoundError:
                return self.json({"error":"Image model unavailable. Scenario inspection is simulated and labelled as such."}, 503)
            except ImportError:
                return self.json({"error":"Image inference dependencies are unavailable on this web host."}, 503)
            except ValueError as exc:
                return self.json({'error':str(exc)},400)
        return self.json({"error":"not found"}, 404)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=os.getenv("ALLPOWER_DB", "data/allpower.sqlite3"))
    p.add_argument("--host", default=os.getenv("ALLPOWER_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.getenv("ALLPOWER_PORT", "8080")))
    args = p.parse_args()
    server = ThreadingHTTPServer((args.host,args.port), Handler)
    server.db_path = args.db
    store.connect(args.db).close()
    print(f"AllPower http://{args.host}:{args.port}", flush=True)
    server.serve_forever()

if __name__ == "__main__": main()
