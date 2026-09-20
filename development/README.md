# development/

New development work for the LoRa-WiFi SAR Mesh project. **The
existing `phase 1/` … `phase 11/` folders at the repo root are
untouched** — they remain the working reference / rollback baseline.

Full review, feasibility assessment, and the original phase plan:
`docs/PLAN.md`. What the project actually built and the demo
walkthrough: `docs/FINAL_REPORT.md` and `docs/DEMO_SCRIPT.md`.

---

## Start here

If you have **never seen this project** before, read these three
files in order and you have everything you need:

1. [`docs/FINAL_REPORT.md`](docs/FINAL_REPORT.md) — what was built,
   what wasn't, and the honest limitations.
2. [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) — the 12–15 minute
   live demo, step by step.
3. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the system,
   layer by layer.

If you are about to **build the demo** (wiring + flashing + Pi
setup), add:

- [`docs/WIRING.md`](docs/WIRING.md) — per-board wiring tables
- [`development/pi/DEPLOY.md`](pi/DEPLOY.md) — one-shot Pi setup
  (`bash install.sh --enable`) and day-to-day update (`bash
  update.sh`)

If you are about to **run the integration test**:

- [`phase 9/README.md`](phase%209/README.md) — the integration phase
- [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md) — what to measure and
  the §A end-to-end scenario
- [`docs/TUNING.md`](docs/TUNING.md) — which knobs can be touched
  and how

---

## Why this folder exists

The root `phase N/` sketches work in short demos, but each is a
standalone copy-paste program. Bug fixes don't propagate, phases
10–11 dropped the multi-hop mesh and self-healing, phase 11 never
reads the GPS, the SOS screen never clears, and blocking `delay()`
calls make the single half-duplex radio deaf for seconds at a
time. This folder rebuilds the node firmware around **one shared,
non-blocking, tested core** and adds the Wi-Fi captive portal, the
Raspberry Pi command centre, and the autonomous rover on top.

---

## Layout

```
development/
├── README.md                      ← this file: start here
├── Progress_Tracker.md            ← checkbox tracker (development/ side)
├── docs/                          ← every project-level doc
│   ├── PLAN.md                    (review + plan, original)
│   ├── FINAL_REPORT.md            (Phase 10 deliverable)
│   ├── DEMO_SCRIPT.md             (Phase 10 deliverable)
│   ├── ARCHITECTURE.md            (Phase 10 deliverable)
│   ├── WIRING.md                  (Phase 10 deliverable)
│   ├── LIMITATIONS.md             (Phase 10 deliverable)
│   ├── PACKET_SPEC.md             (frozen wire format)
│   ├── BUILD_AND_FLASH.md         (which tabs to paste, in what order)
│   ├── TUNING.md                  (Phase 9 deliverable)
│   ├── TEST_REPORT.md             (Phase 9 deliverable)
│   ├── SOS_AND_GPS.md             (Phase 4 narrative)
│   ├── CAPTIVE_PORTAL.md          (Phase 4 narrative)
│   ├── COMMAND_CENTER.md          (Phase 5 narrative)
│   ├── MESH_DESIGN.md             (Phase 3 narrative)
│   └── ROVER.md                   (Phase 8 narrative)
├── phase 1/   … phase 9/          ← one folder per phase, complete sketches
└── pi/                            ← THE canonical Pi codebase
                                    (mirrored at phase 9/pi/, not edited there)
```

> `pi/` is **not** phase-numbered. Pi-side fixes since phase 5 have
> landed directly in `development/pi/`. Each phase's README says
> what changed there. Phase 9 keeps a snapshot of `pi/` so the
> integration test runs a known version; the canonical copy is
> `development/pi/` and is what `bash update.sh` pulls.

> Phase 2 was inserted after the original plan: hybrid
> GPS-module / phone location came earlier than the plan's
> Phase 3+4, so location and the captive portal moved forward and
> mesh routing moved back one slot. `docs/PLAN.md` still shows the
> original numbering.

Each `phase N/` folder holds one **complete standalone sketch per
node** plus a `README.md` with the build steps, test procedure,
and completion criteria for that phase. Each phase's sketches
carry everything the previous phase had plus that phase's new
capability — so you always flash exactly one file per board.

---

## Conventions (kept from the existing project)

- **Complete copy-paste sketches.** Every `Node X.md` is a whole
  program: select all, paste into the Arduino IDE, upload. Same
  convention as the root `phase 1/` … `phase 11/` files.
- **All three boards must run the same phase.** The protocol
  version is checked on every packet, so mixed phases simply drop
  each other's frames.
- **3× identical ESP32 + 1× ESP32-S3 rover.** No Arduino Nano /
  ATmega (the old Node C on a 2 KB ATmega was the source of a
  long tail of stability patches).
- **No `delay()` in `loop()`. No `String` in the packet hot
  path.** See `phase 1/README.md` for why.
- Pin assignments follow `docs/WIRING.md`.
- The tunable block (pins, radio settings, timeouts) is repeated
  at the top of each node sketch — **if you change one, change
  all three (and `pi/sx1278.py`)**.

---

## Build & run order

| Phase | What | Gate |
|---|---|---|
| 0 | Bench-test the existing root `phase 9` + `phase 10` sketches | `docs/PHASE0_FINDINGS.md` filled in |
| 1 | Shared core — heartbeat, neighbours, CRC, watchdog | 60-min soak, heap flat |
| 2 | Hybrid location — GPS module + phone via captive portal | portal works on a phone; Wi-Fi and LoRa coexist |
| 3 | Unified mesh — routing, multi-hop, self-healing | A→C via B; kill/restore B |
| 4 | SOS button + rescue messaging | SOS auto-clears; reaches whole mesh |
| 5 | Pi command centre (own LoRa) + web dashboard | every event on the map; commands out |
| 6 | Reliability + GPS | maxloop single-digit ms; lost node rejoins in ~5s |
| 7 | Range + GPS + new UI | longer open-space range; portal/OLED redesign |
| 8 | Autonomous rover + mobile relay | 5 min collision-free; relay restores A↔C |
| 9 | Integration, tuning, field/range test | end-to-end scenario passes 3× |
| 10 | Demo script + documentation | clean-room reproduction succeeds |

Detailed flashing instructions: `docs/BUILD_AND_FLASH.md`.

---

## Status

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
| 8 Autonomous rover | 🟢 rover code complete + bench-tested by user |
| 9 Integration & field test | 🟡 docs in place + integrated code drop — awaiting hardware run to fill `docs/TEST_REPORT.md` |
| 10 Demo script + documentation | 🟢 docs complete — DEMO_SCRIPT, ARCHITECTURE, WIRING, LIMITATIONS, FINAL_REPORT all shipped |

The 🟡 "awaiting hardware" badges are honest: every code drop has
been bench-verified in pieces (the rover and dashboard have been
demoed end-to-end), but the **3-consecutive-runs** integration test
that gates Phase 9 has not yet been signed off. Everything needed
for it is in `phase 9/`; the §A template is in
`docs/TEST_REPORT.md`.

---

## Where to look for things

| I want to … | Open |
|---|---|
| see what the demo does on stage | `docs/DEMO_SCRIPT.md` |
| understand how the system fits together | `docs/ARCHITECTURE.md` |
| wire a board | `docs/WIRING.md` |
| know what's deliberately not built | `docs/LIMITATIONS.md` |
| know how every byte on the wire is framed | `docs/PACKET_SPEC.md` |
| run the integration test | `phase 9/README.md` + `docs/TEST_REPORT.md` |
| tune a knob without breaking it | `docs/TUNING.md` |
| set up the Pi from scratch | `development/pi/DEPLOY.md` |
| pull the latest onto the Pi | `bash development/pi/update.sh` |
| understand a specific phase's design | `phase N/README.md` for that phase |
| reproduce the work after a clean checkout | `docs/FINAL_REPORT.md` §"How to reproduce the demo" |

---

## License

MIT (same as the root repo).
