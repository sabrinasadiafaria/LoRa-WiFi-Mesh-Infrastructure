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

// External SOS Push Button Pin on Node B
#define EXTERNAL_SOS_BUTTON 4 // GPIO 4 -> Connect to one side of button, other side to GND

const String MY_NODE_ID = "NODE_B";

float latitude = 23.797950;
float longitude = 90.449850;
int msgIdCounter = 100;
unsigned long lastTextSend = 0;
bool sosAlertActive = false;
String lastSosNode = "";

void updateOLED(String header, String line1, String line2) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  if (sosAlertActive) {
    display.setCursor(0, 0);
    display.println("!! SOS EMERGENCY !!");
    display.setCursor(0, 18);
    display.print("VICTIM: ");
    display.println(lastSosNode);
    display.setCursor(0, 34);
    display.println(line1);
    display.setCursor(0, 48);
    display.println(line2);
  } else {
    display.setCursor(0, 0);
    display.println("--- NODE B RESCUE ---");
    display.setCursor(0, 18);
    display.println(header);
    display.setCursor(0, 34);
    display.println(line1);
    display.setCursor(0, 48);
    display.println(line2);
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

  Serial.println("\n🚨 [SOS BROADCAST SENT] -> " + sosPacket + "\n");
  updateOLED("SOS BROADCAST SENT", "Lat: " + String(latitude, 4), "Lon: " + String(longitude, 4));
}

void sendTextMessage(String dest, String messageText) {
  int msgId = msgIdCounter++;
  String textPacket = "TEXT:" + MY_NODE_ID + ":" + dest + ":" + String(msgId) + ":" + messageText;

  LoRa.beginPacket();
  LoRa.print(textPacket);
  LoRa.endPacket();

  Serial.println("TX TEXT to " + dest + " -> " + messageText);
  updateOLED("TX TEXT -> " + dest, "ID#" + String(msgId), messageText);
}

void setup() {
  Serial.begin(115200);

  // Configure External SOS Push Button with Internal Pull-up (Active LOW)
  pinMode(EXTERNAL_SOS_BUTTON, INPUT_PULLUP);

  Wire.begin(8, 9);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);

  updateOLED("Status: Booting", "Rescue System ON", "Press Button for SOS");
  delay(1000);

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    while (1);
  }

  Serial.println("Node B - Phase 11 Rescue Messaging System Ready");
  updateOLED("Status: READY", "Press SOS Button", "Mesh Active");
}

void loop() {
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

        Serial.println("\n🚨🚨🚨 [SOS EMERGENCY RECEIVED] 🚨🚨🚨");
        Serial.println("Victim Node: " + victimId);
        Serial.println("Location: " + victimLat + ", " + victimLon);
        Serial.println("Alert: " + sosMsg + " (RSSI: " + String(rssi) + "dBm)\n");

        updateOLED("SOS ALERT!", "Lat: " + victimLat, "Lon: " + victimLon);
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

        if (dest == MY_NODE_ID || dest == "BROADCAST") {
          Serial.println(">>> RX TEXT from " + src + " (ID #" + String(msgId) + "): " + txtMsg);
          updateOLED("RX TEXT from " + src, "ID#" + String(msgId), txtMsg);
        }
      }
    }
  }
}
