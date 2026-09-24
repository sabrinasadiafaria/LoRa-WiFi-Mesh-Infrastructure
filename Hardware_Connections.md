# Hardware Connections

Use this document to verify your wiring connections for each node while assembling and testing.

---

## 🟢 Node A Configuration (ESP32 Standard + NEO-6M GPS)

**Hardware Components:**
* Microcontroller: ESP32 (Standard)
* Display: 1.3" OLED (SH1106) / 0.96" OLED (SSD1306)
* Radio: LoRa SX1278 (433MHz)
* GPS: NEO-6M
* Audio Alert: Piezo Audio Transducer (Buzzer)
* Buttons: 2x Tactile Buttons (Button 1: SOS / Button 2: Status Cycle & Quick Report)

### 🔌 Node A Wiring Diagram

| Component Pin | ESP32 Pin | Description |
| :--- | :--- | :--- |
| **LoRa VCC** | **3.3V** | Power (**Do NOT use 5V for LoRa**) |
| **LoRa GND** | **GND** | Ground |
| **LoRa SCK** | **GPIO 18** | SPI Clock |
| **LoRa MISO** | **GPIO 19** | SPI Master In |
| **LoRa MOSI** | **GPIO 23** | SPI Master Out |
| **LoRa NSS / CS** | **GPIO 5** | SPI Chip Select |
| **LoRa RST** | **GPIO 14** | Reset |
| **LoRa DIO0** | **GPIO 26** | Hardware Interrupt |
| **OLED VCC** | **3.3V / 5V** | Display Power |
| **OLED GND** | **GND** | Display Ground |
| **OLED SDA** | **GPIO 21** | Hardware I2C Data |
| **OLED SCL** | **GPIO 22** | Hardware I2C Clock |
| **NEO-6M GPS VCC** | **3.3V / 5V** | GPS Power |
| **NEO-6M GPS GND** | **GND** | GPS Ground |
| **NEO-6M GPS TX** | **GPIO 16** | Hardware Serial2 RX (RX2) |
| **NEO-6M GPS RX** | **GPIO 17** | Hardware Serial2 TX (TX2) |
| **Piezo Buzzer (+)**| **GPIO 25** | Audio Alerts (SOS, RX Beeps, Lock Chirps) |
| **Button 1 (SOS)** | **GPIO 4** | Active LOW (Short press: Wake screen / Long press: SOS) |
| **Button 2 (Status)**| **GPIO 13**| Active LOW (Single tap: Cycle Status / Long press: Report) |

---

## 🔵 Node B Configuration (ESP32 Standard + NEO-M8N GPS)

**Hardware Components:**
* Microcontroller: ESP32 (Standard)
* Display: 0.96" OLED (SSD1306)
* Radio: LoRa SX1278 (433MHz)
* GPS: NEO-M8N
* Audio Alert: Piezo Audio Transducer (Buzzer)
* Buttons: 2x Tactile Buttons (Button 1: SOS / Button 2: Status Cycle & Quick Report)

### 🔌 Node B Wiring Diagram

| Component Pin | ESP32 Pin | Description |
| :--- | :--- | :--- |
| **LoRa VCC** | **3.3V** | Power (**Do NOT use 5V for LoRa**) |
| **LoRa GND** | **GND** | Ground |
| **LoRa SCK** | **GPIO 18** | SPI Clock |
| **LoRa MISO** | **GPIO 19** | SPI Master In |
| **LoRa MOSI** | **GPIO 23** | SPI Master Out |
| **LoRa NSS / CS** | **GPIO 5** | SPI Chip Select |
| **LoRa RST** | **GPIO 14** | Reset |
| **LoRa DIO0** | **GPIO 26** | Hardware Interrupt |
| **OLED VCC** | **3.3V / 5V** | Display Power |
| **OLED GND** | **GND** | Display Ground |
| **OLED SDA** | **GPIO 21** | Hardware I2C Data |
| **OLED SCL** | **GPIO 22** | Hardware I2C Clock |
| **NEO-M8N GPS VCC** | **3.3V / 5V** | GPS Power |
| **NEO-M8N GPS GND** | **GND** | GPS Ground |
| **NEO-M8N GPS TX** | **GPIO 16** | Hardware Serial2 RX (RX2) |
| **NEO-M8N GPS RX** | **GPIO 17** | Hardware Serial2 TX (TX2) |
| **Piezo Buzzer (+)**| **GPIO 25** | Audio Alerts (SOS, RX Beeps, Lock Chirps) |
| **Button 1 (SOS)** | **GPIO 4** | Active LOW (Short press: Wake screen / Long press: SOS) |
| **Button 2 (Status)**| **GPIO 13**| Active LOW (Single tap: Cycle Status / Long press: Report) |

---

## 🟡 Node C Configuration (ESP32 Standard + NEO-M8N GPS)

**Hardware Components:**
* Microcontroller: ESP32 (Standard)
* Display: 0.96" OLED (SSD1306)
* Radio: LoRa SX1278 (433MHz)
* GPS: NEO-M8N
* Audio Alert: Piezo Audio Transducer (Buzzer)
* Buttons: 2x Tactile Buttons (Button 1: SOS / Button 2: Status Cycle & Quick Report)

### 🔌 Node C Wiring Diagram

| Component Pin | ESP32 Pin | Description |
| :--- | :--- | :--- |
| **LoRa VCC** | **3.3V** | Power (**Do NOT use 5V for LoRa**) |
| **LoRa GND** | **GND** | Ground |
| **LoRa SCK** | **GPIO 18** | SPI Clock |
| **LoRa MISO** | **GPIO 19** | SPI Master In |
| **LoRa MOSI** | **GPIO 23** | SPI Master Out |
| **LoRa NSS / CS** | **GPIO 5** | SPI Chip Select |
| **LoRa RST** | **GPIO 14** | Reset |
| **LoRa DIO0** | **GPIO 26** | Hardware Interrupt |
| **OLED VCC** | **3.3V / 5V** | Display Power |
| **OLED GND** | **GND** | Display Ground |
| **OLED SDA** | **GPIO 21** | Hardware I2C Data |
| **OLED SCL** | **GPIO 22** | Hardware I2C Clock |
| **NEO-M8N GPS VCC** | **3.3V / 5V** | GPS Power |
| **NEO-M8N GPS GND** | **GND** | GPS Ground |
| **NEO-M8N GPS TX** | **GPIO 16** | Hardware Serial2 RX (RX2) |
| **NEO-M8N GPS RX** | **GPIO 17** | Hardware Serial2 TX (TX2) |
| **Piezo Buzzer (+)**| **GPIO 25** | Audio Alerts (SOS, RX Beeps, Lock Chirps) |
| **Button 1 (SOS)** | **GPIO 4** | Active LOW (Short press: Wake screen / Long press: SOS) |
| **Button 2 (Status)**| **GPIO 13**| Active LOW (Single tap: Cycle Status / Long press: Report) |
