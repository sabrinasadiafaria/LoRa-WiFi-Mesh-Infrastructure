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
unsigned long lastHeartbeatTime = 2500; // Offset by 2.5s to avoid collision with Node A

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
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  // Line 1: Header
  display.setCursor(0, 0);
  display.println("NODE B (Discovery)");

  // Line 2: Active Neighbor Count
  int activeNum = getActiveNeighborCount();
  display.setCursor(0, 16);
  display.print("Neighbors Active: ");
  display.println(activeNum);

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
    display.setCursor(0, 32);
    display.print("> ");
    display.print(neighbors[displayIdx].id);
    display.print(" (");
    display.print(neighbors[displayIdx].rssi);
    display.println("dBm)");

    display.setCursor(0, 48);
    display.print("Seen: ");
    display.print(agoSec);
    display.println("s ago");
  } else {
    display.setCursor(0, 32);
    display.println("Scanning...");
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

  Serial.println("Node B - Phase 6 Dynamic Neighbor Discovery Ready");
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
