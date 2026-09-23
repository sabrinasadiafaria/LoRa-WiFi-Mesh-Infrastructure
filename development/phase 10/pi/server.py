"""
Flask app: the command-centre dashboard + JSON API + live event stream — Phase 10.

Preserves ALL Phase 9 routes and adds new endpoints for:
  /api/auth, /api/devices, /api/teams, /api/location, /api/messages/*,
  /api/alerts, /api/events/history, /api/nodes, /api/missions,
  /api/rover/*, /api/reports (enhanced), /api/sos (enhanced)

Existing routes from Phase 9 are UNCHANGED so the captive portal and
the existing dashboard continue to work without modification.
"""

import json
import queue
import threading
import time
import logging
from flask import Flask, Response, request, jsonify, send_from_directory

import config
from auth import require_auth, auth_route

app = Flask(__name__, static_folder="dashboard", static_url_path="")

log = logging.getLogger("server")

# set by main.py
MESH = None
DB = None
HEALTH = None
ALERTS = None
MESSAGES = None
MISSIONS = None
ROVER = None

_subscribers = []
_sub_lock = threading.Lock()


def publish(kind, data):
    msg = json.dumps({"kind": kind, "data": data, "ts": time.time()})
    with _sub_lock:
        subs = list(_subscribers)
    for q in subs:
        try:
            q.put_nowait(msg)
        except queue.Full:
            pass


# ===================================================================
# Phase 9 routes (PRESERVED EXACTLY)
# ===================================================================

@app.route("/")
def index():
    return send_from_directory("dashboard", "index.html")


@app.route("/portal")
@app.route("/portal/")
def portal():
    return send_from_directory("dashboard", "portal.html")


@app.route("/api/state")
def api_state():
    st = DB.state_v10()  # Phase 10: extended state
    st["mesh"] = MESH.snapshot()
    st["now"] = time.time()
    # Add health and rover snapshots
    if HEALTH:
        st["node_health"] = HEALTH.snapshot()
    if ROVER:
        st["rover_detail"] = ROVER.snapshot()
    return jsonify(st)


@app.route("/api/events")
def api_events():
    q = queue.Queue(maxsize=200)
    with _sub_lock:
        _subscribers.append(q)

    def stream():
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    msg = q.get(timeout=15)
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            with _sub_lock:
                if q in _subscribers:
                    _subscribers.remove(q)

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


def _safe_dest(s):
    if not s:
        return None
    s = s.strip().upper()
    if len(s) > 4:
        return None
    for ch in s:
        if not (ch.isalnum() or ch == "*"):
            return None
    return s


def _safe_text(s, maxlen=120):
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    for bad in ("|", "\\", "\r", "\n"):
        s = s.replace(bad, "/")
    return s[:maxlen]


@app.route("/api/send", methods=["POST"])
def api_send():
    body = request.get_json(force=True, silent=True) or {}
    dest = _safe_dest(body.get("dest", ""))
    text = _safe_text(body.get("text", ""))
    if not dest or not text:
        return jsonify(ok=False, error="dest and text required"), 400
    if dest not in {"A", "B", "C", "R", "*"}:
        return jsonify(ok=False, error="dest must be A/B/C/R/*"), 400
    MESH.send_data(dest, text)
    DB.message("PI", dest, text, "out")
    publish("message", {"src": "PI", "dest": dest, "text": text, "direction": "out"})
    return jsonify(ok=True)


# ---- Pi-side captive portal endpoints (PRESERVED) ---------------------

@app.route("/api/sos", methods=["GET", "POST"])
def api_sos():
    """SOS endpoint — enhanced for Phase 10 (accepts more fields)."""
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
    else:
        body = {}

    victim = body.get("device_id", "PHONE")
    lat = _safe_float(body.get("lat", body.get("latitude", 0)))
    lon = _safe_float(body.get("lon", body.get("longitude", 0)))
    msg = str(body.get("msg", body.get("message", "PORTAL")))[:200]
    team = body.get("team_id", "")
    accuracy = _safe_float(body.get("accuracy", 0))
    battery = _safe_int(body.get("battery", -1))

    DB.sos(victim, lat, lon, msg)
    publish("sos", {"victim": victim, "lat": lat, "lon": lon, "msg": msg,
                    "team": team, "accuracy": accuracy, "battery": battery})

    # Generate alert
    if ALERTS:
        ALERTS.create("SOS", source=victim,
                      message=f"SOS from {victim}: {msg}",
                      severity="EMERGENCY",
                      data={"lat": lat, "lon": lon, "team": team, "battery": battery})

    return jsonify(ok=True)


@app.route("/api/loc", methods=["GET", "POST"])
def api_loc():
    try:
        if request.method == "GET":
            lat = float(request.args.get("lat", ""))
            lon = float(request.args.get("lon", ""))
        else:
            body = request.get_json(force=True, silent=True) or {}
            lat = float(body.get("lat", body.get("latitude", "")))
            lon = float(body.get("lon", body.get("longitude", "")))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="bad lat/lon"), 400
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify(ok=False, error="lat/lon out of range"), 400
    DB.position("PHONE", lat, lon, src=2, sats=0)
    publish("pos", {"id": "PHONE", "lat": lat, "lon": lon, "src": 2, "sats": 0})
    return jsonify(ok=True)


@app.route("/api/report", methods=["GET", "POST"])
def api_report():
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
        code = str(body.get("code", "")).strip().upper()
        lat = _safe_float(body.get("lat", body.get("latitude", 0)))
        lon = _safe_float(body.get("lon", body.get("longitude", 0)))
        team = str(body.get("team", body.get("team_id", "?")))[:8]
        description = str(body.get("description", ""))[:500]
        device_id = str(body.get("device_id", "PHONE"))
    else:
        code = (request.args.get("code") or "").strip().upper()
        lat = 0.0
        lon = 0.0
        team = "?"
        description = ""
        device_id = "PHONE"

    valid_codes = {"VICTIM_FOUND", "MEDICAL", "BLOCKED", "DANGER",
                   "HAZARD", "SUPPLIES_REQUIRED", "AREA_CLEAR", "OTHER"}
    if code not in valid_codes:
        return jsonify(ok=False, error=f"bad report code, must be one of: {','.join(sorted(valid_codes))}"), 400

    DB.report(device_id, code, lat, lon, team, description, device_id)
    publish("report", {"id": device_id, "code": code, "lat": lat, "lon": lon,
                       "team": team, "description": description})
    return jsonify(ok=True)


@app.route("/api/rescan", methods=["GET", "POST"])
def api_rescan():
    return jsonify(ok=True, message="no radio to rescan from the gateway")


DEST_VERBS = {
    "A": {"WHERE", "SOS", "SOSCLR", "PING"},
    "B": {"WHERE", "SOS", "SOSCLR", "PING"},
    "C": {"WHERE", "SOS", "SOSCLR", "PING"},
    "*": {"WHERE", "SOS", "SOSCLR", "PING"},
    "R": {"WHERE", "SOS", "SOSCLR", "PING",
          "FWD", "BACK", "LEFT", "RIGHT", "STOP", "MODE",
          "GOTO", "GOCLR"},
}
MODE_ARGS = {"MANUAL", "AUTO", "RELAY"}

VALID_STATES = {"AVAILABLE", "SEARCHING", "NEED_ASSIST", "VICTIM_FOUND", "EMERGENCY",
                "SAFE", "MOVING", "RESTING", "RETURNING", "INJURED"}


@app.route("/api/teamstatus", methods=["GET", "POST"])
def api_teamstatus():
    if request.method == "GET":
        st_arg = request.args.get("state", "")
    else:
        body = request.get_json(force=True, silent=True) or {}
        st_arg = body.get("state", "")
    st = (st_arg or "").strip().upper()
    if st not in VALID_STATES:
        return jsonify(ok=False, error="unknown state"), 400
    device_id = request.args.get("device_id") or "PHONE"
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
        device_id = body.get("device_id", device_id)
    DB.status(device_id, "?", st)
    publish("status", {"id": device_id, "team": "?", "state": st})
    return jsonify(ok=True)


@app.route("/api/team", methods=["GET", "POST"])
def api_team():
    if request.method == "GET":
        team = request.args.get("team", "")
    else:
        body = request.get_json(force=True, silent=True) or {}
        team = body.get("team", "")
    team = (team or "").strip().upper()[:8]
    if not team or not team[0].isalnum():
        return jsonify(ok=False, error="bad team"), 400
    DB.status("PHONE", team, "AVAILABLE")
    DB.team_create(team)
    publish("status", {"id": "PHONE", "team": team, "state": "AVAILABLE"})
    return jsonify(ok=True)


@app.route("/api/command", methods=["POST"])
def api_command():
    body = request.get_json(force=True, silent=True) or {}
    dest = _safe_dest(body.get("dest", ""))
    verb = (body.get("verb") or "").strip().upper()
    if verb == "GOTO":
        raw = (body.get("arg") or "").strip()
        ok, err, normalised = _validate_goto(raw)
        if not ok:
            return jsonify(ok=False, error=err), 400
        MESH.send_cmd(dest, "GOTO", normalised)
        DB.raw("cmd_out", f"{dest} GOTO {normalised}")
        if ROVER:
            parts = normalised.split(",")
            lat = int(parts[0]) / 1e6
            lon = int(parts[1]) / 1e6
            DB.rover_cmd_log(config.ROVER_ID, "GOTO", normalised)
        publish("command", {"dest": dest, "verb": "GOTO", "arg": normalised})
        return jsonify(ok=True)
    arg = (body.get("arg") or "").strip().upper()
    if not dest or dest not in DEST_VERBS or verb not in DEST_VERBS[dest]:
        return jsonify(ok=False, error="bad dest or verb"), 400
    if verb == "MODE" and arg not in MODE_ARGS:
        return jsonify(ok=False, error="MODE arg must be MANUAL/AUTO/RELAY"), 400
    if len(arg) > 12:
        return jsonify(ok=False, error="arg too long"), 400
    MESH.send_cmd(dest, verb, arg)
    DB.raw("cmd_out", f"{dest} {verb} {arg}")
    publish("command", {"dest": dest, "verb": verb, "arg": arg})
    return jsonify(ok=True)


def _validate_goto(raw: str):
    if not raw or "," not in raw:
        return False, "GOTO arg must be 'lat,lon'", ""
    a, _, b = raw.partition(",")
    try:
        la = float(a); lo = float(b)
    except ValueError:
        return False, "GOTO arg must be numeric", ""
    if not (-90.0 <= la <= 90.0 and -180.0 <= lo <= 180.0):
        return False, "GOTO arg out of range", ""
    return True, "", f"{int(round(la * 1e6))},{int(round(lo * 1e6))}"


@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def tile(z, x, y):
    return send_from_directory("dashboard/tiles", f"{z}/{x}/{y}.png")


# ===================================================================
# Phase 10 NEW API routes
# ===================================================================

# ---- Authentication --------------------------------------------------

@app.route("/api/auth", methods=["POST"])
def api_auth():
    return auth_route()


# ---- Devices ---------------------------------------------------------

@app.route("/api/devices", methods=["GET", "POST"])
def api_devices():
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
        dev_id = str(body.get("id", body.get("device_id", ""))).strip()
        if not dev_id:
            return jsonify(ok=False, error="device id required"), 400
        DB.device_register(
            dev_id,
            name=str(body.get("name", "")),
            dev_type=str(body.get("type", "phone")),
            team_id=str(body.get("team_id", "")),
        )
        return jsonify(ok=True, device=DB.device_get(dev_id))
    return jsonify(ok=True, devices=DB.devices_list())


@app.route("/api/devices/<dev_id>", methods=["GET"])
def api_device_detail(dev_id):
    d = DB.device_get(dev_id)
    if not d:
        return jsonify(ok=False, error="not found"), 404
    return jsonify(ok=True, device=d)


# ---- Teams -----------------------------------------------------------

@app.route("/api/teams", methods=["GET", "POST"])
def api_teams():
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
        team_id = str(body.get("id", body.get("team_id", ""))).strip().upper()
        if not team_id:
            return jsonify(ok=False, error="team id required"), 400
        DB.team_create(team_id, name=str(body.get("name", "")))
        return jsonify(ok=True, team=DB.team_get(team_id))
    return jsonify(ok=True, teams=DB.teams_list())


@app.route("/api/teams/<team_id>", methods=["GET"])
def api_team_detail(team_id):
    t = DB.team_get(team_id)
    if not t:
        return jsonify(ok=False, error="not found"), 404
    return jsonify(ok=True, team=t)


# ---- Location (from Android phones) ----------------------------------

@app.route("/api/location", methods=["POST"])
def api_location():
    body = request.get_json(force=True, silent=True) or {}
    device_id = str(body.get("device_id", "")).strip()
    lat = _safe_float(body.get("latitude", body.get("lat")))
    lon = _safe_float(body.get("longitude", body.get("lon")))
    if lat is None or lon is None:
        return jsonify(ok=False, error="latitude and longitude required"), 400
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify(ok=False, error="coordinates out of range"), 400
    if not device_id:
        return jsonify(ok=False, error="device_id required"), 400

    accuracy = _safe_float(body.get("accuracy", 0))
    team_id = str(body.get("team_id", ""))
    battery = _safe_int(body.get("battery", -1))
    source = str(body.get("source", "phone_native"))

    DB.location_add(device_id, lat, lon, accuracy, source, team_id, battery)
    DB.position(device_id, lat, lon, src=2, sats=0)
    DB.device_register(device_id, dev_type="phone", team_id=team_id)
    DB.device_seen(device_id)

    publish("pos", {"id": device_id, "lat": lat, "lon": lon, "src": 2,
                    "sats": 0, "accuracy": accuracy, "team": team_id})
    return jsonify(ok=True)


@app.route("/api/location/history", methods=["GET"])
def api_location_history():
    device_id = request.args.get("device_id")
    since = _safe_float(request.args.get("since"))
    limit = _safe_int(request.args.get("limit", "200"))
    data = DB.location_history(device_id, since, limit)
    return jsonify(ok=True, locations=data)


# ---- Messages (with ACK tracking) ------------------------------------

@app.route("/api/messages", methods=["GET"])
def api_messages():
    limit = _safe_int(request.args.get("limit", "50"))
    if MESSAGES:
        return jsonify(ok=True, messages=MESSAGES.list_messages(limit))
    return jsonify(ok=True, messages=[])


@app.route("/api/messages/send", methods=["POST"])
def api_messages_send():
    body = request.get_json(force=True, silent=True) or {}
    dest = _safe_dest(body.get("dest", ""))
    text = _safe_text(body.get("text", ""))
    src = str(body.get("src", "PI"))
    priority = _safe_int(body.get("priority", "3"))

    if not dest or not text:
        return jsonify(ok=False, error="dest and text required"), 400
    if not MESSAGES:
        return jsonify(ok=False, error="message system not available"), 500

    msg_id = MESSAGES.send(src, dest, text, priority)
    return jsonify(ok=True, msg_id=msg_id)


@app.route("/api/messages/<msg_id>/ack", methods=["POST"])
def api_messages_ack(msg_id):
    body = request.get_json(force=True, silent=True) or {}
    ack_by = str(body.get("ack_by", ""))
    if MESSAGES:
        MESSAGES.ack_received(msg_id, ack_by)
    return jsonify(ok=True)


# ---- Alerts -----------------------------------------------------------

@app.route("/api/alerts", methods=["GET"])
def api_alerts():
    active_only = request.args.get("active", "").lower() in ("1", "true", "yes")
    limit = _safe_int(request.args.get("limit", "100"))
    if ALERTS:
        if active_only:
            return jsonify(ok=True, alerts=ALERTS.active())
        return jsonify(ok=True, alerts=ALERTS.history(limit))
    return jsonify(ok=True, alerts=[])


@app.route("/api/alerts/<int:alert_id>/resolve", methods=["POST"])
def api_alert_resolve(alert_id):
    body = request.get_json(force=True, silent=True) or {}
    resolved_by = str(body.get("resolved_by", "operator"))
    if ALERTS:
        ALERTS.resolve(alert_id, resolved_by)
    return jsonify(ok=True)


# ---- Events (node events history) ------------------------------------

@app.route("/api/events/history", methods=["GET"])
def api_events_history():
    node_id = request.args.get("node_id")
    limit = _safe_int(request.args.get("limit", "50"))
    data = DB.node_events_list(node_id, limit)
    return jsonify(ok=True, events=data)


# ---- Nodes (health + detail) ------------------------------------------

@app.route("/api/nodes", methods=["GET"])
def api_nodes():
    nodes = []
    for r in DB._query("SELECT id,last_seen,rssi,snr,uptime,heap,online FROM nodes"):
        n = dict(zip(("id", "last_seen", "rssi", "snr", "uptime", "heap", "online"), r))
        if HEALTH:
            h = HEALTH.node_detail(n["id"])
            if h:
                n["health"] = h
        nodes.append(n)
    return jsonify(ok=True, nodes=nodes)


@app.route("/api/nodes/<node_id>", methods=["GET"])
def api_node_detail(node_id):
    rows = DB._query("SELECT id,last_seen,rssi,snr,uptime,heap,online FROM nodes WHERE id=?", (node_id,))
    if not rows:
        return jsonify(ok=False, error="not found"), 404
    n = dict(zip(("id", "last_seen", "rssi", "snr", "uptime", "heap", "online"), rows[0]))
    if HEALTH:
        n["health"] = HEALTH.node_detail(node_id)
    n["events"] = DB.node_events_list(node_id, 20)
    return jsonify(ok=True, node=n)


# ---- Missions ---------------------------------------------------------

@app.route("/api/missions", methods=["GET", "POST"])
def api_missions():
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
        if not MISSIONS:
            return jsonify(ok=False, error="mission system not available"), 500
        m = MISSIONS.create(
            name=str(body.get("name", "")),
            description=str(body.get("description", "")),
            teams=body.get("teams", body.get("assigned_teams", [])),
            rover=str(body.get("rover", body.get("assigned_rover", ""))),
            target_lat=_safe_float(body.get("target_lat", 0)),
            target_lon=_safe_float(body.get("target_lon", 0)),
            radius=_safe_float(body.get("radius", body.get("area_radius_m", 0))),
        )
        return jsonify(ok=True, mission=m)
    status = request.args.get("status")
    if MISSIONS:
        return jsonify(ok=True, missions=MISSIONS.list_all(status))
    return jsonify(ok=True, missions=[])


@app.route("/api/missions/<mission_id>", methods=["GET", "PUT", "DELETE"])
def api_mission_detail(mission_id):
    if not MISSIONS:
        return jsonify(ok=False, error="mission system not available"), 500
    if request.method == "GET":
        m = MISSIONS.get(mission_id)
        if not m:
            return jsonify(ok=False, error="not found"), 404
        return jsonify(ok=True, mission=m)
    elif request.method == "PUT":
        body = request.get_json(force=True, silent=True) or {}
        m = MISSIONS.update(mission_id, **body)
        if not m:
            return jsonify(ok=False, error="not found"), 404
        return jsonify(ok=True, mission=m)
    elif request.method == "DELETE":
        MISSIONS.cancel(mission_id)
        return jsonify(ok=True)


# ---- Rover (enhanced) ------------------------------------------------

@app.route("/api/rover/status", methods=["GET"])
def api_rover_status():
    if ROVER:
        return jsonify(ok=True, rover=ROVER.snapshot())
    return jsonify(ok=True, rover={})


@app.route("/api/rover/telemetry", methods=["GET"])
def api_rover_telemetry():
    limit = _safe_int(request.args.get("limit", "50"))
    data = DB.rover_telemetry_history(config.ROVER_ID, limit)
    return jsonify(ok=True, telemetry=data)


@app.route("/api/rover/goto", methods=["POST"])
def api_rover_goto():
    body = request.get_json(force=True, silent=True) or {}
    lat = _safe_float(body.get("lat", body.get("latitude")))
    lon = _safe_float(body.get("lon", body.get("longitude")))
    if lat is None or lon is None:
        return jsonify(ok=False, error="lat and lon required"), 400
    if ROVER:
        ok, result = ROVER.goto(config.ROVER_ID, lat, lon)
        return jsonify(ok=ok, cmd_id=result if ok else None, error=result if not ok else None)
    # Fallback: use mesh directly
    normalised = f"{int(round(lat * 1e6))},{int(round(lon * 1e6))}"
    MESH.send_cmd(config.ROVER_ID, "GOTO", normalised)
    return jsonify(ok=True)


@app.route("/api/rover/stop", methods=["POST"])
def api_rover_stop():
    if ROVER:
        ROVER.emergency_stop(config.ROVER_ID)
    else:
        MESH.send_cmd(config.ROVER_ID, "STOP")
    return jsonify(ok=True)


@app.route("/api/rover/pause", methods=["POST"])
def api_rover_pause():
    if ROVER:
        ROVER.pause_rover(config.ROVER_ID)
    else:
        MESH.send_cmd(config.ROVER_ID, "MODE", "RELAY")
    return jsonify(ok=True)


@app.route("/api/rover/resume", methods=["POST"])
def api_rover_resume():
    if ROVER:
        ROVER.resume_rover(config.ROVER_ID)
    else:
        MESH.send_cmd(config.ROVER_ID, "MODE", "AUTO")
    return jsonify(ok=True)


# ---- Reports (enhanced) -----------------------------------------------

@app.route("/api/reports", methods=["GET", "POST"])
def api_reports():
    if request.method == "GET":
        limit = _safe_int(request.args.get("limit", "30"))
        rows = DB._query(
            "SELECT ts,id,code,lat,lon,team,description,device_id FROM reports ORDER BY ts DESC LIMIT ?",
            (limit,))
        data = [dict(zip(("ts", "id", "code", "lat", "lon", "team", "description", "device_id"), r))
                for r in rows]
        return jsonify(ok=True, reports=data)
    else:
        return api_report()


# ---- SOS (list) -------------------------------------------------------

@app.route("/api/sos/list", methods=["GET"])
def api_sos_list():
    limit = _safe_int(request.args.get("limit", "20"))
    rows = DB._query(
        "SELECT ts,victim,lat,lon,msg,cleared FROM sos_events ORDER BY ts DESC LIMIT ?",
        (limit,))
    data = [dict(zip(("ts", "victim", "lat", "lon", "msg", "cleared"), r)) for r in rows]
    return jsonify(ok=True, sos_events=data)


@app.route("/api/sos/clear", methods=["POST"])
def api_sos_clear():
    body = request.get_json(force=True, silent=True) or {}
    victim = str(body.get("victim", "")).strip()
    if not victim:
        return jsonify(ok=False, error="victim required"), 400
    DB.sos_clear(victim)
    return jsonify(ok=True)


# ===================================================================
# Helpers
# ===================================================================

def _safe_float(v, default=None):
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _safe_int(v, default=0):
    if v is None:
        return default
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return default
