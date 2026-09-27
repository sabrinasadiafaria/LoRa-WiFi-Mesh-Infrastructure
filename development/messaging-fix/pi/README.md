# SAR Command Centre - Raspberry Pi

The Pi is the gateway + command-centre for the mesh:

- it runs its own LoRa node (`MY_ID = "PI"`) on the same frequency as the
  ESP32 nodes and the rover, so the dashboard sees every packet that
  reaches the air (and can also originate commands back into the mesh).
- it stores everything in a local SQLite database (`sar.db`, one file,
  schema on first run).
- it serves the live web dashboard at `:8000` and a phone-friendly
  captive portal page at `:8000/portal`.
- it talks to the ESP32 nodes ONLY through LoRa - no USB serial bridge.

## Run it

```bash
# normal run (needs an SX1278 wired to the Pi's SPI0)
python3 main.py

# no hardware - replays synthetic packets so the dashboard demos on any PC
python3 main.py --fake-radio

# different port / DB file
python3 main.py --port 9000 --db /var/lib/sar/sar.db
```

The dashboard URL is printed at boot (`http://<pi-ip>:8000/`). The portal
page is at `http://<pi-ip>:8000/portal`.

## Files

| File                  | Purpose                                                  |
|-----------------------|----------------------------------------------------------|
| `main.py`             | entry point - mesh loop + Flask + a periodic DB trim     |
| `mesh.py`             | the Pi as a LoRa node (build/parse + routing + forwarding) |
| `server.py`           | Flask app: dashboard, JSON API, SSE event stream, portal |
| `db.py`               | SQLite store + bounded retention                         |
| `sx1278.py`           | register-level SX1278 driver (PHY must match the nodes)  |
| `fake_radio.py`       | no-hardware stand-in for the SX1278                      |
| `download_tiles.py`   | one-shot OSM tile cache for the map                      |
| `requirements.txt`    | flask, spidev, gpiozero, lgpio                           |
| `sar-pi.service`      | systemd unit (edit the paths before enabling)            |
| `dashboard/`          | the static HTML/CSS/JS the Pi serves                     |
| `dashboard/leaflet/`  | the vendored Leaflet assets (PUT_LEAFLET_HERE.txt)       |
| `dashboard/tiles/`    | the pre-downloaded OSM tiles                             |

## Dashboard

The dashboard is now a 2×2 grid of panels (matches the design image):

```
+----------------------------+---------------------------+
|  NODES MAP (Leaflet)       |  LIVE TELEMETRY           |
|                            |                           |
+----------------------------+---------------------------+
|  RECENT ACTIVITY           |  TEAM STATUS              |
|                            |                           |
+----------------------------+---------------------------+
```

A persistent top status bar shows mesh health (active nodes / total),
active SOS count, last-update time, link state and a clock. A red SOS
banner sits above the bar whenever the mesh has an uncleared SOS, with
the victim's coordinates - click it to focus the map.

The rover floating panel slides up from the bottom-right the moment a
rover has reported in. It only shows on dashboards where the rover
exists - nothing changes for a deployment without one.

The dashboard is dark-themed, responsive (collapses to one column under
1100 px, hides auxiliary bars under 700 px), and uses the same SSE
stream and `/api/state` JSON shape as the old one - the wire is
unchanged.

## Captive portal

The Pi serves a phone-friendly captive portal page at `/portal` for the
convenience of demo audiences that connect to the Pi directly instead of
to a mesh node. It mirrors the per-node portal's API (`/api/sos`,
`/api/loc`, `/api/report`, `/api/teamstatus`, `/api/team`, `/api/send`)
so the same UI works on either. The on-node portal (in `development/
phase 8/Node A.md` and `Node C.md`) is unchanged - it is already modern
and friendly; the Pi-hosted version just adds the **team picker** and
**send message** pieces that the on-node page leaves to the dashboard.

The portal uses no external JS or CSS - the whole UI is one self-contained
HTML file so a phone with a flaky Wi-Fi still renders it. Status banner,
team picker, status grid, report grid, send message, GPS share (button +
manual entry fallback) are all there.

## Wire protocol

The Pi speaks the same `v1|TYPE|SRC|DEST|MSGID|TTL|PAYLOAD|CHK` framed
ASCII protocol as the nodes (see `development/docs/PACKET_SPEC.md`).
Packet types it consumes: `HB`, `RT`, `GPS`, `SOS`, `SOSACK`, `RPT`,
`STAT`, `DATA`, `CMD`, `ROVER`. The Pi only forwards packets of type
`DATA` / `SOS` / `SOSACK` / `RPT` / `CMD`; the rest are end-of-line on
the Pi.

## JSON API (for the dashboard + portal)

```
GET  /api/state              full snapshot
GET  /api/events             Server-Sent-Events stream of mesh events
POST /api/send               send a text message to a node
POST /api/command            send a verb to a node (WHERE/SOS/MODE/FWD...)
POST /api/teamstatus         set a phone-portal user's status (local only)
POST /api/team               pick a team (local only)
POST /api/sos                portal-side SOS
POST /api/loc                portal-side GPS
POST /api/report             portal-side rescue report
POST /api/rescan             portal-side radio rescan (Pi is a no-op)
GET  /portal                 phone-friendly portal page
GET  /tiles/<z>/<x>/<y>.png  OSM map tile
```

`/api/state` returns:

```json
{
  "now":       1737380000.0,
  "nodes":     [{"id":"A","last_seen":...,"rssi":...,"online":1, ...}, ...],
  "positions": {"A": {"id":"A","lat":...,"lon":...,"src":1,"sats":7,"ts":...}, ...},
  "trails":    {"A": [[lat,lon], ...], ...},
  "sos":       [{"ts":...,"victim":"A","lat":...,"lon":...,"msg":"MAYDAY","cleared":0}],
  "messages":  [{"ts":...,"src":"A","dest":"PI","text":"...","direction":"in"}],
  "reports":   [{"ts":...,"id":"A","code":"VICTIM_FOUND","lat":...,"lon":...,"team":"T1"}],
  "status":    [{"id":"A","team":"T1","state":"SEARCHING","ts":...}],
  "rover":     [{"id":"R","mode":"MANUAL","obstacle_cm":-1,"battery_pct":-1,"ts":...}],
  "mesh":      {"neighbors": {...}, "routes": {...}}
}
```

## What's new this round (Phase 9 polish)

- Dashboard rewritten to the 4-panel layout (top status bar + 2×2).
- Pi-hosted captive portal at `/portal` with team picker + send-message
  + connection-status banner.
- Bug fixes (manual review - see git history):
  - `server.py` SSE `_subscribers` list was iterated from one thread and
    mutated from another; now under a lock.
  - `server.py` accepted any `dest` string; now validates against
    A/B/C/R/*.
  - `mesh.py` `_service_tx` advanced `_last_tx` even when the radio
    rejected the frame; now only advances on success.
  - `db.py` `state()` ran an unbounded `SELECT … ORDER BY ts`; now uses
    a per-id MAX(ts) join.
  - `db.py` adds a 5-minute periodic `trim()` so the SQLite file stays
    bounded on a long-running Pi.
  - `fake_radio.py` `poll()` no longer busy-sleeps when there's no
    packet to emit.
  - Dashboard cleans up SOS rings + stale markers when an SOS is
    cleared or a node goes offline.
- `/api/send` now allows `dest = "R"` (rover), which the dashboard uses
  to send text messages to the rover.

## Limits

- The Pi's GPS is its LoRa radio - there is no GPS module on the gateway.
  A phone-portal location update is recorded under the id `PHONE` and
  shows up on the dashboard, but never enters the mesh as a `GPS:`
  packet (the mesh doesn't know `PHONE` as a sender).
- The dashboard's "Team" picker for phone-portal users stores the pick
  in the Pi DB only. It does NOT propagate to the mesh's `STAT:` packets
  (those are owned by the nodes). A future change could carry a phone
  session id end-to-end.
- No encryption. The proposal already defers this. LoRa packets are
  plaintext on the air.
- Indoor GPS still won't get a fix. Use phone GPS or a window-side
  outdoor rehearsal.
