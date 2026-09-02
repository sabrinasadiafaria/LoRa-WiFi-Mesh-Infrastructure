# LoRa-WiFi SAR Mesh — Full Review, Feasibility Assessment & Phase-Wise Development Plan

## Context

This is a **CSE-4326 Microprocessors & Microcontrollers Laboratory** project: an off-grid,
self-healing **LoRa mesh** for Search & Rescue, with a Wi-Fi captive portal, an autonomous
rescue rover, and a Raspberry Pi command center. The proposal (`planing/Project poposal.pdf`,
14-slide deck, presented 1 Sep 2026) has **already been approved** — the goal now is to turn a
working-looking pile of copy-paste sketches into a **reliable, demonstrable, impressive** system.

The user has confirmed:
- **Hardware in hand:** 3× ESP32 + LoRa SX1278 (433 MHz) + OLED, NEO-6M/M8N GPS modules,
  push buttons + breadboard/power, Raspberry Pi + rover chassis/motor/ultrasonic parts.
- **Timeline:** approved, no hard checkpoint — proceed, but keep every phase independently demoable.
- **Code style:** keep the **Markdown copy-paste sketch** convention (one file per node, pasteable
  into Arduino IDE). New work lives under `development/`. **Do not touch the existing `phase N/` files.**
- **Must be in the final demo:** (1) reliable multi-hop mesh + self-healing, (2) SOS + live GPS,
  (3) Wi-Fi captive portal, (4) Raspberry Pi command center + dashboard.

This document is the deliverable the user asked for: sections 1–15 below, then the phase plan.
**No code changes yet — waiting for approval of this plan.**

---

## 1. Existing Project Structure

Documentation-and-code-snippet repo. **No `.ino`/`.cpp`/`.h`, no `platformio.ini`, no build system,
no `.gitignore`, no CI.** Every sketch is a full standalone program pasted inside a `.md` file.

```
LoRa-WiFi-Mesh-Infrastructure/
├── README.md                       # pitch; stale (only mentions phase 1)
├── Project idea.md                 # architecture narrative
├── PLan.md                         # 16-phase roadmap + packet-format reference
├── Project_Overview_And_Features.md# richest doc: 16-phase table + 12 "advanced features"
├── Hardware_Connections.md         # per-node wiring tables (assumes 3× plain ESP32)
├── Progress_Tracker.md             # test checklist: Phase 10 ✓, Phase 11 unchecked
├── X.md, abc.md                    # empty (0 bytes)
├── planing/  (untracked)           # "Project poposal.pdf" — the approved proposal deck
├── phase 1/   (7 files)            # OLED tests + LoRa TX/RX bring-up (this IS "Phase 2" too)
├── phase 3/   (2)  two-way non-blocking messaging
├── phase 4/   (2)  MSG/ACK reliable transport, retries, dedup
├── phase 5/   (2)  HB heartbeat, 12 s dead-node timeout
├── phase 6/   (2)  dynamic neighbor table
├── phase 7/   (2)  distance-vector routing advertisements (RT:)
├── phase 8/   (3)  multi-hop forwarding (DATA:), adds Node C (Nano/Uno)
├── phase 9/   (3)  self-healing: dead-route invalidation + failover + recovery
├── phase 10/  (3)  real NMEA GPS parsing on Serial2, GPS: telemetry
└── phase 11/  (3)  TEXT: messaging + hardware SOS button + full-screen SOS OLED  [in progress]
```
No `phase 2/`. Phases 12–16 (rover, Pi, dashboard, optimization, docs) are roadmap text only.

**Hardware target drift across phases:** early phases mix ESP32 + ESP32-S3 (Node B, SPI 12/13/11)
+ Arduino Nano/Uno (Node C, 2 KB RAM); phase 10/11 converge Node B/C back to plain ESP32.
`Hardware_Connections.md` documents the final intent: 3× identical ESP32, LoRa on 5/14/26 + SPI
18/19/23, OLED I2C 21/22, GPS on Serial2 16/17, SOS button GPIO 4.

**Packet protocol (all ASCII, colon-delimited, no CRC / length / auth):**
| Type | Format | Phase |
|---|---|---|
| `MSG` / `ACK` | `MSG:ID:PAYLOAD` / `ACK:ID:OK` | 4 |
| `HB` | `HB:NODE_ID:UPTIME` | 5–6 |
| `RT` | `RT:SENDER:DEST1,HOPS1;DEST2,HOPS2;…` | 7–9 |
| `DATA` | `DATA:SRC:DEST:HOPS:MSG_ID:PAYLOAD` (TTL = MAX_HOPS 5) | 8–9 |
| `GPS` | `GPS:SRC:LAT:LON:BAT:UPTIME` | 10 |
| `TEXT` | `TEXT:SRC:DEST|ALL:MSG_ID:body` | 11 |
| `SOS` | `SOS:SRC:LAT:LON:MAYDAY text` (sent 3×) | 11 |

**Libraries actually used:** `LoRa` (Sandeep Mistry), `U8g2` (Node A / SH1106), `Adafruit_GFX`
+ `Adafruit_SSD1306` (Node B/C), `Wire`, `SPI`, ESP32 `HardwareSerial`. **No `WiFi.h`, no
`WebServer`, no `DNSServer`, no `TinyGPS++`, no crypto, no SPIFFS/LittleFS anywhere.**

---

## 2. Current Implementation Status

| Capability | Status | Notes |
|---|---|---|
| OLED bring-up (SH1106 + SSD1306, 3 platforms) | **Implemented & HW-tested** | Extensive commit history of real-device fixes |
| LoRa point-to-point @ 433 MHz | **Implemented & HW-tested** | Library-default PHY (SF7/BW125/CRC off/sync 0x12) |
| Two-way non-blocking messaging | **Implemented** (phase 3) | |
| Reliable MSG/ACK + retry + dedup | **Implemented** (phase 4 only) | **Not carried into phase 10/11** |
| Heartbeat + dead-node timeout | **Implemented** (phase 5–6 only) | Dropped after phase 6; phase 11 uses the TEXT beacon as a keepalive |
| Dynamic neighbor discovery | **Implemented** (phase 6) / **partial** (phase 10–11) | Phase 10–11 use a cut-down fixed `[5]`/`[3]` array |
| Distance-vector routing (`RT:`) | **Implemented** (phase 7–9 only) | Split-horizon *claimed* but *not* implemented |
| Multi-hop forwarding (`DATA:`) | **Implemented** (phase 8–9 only) | No duplicate/seen-ID cache on forward |
| Self-healing (invalidate + failover + recover) | **Implemented** (phase 9 only) | **Not in shipping firmware (phase 10/11)** |
| Real GPS NMEA parsing | **Implemented** (phase 10) | Hand-rolled `$GxRMC`/`$GxGGA`; **regressed** — phase 11 never reads GPS |
| GPS telemetry broadcast | **Implemented** (phase 10) | |
| TEXT messaging | **Partial / not real messaging** | DEST hardcoded `ALL`; body is auto-counter `"Rescue Active #n"`; no input path |
| Hardware SOS button + 3× broadcast | **Implemented** (phase 11) | Sends **hardcoded** coords; blocking; button has no edge detection |
| Full-screen SOS OLED takeover | **Implemented** (phase 11) | `sosAlertActive` **never clears** (permanent lockout) |
| Battery telemetry | **Stub** | `batteryLevel = 98/94/92` literals, never sampled |
| Wi-Fi AP / captive portal / web UI | **Not implemented** | Doc-only |
| Raspberry Pi gateway / dashboard | **Not started** | |
| Autonomous rover | **Not started** | |
| Encryption / binary protocol / DTN / sensors | **Not started** (listed as "advanced") | |

**Legend:** Implemented = code exists and was run on hardware; Partial = works but incomplete/degraded;
Not started = roadmap only.

---

## 3. Project Proposal Summary

**Title:** "Off-Grid LoRa-Based Self-Healing Mesh Communication Infrastructure, with an Autonomous
Rescue Rover for Emergency Search & Rescue Operations."

**Problem:** disasters destroy the cellular/power/internet infrastructure that rescue depends on;
the 24–72 h survival window is lost to poor coordination; rescuers must physically enter hazardous
structures to check for survivors; dedicated GPS fails indoors/under debris.

**Four integrated deliverables:**
1. **LoRa Mesh Nodes** — long-range, multi-hop forwarding, auto neighbor discovery, reliable
   ACK messaging, heartbeat monitoring, self-healing rerouting.
2. **Wi-Fi Captive Portal** — every capable node runs a SoftAP + captive portal; any smartphone
   browser (no app) registers a User/Team ID, shares phone GPS, raises SOS, sends short messages,
   files one-tap rescue reports (Victim Found / Medical / Blocked / Danger), updates team status.
3. **Autonomous Rover** — ESP32 + LoRa + 2WD/4WD chassis + L298N/TB6612 + HC-SR04 + GPS.
   Autonomous obstacle-avoidance exploration; **full mesh member**; **mobile LoRa relay** that
   physically repositions to bridge separated nodes.
4. **Raspberry Pi Command Center** — gateway ESP32 ↔ Pi over UART/USB; Python service; local DB
   (SQLite / InfluxDB); offline web dashboard with Leaflet/Mapbox map, node health, telemetry
   charts, prominent SOS alerts.

**Software stack (proposal):** Arduino/PlatformIO/C++; ESP32 SoftAP + HTTP + captive portal +
LoRa; Pi = Python + serial + local storage; web = HTML/CSS/JS; phone = Browser Geolocation API
with hybrid GPS fallback.

**Demonstrated-capabilities checklist (the de-facto rubric, slide 12):** long-range link,
multi-hop routing, auto discovery, reliable ACK messaging, heartbeat, self-healing, captive
portal, mobile GPS sharing, SOS alerts & reports, team status, autonomous rover run, mobile relay.

**Explicitly deferred to "Future Scope":** camera, thermal detection, gas/smoke, AI victim
detection, offline maps, drones, **encryption**, solar, real field trials. **No timeline, no
Gantt, no numeric grading rubric in the proposal.**

---

## 4. Proposal vs Current Implementation

| Proposal promise | Reality in code | Gap |
|---|---|---|
| Multi-hop mesh A→B→C | Exists in phase 8–9, **not** in shipping phase 10/11 | **Regression to re-integrate** |
| Self-healing rerouting | Exists in phase 9, **not** in phase 10/11 | Same |
| Reliable ACK messaging | Phase 4 only | Not in mesh firmware |
| Heartbeat monitoring | Phase 5–6 only | Replaced by ad-hoc TEXT beacon |
| Auto neighbor discovery | Full in phase 6; cut-down in phase 10–11 | Needs unifying |
| GPS position telemetry | Phase 10 works; phase 11 ignores GPS | **Wire GPS into SOS/telemetry** |
| SOS from button **and** portal | Button only; coords hardcoded; latch bug | Fix + add portal trigger |
| Wi-Fi captive portal, phone GPS, messages, reports, team status | **0 lines of code** | **Build from scratch** |
| Rover (autonomous + mobile relay) | **Nothing** | **Build from scratch** |
| Gateway ESP32 ↔ Pi ↔ dashboard, DB, map | **Nothing** | **Build from scratch** |
| "Split-horizon / distance-vector loop avoidance" | Claimed; only a partial count-to-infinity guard + timeout | Implement properly or reword claim |
| "Adaptive Data Rate SF7–SF12" | Not implemented; PHY never configured | Out of must-have scope; set a fixed sane PHY instead |
| LoRa on 3.3 V, "Do NOT use 5V" | Consistent in docs | OK |
| Uniform 3× ESP32 | Code still carries S3 + Nano variants in old phases | New code standardizes on 3× ESP32 |

**Missing requirements not yet anywhere:** message input mechanism; SOS acknowledgement/clear;
node persistence (IDs, last position) across reboot; any packet integrity check; a documented,
frozen packet spec; power/battery measurement; watchdog; field range test data.

---

## 5. Working Features (safe to demo today, from existing `phase N/` files)

- **Phase 1:** OLED (SH1106 + SSD1306) and LoRa SX1278 init on ESP32; LoRa TX (Node A) → RX with
  RSSI on OLED (Node B).
- **Phase 3:** bi-directional non-blocking `Hello` exchange, RSSI on OLED.
- **Phase 4:** `MSG:ID:payload` with automatic `ACK:ID`, 3 retries + backoff jitter, duplicate
  filtering, delivery-confirmed / delivery-failed states.
- **Phase 5:** `HB:` heartbeat every 5 s, target ONLINE/OFFLINE with 12 s timeout.
- **Phase 6:** neighbor table auto-populated from heartbeats; NEW / RECONNECTED / LOST events.
- **Phase 7:** `RT:` advertisements, routing table with hop counts, serial table printout.
- **Phase 8:** `DATA:` end-to-end with hop TTL; Node A → Node C via Node B.
- **Phase 9:** kill Node B → route invalidated → failover; restore Node B → route recovered.
- **Phase 10:** real GPS fix parsed from NEO-6M/M8N on Serial2; `GPS:` telemetry; "Searching
  Sats" fallback; OLED shows lat/lon/sats + connected-node list.
- **Phase 11 (partial):** press SOS button → 3× `SOS:` broadcast → **all in-range nodes** show a
  full-screen SOS screen with victim ID + coordinates; periodic `TEXT:` beacons keep the
  connected-node list alive.

---

## 6. Incomplete / Missing Features

**Partial:** phase-11 TEXT "messaging" (no way to type a message; DEST always ALL);
phase-11 SOS (hardcoded coords, blocking burst, latch); neighbor table in phase 10–11
(fixed size, no full-table handling); GPS validity check (`!= 0.0` rejects equator/meridian).

**Regressed (worked earlier, dropped later):** multi-hop routing, forwarding, self-healing,
real heartbeat, reliable ACK — none of these are in phase 10/11.

**Never started:** Wi-Fi SoftAP; DNS captive-portal redirect; HTTP server + portal pages;
Browser-Geolocation phone GPS; rescue reports; team status; gateway serial bridge; Pi Python
service; local DB; web dashboard + map; rover motor control; rover obstacle avoidance; rover
mesh membership; rover mobile-relay logic; persistence; packet CRC/auth; watchdog; battery ADC.

---

## 7. Problems / Bugs Found (verified in code)

**Critical:**
1. **`sosAlertActive` never resets** (`phase 11/Node A:125,232` + B + C). After the first SOS
   ever sent or received, the OLED is stuck on the SOS screen permanently and normal RX display
   is suppressed. No timeout, no button-to-clear.
2. **Startup-stagger integer underflow.** `lastBroadcastTime = millis() + random(0,2000)` sets
   the timestamp into the future; the unsigned guard `millis() - lastBroadcastTime > interval`
   underflows to a huge number → node transmits immediately on loop 1, defeating the anti-collision
   stagger. Present in `phase 11` A:194 / B:189 / C:191 and `phase 10` B:34 / C:34.
3. **Blocking `delay()` deafens the half-duplex radio.** `sendSosAlert()` blocks ~1.5 s
   (3× `delay(500)`), then `loop()` adds `delay(2000)` — ~3.5 s during which no incoming SOS/
   packet is received. Also setup ≈5 s of delays, `delay(50/100)` in button + forward paths.
4. **No multi-hop in shipping firmware** — the proposal's core promise is unmet by phase 10/11.

**High:**
5. `int msgId` is parsed but never used in phase 11 RX → **no duplicate filtering**; duplicate
   packets re-fire OLED writes; also a compiler warning.
6. `while(1);` hard-hang on LoRa init failure, **no watchdog** anywhere → frozen "safety" device.
7. **Pervasive `String`** — per-byte `incoming += (char)LoRa.read()`, `String` struct members,
   many concatenated temporaries every loop → ESP32 heap fragmentation over long runs; on the
   2 KB AVR Node C (old phases) likely instability (commit history shows repeated stabilization
   patches).
8. **SOS button:** level-triggered, no release/edge detection → holding it re-fires SOS +
   `delay(2000)` every ~2 s. Also GPIO 4 in code vs "BOOT / GPIO 0" in `Progress_Tracker.md`
   and the overview — doc/code mismatch.
9. **Weak RNG seed** `randomSeed(analogRead(0)+millis())` — GPIO0 is a strapping pin, near-constant;
   all three nodes seed alike → correlated jitter, partially defeating collision avoidance.
   (Phase 4 correctly used ADC1 `analogRead(34)`.)

**Medium:**
10. Split-horizon claimed but not implemented; count-to-infinity only bounded by `MAX_HOPS`+timeout.
11. `forwardPacket()` has no seen-ID cache → two nodes with a route both forward → duplicate storms.
12. LoRa PHY never configured: CRC **off**, default sync word `0x12` (collides with any nearby
    SX127x traffic), no explicit SF/BW/TX-power.
13. `Serial2.readStringUntil('\n')` blocks up to 1000 ms if GPS unplugged.
14. `parseNmeaCoord` assumes exactly 2 minutes-digits (`dotIdx-2`) and uses exact-float validity.
15. `LoRa.beginPacket()/endPacket()` return values never checked; TX failures invisible.
16. Severe **copy-paste duplication** — neighbor code in 6 files, NMEA parser byte-identical in 3,
    routing code across 3 phases × 3 nodes, `setup()` LoRa block ~20×. Bug fixes don't propagate;
    phase 10 vs 11 neighbor code has already diverged (15 s vs 30 s timeout, different prefix
    stripping).
17. Emoji strings (`"🚨 SOS EMERGENCY 🚨"`) won't render in the base bitmap fonts.
18. `X.md`, `abc.md` empty; `README.md` stale; typos in many filenames (`PLan.md`, `planing/`,
    `reciver`, `initizile`, `poposal`).

---

## 8. Feasibility Assessment

**Verdict: feasible and appropriately scoped for a Micro-controllers lab project — *if* the
system is rebuilt around one shared, non-blocking, tested code core instead of extending the
current copy-paste chain.** All four must-have capabilities are individually proven technology on
ESP32; the risk is integration and reliability, not possibility.

**Hardware feasibility — HIGH.**
- 3× ESP32 + SX1278 + OLED + GPS + button: standard, well-documented, all in hand. LoRa @ 433 MHz
  on 3.3 V is correct. SX1278 max payload 255 B >> our packets.
- ESP32 can run SoftAP + HTTP + captive portal **and** LoRa SPI **and** GPS UART concurrently —
  this is a common pattern (single core is enough at our packet rates). Wi-Fi + LoRa coexist fine
  (different radios); expect a small current bump — power banks cover it.
- Rover: ESP32 + L298N + 2 DC motors + HC-SR04 is the canonical beginner robotics build. Feasible.
  **Separate battery for motors vs logic is mandatory** (motor brown-outs reset the ESP32).
- Raspberry Pi reading a USB-serial ESP32 gateway and serving a Flask/FastAPI + Leaflet page is
  routine.

**Software feasibility — MEDIUM.** The mesh, GPS, and SOS logic already exist in pieces and
"work" in demos. Consolidating them into one non-blocking loop with a proper packet layer is
straightforward embedded work. The captive portal is new but is a solved pattern
(`WiFi.softAP` + `DNSServer` wildcard + `WebServer` with a catch-all handler). The Pi dashboard
is standard web work. **The rover autonomy is the least contained piece** and should stay
deliberately simple (bump-and-turn obstacle avoidance + manual/relay modes).

**Communication / network feasibility — MEDIUM.** LoRa is half-duplex, low-bandwidth
(~1–5 kbit/s effective at SF7–SF9) and **collision-prone with no MAC**. With 3 static nodes +
1 rover + gateway all beaconing, naive flooding will congest. Mitigations that must be in the
rebuild: single scheduled TX point per node, randomized jitter that actually works (fix bug #2),
a seen-ID cache to kill duplicate forwards, controlled beacon rate (heartbeat ≤ every 10–15 s),
CRC **on**, a private sync word, and short packets. This keeps airtime well under any sane duty
cycle for a lab demo. Realistic indoor/campus range at SF7: 100–300 m; multi-hop is what sells
the demo.

**Power / resource feasibility — MEDIUM-HIGH.** ESP32 + LoRa TX peaks ~120–160 mA; a 5 V power
bank runs a node for many hours — fine for a demo. Long-run heap health on ESP32 requires
dropping `String` from the hot path (fix #7). Node C staying on ESP32 (not the 2 KB Nano) removes
the worst resource risk — the new `development/` code targets **3× identical ESP32** only.

**Sensor / module compatibility — HIGH.** NEO-6M and NEO-M8N both emit standard NMEA at 9600 8N1;
the existing parser handles `$GP*` and `$GN*`. GPS needs **sky view / window** for first fix
(cold fix 30 s–several min) — bench demo needs the "no fix" fallback and ideally an antenna near
a window, or a recorded-NMEA replay mode for indoor rehearsal.

**Reliability — the main deliverable risk.** Current code fails a "leave it running for an hour
with 3 radios" test (latch bug, stagger bug, blocking SOS, heap). Phase 0 exists to prove/fix
exactly this before building upward.

**Real-world usability — adequate for a lab demo, not a field tool.** No encryption (proposal
already defers this), no duty-cycle enforcement, hand-carried nodes. That's an acceptable,
honestly-scoped academic prototype.

**Project complexity / time.** Four subsystems (mesh, portal, Pi, rover) + integration. With the
phased plan below, each phase is a self-contained, demoable checkpoint, so the project degrades
gracefully if time runs short: even stopping after Phase 4 yields an impressive mesh + SOS + GPS
+ captive-portal demo.

---

## 9. Required Testing (before trusting each layer)

**Phase 0 bench tests (do first, on the existing phase 9 + phase 10 sketches):**
1. **3-radio soak:** flash phase 9 to A/B/C, run 60 min, confirm no lockups, routes stable,
   heap (print `ESP.getFreeHeap()` every 30 s) not trending down.
2. **Multi-hop proof:** physically separate A and C (foil-bag or distance) so they only reach via
   B; confirm `DATA:` A→C arrives; kill B; confirm self-heal message; restore B; confirm recovery.
3. **GPS reality check:** phase 10 on one node near a window — does it get a real fix? how long?
   Record raw NMEA to a file for an indoor replay fixture.
4. **Collision measurement:** all 3 beaconing; count RX vs expected over 10 min; quantify loss.
5. **SOS latch / stagger bugs:** reproduce both on phase 11 to confirm the diagnosis.
6. **Range:** hand-carry one node outdoors; log RSSI vs distance at SF7; find the usable radius.
7. **Wi-Fi + LoRa coexistence:** minimal sketch doing `softAP` + LoRa RX simultaneously on one
   ESP32; confirm packet loss is acceptable and no brown-out.

**Per-phase tests** are specified in each phase below. Every phase has a pass/fail completion
criterion.

---

## 10. Technical Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | LoRa congestion / collisions with 4–5 beaconing nodes | High | Med | Single TX scheduler, working jitter, seen-ID cache, CRC on, slow beacons, short packets; measure in Phase 0 |
| R2 | ESP32 heap fragmentation over long demo (String) | Med | High | Static `char[]` buffers in `development/` core; `getFreeHeap()` on OLED during dev; soak test |
| R3 | GPS never gets a fix indoors during the demo | High | Med | "No fix" fallback UI; NMEA-replay fixture; outdoor/window rehearsal; portal phone-GPS as the primary location source |
| R4 | Wi-Fi AP + LoRa + GPS starve each other on one core | Med | Med | Phase 0 coexistence test; keep HTTP handlers tiny & non-blocking; portal node need not also forward heavy mesh traffic |
| R5 | Rover motor noise brown-outs / resets the ESP32 | High | Med | Separate motor battery, common ground, decoupling caps, flyback protection on L298N |
| R6 | Rover autonomy eats all the time | Med | High | Keep it to bump-turn avoidance + manual + relay modes; rover is Phase 6, after everything else works |
| R7 | Captive portal doesn't auto-pop on modern phones (HSTS, private DNS) | Med | Low | Standard 204/redirect handlers for Android/iOS/Windows probes; document "open 192.168.4.1" fallback |
| R8 | Single half-duplex radio: any blocking call drops packets | High | High | Ban `delay()` from `development/` loop; state-machine everything; optional DIO0 RX interrupt |
| R9 | Copy-paste divergence returns | Med | Med | Shared `common/*.h` tab files pasted once; per-node sketch only sets config |
| R10 | Breaking the working `phase N/` reference | Low | High | `development/` is additive; never edit `phase N/`; git branch for dev work |
| R11 | Packet spec keeps changing under subsystems | Med | Med | Freeze `development/docs/PACKET_SPEC.md` v1 in Phase 1; version the protocol byte |
| R12 | Scope creep from the 12 "advanced features" | Med | Med | Explicitly out of scope; revisit only after Phases 0–7 done |

---

## 11. Recommended Architecture

**Keep the Markdown-sketch delivery style, but eliminate duplication via shared "tab" files.**
Arduino IDE supports multiple tabs — a sketch can `#include "mesh_core.h"`. We ship each shared
module as its own `.md` (paste into a new tab of that name) plus one thin per-node `.md`.

```
Node firmware (3× identical ESP32), single cooperative non-blocking loop:
  ┌ radio_layer   : LoRa init, fixed PHY (SF8/BW125/CRC on/private sync word),
  │                 send queue (1 TX per service tick + jitter), RX pump, CRC check
  ├ packet layer  : one framed format  v1|TYPE|SRC|DEST|MSGID|TTL|PAYLOAD  (still ASCII,
  │                 fixed field order, seen-ID cache for dedup + forward suppression)
  ├ mesh layer    : neighbor table + heartbeat + distance-vector routes + forwarding +
  │                 self-healing  (phase 6–9 logic, unified, non-blocking, one table)
  ├ gps layer     : non-blocking Serial2 NMEA reader (phase 10 parser), fix state,
  │                 optional replay-from-flash for indoor demo
  ├ app layer     : SOS (edge-triggered button OR portal), TEXT messaging (portal/serial
  │                 input), rescue reports, team status, telemetry broadcast
  ├ ui layer      : OLED renderer (one abstraction; SH1106 + SSD1306), SOS screen with
  │                 auto-clear timeout + manual clear
  └ portal layer  : (portal-capable nodes) WiFi.softAP + DNSServer(*) + WebServer,
                     static HTML/CSS/JS in PROGMEM, JSON API to app layer, Browser
                     Geolocation → phone position injected as a GPS source
Gateway node = a normal mesh node + serial framing to the Pi (no portal, no GPS needed).
Rover node   = a normal mesh node + motor/ultrasonic control + MOVE/relay commands.
Raspberry Pi:
  serial_reader.py → SQLite → FastAPI/Flask → static dashboard (Leaflet offline tiles,
  node-health table, live SOS banner, message log, team-status board).
```

**Design rules for all `development/` code:** no `delay()` in `loop()`; no `String` in the RX/
parse/forward hot path (use `char buf[128]`); every subsystem is a `service()` called each loop;
CRC on; private sync word; watchdog enabled; `getFreeHeap()` shown during development; every
constant in one `config.h` tab; packet spec frozen and versioned.

---

## 12. Phase-Wise Development Plan

> Phases are numbered fresh for `development/`. They do **not** overwrite the proposal's Phase 1–16
> numbering — they replace the *forward* work (old Phases 11–16) with a reliability-first path.
> Every phase is independently demoable and has a hard completion criterion.

### Phase 0 — Existing-System Audit & Feasibility Bench Test
- **Goal:** confirm what actually works on hardware; get real numbers for range, collisions, GPS
  fix time, heap trend; reproduce the known bugs.
- **Tasks:** run the 7 tests in §9 using the **existing** `phase 9/` and `phase 10/` sketches;
  record everything in `development/docs/PHASE0_FINDINGS.md`; capture a raw-NMEA log file.
- **Files created:** `development/docs/PHASE0_FINDINGS.md`, `development/fixtures/sample_nmea.txt`.
  **No firmware changes.**
- **Hardware:** 3× ESP32 + LoRa + OLED; 1× GPS; power banks; a way to isolate a node (distance/foil).
- **Software:** Arduino IDE + existing libs; a stopwatch; serial logger.
- **Dependencies:** none.
- **Test method:** follow §9; each test has an explicit observation to log.
- **Expected result:** phase 9 multi-hop + self-heal works; phase 10 gets a GPS fix within a few
  minutes near a window; collision loss and range radius quantified; latch + stagger bugs reproduced.
- **Completion criteria:** `PHASE0_FINDINGS.md` filled with pass/fail + numbers for all 7 tests;
  go/no-go decision on SF and beacon rate recorded.

### Phase 1 — Shared Core Firmware (radio + packet + OLED + non-blocking skeleton)
- **Goal:** one clean, non-blocking node skeleton with a framed, CRC-checked packet layer and a
  reusable OLED renderer — the foundation everything else plugs into.
- **Tasks:** create shared tab files; define & freeze `PACKET_SPEC.md` v1 (versioned, seen-ID
  cache, fixed fields); implement LoRa layer with fixed PHY + TX scheduler + working jitter
  (fix bug #2) + CRC on + private sync word; OLED abstraction over SH1106/SSD1306; enable
  watchdog; ban `delay()`/`String` from hot path; `getFreeHeap()` on screen.
- **Files created:**
  `development/firmware/common/config.h.md`,
  `development/firmware/common/radio_layer.h.md`,
  `development/firmware/common/packet.h.md`,
  `development/firmware/common/oled_ui.h.md`,
  `development/firmware/common/scheduler.h.md`,
  `development/firmware/nodes/Node_A.md`, `Node_B.md`, `Node_C.md` (thin: config + `setup/loop`),
  `development/docs/PACKET_SPEC.md`,
  `development/docs/BUILD_AND_FLASH.md` (which tabs to paste, in what order).
- **Hardware:** 3× ESP32 + LoRa + OLED.
- **Software:** `LoRa`, `U8g2`, `Adafruit_GFX`+`Adafruit_SSD1306`, ESP32 core, `esp_task_wdt`.
- **Dependencies:** Phase 0 (SF + beacon-rate decision).
- **Test method:** flash all 3; each broadcasts a `HB` beacon; confirm every node hears the other
  two, CRC rejects a deliberately corrupted packet, OLED shows neighbor list + free heap; 60 min
  soak — heap flat, no resets (watchdog log clean).
- **Expected result:** rock-solid 3-node beacon network, no blocking, stable heap.
- **Completion criteria:** 60 min soak passes on all 3 nodes; corrupted-packet test rejects;
  `PACKET_SPEC.md` v1 frozen and committed.

### Phase 2 — Unified Mesh: discovery + routing + multi-hop + self-healing
- **Goal:** re-integrate phase 6–9 capability on the new core, in one routing table, non-blocking,
  with real duplicate suppression.
- **Tasks:** port neighbor discovery, `RT:` distance-vector advertisements, `DATA:` forwarding
  with TTL **and seen-ID cache**, route timeout + invalidation + failover + recovery; implement
  actual split-horizon (don't advertise a route back to its next-hop) OR reword the claim;
  OLED shows routes + self-heal status.
- **Files created/modified:** `development/firmware/common/mesh_core.h.md` (new);
  Node_A/B/C `.md` gain `mesh.service()` call; `development/docs/MESH_DESIGN.md`.
- **Hardware:** 3× ESP32 + LoRa + OLED.
- **Software:** as Phase 1.
- **Dependencies:** Phase 1.
- **Test method:** repeat Phase 0 test 2 (A↔C only via B): send `DATA:` A→C, confirm delivery,
  RSSI/hop shown; kill B → "route lost / self-healing" within timeout; restore B → "route
  recovered"; 30 min soak with all 3 → no duplicate storms (log forward counts), heap flat.
- **Expected result:** demonstrable multi-hop + self-healing, better behaved than phase 9.
- **Completion criteria:** multi-hop delivery + kill/restore self-heal demoed on hardware;
  duplicate-forward count ≈ 0 in logs; 30 min soak clean.

### Phase 3 — GPS + SOS + Messaging (real data, non-blocking, bug-free)
- **Goal:** the SAR application layer: live GPS telemetry, working hardware SOS with real coords
  and auto-clearing alert, and actually-typeable messages (via serial for now; portal in Phase 4).
- **Tasks:** port the phase-10 NMEA parser into a non-blocking `gps_layer` + optional flash
  replay; broadcast `GPS:` telemetry from the real fix; SOS = **edge-triggered** button →
  non-blocking 3× staggered `SOS:` (no `delay`) with **current GPS coords** (or last-known +
  a "stale" flag); SOS OLED screen with 60 s auto-clear + button-hold-to-clear (fix bug #1);
  seen-ID dedup on SOS; TEXT messaging with a real payload entered over USB serial
  (`TEXT:SRC:DEST:ID:body`), directed or broadcast; add battery ADC read (voltage divider) or
  clearly label the value simulated.
- **Files created:** `development/firmware/common/gps_layer.h.md`,
  `development/firmware/common/app_sos.h.md`, `development/firmware/common/app_msg.h.md`;
  Node_*.md updated; `development/docs/SOS_AND_GPS.md`.
- **Hardware:** 3× ESP32 + LoRa + OLED + ≥1 GPS + 3 push buttons (+ optional resistor divider
  for battery sense).
- **Software:** as before; no new libs (parser stays hand-rolled).
- **Dependencies:** Phase 2.
- **Test method:** GPS node near window gets fix → `GPS:` telemetry on peers' OLED + serial;
  press SOS on Node A → B & C show SOS screen with A's **real** coords; screen clears after 60 s
  or on button-hold; hold SOS button → exactly one SOS burst, not repeated; send a TEXT from
  serial on B → A shows it; 30 min soak with GPS + beacons → heap flat.
- **Expected result:** press-button-see-location-on-every-node, with correct coordinates and a
  screen that recovers.
- **Completion criteria:** SOS with live coords + auto-clear verified on 3 nodes; no latch, no
  repeat-fire; GPS telemetry visible network-wide; soak clean.

### Phase 4 — Wi-Fi Captive Portal (phone access, no app)
- **Goal:** any smartphone connects to a node's Wi-Fi, a portal opens, and the user can share
  phone GPS, send a message, raise SOS, file a rescue report, set team status — all injected into
  the mesh.
- **Tasks:** on portal-capable nodes (A & C): `WiFi.softAP("SOS_Node_A", ...)`, `DNSServer` on
  port 53 answering every query with the AP IP, `WebServer` on 80 with a catch-all → portal page;
  Android (`/generate_204`), iOS (`/hotspot-detect.html`), Windows (`/ncsi.txt`) probe handlers
  to trigger auto-pop; static HTML/CSS/JS in `PROGMEM` (SEND SOS button, Share Location, Send
  Message, Quick Report presets, Team Status); JS uses `navigator.geolocation` → POST to
  `/api/loc`; ESP32 turns portal actions into `SOS:` / `TEXT:` / `RPT:` / `STAT:` mesh packets;
  keep all handlers non-blocking and short so mesh RX isn't starved.
- **Files created:** `development/firmware/common/portal_layer.h.md`,
  `development/firmware/common/portal_pages.h.md` (PROGMEM HTML/CSS/JS),
  `development/firmware/nodes/Node_A_Portal.md`, `Node_C_Portal.md`;
  `development/docs/CAPTIVE_PORTAL.md`; new packet types `RPT:` and `STAT:` added to
  `PACKET_SPEC.md` (v2, version byte bumped).
- **Hardware:** 3× ESP32 (A & C portal, B relay), a smartphone.
- **Software:** ESP32 core `WiFi`, `WebServer`, `DNSServer` (all bundled with the ESP32 board
  package — no external libs).
- **Dependencies:** Phase 3; Phase 0 test 7 (coexistence) must have passed.
- **Test method:** phone connects to `SOS_Node_A` → portal auto-opens (or `192.168.4.1`);
  "Share Location" → Node B/C OLED + serial show the phone's coordinates tagged as phone-GPS;
  "SEND SOS" → SOS screen on all nodes; send a message → appears on target node; file a report /
  set status → shows on peers; run mesh soak with a phone attached → mesh packet loss still
  acceptable (compare to Phase 2 numbers).
- **Expected result:** the headline "any phone, no app" demo.
- **Completion criteria:** portal auto-pops on a real Android or iOS phone; all 5 portal actions
  produce the correct mesh packet and peer-visible result; mesh stays healthy with AP active.

### Phase 5 — Raspberry Pi Command Center + Dashboard
- **Goal:** a gateway ESP32 feeds all mesh traffic to a Pi that stores it and serves a live
  offline web dashboard with a map, node health, SOS banner, message log, team board.
- **Tasks:** gateway sketch = mesh node (no portal/GPS) that prints every received packet as a
  framed line over USB serial (and can inject commands from the Pi → mesh); Pi
  `serial_reader.py` parses frames → SQLite (`nodes`, `positions`, `messages`, `sos`, `reports`,
  `status`); `api.py` (FastAPI or Flask) serves REST + a Server-Sent-Events stream; static
  dashboard: Leaflet with **pre-downloaded offline tiles** for the demo area, node markers +
  trails, health table (last-seen, RSSI, battery, hops), red SOS banner with location + "focus
  on map", scrolling message log, team-status board; `systemd` unit so it runs on boot.
- **Files created:**
  `development/firmware/nodes/Node_Gateway.md`,
  `development/pi/serial_reader.py`, `development/pi/api.py`, `development/pi/db.py`,
  `development/pi/schema.sql`, `development/pi/requirements.txt`,
  `development/pi/dashboard/` (`index.html`, `app.js`, `style.css`, `tiles/`),
  `development/pi/README.md`, `development/pi/sar-dashboard.service`,
  `development/docs/COMMAND_CENTER.md`.
- **Hardware:** 4× ESP32 (A, B, C + gateway), Raspberry Pi + USB cable + screen.
- **Software:** Python 3, `pyserial`, `fastapi`+`uvicorn` (or `flask`), `sqlite3` (stdlib),
  Leaflet (vendored locally), offline tiles.
- **Dependencies:** Phase 4 (packet spec v2 frozen).
- **Test method:** full network + gateway + Pi running; trigger SOS from a phone portal → SOS
  appears on the dashboard within ~2 s with correct map location; move a GPS node → marker/trail
  updates; kill Node B → dashboard health table flips it to offline and shows the self-heal;
  send messages / reports / status → all appear; reboot Pi → service auto-starts and backfills
  from SQLite.
- **Expected result:** commander's-eye-view screen — the second headline demo.
- **Completion criteria:** every mesh event type visible on the dashboard end-to-end; map works
  fully offline; survives a Pi reboot.

### Phase 6 — Autonomous Rescue Rover (+ mobile LoRa relay)
- **Goal:** a mobile ESP32 node that drives itself with obstacle avoidance, is a full mesh member,
  reports its telemetry, and can be commanded to reposition as a relay.
- **Tasks:** rover sketch = mesh node + `motor_layer` (L298N: fwd/back/left/right/stop) +
  `ultrasonic_layer` (HC-SR04, non-blocking ping) + GPS; modes: `MANUAL` (portal/dashboard
  arrow commands via `MOVE:` packets), `AUTO` (bump-turn: drive forward, on obstacle < 25 cm
  stop→back→turn), `RELAY` (hold position, just forward mesh traffic); broadcast
  `ROVER:id:mode:obstacle:battery:lat:lon`; dashboard gets a rover panel + drive buttons;
  **separate motor battery, common ground, flyback diodes, decoupling caps**.
- **Files created:**
  `development/firmware/nodes/Node_Rover.md`,
  `development/firmware/common/motor_layer.h.md`,
  `development/firmware/common/ultrasonic_layer.h.md`,
  `development/docs/ROVER.md`; `MOVE:` / `ROVER:` added to `PACKET_SPEC.md` (v3);
  dashboard rover panel in `development/pi/dashboard/`.
- **Hardware:** 1× ESP32, 2WD/4WD chassis, 2 DC motors, L298N (or TB6612), HC-SR04, GPS,
  motor battery pack (+ logic battery), caps/diodes.
- **Software:** as before; no new libs.
- **Dependencies:** Phase 5 (dashboard to drive/monitor it); Phase 2 (mesh membership).
- **Test method:** rover joins mesh, appears on dashboard with telemetry; `MANUAL` drive from
  dashboard buttons works; `AUTO` — place obstacles, rover avoids them for 5 min without
  collision or reset; `RELAY` — separate A and C beyond range, drive rover between them, confirm
  A↔C traffic flows only while the rover bridges; motor-noise soak — 10 min driving, ESP32
  never resets (R5).
- **Expected result:** "the robot that is also the network" — the proposal's signature idea.
- **Completion criteria:** autonomous avoidance 5 min collision-free; mobile relay visibly
  restores an A↔C link; no brown-out resets under motor load.

### Phase 7 — Integration, Hardening & Field Test
- **Goal:** all subsystems running together, tuned, and validated at range.
- **Tasks:** full-system run (A+C portal, B relay, gateway, Pi, rover); tune beacon rates / SF /
  TX power from measured loss; add any missing watchdog/reboot recovery; 2 h continuous soak;
  outdoor multi-hop range test with logged RSSI/distance; finalize `PACKET_SPEC.md`; write
  `development/docs/TEST_REPORT.md` with all numbers.
- **Files created:** `development/docs/TEST_REPORT.md`,
  `development/docs/TUNING.md`; small fixes across `common/*` tabs.
- **Hardware:** everything.
- **Dependencies:** Phases 1–6.
- **Test method:** scripted end-to-end scenario (see Phase 7 script in `TEST_REPORT.md`):
  phone SOS → dashboard → dispatch rover → self-heal on node loss → message relay — run 3×,
  all pass; 2 h soak clean.
- **Expected result:** a coherent system, not a set of demos.
- **Completion criteria:** end-to-end scenario passes 3× consecutively; 2 h soak with zero
  unrecovered failures; range data recorded.

### Phase 8 — Final Demonstration Package & Documentation
- **Goal:** everything a grader/evaluator needs.
- **Tasks:** `development/docs/DEMO_SCRIPT.md` (step-by-step 10–15 min live demo mapped to the
  proposal's 12 "demonstrated capabilities"); wiring diagrams / photos; architecture diagram;
  `development/README.md` (how to build, flash, run, in order); update root `README.md` note
  pointing to `development/`; short slide deck / poster; known-limitations section (no
  encryption, duty cycle, indoor GPS) stated honestly; fill `Progress_Tracker.md`-style
  checklist for the new phases.
- **Files created:** `development/README.md`, `development/docs/DEMO_SCRIPT.md`,
  `development/docs/ARCHITECTURE.md`, `development/docs/WIRING.md`,
  `development/docs/LIMITATIONS.md`, `development/docs/FINAL_REPORT.md`.
- **Dependencies:** Phase 7.
- **Test method:** a team member who didn't write the code follows `DEMO_SCRIPT.md` and
  `BUILD_AND_FLASH.md` from scratch and gets a working demo.
- **Completion criteria:** clean-room reproduction succeeds; every proposal "demonstrated
  capability" has a line in the demo script that exercises it.

---

## 13. Recommended `development/` Folder Structure

```
development/
├── README.md                      # start here: what this is, build order, run order
├── docs/
│   ├── PHASE0_FINDINGS.md
│   ├── PACKET_SPEC.md             # frozen, versioned wire format  (the single source of truth)
│   ├── MESH_DESIGN.md
│   ├── SOS_AND_GPS.md
│   ├── CAPTIVE_PORTAL.md
│   ├── COMMAND_CENTER.md
│   ├── ROVER.md
│   ├── BUILD_AND_FLASH.md         # which .md tab goes where, paste order, lib versions
│   ├── ARCHITECTURE.md
│   ├── WIRING.md
│   ├── TUNING.md
│   ├── TEST_REPORT.md
│   ├── LIMITATIONS.md
│   ├── DEMO_SCRIPT.md
│   └── FINAL_REPORT.md
├── fixtures/
│   └── sample_nmea.txt            # recorded GPS stream for indoor replay
├── firmware/
│   ├── common/                    # shared Arduino "tabs", one concept per file (.h.md)
│   │   ├── config.h.md            # ALL constants + per-node #define switches
│   │   ├── scheduler.h.md         # non-blocking service-tick helper (replaces delay())
│   │   ├── radio_layer.h.md       # LoRa init, PHY, TX queue+jitter, RX pump, CRC
│   │   ├── packet.h.md            # frame build/parse, seen-ID cache, version byte
│   │   ├── mesh_core.h.md         # neighbors + routes + forwarding + self-healing
│   │   ├── gps_layer.h.md         # non-blocking NMEA + fix state + flash replay
│   │   ├── oled_ui.h.md           # SH1106/SSD1306 abstraction + screens
│   │   ├── app_sos.h.md
│   │   ├── app_msg.h.md
│   │   ├── portal_layer.h.md      # softAP + DNS + WebServer glue
│   │   ├── portal_pages.h.md      # PROGMEM HTML/CSS/JS
│   │   ├── motor_layer.h.md       # rover only
│   │   └── ultrasonic_layer.h.md  # rover only
│   └── nodes/                     # thin per-device sketches: pick config + call services
│       ├── Node_A.md              # mesh + gps + sos + portal
│       ├── Node_B.md              # mesh relay (+ gps optional)
│       ├── Node_C.md              # mesh + gps + sos + portal
│       ├── Node_Gateway.md        # mesh + serial bridge to Pi
│       └── Node_Rover.md          # mesh + motors + ultrasonic + gps
└── pi/
    ├── README.md
    ├── requirements.txt
    ├── schema.sql
    ├── db.py
    ├── serial_reader.py
    ├── api.py
    ├── sar-dashboard.service
    └── dashboard/
        ├── index.html
        ├── app.js
        ├── style.css
        └── tiles/                 # offline map tiles for the demo area
```

Existing `phase 1/` … `phase 11/` stay **exactly as they are** — the reference/rollback baseline.

---

## 14. Priority Order

1. **Phase 0** — audit & bench test (no code) — *gates every downstream decision.*
2. **Phase 1** — shared core (radio + packet + OLED + non-blocking skeleton).
3. **Phase 2** — unified mesh (multi-hop + self-healing) — *proposal core capability #1.*
4. **Phase 3** — GPS + SOS + messaging with real data & no bugs — *capability #2.*
5. **Phase 4** — Wi-Fi captive portal — *capability #3, first headline demo.*
6. **Phase 5** — Raspberry Pi command center + dashboard — *capability #4, second headline demo.*
7. **Phase 6** — autonomous rover + mobile relay — *proposal signature feature.*
8. **Phase 7** — integration, hardening, field/range test.
9. **Phase 8** — demo script + documentation + final report.

Natural stop points if time is squeezed: after **Phase 4** (mesh + SOS + GPS + portal — already
a strong demo) or after **Phase 5** (adds the command center). The rover is the most droppable.

---

## 15. What We Should Implement First

**Immediately, in order:**
1. Create the `development/` skeleton + `README.md` + empty `docs/` stubs (additive, safe).
2. **Phase 0** hands-on: flash the *existing* `phase 9` sketches to A/B/C and `phase 10` to one
   node, run the 7 tests in §9, fill `PHASE0_FINDINGS.md`, record a raw-NMEA log.
3. Write and **freeze `PACKET_SPEC.md` v1** (framed, versioned, CRC, seen-ID cache).
4. Build **Phase 1** shared core: `config.h`, `scheduler.h`, `radio_layer.h`, `packet.h`,
   `oled_ui.h`, and thin `Node_A/B/C.md`; prove the 60 min soak.

Everything after that follows the phase order. No existing file is modified; all new work is
under `development/`; the Markdown copy-paste convention is preserved (shared code = extra
Arduino tabs, pasted once).

---

## Verification (how we'll know the whole thing works)

- **Per phase:** the explicit completion criteria above, each demoable on hardware.
- **Phase 7 end-to-end script** (run 3×): phone connects to Node A portal → shares location →
  raises SOS → SOS + location appear on every node OLED and on the Pi dashboard map → commander
  dispatches the rover from the dashboard → Node B is powered off → mesh self-heals and the
  dashboard shows it → a TEXT reply from the dashboard reaches Node C → Node B restored → route
  recovers. All steps observable, < 15 min, repeatable.
- **Soak:** 2 h continuous full-system run, `getFreeHeap()` logged, zero unrecovered resets.
- **Range:** logged RSSI-vs-distance table at the chosen SF, multi-hop confirmed beyond
  single-node range.
- **Clean-room:** a teammate reproduces the demo from `development/docs/` alone.
