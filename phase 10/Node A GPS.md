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

// GPS Hardware Serial Pins on ESP32 (Serial2)
#define GPS_RX_PIN 16
#define GPS_TX_PIN 17

const String MY_NODE_ID = "NODE_A";
const int GPS_BROADCAST_INTERVAL = 6000; // Broadcast GPS telemetry every 6s

// Default / Base GPS Coordinates (UIU Campus, Dhaka)
float latitude = 23.797810;
float longitude = 90.449720;
int batteryLevel = 98;
bool hasGpsLock = false;

unsigned long lastGpsBroadcast = 0;

void updateOLED(float lat, float lon, int bat, bool lock) {
  display.clearBuffer();
  display.setFont(u8g2_font_ncenB08_tr);

  display.drawStr(0, 10, "--- NODE A (GPS) ---");
  
  display.setCursor(0, 26);
  display.print("Lat: ");
  display.print(lat, 5);

  display.setCursor(0, 40);
  display.print("Lon: ");
  display.print(lon, 5);

  display.setCursor(0, 56);
  display.print("Bat: ");
  display.print(bat);
  display.print("% | ");
  if (lock) {
    display.print("GPS: FIX");
  } else {
    display.print("GPS: SIM");
  }
  
  display.sendBuffer();
}

void readGpsSensor() {
  // Read NMEA sentences if GPS module is sending data on Serial2
  while (Serial2.available() > 0) {
    String nmeaLine = Serial2.readStringUntil('\n');
    // Parse $GPRMC or $GPGGA if valid fix
    if (nmeaLine.startsWith("$GPRMC") || nmeaLine.startsWith("$GPGGA")) {
      int commaCount = 0;
      for (int i = 0; i < nmeaLine.length(); i++) {
        if (nmeaLine.charAt(i) == ',') commaCount++;
      }
      if (commaCount >= 6) {
        hasGpsLock = true;
      }
    }
  }

  // If no physical GPS fix on bench test, add realistic small movement drift
  if (!hasGpsLock) {
    latitude += ((random(-5, 6)) * 0.00001);
    longitude += ((random(-5, 6)) * 0.00001);
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
  updateOLED(latitude, longitude, batteryLevel, hasGpsLock);
}

void setup() {
  Serial.begin(115200);

  // Initialize GPS Hardware Serial2
  Serial2.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);

  // Step 1: Initialize Display
  Wire.begin(21, 22);
  display.begin();

  updateOLED(latitude, longitude, batteryLevel, false);
  delay(1000);

  // Step 2: Initialize LoRa
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    while (1);
  }

  Serial.println("Node A - Phase 10 GPS Tracking Ready");
}

void loop() {
  // 1. Parse hardware GPS serial stream
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
