"""
Flask app: the command-centre dashboard + JSON API + live event stream.

Runs in the same process as the mesh loop (main.py wires them together).
"""

import json
import queue
import threading
import time
from flask import Flask, Response, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="dashboard", static_url_path="")

# set by main.py
MESH = None
DB = None

_subscribers = []          # list[queue.Queue]  for SSE
_sub_lock = threading.Lock()

# LoRa DATA packet payload budget.  The wire frame
#   v1|DATA|PI|<dest>|<msgid>|4|<payload>|xx
# eats ~28 bytes, and the SX1278 caps at 255.  We leave room for a
# [n/N] chunk prefix (up to 7 chars) so the usable text per chunk is
# ~100 chars.  Messages longer than this are auto-split.
LORA_MAX_TEXT = 100


def publish(kind, data):
    msg = json.dumps({"kind": kind, "data": data, "ts": time.time()})
    with _sub_lock:
        subs = list(_subscribers)
    for q in subs:
        try:
            q.put_nowait(msg)
        except queue.Full:
            pass


@app.route("/")
def index():
    return send_from_directory("dashboard", "index.html")


# Captive portal page for phones that hit the Pi's AP. Identical to the
# per-node portal in look-and-feel, served from the Pi for the convenience
# of demo audiences that connect directly to the Pi instead of a mesh node.
# See development/pi/README.md for the rationale.
@app.route("/portal")
@app.route("/portal/")
def portal():
    return send_from_directory("dashboard", "portal.html")


@app.route("/api/state")
def api_state():
    st = DB.state()
    st["mesh"] = MESH.snapshot()
    st["now"] = time.time()
    return jsonify(st)


@app.route("/api/messages")
def api_messages():
    """Return message history for the Messages panel."""
    limit = min(int(request.args.get("limit", 100)), 500)
    msgs = DB.messages_list(limit)
    return jsonify(messages=msgs)


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
    """A node id is at most 4 chars and must be one of A/B/C/R/PI/*. Anything
    else is junk (header injection, control chars, etc.) and gets rejected."""
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
    # strip anything that could break the wire frame
    for bad in ("|", "\\", "\r", "\n"):
        s = s.replace(bad, "/")
    return s[:maxlen]


@app.route("/api/send", methods=["POST"])
def api_send():
    body = request.get_json(force=True, silent=True) or {}
    dest = _safe_dest(body.get("dest", ""))
    text = _safe_text(body.get("text", ""), maxlen=500)  # allow longer input; we chunk
    if not dest or not text:
        return jsonify(ok=False, error="dest and text required"), 400
    if dest not in {"A", "B", "C", "R"}:
        # '*' broadcast from the dashboard would be noisy; allow it
        if dest != "*":
            return jsonify(ok=False, error="dest must be A/B/C/R/*"), 400

    # ---- LoRa chunking ---------------------------------------------------
    # Split long messages into <=LORA_MAX_TEXT-char chunks.  Each chunk
    # after the first gets a [n/N] prefix so the receiver can tell them
    # apart. Short messages are sent as-is (no prefix overhead).
    if len(text) <= LORA_MAX_TEXT:
        chunks = [text]
    else:
        raw_chunks = []
        remaining = text
        # First chunk gets [1/N] prefix too, so budget accordingly
        while remaining:
            raw_chunks.append(remaining[:LORA_MAX_TEXT])
            remaining = remaining[LORA_MAX_TEXT:]
        total = len(raw_chunks)
        chunks = [f"[{i+1}/{total}]{c}" for i, c in enumerate(raw_chunks)]

    for chunk in chunks:
        MESH.send_data(dest, chunk)
        DB.message("PI", dest, chunk, "out")
        publish("message", {"src": "PI", "dest": dest, "text": chunk, "direction": "out"})

    return jsonify(ok=True, chunks=len(chunks))


# ---- Pi-side captive portal endpoints ----------------------------------
# These mirror the on-node portal's API so the Pi can also serve a portal
# page to anyone who happens to be on the Pi's own SoftAP (or anyone pointed
# at the Pi's IP by the on-node portal). The mesh side-effects come from
# calling into the existing MESH / DB / publish hooks - no new wire types.

@app.route("/api/sos", methods=["GET", "POST"])
def api_sos():
    # Pi can't be a "victim" the way a node can, so this just records a
    # phone-portal SOS in the DB and shows it on the dashboard. The mesh
    # nodes can still raise real SOS with their own button or their portal.
    DB.sos("PHONE", 0.0, 0.0, "PORTAL")
    publish("sos", {"victim": "PHONE", "lat": 0.0, "lon": 0.0, "msg": "PORTAL"})
    return jsonify(ok=True)


@app.route("/api/loc", methods=["GET", "POST"])
def api_loc():
    # The Pi has no GPS, so a phone-portal location update can only be
    # remembered for the dashboard - we tag it as a phone source and store
    # it under a "PHONE" id so the map shows the latest phone position.
    try:
        if request.method == "GET":
            lat = float(request.args.get("lat", ""))
            lon = float(request.args.get("lon", ""))
        else:
            body = request.get_json(force=True, silent=True) or {}
            lat = float(body.get("lat", ""))
            lon = float(body.get("lon", ""))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="bad lat/lon"), 400
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify(ok=False, error="lat/lon out of range"), 400
    DB.position("PHONE", lat, lon, src=2, sats=0)
    publish("pos", {"id": "PHONE", "lat": lat, "lon": lon, "src": 2, "sats": 0})
    return jsonify(ok=True)


@app.route("/api/report", methods=["GET", "POST"])
def api_report():
    code = (request.args.get("code") or "").strip().upper()
    if code not in {"VICTIM_FOUND", "MEDICAL", "BLOCKED", "DANGER"}:
        return jsonify(ok=False, error="bad report code"), 400
    DB.report("PHONE", code, 0.0, 0.0, "?")
    publish("report", {"id": "PHONE", "code": code, "lat": 0.0, "lon": 0.0, "team": "?"})
    return jsonify(ok=True)


@app.route("/api/rescan", methods=["GET", "POST"])
def api_rescan():
    # Nothing meaningful for the Pi to "rescan" - the radio is its own.
    # The on-node portal does the real work; the Pi endpoint exists only so
    # a Pi-hosted portal page doesn't 404 on the same button.
    return jsonify(ok=True, message="no radio to rescan from the gateway")


# Verbs per destination. 'R' (rover) can also receive plain text messages via
# the standard /api/send, see _safe_dest above. SOS / WHERE / MODE etc. stay
# channel-separated through /api/command.
DEST_VERBS = {
    "A": {"WHERE", "SOS", "SOSCLR", "PING"},
    "B": {"WHERE", "SOS", "SOSCLR", "PING"},
    "C": {"WHERE", "SOS", "SOSCLR", "PING"},
    "*": {"WHERE", "SOS", "SOSCLR", "PING"},
    # Phase 8: the rover's drive/mode verbs. FWD/BACK/LEFT/RIGHT/STOP are the
    # bounded manual-drive pulse (see Node Rover.md's dead-man-switch note -
    # a dashboard button held down must keep POSTing to keep it moving).
    # GOTO and GOCLR are Phase 9 - send the rover to a GPS target.
    "R": {"WHERE", "SOS", "SOSCLR", "PING",
          "FWD", "BACK", "LEFT", "RIGHT", "STOP", "MODE",
          "GOTO", "GOCLR"},
}
MODE_ARGS = {"MANUAL", "AUTO", "RELAY"}

# Routes the Pi dashboard and the Pi-served captive portal page both call.
# They do NOT translate to mesh packets - the mesh is the source of truth for
# team ids and status (STAT:). A phone-portal user's status lives only in
# the Pi's local DB and shows up on the dashboard immediately (the dashboard
# reads the same DB). We just store it and publish an SSE event.
VALID_STATES = {"AVAILABLE", "SEARCHING", "NEED_ASSIST", "VICTIM_FOUND", "EMERGENCY"}


@app.route("/api/teamstatus", methods=["GET", "POST"])
def api_teamstatus():
    # GET ?state=X   (the Node A/C portals call it as a GET)
    # POST {"state": "X"}  (the Pi dashboard calls it as a POST)
    if request.method == "GET":
        st_arg = request.args.get("state", "")
    else:
        body = request.get_json(force=True, silent=True) or {}
        st_arg = body.get("state", "")
    st = (st_arg or "").strip().upper()
    if st not in VALID_STATES:
        return jsonify(ok=False, error="unknown state"), 400
    # The "phone" is the actor here - it has no mesh id. The dashboard picks
    # up the change on its next /api/state refresh (and immediately via SSE).
    DB.status("PHONE", "?", st)
    publish("status", {"id": "PHONE", "team": "?", "state": st})
    return jsonify(ok=True)


@app.route("/api/team", methods=["GET", "POST"])
def api_team():
    """Captive-portal users pick their team on first visit. The Pi cannot
    push this onto the mesh on its own (mesh STAT packets are owned by the
    nodes, not the gateway), so we store the pick locally and let the
    dashboard see it. A future change could carry a phone session id end-
    to-end; for now this is best-effort and shown only on the Pi dashboard."""
    if request.method == "GET":
        team = request.args.get("team", "")
    else:
        body = request.get_json(force=True, silent=True) or {}
        team = body.get("team", "")
    team = (team or "").strip().upper()[:8]
    if not team or not team[0].isalnum():
        return jsonify(ok=False, error="bad team"), 400
    DB.status("PHONE", team, "AVAILABLE")
    publish("status", {"id": "PHONE", "team": team, "state": "AVAILABLE"})
    return jsonify(ok=True)


@app.route("/api/command", methods=["POST"])
def api_command():
    body = request.get_json(force=True, silent=True) or {}
    dest = _safe_dest(body.get("dest", ""))
    verb = (body.get("verb") or "").strip().upper()
    # GOTO's arg is "lat,lon" as integer microdegrees ("23687750,90432100" for
    # 23.687750, 90.432100). Uppercasing would corrupt digits and the dash in
    # negative coords, so GOTO bypasses the normal .upper() / length cap and
    # runs its own tighter validation.
    if verb == "GOTO":
        raw = (body.get("arg") or "").strip()
        ok, err, normalised = _validate_goto(raw)
        if not ok:
            return jsonify(ok=False, error=err), 400
        MESH.send_cmd(dest, "GOTO", normalised)
        DB.raw("cmd_out", f"{dest} GOTO {normalised}")
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
    """Accept '<lat_microdeg>,<lon_microdeg>' in [-90000000, 90000000] each,
    or 'lat,lon' as plain decimal degrees. Returns (ok, err, normalised)."""
    if not raw or "," not in raw:
        return False, "GOTO arg must be 'lat,lon'", ""
    a, _, b = raw.partition(",")
    try:
        la = float(a); lo = float(b)
    except ValueError:
        return False, "GOTO arg must be numeric", ""
    if not (-90.0 <= la <= 90.0 and -180.0 <= lo <= 180.0):
        return False, "GOTO arg out of range", ""
    # Normalise to integer microdegrees so the wire bytes are tiny and the
    # rover doesn't have to do float parsing in a packet path.
    return True, "", f"{int(round(la * 1e6))},{int(round(lo * 1e6))}"


@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def tile(z, x, y):
    # served from the pre-downloaded cache; 404 -> Leaflet shows the grey grid
    return send_from_directory("dashboard/tiles", f"{z}/{x}/{y}.png")
