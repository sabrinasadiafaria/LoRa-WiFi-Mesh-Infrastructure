#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <U8g2lib.h>

U8G2_SH1106_128X64_NONAME_F_HW_I2C display(U8G2_R0, U8X8_PIN_NONE);

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

const String MY_NODE_ID = "NODE_A";
const int GPS_BROADCAST_INTERVAL = 5000;

float latitude = 0.0;
float longitude = 0.0;
int batteryLevel = 98;
int satellites = 0;
bool hasGpsFix = false;
String rawNmeaStatus = "Searching Satellites...";

unsigned long lastGpsBroadcast = 0;

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
  
  // Parse $GPRMC or $GNRMC (Recommended Minimum Navigation Information)
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
        rawNmeaStatus = "GPS FIX LOCKED";
      }
    } else {
      hasGpsFix = false;
      rawNmeaStatus = "No Satellite Fix Yet";
    }
  }
  // Parse $GPGGA or $GNGGA (Global Positioning System Fix Data)
  else if (line.startsWith("$GPGGA") || line.startsWith("$GNGGA")) {
    String satsStr = getField(line, ',', 7);
    if (satsStr.length() > 0) {
      satellites = satsStr.toInt();
    }
  }
}

void updateOLED(float lat, float lon, int bat, bool fix, int sats) {
  display.clearBuffer();
  display.setFont(u8g2_font_ncenB08_tr);

  display.drawStr(0, 10, "--- NODE A (HARDWARE GPS) ---");
  
  if (fix) {
    display.setCursor(0, 26);
    display.print("Lat: ");
    display.print(lat, 5);

    display.setCursor(0, 40);
    display.print("Lon: ");
    display.print(lon, 5);

    display.setCursor(0, 56);
    display.print("Bat: ");
    display.print(bat);
    display.print("% | Sat: ");
    display.print(sats);
  } else {
    display.setCursor(0, 28);
    display.print("GPS: Searching Sats...");
    display.setCursor(0, 44);
    display.print("Sats in view: ");
    display.print(sats);
    display.setCursor(0, 58);
    display.print("Place near window/sky");
  }
  
  display.sendBuffer();
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
  
  // Format: GPS:SENDER_ID:LATITUDE:LONGITUDE:BATTERY:UPTIME
  String telemetryPacket = "GPS:" + MY_NODE_ID + ":" + 
                          String(latitude, 6) + ":" + 
                          String(longitude, 6) + ":" + 
                          String(batteryLevel) + ":" + 
                          String(uptimeSec);

  LoRa.beginPacket();
  LoRa.print(telemetryPacket);
  LoRa.endPacket();

  Serial.println("TX GPS Telemetry -> " + telemetryPacket);
  updateOLED(latitude, longitude, batteryLevel, hasGpsFix, satellites);
}

void setup() {
  Serial.begin(115200);

  // Initialize GPS Hardware Serial2 at 9600 baud (Standard Neo-6M baud rate)
  Serial2.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);

  // STEP 1: Initialize Display
  Wire.begin(21, 22);
  display.begin();

  updateOLED(0.0, 0.0, batteryLevel, false, 0);
  delay(1000);

  // STEP 2: Initialize LoRa
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    while (1);
  }

  Serial.println("Node A - Phase 10 Hardware GPS Module Ready");
}

void loop() {
  // 1. Read real GPS stream from hardware Serial2
  readGpsSensor();

  // 2. Receive incoming GPS Telemetry packets from other nodes
  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    String incoming = "";
    while (LoRa.available()) {
      incoming += (char)LoRa.read();
    }
    int rssi = LoRa.packetRssi();

    if (incoming.startsWith("GPS:")) {
      Serial.println("RX Telemetry [RSSI " + String(rssi) + "dBm]: " + incoming);
    }
  }

  // 3. Broadcast GPS Telemetry periodically
  if (millis() - lastGpsBroadcast > GPS_BROADCAST_INTERVAL) {
    broadcastGpsTelemetry();
    lastGpsBroadcast = millis();
  }
}
