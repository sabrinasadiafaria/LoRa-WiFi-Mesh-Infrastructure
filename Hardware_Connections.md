# Hardware Connections

Use this document to verify your wiring connections for each node while assembling and testing.

---

## 🟢 Node A Configuration

**Hardware Components:**
* Microcontroller: ESP32 (Standard)
* Display: 1.3" OLED (SH1106)
* Radio: LoRa SX1278 (433MHz)
* Accessories: Jumper wires, Breadboard

### 🔌 Node A Wiring Diagram

| LoRa SX1278 Pin | ESP32 Pin | Description |
| :--- | :--- | :--- |
| VCC | 3.3V | Power (Do NOT use 5V) |
| GND | GND | Ground |
| SCK | GPIO 18 | SPI Clock |
| MISO | GPIO 19 | SPI Master In Slave Out |
| MOSI | GPIO 23 | SPI Master Out Slave In |
| NSS / CS | GPIO 5 | SPI Chip Select |
| RST | GPIO 14 | Reset |
| DIO0 | GPIO 26 | Interrupt Pin |

| 1.3" OLED Pin | ESP32 Pin | Description |
| :--- | :--- | :--- |
| VCC | 3.3V | Power |
| GND | GND | Ground |
| SDA | GPIO 21 | I2C Data |
| SCL | GPIO 22 | I2C Clock |

---

## 🔵 Node B Configuration

**Hardware Components:**
* Microcontroller: ESP32-S3
* Display: 0.96" OLED (SSD1306)
* Radio: LoRa SX1278 (433MHz)
* Accessories: Jumper wires, Breadboard

### 🔌 Node B Wiring Diagram

| LoRa SX1278 Pin | ESP32-S3 Pin | Description |
| :--- | :--- | :--- |
| VCC | 3.3V | Power (Do NOT use 5V) |
| GND | GND | Ground |
| SCK | GPIO 12 | SPI Clock |
| MISO | GPIO 13 | SPI Master In Slave Out |
| MOSI | GPIO 11 | SPI Master Out Slave In |
| NSS / CS | GPIO 10 | SPI Chip Select |
| RST | GPIO 14 | Reset |
| DIO0 | GPIO 15 | Interrupt Pin |

| 0.96" OLED Pin | ESP32-S3 Pin | Description |
| :--- | :--- | :--- |
| VCC | 3.3V | Power |
| GND | GND | Ground |
| SDA | GPIO 8 | I2C Data |
| SCL | GPIO 9 | I2C Clock |
