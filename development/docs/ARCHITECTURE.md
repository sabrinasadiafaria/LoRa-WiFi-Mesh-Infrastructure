# Architecture

What the system is, layer by layer, where each piece lives in the
repo, and how a packet travels from a button press on the rover to
a red ring on the Pi dashboard.

This document is the answer to "draw me a picture of how it all
fits together". For the wire-level protocol see
`docs/PACKET_SPEC.md`. For per-board wiring see `docs/WIRING.md`.
For the demo flow see `docs/DEMO_SCRIPT.md`. For what the project
*doesn't* do see `docs/LIMITATIONS.md`.

---

## The four-box view

```
           ┌─────────────────────┐                  ┌─────────────────────┐
           │   ESP32 NODE  A  C  │ ◄───  LoRa  ──► │   ESP32 NODE  B     │
           │  (portal + GPS+SOS) │                  │  (mesh relay)       │
           └──────────┬──────────┘                  └──────────┬──────────┘
                      │                                       │
                      │ Wi-Fi 2.4 GHz                         │
                      ▼                                       │
            ┌──────────────────┐                              │
            │  PHONE BROWSER   │                              │
            │ (navigator.geoloc│                              │
            │  → POST /api/loc)│                              │
            └──────────────────┘                              │
                                                               │
              ┌────────────────────────────────────────────────┘
              │
              ▼
   ┌────────────────────────┐                  ┌─────────────────────┐
   │  ESP32-S3  NODE  R     │ ◄───  LoRa  ──► │  RASPBERRY PI G/W   │
   │  (rover: motors, ultra-│                  │  (sx1278.py + Flask │
   │   sonic, GPS, E-STOP)  │                  │   dashboard :8000)  │
   └────────────────────────┘                  └──────────┬──────────┘
                                                         │
                                                  Ethernet / Wi-Fi
                                                         │
                                                         ▼
                                              ┌─────────────────────┐
                                              │  COMMANDER LAPTOP   │
                                              │  dashboard browser  │
                                              └─────────────────────┘
```

**Three radios in play:** LoRa (433 MHz) between every ESP32 and the
Pi; Wi-Fi 2.4 GHz from the phone to a portal-capable node (or to the
Pi); Ethernet / Wi-Fi from the Pi to the projector's laptop.

There is **no USB serial bridge** to the Pi and **no cloud** in the
loop. Everything is on the bench or in the lab.

---

## The seven-layer model

Each ESP32 sketch and the Pi gateway are organised the same way.
Layers are stacked bottom-up; lower layers know nothing about higher
ones.

| # | Layer | Lives in | Owns |
|---|---|---|---|
| 1 | **radio** | `firmware/common/radio_layer.h.md` (n/a in this codebase — folded into the per-node sketch), `pi/sx1278.py` on the Pi | SX1278 init, fixed PHY (433 MHz, SF7, BW125, CR 4/5, CRC on, sync 0x2A), private sync word, TX scheduler, RX pump, airtime wait |
| 2 | **packet** | per-node sketch + `pi/mesh.py` | framed ASCII: `v1|TYPE|SRC|DEST|MSGID|TTL|PAYLOAD|CHK`. CRC check. Seen-ID cache. |
| 3 | **mesh** | per-node sketch + `pi/mesh.py` | neighbour table, heartbeat, distance-vector routing with split horizon, multi-hop forwarding, self-healing route expiry |
| 4 | **GPS** | per-node sketch (`gpsService()`) + `pi/mesh.py` | non-blocking Serial2 NMEA reader, fix state, "Searching Sats" fallback |
| 5 | **app** | per-node sketch (`sosService()`, `sendLocation()`, etc.) | SOS button + screen, GPS telemetry broadcast, TEXT messaging, rescue reports, team status, rover telemetry |
| 6 | **ui** | per-node sketch (`drawUI()`) + `pi/dashboard/` | OLED pages (5-page rotation), Pi dashboard (4-panel grid + rover panel + SOS banner) |
| 7 | **portal** | per-node sketch (`portalService()`) + `pi/server.py` `/portal` route | `WiFi.softAP` + `DNSServer` + `WebServer` catch-all → captive-portal HTML/CSS/JS in PROGMEM. Browser Geolocation → POST → mesh packet |

A node is a **subset** of these layers, depending on what role it
plays:

| Node | Layers included |
|---|---|
| A | 1, 2, 3, 4, 5, 6, 7 |
| B | 1, 2, 3, 6 (no GPS, no portal, no app) |
| C | 1, 2, 3, 4, 5, 6, 7 |
| R (rover) | 1, 2, 3, 4, 5, 6 + motor + ultrasonic (no portal, no OLED-touch app UI) |
| Pi | 1, 2, 3, 5 (sends CMD/RPT to mesh), 6 (dashboard only), 7 (`/portal` mirror) |

---

## Data flow: the headline SOS scenario

What happens between the phone's "SEND SOS" button press and the red
ring appearing on the Pi dashboard. The numbers are the typical
end-to-end latencies in Phase 9's test runs (with `[PHASE9: …]`
placeholders for a real measurement).

```
PHONE BROWSER                  NODE A                LORA AIR           NODE B / C              PI GATEWAY          DASHBOARD
   │                             │                       │                  │                       │                   │
   │  tap "SEND SOS"             │                       │                  │                       │                   │
   │  POST /api/sos {loc, msg}   │                       │                  │                       │                   │
   ├────────────────────────────►│                       │                  │                       │                   │
   │                             │  build SOS frame:     │                  │                       │                   │
   │                             │  v1|SOS|A|DEST|MSGID| │                  │                       │                   │
   │                             │  TTL|PAYLOAD|CHK      │                  │                       │                   │
   │                             ├──────────────────────►│                  │                       │                   │
   │                             │                       │ SOS  (A → ALL)   │                       │                   │
   │                             │                       ├─────────────────►│                       │                   │
   │                             │                       │                  │ match dest, render    │                   │
   │                             │                       │                  │ full-screen SOS +     │                   │
   │                             │                       │                  │ forward (TTL-1) ───►  │                   │
   │                             │                       │                  │                       │ match dest "PI",   │
   │                             │                       │                  │                       │ store to SQLite,   │
   │                             │                       │                  │                       │ publish on SSE ───►│
   │                             │                       │                  │                       │                   │ SOS banner slides in
   │                             │                       │                  │                       │                   │ ring at SOS lat/lon
   │                             │                       │                  │                       │                   │ <2 s [PHASE9]
   │                             │                       │                  │                       │                   │
```

End-to-end budget: **<2 s** from button press to dashboard banner,
**<3 s** to all in-range nodes' OLEDs.

The critical thing this diagram does not show: the same `SOS:` packet
goes through **the same packet layer** the rest of the mesh uses. It
is not a side-channel. That means CRC is checked, the seen-ID cache
suppresses duplicates if two nodes both forward, and the route table
treats it the same as `DATA:` or `CMD:`.

---

## Data flow: rover → dashboard (multi-hop telemetry)

```
ROVER (R)                       ANY NODE A/B/C         PI GATEWAY                DASHBOARD
   │                                │                      │                          │
   │  every 10 s:                   │                      │                          │
   │  v1|ROVER|R|DEST|MSGID|TTL|    │                      │                          │
   │  mode,obstacle_cm,battery_pct|CHK                    │                          │
   ├───────────────────────────────►│                      │                          │
   │                                │ match src R, add to  │                          │
   │                                │ neighbour table,     │                          │
   │                                │ forward (TTL-1) ────►│                          │
   │                                │                      │ match src R,             │
   │                                │                      │ update rover row in DB,  │
   │                                │                      │ publish on SSE ─────────►│
   │                                │                      │                          │ rover panel updates
   │                                │                      │                          │ mode / obstacle / battery
   │                                │                      │                          │
```

This works **even when the rover is out of the Pi's direct range** —
that is the entire point of being a mobile relay. Nodes A, B, C all
relay `ROVER:` broadcasts the same way they relay `SOS:` / `RPT:`.

---

## Data flow: phone → mesh (portal)

```
PHONE BROWSER                NODE A (or C)              LORA AIR                  OTHER NODES              PI
   │                            │                          │                          │                    │
   │  POST /api/sos            │                           │                          │                    │
   │  (same JSON shape as the  │                           │                          │                    │
   │   Pi's /api/sos)          │                           │                          │                    │
   ├───────────────────────────►│                           │                          │                    │
   │                            │ validate (auth, schema) │                          │                    │
   │                            │ build packet             │                          │                    │
   │                            ├─────────────────────────►│                          │                    │
   │                            │                           │  → other nodes + Pi       │                    │
   │                            │                           │                           │                    │
   │  ←  200 OK                │                           │                           │                    │
   │   { "ok": true,            │                           │                           │                    │
   │     "mesh_packet": "..." } │                           │                           │                    │
```

The portal **does not** talk to the Pi directly. It only talks to the
node it's connected to. That node converts the HTTP POST into a mesh
packet and sends it on the air. The Pi picks it up over LoRa the same
way it would have if a button had been pressed.

This is the design choice that keeps the demo robust: the phone is
one of many sources; the Pi is one of many listeners; the LoRa air is
the only backbone.

---

## Mesh protocol in one paragraph

Distance-vector routing with split horizon and a 45-second route
timeout. Each node broadcasts `RT:` advertisements every 30 s listing
the destinations it can reach and at what hop count. When a node
hears an `RT:` from a neighbour, it merges the route into its own
table — but it does **not** advertise back a route it learned from
that neighbour (split horizon; prevents count-to-infinity loops). If
no `RT:` refreshes a route for 45 s, the route is invalidated and the
next `DATA:` finds the next-best path or is dropped with `no route`.

Forwarding uses a **seen-ID cache** (32 entries) so two nodes with
the same route don't both forward the same `DATA:`. CRC is **on** and
the sync word is private (`0x2A`) so other SX127x users on the same
band don't collide with us. Full spec: `docs/PACKET_SPEC.md`.

---

## Storage

Everything the Pi sees is written to `sar.db` (SQLite, one file,
created on first run). Tables:

| table | rows | written by | read by |
|---|---|---|---|
| `nodes` | last seen per node id | mesh HB handler | dashboard `/api/state` |
| `positions` | last GPS fix per node id + last 200 for trails | mesh GPS handler | dashboard map |
| `messages` | every TEXT in/out | message handler | dashboard activity panel |
| `sos` | every SOS, until cleared | sos handler | dashboard SOS banner |
| `reports` | every rescue report | report handler | dashboard reports panel |
| `status` | every STAT update | status handler | dashboard team board |
| `rover_status` | last telemetry per rover | rover handler | dashboard rover panel |
| `raw` | every event for debugging | on_event catch-all | `sqlite3 sar.db` |

A 5-minute periodic `trim()` keeps the file bounded on long runs
(keeps last N rows per kind; default N = 1000).

---

## Threading

| Thread | What | Why |
|---|---|---|
| main | Flask dev server + signal handling | single dashboard viewer is fine on dev server; swap for `waitress-serve` for >1 viewer |
| mesh loop | SX1278 RX pump, TX queue, route table, periodic broadcasts | must own the radio without Flask getting in the way |
| db-trim | every 5 min, garbage-collect the SQLite store | mesh loop holds the DB lock, so trim runs on a separate thread |

Everything inside the mesh loop is **non-blocking**. No `delay()` in
the RX/TX path; every periodic task is a `due()` check against
`millis()`.

---

## What lives in the repo

```
development/
├── README.md                      ← start here
├── phase 0  / … / phase 10/      ← standalone, one folder per phase
├── firmware/                     ← (proposed structure, see docs/PLAN.md §13)
├── pi/                           ← THE canonical Pi codebase
├── docs/                         ← every doc referenced from this file
└── Progress_Tracker.md           ← checkbox tracker mirroring the root one
```

Phases 1–8 each have their own README with the per-phase rationale,
test procedure, and what they changed. Phases 9–10 are integration
and demo; their READMEs are the playbook + the script. The
per-node `phase N/Node X.md` files are **complete standalone
sketches** — paste any single one into the Arduino IDE and it
flashes. That convention is preserved from the existing `phase 1/`
through `phase 11/` at the repo root and is intentional: a single
file per board per phase is the only documentation format a casual
reader can follow without a build system.

The Pi codebase is **not** phase-numbered (only `phase 9/pi/` mirrors
it). All Pi-side fixes since phase 5 have landed directly in
`development/pi/`, because copying the dashboard + Leaflet vendoring
into every phase folder was wasted effort.

---

## Where to look when something breaks

| Symptom | Open first |
|---|---|
| Two nodes won't see each other | each node's boot banner — PHY box. If they don't match, change one. |
| Pi is silent | `journalctl -u sar-pi -n 50`. Check `Could not claim GPIO25` (means `main.py` was killed mid-syscall — `sudo systemctl restart sar-pi`). |
| Dashboard loads but no data | `tail -f` the Pi serial console; check that mesh loop is alive. |
| Phone portal doesn't auto-pop | browser cache + captive-portal probe handlers. Manual fallback: open `192.168.4.1`. |
| Rover motors don't move | battery + common ground; remove ENA/ENB jumpers; check the SOS button isn't pressed (it's an E-STOP). |
| Repeated watchdog resets | heap leak. Print `getFreeHeap()` on each loop; check no per-loop `String` concatenation in RX path. |
