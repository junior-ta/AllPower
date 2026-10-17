from __future__ import annotations
import argparse, json, mimetypes, os, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from . import store
from .scenarios import SCENARIOS

ROOT = Path(__file__).resolve().parent.parent
MAX_BODY = 2_000_000

class Handler(BaseHTTPRequestHandler):
    def json(self, data, status=200):
        payload = json.dumps(data, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers(); self.wfile.write(payload)

    def authorized(self):
        token = os.getenv("ALLPOWER_TOKEN", "")
        return not token or self.headers.get("X-AllPower-Token") == token

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/") and not self.authorized():
            return self.json({"error":"unauthorized"}, 401)
        if path == "/api/status":
            model_file = ROOT / 'artifacts' / 'demand' / 'evaluation.json'
            demand_source = os.getenv('ALLPOWER_DEMAND_CSV')
            return self.json({"runtime_arch": os.uname().machine,
                              "model_version":"evaluated demand candidates available" if model_file.exists() else "seasonal-benchmark-v1",
                              "data_freshness":"user supplied CSV" if demand_source else "bundled scenario",
                              "mode":"real demand plus simulated supply" if demand_source else "simulated demo",
                              **store.status(self.server.db_path)})
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
        if not self.authorized(): return self.json({"error":"unauthorized"}, 401)
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
            found = store.acknowledge(self.server.db_path, match.group(1))
            return self.json({"status":"acknowledged"} if found else {"error":"unknown advisory"}, 200 if found else 404)
        if path == "/api/inspection":
            if self.headers.get('Content-Type','').split(';')[0] not in ('image/jpeg','image/png'):
                return self.json({'error':'Only JPEG or PNG is accepted'},415)
            try:
                from .vision import classify
                return self.json(classify(body))
            except FileNotFoundError:
                return self.json({"error":"Image model unavailable. Scenario inspection is simulated and labelled as such."}, 503)
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
