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
const int HEARTBEAT_INTERVAL = 4000;
const int TEXT_BROADCAST_INTERVAL = 10000;
const int NEIGHBOR_TIMEOUT = 45000;

// Active Connected Neighbor Tracking
struct NeighborNode {
  String id;
  int rssi;
  unsigned long lastSeen;
  bool active;
};

NeighborNode neighbors[3];
int neighborCount = 0;

float latitude = 23.798100;
float longitude = 90.450100;
int msgIdCounter = 200;

unsigned long lastHeartbeat = 3000;
unsigned long lastTextBroadcast = 7000;
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

  if (neighborCount < 3) {
    neighbors[neighborCount].id = nodeSender;
    neighbors[neighborCount].rssi = rssi;
    neighbors[neighborCount].lastSeen = now;
    neighbors[neighborCount].active = true;
    neighborCount++;
    Serial.println(F(">>> NEW CONNECTED NODE ADDED"));
  }
}

void pruneNeighbors() {
  unsigned long now = millis();
  for (int i = 0; i < neighborCount; i++) {
    if (neighbors[i].active && (now - neighbors[i].lastSeen > NEIGHBOR_TIMEOUT)) {
      neighbors[i].active = false;
      Serial.println(F(">>> NODE DISCONNECTED"));
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

  String headerStr = "NODE C | CON: " + getConnectedNodesStr();

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

  String sosPacket = "SOS:" + MY_NODE_ID + ":" + String(latitude, 6) + ":" + String(longitude, 6) + ":MAYDAY FIELD RESCUER";

  for (int i = 0; i < 3; i++) {
    LoRa.beginPacket();
    LoRa.print(sosPacket);
    LoRa.endPacket();
    delay(400);
  }

  Serial.println(F("\n🚨 [SOS BROADCAST SENT]"));
  updateOLED("SOS SENT TO ALL", "Lat:" + String(latitude, 4) + " Lon:" + String(longitude, 4));
}

void broadcastTextMessage(String messageText) {
  int msgId = msgIdCounter++;
  String textPacket = "TEXT:" + MY_NODE_ID + ":ALL:" + String(msgId) + ":" + messageText;

  LoRa.beginPacket();
  LoRa.print(textPacket);
  LoRa.endPacket();

  Serial.println(F("TX BROADCAST to ALL"));
  updateOLED("TX BROADCAST", messageText);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(EXTERNAL_SOS_BUTTON, INPUT_PULLUP);

  Wire.begin();
  delay(200);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    display.begin(SSD1306_SWITCHCAPVCC, 0x3D);
  }

  display.clearDisplay();
  display.display();
  delay(200);

  updateOLED("Display Ready...", "Booting Node C");
  delay(1000);

  SPI.begin();
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println(F("LoRa init failed!"));
    updateOLED("LoRa FAIL!", "Check SPI Pins!");
    while (1);
  }

  updateOLED("LoRa Ready!", "Mesh Active");
  delay(1500);

  Serial.println(F("Node C - Arduino Nano Permanent Connection Ready"));
}

void loop() {
  pruneNeighbors();

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

        updateNeighbor(victimId, rssi);
        sosAlertActive = true;
        lastSosNode = victimId;

        Serial.println(F("\n🚨🚨🚨 [SOS EMERGENCY RECEIVED] 🚨🚨🚨"));
        Serial.print(F("Victim: ")); Serial.println(victimId);

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
          Serial.print(F(">>> RX MSG from ")); Serial.print(src);
          Serial.print(F(" [RSSI ")); Serial.print(rssi); Serial.println(F("dBm]"));

          if (!sosAlertActive) {
            updateOLED("RX: " + src + " (" + String(rssi) + "dBm)", txtMsg);
          }
        }
      }
    }
  }

  // Broadcast Periodic Heartbeats ALWAYS
  if (millis() - lastHeartbeat > HEARTBEAT_INTERVAL) {
    sendHeartbeat();
    lastHeartbeat = millis();
  }

  // Broadcast Periodic Text Messages
  if (millis() - lastTextBroadcast > TEXT_BROADCAST_INTERVAL) {
    static int msgCount = 1;
    String sampleMsg = "Nano Patrol #" + String(msgCount++);
    broadcastTextMessage(sampleMsg);
    lastTextBroadcast = millis();
  }
}
