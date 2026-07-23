# Hardware Connections

Use this document to verify your wiring connections for each node while assembling and testing.

---

## 🟢 Node A Configuration (ESP32 Standard + NEO-6M GPS)

**Hardware Components:**
* Microcontroller: ESP32 (Standard)
* Display: 1.3" OLED (SH1106) / 0.96" OLED (SSD1306)
* Radio: LoRa SX1278 (433MHz)
* GPS: NEO-6M
* Button: External Push Button (GPIO 4 / GPIO 0)

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

---

## 🔵 Node B Configuration (ESP32 Standard + NEO-M8N GPS)

**Hardware Components:**
* Microcontroller: ESP32 (Standard)
* Display: 0.96" OLED (SSD1306)
* Radio: LoRa SX1278 (433MHz)
* GPS: NEO-M8N
* Button: External Push Button (GPIO 4 / GPIO 0)

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

---

## 🟡 Node C Configuration (ESP32 Standard + NEO-M8N GPS)

**Hardware Components:**
* Microcontroller: ESP32 (Standard)
* Display: 0.96" OLED (SSD1306)
* Radio: LoRa SX1278 (433MHz)
* GPS: NEO-M8N
* Button: External Push Button (GPIO 4 / GPIO 0)

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
