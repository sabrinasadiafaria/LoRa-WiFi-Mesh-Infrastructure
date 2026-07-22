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

const String MY_NODE_ID = "NODE_A";
const int SOS_BUTTON_PIN = 0; // ESP32 BOOT button (GPIO 0) as SOS trigger!

float latitude = 23.797810;
float longitude = 90.449720;
int msgIdCounter = 1;
unsigned long lastTextSend = 0;
bool sosAlertActive = false;
String lastSosNode = "";

void updateOLED(String header, String line1, String line2) {
  display.clearBuffer();
  display.setFont(u8g2_font_ncenB08_tr);

  if (sosAlertActive) {
    display.drawStr(0, 10, "!! SOS EMERGENCY !!");
    display.setCursor(0, 26);
    display.print("VICTIM: " + lastSosNode);
    display.setCursor(0, 42);
    display.print(line1);
    display.setCursor(0, 58);
    display.print(line2);
  } else {
    display.drawStr(0, 10, "--- NODE A RESCUE ---");
    display.setCursor(0, 26);
    display.print(header);
    display.setCursor(0, 42);
    display.print(line1);
    display.setCursor(0, 58);
    display.print(line2);
  }
  
  display.sendBuffer();
}

void sendSosAlert() {
  sosAlertActive = true;
  lastSosNode = MY_NODE_ID;
  
  // Format: SOS:SENDER_ID:LATITUDE:LONGITUDE:PAYLOAD
  String sosPacket = "SOS:" + MY_NODE_ID + ":" + String(latitude, 6) + ":" + String(longitude, 6) + ":MAYDAY INJURED RESCUER";

  // Transmit 3 times for guaranteed delivery
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
  // Format: TEXT:SRC:DEST:MSG_ID:TEXT_BODY
  String textPacket = "TEXT:" + MY_NODE_ID + ":" + dest + ":" + String(msgId) + ":" + messageText;

  LoRa.beginPacket();
  LoRa.print(textPacket);
  LoRa.endPacket();

  Serial.println("TX TEXT to " + dest + " -> " + messageText);
  updateOLED("TX TEXT -> " + dest, "ID#" + String(msgId), messageText);
}

void setup() {
  Serial.begin(115200);
  pinMode(SOS_BUTTON_PIN, INPUT_PULLUP);

  // Initialize Display
  Wire.begin(21, 22);
  display.begin();

  updateOLED("Status: Booting", "Rescue System ON", "Press BOOT for SOS");
  delay(1000);

  // Initialize LoRa
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    while (1);
  }

  Serial.println("Node A - Phase 11 Rescue Messaging & SOS System Ready");
  Serial.println(">>> PRESS ESP32 BOOT BUTTON (GPIO 0) TO TRIGGER EMERGENCY SOS!");
  updateOLED("Status: READY", "Press BOOT for SOS", "Mesh Active");
}

void loop() {
  // 1. Check hardware SOS trigger button (Active LOW)
  if (digitalRead(SOS_BUTTON_PIN) == LOW) {
    delay(50); // Debounce
    if (digitalRead(SOS_BUTTON_PIN) == LOW) {
      sendSosAlert();
      delay(2000); // Hold delay
    }
  }

  // 2. Receive incoming Rescue & SOS Messages
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

  // 3. Periodically transmit test rescue messages
  if (millis() - lastTextSend > 12000 && !sosAlertActive) {
    sendTextMessage("NODE_C", "Survivor Found Sector 4");
    lastTextSend = millis();
  }
}
