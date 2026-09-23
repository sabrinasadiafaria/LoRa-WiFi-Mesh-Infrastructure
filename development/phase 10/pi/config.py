"""
Phase 10 — Centralized Configuration

All configurable values live here. No magic numbers in the main code.
Import this module and use the values by name.

Values are grouped by subsystem. Timeouts and intervals are in seconds
unless the name says otherwise.
"""

import os
import json

# ---- file paths --------------------------------------------------------
DB_PATH = os.environ.get("SAR_DB_PATH", "sar.db")
LOG_DIR = os.environ.get("SAR_LOG_DIR", "logs")

# ---- network / server ---------------------------------------------------
API_HOST = "0.0.0.0"
API_PORT = int(os.environ.get("SAR_PORT", "8000"))
API_KEY = os.environ.get("SAR_API_KEY", "sar-phase10-key")  # simple auth

# ---- LoRa mesh (MUST match ESP32 nodes + pi/sx1278.py) -------------------
PROTO_VERSION = 1
MY_ID = "PI"
MAX_HOPS = 4

# ---- timing — node / mesh -----------------------------------------------
HB_INTERVAL_S = 25.0          # Pi heartbeat period (slightly slower than nodes)
RT_INTERVAL_S = 45.0          # route advertisement period
NEIGHBOR_TIMEOUT_S = 75.0     # a neighbour not heard for this long is "lost"
ROUTE_TIMEOUT_S = 120.0       # a route not refreshed for this long is invalid
TX_MIN_GAP_S = 0.10           # minimum gap between two transmissions
SEEN_CACHE_SIZE = 64          # ring buffer for duplicate suppression

# ---- node health ---------------------------------------------------------
NODE_ONLINE_TIMEOUT_S = 75.0  # no packet → DEGRADED after this
NODE_OFFLINE_TIMEOUT_S = 150.0  # no packet → OFFLINE after this
NODE_WEAK_SIGNAL_RSSI = -110  # RSSI below this → WEAK_SIGNAL alert
NODE_HEALTH_CHECK_INTERVAL_S = 10.0  # how often the health loop runs

# ---- alerts --------------------------------------------------------------
ALERT_DEDUP_WINDOW_S = 300.0  # suppress duplicate alerts within this window
ALERT_MAX_ACTIVE = 200        # cap active alerts stored in memory

# ---- messaging -----------------------------------------------------------
MSG_ACK_TIMEOUT_S = 10.0      # wait this long for an ACK
MSG_MAX_RETRIES = 3           # retry up to this many times
MSG_MAX_LENGTH = 120          # max chars in a message payload
MSG_PRIORITIES = {
    "EMERGENCY": 0,
    "CRITICAL": 1,
    "IMPORTANT": 2,
    "NORMAL": 3,
    "TELEMETRY": 4,
}

# ---- rover ---------------------------------------------------------------
ROVER_ID = "R"
ROVER_COMM_WATCHDOG_S = 15.0  # no telemetry for this long → ROVER_LINK_LOST
ROVER_ARRIVE_RADIUS_M = 2.0   # "close enough" for GOTO navigation
ROVER_OBSTACLE_THRESHOLD_CM = 25  # obstacle closer → safety stop
ROVER_TELEMETRY_INTERVAL_S = 10.0  # expected telemetry interval

# ---- GPS -----------------------------------------------------------------
GPS_UPDATE_INTERVAL_S = 45.0  # broadcast period on nodes
GPS_STALE_THRESHOLD_S = 120.0  # older than this = stale fix

# ---- missions ------------------------------------------------------------
MISSION_ID_PREFIX = "M"       # missions are named M001, M002, …

# ---- database retention --------------------------------------------------
POS_RETENTION_S = 3600        # 1 hour of trail history (was 30 min)
MSG_RETENTION_S = 7 * 24 * 3600  # 7 days of messages (was 1 day)
RPT_RETENTION_S = 7 * 24 * 3600  # 7 days of reports
RAW_RETENTION_S = 24 * 3600   # 24 hours of raw log (was 6 hours)
ALERT_RETENTION_S = 7 * 24 * 3600  # 7 days of alerts
TELEMETRY_RETENTION_S = 24 * 3600  # 24 hours of rover telemetry
LOC_HISTORY_RETENTION_S = 7 * 24 * 3600  # 7 days of location history

# ---- logging -------------------------------------------------------------
LOG_LEVEL = os.environ.get("SAR_LOG_LEVEL", "INFO")
LOG_MAX_SIZE_MB = 50          # rotate logs at this size
LOG_BACKUP_COUNT = 3          # keep this many rotated log files


def as_dict():
    """Return all config as a dict (useful for /api/config or debugging)."""
    return {k: v for k, v in globals().items()
            if k.isupper() and not k.startswith("_")}


def load_overrides(path="config.json"):
    """Load overrides from a JSON file if it exists."""
    if not os.path.isfile(path):
        return
    with open(path, "r") as f:
        overrides = json.load(f)
    g = globals()
    for k, v in overrides.items():
        if k.isupper() and k in g:
            g[k] = type(g[k])(v)  # coerce to original type
