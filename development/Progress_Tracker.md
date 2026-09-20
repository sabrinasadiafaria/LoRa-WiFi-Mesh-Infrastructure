# Progress Tracker (development/)

Track progress on the **rebuilt** system under `development/`. This
is the development-side mirror of the root `Progress_Tracker.md`
(which tracks the original `phase 1/` … `phase 11/` reference
folder).

Each phase here builds on the previous one. The `phase N/Node X.md`
files are **complete standalone sketches** — flash any one of them
on the matching board to run that phase.

---

## Phase 0 — Audit & bench test

- [ ] Run the existing root `phase 9/` sketch on A/B/C
- [ ] Run the existing root `phase 10/` sketch on one node for GPS
- [ ] Record RSSI / range / collision / heap numbers
- [ ] Reproduce the known bugs (SOS latch, startup-stagger underflow)
- [ ] Fill `docs/PHASE0_FINDINGS.md`

---

## Phase 1 — Shared core firmware

- [ ] Flash `phase 1/Node A.md`, `phase 1/Node B.md`, `phase 1/Node C.md`
- [ ] All three nodes hear each other
- [ ] CRC rejects a deliberately corrupted packet
- [ ] OLED shows neighbour list + free heap
- [ ] 60 min soak — heap flat, no watchdog resets
- [ ] `docs/PACKET_SPEC.md` v1 frozen

---

## Phase 2 — Hybrid location (GPS + phone portal)

- [ ] Portal auto-pops on a real Android / iOS phone
- [ ] GPS node near a window gets a real fix (real NMEA on Serial2)
- [ ] "Share Location" from portal injects phone GPS into the mesh
- [ ] "Searching Sats" fallback banner when no fix yet
- [ ] Wi-Fi + LoRa + GPS coexist on one core (loop time stays single-digit ms)

---

## Phase 3 — Unified mesh (routing + multi-hop + self-healing)

- [ ] `RT:` distance-vector advertisements visible on each node
- [ ] A → C via B (force A↔C out of range; route goes through B)
- [ ] Power off B → routes invalidate → A↔C routes via rover (or fail with a clear message)
- [ ] Restore B → route recovered
- [ ] Duplicate forwards ≈ 0 (seen-ID cache working)
- [ ] 30 min soak clean

---

## Phase 4 — SOS button + rescue messaging

- [ ] Press SOS on Node A → `SOS:` broadcast 3×, non-blocking
- [ ] All in-range nodes show full-screen SOS OLED with **real GPS coords**
- [ ] SOS auto-clears after 60 s
- [ ] Hold button ≥ 1.5 s → manual clear
- [ ] TEXT messaging over USB serial: directed or broadcast
- [ ] Edge-triggered button — holding it doesn't repeat-fire

---

## Phase 5 — Pi command centre + dashboard

- [ ] `bash development/pi/install.sh --enable` succeeds
- [ ] Pi dashboard loads at `http://<pi-ip>:8000/` in <3 s
- [ ] All four panels render; SOS banner hidden; rover panel visible
- [ ] Pi serves a `/portal` page that mirrors the on-node portal
- [ ] Every mesh event type (HB / GPS / SOS / TEXT / RPT / STAT / ROVER) appears on the dashboard
- [ ] `/api/command` issues work: WHERE, SOS, SOSCLR, MODE, FWD/BACK/LEFT/RIGHT/STOP
- [ ] Dashboard map uses offline tiles (no internet needed)

---

## Phase 6 — Reliability + GPS fixes

- [ ] Max loop time stays under 10 ms across all phases
- [ ] Lost node rejoins in ~5 s (HB timeout + jitter)
- [ ] No BROWNOUT resets in a 1 h soak
- [ ] Battery ADC reading populated (or stub flag is honest)
- [ ] Heap trend within ±2 KB across the soak

---

## Phase 7 — Range + GPS + new UI

- [ ] Outdoors: A↔C range extended vs Phase 1 numbers
- [ ] Airtime correctly computed for the chosen SF
- [ ] GPS Serial2 RX buffer large enough that no NMEA is dropped
- [ ] New OLED with 5 organised pages (HB, LINKS, GPS, ROUTES, STATS)
- [ ] Redesigned portal polls `/api/status` every 4 s; live peer table with signal bars

---

## Phase 8 — Autonomous rover + mobile relay

- [ ] Rover joins mesh as `R`, mode `MANUAL` on boot
- [ ] Bench test (wheels OFF ground): FWD/BACK/LEFT/RIGHT spin the right wheels
- [ ] Ultrasonic fault detection: unplug ECHO → AUTO refuses to drive
- [ ] AUTO mode: 5 min collision-free on the floor
- [ ] SOS button on rover cuts motors instantly (hardware E-STOP)
- [ ] Mobile relay: separate A and C beyond range, drive rover between them, A↔C traffic flows
- [ ] Telemetry (mode / obstacle / battery) reaches the dashboard
- [ ] All rover bugs from `phase 8/README.md` §"Bugs found" verified fixed

---

## Phase 9 — Integration, tuning, field / range test

- [ ] Bench pre-flight (§0 of `docs/TEST_REPORT.md`) all green
- [ ] 2 h soak (§C) — zero watchdog resets, heap ±2 KB, missed HB = 0
- [ ] Outdoor range test (§D) — 90 %-loss radius recorded for at least 3 obstacle conditions
- [ ] End-to-end scenario (§A) passes **3 consecutive runs** from `docs/DEMO_SCRIPT.md`
- [ ] Tuning pass (§B) — only changed knobs recorded, with the measurement that motivated each
- [ ] Duplicate-forward check (§E) — seen-ID cache still working
- [ ] Follow-up defects (§F) listed, not patched in this phase
- [ ] Sign-off (§G) by reviewer

---

## Phase 10 — Demo script + documentation

- [x] `docs/DEMO_SCRIPT.md` — 12–15 min walkthrough mapped to the proposal's 12 demonstrated capabilities
- [x] `docs/ARCHITECTURE.md` — system layers + data flow + message sequences
- [x] `docs/WIRING.md` — per-board wiring tables consolidated
- [x] `docs/LIMITATIONS.md` — honest known-limitations + future scope
- [x] `docs/FINAL_REPORT.md` — what was built vs. proposal, headline numbers, sign-off
- [x] `development/README.md` rewritten as the start-here doc
- [x] Root `README.md` updated with pointer to `development/`
- [x] This tracker file
- [ ] **Clean-room reproduction succeeds** — a team member who didn't write the code follows
      `docs/DEMO_SCRIPT.md` + `development/pi/DEPLOY.md` from scratch and gets a working demo.

The clean-room reproduction is the final gate; until it has been
done at least once, Phase 10 is "complete but unverified" rather
than "complete and proven".

---

## Quick status legend

| Symbol | Meaning |
|---|---|
| 🟢 | Complete + bench-tested by user |
| 🟡 | Code written, awaiting hardware verification |
| ⬜ | Not started |

| Phase | State |
|---|---|
| 0 Audit & bench test | ⬜ awaiting hardware run |
| 1 Shared core firmware | 🟡 code written — awaiting hardware verification |
| 2 Hybrid location + captive portal | 🟡 code written — awaiting hardware verification |
| 3 Multi-hop mesh + self-healing | 🟡 code written — awaiting hardware verification |
| 4 SOS + rescue messaging | 🟡 code written — awaiting hardware verification |
| 5 Pi command centre + dashboard | 🟡 code written — awaiting hardware verification |
| 6 Reliability + GPS | 🟡 code written — awaiting hardware verification |
| 7 Range + GPS + new UI | 🟡 code written — awaiting hardware verification |
| 8 Autonomous rover | 🟢 rover code complete + bench-tested |
| 9 Integration & field test | 🟡 integrated code drop in `phase 9/`, test report template in `docs/TEST_REPORT.md` — awaiting 3-run sign-off |
| 10 Demo script + documentation | 🟢 docs complete — clean-room reproduction gate still open |
