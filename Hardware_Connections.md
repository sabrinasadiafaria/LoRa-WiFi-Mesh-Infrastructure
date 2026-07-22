# Hardware Connections

Use this document to verify your wiring connections for each node while assembling and testing.

---

## 🟢 Node A Configuration (ESP32 Standard)

**Hardware Components:**
* Microcontroller: ESP32 (Standard)
* Display: 1.3" OLED (SH1106)
* Radio: LoRa SX1278 (433MHz)
* GPS: NEO-6M / GT-U7 / GY-GPS6MV2
* Button: External Push Button (SOS Alert Trigger)

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

| GPS Module Pin | ESP32 Pin | Description |
| :--- | :--- | :--- |
| VCC | 3.3V or 5V | Power |
| GND | GND | Ground |
| TX | GPIO 16 | Hardware Serial2 RX2 |
| RX | GPIO 17 | Hardware Serial2 TX2 |

| External SOS Button | ESP32 Pin | Description |
| :--- | :--- | :--- |
| **Pin 1 (Leg A)** | **GPIO 4** | SOS Signal Pin (Active LOW) |
| **Pin 2 (Leg B)** | **GND** | Ground |

---

## 🔵 Node B Configuration (ESP32-S3)

**Hardware Components:**
* Microcontroller: ESP32-S3
* Display: 0.96" OLED (SSD1306)
* Radio: LoRa SX1278 (433MHz)
* GPS: NEO-6M / GT-U7 / GY-GPS6MV2
* Button: External Push Button (SOS Alert Trigger)

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

| GPS Module Pin | ESP32-S3 Pin | Description |
| :--- | :--- | :--- |
| VCC | 3.3V or 5V | Power |
| GND | GND | Ground |
| TX | GPIO 16 | Hardware Serial2 RX2 |
| RX | GPIO 17 | Hardware Serial2 TX2 |

| External SOS Button | ESP32-S3 Pin | Description |
| :--- | :--- | :--- |
| **Pin 1 (Leg A)** | **GPIO 4** | SOS Signal Pin (Active LOW) |
| **Pin 2 (Leg B)** | **GND** | Ground |

---

## 🟡 Node C Configuration (Arduino Uno / Nano)

**Hardware Components:**
* Microcontroller: **Arduino Uno** or **Arduino Nano**
* Display: 0.96" OLED (SSD1306)
* Radio: LoRa SX1278 (433MHz)
* GPS: NEO-6M / GT-U7 / GY-GPS6MV2
* Button: External Push Button (SOS Alert Trigger)

### 🔌 Node C Wiring Diagram (Arduino Uno / Nano)

| LoRa SX1278 Pin | Arduino Uno / Nano Pin | Description |
| :--- | :--- | :--- |
| **VCC** | **3.3V** | Power (**MUST be 3.3V!**) |
| GND | GND | Ground |
| SCK | Pin 13 | Hardware SPI Clock |
| MISO | Pin 12 | Hardware SPI Master In |
| MOSI | Pin 11 | Hardware SPI Master Out |
| NSS / CS | Pin 10 | SPI Chip Select |
| RST | Pin 9 | Reset |
| DIO0 | Pin 2 | External Interrupt INT0 |

| 0.96" OLED Pin | Arduino Uno / Nano Pin | Description |
| :--- | :--- | :--- |
| VCC | 5V or 3.3V | Power |
| GND | GND | Ground |
| SDA | **Pin A4** | Hardware I2C Data |
| SCL | **Pin A5** | Hardware I2C Clock |

| GPS Module Pin | Arduino Nano Pin | Description |
| :--- | :--- | :--- |
| VCC | 5V or 3.3V | Power |
| GND | GND | Ground |
| TX | Pin D4 | SoftwareSerial RX |
| RX | Pin D3 | SoftwareSerial TX |

| External SOS Button | Arduino Nano Pin | Description |
| :--- | :--- | :--- |
| **Pin 1 (Leg A)** | **Pin D5** | SOS Signal Pin (Active LOW) |
| **Pin 2 (Leg B)** | **GND** | Ground |
