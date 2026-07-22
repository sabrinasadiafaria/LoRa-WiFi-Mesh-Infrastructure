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
#define EXTERNAL_SOS_BUTTON 5

#define LORA_FREQ 433E6

const String MY_NODE_ID = "NODE_C";

float latitude = 23.798100;
float longitude = 90.450100;
int lastRssi = 0;
int msgIdCounter = 200;
unsigned long lastTextBroadcast = 7000;
bool sosAlertActive = false;
String lastSosNode = "";

void updateOLED(String line1, String line2, String line3) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  if (sosAlertActive) {
    display.setCursor(0, 0);
    display.println(F("!! 🚨 SOS EMERGENCY 🚨 !!"));
    display.setCursor(0, 18);
    display.print(F("VICTIM: "));
    display.println(lastSosNode);
    display.setCursor(0, 34);
    display.println(line1);
    display.setCursor(0, 48);
    display.println(line2);
  } else {
    display.setCursor(0, 0);
    display.println(F("--- NODE C (MESH) ---"));
    display.setCursor(0, 18);
    display.println(line1);
    display.setCursor(0, 34);
    display.println(line2);
    display.setCursor(0, 48);
    display.println(line3);
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

  Serial.println(F("\n🚨🚨🚨 [SOS BROADCAST SENT TO ALL NODES]"));
  updateOLED("SOS SENT TO ALL", "Lat: " + String(latitude, 4), "Lon: " + String(longitude, 4));
}

void broadcastTextMessage(String messageText) {
  int msgId = msgIdCounter++;
  // Format: TEXT:SRC:DEST:MSG_ID:TEXT_BODY (DEST = ALL for universal broadcast!)
  String textPacket = "TEXT:" + MY_NODE_ID + ":ALL:" + String(msgId) + ":" + messageText;

  LoRa.beginPacket();
  LoRa.print(textPacket);
  LoRa.endPacket();

  Serial.println(F("TX BROADCAST to ALL NODES"));
  updateOLED("TX -> ALL NODES", messageText, "Lat:" + String(latitude,4) + " Lon:" + String(longitude,4));
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

  updateOLED("Display Ready...", "Booting Node C", "Step 1/2 Complete");
  delay(1000);

  // STEP 2: Initialize LoRa with explicit SPI delay
  updateOLED("Init LoRa Radio...", "Frequency 433MHz", "Step 2/2");
  delay(800);

  SPI.begin();
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println(F("LoRa init failed!"));
    updateOLED("LoRa FAIL!", "Check SPI Pins!", "System Halted");
    while (1);
  }

  updateOLED("LoRa Ready!", "All Systems GO", "Mesh Network ACTIVE");
  delay(1500);

  Serial.println(F("Node C - Arduino Nano Universal Broadcast Ready"));
}

void loop() {
  // 1. Check External SOS Push Button
  if (digitalRead(EXTERNAL_SOS_BUTTON) == LOW) {
    delay(50);
    if (digitalRead(EXTERNAL_SOS_BUTTON) == LOW) {
      sendSosAlert();
      delay(2000);
    }
  }

  // 2. Process Incoming Packets from ALL Nodes
  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    String incoming = "";
    while (LoRa.available()) {
      incoming += (char)LoRa.read();
    }
    lastRssi = LoRa.packetRssi();

    if (incoming.startsWith("SOS:")) {
      int p1 = incoming.indexOf(':');
      int p2 = incoming.indexOf(':', p1 + 1);
      int p3 = incoming.indexOf(':', p2 + 1);
      int p4 = incoming.indexOf(':', p3 + 1);

      if (p4 != -1) {
        String victimId = incoming.substring(p1 + 1, p2);
        String victimLat = incoming.substring(p2 + 1, p3);
        String victimLon = incoming.substring(p3 + 1, p4);

        sosAlertActive = true;
        lastSosNode = victimId;

        Serial.println(F("\n🚨🚨🚨 [SOS EMERGENCY RECEIVED] 🚨🚨🚨"));
        Serial.print(F("Victim: ")); Serial.println(victimId);

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

        if (src != MY_NODE_ID && (dest == MY_NODE_ID || dest == "ALL" || dest == "BROADCAST")) {
          Serial.print(F(">>> RX TEXT from ")); Serial.print(src);
          Serial.print(F(" [RSSI ")); Serial.print(lastRssi); Serial.println(F("dBm]"));

          updateOLED("RX: " + src + " (" + String(lastRssi) + "dBm)", txtMsg, "Lat:" + String(latitude,4) + " Lon:" + String(longitude,4));
        }
      }
    }
  }

  // 3. Periodically transmit broadcast text messages to ALL connected nodes
  if (millis() - lastTextBroadcast > TEXT_BROADCAST_INTERVAL && !sosAlertActive) {
    static int msgCount = 1;
    String sampleMsg = "Nano Base #" + String(msgCount++);
    broadcastTextMessage(sampleMsg);
    lastTextBroadcast = millis();
  }
}
