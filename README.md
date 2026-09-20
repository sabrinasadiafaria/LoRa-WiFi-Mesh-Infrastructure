# LoRa-WiFi Mesh Infrastructure 📡🆘

A professional-grade, multi-hop mesh communication system designed for Search and Rescue (SAR) operations. This project utilizes ESP32 microcontrollers, LoRa radio technology, and GPS tracking to build a robust, self-healing network independent of cellular infrastructure.

> **Looking for the working code?** Start at [`development/README.md`](development/README.md) — it has
> the start-here guide, the demo walkthrough, the wiring tables, the architecture, and the canonical
> Pi codebase. The original `phase 1/` … `phase 11/` folders below remain as the working reference /
> rollback baseline. The full review, plan, and feasibility assessment are in
> [`development/docs/PLAN.md`](development/docs/PLAN.md).

## Features
- **Long-Range Communication**: Utilizes LoRa for low-power, high-range data transmission.
- **Self-Healing Mesh**: Automatically reroutes packets if a node drops offline.
- **GPS Integration**: Real-time location tracking of all network nodes.
- **Command Center Dashboard**: Visualizes network topology and node locations on a web dashboard.
- **Wi-Fi Captive Portal**: Phone browser, no app, raises SOS / shares GPS / files rescue reports.
- **Autonomous Rescue Rover**: Mobile mesh member that doubles as a LoRa relay.

## Folder Structure
- `phase 1/` … `phase 11/`: the original Arduino sketches (Markdown format for easy copy/paste) —
  OLED tests, LoRa TX/RX bring-up, multi-hop, GPS, SOS. The working reference / rollback baseline.
- `development/`: the **rebuilt, integrated system**. Start with `development/README.md`.
- `planing/`: the approved proposal deck (`Project poposal.pdf`, presented 1 Sep 2026).
- `Project idea.md`, `PLan.md`, `Hardware_Connections.md`, `Progress_Tracker.md`: original design notes.

## Getting Started (Phase 1)
To get started with basic hardware testing, navigate to the `phase 1/` directory. You will find Markdown files containing code snippets ready to be copied into the Arduino IDE.

1. Install the `LoRa` by Sandeep Mistry and `Adafruit SSD1306` libraries in the Arduino IDE.
2. Connect your ESP32 to the LoRa module and OLED display.
3. Flash the Sender/Receiver and OLED test codes to verify your hardware setup.

## License
MIT License