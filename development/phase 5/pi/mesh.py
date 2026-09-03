"""
The Pi as a mesh node.

Implements the same wire protocol as development/phase 4/*.md:

    v<VER>|<TYPE>|<SRC>|<DEST>|<MSGID>|<TTL>|<PAYLOAD>|<CHK>

and the same behaviour: heartbeat, distance-vector routing with split
horizon, multi-hop forwarding with a seen-ID cache, and self-healing route
expiry. The Pi's node id is "PI".

Nodes reach the Pi directly if in range, or multi-hop (C -> B -> A -> PI).
The Pi reaches nodes the same way in reverse. Commands from the dashboard
go out as CMD packets.
"""

import time
import threading
import random

PROTO_VERSION = 1
MY_ID = "PI"

# match the ESP32 constants
HB_INTERVAL = 10.0
RT_INTERVAL = 15.0
NEIGHBOR_TIMEOUT = 35.0
ROUTE_TIMEOUT = 50.0
MAX_HOPS = 4
TX_MIN_GAP = 0.15
SEEN_CACHE = 64

FORWARDABLE = {"DATA", "SOS", "SOSACK", "RPT", "CMD"}
CONSUMED_NO_FWD = {"HB", "RT", "GPS", "STAT", "ROVER"}


def checksum(s: str) -> int:
    c = 0
    for ch in s.encode("ascii", "replace"):
        c ^= ch
    return c


def sanitize(s: str) -> str:
    for bad in ("|", "\\", "\r", "\n"):
        s = s.replace(bad, "/")
    return s


def build(ptype, src, dest, msgid, ttl, payload) -> bytes:
    body = f"v{PROTO_VERSION}|{ptype}|{src}|{dest}|{msgid}|{ttl}|{payload}"
    return f"{body}|{checksum(body):02x}".encode("ascii", "replace")


def parse(raw: bytes):
    try:
        s = raw.decode("ascii", "strict")
    except UnicodeDecodeError:
        return None
    if s.count("|") < 7:
        return None
    body, _, chk = s.rpartition("|")
    if len(chk) != 2:
        return None
    try:
        if checksum(body) != int(chk, 16):
            return None
    except ValueError:
        return None
    parts = body.split("|", 6)
    if len(parts) != 7 or not parts[0].startswith("v"):
        return None
    try:
        ver = int(parts[0][1:])
    except ValueError:
        return None
    if ver != PROTO_VERSION:
        return None
    try:
        msgid = int(parts[4]); ttl = int(parts[5])
    except ValueError:
        return None
    return {
        "ver": ver, "type": parts[1], "src": parts[2], "dest": parts[3],
        "msgid": msgid, "ttl": ttl, "payload": parts[6],
    }


class Mesh:
    """
    Owns the radio. Runs a single RX/TX loop in its own thread. Everything
    the dashboard needs is delivered through the `on_event` callback; the
    dashboard sends by calling `send_data` / `send_cmd`.
    """

    def __init__(self, radio, on_event):
        self.radio = radio
        self.on_event = on_event            # on_event(kind:str, data:dict)
        self._msgid = 0
        self._seen = []
        self._txq = []
        self._last_tx = 0.0
        self._lock = threading.Lock()
        self.neighbors = {}                 # id -> {rssi, snr, last, uptime, heap}
        self.routes = {}                    # dest -> {via, hops, last, valid}
        self._stop = threading.Event()
        self._hb_at = 0.0
        self._rt_at = 0.0

    # ---- public API ---------------------------------------------------
    def start(self):
        self.radio.begin()
        self.radio.receive()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def stop(self):
        self._stop.set()

    def next_msgid(self):
        self._msgid = 1 if self._msgid >= 65535 else self._msgid + 1
        return self._msgid

    def send_data(self, dest, text):
        text = sanitize(text)[:120]
        self._enqueue(build("DATA", MY_ID, dest, self.next_msgid(), MAX_HOPS, text))
        return True

    def send_cmd(self, dest, verb, arg=""):
        payload = sanitize(f"{verb},{arg}" if arg else verb)
        self._enqueue(build("CMD", MY_ID, dest, self.next_msgid(), MAX_HOPS, payload))
        return True

    def best_hop(self, dest):
        r = self.routes.get(dest)
        return r["via"] if r and r["valid"] else None

    def snapshot(self):
        now = time.time()
        return {
            "neighbors": {
                nid: {**v, "age": round(now - v["last"], 1)}
                for nid, v in self.neighbors.items()
            },
            "routes": {
                d: {**v, "age": round(now - v["last"], 1)}
                for d, v in self.routes.items()
            },
        }

    # ---- internals --------------------------------------------------
    def _enqueue(self, frame: bytes):
        with self._lock:
            if len(self._txq) < 8:
                self._txq.append(frame)

    def _seen_or_add(self, src, msgid):
        key = (src, msgid)
        if key in self._seen:
            return True
        self._seen.append(key)
        if len(self._seen) > SEEN_CACHE:
            self._seen.pop(0)
        return False

    def _route_update(self, dest, via, hops, rssi):
        if dest == MY_ID or hops < 1 or hops > MAX_HOPS:
            return
        now = time.time()
        r = self.routes.get(dest)
        if r is None:
            self.routes[dest] = {"via": via, "hops": hops, "last": now, "valid": True}
            self.on_event("route", {"dest": dest, "via": via, "hops": hops, "state": "new"})
            return
        if via == r["via"] or hops < r["hops"] or not r["valid"]:
            was_valid = r["valid"]
            r.update(via=via, hops=hops, last=now, valid=True)
            if not was_valid:
                self.on_event("route", {"dest": dest, "via": via, "hops": hops, "state": "recovered"})

    def _expire_routes(self):
        now = time.time()
        for dest, r in self.routes.items():
            if r["valid"] and now - r["last"] > ROUTE_TIMEOUT:
                r["valid"] = False
                self.on_event("route", {"dest": dest, "state": "lost"})

    def _prune_neighbors(self):
        now = time.time()
        for nid, v in list(self.neighbors.items()):
            if v.get("active", True) and now - v["last"] > NEIGHBOR_TIMEOUT:
                v["active"] = False
                self.on_event("node", {"id": nid, "state": "lost"})

    def _send_hb(self):
        payload = f"{int(time.time())},{0},{5}"      # uptime,heap,fwver (fw 5 = phase 5)
        self._enqueue(build("HB", MY_ID, "*", self.next_msgid(), 0, payload))

    def _send_rt(self):
        entries = []
        for dest, r in self.routes.items():
            if r["valid"]:
                entries.append(f"{dest},{r['hops']},{r['via']}")
        self._enqueue(build("RT", MY_ID, "*", self.next_msgid(), 0, ";".join(entries) + (";" if entries else "")))

    def _service_tx(self):
        now = time.time()
        if now - self._last_tx < TX_MIN_GAP:
            return
        with self._lock:
            frame = self._txq.pop(0) if self._txq else None
        if frame is None:
            return
        self.radio.send(frame)
        self._last_tx = time.time() + random.uniform(0, 0.2)

    def _handle(self, pkt, rssi, snr):
        src = pkt["src"]
        if src == MY_ID:
            return
        if pkt["type"] in FORWARDABLE and self._seen_or_add(src, pkt["msgid"]):
            return

        # any packet proves the sender is a 1-hop neighbour
        now = time.time()
        fresh = src not in self.neighbors or not self.neighbors[src].get("active", False)
        self.neighbors.setdefault(src, {})
        self.neighbors[src].update(rssi=rssi, snr=snr, last=now, active=True)
        self._route_update(src, src, 1, rssi)
        if fresh:
            self.on_event("node", {"id": src, "state": "up", "rssi": rssi})

        t = pkt["type"]
        pl = pkt["payload"]

        if t == "HB":
            bits = pl.split(",")
            if len(bits) >= 2:
                self.neighbors[src]["uptime"] = _int(bits[0])
                self.neighbors[src]["heap"] = _int(bits[1])
            self.on_event("hb", {"id": src, "rssi": rssi, "snr": snr})

        elif t == "RT":
            for e in pl.split(";"):
                if not e:
                    continue
                f = e.split(",")
                if len(f) == 3 and f[2] != MY_ID and f[0] != MY_ID:
                    self._route_update(f[0], src, _int(f[1]) + 1, rssi)

        elif t == "GPS":
            f = pl.split(",")
            if len(f) >= 2:
                self.on_event("pos", {
                    "id": src, "lat": _float(f[0]), "lon": _float(f[1]),
                    "sats": _int(f[2]) if len(f) > 2 else 0,
                    "src": _int(f[3]) if len(f) > 3 else 0,
                    "age": _int(f[4]) if len(f) > 4 else 0,
                    "rssi": rssi,
                })
            self._forward_if_needed(pkt)   # GPS is broadcast; still relay hop-wise? no

        elif t == "SOS":
            f = pl.split(",", 2)
            self.on_event("sos", {
                "victim": src, "lat": _float(f[0]) if f else 0,
                "lon": _float(f[1]) if len(f) > 1 else 0,
                "msg": f[2] if len(f) > 2 else "", "rssi": rssi,
            })
            # acknowledge and relay
            self._enqueue(build("SOSACK", MY_ID, src, self.next_msgid(), MAX_HOPS,
                                f"{src},{pkt['msgid']}"))
            self._forward_if_needed(pkt)

        elif t == "SOSACK":
            self._forward_if_needed(pkt)

        elif t == "RPT":
            f = pl.split(",")
            self.on_event("report", {
                "id": src, "code": f[0] if f else "",
                "lat": _float(f[1]) if len(f) > 1 else 0,
                "lon": _float(f[2]) if len(f) > 2 else 0,
                "team": f[3] if len(f) > 3 else "",
            })
            self._forward_if_needed(pkt)

        elif t == "STAT":
            f = pl.split(",")
            if len(f) == 2:
                self.on_event("status", {"id": src, "team": f[0], "state": f[1]})

        elif t == "DATA":
            if pkt["dest"] == MY_ID:
                self.on_event("message", {"src": src, "text": pl})
            else:
                self._forward_if_needed(pkt)

        elif t == "CMD":
            # commands are Pi -> node; if we somehow receive one, just relay
            if pkt["dest"] != MY_ID:
                self._forward_if_needed(pkt)

    def _forward_if_needed(self, pkt):
        if pkt["dest"] == MY_ID or pkt["ttl"] <= 0:
            return
        if pkt["type"] in CONSUMED_NO_FWD:
            return
        # broadcast SOS/RPT: relay to everyone; directed: only if we have a route
        if pkt["dest"] != "*" and self.best_hop(pkt["dest"]) is None:
            return
        self._enqueue(build(pkt["type"], pkt["src"], pkt["dest"],
                            pkt["msgid"], pkt["ttl"] - 1, pkt["payload"]))

    def _run(self):
        self._hb_at = time.time() + random.uniform(0, 2)
        self._rt_at = time.time() + random.uniform(1, 4)
        while not self._stop.is_set():
            got = self.radio.poll()
            if got:
                data, rssi, snr = got
                pkt = parse(data)
                if pkt:
                    try:
                        self._handle(pkt, rssi, snr)
                    except Exception as e:      # never let one bad packet kill the loop
                        self.on_event("error", {"where": "handle", "err": str(e)})

            now = time.time()
            if now >= self._hb_at:
                self._send_hb(); self._hb_at = now + HB_INTERVAL + random.uniform(0, 3)
            if now >= self._rt_at:
                self._send_rt(); self._rt_at = now + RT_INTERVAL + random.uniform(0, 4)

            self._expire_routes()
            self._prune_neighbors()
            self._service_tx()
            time.sleep(0.005)


def _int(s, d=0):
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return d


def _float(s, d=0.0):
    try:
        return float(s)
    except (ValueError, TypeError):
        return d
