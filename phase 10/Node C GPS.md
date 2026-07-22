#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

#define OLED_RESET -1

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Hardware SPI Pins for Arduino Uno / Nano (ATmega328P)
#define LORA_SS    10
#define LORA_RST   9
#define LORA_DIO0  2

#define LORA_FREQ 433E6

const String MY_NODE_ID = "NODE_C";
const int GPS_BROADCAST_INTERVAL = 6000;

// Default / Base GPS Coordinates (UIU Campus, Dhaka)
float latitude = 23.798100;
float longitude = 90.450100;
int batteryLevel = 88;
bool hasGpsLock = false;

unsigned long lastGpsBroadcast = 4500; // Offset start by 4.5s to avoid collision

void updateOLED(float lat, float lon, int bat, bool lock) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  display.setCursor(0, 0);
  display.println(F("--- NODE C (GPS) ---"));

  display.setCursor(0, 18);
  display.print(F("Lat: "));
  display.println(lat, 5);

  display.setCursor(0, 32);
  display.print(F("Lon: "));
  display.println(lon, 5);

  display.setCursor(0, 48);
  display.print(F("Bat: "));
  display.print(bat);
  display.print(F("% | "));
  if (lock) {
    display.println(F("GPS: FIX"));
  } else {
    display.println(F("GPS: SIM"));
  }

  display.display();
}

void simulateGpsMovement() {
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

  Serial.println(F("TX GPS Telemetry"));
  updateOLED(latitude, longitude, batteryLevel, hasGpsLock);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  // STEP 1: Initialize Display
  Wire.begin();
  delay(200);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    display.begin(SSD1306_SWITCHCAPVCC, 0x3D);
  }

  display.clearDisplay();
  display.display();
  delay(200);

  updateOLED(latitude, longitude, batteryLevel, false);
  delay(1000);

  // STEP 2: Initialize LoRa
  SPI.begin();
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println(F("LoRa init failed!"));
    updateOLED(0.0, 0.0, 0, false);
    while (1);
  }

  Serial.println(F("Node C - Arduino Nano GPS Ready"));
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
      Serial.println(F("RX Telemetry Packet"));
    }
  }

  if (millis() - lastGpsBroadcast > GPS_BROADCAST_INTERVAL) {
    broadcastGpsTelemetry();
    lastGpsBroadcast = millis();
  }
}
