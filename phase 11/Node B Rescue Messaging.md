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

// External SOS Push Button Pin (GPIO 4 to GND)
#define EXTERNAL_SOS_BUTTON 4

const String MY_NODE_ID = "NODE_B";
const int HEARTBEAT_INTERVAL = 4000;    // Broadcast Heartbeat every 4s to keep connection alive ALWAYS
const int TEXT_BROADCAST_INTERVAL = 10000;
const int NEIGHBOR_TIMEOUT = 45000;      // 45s timeout

// Active Connected Neighbor Tracking
struct NeighborNode {
  String id;
  int rssi;
  unsigned long lastSeen;
  bool active;
};

NeighborNode neighbors[5];
int neighborCount = 0;

float latitude = 23.797950;
float longitude = 90.449850;
int batteryLevel = 92;
int msgIdCounter = 100;

unsigned long lastHeartbeat = 1500;
unsigned long lastTextBroadcast = 5000;
bool sosAlertActive = false;
String lastSosNode = "";

void updateNeighbor(String nodeSender, int rssi) {
  if (nodeSender == MY_NODE_ID || nodeSender.length() == 0) return;
  unsigned long now = millis();

  for (int i = 0; i < neighborCount; i++) {
    if (neighbors[i].id == nodeSender) {
      neighbors[i].rssi = rssi;
      neighbors[i].lastSeen = now;
      neighbors[i].active = true;
      return;
    }
  }

  if (neighborCount < 5) {
    neighbors[neighborCount].id = nodeSender;
    neighbors[neighborCount].rssi = rssi;
    neighbors[neighborCount].lastSeen = now;
    neighbors[neighborCount].active = true;
    neighborCount++;
    Serial.println(">>> NEW CONNECTED NODE ADDED: " + nodeSender);
  }
}

void pruneNeighbors() {
  unsigned long now = millis();
  for (int i = 0; i < neighborCount; i++) {
    if (neighbors[i].active && (now - neighbors[i].lastSeen > NEIGHBOR_TIMEOUT)) {
      neighbors[i].active = false;
      Serial.println(">>> NODE DISCONNECTED: " + neighbors[i].id);
    }
  }
}

String getConnectedNodesStr() {
  String connStr = "";
  for (int i = 0; i < neighborCount; i++) {
    if (neighbors[i].active) {
      if (connStr.length() > 0) connStr += ",";
      connStr += neighbors[i].id.substring(5);
    }
  }
  if (connStr.length() == 0) return "None";
  return connStr;
}

void updateOLED(String line1, String line2) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  String headerStr = "NODE B | CON: " + getConnectedNodesStr();

  if (sosAlertActive) {
    display.setCursor(0, 0);
    display.println("!! 🚨 SOS EMERGENCY 🚨 !!");
    display.setCursor(0, 18);
    display.print("VICTIM: ");
    display.println(lastSosNode);
    display.setCursor(0, 34);
    display.println(line1);
    display.setCursor(0, 48);
    display.println(line2);
  } else {
    display.setCursor(0, 0);
    display.println(headerStr);

    display.setCursor(0, 18);
    display.println(line1);
    display.setCursor(0, 34);
    display.println(line2);
    display.setCursor(0, 50);
    display.println("Lat:" + String(latitude, 4) + " Lon:" + String(longitude, 4));
  }

  display.display();
}

void sendHeartbeat() {
  unsigned long uptimeSec = millis() / 1000;
  String hbPacket = "HB:" + MY_NODE_ID + ":" + String(uptimeSec);
  
  LoRa.beginPacket();
  LoRa.print(hbPacket);
  LoRa.endPacket();
}

void sendSosAlert() {
  sosAlertActive = true;
  lastSosNode = MY_NODE_ID;
  
  String sosPacket = "SOS:" + MY_NODE_ID + ":" + String(latitude, 6) + ":" + String(longitude, 6) + ":MAYDAY MEDICAL ASSISTANCE";

  for (int i = 0; i < 3; i++) {
    LoRa.beginPacket();
    LoRa.print(sosPacket);
    LoRa.endPacket();
    delay(400);
  }

  Serial.println("\n🚨🚨🚨 [SOS BROADCAST SENT TO ALL NODES] -> " + sosPacket + "\n");
  updateOLED("SOS SENT TO ALL", "Lat:" + String(latitude, 4) + " Lon:" + String(longitude, 4));
}

void broadcastTextMessage(String messageText) {
  int msgId = msgIdCounter++;
  String textPacket = "TEXT:" + MY_NODE_ID + ":ALL:" + String(msgId) + ":" + messageText;

  LoRa.beginPacket();
  LoRa.print(textPacket);
  LoRa.endPacket();

  Serial.println("TX BROADCAST -> " + textPacket);
  updateOLED("TX BROADCAST", messageText);
}

void setup() {
  Serial.begin(115200);
  pinMode(EXTERNAL_SOS_BUTTON, INPUT_PULLUP);

  // STEP 1: Initialize Display
  Wire.begin(8, 9);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);

  updateOLED("Display Ready...", "Booting Node B");
  delay(1000);

  // STEP 2: Initialize LoRa Radio
  updateOLED("Init LoRa Radio...", "Frequency 433MHz");
  delay(800);

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    updateOLED("LoRa FAIL!", "Check SPI Pins!");
    while (1);
  }

  updateOLED("LoRa Ready!", "Mesh Active");
  delay(1500);

  Serial.println("Node B - Phase 11 Permanent Connection Mesh Ready");
}

void loop() {
  pruneNeighbors();

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
    int rssi = LoRa.packetRssi();

    if (incoming.startsWith("HB:")) {
      int p1 = incoming.indexOf(':');
      int p2 = incoming.indexOf(':', p1 + 1);
      if (p1 != -1) {
        String senderId = (p2 == -1) ? incoming.substring(p1 + 1) : incoming.substring(p1 + 1, p2);
        updateNeighbor(senderId, rssi);
        if (!sosAlertActive) {
          updateOLED("Connected Nodes", getConnectedNodesStr());
        }
      }
    }
    else if (incoming.startsWith("SOS:")) {
      int p1 = incoming.indexOf(':');
      int p2 = incoming.indexOf(':', p1 + 1);
      int p3 = incoming.indexOf(':', p2 + 1);
      int p4 = incoming.indexOf(':', p3 + 1);

      if (p4 != -1) {
        String victimId = incoming.substring(p1 + 1, p2);
        String victimLat = incoming.substring(p2 + 1, p3);
        String victimLon = incoming.substring(p3 + 1, p4);
        String sosMsg = incoming.substring(p4 + 1);

        updateNeighbor(victimId, rssi);
        sosAlertActive = true;
        lastSosNode = victimId;

        Serial.println("\n🚨🚨🚨 [SOS EMERGENCY RECEIVED FROM " + victimId + "] 🚨🚨🚨");
        Serial.println("Location: " + victimLat + ", " + victimLon);
        Serial.println("Payload: " + sosMsg + " (RSSI: " + String(rssi) + "dBm)\n");

        updateOLED("SOS: " + victimId + " (" + String(rssi) + "dBm)", "Lat:" + victimLat + " Lon:" + victimLon);
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
          updateNeighbor(src, rssi);
          Serial.println(">>> RX MSG from " + src + " [RSSI " + String(rssi) + "dBm]: " + txtMsg);
          if (!sosAlertActive) {
            updateOLED("RX: " + src + " (" + String(rssi) + "dBm)", txtMsg);
          }
        }
      }
    }
  }

  // 3. Broadcast Periodic Heartbeats ALWAYS
  if (millis() - lastHeartbeat > HEARTBEAT_INTERVAL) {
    sendHeartbeat();
    lastHeartbeat = millis();
  }

  // 4. Broadcast Periodic Text Messages
  if (millis() - lastTextBroadcast > TEXT_BROADCAST_INTERVAL) {
    static int msgCount = 1;
    String sampleMsg = "Node B Patrol #" + String(msgCount++);
    broadcastTextMessage(sampleMsg);
    lastTextBroadcast = millis();
  }
}
