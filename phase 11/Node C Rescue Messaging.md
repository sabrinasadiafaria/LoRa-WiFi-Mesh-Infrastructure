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

// External SOS Push Button Pin on Node C (Arduino Nano Pin D5)
#define EXTERNAL_SOS_BUTTON 5 // Pin D5 -> Connect to one side of button, other side to GND

#define LORA_FREQ 433E6

const String MY_NODE_ID = "NODE_C";

float latitude = 23.798100;
float longitude = 90.450100;
int msgIdCounter = 200;
bool sosAlertActive = false;
String lastSosNode = "";

void updateOLED(String header, String line1, String line2) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  if (sosAlertActive) {
    display.setCursor(0, 0);
    display.println(F("!! SOS EMERGENCY !!"));
    display.setCursor(0, 18);
    display.print(F("VICTIM: "));
    display.println(lastSosNode);
    display.setCursor(0, 34);
    display.println(line1);
    display.setCursor(0, 48);
    display.println(line2);
  } else {
    display.setCursor(0, 0);
    display.println(F("--- NODE C RESCUE ---"));
    display.setCursor(0, 18);
    display.println(header);
    display.setCursor(0, 34);
    display.println(line1);
    display.setCursor(0, 48);
    display.println(line2);
  }

  display.display();
}

void sendSosAlert() {
  sosAlertActive = true;
  lastSosNode = MY_NODE_ID;

  // Format: SOS:SENDER_ID:LATITUDE:LONGITUDE:PAYLOAD
  String sosPacket = "SOS:" + MY_NODE_ID + ":" + String(latitude, 6) + ":" + String(longitude, 6) + ":MAYDAY FIELD RESCUER";

  for (int i = 0; i < 3; i++) {
    LoRa.beginPacket();
    LoRa.print(sosPacket);
    LoRa.endPacket();
    delay(100);
  }

  Serial.println(F("\n🚨 [SOS BROADCAST SENT]"));
  updateOLED("SOS BROADCAST SENT", "Lat: " + String(latitude, 4), "Lon: " + String(longitude, 4));
}

void setup() {
  Serial.begin(115200);
  delay(500);

  // Configure External SOS Push Button on Pin D5 (Active LOW)
  pinMode(EXTERNAL_SOS_BUTTON, INPUT_PULLUP);

  // STEP 1: Initialize Display
  Wire.begin();
  delay(200);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    display.begin(SSD1306_SWITCHCAPVCC, 0x3D);
  }

  display.clearDisplay();
  display.display();
  delay(200);

  updateOLED("Status: Booting", "Rescue System ON", "Press Button for SOS");
  delay(1000);

  // STEP 2: Initialize LoRa
  SPI.begin();
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println(F("LoRa init failed!"));
    while (1);
  }

  Serial.println(F("Node C - Arduino Nano Rescue System Ready"));
  updateOLED("Status: READY", "Press SOS Button", "Mesh Active");
}

void loop() {
  // Check External SOS Push Button
  if (digitalRead(EXTERNAL_SOS_BUTTON) == LOW) {
    delay(50);
    if (digitalRead(EXTERNAL_SOS_BUTTON) == LOW) {
      sendSosAlert();
      delay(2000);
    }
  }

  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    String incoming = "";
    while (LoRa.available()) {
      incoming += (char)LoRa.read();
    }
    int rssi = LoRa.packetRssi();

    if (incoming.startsWith("SOS:")) {
      int p1 = incoming.indexOf(':');
      int p2 = incoming.indexOf(':', p1 + 1);
      int p3 = incoming.indexOf(':', p2 + 1);
      int p4 = incoming.indexOf(':', p3 + 1);

      if (p4 != -1) {
        String victimId = incoming.substring(p1 + 1, p2);
        String victimLat = incoming.substring(p2 + 1, p3);
        String victimLon = incoming.substring(p3 + 1, p4);
        String sosMsg = incoming.substring(p4 + 1);

        sosAlertActive = true;
        lastSosNode = victimId;

        Serial.println(F("\n🚨🚨🚨 [SOS EMERGENCY RECEIVED] 🚨🚨🚨"));
        Serial.print(F("Victim: ")); Serial.println(victimId);
        Serial.print(F("Lat: ")); Serial.println(victimLat);
        Serial.print(F("Lon: ")); Serial.println(victimLon);

        updateOLED("SOS ALERT!", "Lat: " + victimLat, "Lon: " + victimLon);
      }
    } 
    else if (incoming.startsWith("TEXT:")) {
      int p1 = incoming.indexOf(':');
      int p2 = incoming.indexOf(':', p1 + 1);
      int p3 = incoming.indexOf(':', p2 + 1);
      int p4 = incoming.indexOf(':', p3 + 1);

      if (p4 != -1) {
        String src = incoming.substring(p1 + 1, p2);
        String dest = incoming.substring(p2 + 1, p3);
        int msgId = incoming.substring(p3 + 1, p4).toInt();
        String txtMsg = incoming.substring(p4 + 1);

        if (dest == MY_NODE_ID || dest == "BROADCAST") {
          Serial.print(F(">>> RX TEXT from ")); Serial.println(src);
          updateOLED("RX TEXT from " + src, "ID#" + String(msgId), txtMsg);
        }
      }
    }
  }
}
