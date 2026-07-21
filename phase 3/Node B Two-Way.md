# Node B - Phase 3 (Two-Way Communication)

This code enables **Node B** to both send and receive LoRa packets non-blockingly. It will send a message every 5 seconds and continuously listen for incoming messages from Node A.

```cpp
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

int txCounter = 0;
unsigned long lastSendTime = 0;
const int sendInterval = 6000; // Send every 6 seconds (offset from Node A to reduce collision)

String lastReceived = "";
int lastRssi = 0;

void setup() {
  Serial.begin(115200);

  Wire.begin(8, 9);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    while (1);
  }

  Serial.println("Node B - Two-Way Communication Ready");
  updateOLED("Started", 0);
}

void loop() {
  // 1. Check for incoming packets
  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    String msg = "";
    while (LoRa.available()) {
      msg += (char)LoRa.read();
    }
    lastRssi = LoRa.packetRssi();
    lastReceived = msg;

    Serial.print("RX: ");
    Serial.print(msg);
    Serial.print(" RSSI: ");
    Serial.println(lastRssi);

    updateOLED(msg, lastRssi);
  }

  // 2. Send packet periodically
  if (millis() - lastSendTime > sendInterval) {
    String txMsg = "Hello A #" + String(txCounter);
    
    LoRa.beginPacket();
    LoRa.print(txMsg);
    LoRa.endPacket();
    
    Serial.println("TX: " + txMsg);
    txCounter++;
    lastSendTime = millis();
  }
}

void updateOLED(String rxMsg, int rssi) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  display.setCursor(0, 0);
  display.println("NODE B (Two-Way)");

  display.setCursor(0, 18);
  display.print("RX:");
  display.setCursor(25, 18);
  display.println(rxMsg);

  if (rssi != 0) {
    display.setCursor(0, 40);
    display.print("RSSI:");
    display.setCursor(35, 40);
    display.println(rssi);
  }

  display.display();
}
```
