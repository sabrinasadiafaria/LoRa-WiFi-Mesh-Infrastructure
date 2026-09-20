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
const int ROUTE_BROADCAST_INTERVAL = 5000; // Broadcast routes every 5s
const int ROUTE_TIMEOUT = 15000;           // Expire route after 15s
const int MAX_ROUTES = 10;

struct RouteEntry {
  String destNode;
  String nextHop;
  int hops;
  int rssi;
  unsigned long lastUpdated;
  bool valid;
};

RouteEntry routingTable[MAX_ROUTES];
int routeCount = 0;
unsigned long lastBroadcastTime = 0;

void updateOrAddRoute(String dest, String nextHop, int hops, int rssi) {
  // RULE 1: Never add a route to yourself
  if (dest == MY_NODE_ID) return;

  unsigned long now = millis();

  // Search if route to dest already exists
  for (int i = 0; i < routeCount; i++) {
    if (routingTable[i].destNode == dest) {
      // Update if advertisement comes from current nextHop, OR offers a strictly shorter path
      if (nextHop == routingTable[i].nextHop || hops < routingTable[i].hops || !routingTable[i].valid) {
        routingTable[i].nextHop = nextHop;
        routingTable[i].hops = hops;
        routingTable[i].rssi = rssi;
        routingTable[i].lastUpdated = now;
        routingTable[i].valid = true;
      }
      return;
    }
  }

  // Add new route if destination not in table
  if (routeCount < MAX_ROUTES) {
    routingTable[routeCount].destNode = dest;
    routingTable[routeCount].nextHop = nextHop;
    routingTable[routeCount].hops = hops;
    routingTable[routeCount].rssi = rssi;
    routingTable[routeCount].lastUpdated = now;
    routingTable[routeCount].valid = true;
    routeCount++;
    Serial.println(">>> NEW ROUTE DISCOVERED: Dest=" + dest + " via " + nextHop + " (Hops: " + String(hops) + ")");
  }
}

void checkRouteTimeouts() {
  unsigned long now = millis();
  for (int i = 0; i < routeCount; i++) {
    if (routingTable[i].valid && (now - routingTable[i].lastUpdated > ROUTE_TIMEOUT)) {
      routingTable[i].valid = false;
      Serial.println(">>> ALERT: Route Expired for Dest: " + routingTable[i].destNode);
    }
  }
}

void printRoutingTable() {
  Serial.println("\n========== ROUTING TABLE (" + MY_NODE_ID + ") ==========");
  Serial.println("DEST        NEXT_HOP    HOPS   RSSI    STATUS");
  int activeCount = 0;
  for (int i = 0; i < routeCount; i++) {
    if (routingTable[i].valid) {
      activeCount++;
      Serial.println(routingTable[i].destNode + "      " + routingTable[i].nextHop + "      " + 
                     String(routingTable[i].hops) + "      " + String(routingTable[i].rssi) + "dBm  ACTIVE");
    }
  }
  if (activeCount == 0) Serial.println(" (No active routes discovered)");
  Serial.println("============================================\n");
}

void updateOLED() {
  display.clearBuffer();
  display.setFont(u8g2_font_ncenB08_tr);

  // Line 1: Header
  display.drawStr(0, 10, "NODE A (Routing)");

  // Line 2: Active Route Count
  int activeRoutes = 0;
  int firstActiveIdx = -1;
  for (int i = 0; i < routeCount; i++) {
    if (routingTable[i].valid) {
      activeRoutes++;
      if (firstActiveIdx == -1) firstActiveIdx = i;
    }
  }

  display.setCursor(0, 24);
  display.print("Active Routes: " + String(activeRoutes));

  if (firstActiveIdx != -1) {
    display.setCursor(0, 40);
    display.print("> " + routingTable[firstActiveIdx].destNode + " via " + routingTable[firstActiveIdx].nextHop);
    display.setCursor(0, 54);
    display.print("Hops: " + String(routingTable[firstActiveIdx].hops) + " (" + String(routingTable[firstActiveIdx].rssi) + "dBm)");
  } else {
    display.drawStr(0, 44, "Building routes...");
  }

  display.sendBuffer();
}

void broadcastRoutes() {
  // Format: RT:SENDER_ID:DEST1,HOPS1;DEST2,HOPS2...
  String packetStr = "RT:" + MY_NODE_ID + ":";

  // Include valid learned routes (excluding self)
  for (int i = 0; i < routeCount; i++) {
    if (routingTable[i].valid && routingTable[i].destNode != MY_NODE_ID) {
      packetStr += routingTable[i].destNode + "," + String(routingTable[i].hops) + ";";
    }
  }

  LoRa.beginPacket();
  LoRa.print(packetStr);
  LoRa.endPacket();

  Serial.println("TX Route Broadcast -> " + packetStr);
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

  Serial.println("Node A - Phase 7 Dynamic Routing Table Ready");
  updateOLED();
}

void loop() {
  // 1. Receive & Process Route Advertisements
  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    String incoming = "";
    while (LoRa.available()) {
      incoming += (char)LoRa.read();
    }
    int rssi = LoRa.packetRssi();

    // Parse packet format RT:SENDER_ID:DEST1,HOPS1;DEST2,HOPS2;
    if (incoming.startsWith("RT:")) {
      int firstColon = incoming.indexOf(':');
      int secondColon = incoming.indexOf(':', firstColon + 1);

      if (firstColon != -1 && secondColon != -1) {
        String senderId = incoming.substring(firstColon + 1, secondColon);
        String routesPayload = incoming.substring(secondColon + 1);

        if (senderId != MY_NODE_ID) {
          // Direct neighbor route (1 hop)
          updateOrAddRoute(senderId, senderId, 1, rssi);

          // Parse advertised multi-hop routes
          int startIdx = 0;
          while (startIdx < routesPayload.length()) {
            int semiIdx = routesPayload.indexOf(';', startIdx);
            if (semiIdx == -1) break;

            String routePair = routesPayload.substring(startIdx, semiIdx);
            int commaIdx = routePair.indexOf(',');
            if (commaIdx != -1) {
              String dest = routePair.substring(0, commaIdx);
              int remoteHops = routePair.substring(commaIdx + 1).toInt();

              // Avoid routing loops back to self
              if (dest != MY_NODE_ID) {
                updateOrAddRoute(dest, senderId, remoteHops + 1, rssi);
              }
            }
            startIdx = semiIdx + 1;
          }
        }
      }
    }
  }

  // 2. Check route timeouts
  checkRouteTimeouts();

  // 3. Broadcast routes periodically
  if (millis() - lastBroadcastTime > ROUTE_BROADCAST_INTERVAL) {
    broadcastRoutes();
    lastBroadcastTime = millis();
  }

  // 4. Update OLED & Serial logs regularly
  static unsigned long lastUpdate = 0;
  if (millis() - lastUpdate > 3000) {
    updateOLED();
    printRoutingTable();
    lastUpdate = millis();
  }
}
