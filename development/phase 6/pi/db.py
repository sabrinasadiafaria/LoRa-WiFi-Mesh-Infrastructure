"""
SQLite store for the command centre. One file, created on first run.

Everything the mesh reports is appended here so the dashboard survives a
reboot and there is a record for the post-mission report.
"""

import sqlite3
import time
import threading

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id        TEXT PRIMARY KEY,
    last_seen REAL,
    rssi      INTEGER,
    snr       REAL,
    uptime    INTEGER,
    heap      INTEGER,
    online    INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS positions (
    ts   REAL, id TEXT, lat REAL, lon REAL, src INTEGER, sats INTEGER
);
CREATE INDEX IF NOT EXISTS idx_pos_id_ts ON positions(id, ts);
CREATE TABLE IF NOT EXISTS messages (
    ts REAL, src TEXT, dest TEXT, text TEXT, direction TEXT
);
CREATE TABLE IF NOT EXISTS sos_events (
    ts REAL, victim TEXT, lat REAL, lon REAL, msg TEXT, cleared INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS reports (
    ts REAL, id TEXT, code TEXT, lat REAL, lon REAL, team TEXT
);
CREATE TABLE IF NOT EXISTS team_status (
    id TEXT PRIMARY KEY, team TEXT, state TEXT, ts REAL
);
CREATE TABLE IF NOT EXISTS raw_log (
    ts REAL, kind TEXT, data TEXT
);
"""


class DB:
    def __init__(self, path="sar.db"):
        self._path = path
        self._lock = threading.Lock()
        self._c = sqlite3.connect(path, check_same_thread=False)
        self._c.executescript(_SCHEMA)
        self._c.commit()

    def _run(self, sql, args=()):
        with self._lock:
            cur = self._c.execute(sql, args)
            self._c.commit()
            return cur

    # ---- writers -----------------------------------------------------
    def node_seen(self, nid, rssi=None, snr=None, uptime=None, heap=None, online=1):
        self._run(
            """INSERT INTO nodes(id,last_seen,rssi,snr,uptime,heap,online)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 last_seen=excluded.last_seen,
                 rssi=COALESCE(excluded.rssi, nodes.rssi),
                 snr=COALESCE(excluded.snr, nodes.snr),
                 uptime=COALESCE(excluded.uptime, nodes.uptime),
                 heap=COALESCE(excluded.heap, nodes.heap),
                 online=excluded.online""",
            (nid, time.time(), rssi, snr, uptime, heap, online))

    def node_offline(self, nid):
        self._run("UPDATE nodes SET online=0 WHERE id=?", (nid,))

    def position(self, nid, lat, lon, src=0, sats=0):
        self._run("INSERT INTO positions(ts,id,lat,lon,src,sats) VALUES(?,?,?,?,?,?)",
                  (time.time(), nid, lat, lon, src, sats))

    def message(self, src, dest, text, direction):
        self._run("INSERT INTO messages(ts,src,dest,text,direction) VALUES(?,?,?,?,?)",
                  (time.time(), src, dest, text, direction))

    def sos(self, victim, lat, lon, msg):
        self._run("INSERT INTO sos_events(ts,victim,lat,lon,msg) VALUES(?,?,?,?,?)",
                  (time.time(), victim, lat, lon, msg))

    def sos_clear(self, victim):
        self._run("UPDATE sos_events SET cleared=1 WHERE victim=? AND cleared=0", (victim,))

    def report(self, nid, code, lat, lon, team):
        self._run("INSERT INTO reports(ts,id,code,lat,lon,team) VALUES(?,?,?,?,?,?)",
                  (time.time(), nid, code, lat, lon, team))

    def status(self, nid, team, state):
        self._run(
            """INSERT INTO team_status(id,team,state,ts) VALUES(?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET team=excluded.team,
                 state=excluded.state, ts=excluded.ts""",
            (nid, team, state, time.time()))

    def raw(self, kind, data):
        self._run("INSERT INTO raw_log(ts,kind,data) VALUES(?,?,?)",
                  (time.time(), kind, str(data)[:400]))

    # ---- readers for the dashboard --------------------------------
    def state(self):
        cur = self._c.execute("SELECT id,last_seen,rssi,snr,uptime,heap,online FROM nodes")
        nodes = [dict(zip(("id", "last_seen", "rssi", "snr", "uptime", "heap", "online"), r))
                 for r in cur.fetchall()]

        latest = {}
        for r in self._c.execute(
                "SELECT id,lat,lon,src,sats,ts FROM positions ORDER BY ts"):
            latest[r[0]] = {"id": r[0], "lat": r[1], "lon": r[2],
                            "src": r[3], "sats": r[4], "ts": r[5]}

        trails = {}
        for r in self._c.execute(
                "SELECT id,lat,lon FROM positions WHERE ts > ? ORDER BY ts",
                (time.time() - 1800,)):
            trails.setdefault(r[0], []).append([r[1], r[2]])

        sos = [dict(zip(("ts", "victim", "lat", "lon", "msg", "cleared"), r))
               for r in self._c.execute(
                   "SELECT ts,victim,lat,lon,msg,cleared FROM sos_events "
                   "ORDER BY ts DESC LIMIT 20")]

        msgs = [dict(zip(("ts", "src", "dest", "text", "direction"), r))
                for r in self._c.execute(
                    "SELECT ts,src,dest,text,direction FROM messages "
                    "ORDER BY ts DESC LIMIT 40")]

        reports = [dict(zip(("ts", "id", "code", "lat", "lon", "team"), r))
                   for r in self._c.execute(
                       "SELECT ts,id,code,lat,lon,team FROM reports "
                       "ORDER BY ts DESC LIMIT 30")]

        status = [dict(zip(("id", "team", "state", "ts"), r))
                  for r in self._c.execute(
                      "SELECT id,team,state,ts FROM team_status ORDER BY id")]

        return {"nodes": nodes, "positions": latest, "trails": trails,
                "sos": sos, "messages": msgs, "reports": reports, "status": status}
