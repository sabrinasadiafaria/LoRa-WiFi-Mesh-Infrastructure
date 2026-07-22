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

// GPS Pins
#define GPS_RX_PIN 16
#define GPS_TX_PIN 17

// External SOS Push Button Pin (GPIO 4 to GND)
#define EXTERNAL_SOS_BUTTON 4

const String MY_NODE_ID = "NODE_A";
const int TEXT_BROADCAST_INTERVAL = 10000;
const int NEIGHBOR_TIMEOUT = 20000; // 20s timeout

// Active Connected Neighbor Tracking
struct NeighborNode {
  String id;
  int rssi;
  unsigned long lastSeen;
  bool active;
};

NeighborNode neighbors[5];
int neighborCount = 0;

float latitude = 23.797810;
float longitude = 90.449720;
int batteryLevel = 98;
int msgIdCounter = 1;

unsigned long lastTextBroadcast = 0;
bool sosAlertActive = false;
String lastSosNode = "";
String lastSosPayload = "";
String lastMessage = "Scanning Mesh...";

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
      connStr += neighbors[i].id.substring(5); // e.g. "B", "C"
    }
  }
  if (connStr.length() == 0) return "None";
  return connStr;
}

void updateOLED(String line1, String line2) {
  display.clearBuffer();
  display.setFont(u8g2_font_ncenB08_tr);

  if (sosAlertActive) {
    display.drawStr(0, 10, "!! 🚨 SOS EMERGENCY 🚨 !!");
    display.setCursor(0, 26);
    display.print("VICTIM: " + lastSosNode);
    display.setCursor(0, 42);
    display.print(line1);
    display.setCursor(0, 58);
    display.print(line2);
  } else {
    // Header showing active connected nodes (e.g. "NODE A | CON: B,C")
    String headerStr = "NODE A | CON: " + getConnectedNodesStr();
    display.setCursor(0, 10);
    display.print(headerStr);

    display.setCursor(0, 28);
    display.print(line1);
    display.setCursor(0, 44);
    display.print(line2);
    display.setCursor(0, 60);
    display.print("Lat:" + String(latitude, 4) + " Lon:" + String(longitude, 4));
  }
  
  display.sendBuffer();
}

void sendSosAlert() {
  sosAlertActive = true;
  lastSosNode = MY_NODE_ID;
  lastSosPayload = "MAYDAY INJURED RESCUER";
  
  // Format: SOS:SENDER_ID:LATITUDE:LONGITUDE:PAYLOAD
  String sosPacket = "SOS:" + MY_NODE_ID + ":" + String(latitude, 6) + ":" + String(longitude, 6) + ":" + lastSosPayload;

  // Transmit cleanly 3 times with 500ms spacing to prevent buffer overrun on receivers
  for (int i = 0; i < 3; i++) {
    LoRa.beginPacket();
    LoRa.print(sosPacket);
    LoRa.endPacket();
    delay(500);
  }

  Serial.println("\n🚨🚨🚨 [SOS BROADCAST SENT TO ALL NODES] -> " + sosPacket + "\n");
  updateOLED("SOS SENT TO ALL", "Lat:" + String(latitude, 4) + " Lon:" + String(longitude, 4));
}

void broadcastTextMessage(String messageText) {
  int msgId = msgIdCounter++;
  // Format: TEXT:SRC:DEST:MSG_ID:TEXT_BODY (DEST = ALL for universal broadcast!)
  String textPacket = "TEXT:" + MY_NODE_ID + ":ALL:" + String(msgId) + ":" + messageText;

  LoRa.beginPacket();
  LoRa.print(textPacket);
  LoRa.endPacket();

  lastMessage = "TX: " + messageText;
  Serial.println("TX BROADCAST -> " + textPacket);
  updateOLED("TX BROADCAST", messageText);
}

void setup() {
  Serial.begin(115200);
  pinMode(EXTERNAL_SOS_BUTTON, INPUT_PULLUP);

  // STEP 1: Initialize Display
  Wire.begin(21, 22);
  display.begin();
  
  updateOLED("Display Ready...", "Booting Node A");
  delay(1000);

  // STEP 2: Initialize GPS Serial
  Serial2.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
  updateOLED("GPS Serial Ready...", "Step 2/3 Complete");
  delay(1000);

  // STEP 3: Initialize LoRa Radio
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

  Serial.println("Node A - Phase 11 Connected Mesh & SOS Ready");
  Serial.println(">>> PRESS EXTERNAL SOS BUTTON (GPIO 4) TO BROADCAST SOS TO ALL!");
}

void loop() {
  // Prune disconnected neighbors
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

    if (incoming.startsWith("SOS:")) {
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
          lastMessage = src + ": " + txtMsg;

          Serial.println(">>> RX MSG from " + src + " [RSSI " + String(rssi) + "dBm]: " + txtMsg);
          updateOLED("RX: " + src + " (" + String(rssi) + "dBm)", txtMsg);
        }
      }
    }
  }

  // 3. Broadcast Periodic Text Messages to ALL connected nodes
  if (millis() - lastTextBroadcast > TEXT_BROADCAST_INTERVAL && !sosAlertActive) {
    static int msgCount = 1;
    String sampleMsg = "Rescue Active #" + String(msgCount++);
    broadcastTextMessage(sampleMsg);
    lastTextBroadcast = millis();
  }
}
