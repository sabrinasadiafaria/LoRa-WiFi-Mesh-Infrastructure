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
const int HEARTBEAT_INTERVAL = 5000; // Broadcast heartbeat every 5 seconds
const int NEIGHBOR_TIMEOUT = 12000;  // Remove neighbor if not heard for 12 seconds
const int MAX_NEIGHBORS = 10;

struct Neighbor {
  String id;
  int rssi;
  unsigned long lastSeen;
  int uptime;
  bool active;
};

Neighbor neighbors[MAX_NEIGHBORS];
int neighborCount = 0;
unsigned long lastHeartbeatTime = 0;

void addOrUpdateNeighbor(String senderId, int rssi, int uptime) {
  unsigned long now = millis();
  
  // 1. Search if neighbor already exists
  for (int i = 0; i < neighborCount; i++) {
    if (neighbors[i].id == senderId) {
      neighbors[i].rssi = rssi;
      neighbors[i].lastSeen = now;
      neighbors[i].uptime = uptime;
      if (!neighbors[i].active) {
        neighbors[i].active = true;
        Serial.println(">>> RECONNECTED Neighbor: " + senderId);
      }
      return;
    }
  }

  // 2. Add as new neighbor if space permits
  if (neighborCount < MAX_NEIGHBORS) {
    neighbors[neighborCount].id = senderId;
    neighbors[neighborCount].rssi = rssi;
    neighbors[neighborCount].lastSeen = now;
    neighbors[neighborCount].uptime = uptime;
    neighbors[neighborCount].active = true;
    neighborCount++;
    Serial.println(">>> NEW NEIGHBOR DISCOVERED: " + senderId + " [Total: " + String(neighborCount) + "]");
  }
}

void checkTimeouts() {
  unsigned long now = millis();
  for (int i = 0; i < neighborCount; i++) {
    if (neighbors[i].active && (now - neighbors[i].lastSeen > NEIGHBOR_TIMEOUT)) {
      neighbors[i].active = false;
      Serial.println(">>> ALERT: Neighbor Lost (Timeout): " + neighbors[i].id);
    }
  }
}

int getActiveNeighborCount() {
  int count = 0;
  for (int i = 0; i < neighborCount; i++) {
    if (neighbors[i].active) count++;
  }
  return count;
}

void updateOLED() {
  display.clearBuffer();
  display.setFont(u8g2_font_ncenB08_tr);

  // Line 1: Header
  display.drawStr(0, 10, "NODE A (Discovery)");

  // Line 2: Active Neighbor Count
  int activeNum = getActiveNeighborCount();
  display.setCursor(0, 24);
  display.print("Neighbors Active: " + String(activeNum));

  // Line 3 & 4: Display First Active Neighbor
  int displayIdx = -1;
  for (int i = 0; i < neighborCount; i++) {
    if (neighbors[i].active) {
      displayIdx = i;
      break;
    }
  }

  if (displayIdx != -1) {
    unsigned long agoSec = (millis() - neighbors[displayIdx].lastSeen) / 1000;
    display.setCursor(0, 40);
    display.print("> " + neighbors[displayIdx].id + " (" + String(neighbors[displayIdx].rssi) + "dBm)");
    display.setCursor(0, 54);
    display.print("Seen: " + String(agoSec) + "s ago");
  } else {
    display.drawStr(0, 44, "Scanning...");
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

  Serial.println("Node A - Phase 6 Dynamic Neighbor Discovery Ready");
  updateOLED();
}

void loop() {
  // 1. Receive & Process incoming Heartbeats
  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    String incoming = "";
    while (LoRa.available()) {
      incoming += (char)LoRa.read();
    }
    int rssi = LoRa.packetRssi();

    if (incoming.startsWith("HB:")) {
      int firstColon = incoming.indexOf(':');
      int secondColon = incoming.indexOf(':', firstColon + 1);

      if (firstColon != -1 && secondColon != -1) {
        String senderId = incoming.substring(firstColon + 1, secondColon);
        int uptime = incoming.substring(secondColon + 1).toInt();

        if (senderId != MY_NODE_ID) {
          addOrUpdateNeighbor(senderId, rssi, uptime);
        }
      }
    }
  }

  // 2. Check for neighbor timeouts
  checkTimeouts();

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
