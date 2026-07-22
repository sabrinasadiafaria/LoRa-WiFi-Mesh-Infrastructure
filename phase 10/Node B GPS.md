#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

#define LORA_SCK   12
#define LORA_MISO  13
#define LORA_MOSI  11
#define LORA_SS    10
#define LORA_RST   14
#define LORA_DIO0  15

#define LORA_FREQ 433E6

// GPS Hardware Serial Pins on ESP32-S3 (Serial2)
#define GPS_RX_PIN 16
#define GPS_TX_PIN 17

const String MY_NODE_ID = "NODE_B";
const int GPS_BROADCAST_INTERVAL = 6000;

// Default / Base GPS Coordinates (UIU Campus, Dhaka)
float latitude = 23.797950;
float longitude = 90.449850;
int batteryLevel = 92;
bool hasGpsLock = false;

unsigned long lastGpsBroadcast = 3000; // Offset start by 3s to avoid collision

void updateOLED(float lat, float lon, int bat, bool lock) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  display.setCursor(0, 0);
  display.println("--- NODE B (GPS) ---");

  display.setCursor(0, 18);
  display.print("Lat: ");
  display.println(lat, 5);

  display.setCursor(0, 32);
  display.print("Lon: ");
  display.println(lon, 5);

  display.setCursor(0, 48);
  display.print("Bat: ");
  display.print(bat);
  display.print("% | ");
  if (lock) {
    display.println("GPS: FIX");
  } else {
    display.println("GPS: SIM");
  }

  display.display();
}

void readGpsSensor() {
  while (Serial2.available() > 0) {
    String nmeaLine = Serial2.readStringUntil('\n');
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

  Serial2.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);

  Wire.begin(8, 9);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);

  updateOLED(latitude, longitude, batteryLevel, false);
  delay(1000);

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    while (1);
  }

  Serial.println("Node B - Phase 10 GPS Tracking Ready");
}

void loop() {
  readGpsSensor();

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

  if (millis() - lastGpsBroadcast > GPS_BROADCAST_INTERVAL) {
    broadcastGpsTelemetry();
    lastGpsBroadcast = millis();
  }
}
