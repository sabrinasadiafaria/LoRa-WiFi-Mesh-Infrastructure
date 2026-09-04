"""
Flask app: the command-centre dashboard + JSON API + live event stream.

Runs in the same process as the mesh loop (main.py wires them together).
"""

import json
import queue
import time
from flask import Flask, Response, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="dashboard", static_url_path="")

# set by main.py
MESH = None
DB = None

_subscribers = []          # list[queue.Queue]  for SSE


def publish(kind, data):
    msg = json.dumps({"kind": kind, "data": data, "ts": time.time()})
    for q in list(_subscribers):
        try:
            q.put_nowait(msg)
        except queue.Full:
            pass


@app.route("/")
def index():
    return send_from_directory("dashboard", "index.html")


@app.route("/api/state")
def api_state():
    st = DB.state()
    st["mesh"] = MESH.snapshot()
    st["now"] = time.time()
    return jsonify(st)


@app.route("/api/events")
def api_events():
    q = queue.Queue(maxsize=200)
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
            if q in _subscribers:
                _subscribers.remove(q)

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


@app.route("/api/send", methods=["POST"])
def api_send():
    body = request.get_json(force=True, silent=True) or {}
    dest = (body.get("dest") or "").strip().upper()
    text = (body.get("text") or "").strip()
    if not dest or not text:
        return jsonify(ok=False, error="dest and text required"), 400
    MESH.send_data(dest, text)
    DB.message("PI", dest, text, "out")
    publish("message", {"src": "PI", "dest": dest, "text": text, "direction": "out"})
    return jsonify(ok=True)


@app.route("/api/command", methods=["POST"])
def api_command():
    body = request.get_json(force=True, silent=True) or {}
    dest = (body.get("dest") or "").strip().upper()
    verb = (body.get("verb") or "").strip().upper()
    arg = (body.get("arg") or "").strip()
    if dest not in ("A", "B", "C", "*") or verb not in ("WHERE", "SOS", "SOSCLR", "PING"):
        return jsonify(ok=False, error="bad dest or verb"), 400
    MESH.send_cmd(dest, verb, arg)
    DB.raw("cmd_out", f"{dest} {verb} {arg}")
    publish("command", {"dest": dest, "verb": verb, "arg": arg})
    return jsonify(ok=True)


@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def tile(z, x, y):
    # served from the pre-downloaded cache; 404 -> Leaflet shows the grey grid
    return send_from_directory("dashboard/tiles", f"{z}/{x}/{y}.png")
