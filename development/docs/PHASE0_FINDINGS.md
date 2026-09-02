# Phase 0 — Existing-System Audit & Feasibility Bench Test

**Goal:** confirm what actually works on real hardware, get real numbers (range, collision loss,
GPS fix time, heap trend), and reproduce the two known critical bugs — *before* writing any new
firmware. Uses the **existing** `phase 9/` and `phase 10/` sketches only. No code changes.

**Tester:** ______________  **Date:** ______________
**Hardware used:** 3× ESP32 + SX1278 (433 MHz) + OLED · GPS: ________ (NEO-6M / NEO-M8N) · power: ________

> Tip: for the heap/soak tests, temporarily add one line to the existing sketch's `loop()` throttle
> block — `Serial.printf("heap=%u\n", ESP.getFreeHeap());` — this is a local measurement aid, not a
> committed change. Note in the log if you did this.

---

## Test 1 — 3-radio soak (phase 9 self-healing)

Flash `phase 9/Node A|B|C Self-Healing.md` to the three ESP32s. Run **60 minutes**. Log every ~10 min.

| Time | Node A routes | Node B routes | Node C routes | Any reset? | Free heap A / B / C |
|---|---|---|---|---|---|
| 0 min | | | | | |
| 10 | | | | | |
| 20 | | | | | |
| 30 | | | | | |
| 45 | | | | | |
| 60 | | | | | |

- Routes stayed stable (no flapping): ⬜ yes ⬜ no — notes: __________
- Heap trend (flat / slowly falling / crashed): __________
- **Result:** ⬜ PASS ⬜ FAIL — __________

## Test 2 — Multi-hop + self-heal proof

Place Node A and Node C so they **cannot** hear each other directly (distance, or seal one in
foil); Node B in the middle can hear both. Node A auto-sends `DATA:` to Node C every ~10 s.

- `DATA:` A→C arrives at C via B (`>>> RECEIVED FINAL DATA`): ⬜ yes ⬜ no — hop count shown: ____
- Power off Node B → within the 12 s route timeout Node A/C log `ALERT [SELF-HEALING]` / route lost: ⬜ yes ⬜ no — time observed: ____ s
- Power Node B back on → `RECOVERED ROUTE` / `>>> SELF-HEALED FORWARD` resumes: ⬜ yes ⬜ no — time: ____ s
- **Result:** ⬜ PASS ⬜ FAIL — __________

## Test 3 — GPS reality check (phase 10)

Flash `phase 10/Node A GPS.md` to one node with a real GPS module. Place the GPS antenna near a
window / outdoors.

- Time from power-on to first real fix (`hasGpsFix`, lat/lon non-zero): ______ (⬜ never after 15 min)
- Satellites in view when fixed: ____
- Coordinates plausible for your location: ⬜ yes ⬜ no
- Indoors with no window, does it correctly show "Searching Sats" (not garbage): ⬜ yes ⬜ no
- **Captured raw NMEA log** to `development/fixtures/sample_nmea.txt`: ⬜ done
  (paste ~2 min of the GPS serial output — used later for an indoor replay fixture)
- **Result:** ⬜ PASS ⬜ FAIL — __________

## Test 4 — Collision / loss measurement

All 3 nodes running phase 9. On Node A's serial, count route broadcasts *received* from B and C
over **10 minutes** vs expected (~1 per 5 s per node = ~120 each).

| From | Expected | Received | Loss % |
|---|---|---|---|
| Node B `RT:` | ~120 | | |
| Node C `RT:` | ~120 | | |

- **Result:** loss is ⬜ <10% (good) ⬜ 10–30% (tune beacon rate) ⬜ >30% (problem) — __________

## Test 5 — Reproduce the known bugs (phase 11)

Flash `phase 11/Node A|B|C Rescue Messaging.md`.

- **SOS latch:** press the SOS button on Node A once. Do Node B & C stay stuck on the SOS screen
  forever (never return to the normal `CON:` header)? ⬜ confirmed stuck ⬜ recovered on its own
- **Startup stagger:** power all 3 at once. Do they all transmit their first `TEXT:` almost
  simultaneously (within ~1 s) instead of staggered? ⬜ confirmed simultaneous ⬜ staggered
- Notes: __________

## Test 6 — Range (single link)

Two nodes running phase 9 (or phase 3). Hand-carry one; log RSSI on the stationary node's OLED /
serial at increasing distance, line-of-sight, outdoors.

| Distance | RSSI (dBm) | Packets still arriving? |
|---|---|---|
| 10 m | | |
| 50 m | | |
| 100 m | | |
| 200 m | | |
| ____ m | | |

- Usable single-hop radius at library-default SF7: ______ m
- **Result:** ⬜ PASS (≥100 m) ⬜ MARGINAL ⬜ FAIL

## Test 7 — Wi-Fi + LoRa coexistence

Minimal throwaway sketch on one ESP32: `WiFi.softAP("coexist_test")` + the phase-3 LoRa RX loop.
A second node transmits `Hello #n` every 2 s. Connect a phone to the AP and load any page.

- LoRa packets still received with the AP up + a client browsing: ⬜ yes ⬜ intermittent ⬜ no
- Packet loss vs no-WiFi baseline: ______ %
- Any brown-out / reset when the phone associates: ⬜ no ⬜ yes
- **Result:** ⬜ PASS ⬜ FAIL — __________

---

## Go / No-Go decisions (fill in before starting Phase 1)

- **Spreading factor for `development/` firmware:** ⬜ SF7 ⬜ SF8 ⬜ SF9 — reason: __________
- **Heartbeat / beacon interval:** every ______ s (default 10–15 s; raise if Test 4 loss high)
- **TX power:** ______ dBm
- **Expected usable range per hop:** ______ m
- **GPS strategy for the demo:** ⬜ live outdoors ⬜ NMEA replay indoors ⬜ phone-GPS via portal is primary
- **Any blockers found that change the plan:** __________
