# LoRa-WiFi Mesh Infrastructure 📡🆘

A professional-grade, multi-hop mesh communication system designed for Search and Rescue (SAR) operations. This project utilizes ESP32 microcontrollers, LoRa radio technology, and GPS tracking to build a robust, self-healing network independent of cellular infrastructure.

## Features
- **Long-Range Communication**: Utilizes LoRa for low-power, high-range data transmission.
- **Self-Healing Mesh**: Automatically reroutes packets if a node drops offline.
- **GPS Integration**: Real-time location tracking of all network nodes.
- **Command Center Dashboard**: Visualizes network topology and node locations on a web dashboard.

## Folder Structure
- `phase 1/`: Contains Arduino sketches (Markdown format for easy copy/paste) for initial hardware verification, OLED testing, and basic Point-to-Point LoRa communication.
- `Project idea.md`: Detailed architecture and system design.
- `PLan.md`: Roadmap, task list, and upcoming features.

## Getting Started (Phase 1)
To get started with basic hardware testing, navigate to the `phase 1/` directory. You will find Markdown files containing code snippets ready to be copied into the Arduino IDE. 

1. Install the `LoRa` by Sandeep Mistry and `Adafruit SSD1306` libraries in the Arduino IDE.
2. Connect your ESP32 to the LoRa module and OLED display.
3. Flash the Sender/Receiver and OLED test codes to verify your hardware setup.

## License
MIT License