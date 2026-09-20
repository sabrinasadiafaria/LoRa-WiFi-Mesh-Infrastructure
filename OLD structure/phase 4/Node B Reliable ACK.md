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

// Protocol configuration
const int ACK_TIMEOUT_BASE = 2000; // Base wait 2.0s for ACK
const int MAX_RETRIES = 3;         // Retry up to 3 times
const int SEND_INTERVAL_BASE = 12000; // New send every ~12s (staggered from Node A)

int msgCounter = 100;
unsigned long lastSendTime = 0;

// State tracking for outgoing message
bool waitingForAck = false;
int currentMsgId = 0;
String currentPayload = "";
unsigned long ackTimer = 0;
int currentAckTimeout = 2000;
int retryCount = 0;
String ackStatusStr = "Idle";

// Duplicate detection for incoming messages
int lastProcessedMsgId = -1;

void updateOLED(String statusLine, String rxMsg, int rssi) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  display.setCursor(0, 0);
  display.println("NODE B (Reliable ACK)");

  display.setCursor(0, 16);
  display.print("Status: ");
  display.println(statusLine);

  display.setCursor(0, 32);
  display.print("RX: ");
  display.println(rxMsg);

  if (rssi != 0) {
    display.setCursor(0, 48);
    display.print("RSSI: ");
    display.println(rssi);
  }

  display.display();
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
  randomSeed(analogRead(1)); // Seed random generator for backoff jitter

  Wire.begin(8, 9);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    while (1);
  }

  Serial.println("Node B - Phase 4 Reliable Communication (ACK) Ready");
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

        // Small 100ms delay to allow sender radio to settle into RX mode before replying ACK
        delay(100);
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

  // 2. Retry Logic on ACK Timeout with Random Backoff Jitter
  if (waitingForAck && (millis() - ackTimer > currentAckTimeout)) {
    if (retryCount < MAX_RETRIES) {
      retryCount++;
      ackTimer = millis();
      // Add random 200-800ms jitter to prevent collision loops
      currentAckTimeout = ACK_TIMEOUT_BASE + random(200, 800);
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

  // 3. Initiate Periodic Send when not waiting for ACK (Interval with random jitter)
  if (!waitingForAck && (millis() - lastSendTime > (SEND_INTERVAL_BASE + random(0, 3000)))) {
    currentMsgId = msgCounter++;
    currentPayload = "DataB #" + String(currentMsgId);
    waitingForAck = true;
    retryCount = 0;
    ackTimer = millis();
    currentAckTimeout = ACK_TIMEOUT_BASE + random(0, 500);
    ackStatusStr = "Waiting ACK";

    Serial.println(">>> Initiating TX ID#" + String(currentMsgId));
    sendPacket("MSG", currentMsgId, currentPayload);
    updateOLED(ackStatusStr, currentPayload, 0);

    lastSendTime = millis();
  }
}
