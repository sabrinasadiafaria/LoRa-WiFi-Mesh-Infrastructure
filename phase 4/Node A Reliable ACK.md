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

// Protocol configuration
const int ACK_TIMEOUT = 1500;   // Wait 1.5s for ACK
const int MAX_RETRIES = 3;      // Retry up to 3 times
const int SEND_INTERVAL = 7000; // Trigger new send every 7 seconds

int msgCounter = 1;
unsigned long lastSendTime = 0;

// State tracking for outgoing message
bool waitingForAck = false;
int currentMsgId = 0;
String currentPayload = "";
unsigned long ackTimer = 0;
int retryCount = 0;
String ackStatusStr = "Idle";

// Duplicate detection for incoming messages
int lastProcessedMsgId = -1;

void updateOLED(String statusLine, String rxMsg, int rssi) {
  display.clearBuffer();
  display.setFont(u8g2_font_ncenB08_tr);

  display.drawStr(0, 10, "NODE A (Reliable ACK)");
  
  display.setCursor(0, 24);
  display.print("Status: ");
  display.print(statusLine);

  display.drawStr(0, 38, "Last RX:");
  display.setCursor(0, 50);
  display.print(rxMsg);
  
  if (rssi != 0) {
    display.setCursor(0, 62);
    display.print("RSSI: ");
    display.print(rssi);
  }
  
  display.sendBuffer();
}

void sendPacket(String type, int id, String payload) {
  String packetStr = type + ":" + String(id) + ":" + payload;
  LoRa.beginPacket();
  LoRa.print(packetStr);
  LoRa.endPacket();
  Serial.println("TX -> " + packetStr);
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

  Serial.println("Node A - Phase 4 Reliable Communication (ACK) Ready");
  updateOLED("Ready", "None", 0);
}

void loop() {
  // 1. Receive Packets
  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    String incoming = "";
    while (LoRa.available()) {
      incoming += (char)LoRa.read();
    }
    int rssi = LoRa.packetRssi();

    // Parse packet format TYPE:ID:PAYLOAD
    int firstColon = incoming.indexOf(':');
    int secondColon = incoming.indexOf(':', firstColon + 1);

    if (firstColon != -1) {
      String type = incoming.substring(0, firstColon);
      
      if (type == "MSG" && secondColon != -1) {
        int id = incoming.substring(firstColon + 1, secondColon).toInt();
        String payload = incoming.substring(secondColon + 1);

        Serial.println("RX MSG ID#" + String(id) + ": " + payload + " [RSSI: " + String(rssi) + "]");

        // Send ACK back immediately
        sendPacket("ACK", id, "OK");

        // Process message if not duplicate
        if (id != lastProcessedMsgId) {
          lastProcessedMsgId = id;
          updateOLED(ackStatusStr, payload, rssi);
        } else {
          Serial.println("Duplicate MSG ID#" + String(id) + " ignored.");
        }
      }
      else if (type == "ACK") {
        int ackId = incoming.substring(firstColon + 1, secondColon != -1 ? secondColon : incoming.length()).toInt();
        Serial.println("RX ACK for ID#" + String(ackId));

        if (waitingForAck && ackId == currentMsgId) {
          waitingForAck = false;
          ackStatusStr = "ACK Received!";
          Serial.println(">>> Delivery Confirmed for ID#" + String(currentMsgId));
          updateOLED(ackStatusStr, "ID#" + String(currentMsgId) + " delivered", rssi);
        }
      }
    }
  }

  // 2. Retry Logic on ACK Timeout
  if (waitingForAck && (millis() - ackTimer > ACK_TIMEOUT)) {
    if (retryCount < MAX_RETRIES) {
      retryCount++;
      ackTimer = millis();
      ackStatusStr = "Retry " + String(retryCount) + "/" + String(MAX_RETRIES);
      Serial.println(">>> ACK Timeout! Retrying ID#" + String(currentMsgId) + " (" + String(retryCount) + "/" + String(MAX_RETRIES) + ")");
      sendPacket("MSG", currentMsgId, currentPayload);
      updateOLED(ackStatusStr, currentPayload, 0);
    } else {
      waitingForAck = false;
      ackStatusStr = "ACK FAILED!";
      Serial.println(">>> Delivery Failed for ID#" + String(currentMsgId) + " after max retries.");
      updateOLED(ackStatusStr, "ID#" + String(currentMsgId) + " Lost", 0);
    }
  }

  // 3. Initiate Periodic Send when not waiting for ACK
  if (!waitingForAck && (millis() - lastSendTime > SEND_INTERVAL)) {
    currentMsgId = msgCounter++;
    currentPayload = "DataA #" + String(currentMsgId);
    waitingForAck = true;
    retryCount = 0;
    ackTimer = millis();
    ackStatusStr = "Waiting ACK";

    Serial.println(">>> Initiating TX ID#" + String(currentMsgId));
    sendPacket("MSG", currentMsgId, currentPayload);
    updateOLED(ackStatusStr, currentPayload, 0);

    lastSendTime = millis();
  }
}
