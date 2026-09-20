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

int txCounter = 0;
unsigned long lastSendTime = 0;
const int sendInterval = 5000; // Send every 5 seconds

String lastReceived = "None";
int lastRssi = 0;

void updateOLED(String rxMsg, int rssi) {
  display.clearBuffer();
  display.setFont(u8g2_font_ncenB08_tr);

  display.drawStr(0, 12, "NODE A (Two-Way)");
  
  display.drawStr(0, 30, "Last RX:");
  display.setCursor(0, 44);
  display.print(rxMsg);
  
  if (rssi != 0) {
    display.setCursor(0, 58);
    display.print("RSSI: ");
    display.print(rssi);
  }
  
  display.sendBuffer();
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

  Serial.println("Node A - Two-Way Communication Ready");
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
    String txMsg = "Hello B #" + String(txCounter);
    
    LoRa.beginPacket();
    LoRa.print(txMsg);
    LoRa.endPacket();
    
    Serial.println("TX: " + txMsg);
    txCounter++;
    lastSendTime = millis();
  }
}
