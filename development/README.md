# development/

New development work for the LoRa-WiFi SAR Mesh project. **The existing `phase 1/` … `phase 11/`
folders are untouched** — they remain the working reference / rollback baseline.

Full review, feasibility assessment and the phase-wise plan this folder implements:
`C:\Users\Lenovo\.claude\plans\hey-this-is-my-swirling-forest.md`
(a copy of the plan is also kept in `docs/PLAN.md`).

## Why this folder exists

The `phase N/` sketches work in short demos but each is a standalone copy-paste program. Bug
fixes don't propagate, phase 10/11 dropped the multi-hop mesh and self-healing, phase 11 never
reads the GPS, the SOS screen never clears, and blocking `delay()` calls make the single
half-duplex radio deaf for seconds at a time. This folder rebuilds the node firmware around
**one shared, non-blocking, tested core** and then adds the Wi-Fi captive portal, the Raspberry
Pi command center, and the autonomous rover.

## Conventions (kept from the existing project)

- **Arduino IDE copy-paste style.** Firmware is distributed as Markdown files. Shared modules
  live in `firmware/common/*.h.md` and are pasted **once each** into a new Arduino IDE tab whose
  name matches the file (e.g. `radio_layer.h`). Per-device sketches in `firmware/nodes/*.md` are
  thin: they set config and call the shared services.
- **3× identical ESP32.** All node code targets plain ESP32 (no ESP32-S3, no Arduino Nano).
- **No `delay()` in `loop()`. No `String` in the packet hot path.** See `docs/PLAN.md` §11.
- Pin assignments follow `../Hardware_Connections.md`.

## Build & run order

| Step | What | Where |
|---|---|---|
| 0 | Bench-test the existing `phase 9` + `phase 10` sketches, record findings | `docs/PHASE0_FINDINGS.md` |
| 1 | Flash shared core (radio + packet + OLED skeleton) to Node A/B/C | `firmware/common/`, `firmware/nodes/` |
| 2 | Add unified mesh (discovery + routing + multi-hop + self-healing) | `firmware/common/mesh_core.h.md` |
| 3 | Add GPS + SOS + serial messaging | `firmware/common/gps_layer.h.md`, `app_sos.h.md`, `app_msg.h.md` |
| 4 | Add Wi-Fi captive portal on Node A & C | `firmware/common/portal_layer.h.md`, `portal_pages.h.md` |
| 5 | Add gateway node + Raspberry Pi command center + dashboard | `firmware/nodes/Node_Gateway.md`, `pi/` |
| 6 | Build the autonomous rover node | `firmware/nodes/Node_Rover.md`, `motor_layer.h.md`, `ultrasonic_layer.h.md` |
| 7 | Full-system integration, tuning, field/range test | `docs/TEST_REPORT.md`, `docs/TUNING.md` |
| 8 | Demo script + documentation + final report | `docs/DEMO_SCRIPT.md`, `docs/FINAL_REPORT.md` |

Detailed flashing instructions (which tab, in what order, library versions):
`docs/BUILD_AND_FLASH.md`.

## Status

| Phase | State |
|---|---|
| 0 Audit & bench test | ⬜ not started |
| 1 Shared core firmware | ⬜ not started |
| 2 Unified mesh | ⬜ not started |
| 3 GPS + SOS + messaging | ⬜ not started |
| 4 Wi-Fi captive portal | ⬜ not started |
| 5 Pi command center | ⬜ not started |
| 6 Autonomous rover | ⬜ not started |
| 7 Integration & field test | ⬜ not started |
| 8 Demo & documentation | ⬜ not started |
