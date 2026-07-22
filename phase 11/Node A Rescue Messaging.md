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

// GPS Hardware Serial2 Pins
#define GPS_RX_PIN 16
#define GPS_TX_PIN 17

// External SOS Push Button Pin (GPIO 4 to GND)
#define EXTERNAL_SOS_BUTTON 4

const String MY_NODE_ID = "NODE_A";
const int ROUTE_BROADCAST_INTERVAL = 5000;
const int TEXT_BROADCAST_INTERVAL = 10000;

float latitude = 23.797810;
float longitude = 90.449720;
int batteryLevel = 98;
int lastRssi = 0;
int activeNeighbors = 0;
int msgIdCounter = 1;

unsigned long lastRouteBroadcast = 0;
unsigned long lastTextBroadcast = 0;
bool sosAlertActive = false;
String lastSosNode = "";
String lastSosPayload = "";
String lastMessage = "Scanning Mesh...";

void updateOLED(String line1, String line2, String line3) {
  display.clearBuffer();
  display.setFont(u8g2_font_ncenB08_tr);

  if (sosAlertActive) {
    display.drawStr(0, 10, "!! 🚨 SOS EMERGENCY 🚨 !!");
    display.setCursor(0, 26);
    display.print("VICTIM: ");
    display.print(lastSosNode);
    display.setCursor(0, 42);
    display.print(line1);
    display.setCursor(0, 58);
    display.print(line2);
  } else {
    display.drawStr(0, 10, "--- NODE A (MESH) ---");
    display.setCursor(0, 26);
    display.print(line1);
    display.setCursor(0, 42);
    display.print(line2);
    display.setCursor(0, 58);
    display.print(line3);
  }
  
  display.sendBuffer();
}

void sendSosAlert() {
  sosAlertActive = true;
  lastSosNode = MY_NODE_ID;
  
  // Format: SOS:SENDER_ID:LATITUDE:LONGITUDE:PAYLOAD
  String sosPacket = "SOS:" + MY_NODE_ID + ":" + String(latitude, 6) + ":" + String(longitude, 6) + ":MAYDAY INJURED RESCUER";

  for (int i = 0; i < 3; i++) {
    LoRa.beginPacket();
    LoRa.print(sosPacket);
    LoRa.endPacket();
    delay(100);
  }

  Serial.println("\n🚨🚨🚨 [SOS BROADCAST SENT TO ALL NODES] -> " + sosPacket + "\n");
  updateOLED("SOS SENT TO ALL", "Lat: " + String(latitude, 4), "Lon: " + String(longitude, 4));
}

void broadcastTextMessage(String messageText) {
  int msgId = msgIdCounter++;
  // Format: TEXT:SRC:DEST:MSG_ID:TEXT_BODY (DEST = ALL for universal broadcast!)
  String textPacket = "TEXT:" + MY_NODE_ID + ":ALL:" + String(msgId) + ":" + messageText;

  LoRa.beginPacket();
  LoRa.print(textPacket);
  LoRa.endPacket();

  lastMessage = "TX ALL: " + messageText;
  Serial.println("TX BROADCAST to ALL NODES -> " + textPacket);
  updateOLED("TX -> ALL NODES", messageText, "Lat:" + String(latitude,4) + " Lon:" + String(longitude,4));
}

void broadcastRouteTable() {
  String packetStr = "RT:" + MY_NODE_ID + ":NODE_B,1;";
  LoRa.beginPacket();
  LoRa.print(packetStr);
  LoRa.endPacket();
}

void setup() {
  Serial.begin(115200);

  // Configure External SOS Push Button
  pinMode(EXTERNAL_SOS_BUTTON, INPUT_PULLUP);

  // STEP 1: Initialize OLED Display
  Wire.begin(21, 22);
  display.begin();
  
  updateOLED("Display Ready...", "Booting Node A", "Step 1/3 Complete");
  delay(1000);

  // STEP 2: Initialize GPS Serial
  Serial2.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
  updateOLED("GPS Module Ready...", "Serial2 Active", "Step 2/3 Complete");
  delay(1000);

  // STEP 3: Initialize LoRa Radio with explicit SPI delay
  updateOLED("Init LoRa Radio...", "Frequency 433MHz", "Step 3/3");
  delay(500);

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    updateOLED("LoRa FAIL!", "Check SPI Pins!", "System Halted");
    while (1);
  }

  updateOLED("LoRa Ready!", "All Systems GO", "Mesh Network ACTIVE");
  delay(1500);

  Serial.println("Node A - Universal Broadcast & Rescue System Ready");
  Serial.println(">>> PRESS EXTERNAL SOS BUTTON (GPIO 4) TO BROADCAST EMERGENCY TO ALL NODES!");
}

void loop() {
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
    lastRssi = LoRa.packetRssi();

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

        sosAlertActive = true;
        lastSosNode = victimId;

        Serial.println("\n🚨🚨🚨 [SOS RECEIVED FROM " + victimId + "] 🚨🚨🚨");
        Serial.println("Location: " + victimLat + ", " + victimLon);
        Serial.println("RSSI Signal: " + String(lastRssi) + " dBm\n");

        updateOLED("SOS ALERT!", "Lat:" + victimLat + " Lon:" + victimLon, "Signal: " + String(lastRssi) + "dBm");
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
          activeNeighbors++;
          lastMessage = src + ": " + txtMsg;
          Serial.println(">>> RX MSG from " + src + " [RSSI " + String(lastRssi) + "dBm]: " + txtMsg);
          updateOLED("RX: " + src + " (" + String(lastRssi) + "dBm)", txtMsg, "Lat:" + String(latitude,4) + " Lon:" + String(longitude,4));
        }
      }
    }
  }

  // 3. Broadcast Periodic Text Messages to ALL connected nodes
  if (millis() - lastTextBroadcast > TEXT_BROADCAST_INTERVAL && !sosAlertActive) {
    static int msgCount = 1;
    String sampleMsg = "Rescue Team Active #" + String(msgCount++);
    broadcastTextMessage(sampleMsg);
    lastTextBroadcast = millis();
  }

  // 4. Broadcast Routing Table
  if (millis() - lastRouteBroadcast > ROUTE_BROADCAST_INTERVAL) {
    broadcastRouteTable();
    lastRouteBroadcast = millis();
  }
}
