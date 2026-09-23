#!/usr/bin/env python3
"""
SAR Command Centre - Phase 10 entry point.

  python3 main.py                 # normal run (needs SX1278 wired)
  python3 main.py --fake-radio    # no hardware: synthetic packets
  python3 main.py --fake-radio --port 8000

Wires together:
  - Mesh loop (LoRa RX/TX in its own thread)
  - Flask dashboard on :8000
  - Node Health Manager (background thread)
  - Alert/Event System
  - Message Router with ACK/retry
  - Mission Manager
  - Rover Command Coordinator

Phase 10 extends Phase 9; every Phase 9 feature still works exactly
as before. See config.py for all configurable values.
"""

import argparse
import logging
import signal
import sys
import threading
import time

import config
config.load_overrides()  # load config.json if it exists

import db as dbmod
import mesh as meshmod
import server
from health import HealthManager
from alerts import AlertManager
from messages import MessageRouter
from missions import MissionManager
from rover_mgr import RoverManager

# ---- logging -----------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


def make_radio(fake):
    if fake:
        from fake_radio import FakeRadio
        return FakeRadio()
    from sx1278 import SX1278
    return SX1278()


def main():
    ap = argparse.ArgumentParser(description="SAR Command Centre — Phase 10")
    ap.add_argument("--fake-radio", action="store_true",
                    help="Use synthetic traffic instead of real SX1278 hardware")
    ap.add_argument("--port", type=int, default=config.API_PORT)
    ap.add_argument("--db", default=config.DB_PATH)
    ap.add_argument("--log-level", default=config.LOG_LEVEL,
                    choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = ap.parse_args()

    if args.log_level:
        logging.getLogger().setLevel(getattr(logging, args.log_level))

    # ---- database -------------------------------------------------------
    database = dbmod.DB(args.db)
    log.info("Database: %s", args.db)

    # ---- alert manager (must exist before health/rover) -----------------
    alert_mgr = AlertManager(database, publish_fn=server.publish)

    # ---- mesh -----------------------------------------------------------
    def on_event(kind, data):
        """Bridge: mesh -> database + managers + dashboard live stream."""
        try:
            if kind == "hb":
                database.node_seen(data["id"], rssi=data.get("rssi"), snr=data.get("snr"))
                health_mgr.node_packet(data["id"], rssi=data.get("rssi"), snr=data.get("snr"))
            elif kind == "node":
                if data["state"] == "lost":
                    database.node_offline(data["id"])
                else:
                    database.node_seen(data["id"], rssi=data.get("rssi"), online=1)
                    health_mgr.node_packet(data["id"], rssi=data.get("rssi"))
            elif kind == "pos":
                database.node_seen(data["id"])
                database.position(data["id"], data["lat"], data["lon"],
                                  data.get("src", 0), data.get("sats", 0))
                health_mgr.node_packet(data["id"])
                # Track GPS state
                has_fix = data.get("lat", 0) != 0 or data.get("lon", 0) != 0
                health_mgr.node_gps_update(data["id"], has_fix)
            elif kind == "sos":
                database.sos(data["victim"], data["lat"], data["lon"], data["msg"])
                alert_mgr.create("SOS", source=data["victim"],
                                 message=f"SOS from {data['victim']}: {data.get('msg', '')}",
                                 severity="EMERGENCY",
                                 data={"lat": data["lat"], "lon": data["lon"]})
            elif kind == "message":
                database.message(data["src"], "PI", data["text"], "in")
                # Check if this is a tracked message (M:<id>:<text>)
                text = data.get("text", "")
                if text.startswith("M:") and ":" in text[2:]:
                    parts = text[2:].split(":", 1)
                    msg_id = parts[0]
                    # Send MSGACK back
                    m.send_data(data["src"],
                                f"MSGACK:{msg_id}")
            elif kind == "msgack":
                # Message ACK received from a node
                msg_id = data.get("msg_id", "")
                if msg_router and msg_id:
                    msg_router.ack_received(msg_id, ack_by=data.get("src", ""))
            elif kind == "report":
                database.report(data["id"], data["code"], data["lat"],
                                data["lon"], data.get("team", ""))
            elif kind == "status":
                database.status(data["id"], data["team"], data["state"])
            elif kind == "rover":
                database.node_seen(data["id"], rssi=data.get("rssi"))
                database.rover(data["id"], data["mode"], data["obstacle"], data["battery"])
                health_mgr.node_packet(data["id"], rssi=data.get("rssi"))
                health_mgr.node_battery(data["id"], data.get("battery", -1))
                # Update rover manager
                rover_mgr.telemetry_update(
                    data["id"], data["mode"],
                    data["obstacle"], data["battery"],
                    dist_m=data.get("dist_m", -1),
                    heading_err=data.get("heading_err", -999),
                    rssi=data.get("rssi"),
                )
            elif kind == "route":
                database.raw("route", data)
            database.raw(kind, data)
        except Exception as e:
            log.error("on_event error: %s", e, exc_info=True)
        server.publish(kind, data)

    radio = make_radio(args.fake_radio)
    m = meshmod.Mesh(radio, on_event)

    # ---- managers -------------------------------------------------------
    health_mgr = HealthManager(database, publish_fn=server.publish)
    msg_router = MessageRouter(database, m, alert_mgr, publish_fn=server.publish)
    mission_mgr = MissionManager(database, publish_fn=server.publish)
    rover_mgr = RoverManager(database, m, alert_mgr, publish_fn=server.publish)

    # ---- wire into server -----------------------------------------------
    server.MESH = m
    server.DB = database
    server.HEALTH = health_mgr
    server.ALERTS = alert_mgr
    server.MESSAGES = msg_router
    server.MISSIONS = mission_mgr
    server.ROVER = rover_mgr

    # ---- start everything -----------------------------------------------
    try:
        m.start()
    except Exception as e:
        log.critical("Radio failed to start: %s", e)
        print(f"\nRadio failed to start: {e}\n"
              f"Wiring: see sx1278.py header. Or run with --fake-radio.\n",
              file=sys.stderr)
        sys.exit(1)

    health_mgr.start()
    msg_router.start()
    rover_mgr.start()

    log.info("=" * 60)
    log.info("SAR Command Centre — Phase 10")
    log.info("Dashboard: http://<pi-ip>:%d/", args.port)
    log.info("API:       http://<pi-ip>:%d/api/state", args.port)
    log.info("Portal:    http://<pi-ip>:%d/portal", args.port)
    log.info("=" * 60)

    if args.fake_radio:
        log.info("Radio: FAKE (no hardware)")
    else:
        import sx1278 as _phy
        log.info("Radio PHY: freq=%d SF%d BW=%d CR4/%d sync=0x%02X TX=%ddBm",
                 _phy.FREQ_HZ, _phy.SF, _phy.BW_HZ, _phy.CR_DENOM,
                 _phy.SYNC_WORD, _phy.TX_POWER_DBM)

    # SIGTERM handler
    def _on_term(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _on_term)

    # DB trim timer
    last_trim = [0.0]
    def _trim_tick():
        while True:
            time.sleep(60)
            if time.time() - last_trim[0] < 300:
                continue
            last_trim[0] = time.time()
            try:
                database.trim()
            except Exception as e:
                log.error("DB trim error: %s", e)
    threading.Thread(target=_trim_tick, daemon=True, name="db-trim").start()

    try:
        server.app.run(host="0.0.0.0", port=args.port, threaded=True,
                       use_reloader=False)
    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        health_mgr.stop()
        msg_router.stop()
        rover_mgr.stop()
        m.stop()
        radio.close()
        log.info("Clean shutdown complete.")


if __name__ == "__main__":
    main()
