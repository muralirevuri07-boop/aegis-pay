import sqlite3, json
from datetime import datetime, timezone

DB = "aegis.db"

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def init():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS purchases(
            id INTEGER PRIMARY KEY AUTOINCREMENT, request TEXT, items TEXT DEFAULT '[]',
            total REAL DEFAULT 0, verdict TEXT, reasons TEXT DEFAULT '[]', status TEXT,
            order_id TEXT, approve_url TEXT, agent_message TEXT, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, purchase_id INTEGER,
            event TEXT, detail TEXT)""")

def create(request):
    with conn() as c:
        cur = c.execute("INSERT INTO purchases(request, status, created_at) VALUES(?,?,?)",
                        (request, "new", now()))
        return cur.lastrowid

def update(pid, **fields):
    for k in ("items", "reasons"):
        if k in fields:
            fields[k] = json.dumps(fields[k])
    cols = ", ".join(f"{k}=?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE purchases SET {cols} WHERE id=?", (*fields.values(), pid))

def _row(r):
    if r is None:
        return None
    d = dict(r)
    d["items"] = json.loads(d["items"] or "[]")
    d["reasons"] = json.loads(d["reasons"] or "[]")
    return d

def get(pid):
    with conn() as c:
        return _row(c.execute("SELECT * FROM purchases WHERE id=?", (pid,)).fetchone())

def by_order(order_id):
    with conn() as c:
        return _row(c.execute("SELECT * FROM purchases WHERE order_id=?", (order_id,)).fetchone())

def list_purchases():
    with conn() as c:
        return [_row(r) for r in c.execute("SELECT * FROM purchases ORDER BY id DESC LIMIT 20")]

def log(pid, event, detail=""):
    with conn() as c:
        c.execute("INSERT INTO audit(ts, purchase_id, event, detail) VALUES(?,?,?,?)",
                  (now(), pid, event, detail))

def list_audit():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 40")]

def spent_today():
    today = now()[:10]
    with conn() as c:
        row = c.execute("SELECT COALESCE(SUM(total),0) FROM purchases WHERE status='paid' AND substr(created_at,1,10)=?", (today,)).fetchone()
        return float(row[0])
