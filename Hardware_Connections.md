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

## 🟡 Node C Configuration

**Hardware Components:**
* Microcontroller: ESP8266 NodeMCU (or Standard ESP32)
* Display: 0.96" OLED (SSD1306)
* Radio: LoRa SX1278 (433MHz)
* Accessories: Jumper wires, Breadboard

### 🔌 Node C Wiring Diagram (Option 1: ESP8266 NodeMCU)

| LoRa SX1278 Pin | ESP8266 Label | GPIO Pin | Description |
| :--- | :--- | :--- | :--- |
| VCC | 3.3V | 3.3V | Power (Do NOT use 5V) |
| GND | GND | GND | Ground |
| SCK | D5 | GPIO 14 | SPI Clock |
| MISO | D6 | GPIO 12 | SPI Master In Slave Out |
| MOSI | D7 | GPIO 13 | SPI Master Out Slave In |
| NSS / CS | D8 | GPIO 15 | SPI Chip Select |
| RST | D0 | GPIO 16 | Reset |
| DIO0 | D2 | GPIO 4 | Interrupt Pin |

| 0.96" OLED Pin | ESP8266 Label | GPIO Pin | Description |
| :--- | :--- | :--- | :--- |
| VCC | 3.3V | 3.3V | Power |
| GND | GND | GND | Ground |
| SDA | D2 | GPIO 4 | I2C Data |
| SCL | D1 | GPIO 5 | I2C Clock |

---

### 🔌 Node C Wiring Diagram (Option 2: Standard ESP32)

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

| 0.96" OLED Pin | ESP32 Pin | Description |
| :--- | :--- | :--- |
| VCC | 3.3V | Power |
| GND | GND | Ground |
| SDA | GPIO 21 | I2C Data |
| SCL | GPIO 22 | I2C Clock |
