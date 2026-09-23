"""
The Pi as a mesh node — Phase 10.

This is the Phase 9 mesh.py with the following additions:
  - MSGACK packet type: received when a node acknowledges a tracked message
  - on_event callback extended to support 'msgack' event kind
  - No protocol version bump needed: v1 already ignores unknown types

All Phase 9 behavior is preserved exactly. The wire format is unchanged.
"""

import time
import threading
import random

import config

PROTO_VERSION = config.PROTO_VERSION
MY_ID = config.MY_ID

# match the ESP32 constants
HB_INTERVAL = config.HB_INTERVAL_S
RT_INTERVAL = config.RT_INTERVAL_S
NEIGHBOR_TIMEOUT = config.NEIGHBOR_TIMEOUT_S
ROUTE_TIMEOUT = config.ROUTE_TIMEOUT_S
MAX_HOPS = config.MAX_HOPS
TX_MIN_GAP = config.TX_MIN_GAP_S
SEEN_CACHE = config.SEEN_CACHE_SIZE

FORWARDABLE = {"DATA", "SOS", "SOSACK", "RPT", "CMD", "MSGACK"}
CONSUMED_NO_FWD = {"HB", "RT", "GPS", "STAT", "ROVER"}

PRI_CMD     = 0
PRI_SOS     = 0
PRI_RPT     = 1
PRI_DATA    = 2
PRI_FWD     = 3
PRI_PERIODIC = 4


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
        self.on_event = on_event
        self._msgid = 0
        self._seen = []
        self._txq = []
        self._last_tx = 0.0
        self._lock = threading.Lock()
        self.neighbors = {}
        self.routes = {}
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
        text = sanitize(text)[:config.MSG_MAX_LENGTH]
        self._enqueue(build("DATA", MY_ID, dest, self.next_msgid(), MAX_HOPS, text),
                      pri=PRI_DATA)
        return True

    def send_cmd(self, dest, verb, arg=""):
        payload = sanitize(f"{verb},{arg}" if arg else verb)
        self._enqueue(build("CMD", MY_ID, dest, self.next_msgid(), MAX_HOPS, payload),
                      pri=PRI_CMD)
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
    def _enqueue(self, frame: bytes, pri: int = PRI_PERIODIC):
        with self._lock:
            if len(self._txq) < 24:
                self._txq.append((pri, frame))

    def _seen_forget(self, src):
        self._seen = [k for k in self._seen if k[0] != src]

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
        payload = f"{int(time.time())}"
        self._enqueue(build("HB", MY_ID, "*", self.next_msgid(), 0, payload),
                      pri=PRI_PERIODIC)

    def _send_rt(self):
        entries = []
        for dest, r in self.routes.items():
            if r["valid"]:
                if r["hops"] == 1:
                    entries.append(f"{dest},{r['via']}")
                else:
                    entries.append(f"{dest},{r['hops']},{r['via']}")
        payload = ";".join(entries)
        self._enqueue(build("RT", MY_ID, "*", self.next_msgid(), 0, payload),
                      pri=PRI_PERIODIC)

    def _service_tx(self):
        now = time.time()
        if now - self._last_tx < TX_MIN_GAP:
            return
        with self._lock:
            if not self._txq:
                return
            self._txq.sort(key=lambda t: t[0])
            _, frame = self._txq.pop(0)
        ok = self.radio.send(frame)
        if not ok:
            return
        ptype = frame.split(b"|", 2)[1].decode("ascii", "replace")
        if ptype in ("CMD", "RPT", "DATA", "SOSACK", "MSGACK"):
            self._last_tx = time.time() + random.uniform(0, 0.05)
        else:
            self._last_tx = time.time() + random.uniform(0, 0.25)

    def _handle(self, pkt, rssi, snr):
        src = pkt["src"]
        if src == MY_ID:
            return
        if pkt["type"] in FORWARDABLE and self._seen_or_add(src, pkt["msgid"]):
            return

        now = time.time()
        fresh = src not in self.neighbors or not self.neighbors[src].get("active", False)
        self.neighbors.setdefault(src, {})
        self.neighbors[src].update(rssi=rssi, snr=snr, last=now, active=True)
        self._route_update(src, src, 1, rssi)
        if fresh:
            self._seen_forget(src)
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
            self._forward_if_needed(pkt)

        elif t == "SOS":
            f = pl.split(",", 2)
            self.on_event("sos", {
                "victim": src, "lat": _float(f[0]) if f else 0,
                "lon": _float(f[1]) if len(f) > 1 else 0,
                "msg": f[2] if len(f) > 2 else "", "rssi": rssi,
            })
            self._enqueue(build("SOSACK", MY_ID, src, self.next_msgid(), MAX_HOPS,
                                f"{src},{pkt['msgid']}"), pri=PRI_SOS)
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

        elif t == "ROVER":
            f = pl.split(",")
            if len(f) >= 3:
                self.on_event("rover", {
                    "id": src, "mode": f[0],
                    "obstacle": _int(f[1], -1),
                    "battery": _int(f[2], -1),
                    "dist_m": _int(f[3], -1) if len(f) > 3 else -1,
                    "heading_err": _int(f[4], -999) if len(f) > 4 else -999,
                    "rssi": rssi,
                })

        elif t == "DATA":
            if pkt["dest"] == MY_ID:
                self.on_event("message", {"src": src, "text": pl})
            else:
                self._forward_if_needed(pkt)

        elif t == "CMD":
            if pkt["dest"] != MY_ID:
                self._forward_if_needed(pkt)

        # ---- Phase 10: MSGACK handling --------------------------------
        elif t == "MSGACK":
            # Payload format: <original_msg_id>
            self.on_event("msgack", {"src": src, "msg_id": pl.strip(), "rssi": rssi})
            if pkt["dest"] != MY_ID:
                self._forward_if_needed(pkt)

    def _forward_if_needed(self, pkt):
        if pkt["dest"] == MY_ID or pkt["ttl"] <= 0:
            return
        if pkt["type"] in CONSUMED_NO_FWD:
            return
        if pkt["dest"] != "*" and self.best_hop(pkt["dest"]) is None:
            return
        pri = PRI_SOS if pkt["type"] == "SOS" else PRI_RPT if pkt["type"] == "RPT" else PRI_FWD
        self._enqueue(build(pkt["type"], pkt["src"], pkt["dest"],
                            pkt["msgid"], pkt["ttl"] - 1, pkt["payload"]), pri=pri)

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
                    except Exception as e:
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
