#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <U8g2lib.h>

// SH1106 1.3" OLED (Change to U8G2_SSD1306_128X64_NONAME_F_HW_I2C if using SSD1306 0.96")
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
String lastRxTelemetry = "No RX Yet";

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
  
  // Parse $GPRMC or $GNRMC (Recommended Minimum Navigation Data)
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
      rawNmeaStatus = "Searching Satellites...";
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
  display.clearBuffer();
  display.setFont(u8g2_font_ncenB08_tr);

  display.drawStr(0, 10, "--- NODE A (NEO-6M) ---");
  
  if (hasGpsFix) {
    display.setCursor(0, 24);
    display.print("Lat: ");
    display.print(latitude, 5);

    display.setCursor(0, 36);
    display.print("Lon: ");
    display.print(longitude, 5);

    display.setCursor(0, 48);
    display.print("Sats: ");
    display.print(satellites);
    display.print(" | Bat: ");
    display.print(batteryLevel);
    display.print("%");
  } else {
    display.setCursor(0, 24);
    display.print("GPS: Searching Sats...");
    display.setCursor(0, 36);
    display.print("Sats in view: ");
    display.print(satellites);
    display.setCursor(0, 48);
    display.print("Bench Fallback Lat/Lon");
  }

  display.setCursor(0, 60);
  display.print(lastRxTelemetry);
  
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
  
  // Use real GPS coordinates if locked, otherwise bench fallback coordinates
  float txLat = hasGpsFix ? latitude : 23.797700;
  float txLon = hasGpsFix ? longitude : 90.449600;

  // Packet Format: GPS:SENDER_ID:LATITUDE:LONGITUDE:BATTERY:UPTIME
  String telemetryPacket = "GPS:" + MY_NODE_ID + ":" + 
                          String(txLat, 6) + ":" + 
                          String(txLon, 6) + ":" + 
                          String(batteryLevel) + ":" + 
                          String(uptimeSec);

  LoRa.beginPacket();
  LoRa.print(telemetryPacket);
  LoRa.endPacket();

  Serial.println("TX GPS Telemetry -> " + telemetryPacket);
  updateOLED();
}

void setup() {
  Serial.begin(115200);

  // Initialize GPS Hardware Serial2 at 9600 baud
  Serial2.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);

  // STEP 1: Initialize Display
  Wire.begin(21, 22);
  display.begin();

  updateOLED();
  delay(1000);

  // STEP 2: Initialize LoRa
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    while (1);
  }

  Serial.println("Node A (ESP32 + NEO-6M GPS) Ready");
}

void loop() {
  // 1. Read real GPS NMEA stream
  readGpsSensor();

  // 2. Listen for incoming LoRa GPS Telemetry
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

  // 3. Periodic Broadcast
  if (millis() - lastGpsBroadcast > GPS_BROADCAST_INTERVAL) {
    broadcastGpsTelemetry();
    lastGpsBroadcast = millis();
  }
}
