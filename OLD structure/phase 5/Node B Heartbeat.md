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

// Node Configuration
const String MY_NODE_ID = "NODE_B";
const String TARGET_NODE_ID = "NODE_A";
const int HEARTBEAT_INTERVAL = 5000; // Send heartbeat every 5 seconds
const int NODE_TIMEOUT = 12000;       // Consider target offline after 12 seconds

unsigned long lastHeartbeatTime = 2500; // Offset start by 2.5s to avoid packet collision with Node A
unsigned long targetLastSeenTime = 0;
bool targetOnline = false;
int targetRssi = 0;
int targetUptime = 0;

void updateOLED() {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  // Line 1: Header
  display.setCursor(0, 0);
  display.println("NODE B (Heartbeat)");

  // Line 2: Target Node Status
  display.setCursor(0, 16);
  display.print(TARGET_NODE_ID + ": ");
  if (targetOnline) {
    display.println("ONLINE");
  } else {
    display.println("OFFLINE");
  }

  // Line 3: Last Seen Time
  display.setCursor(0, 32);
  if (targetLastSeenTime == 0) {
    display.println("Last Seen: Never");
  } else {
    unsigned long elapsedSec = (millis() - targetLastSeenTime) / 1000;
    display.println("Last Seen: " + String(elapsedSec) + "s ago");
  }

  // Line 4: RSSI if online
  display.setCursor(0, 48);
  if (targetOnline && targetRssi != 0) {
    display.println("RSSI: " + String(targetRssi) + " dBm");
  } else if (!targetOnline && targetLastSeenTime != 0) {
    display.println("Status: TIMEOUT!");
  }

  display.display();
}

void sendHeartbeat() {
  unsigned long uptimeSec = millis() / 1000;
  String packetStr = "HB:" + MY_NODE_ID + ":" + String(uptimeSec);

  LoRa.beginPacket();
  LoRa.print(packetStr);
  LoRa.endPacket();

  Serial.println("TX Heartbeat -> " + packetStr);
}

void setup() {
  Serial.begin(115200);

  Wire.begin(8, 9);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    while (1);
  }

  Serial.println("Node B - Phase 5 Heartbeat System Ready");
  updateOLED();
}

void loop() {
  // 1. Check for incoming Heartbeat packets
  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    String incoming = "";
    while (LoRa.available()) {
      incoming += (char)LoRa.read();
    }
    int rssi = LoRa.packetRssi();

    // Parse packet format HB:SENDER_ID:UPTIME
    if (incoming.startsWith("HB:")) {
      int firstColon = incoming.indexOf(':');
      int secondColon = incoming.indexOf(':', firstColon + 1);

      if (firstColon != -1 && secondColon != -1) {
        String senderId = incoming.substring(firstColon + 1, secondColon);
        int uptime = incoming.substring(secondColon + 1).toInt();

        if (senderId == TARGET_NODE_ID) {
          targetLastSeenTime = millis();
          targetOnline = true;
          targetRssi = rssi;
          targetUptime = uptime;

          Serial.println("RX Heartbeat from " + senderId + " [Uptime: " + String(uptime) + "s, RSSI: " + String(rssi) + "]");
        }
      }
    }
  }

  // 2. Check for Target Timeout
  if (targetOnline && (millis() - targetLastSeenTime > NODE_TIMEOUT)) {
    targetOnline = false;
    Serial.println(">>> ALERT: " + TARGET_NODE_ID + " went OFFLINE (Timeout)!");
  }

  // 3. Send Heartbeat Periodically (Offset from Node A)
  if (millis() - lastHeartbeatTime > HEARTBEAT_INTERVAL) {
    sendHeartbeat();
    lastHeartbeatTime = millis();
  }

  // 4. Update OLED display regularly
  static unsigned long lastDisplayUpdate = 0;
  if (millis() - lastDisplayUpdate > 1000) {
    updateOLED();
    lastDisplayUpdate = millis();
  }
}
