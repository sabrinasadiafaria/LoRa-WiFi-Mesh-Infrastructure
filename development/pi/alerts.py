"""
Alert / Event System — Phase 10.

Central alert management that sits between the health manager, rover
manager, message system, and the dashboard. All alerts flow through
here so there is one place to query active/historical alerts and one
SSE channel for the dashboard.

Alert types (non-exhaustive, extensible):
    NODE_OFFLINE, NODE_RECOVERED, NODE_WEAK_SIGNAL, NODE_ROUTE_LOST,
    GPS_LOST, GPS_RECOVERED, ROVER_OFFLINE, ROVER_LINK_LOST,
    ROVER_GPS_LOST, ROVER_OBSTACLE, ROVER_ARRIVED, ROVER_FAULT,
    LOW_BATTERY, SOS, MESSAGE_FAILED, MESSAGE_ACK_TIMEOUT

Severity levels:
    INFO, WARNING, CRITICAL, EMERGENCY
"""

import time
import logging

import config

log = logging.getLogger("alerts")

# Severity ordering (lower = more severe)
SEVERITY_ORDER = {"EMERGENCY": 0, "CRITICAL": 1, "WARNING": 2, "INFO": 3}

# Default severity mapping
DEFAULT_SEVERITY = {
    "NODE_OFFLINE": "CRITICAL",
    "NODE_RECOVERED": "INFO",
    "NODE_WEAK_SIGNAL": "WARNING",
    "NODE_ROUTE_LOST": "WARNING",
    "GPS_LOST": "WARNING",
    "GPS_RECOVERED": "INFO",
    "ROVER_OFFLINE": "CRITICAL",
    "ROVER_LINK_LOST": "CRITICAL",
    "ROVER_GPS_LOST": "WARNING",
    "ROVER_OBSTACLE": "WARNING",
    "ROVER_ARRIVED": "INFO",
    "ROVER_FAULT": "CRITICAL",
    "LOW_BATTERY": "WARNING",
    "SOS": "EMERGENCY",
    "MESSAGE_FAILED": "WARNING",
    "MESSAGE_ACK_TIMEOUT": "WARNING",
}


class AlertManager:
    """
    Thin wrapper over the DB alert methods that adds dedup logic,
    severity defaults, and publishes to SSE.
    """

    def __init__(self, db, publish_fn=None):
        self.db = db
        self.publish = publish_fn or (lambda k, d: None)

    def create(self, alert_type, source="", message="", data=None,
               severity=None):
        """Create an alert if not a duplicate. Returns alert_id or None."""
        if severity is None:
            severity = DEFAULT_SEVERITY.get(alert_type, "INFO")

        # dedup: don't create the same type+source if one is already active
        if self.db.alerts_recent_of_type(alert_type, source):
            return None

        alert_id = self.db.alert_create(
            alert_type=alert_type,
            severity=severity,
            source=source,
            message=message or f"{alert_type}: {source}",
            data=data,
        )
        log.info("[%s] %s: %s from %s", severity, alert_type, message, source)

        self.publish("alert", {
            "id": alert_id,
            "type": alert_type,
            "severity": severity,
            "source": source,
            "message": message,
            "data": data or {},
            "ts": time.time(),
        })
        return alert_id

    def resolve(self, alert_id, resolved_by="system"):
        self.db.alert_resolve(alert_id, resolved_by)
        self.publish("alert_resolved", {"id": alert_id, "resolved_by": resolved_by})

    def active(self):
        return self.db.alerts_active()

    def history(self, limit=100):
        return self.db.alerts_all(limit)
