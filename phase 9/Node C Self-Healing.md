#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// Hardware SPI Pins for Arduino Uno / Nano (ATmega328P)
#define LORA_SS    10
#define LORA_RST   9
#define LORA_DIO0  2

#define LORA_FREQ 433E6

const String MY_NODE_ID = "NODE_C";
const int ROUTE_BROADCAST_INTERVAL = 5000;
const int ROUTE_TIMEOUT = 12000;
const int MAX_ROUTES = 5;
const int MAX_HOPS = 5;

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
unsigned long lastBroadcastTime = 4000;
unsigned long lastSendTime = 0;
int msgIdCounter = 200;

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
    Serial.println(F(">>> NEW ROUTE DISCOVERED"));
  }
}

void checkRouteTimeouts() {
  unsigned long now = millis();
  for (int i = 0; i < routeCount; i++) {
    if (routingTable[i].valid && (now - routingTable[i].lastUpdated > ROUTE_TIMEOUT)) {
      routingTable[i].valid = false;
      Serial.println(F(">>> ALERT [SELF-HEALING]: Route Lost!"));
    }
  }
}

String getBestNextHop(String dest) {
  int bestHops = 999;
  String bestHop = "";
  for (int i = 0; i < routeCount; i++) {
    if (routingTable[i].destNode == dest && routingTable[i].valid) {
      if (routingTable[i].hops < bestHops) {
        bestHops = routingTable[i].hops;
        bestHop = routingTable[i].nextHop;
      }
    }
  }
  return bestHop;
}

void updateOLED(String statusLine, String lastRx) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  display.setCursor(0, 0);
  display.println(F("NODE C (Self-Healing)"));

  display.setCursor(0, 16);
  display.print(F("Status: "));
  display.println(statusLine);

  display.setCursor(0, 32);
  display.print(F("Last RX/Fwd: "));
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
    Serial.println(F("Drop: MAX HOPS"));
    return;
  }

  String nextHop = getBestNextHop(dest);
  if (nextHop == "") {
    Serial.println(F(">>> SELF-HEAL DROP: No Route"));
    return;
  }

  String fwdPacket = "DATA:" + src + ":" + dest + ":" + String(hops + 1) + ":" + String(msgId) + ":" + payload;

  delay(100);
  LoRa.beginPacket();
  LoRa.print(fwdPacket);
  LoRa.endPacket();

  Serial.println(F(">>> SELF-HEALED FORWARD"));
  updateOLED("FWD via " + nextHop, "ID#" + String(msgId));
}

void setup() {
  Serial.begin(115200);

  Wire.begin();
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);

  SPI.begin();
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println(F("LoRa init failed!"));
    while (1);
  }

  Serial.println(F("Node C - Arduino Nano Self-Healing Ready"));
  updateOLED("Mesh Ready", "Waiting...");
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
          Serial.println(F(">>> RECEIVED FINAL DATA!"));
          updateOLED("RX Final", src + ": " + payload);
        } else {
          forwardPacket(src, dest, hops, msgId, payload);
        }
      }
    }
  }

  // 2. Monitor route health & purge failed nodes
  checkRouteTimeouts();

  // 3. Broadcast routes periodically
  if (millis() - lastBroadcastTime > ROUTE_BROADCAST_INTERVAL) {
    broadcastRoutes();
    lastBroadcastTime = millis();
  }
}
