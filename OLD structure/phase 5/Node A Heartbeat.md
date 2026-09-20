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

// Node Configuration
const String MY_NODE_ID = "NODE_A";
const String TARGET_NODE_ID = "NODE_B";
const int HEARTBEAT_INTERVAL = 5000; // Send heartbeat every 5 seconds
const int NODE_TIMEOUT = 12000;       // Consider target offline after 12 seconds

unsigned long lastHeartbeatTime = 0;
unsigned long targetLastSeenTime = 0;
bool targetOnline = false;
int targetRssi = 0;
int targetUptime = 0;

void updateOLED() {
  display.clearBuffer();
  display.setFont(u8g2_font_ncenB08_tr);

  // Line 1: Header
  display.drawStr(0, 10, "NODE A (Heartbeat)");

  // Line 2: Target Node Status
  display.setCursor(0, 26);
  display.print(TARGET_NODE_ID + ": ");
  if (targetOnline) {
    display.print("ONLINE");
  } else {
    display.print("OFFLINE");
  }

  // Line 3: Last Seen Time
  display.setCursor(0, 42);
  if (targetLastSeenTime == 0) {
    display.print("Last Seen: Never");
  } else {
    unsigned long elapsedSec = (millis() - targetLastSeenTime) / 1000;
    display.print("Last Seen: " + String(elapsedSec) + "s ago");
  }

  // Line 4: RSSI if online
  if (targetOnline && targetRssi != 0) {
    display.setCursor(0, 58);
    display.print("RSSI: " + String(targetRssi) + " dBm");
  } else if (!targetOnline && targetLastSeenTime != 0) {
    display.setCursor(0, 58);
    display.print("Status: TIMEOUT!");
  }

  display.sendBuffer();
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

  Wire.begin(21, 22);
  display.begin();

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    while (1);
  }

  Serial.println("Node A - Phase 5 Heartbeat System Ready");
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

  // 3. Send Heartbeat Periodically
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
