# development/

New development work for the LoRa-WiFi SAR Mesh project. **The existing `phase 1/` … `phase 11/`
folders at the repo root are untouched** — they remain the working reference / rollback baseline.

Full review, feasibility assessment and the phase plan this folder implements: `docs/PLAN.md`.

## Why this folder exists

The root `phase N/` sketches work in short demos but each is a standalone copy-paste program.
Bug fixes don't propagate, phase 10/11 dropped the multi-hop mesh and self-healing, phase 11
never reads the GPS, the SOS screen never clears, and blocking `delay()` calls make the single
half-duplex radio deaf for seconds at a time. This folder rebuilds the node firmware around
**one shared, non-blocking, tested core** and then adds the Wi-Fi captive portal, the Raspberry
Pi command center, and the autonomous rover.

## Layout

```
development/
├── docs/            plan, packet spec, per-phase design notes, test reports
├── fixtures/        recorded GPS NMEA for indoor demo rehearsal
├── phase 1/         shared core: radio + packet + OLED + neighbours
├── phase 2/         hybrid location: GPS module + phone via captive portal
├── phase 3/         multi-hop mesh: routing + forwarding + self-healing
├── phase 4/         SOS button + rescue messaging
├── phase 5/         Pi joins mesh (own SX1278) + web dashboard
├── phase 6/         autonomous rover
└── pi/              Python service + web dashboard (used from phase 5)
```

> Phase 2 was inserted after the original plan was written: the user asked for hybrid
> GPS-module / phone location earlier than the plan's Phase 3+4, so location and the captive
> portal moved forward and mesh routing moved back one slot. `docs/PLAN.md` still shows the
> original numbering.

Each `phase N/` folder holds one **complete standalone sketch per node** plus a `README.md` with
the build steps, test procedure and completion criteria for that phase. Each phase's sketches
carry everything the previous phase had, plus that phase's new capability — so you always flash
exactly one file per board.

## Conventions (kept from the existing project)

- **Complete copy-paste sketches.** Every `Node X.md` is a whole program: select all, paste into
  the Arduino IDE, upload. Raw code only — no Markdown fences or headings. Same convention as the
  root `phase 10/` and `phase 11/` files.
- **All three boards must run the same phase.** The protocol version is checked on every packet,
  so mixed phases simply drop each other's frames.
- **3× identical ESP32.** No ESP32-S3, no Arduino Nano (the old Node C on a 2 KB ATmega was the
  source of a long tail of stability patches).
- **No `delay()` in `loop()`. No `String` in the packet hot path.**
- Pin assignments follow `../Hardware_Connections.md`.
- The tunable block (pins, radio settings, timeouts) is repeated at the top of each node sketch —
  **if you change one, change all three.**

## Build & run order

| Phase | What | Gate |
|---|---|---|
| 0 | Bench-test the existing root `phase 9` + `phase 10` sketches | `docs/PHASE0_FINDINGS.md` filled in |
| 1 | Shared core — heartbeat, neighbours, CRC, watchdog | 60-min soak, heap flat |
| 2 | Hybrid location — GPS module + phone via captive portal | portal works on a phone; Wi-Fi and LoRa coexist |
| 3 | Unified mesh — routing, multi-hop, self-healing | A→C via B; kill/restore B |
| 4 | SOS button + rescue messaging | SOS auto-clears; reaches whole mesh |
| 5 | Pi command centre (own LoRa) + web dashboard | every event on the map; commands out |
| 6 | Autonomous rover + mobile relay | 5 min collision-free; relay restores A↔C |
| 7 | Integration, tuning, field/range test | end-to-end scenario passes 3× |
| 8 | Demo script + documentation | clean-room reproduction succeeds |

Detailed flashing instructions: `docs/BUILD_AND_FLASH.md`.

## Status

| Phase | State |
|---|---|
| 0 Audit & bench test | ⬜ awaiting hardware run |
| 1 Shared core firmware | 🟡 code written — awaiting hardware verification |
| 2 Hybrid location + captive portal | 🟡 code written — awaiting hardware verification |
| 3 Multi-hop mesh + self-healing | 🟡 code written — awaiting hardware verification |
| 4 SOS + rescue messaging | 🟡 code written — awaiting hardware verification |
| 5 Pi command centre + dashboard | 🟡 code written — awaiting hardware verification |
| 6 Autonomous rover | ⬜ not started |
| 7 Integration & field test | ⬜ not started |
| 8 Demo & documentation | ⬜ not started |
