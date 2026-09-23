"""
SQLite store for the command centre — Phase 10.

Extends the Phase 9 schema with new tables for:
  devices, teams, message_ack, alerts, node_events, missions,
  rover_telemetry, rover_commands, location_history.

Backward compatible: all Phase 9 tables are preserved as-is.
New tables are created via IF NOT EXISTS so the migration is safe
to run on an existing Phase 9 database.
"""

import sqlite3
import time
import json
import uuid
import threading

import config

# ---- Phase 9 original schema (unchanged) ----------------------------------
_SCHEMA_V9 = """
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
    ts REAL, id TEXT, code TEXT, lat REAL, lon REAL, team TEXT,
    description TEXT DEFAULT '', device_id TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS team_status (
    id TEXT PRIMARY KEY, team TEXT, state TEXT, ts REAL
);
CREATE TABLE IF NOT EXISTS raw_log (
    ts REAL, kind TEXT, data TEXT
);
CREATE TABLE IF NOT EXISTS rover_status (
    id TEXT PRIMARY KEY, mode TEXT, obstacle_cm INTEGER, battery_pct INTEGER, ts REAL
);
"""

# ---- Phase 10 new tables --------------------------------------------------
_SCHEMA_V10 = """
-- Device registry
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT DEFAULT '',
    type TEXT DEFAULT 'node',
    team_id TEXT DEFAULT '',
    registered_at REAL,
    last_seen REAL,
    config TEXT DEFAULT '{}'
);

-- Team registry
CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    name TEXT DEFAULT '',
    created_at REAL,
    status TEXT DEFAULT 'ACTIVE'
);

-- Message tracking with ACK support
CREATE TABLE IF NOT EXISTS message_ack (
    msg_id TEXT PRIMARY KEY,
    src TEXT NOT NULL,
    dest TEXT NOT NULL,
    text TEXT NOT NULL,
    priority INTEGER DEFAULT 3,
    status TEXT DEFAULT 'PENDING',
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at REAL,
    sent_at REAL,
    acked_at REAL,
    ack_by TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_msgack_status ON message_ack(status);
CREATE INDEX IF NOT EXISTS idx_msgack_dest ON message_ack(dest);

-- Central alert/event system
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    severity TEXT DEFAULT 'INFO',
    source TEXT DEFAULT '',
    message TEXT DEFAULT '',
    data TEXT DEFAULT '{}',
    created_at REAL,
    resolved_at REAL,
    resolved_by TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(type);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at);

-- Node event history
CREATE TABLE IF NOT EXISTS node_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    data TEXT DEFAULT '{}',
    created_at REAL
);
CREATE INDEX IF NOT EXISTS idx_nodeev_node ON node_events(node_id);

-- Mission management
CREATE TABLE IF NOT EXISTS missions (
    id TEXT PRIMARY KEY,
    name TEXT DEFAULT '',
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'PLANNED',
    assigned_teams TEXT DEFAULT '[]',
    assigned_rover TEXT DEFAULT '',
    target_lat REAL,
    target_lon REAL,
    area_radius_m REAL DEFAULT 0,
    created_at REAL,
    updated_at REAL,
    completed_at REAL
);

-- Rover telemetry history
CREATE TABLE IF NOT EXISTS rover_telemetry (
    ts REAL,
    rover_id TEXT,
    mode TEXT,
    lat REAL,
    lon REAL,
    target_lat REAL,
    target_lon REAL,
    distance_m REAL,
    bearing REAL,
    heading REAL,
    heading_error REAL,
    obstacle_cm INTEGER,
    battery_pct INTEGER,
    gps_fix INTEGER DEFAULT 0,
    state TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_rovertel_ts ON rover_telemetry(ts);

-- Rover command log
CREATE TABLE IF NOT EXISTS rover_commands (
    id TEXT PRIMARY KEY,
    rover_id TEXT,
    command TEXT,
    args TEXT DEFAULT '',
    status TEXT DEFAULT 'SENT',
    sent_at REAL,
    acked_at REAL
);

-- Location history (from Android phones and nodes)
CREATE TABLE IF NOT EXISTS location_history (
    ts REAL,
    device_id TEXT,
    team_id TEXT DEFAULT '',
    lat REAL,
    lon REAL,
    accuracy REAL DEFAULT 0,
    source TEXT DEFAULT 'unknown',
    battery INTEGER DEFAULT -1
);
CREATE INDEX IF NOT EXISTS idx_lochist_device ON location_history(device_id, ts);
CREATE INDEX IF NOT EXISTS idx_lochist_ts ON location_history(ts);
"""


class DB:
    def __init__(self, path=None):
        self._path = path or config.DB_PATH
        self._lock = threading.Lock()
        self._c = sqlite3.connect(self._path, check_same_thread=False)
        self._c.executescript(_SCHEMA_V9)
        self._c.executescript(_SCHEMA_V10)
        self._c.commit()

    def _run(self, sql, args=()):
        with self._lock:
            cur = self._c.execute(sql, args)
            self._c.commit()
            return cur

    def _query(self, sql, args=()):
        with self._lock:
            return self._c.execute(sql, args).fetchall()

    # =====================================================================
    # Phase 9 writers (preserved exactly)
    # =====================================================================
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

    def report(self, nid, code, lat, lon, team, description="", device_id=""):
        self._run("INSERT INTO reports(ts,id,code,lat,lon,team,description,device_id) VALUES(?,?,?,?,?,?,?,?)",
                  (time.time(), nid, code, lat, lon, team, description, device_id))

    def status(self, nid, team, state):
        self._run(
            """INSERT INTO team_status(id,team,state,ts) VALUES(?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET team=excluded.team,
                 state=excluded.state, ts=excluded.ts""",
            (nid, team, state, time.time()))

    def raw(self, kind, data):
        self._run("INSERT INTO raw_log(ts,kind,data) VALUES(?,?,?)",
                  (time.time(), kind, str(data)[:400]))

    def rover(self, nid, mode, obstacle_cm, battery_pct):
        self._run(
            """INSERT INTO rover_status(id,mode,obstacle_cm,battery_pct,ts)
               VALUES(?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET mode=excluded.mode,
                 obstacle_cm=excluded.obstacle_cm,
                 battery_pct=excluded.battery_pct, ts=excluded.ts""",
            (nid, mode, obstacle_cm, battery_pct, time.time()))

    # =====================================================================
    # Phase 9 readers (preserved)
    # =====================================================================
    def state(self):
        cur = self._c.execute("SELECT id,last_seen,rssi,snr,uptime,heap,online FROM nodes")
        nodes = [dict(zip(("id", "last_seen", "rssi", "snr", "uptime", "heap", "online"), r))
                 for r in cur.fetchall()]

        latest = {}
        for r in self._c.execute(
                "SELECT p.id, p.lat, p.lon, p.src, p.sats, p.ts FROM positions p "
                "JOIN (SELECT id, MAX(ts) AS mts FROM positions GROUP BY id) m "
                "ON m.id = p.id AND m.mts = p.ts"):
            latest[r[0]] = {"id": r[0], "lat": r[1], "lon": r[2],
                            "src": r[3], "sats": r[4], "ts": r[5]}

        trails = {}
        for r in self._c.execute(
                "SELECT id,lat,lon FROM positions WHERE ts > ? ORDER BY ts",
                (time.time() - config.POS_RETENTION_S,)):
            trails.setdefault(r[0], []).append([r[1], r[2]])

        sos_list = [dict(zip(("ts", "victim", "lat", "lon", "msg", "cleared"), r))
               for r in self._c.execute(
                   "SELECT ts,victim,lat,lon,msg,cleared FROM sos_events "
                   "ORDER BY ts DESC LIMIT 20")]

        msgs = [dict(zip(("ts", "src", "dest", "text", "direction"), r))
                for r in self._c.execute(
                    "SELECT ts,src,dest,text,direction FROM messages "
                    "ORDER BY ts DESC LIMIT 40")]

        rpts = [dict(zip(("ts", "id", "code", "lat", "lon", "team"), r))
                   for r in self._c.execute(
                       "SELECT ts,id,code,lat,lon,team FROM reports "
                       "ORDER BY ts DESC LIMIT 30")]

        status_list = [dict(zip(("id", "team", "state", "ts"), r))
                  for r in self._c.execute(
                      "SELECT id,team,state,ts FROM team_status ORDER BY id")]

        rover_list = [dict(zip(("id", "mode", "obstacle_cm", "battery_pct", "ts"), r))
                 for r in self._c.execute(
                     "SELECT id,mode,obstacle_cm,battery_pct,ts FROM rover_status")]

        return {"nodes": nodes, "positions": latest, "trails": trails,
                "sos": sos_list, "messages": msgs, "reports": rpts,
                "status": status_list, "rover": rover_list}

    # =====================================================================
    # Phase 10 NEW writers
    # =====================================================================

    # ---- devices ---------------------------------------------------------
    def device_register(self, dev_id, name="", dev_type="node", team_id="", dev_config=None):
        self._run(
            """INSERT INTO devices(id,name,type,team_id,registered_at,last_seen,config)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 name=COALESCE(NULLIF(excluded.name,''), devices.name),
                 type=excluded.type, team_id=excluded.team_id,
                 last_seen=excluded.last_seen,
                 config=COALESCE(excluded.config, devices.config)""",
            (dev_id, name, dev_type, team_id, time.time(), time.time(),
             json.dumps(dev_config or {})))

    def device_seen(self, dev_id):
        self._run("UPDATE devices SET last_seen=? WHERE id=?", (time.time(), dev_id))

    def devices_list(self):
        return [dict(zip(("id", "name", "type", "team_id", "registered_at", "last_seen", "config"), r))
                for r in self._query("SELECT id,name,type,team_id,registered_at,last_seen,config FROM devices ORDER BY id")]

    def device_get(self, dev_id):
        rows = self._query("SELECT id,name,type,team_id,registered_at,last_seen,config FROM devices WHERE id=?", (dev_id,))
        if not rows:
            return None
        return dict(zip(("id", "name", "type", "team_id", "registered_at", "last_seen", "config"), rows[0]))

    # ---- teams -----------------------------------------------------------
    def team_create(self, team_id, name=""):
        self._run(
            """INSERT INTO teams(id,name,created_at) VALUES(?,?,?)
               ON CONFLICT(id) DO UPDATE SET name=COALESCE(NULLIF(excluded.name,''), teams.name)""",
            (team_id, name, time.time()))

    def teams_list(self):
        return [dict(zip(("id", "name", "created_at", "status"), r))
                for r in self._query("SELECT id,name,created_at,status FROM teams ORDER BY id")]

    def team_get(self, team_id):
        rows = self._query("SELECT id,name,created_at,status FROM teams WHERE id=?", (team_id,))
        if not rows:
            return None
        return dict(zip(("id", "name", "created_at", "status"), rows[0]))

    # ---- message ACK tracking --------------------------------------------
    def msg_create(self, src, dest, text, priority=3):
        msg_id = str(uuid.uuid4())[:8]
        now = time.time()
        self._run(
            "INSERT INTO message_ack(msg_id,src,dest,text,priority,status,created_at,max_retries) VALUES(?,?,?,?,?,?,?,?)",
            (msg_id, src, dest, text, priority, "PENDING", now, config.MSG_MAX_RETRIES))
        return msg_id

    def msg_sent(self, msg_id):
        self._run("UPDATE message_ack SET status='SENT', sent_at=?, retry_count=retry_count+1 WHERE msg_id=?",
                  (time.time(), msg_id))

    def msg_acked(self, msg_id, ack_by=""):
        self._run("UPDATE message_ack SET status='ACKNOWLEDGED', acked_at=?, ack_by=? WHERE msg_id=?",
                  (time.time(), ack_by, msg_id))

    def msg_failed(self, msg_id):
        self._run("UPDATE message_ack SET status='FAILED' WHERE msg_id=?", (msg_id,))

    def msg_pending(self):
        return [dict(zip(("msg_id", "src", "dest", "text", "priority", "status",
                          "retry_count", "max_retries", "created_at", "sent_at"), r))
                for r in self._query(
                    "SELECT msg_id,src,dest,text,priority,status,retry_count,max_retries,created_at,sent_at "
                    "FROM message_ack WHERE status IN ('PENDING','SENT') ORDER BY priority, created_at")]

    def msg_list(self, limit=50):
        return [dict(zip(("msg_id", "src", "dest", "text", "priority", "status",
                          "retry_count", "created_at", "sent_at", "acked_at", "ack_by"), r))
                for r in self._query(
                    "SELECT msg_id,src,dest,text,priority,status,retry_count,created_at,sent_at,acked_at,ack_by "
                    "FROM message_ack ORDER BY created_at DESC LIMIT ?", (limit,))]

    def msg_get(self, msg_id):
        rows = self._query(
            "SELECT msg_id,src,dest,text,priority,status,retry_count,max_retries,created_at,sent_at,acked_at,ack_by "
            "FROM message_ack WHERE msg_id=?", (msg_id,))
        if not rows:
            return None
        return dict(zip(("msg_id", "src", "dest", "text", "priority", "status",
                         "retry_count", "max_retries", "created_at", "sent_at", "acked_at", "ack_by"), rows[0]))

    # ---- alerts ----------------------------------------------------------
    def alert_create(self, alert_type, severity="INFO", source="", message="", data=None):
        self._run(
            "INSERT INTO alerts(type,severity,source,message,data,created_at) VALUES(?,?,?,?,?,?)",
            (alert_type, severity, source, message, json.dumps(data or {}), time.time()))
        return self._c.execute("SELECT last_insert_rowid()").fetchone()[0]

    def alert_resolve(self, alert_id, resolved_by="system"):
        self._run("UPDATE alerts SET resolved_at=?, resolved_by=? WHERE id=? AND resolved_at IS NULL",
                  (time.time(), resolved_by, alert_id))

    def alerts_active(self):
        return [dict(zip(("id", "type", "severity", "source", "message", "data", "created_at"), r))
                for r in self._query(
                    "SELECT id,type,severity,source,message,data,created_at "
                    "FROM alerts WHERE resolved_at IS NULL ORDER BY created_at DESC LIMIT ?",
                    (config.ALERT_MAX_ACTIVE,))]

    def alerts_all(self, limit=100):
        return [dict(zip(("id", "type", "severity", "source", "message", "data",
                          "created_at", "resolved_at", "resolved_by"), r))
                for r in self._query(
                    "SELECT id,type,severity,source,message,data,created_at,resolved_at,resolved_by "
                    "FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,))]

    def alerts_recent_of_type(self, alert_type, source, window_s=None):
        """Check if an alert of this type+source was created recently (dedup)."""
        window = window_s or config.ALERT_DEDUP_WINDOW_S
        rows = self._query(
            "SELECT id FROM alerts WHERE type=? AND source=? AND resolved_at IS NULL "
            "AND created_at > ? LIMIT 1",
            (alert_type, source, time.time() - window))
        return len(rows) > 0

    # ---- node events -----------------------------------------------------
    def node_event(self, node_id, event_type, data=None):
        self._run("INSERT INTO node_events(node_id,event_type,data,created_at) VALUES(?,?,?,?)",
                  (node_id, event_type, json.dumps(data or {}), time.time()))

    def node_events_list(self, node_id=None, limit=50):
        if node_id:
            return [dict(zip(("id", "node_id", "event_type", "data", "created_at"), r))
                    for r in self._query(
                        "SELECT id,node_id,event_type,data,created_at FROM node_events "
                        "WHERE node_id=? ORDER BY created_at DESC LIMIT ?", (node_id, limit))]
        return [dict(zip(("id", "node_id", "event_type", "data", "created_at"), r))
                for r in self._query(
                    "SELECT id,node_id,event_type,data,created_at FROM node_events "
                    "ORDER BY created_at DESC LIMIT ?", (limit,))]

    # ---- missions --------------------------------------------------------
    def mission_create(self, mission_id, name="", description="", teams=None,
                       rover="", target_lat=0, target_lon=0, radius=0):
        now = time.time()
        self._run(
            "INSERT INTO missions(id,name,description,status,assigned_teams,assigned_rover,"
            "target_lat,target_lon,area_radius_m,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (mission_id, name, description, "PLANNED", json.dumps(teams or []),
             rover, target_lat, target_lon, radius, now, now))

    def mission_update(self, mission_id, **kwargs):
        allowed = {"name", "description", "status", "assigned_teams", "assigned_rover",
                   "target_lat", "target_lon", "area_radius_m"}
        sets = []
        vals = []
        for k, v in kwargs.items():
            if k in allowed:
                if k == "assigned_teams" and isinstance(v, list):
                    v = json.dumps(v)
                sets.append(f"{k}=?")
                vals.append(v)
        if not sets:
            return
        sets.append("updated_at=?")
        vals.append(time.time())
        if kwargs.get("status") in ("COMPLETED", "CANCELLED"):
            sets.append("completed_at=?")
            vals.append(time.time())
        vals.append(mission_id)
        self._run(f"UPDATE missions SET {','.join(sets)} WHERE id=?", vals)

    def missions_list(self, status=None):
        if status:
            return [self._mission_row(r) for r in self._query(
                "SELECT * FROM missions WHERE status=? ORDER BY created_at DESC", (status,))]
        return [self._mission_row(r) for r in self._query(
            "SELECT * FROM missions ORDER BY created_at DESC")]

    def mission_get(self, mission_id):
        rows = self._query("SELECT * FROM missions WHERE id=?", (mission_id,))
        return self._mission_row(rows[0]) if rows else None

    def _mission_row(self, r):
        cols = ("id", "name", "description", "status", "assigned_teams", "assigned_rover",
                "target_lat", "target_lon", "area_radius_m", "created_at", "updated_at", "completed_at")
        d = dict(zip(cols, r))
        try:
            d["assigned_teams"] = json.loads(d["assigned_teams"])
        except (json.JSONDecodeError, TypeError):
            d["assigned_teams"] = []
        return d

    # ---- rover telemetry history -----------------------------------------
    def rover_telemetry(self, rover_id, mode, lat, lon, target_lat, target_lon,
                        distance_m, bearing, heading, heading_error,
                        obstacle_cm, battery_pct, gps_fix, state=""):
        self._run(
            "INSERT INTO rover_telemetry(ts,rover_id,mode,lat,lon,target_lat,target_lon,"
            "distance_m,bearing,heading,heading_error,obstacle_cm,battery_pct,gps_fix,state) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (time.time(), rover_id, mode, lat, lon, target_lat, target_lon,
             distance_m, bearing, heading, heading_error,
             obstacle_cm, battery_pct, gps_fix, state))

    def rover_telemetry_history(self, rover_id=None, limit=100):
        if rover_id:
            return [dict(zip(("ts", "rover_id", "mode", "lat", "lon", "target_lat", "target_lon",
                              "distance_m", "bearing", "heading", "heading_error",
                              "obstacle_cm", "battery_pct", "gps_fix", "state"), r))
                    for r in self._query(
                        "SELECT ts,rover_id,mode,lat,lon,target_lat,target_lon,"
                        "distance_m,bearing,heading,heading_error,obstacle_cm,battery_pct,gps_fix,state "
                        "FROM rover_telemetry WHERE rover_id=? ORDER BY ts DESC LIMIT ?", (rover_id, limit))]
        return [dict(zip(("ts", "rover_id", "mode", "lat", "lon", "target_lat", "target_lon",
                          "distance_m", "bearing", "heading", "heading_error",
                          "obstacle_cm", "battery_pct", "gps_fix", "state"), r))
                for r in self._query(
                    "SELECT ts,rover_id,mode,lat,lon,target_lat,target_lon,"
                    "distance_m,bearing,heading,heading_error,obstacle_cm,battery_pct,gps_fix,state "
                    "FROM rover_telemetry ORDER BY ts DESC LIMIT ?", (limit,))]

    # ---- rover commands --------------------------------------------------
    def rover_cmd_log(self, rover_id, command, args=""):
        cmd_id = str(uuid.uuid4())[:8]
        self._run("INSERT INTO rover_commands(id,rover_id,command,args,status,sent_at) VALUES(?,?,?,?,?,?)",
                  (cmd_id, rover_id, command, args, "SENT", time.time()))
        return cmd_id

    def rover_cmd_ack(self, cmd_id):
        self._run("UPDATE rover_commands SET status='ACKED', acked_at=? WHERE id=?",
                  (time.time(), cmd_id))

    def rover_cmds_list(self, rover_id=None, limit=30):
        if rover_id:
            return [dict(zip(("id", "rover_id", "command", "args", "status", "sent_at", "acked_at"), r))
                    for r in self._query(
                        "SELECT id,rover_id,command,args,status,sent_at,acked_at "
                        "FROM rover_commands WHERE rover_id=? ORDER BY sent_at DESC LIMIT ?", (rover_id, limit))]
        return [dict(zip(("id", "rover_id", "command", "args", "status", "sent_at", "acked_at"), r))
                for r in self._query(
                    "SELECT id,rover_id,command,args,status,sent_at,acked_at "
                    "FROM rover_commands ORDER BY sent_at DESC LIMIT ?", (limit,))]

    # ---- location history ------------------------------------------------
    def location_add(self, device_id, lat, lon, accuracy=0, source="unknown",
                     team_id="", battery=-1):
        self._run(
            "INSERT INTO location_history(ts,device_id,team_id,lat,lon,accuracy,source,battery) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (time.time(), device_id, team_id, lat, lon, accuracy, source, battery))

    def location_history(self, device_id=None, since=None, limit=200):
        since = since or (time.time() - 3600)
        if device_id:
            return [dict(zip(("ts", "device_id", "team_id", "lat", "lon", "accuracy", "source", "battery"), r))
                    for r in self._query(
                        "SELECT ts,device_id,team_id,lat,lon,accuracy,source,battery "
                        "FROM location_history WHERE device_id=? AND ts>? ORDER BY ts DESC LIMIT ?",
                        (device_id, since, limit))]
        return [dict(zip(("ts", "device_id", "team_id", "lat", "lon", "accuracy", "source", "battery"), r))
                for r in self._query(
                    "SELECT ts,device_id,team_id,lat,lon,accuracy,source,battery "
                    "FROM location_history WHERE ts>? ORDER BY ts DESC LIMIT ?",
                    (since, limit))]

    def location_latest(self):
        """Latest location per device (for map display)."""
        result = {}
        for r in self._query(
                "SELECT lh.device_id, lh.team_id, lh.lat, lh.lon, lh.accuracy, lh.source, lh.battery, lh.ts "
                "FROM location_history lh "
                "JOIN (SELECT device_id, MAX(ts) AS mts FROM location_history GROUP BY device_id) m "
                "ON m.device_id = lh.device_id AND m.mts = lh.ts"):
            result[r[0]] = {"device_id": r[0], "team_id": r[1], "lat": r[2], "lon": r[3],
                            "accuracy": r[4], "source": r[5], "battery": r[6], "ts": r[7]}
        return result

    # =====================================================================
    # Phase 10 extended state (adds alerts, missions to /api/state)
    # =====================================================================
    def state_v10(self):
        """Extended state for Phase 10 dashboard."""
        st = self.state()
        st["alerts"] = self.alerts_active()
        st["missions"] = self.missions_list()
        st["phone_locations"] = self.location_latest()
        return st

    # =====================================================================
    # Housekeeping (extended retention)
    # =====================================================================
    def trim(self):
        now = time.time()
        with self._lock:
            self._c.execute("DELETE FROM positions WHERE ts < ?",
                            (now - config.POS_RETENTION_S,))
            self._c.execute("DELETE FROM messages  WHERE ts < ?",
                            (now - config.MSG_RETENTION_S,))
            self._c.execute("DELETE FROM reports   WHERE ts < ?",
                            (now - config.RPT_RETENTION_S,))
            self._c.execute("DELETE FROM raw_log   WHERE ts < ?",
                            (now - config.RAW_RETENTION_S,))
            self._c.execute("DELETE FROM alerts WHERE resolved_at IS NOT NULL AND created_at < ?",
                            (now - config.ALERT_RETENTION_S,))
            self._c.execute("DELETE FROM rover_telemetry WHERE ts < ?",
                            (now - config.TELEMETRY_RETENTION_S,))
            self._c.execute("DELETE FROM location_history WHERE ts < ?",
                            (now - config.LOC_HISTORY_RETENTION_S,))
            self._c.execute("DELETE FROM node_events WHERE created_at < ?",
                            (now - config.ALERT_RETENTION_S,))
            self._c.commit()
