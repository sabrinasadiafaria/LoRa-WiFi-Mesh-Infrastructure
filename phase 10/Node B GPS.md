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

const String MY_NODE_ID = "NODE_B";
const int GPS_BROADCAST_INTERVAL = 5000;

// Fixed / Test GPS Coordinates for Node B (UIU Campus, Dhaka)
float latitude = 23.797950;
float longitude = 90.449850;
int batteryLevel = 92;

unsigned long lastGpsBroadcast = 2500; // Offset start to avoid packet collision

void updateOLED(float lat, float lon, int bat, String lastRx) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  display.setCursor(0, 0);
  display.println("--- NODE B (TEST GPS) ---");

  display.setCursor(0, 16);
  display.print("Lat: ");
  display.println(lat, 5);

  display.setCursor(0, 28);
  display.print("Lon: ");
  display.println(lon, 5);

  display.setCursor(0, 42);
  display.print("Bat: ");
  display.print(bat);
  display.print("% [TEST FIX]");

  display.setCursor(0, 54);
  display.println(lastRx);

  display.display();
}

void simulateGpsMovement() {
  // Minor realistic drift around test location
  latitude += ((random(-3, 4)) * 0.00001);
  longitude += ((random(-3, 4)) * 0.00001);
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

  Serial.println("TX Telemetry -> " + telemetryPacket);
  updateOLED(latitude, longitude, batteryLevel, "TX Telemetry OK");
}

void setup() {
  Serial.begin(115200);

  Wire.begin(8, 9);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);

  updateOLED(latitude, longitude, batteryLevel, "Booting Node B...");
  delay(1000);

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    while (1);
  }

  Serial.println("Node B - Phase 10 Test Location GPS Ready");
  updateOLED(latitude, longitude, batteryLevel, "Mesh Active");
}

void loop() {
  simulateGpsMovement();

  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    String incoming = "";
    while (LoRa.available()) {
      incoming += (char)LoRa.read();
    }
    int rssi = LoRa.packetRssi();

    if (incoming.startsWith("GPS:")) {
      Serial.println("RX Telemetry [RSSI " + String(rssi) + "dBm]: " + incoming);
      
      // Parse sender ID
      int firstColon = incoming.indexOf(':');
      int secondColon = incoming.indexOf(':', firstColon + 1);
      if (firstColon != -1 && secondColon != -1) {
        String senderId = incoming.substring(firstColon + 1, secondColon);
        updateOLED(latitude, longitude, batteryLevel, "RX GPS from " + senderId);
      }
    }
  }

  if (millis() - lastGpsBroadcast > GPS_BROADCAST_INTERVAL) {
    broadcastGpsTelemetry();
    lastGpsBroadcast = millis();
  }
}
