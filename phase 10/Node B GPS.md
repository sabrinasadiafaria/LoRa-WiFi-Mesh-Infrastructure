# Phase 10 — Node B (ESP32 + LoRa SX1278 + NEO-M8N GPS)

## 📌 Wiring Pinout Table for Node B

| Module Component | Module Pin | ESP32 Pin | Description |
| :--- | :--- | :--- | :--- |
| **LoRa SX1278** | VCC | **3.3V** | Power (Do NOT use 5V for LoRa) |
| | GND | GND | Ground |
| | SCK | **GPIO 18** | SPI Clock |
| | MISO | **GPIO 19** | SPI Master In |
| | MOSI | **GPIO 23** | SPI Master Out |
| | NSS / CS | **GPIO 5** | SPI Chip Select |
| | RST | **GPIO 14** | Reset Pin |
| | DIO0 | **GPIO 26** | Hardware Interrupt |
| **0.96" OLED** | VCC | **3.3V or 5V** | Display Power |
| | GND | GND | Display Ground |
| | SDA | **GPIO 21** | I2C Data |
| | SCL | **GPIO 22** | I2C Clock |
| **NEO-M8N GPS** | VCC | **3.3V or 5V** | GPS Power |
| | GND | GND | GPS Ground |
| | **TX** | **GPIO 16 (RX2)** | Connect GPS TX to ESP32 RX2 |
| | **RX** | **GPIO 17 (TX2)** | Connect GPS RX to ESP32 TX2 |

---

## 💻 Arduino C++ Sketch Code

```cpp
#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

#define LORA_SCK   18
#define LORA_MISO  19
#define LORA_MOSI  23
#define LORA_SS    5
#define LORA_RST   14
#define LORA_DIO0  26

#define LORA_FREQ 433E6

// GPS Hardware Serial2 Pins on ESP32
#define GPS_RX_PIN 16 // ESP32 RX2 -> Connect to GPS TX
#define GPS_TX_PIN 17 // ESP32 TX2 -> Connect to GPS RX

const String MY_NODE_ID = "NODE_B";
const int GPS_BROADCAST_INTERVAL = 5000;

float latitude = 0.0;
float longitude = 0.0;
int batteryLevel = 94;
int satellites = 0;
bool hasGpsFix = false;
String lastRxTelemetry = "No RX Yet";

unsigned long lastGpsBroadcast = 2000; // Offset broadcast to prevent collision

// Helper to parse NMEA coordinate format (DDMM.MMMM to Decimal Degrees)
float parseNmeaCoord(String val, String dir) {
  if (val.length() < 4) return 0.0;
  int dotIdx = val.indexOf('.');
  if (dotIdx == -1) return 0.0;
  
  int degLen = dotIdx - 2;
  float degrees = val.substring(0, degLen).toFloat();
  float minutes = val.substring(degLen).toFloat();
  float decDeg = degrees + (minutes / 60.0);
  
  if (dir == "S" || dir == "W") decDeg = -decDeg;
  return decDeg;
}

// Split NMEA comma-separated strings
String getField(String data, char separator, int index) {
  int found = 0;
  int strIndex[] = { 0, -1 };
  int maxIndex = data.length() - 1;

  for (int i = 0; i <= maxIndex && found <= index; i++) {
    if (data.charAt(i) == separator || i == maxIndex) {
      found++;
      strIndex[0] = strIndex[1] + 1;
      strIndex[1] = (i == maxIndex) ? i + 1 : i;
    }
  }
  return found > index ? data.substring(strIndex[0], strIndex[1]) : "";
}

void parseNmeaSentence(String line) {
  line.trim();
  
  // Parse $GPRMC or $GNRMC (NEO-M8N transmits GNSS GN prefix by default)
  if (line.startsWith("$GPRMC") || line.startsWith("$GNRMC")) {
    String status = getField(line, ',', 2); // 'A' = Valid, 'V' = Warning
    if (status == "A") {
      String latStr = getField(line, ',', 3);
      String latDir = getField(line, ',', 4);
      String lonStr = getField(line, ',', 5);
      String lonDir = getField(line, ',', 6);

      float parsedLat = parseNmeaCoord(latStr, latDir);
      float parsedLon = parseNmeaCoord(lonStr, lonDir);

      if (parsedLat != 0.0 && parsedLon != 0.0) {
        latitude = parsedLat;
        longitude = parsedLon;
        hasGpsFix = true;
      }
    } else {
      hasGpsFix = false;
    }
  }
  // Parse $GPGGA or $GNGGA (Satellite Count)
  else if (line.startsWith("$GPGGA") || line.startsWith("$GNGGA")) {
    String satsStr = getField(line, ',', 7);
    if (satsStr.length() > 0) {
      satellites = satsStr.toInt();
    }
  }
}

void updateOLED() {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  display.setCursor(0, 0);
  display.println("--- NODE B (NEO-M8N) ---");

  if (hasGpsFix) {
    display.setCursor(0, 14);
    display.print("Lat: ");
    display.println(latitude, 5);

    display.setCursor(0, 26);
    display.print("Lon: ");
    display.println(longitude, 5);

    display.setCursor(0, 38);
    display.print("Sats: ");
    display.print(satellites);
    display.print(" | Bat: ");
    display.print(batteryLevel);
    display.println("%");
  } else {
    display.setCursor(0, 14);
    display.println("GPS: Searching Sats...");
    display.setCursor(0, 26);
    display.print("Sats in view: ");
    display.println(satellites);
    display.setCursor(0, 38);
    display.println("Bench Fallback Active");
  }

  display.setCursor(0, 52);
  display.println(lastRxTelemetry);

  display.display();
}

void readGpsSensor() {
  while (Serial2.available() > 0) {
    String line = Serial2.readStringUntil('\n');
    if (line.length() > 0) {
      parseNmeaSentence(line);
    }
  }
}

void broadcastGpsTelemetry() {
  unsigned long uptimeSec = millis() / 1000;

  // Use real GPS coordinates if locked, otherwise bench fallback coordinates
  float txLat = hasGpsFix ? latitude : 23.797950;
  float txLon = hasGpsFix ? longitude : 90.449850;

  // Packet Format: GPS:SENDER_ID:LATITUDE:LONGITUDE:BATTERY:UPTIME
  String telemetryPacket = "GPS:" + MY_NODE_ID + ":" + 
                          String(txLat, 6) + ":" + 
                          String(txLon, 6) + ":" + 
                          String(batteryLevel) + ":" + 
                          String(uptimeSec);

  LoRa.beginPacket();
  LoRa.print(telemetryPacket);
  LoRa.endPacket();

  Serial.println("TX Telemetry -> " + telemetryPacket);
  updateOLED();
}

void setup() {
  Serial.begin(115200);

  // Initialize GPS Hardware Serial2 at 9600 baud for NEO-M8N
  Serial2.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);

  Wire.begin(21, 22);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);

  updateOLED();
  delay(1000);

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    while (1);
  }

  Serial.println("Node B (ESP32 + NEO-M8N GPS) Ready");
}

void loop() {
  // 1. Read real GPS stream
  readGpsSensor();

  // 2. Process incoming packets
  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    String incoming = "";
    while (LoRa.available()) {
      incoming += (char)LoRa.read();
    }
    int rssi = LoRa.packetRssi();

    if (incoming.startsWith("GPS:")) {
      Serial.println("RX Telemetry [" + String(rssi) + "dBm]: " + incoming);
      int firstColon = incoming.indexOf(':');
      int secondColon = incoming.indexOf(':', firstColon + 1);
      if (firstColon != -1 && secondColon != -1) {
        String senderId = incoming.substring(firstColon + 1, secondColon);
        lastRxTelemetry = "RX: " + senderId + " (" + String(rssi) + "dBm)";
        updateOLED();
      }
    }
  }

  // 3. Broadcast telemetry
  if (millis() - lastGpsBroadcast > GPS_BROADCAST_INTERVAL) {
    broadcastGpsTelemetry();
    lastGpsBroadcast = millis();
  }
}
```
