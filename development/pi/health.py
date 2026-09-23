"""
Node Health Manager — Phase 10.

Runs a background thread that periodically checks every known node's
health and generates alerts when a node transitions between states:

    ONLINE → DEGRADED → OFFLINE → RECOVERED (→ ONLINE)

Also detects weak-signal and route-lost conditions.

The health manager does NOT replace the mesh layer's existing
neighbour-timeout handling — it layers on top of it to provide
structured alerts, events, and a queryable node-health snapshot.
"""

import time
import json
import threading
import logging

import config

log = logging.getLogger("health")


class NodeState:
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    RECOVERED = "RECOVERED"


class NodeHealth:
    """Track the health of a single node."""

    def __init__(self, node_id):
        self.node_id = node_id
        self.state = NodeState.ONLINE
        self.last_seen = time.time()
        self.last_rssi = None
        self.last_snr = None
        self.last_route = None
        self.gps_state = None         # True / False / None
        self.battery = None
        self.offline_since = None
        self.last_alert_type = None   # dedup

    def to_dict(self):
        now = time.time()
        return {
            "node_id": self.node_id,
            "state": self.state,
            "last_seen": self.last_seen,
            "age_s": round(now - self.last_seen, 1),
            "last_rssi": self.last_rssi,
            "last_snr": self.last_snr,
            "last_route": self.last_route,
            "gps_state": self.gps_state,
            "battery": self.battery,
            "offline_since": self.offline_since,
            "offline_duration_s": round(now - self.offline_since, 1) if self.offline_since else None,
        }


class HealthManager:
    """
    Monitors all nodes. Call `node_packet(node_id, ...)` whenever ANY
    packet arrives from a node. The health loop runs in its own thread.
    """

    def __init__(self, db, publish_fn=None):
        self.db = db
        self.publish = publish_fn or (lambda k, d: None)
        self._nodes = {}         # node_id -> NodeHealth
        self._lock = threading.Lock()
        self._stop = threading.Event()

    def start(self):
        t = threading.Thread(target=self._loop, daemon=True, name="health")
        t.start()
        log.info("Node Health Manager started (check every %.0fs)", config.NODE_HEALTH_CHECK_INTERVAL_S)

    def stop(self):
        self._stop.set()

    # ---- called by the mesh/event layer ----------------------------------

    def node_packet(self, node_id, rssi=None, snr=None, route=None):
        """Called for EVERY packet received from a node."""
        with self._lock:
            h = self._nodes.get(node_id)
            if h is None:
                h = NodeHealth(node_id)
                self._nodes[node_id] = h
                log.info("New node discovered: %s", node_id)

            h.last_seen = time.time()
            if rssi is not None:
                h.last_rssi = rssi
            if snr is not None:
                h.last_snr = snr
            if route is not None:
                h.last_route = route

            # Was offline or degraded? -> RECOVERED
            if h.state in (NodeState.OFFLINE, NodeState.DEGRADED):
                offline_dur = time.time() - (h.offline_since or h.last_seen)
                h.state = NodeState.ONLINE
                self._emit_event(node_id, "NODE_RECOVERED", "INFO", {
                    "offline_duration_s": round(offline_dur, 1),
                    "current_rssi": rssi,
                })
                h.offline_since = None
                h.last_alert_type = None

    def node_gps_update(self, node_id, has_fix):
        """Called when we learn about a node's GPS state."""
        with self._lock:
            h = self._nodes.get(node_id)
            if h is None:
                return
            old_gps = h.gps_state
            h.gps_state = has_fix
            if old_gps is True and not has_fix:
                self._emit_event(node_id, "GPS_LOST", "WARNING", {})
            elif old_gps is False and has_fix:
                self._emit_event(node_id, "GPS_RECOVERED", "INFO", {})

    def node_battery(self, node_id, pct):
        """Called when battery data is received."""
        with self._lock:
            h = self._nodes.get(node_id)
            if h is None:
                return
            h.battery = pct
            if pct is not None and 0 <= pct < 15:
                if h.last_alert_type != "LOW_BATTERY":
                    self._emit_event(node_id, "LOW_BATTERY", "WARNING",
                                     {"battery_pct": pct})
                    h.last_alert_type = "LOW_BATTERY"

    # ---- query -----------------------------------------------------------

    def snapshot(self):
        """Return health data for all tracked nodes."""
        with self._lock:
            return {nid: h.to_dict() for nid, h in self._nodes.items()}

    def node_detail(self, node_id):
        with self._lock:
            h = self._nodes.get(node_id)
            return h.to_dict() if h else None

    # ---- internal --------------------------------------------------------

    def _emit_event(self, node_id, event_type, severity, data):
        """Create an alert + node event, avoiding duplicates."""
        # Dedup: check if the same alert is already active
        if not self.db.alerts_recent_of_type(event_type, node_id):
            alert_id = self.db.alert_create(
                alert_type=event_type,
                severity=severity,
                source=node_id,
                message=f"{event_type} for node {node_id}",
                data=data,
            )
            self.db.node_event(node_id, event_type, data)
            self.publish("alert", {
                "id": alert_id,
                "type": event_type,
                "severity": severity,
                "source": node_id,
                "data": data,
            })
            log.info("Alert: %s %s [%s] %s", severity, event_type, node_id, data)

    def _loop(self):
        """Periodic health check loop."""
        while not self._stop.wait(config.NODE_HEALTH_CHECK_INTERVAL_S):
            now = time.time()
            with self._lock:
                for nid, h in self._nodes.items():
                    age = now - h.last_seen

                    if h.state == NodeState.ONLINE:
                        if age > config.NODE_OFFLINE_TIMEOUT_S:
                            # ONLINE → OFFLINE
                            h.state = NodeState.OFFLINE
                            h.offline_since = h.last_seen
                            self._emit_event(nid, "NODE_OFFLINE", "CRITICAL", {
                                "last_seen": h.last_seen,
                                "last_rssi": h.last_rssi,
                                "last_route": h.last_route,
                            })
                        elif age > config.NODE_ONLINE_TIMEOUT_S:
                            # ONLINE → DEGRADED
                            h.state = NodeState.DEGRADED
                            h.offline_since = h.last_seen
                            self._emit_event(nid, "NODE_WEAK_SIGNAL", "WARNING", {
                                "age_s": round(age, 1),
                                "last_rssi": h.last_rssi,
                            })

                    elif h.state == NodeState.DEGRADED:
                        if age > config.NODE_OFFLINE_TIMEOUT_S:
                            # DEGRADED → OFFLINE
                            h.state = NodeState.OFFLINE
                            self._emit_event(nid, "NODE_OFFLINE", "CRITICAL", {
                                "last_seen": h.last_seen,
                                "last_rssi": h.last_rssi,
                                "last_route": h.last_route,
                            })

                    # Weak signal check (independent of timeout)
                    if (h.state == NodeState.ONLINE and
                            h.last_rssi is not None and
                            h.last_rssi < config.NODE_WEAK_SIGNAL_RSSI):
                        if h.last_alert_type != "NODE_WEAK_SIGNAL":
                            self._emit_event(nid, "NODE_WEAK_SIGNAL", "WARNING", {
                                "rssi": h.last_rssi,
                            })
                            h.last_alert_type = "NODE_WEAK_SIGNAL"
