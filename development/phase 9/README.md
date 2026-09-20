# Phase 9 — Integration build for demo day

**Goal:** one folder a tester (or a grader) can flash and run end-to-end
without reading any earlier phase folder. Everything that phases 1–8 added
lives here as **complete, standalone, paste-into-Arduino sketches** for
every node, plus a runnable copy of the Pi codebase.

This phase also defines what the integration test actually measures
(`docs/TEST_REPORT.md` next to `phase 9/`), what can be tuned and how
(`docs/TUNING.md`), and what must be true for the phase to be called
done.

---

## What's in this folder

| Path | What | Flash / run as |
|---|---|---|
| `Node A.md` | Classic ESP32 node with Wi-Fi portal + GPS + SOS + team status | Node A on a classic ESP32 |
| `Node B.md` | Classic ESP32 relay (mesh + optional GPS, no portal) | Node B on a classic ESP32 |
| `Node C.md` | Classic ESP32 node — mirror of A (portal + GPS + SOS) | Node C on a classic ESP32 |
| `Node Rover.md` | ESP32-S3 with motors + ultrasonic + GPS + E-STOP | Rover on an ESP32-S3 |
| `pi/main.py` | Pi gateway entrypoint | the gateway Pi |
| `pi/server.py` | Pi Flask dashboard + JSON API + SSE | the gateway Pi |
| `pi/mesh.py` | Pi as a mesh node (read + write LoRa) | the gateway Pi |
| `pi/db.py` | Pi SQLite store | the gateway Pi |
| `pi/sx1278.py` | Pi SX1278 driver (matches node PHY exactly) | the gateway Pi |
| `pi/fake_radio.py` | no-hardware stand-in for the SX1278 | the gateway Pi |
| `pi/dashboard/*` | Leaflet UI, top-bar SOS banner, rover panel | the gateway Pi |
| `pi/requirements.txt`, `pi/sar-pi.service`, `pi/.gitignore` | supporting Pi files | the gateway Pi |
| `TEMPLATES/*` | CSV/CSV templates for soak + range + dedup logs | the tester's laptop |
| `README.md` | this file | — |
| `docs/TEST_REPORT.md` | the actual test report to fill in | — (linked from here) |
| `docs/TUNING.md` | which knobs can be touched and how | — (linked from here) |

The Pi folder under `development/pi/` is the **canonical copy** that the
team edits day-to-day. This `phase 9/pi/` is a snapshot of it taken when
phase 9 was assembled, retitled as the integration build, and is bit-for-
bit identical other than the docstrings pointing back here. If you change
something in `development/pi/` after the phase 9 drop, copy it back into
`phase 9/pi/` so the two stay in sync.

---

## What you flash on demo day

| Board | File | Phase 7–8 did it need portal/relay? |
|---|---|---|
| ESP32 (Node A) | `Node A.md` | portal + GPS + SOS + mesh |
| ESP32 (Node B) | `Node B.md` | mesh-only relay (no portal) |
| ESP32 (Node C) | `Node C.md` | mirror of A |
| ESP32-S3 (Rover) | `Node Rover.md` | mesh + motors + ultrasonic + GPS |
| Raspberry Pi | `pi/main.py` | own LoRa radio + dashboard on :8000 |

Library list and wiring for each board is inside the header block of
each `Node X.md`. The Pi wiring is in the first ~50 lines of
`pi/sx1278.py`.

## What you run

```bash
# the Pi dashboard gateway
cd phase\ 9/pi
pip install -r requirements.txt
python main.py --fake-radio    # no hardware (laptop demo)
python main.py                 # with the SX1278 wired to the Pi
```

Then browse `http://<pi-ip>:8000/` for the dashboard and
`http://<pi-ip>:8000/portal` for the phone-friendly portal.

---

## Why this is in front of the integration test

Earlier phases each verified their piece in isolation. Phase 9 doesn't.
It expects every piece to be present and working together:

- **Three static nodes + rover + Pi**, all running the sketches in this
  folder, all reachable from one another in range.
- **Pi dashboard** at :8000 with the four panels (map, telemetry,
  activity, team) and the sliding rover panel.
- **Portal at /portal** on the Pi for the convenience of demo audiences
  who connect directly to the Pi rather than a node's AP.
- **Real numbers from a real run** in `docs/TEST_REPORT.md`.

The skills and tools needed to wire/test all five boxes are in
`docs/BUILD_AND_FLASH.md` and per-board in each sketch's header.

---

## Test method

Full procedure: `docs/TEST_REPORT.md` in this folder.

The headline gate is **§A — end-to-end scenario run three consecutive
times**. The script lives in `docs/DEMO_SCRIPT.md` (still to be written
in phase 10, but the step list is in `TEST_REPORT.md` §A already).

Supporting measurements:
- **§B**: tuning-pass log — one row per knob that was actually changed
  between iterations.
- **§C**: 2-hour soak with heap + watchdog + packet-loss CSV.
- **§D**: outdoor range test, RSSI vs distance at the chosen SF.
- **§E**: duplicate-forward verification (sees the seen-ID cache from
  phase 1 still working).
- **§F**: any defects that need code, listed here so they don't get
  lost.

---

## What's *not* in Phase 9

- **No new features.** Encryption, duty cycle, solar, field trials are
  all future-scope.
- **No refactor.** If the integration run surfaces ugly code, that's a
  phase 10 follow-up. Phase 9 is read-only on the code.
- **No dashboard redesign.** Phase 9 already shipped a clean dashboard;
  leave it alone for demo day.
- **No protocol changes.** The packet spec is frozen at v3. If something
  needs a new packet type, that's a v4 bump and a fresh plan, not a
  tuning pass.

---

## Completion criteria

- [ ] §0 bench pre-flight all green
- [ ] 2-hour soak: zero watchdog resets, heap ±2 KB, missed HB = 0
- [ ] outdoor range test: 90 %-loss radius recorded for at least 3
      obstacle conditions
- [ ] end-to-end scenario passes **3 consecutive runs**
- [ ] `TUNING.md` knobs table reflects any change that was made, with a
      measurement that motivated it
- [ ] `TEST_REPORT.md` §G signed off by reviewer
- [ ] All headline numbers copied into `DEMO_SCRIPT.md` (phase 10
      deliverable) so the demo runner knows what to expect on the day

---

## Carry-over to Phase 10

Phase 10 = `docs/DEMO_SCRIPT.md`, `docs/ARCHITECTURE.md`,
`docs/WIRING.md`, `docs/LIMITATIONS.md`, `docs/FINAL_REPORT.md`,
`development/README.md` rewrite, root `README.md` pointer.

Phase 10 needs the Phase 9 numbers to be honest, so the two phases
share `TEST_REPORT.md` as the boundary: phase 9 fills it in, phase 10
quotes from it.
