"""SQLite storage: results, UI targets and last-known target state."""
import sqlite3
import threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      INTEGER NOT NULL,
  target  TEXT    NOT NULL,
  ok      INTEGER NOT NULL CHECK (ok IN (0,1)),
  latency_ms REAL,
  error   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_results_target_ts ON results(target, ts);
CREATE INDEX IF NOT EXISTS idx_results_ts ON results(ts);
CREATE TABLE IF NOT EXISTS ui_targets (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  name            TEXT NOT NULL UNIQUE COLLATE NOCASE,
  type            TEXT NOT NULL CHECK (type IN ('http','tcp')),
  url             TEXT,
  expected_status INTEGER,
  host            TEXT,
  port            INTEGER,
  interval        INTEGER NOT NULL CHECK (interval >= 5),
  paused          INTEGER NOT NULL DEFAULT 0,
  created_at      INTEGER NOT NULL,
  updated_at      INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS target_state (
  target TEXT PRIMARY KEY,
  state  TEXT NOT NULL CHECK (state IN ('up','down')),
  since  INTEGER NOT NULL
);
"""

_FIELDS = ("name", "type", "url", "expected_status", "host", "port", "interval")


class DatabaseError(Exception):
    pass


class Database:
    def __init__(self, path):
        self.path = path
        self._local = threading.local()
        try:
            c = self.conn()
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(SCHEMA)
            c.commit()
        except sqlite3.Error as e:
            raise DatabaseError("cannot open database: %s" % e) from None

    def conn(self):
        c = getattr(self._local, "c", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=10)
            c.row_factory = sqlite3.Row
            self._local.c = c
        return c

    # results
    def insert_result(self, ts, target, ok, latency_ms, error):
        c = self.conn()
        c.execute("INSERT INTO results(ts,target,ok,latency_ms,error) VALUES(?,?,?,?,?)",
                  (int(ts), target, 1 if ok else 0, latency_ms, error or ""))
        c.commit()

    def results_since(self, target, since_ts):
        return self.conn().execute(
            "SELECT * FROM results WHERE target=? AND ts>=? ORDER BY ts, id", (target, int(since_ts))).fetchall()

    def latest_result(self, target):
        return self.conn().execute(
            "SELECT * FROM results WHERE target=? ORDER BY ts DESC, id DESC LIMIT 1", (target,)).fetchone()

    def uptime_counts(self, target, since_ts):
        r = self.conn().execute(
            "SELECT COALESCE(SUM(ok),0) AS ok, COUNT(*) AS n FROM results WHERE target=? AND ts>=?",
            (target, int(since_ts))).fetchone()
        return r["ok"], r["n"]

    def prune(self, retention_days, now):
        c = self.conn()
        cur = c.execute("DELETE FROM results WHERE ts < ?", (int(now - retention_days * 86400),))
        c.commit()
        return cur.rowcount

    # ui targets
    def add_ui_target(self, f, now):
        c = self.conn()
        try:
            cur = c.execute(
                "INSERT INTO ui_targets(name,type,url,expected_status,host,port,interval,paused,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,0,?,?)",
                tuple(f.get(k) for k in _FIELDS) + (int(now), int(now)))
            c.commit()
        except sqlite3.IntegrityError:
            c.rollback()
            raise DatabaseError("duplicate name") from None
        return cur.lastrowid

    def update_ui_target(self, id_, f, now):
        c = self.conn()
        try:
            c.execute(
                "UPDATE ui_targets SET name=?,type=?,url=?,expected_status=?,host=?,port=?,interval=?,updated_at=?"
                " WHERE id=?", tuple(f.get(k) for k in _FIELDS) + (int(now), id_))
            c.commit()
        except sqlite3.IntegrityError:
            c.rollback()
            raise DatabaseError("duplicate name") from None

    def set_paused(self, id_, paused, now):
        c = self.conn()
        c.execute("UPDATE ui_targets SET paused=?, updated_at=? WHERE id=?", (1 if paused else 0, int(now), id_))
        c.commit()

    def get_ui_target(self, id_):
        return self.conn().execute("SELECT * FROM ui_targets WHERE id=?", (id_,)).fetchone()

    def list_ui_targets(self):
        return self.conn().execute("SELECT * FROM ui_targets ORDER BY id").fetchall()

    def count_ui_targets(self):
        return self.conn().execute("SELECT COUNT(*) FROM ui_targets").fetchone()[0]

    def delete_ui_target(self, id_):
        c = self.conn()
        row = c.execute("SELECT name FROM ui_targets WHERE id=?", (id_,)).fetchone()
        if row is None:
            return False
        c.execute("DELETE FROM ui_targets WHERE id=?", (id_,))
        c.execute("DELETE FROM target_state WHERE target=?", (row["name"],))
        c.commit()
        return True

    # state
    def get_state(self, target):
        return self.conn().execute("SELECT * FROM target_state WHERE target=?", (target,)).fetchone()

    def upsert_state(self, target, state, since):
        c = self.conn()
        c.execute("INSERT INTO target_state(target,state,since) VALUES(?,?,?) "
                  "ON CONFLICT(target) DO UPDATE SET state=excluded.state, since=excluded.since",
                  (target, state, int(since)))
        c.commit()
