#!/usr/bin/env python3
"""
SAR Command Centre - entry point.

  python3 main.py                 # normal run (needs the SX1278 wired)
  python3 main.py --fake-radio    # no hardware: replays synthetic packets,
                                  # so the dashboard can be demoed on any PC

Starts the mesh loop (its own thread) and the Flask dashboard on :8000.
"""

import argparse
import signal
import sys
import time

import db as dbmod
import mesh as meshmod
import server


def make_radio(fake):
    if fake:
        from fake_radio import FakeRadio
        return FakeRadio()
    from sx1278 import SX1278
    return SX1278()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake-radio", action="store_true")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--db", default="sar.db")
    args = ap.parse_args()

    database = dbmod.DB(args.db)

    def on_event(kind, data):
        """Bridge: mesh -> database + dashboard live stream."""
        try:
            if kind == "hb":
                database.node_seen(data["id"], rssi=data.get("rssi"), snr=data.get("snr"))
            elif kind == "node":
                if data["state"] == "lost":
                    database.node_offline(data["id"])
                else:
                    database.node_seen(data["id"], rssi=data.get("rssi"), online=1)
            elif kind == "pos":
                database.node_seen(data["id"])
                database.position(data["id"], data["lat"], data["lon"],
                                  data.get("src", 0), data.get("sats", 0))
            elif kind == "sos":
                database.sos(data["victim"], data["lat"], data["lon"], data["msg"])
            elif kind == "message":
                database.message(data["src"], "PI", data["text"], "in")
            elif kind == "report":
                database.report(data["id"], data["code"], data["lat"],
                                data["lon"], data.get("team", ""))
            elif kind == "status":
                database.status(data["id"], data["team"], data["state"])
            elif kind == "rover":
                database.node_seen(data["id"], rssi=data.get("rssi"))
                database.rover(data["id"], data["mode"], data["obstacle"], data["battery"])
            elif kind == "route":
                database.raw("route", data)
            database.raw(kind, data)
        except Exception as e:
            print("on_event error:", e, file=sys.stderr)
        server.publish(kind, data)

    radio = make_radio(args.fake_radio)
    m = meshmod.Mesh(radio, on_event)

    server.MESH = m
    server.DB = database

    try:
        m.start()
    except Exception as e:
        print(f"\nRadio failed to start: {e}\n"
              f"Wiring: see sx1278.py header. Or run with --fake-radio to test "
              f"the dashboard without hardware.\n", file=sys.stderr)
        sys.exit(1)

    print(f"SAR Command Centre up.  dashboard: http://<pi-ip>:{args.port}/")

    # PHY box, printed the same way the ESP32 nodes print theirs at boot.
    # These numbers MUST match the box on every node. A single mismatched
    # spreading factor makes the Pi completely deaf to the mesh, and nothing
    # reports an error - a radio that hears nothing looks exactly like a radio
    # with nobody in range. The values are read from sx1278.py rather than
    # written out here, so this can never drift from what the driver does.
    if args.fake_radio:
        print("node id: PI   radio: FAKE (no hardware)")
    else:
        import sx1278 as _phy
        print("############################################################")
        print("#  RADIO PHY - MUST BE IDENTICAL ON ALL 3 NODES AND THE PI")
        print(f"#     freq {_phy.FREQ_HZ} Hz    SF{_phy.SF}    "
              f"BW {_phy.BW_HZ} Hz    CR 4/{_phy.CR_DENOM}")
        print(f"#     sync 0x{_phy.SYNC_WORD:02X}    preamble {_phy.PREAMBLE}    "
              f"CRC on    TX {_phy.TX_POWER_DBM} dBm")
        print("#  Nodes must match: LORA_* in development/phase 7/Node *.md")
        print("############################################################")

    # SIGTERM (systemctl stop / kill, no -9) doesn't raise KeyboardInterrupt
    # in the main thread by default - without this handler the process just
    # dies mid-syscall and the RST GPIO is left claimed for the next run.
    def _on_term(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _on_term)

    try:
        # Flask dev server is fine for a single-viewer lab dashboard. For a
        # few concurrent viewers use: waitress-serve --port 8000 --call server:app
        server.app.run(host="0.0.0.0", port=args.port, threaded=True,
                       use_reloader=False)
    except KeyboardInterrupt:
        print("\nshutting down...")
    finally:
        # MUST run on every exit path (Ctrl+C, systemctl stop, a crash in
        # app.run) or the SX1278 RST GPIO stays claimed and the next launch
        # fails with "Could not claim GPIO25". This used to sit unreachable
        # below app.run() - a KeyboardInterrupt skipped straight past it.
        m.stop()
        radio.close()


if __name__ == "__main__":
    main()
