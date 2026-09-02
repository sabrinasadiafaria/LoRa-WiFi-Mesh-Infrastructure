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
├── phase 1/         shared core: radio + packet + OLED + neighbours   <- YOU ARE HERE
├── phase 2/         unified mesh: routing + multi-hop + self-healing
├── phase 3/         GPS + SOS + messaging
├── phase 4/         Wi-Fi captive portal
├── phase 5/         gateway node + Raspberry Pi command center
├── phase 6/         autonomous rover
└── pi/              Python service + web dashboard (used from phase 5)
```

Each `phase N/` folder is self-contained: shared `*.h.md` Arduino tabs, thin per-node main
sketches, and a `README.md` with the build steps, test procedure and completion criteria for
that phase. Later phases add tabs; they don't fork the earlier ones.

## Conventions (kept from the existing project)

- **Arduino IDE copy-paste style.** Firmware ships as Markdown files containing raw code — no
  fences, no headings — so a file can be pasted straight into a tab.
- Shared modules are `*.h.md` → paste into a **new tab named exactly** `config.h`, `packet.h`, …
- Per-device sketches (`Node A.md`, …) are the main `.ino` tab and contain only two `#define`s
  plus `setup`/`loop`. **All three nodes share byte-identical tabs.**
- **3× identical ESP32.** No ESP32-S3, no Arduino Nano (the old Node C on a 2 KB ATmega was the
  source of a long tail of stability patches).
- **No `delay()` in `loop()`. No `String` in the packet hot path.**
- Pin assignments follow `../Hardware_Connections.md`.

## Build & run order

| Phase | What | Gate |
|---|---|---|
| 0 | Bench-test the existing root `phase 9` + `phase 10` sketches | `docs/PHASE0_FINDINGS.md` filled in |
| 1 | Shared core — heartbeat, neighbours, CRC, watchdog | 60-min soak, heap flat |
| 2 | Unified mesh — routing, multi-hop, self-healing | A→C via B; kill/restore B |
| 3 | GPS + SOS + messaging with real data | SOS shows live coords, screen clears |
| 4 | Wi-Fi captive portal | portal auto-pops on a real phone |
| 5 | Gateway + Raspberry Pi command center + dashboard | every event visible on the map |
| 6 | Autonomous rover + mobile relay | 5 min collision-free; relay restores A↔C |
| 7 | Integration, tuning, field/range test | end-to-end scenario passes 3× |
| 8 | Demo script + documentation | clean-room reproduction succeeds |

Detailed flashing instructions: `docs/BUILD_AND_FLASH.md`.

## Status

| Phase | State |
|---|---|
| 0 Audit & bench test | ⬜ awaiting hardware run |
| 1 Shared core firmware | 🟡 code written — awaiting hardware verification |
| 2 Unified mesh | ⬜ not started |
| 3 GPS + SOS + messaging | ⬜ not started |
| 4 Wi-Fi captive portal | ⬜ not started |
| 5 Pi command center | ⬜ not started |
| 6 Autonomous rover | ⬜ not started |
| 7 Integration & field test | ⬜ not started |
| 8 Demo & documentation | ⬜ not started |
