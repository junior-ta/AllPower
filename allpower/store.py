from __future__ import annotations
import json, sqlite3, time, uuid
from pathlib import Path

class ManagedConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()

def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15, factory=ManagedConnection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=15000")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS jobs (
      id TEXT PRIMARY KEY, scenario TEXT NOT NULL, status TEXT NOT NULL,
      attempts INTEGER NOT NULL DEFAULT 0, lease_until REAL,
      created_at REAL NOT NULL, updated_at REAL NOT NULL, error TEXT);
    CREATE TABLE IF NOT EXISTS runs (
      id TEXT PRIMARY KEY, scenario TEXT NOT NULL, payload TEXT NOT NULL,
      created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS advisories (
      id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
      acknowledged_at REAL, FOREIGN KEY(run_id) REFERENCES runs(id));
    CREATE TABLE IF NOT EXISTS heartbeat (worker_id TEXT PRIMARY KEY, at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS advice_messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
      role TEXT NOT NULL, content TEXT NOT NULL, provider TEXT NOT NULL,
      created_at REAL NOT NULL, FOREIGN KEY(run_id) REFERENCES runs(id));
    CREATE INDEX IF NOT EXISTS advice_by_run ON advice_messages(run_id,id);
    """)
    return db

def enqueue(path, scenario):
    job_id = str(uuid.uuid4()); now = time.time()
    with connect(path) as db:
        db.execute("INSERT INTO jobs(id,scenario,status,created_at,updated_at) VALUES(?,?,'queued',?,?)",
                   (job_id, scenario, now, now))
    return job_id

def claim(path, lease_seconds=30):
    db = connect(path)
    try:
        db.execute("BEGIN IMMEDIATE")
        now = time.time()
        db.execute("""UPDATE jobs SET status='failed', lease_until=NULL,
          error=COALESCE(error,'Worker lease expired after retry limit'), updated_at=?
          WHERE status='running' AND lease_until < ? AND attempts >= 3""", (now,now))
        row = db.execute("""SELECT * FROM jobs WHERE (status='queued' OR
          (status='running' AND lease_until < ?)) AND attempts < 3
          ORDER BY created_at LIMIT 1""", (now,)).fetchone()
        if row:
            db.execute("UPDATE jobs SET status='running', attempts=attempts+1, lease_until=?, updated_at=? WHERE id=?",
                       (now+lease_seconds, now, row["id"]))
        db.commit()
        return dict(row) if row else None
    finally: db.close()

def finish(path, job_id, result):
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        now = time.time()
        db.execute("INSERT OR IGNORE INTO runs(id,scenario,payload,created_at) VALUES(?,?,?,?)",
                   (job_id, result["scenario"], json.dumps(result), now))
        db.execute("INSERT OR IGNORE INTO advisories(id,run_id,status) VALUES(?,?,?)",
                   ("adv-"+job_id, job_id, "open"))
        db.execute("UPDATE jobs SET status='done', lease_until=NULL, updated_at=? WHERE id=?", (now, job_id))

def fail(path, job_id, error):
    with connect(path) as db:
        row = db.execute("SELECT attempts FROM jobs WHERE id=?", (job_id,)).fetchone()
        status = "failed" if row and row["attempts"] >= 3 else "queued"
        db.execute("UPDATE jobs SET status=?, lease_until=NULL, error=?, updated_at=? WHERE id=?",
                   (status, str(error)[:300], time.time(), job_id))

def get_run(path, job_id):
    with connect(path) as db:
        job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not job: return None
        result = dict(job)
        run = db.execute("SELECT payload FROM runs WHERE id=?", (job_id,)).fetchone()
        if run:
            result["result"] = json.loads(run["payload"])
            adv = db.execute("SELECT id,status,acknowledged_at FROM advisories WHERE run_id=?", (job_id,)).fetchone()
            result["advisory"] = dict(adv) if adv else None
        return result

def acknowledge(path, advisory_id):
    with connect(path) as db:
        cur = db.execute("UPDATE advisories SET status='acknowledged', acknowledged_at=COALESCE(acknowledged_at,?) WHERE id=?",
                         (time.time(), advisory_id))
        if not cur.rowcount: return None
        row = db.execute("SELECT id,status,acknowledged_at,run_id FROM advisories WHERE id=?", (advisory_id,)).fetchone()
        return dict(row)

def list_runs(path, limit=20, before=None):
    with connect(path) as db:
        sql = "SELECT id,scenario,status,created_at,updated_at,error FROM jobs"
        params = []
        if before is not None:
            sql += " WHERE created_at < ?"; params.append(before)
        sql += " ORDER BY created_at DESC,id DESC LIMIT ?"; params.append(limit)
        return [dict(row) for row in db.execute(sql, params)]

def latest_run(path):
    with connect(path) as db:
        row = db.execute("SELECT id FROM runs ORDER BY created_at DESC,id DESC LIMIT 1").fetchone()
    return get_run(path, row['id']) if row else None

def acknowledgments(path, limit=20):
    with connect(path) as db:
        rows = db.execute("""SELECT a.id,a.run_id,a.status,a.acknowledged_at,
          r.scenario,r.created_at FROM advisories a JOIN runs r ON r.id=a.run_id
          WHERE a.status='acknowledged' ORDER BY a.acknowledged_at DESC LIMIT ?""", (limit,))
        return [dict(row) for row in rows]

def advice_history(path, run_id):
    with connect(path) as db:
        rows = db.execute("SELECT id,role,content,provider,created_at FROM advice_messages WHERE run_id=? ORDER BY id", (run_id,))
        return [dict(row) for row in rows]

def save_advice(path, run_id, question, answer, provider):
    with connect(path) as db:
        now=time.time()
        if question:
            db.execute("INSERT INTO advice_messages(run_id,role,content,provider,created_at) VALUES(?,'user',?,'user',?)", (run_id,question,now))
        db.execute("INSERT INTO advice_messages(run_id,role,content,provider,created_at) VALUES(?,'assistant',?,?,?)", (run_id,answer,provider,now))

def status(path):
    with connect(path) as db:
        counts = {row["status"]:row["n"] for row in db.execute("SELECT status,COUNT(*) n FROM jobs GROUP BY status")}
        beat = db.execute("SELECT MAX(at) t FROM heartbeat").fetchone()["t"]
    return {"queue": counts, "worker_last_seen_unix": beat,
            "worker_alive": bool(beat and time.time()-beat < 12)}
