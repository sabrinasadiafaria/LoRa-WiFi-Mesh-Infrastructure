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

---

## 🟡 Node C Configuration (Arduino Uno / Nano)

**Hardware Components:**
* Microcontroller: **Arduino Uno** or **Arduino Nano**
* Display: 0.96" OLED (SSD1306)
* Radio: LoRa SX1278 (433MHz)
* Accessories: Jumper wires, Breadboard

> ⚠️ **IMPORTANT VOLTAGE WARNING**: LoRa SX1278 VCC **MUST** be connected to Arduino **3.3V pin**! Connecting LoRa VCC to 5V will burn the SX1278 chip.

### 🔌 Node C Wiring Diagram (Arduino Uno / Nano)

| LoRa SX1278 Pin | Arduino Uno / Nano Pin | Description |
| :--- | :--- | :--- |
| **VCC** | **3.3V** | Power (**MUST be 3.3V, NOT 5V!**) |
| GND | GND | Ground |
| SCK | Pin 13 | Hardware SPI Clock |
| MISO | Pin 12 | Hardware SPI Master In Slave Out |
| MOSI | Pin 11 | Hardware SPI Master Out Slave In |
| NSS / CS | Pin 10 | SPI Chip Select |
| RST | Pin 9 | Reset |
| DIO0 | Pin 2 | External Interrupt INT0 |

| 0.96" OLED Pin | Arduino Uno / Nano Pin | Description |
| :--- | :--- | :--- |
| VCC | 5V or 3.3V | Power |
| GND | GND | Ground |
| SDA | **Pin A4** | Hardware I2C Data |
| SCL | **Pin A5** | Hardware I2C Clock |
