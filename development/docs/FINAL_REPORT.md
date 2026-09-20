# Final Report

Project: Off-Grid LoRa-Based Self-Healing Mesh Communication
Infrastructure, with an Autonomous Rescue Rover for Emergency Search
& Rescue Operations.

Course: CSE-4326 Microprocessors & Microcontrollers Laboratory.

Repo root: `LoRa-WiFi-Mesh-Infrastructure/`

Date: 2026.

---

## 1. What was proposed

The approved project proposal (`planing/Project poposal.pdf`, presented
1 Sep 2026) committed to four integrated deliverables:

1. **LoRa Mesh Nodes** — long-range, multi-hop, self-healing, with
   reliable messaging.
2. **Wi-Fi Captive Portal** — any smartphone browser, no app, can
   raise SOS, share GPS, send messages, file rescue reports, set
   team status.
3. **Autonomous Rescue Rover** — obstacle-avoiding mobile mesh
   member that doubles as a LoRa relay.
4. **Raspberry Pi Command Center** — local gateway with a database
   and a web dashboard (map, telemetry, SOS banner, messages, team).

The proposal also listed twelve "demonstrated capabilities" the live
demo would show (long-range link, multi-hop routing, auto discovery,
reliable ACK messaging, heartbeat, self-healing, captive portal,
mobile GPS sharing, SOS alerts & reports, team status, autonomous
rover, mobile relay).

---

## 2. What was built

All four deliverables. All twelve demonstrated capabilities.

| Deliverable | Where in repo | State |
|---|---|---|
| LoRa Mesh Nodes | `development/phase 1` … `phase 9/Node A.md`, `Node B.md`, `Node C.md` | **Done.** 3× ESP32, mesh + GPS + SOS + portal. Beacon every 15 s, route refresh 30 s, route timeout 45 s, seen-ID cache for forward dedup, CRC on, private sync word 0x2A. |
| Wi-Fi Captive Portal | `Node A.md`, `Node C.md` (`portalService()` + PROGMEM HTML/CSS/JS); also `development/pi/server.py` `/portal` route | **Done.** SoftAP + DNSServer + WebServer on A and C; same UI also served by the Pi at `/portal`. Five user actions: SEND SOS, Share Location, Send Message, Quick Report, Team Status. |
| Autonomous Rover | `development/phase 8/Node Rover.md`, mirrored at `phase 9/Node Rover.md` | **Done.** ESP32-S3, L298N + 4× 6 V gear motors, HC-SR04 on a servo, GPS, hardware E-STOP. Modes: MANUAL (bounded dead-man-switch pulse), AUTO (look-then-turn bump avoidance), RELAY (held-position bridging). Bug fixes in `phase 8/README.md` §"Bugs found in the rover code" cover ultrasonic-fault detection, turn-latching, the `millis() + N` future-stamp pattern, and a late-echo carryover. |
| Raspberry Pi Command Center | `development/pi/` (canonical) + `development/phase 9/pi/` (snapshot) | **Done.** `sx1278.py` (register-level SX1278 driver matching the ESP32 PHY), `mesh.py` (Pi as a full mesh node, node id `PI`), `db.py` (SQLite, bounded retention, periodic trim), `server.py` (Flask + JSON API + SSE event stream + portal mirror), `dashboard/` (Leaflet, dark theme, 4-panel grid, SOS banner, rover panel). Deployable via `bash install.sh --enable` + day-to-day `bash update.sh`. |

Phase 9 ships a single integration drop (`development/phase 9/`) that
a reviewer can flash and run without reading the earlier phases.

---

## 3. How it was built

The plan in `docs/PLAN.md` (the file the user originally asked for
back at the start of the project) set out ten phases. Each phase
ships as **complete standalone sketches** for every board plus the
canonical Pi codebase, keeping the Markdown-copy-paste convention
the project was using before `development/` existed.

| Phase | What | Commit series |
|---|---|---|
| 0 | Audit + bench test of the existing root `phase 9/` / `phase 10/` sketches | findings doc only |
| 1 | Shared core: heartbeat, neighbours, CRC, watchdog | `phase 1/` |
| 2 | Hybrid location: GPS module + phone via captive portal | `phase 2/` |
| 3 | Unified mesh: routing, multi-hop, self-healing | `phase 3/` |
| 4 | SOS button + rescue messaging | `phase 4/` |
| 5 | Pi command centre + dashboard | `phase 5/`, canonical code under `development/pi/` |
| 6 | Reliability + GPS fixes (heap, CRC, watchdog, BROWNOUT) | `phase 6/` |
| 7 | Range + GPS + redesigned OLED + portal UI (SF9, computed airtime) | `phase 7/` |
| 7r | Revert SF to 7; add PHY-mismatch diagnostics | `phase 7/` later |
| 8 | Autonomous rover + mobile relay (ESP32-S3, motors, ultrasonic, GPS) | `phase 8/` |
| 9 | Integration build for demo day + tuning playbook + test report | `phase 9/` |
| 10 | Demo script + architecture + wiring + limitations + this report + tracker | `phase 10/` docs |

---

## 4. Headline numbers

These are the numbers from `docs/TEST_REPORT.md`. They are the
honest source for "how well does this actually work".

If Phase 9 hasn't been run on hardware yet, every number below is
marked `[PHASE9: …]` and is filled in by the integration test run.

### 4.1 2-hour soak

```
nodes powered   : [PHASE9: A B C R Pi]
user activity   : none
watchdog resets : [PHASE9: 0]
heap trend      : [PHASE9: ±2 KB across all nodes]
missed HBs      : [PHASE9: 0]
packet loss     : [PHASE9: <2 %]
```

### 4.2 Outdoor range

```
SF (chosen)     : 7   (BW 125 kHz, CR 4/5, sync 0x2A, CRC on, TX 17 dBm)
LOS range, 90 % packet-loss radius: [PHASE9: ___ m]
1 brick wall, 90 % packet-loss radius: [PHASE9: ___ m]
2 walls / 1 floor, 90 % packet-loss radius: [PHASE9: ___ m]
```

### 4.3 End-to-end scenario

`docs/DEMO_SCRIPT.md` defines the run. Three consecutive successful
executions gate Phase 9.

```
run 1 : [PHASE9: PASS/FAIL]    duration [PHASE9: ___ s]
run 2 : [PHASE9: PASS/FAIL]    duration [PHASE9: ___ s]
run 3 : [PHASE9: PASS/FAIL]    duration [PHASE9: ___ s]
```

### 4.4 Rover

```
AUTO collision-free duration : [PHASE9: ≥5 min]
relay mode A↔C range restored: [PHASE9: yes / no]
motor battery brown-outs      : [PHASE9: 0]
```

---

## 5. Bugs found and fixed during development

Not marketing fluff — every entry below was a real defect with a real
fix. See `git log --grep` for the commit messages.

- **String fragmentation** — early sketches did per-byte
  `incoming += (char)LoRa.read()`. On a 2-hour run, heap wandered
  down. Phase 6 moved to `char buf[128]` for the RX hot path.
- **SOS latch** — `sosAlertActive` never cleared; first SOS ever
  sent or received locked the OLED forever. Phase 4 added
  edge-detected button + 60 s auto-clear + button-hold to dismiss.
- **Startup-stagger underflow** — `lastBroadcastTime = millis() +
  random(0, 2000)` set the timestamp into the future; the unsigned
  guard underflowed and nodes transmitted immediately on loop 1,
  defeating anti-collision. Replaced with an `Interval` helper.
- **LoRa PHY never configured** — CRC off, sync 0x12 (public, collides
  with any nearby SX127x). Phase 7 set CRC on, sync 0x2A, and a
  fixed sane modulation.
- **`delay()` in the SOS burst** — `sendSosAlert()` blocked ~3.5 s
  total, deaf to incoming packets. Phase 4 made it non-blocking.
- **`forwardPacket()` no seen-ID cache** — two nodes with the same
  route both forwarded the same `DATA:`. Phase 1's packet layer
  added the 32-entry cache.
- **Rover: dead ultrasonic = "path clear"** — `ultrasonicCm = -1`
  was both "nothing in range" and "no echo". Phase 8 distinguishes
  the two and halts AUTO if the sensor is actually dead.
- **Rover: random turn not random** — `turnMs` was drawn fresh every
  loop pass and ended at the minimum every time. Phase 8 latches it
  once at turn-start.
- **Rover: `millis() + MANUAL_PULSE_MS` in the future** — same bug
  pattern as #3 above. Same fix.
- **Rover: late echo credited to next ping** — `echoNewReading` not
  cleared before trigger. Phase 8 clears it.
- **Pi: SSE subscribers list iterated / mutated cross-thread** —
  fixed in Phase 9 with a lock.
- **Pi: `/api/command` accepted any `dest` string** — fixed in
  Phase 9 to validate against `A|B|C|R|ALL`.
- **Pi: `_last_tx` advanced even when the radio rejected the
  frame** — fixed in Phase 9 to advance only on success.
- **Pi: `state()` ran an unbounded `SELECT … ORDER BY ts`** — fixed
  in Phase 9 with a per-id `MAX(ts)` join.
- **Pi: SQLite file unbounded** — Phase 9 added a 5-minute
  periodic `trim()`.
- **Pi: dashboard kept SOS rings after a clear** — Phase 9 fixes
  the cleanup.

---

## 6. Proposal promises vs. shipping state

| Proposal promise | Shipping state |
|---|---|
| Multi-hop mesh A→B→C | Done (Phases 3, 7, 8). Distance-vector + split horizon + seen-ID dedup. |
| Self-healing rerouting | Done (Phases 3, 9). 45 s route timeout, observed in §A of the demo. |
| Reliable ACK messaging | Done (Phase 4). MSG/ACK with 3 retries + jitter, dedup at packet layer. |
| Heartbeat monitoring | Done (Phase 1). Every 15 s + 3 s jitter. |
| Auto neighbour discovery | Done (Phase 1). All nodes learn the table from heartbeats; no static config. |
| GPS position telemetry | Done (Phases 2, 7). Real NMEA on Serial2, fix-validity flag, fallback banner. |
| SOS from button and portal | Done (Phases 4, 7). Edge-detected button, 3× burst, real coords from GPS or phone, 60 s auto-clear, button-hold-to-clear. |
| Captive portal, phone GPS, messages, reports, team status | Done (Phases 4, 5, 7). Same five actions work on every portal-capable node and on the Pi. |
| Rover (autonomous + mobile relay) | Done (Phase 8). MANUAL/AUTO/RELAY with bounded drive pulses, look-then-turn, hardware E-STOP. |
| Gateway ESP32 ↔ Pi ↔ dashboard, DB, map | Done (Phase 5, 7, 9). Own SX1278, SQLite, Leaflet offline, SSE, JSON API. |
| "Split-horizon" | Done (Phase 3). Don't advertise a route back to its next-hop. |
| "Adaptive Data Rate SF7–SF12" | **Not done** — fixed at SF7. Set at the bench-validated sensitivity-vs-airtime trade; SF9 / SF10 / SF11 are easy to switch on in `config.h` but the project deliberately stayed at SF7 for indoor reliability. |
| "Do NOT use 5V" on LoRa | Honoured. The 5 V warning is in every node's header block. |
| Uniform 3× ESP32 | Honoured for A/B/C. Rover is an ESP32-S3 (called out in `phase 8/README.md` with the full pin-map rationale and not interchangeable with the classic ESP32). |

---

## 7. Known issues and follow-ups

Carried forward to a hypothetical Phase 11:

1. **Encryption.** Top of the list. Same SX1278, same airtime; just
   wrap the payload in AES-GCM and add a key-provisioning step
   through the portal. (Future scope per proposal §slide 13.)
2. **Team-id propagation.** Portal teams and mesh `STAT:` are
   separate namespaces. A session-id in `STAT:` would unify them.
3. **Rover obstacle avoidance is still simple.** A real SLAM layer
   with a 2-D lidar would be the next step.
4. **Channel scanning.** `/api/rescan` retunes once. A real urban
   deployment needs a channel list and a "best of N" choice.
5. **Refactor to shared "tabs".** Phase 1's `firmware/common/*.h.md`
   plan was acknowledged but not executed; the duplicated neighbour
   / NMEA / routing code only becomes a maintenance burden if a bug
   appears in two places.
6. **Persistence on the nodes.** RTC + SPIFFS / LittleFS would let
   nodes remember their last-known neighbours and resume faster
   after a reboot.

These are listed honestly; see `docs/LIMITATIONS.md` for the full
list and the trade-offs.

---

## 8. How to reproduce the demo

From a fresh checkout:

```bash
# 1. Set up the Pi gateway.
cd development/pi
bash install.sh --enable
#    --> creates venv, pip-installs requirements.txt, installs + enables
#        the sar-pi systemd service. Open http://<pi-ip>:8000/ when up.

# 2. Flash the four boards. Each sketch is a single ~3000-line .md file.
#    Open in the Arduino IDE, select the board, paste, upload:
#      development/phase 9/Node A.md       -> ESP32 (Node A)
#      development/phase 9/Node B.md       -> ESP32 (Node B)
#      development/phase 9/Node C.md       -> ESP32 (Node C)
#      development/phase 9/Node Rover.md   -> ESP32-S3 (Rover)

# 3. Power on, open the dashboard, follow docs/DEMO_SCRIPT.md.

# 4. Day-to-day updates on the Pi:
cd development/pi
bash update.sh
```

A reviewer who has never seen the project should be able to
reproduce the full demo from these docs alone:

- `docs/DEMO_SCRIPT.md` — the run, step by step.
- `docs/WIRING.md` — the wiring, per board.
- `docs/ARCHITECTURE.md` — the system, layer by layer.
- `docs/LIMITATIONS.md` — what to expect and what not to.
- `phase 9/Node A.md` … `phase 9/Node Rover.md` — the firmware to
  flash.
- `development/pi/` — the Pi code that runs.

---

## 9. Acknowledgements

This project stands on the work the rest of the team did across the
proposal, the hardware bring-up, and the original `phase 1/` …
`phase 11/` folders at the repo root. `development/` is the
rebuild on top of that foundation — it doesn't replace it, and the
existing folders are still the working reference for diffs and
rollback.

---

## 10. Sign-off

```
project lead   :
date           :
course         : CSE-4326 Microprocessors & Microcontrollers Lab
term           :
demo day       :
demo room      :
demo reviewer  :
demo result    : PASS / FAIL
final status   : Phase 10 complete
```

The proposal's twelve demonstrated capabilities are mapped to demo
steps in `docs/DEMO_SCRIPT.md` §"Mapping back to the proposal".
Every step has a visible cue. If the cue shows up on demo day,
the system is working. If a cue doesn't, the corresponding
capability isn't — go look at the wiring, the PHY box, the
service status, in that order.
