import json, os, sqlite3, uuid, datetime as dt

def _conn():
    c = sqlite3.connect(os.getenv("KISANMATE_DB", "kisanmate.db"))
    c.execute("CREATE TABLE IF NOT EXISTS a(id TEXT PRIMARY KEY, created TEXT, crop TEXT, status TEXT, result TEXT)")
    return c

def save(crop, status, result):
    i = uuid.uuid4().hex
    with _conn() as c:
        c.execute("INSERT INTO a VALUES(?,?,?,?,?)", (i, dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), crop, status, json.dumps(result)))
    return i

def list_all():
    with _conn() as c:
        return [dict(id=r[0], created=r[1], crop=r[2], status=r[3]) for r in c.execute("SELECT id,created,crop,status FROM a ORDER BY created DESC LIMIT 50")]

def get(i):
    with _conn() as c:
        r = c.execute("SELECT result FROM a WHERE id=?", (i,)).fetchone()
    return json.loads(r[0]) if r else None

def clear():
    with _conn() as c:
        c.execute("DELETE FROM a")
