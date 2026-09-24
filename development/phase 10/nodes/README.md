# 🔌 ESP32 Field Nodes Firmware & Hardware Wiring Guide (Phase 10 Release)

This directory contains the production C++ Arduino sketches for **Node A**, **Node B**, and **Node C**.

---

## 🧰 Hardware Additions (Phase 10 Upgrade)

Each ESP32 node is equipped with:
1. **Piezo Audio Transducer (Buzzer)** on **GPIO 25**:
   - 🚨 **SOS Alert Tone**: Pulsing 2.5kHz MAYDAY pattern (`... --- ...`).
   - 📩 **Incoming Message Beep**: High-pitch double chirp when a LoRa text or broadcast arrives.
   - 🛰️ **GPS Lock Tone**: Melodic triple chirp on satellite fix / boot success.
   - 🔘 **Button Click Feedback**: Tactile 30ms audio feedback on button press.

2. **Button 1 — SOS Emergency Button** on **GPIO 4** (Active LOW, internal pullup):
   - **Short Press (< 2 seconds)**: Refreshes / awakes OLED display.
   - **Long Press (> 3 seconds)**: Triggers or Clears global `🚨 SOS MAYDAY 🚨` broadcast across the LoRa mesh and starts audio alert.

3. **Button 2 — Field Status & Rescue Report Button** on **GPIO 13** (Active LOW, internal pullup):
   - **Single Tap**: Cycles team operational status (`AVAILABLE` ➔ `SEARCHING` ➔ `VICTIM_FOUND` ➔ `NEED_ASSIST`) and broadcasts `STAT:` frame to gateway.
   - **Long Press (> 2 seconds)**: Sends instant `VICTIM_FOUND` rescue report with current GPS coordinates to Raspberry Pi Command Centre.

---

## 🔌 Complete Master Wiring Table (Nodes A, B, C)

| Component Pin | ESP32 Pin | Subsystem | Notes |
| :--- | :--- | :--- | :--- |
| **LoRa VCC** | **3.3V** | SX1278 Power | ⚠️ **Do NOT use 5V for LoRa module** |
| **LoRa GND** | **GND** | SX1278 Ground | Common Ground |
| **LoRa SCK** | **GPIO 18** | Hardware SPI | SPI Clock |
| **LoRa MISO** | **GPIO 19** | Hardware SPI | Master In |
| **LoRa MOSI** | **GPIO 23** | Hardware SPI | Master Out |
| **LoRa NSS / CS** | **GPIO 5** | Hardware SPI | Chip Select |
| **LoRa RST** | **GPIO 14** | LoRa Control | Hardware Reset |
| **LoRa DIO0** | **GPIO 26** | LoRa Interrupt | RX Interrupt |
| **OLED VCC / GND** | **3.3V / GND** | I2C Display | 128x64 OLED |
| **OLED SDA** | **GPIO 21** | Hardware I2C | Data Line |
| **OLED SCL** | **GPIO 22** | Hardware I2C | Clock Line |
| **GPS VCC / GND** | **3.3V / GND** | NEO-6M / M8N | GPS Module |
| **GPS TX** | **GPIO 16 (RX2)** | Hardware Serial2 | Serial RX |
| **GPS RX** | **GPIO 17 (TX2)** | Hardware Serial2 | Serial TX |
| **Piezo Buzzer (+)** | **GPIO 25** | Audio Transducer | Passive/Active Buzzer |
| **Piezo Buzzer (-)** | **GND** | Audio Transducer | Ground |
| **Button 1 (SOS)** | **GPIO 4** | Tactile Switch | Connected to GND (Active LOW) |
| **Button 2 (Status)**| **GPIO 13** | Tactile Switch | Connected to GND (Active LOW) |

---

## 🛠️ Arduino IDE / PlatformIO Setup

1. **Required Libraries**:
   - `LoRa` by Sandeep Mistry
   - `Adafruit SSD1306` & `Adafruit GFX Library`
   - `TinyGPSPlus` by Mikal Hart

2. **Board Settings**:
   - Board: `ESP32 Dev Module`
   - Flash Size: `4MB (32Mb)`
   - Upload Speed: `921600` or `115200`

---

## 🔘 Button Interaction Cheat Sheet

| Button | Action | Resulting Mesh Frame | Audio / OLED Feedback |
| :--- | :--- | :--- | :--- |
| **Btn 1 (SOS)** | Tap (< 2s) | *None* | Screen wakes up |
| **Btn 1 (SOS)** | Hold (> 3s) | `SOS:A:*:MAYDAY...` | 🚨 Loud SOS Pattern & red alert |
| **Btn 2 (Status)** | Tap | `STAT:A:SEARCHING` | Status updates on OLED + click beep |
| **Btn 2 (Status)** | Hold (> 2s) | `RPT:A:PI:VICTIM...` | Instant location report sent to Pi |
