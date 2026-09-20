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
const int ROUTE_BROADCAST_INTERVAL = 5000;
const int ROUTE_TIMEOUT = 15000;
const int MAX_ROUTES = 10;
const int MAX_HOPS = 5; // TTL limit to prevent infinite looping

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
unsigned long lastBroadcastTime = 2500;
unsigned long lastSendTime = 0;
int msgIdCounter = 100;

void updateOrAddRoute(String dest, String nextHop, int hops, int rssi) {
  if (dest == MY_NODE_ID) return;
  unsigned long now = millis();

  for (int i = 0; i < routeCount; i++) {
    if (routingTable[i].destNode == dest) {
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

  if (routeCount < MAX_ROUTES) {
    routingTable[routeCount].destNode = dest;
    routingTable[routeCount].nextHop = nextHop;
    routingTable[routeCount].hops = hops;
    routingTable[routeCount].rssi = rssi;
    routingTable[routeCount].lastUpdated = now;
    routingTable[routeCount].valid = true;
    routeCount++;
    Serial.println(">>> NEW ROUTE: Dest=" + dest + " via " + nextHop + " (" + String(hops) + "h)");
  }
}

String getNextHop(String dest) {
  for (int i = 0; i < routeCount; i++) {
    if (routingTable[i].destNode == dest && routingTable[i].valid) {
      return routingTable[i].nextHop;
    }
  }
  return ""; // No route known
}

void updateOLED(String statusLine, String lastRx) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  display.setCursor(0, 0);
  display.println("NODE B (Forwarding)");

  display.setCursor(0, 16);
  display.print("Status: ");
  display.println(statusLine);

  display.setCursor(0, 32);
  display.print("Last RX/Fwd: ");
  display.println(lastRx);

  display.display();
}

void broadcastRoutes() {
  String packetStr = "RT:" + MY_NODE_ID + ":";
  for (int i = 0; i < routeCount; i++) {
    if (routingTable[i].valid && routingTable[i].destNode != MY_NODE_ID) {
      packetStr += routingTable[i].destNode + "," + String(routingTable[i].hops) + ";";
    }
  }
  LoRa.beginPacket();
  LoRa.print(packetStr);
  LoRa.endPacket();
}

void forwardPacket(String src, String dest, int hops, int msgId, String payload) {
  if (hops >= MAX_HOPS) {
    Serial.println("Drop packet: MAX HOPS Exceeded (" + String(hops) + ")");
    return;
  }

  String nextHop = getNextHop(dest);
  if (nextHop == "") {
    Serial.println("Drop packet: No route to forward to " + dest);
    return;
  }

  // Increment hop count and forward
  String fwdPacket = "DATA:" + src + ":" + dest + ":" + String(hops + 1) + ":" + String(msgId) + ":" + payload;

  delay(100); // Radio settle delay
  LoRa.beginPacket();
  LoRa.print(fwdPacket);
  LoRa.endPacket();

  Serial.println(">>> FORWARDED packet: " + src + " -> " + dest + " via " + nextHop + " (Hop " + String(hops + 1) + ")");
  updateOLED("FWD " + src + "->" + dest, "ID#" + String(msgId));
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

  Serial.println("Node B - Phase 8 Multi-Hop Packet Forwarding Ready");
  updateOLED("Ready", "None");
}

void loop() {
  // 1. Receive & Process incoming packets
  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    String incoming = "";
    while (LoRa.available()) {
      incoming += (char)LoRa.read();
    }
    int rssi = LoRa.packetRssi();

    if (incoming.startsWith("RT:")) {
      // Handle Route Advertisements
      int firstColon = incoming.indexOf(':');
      int secondColon = incoming.indexOf(':', firstColon + 1);
      if (firstColon != -1 && secondColon != -1) {
        String senderId = incoming.substring(firstColon + 1, secondColon);
        String routesPayload = incoming.substring(secondColon + 1);

        if (senderId != MY_NODE_ID) {
          updateOrAddRoute(senderId, senderId, 1, rssi);
          int startIdx = 0;
          while (startIdx < routesPayload.length()) {
            int semiIdx = routesPayload.indexOf(';', startIdx);
            if (semiIdx == -1) break;
            String routePair = routesPayload.substring(startIdx, semiIdx);
            int commaIdx = routePair.indexOf(',');
            if (commaIdx != -1) {
              String dest = routePair.substring(0, commaIdx);
              int remoteHops = routePair.substring(commaIdx + 1).toInt();
              if (dest != MY_NODE_ID) {
                updateOrAddRoute(dest, senderId, remoteHops + 1, rssi);
              }
            }
            startIdx = semiIdx + 1;
          }
        }
      }
    } 
    else if (incoming.startsWith("DATA:")) {
      // Handle DATA Packets: DATA:SRC:DEST:HOPS:MSG_ID:PAYLOAD
      int p1 = incoming.indexOf(':');
      int p2 = incoming.indexOf(':', p1 + 1);
      int p3 = incoming.indexOf(':', p2 + 1);
      int p4 = incoming.indexOf(':', p3 + 1);
      int p5 = incoming.indexOf(':', p4 + 1);

      if (p5 != -1) {
        String src = incoming.substring(p1 + 1, p2);
        String dest = incoming.substring(p2 + 1, p3);
        int hops = incoming.substring(p3 + 1, p4).toInt();
        int msgId = incoming.substring(p4 + 1, p5).toInt();
        String payload = incoming.substring(p5 + 1);

        if (dest == MY_NODE_ID) {
          // Packet arrived at final destination!
          Serial.println(">>> RECEIVED FINAL DATA from " + src + " (Hops: " + String(hops) + "): " + payload);
          updateOLED("RX Final", src + ": " + payload);
        } else {
          // Packet is meant for another node -> FORWARD IT!
          forwardPacket(src, dest, hops, msgId, payload);
        }
      }
    }
  }

  // 2. Broadcast routes periodically
  if (millis() - lastBroadcastTime > ROUTE_BROADCAST_INTERVAL) {
    broadcastRoutes();
    lastBroadcastTime = millis();
  }
}
