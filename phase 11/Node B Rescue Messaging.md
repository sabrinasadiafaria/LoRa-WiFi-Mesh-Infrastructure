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
const int ROUTE_BROADCAST_INTERVAL = 5000;
const int TEXT_BROADCAST_INTERVAL = 10000;

float latitude = 23.797950;
float longitude = 90.449850;
int batteryLevel = 92;
int lastRssi = 0;
int msgIdCounter = 100;

unsigned long lastRouteBroadcast = 2500;
unsigned long lastTextBroadcast = 5000;
bool sosAlertActive = false;
String lastSosNode = "";
String lastMessage = "Scanning Mesh...";

void updateOLED(String line1, String line2, String line3) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

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
    display.println("--- NODE B (MESH) ---");
    display.setCursor(0, 18);
    display.println(line1);
    display.setCursor(0, 34);
    display.println(line2);
    display.setCursor(0, 48);
    display.println(line3);
  }

  display.display();
}

void sendSosAlert() {
  sosAlertActive = true;
  lastSosNode = MY_NODE_ID;
  
  // Format: SOS:SENDER_ID:LATITUDE:LONGITUDE:PAYLOAD
  String sosPacket = "SOS:" + MY_NODE_ID + ":" + String(latitude, 6) + ":" + String(longitude, 6) + ":MAYDAY MEDICAL ASSISTANCE";

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

void setup() {
  Serial.begin(115200);

  // Configure External SOS Push Button
  pinMode(EXTERNAL_SOS_BUTTON, INPUT_PULLUP);

  // STEP 1: Initialize Display
  Wire.begin(8, 9);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);

  updateOLED("Display Ready...", "Booting Node B", "Step 1/2 Complete");
  delay(1000);

  // STEP 2: Initialize LoRa Radio with explicit SPI delay
  updateOLED("Init LoRa Radio...", "Frequency 433MHz", "Step 2/2");
  delay(800);

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    updateOLED("LoRa FAIL!", "Check SPI Pins!", "System Halted");
    while (1);
  }

  updateOLED("LoRa Ready!", "All Systems GO", "Mesh Network ACTIVE");
  delay(1500);

  Serial.println("Node B - Universal Broadcast & Rescue System Ready");
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
          lastMessage = src + ": " + txtMsg;
          Serial.println(">>> RX MSG from " + src + " [RSSI " + String(lastRssi) + "dBm]: " + txtMsg);
          updateOLED("RX: " + src + " (" + String(lastRssi) + "dBm)", txtMsg, "Lat:" + String(latitude,4) + " Lon:" + String(longitude,4));
        }
      }
    }
  }

  // 3. Periodically transmit broadcast text messages to ALL connected nodes
  if (millis() - lastTextBroadcast > TEXT_BROADCAST_INTERVAL && !sosAlertActive) {
    static int msgCount = 1;
    String sampleMsg = "Node B Patrol #" + String(msgCount++);
    broadcastTextMessage(sampleMsg);
    lastTextBroadcast = millis();
  }
}
