/*
 * Node A Firmware — Phase 10 Production Release
 * Role: Field Leader / Mesh Gateway Node
 * 
 * Hardware Specs:
 *   - Microcontroller: ESP32 (Standard)
 *   - Radio: SX1278 (433MHz SPI LoRa)
 *   - Display: SH1106 / SSD1306 OLED (128x64 I2C)
 *   - GPS: NEO-6M (Hardware Serial2 on GPIO 16/17)
 *   - Buzzer: Piezo Audio Transducer on GPIO 25
 *   - Button 1: SOS Emergency Button on GPIO 4 (Active LOW)
 *   - Button 2: Status / Rescue Report Button on GPIO 13 (Active LOW)
 * 
 * Pinout Reference:
 *   LoRa SPI  : SCK=18, MISO=19, MOSI=23, NSS=5, RST=14, DIO0=26
 *   OLED I2C  : SDA=21, SCL=22
 *   GPS Serial: RX2=16 (to GPS TX), TX2=17 (to GPS RX)
 *   Buzzer    : GPIO 25 (Active Tone Output)
 *   Button 1  : GPIO 4 (SOS / Screen Toggle)
 *   Button 2  : GPIO 13 (Team Status Cycle / Quick Report)
 */

#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <TinyGPS++.h>
#include <WiFi.h>
#include <DNSServer.h>
#include <WebServer.h>

// Node Config
#define NODE_ID         "A"
#define LORA_FREQ       433E6
#define LORA_SF         7
#define LORA_BW         125E3
#define LORA_CR         5
#define LORA_SYNC       0x2A

// Hardware Pins
#define PIN_LORA_SS     5
#define PIN_LORA_RST    14
#define PIN_LORA_DIO0   26

#define PIN_BUZZER      25
#define PIN_BTN_SOS     4
#define PIN_BTN_STAT    13

#define OLED_WIDTH      128
#define OLED_HEIGHT     64
#define OLED_RESET      -1

Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, OLED_RESET);
TinyGPSPlus gps;
HardwareSerial gpsSerial(2);

// State Variables
bool isSosActive = false;
String currentStatus = "AVAILABLE"; // AVAILABLE, SEARCHING, VICTIM_FOUND, NEED_ASSIST
unsigned long lastHbTime = 0;
unsigned long lastGpsTime = 0;
unsigned long sosBtnPressStart = 0;
unsigned long statBtnPressStart = 0;
bool sosBtnPrevState = HIGH;
bool statBtnPrevState = HIGH;
int msgCount = 0;
String lastRxMsg = "";
String lastRxSrc = "";

// Non-blocking Tone Helper
void playBuzzerTone(int freq, int durationMs) {
  tone(PIN_BUZZER, freq, durationMs);
}

void playSosTonePattern() {
  for (int i = 0; i < 3; i++) { tone(PIN_BUZZER, 2500, 100); delay(150); }
  delay(200);
  for (int i = 0; i < 3; i++) { tone(PIN_BUZZER, 2500, 300); delay(350); }
  delay(200);
  for (int i = 0; i < 3; i++) { tone(PIN_BUZZER, 2500, 100); delay(150); }
}

void playMsgRxChirp() {
  tone(PIN_BUZZER, 1200, 80);
  delay(100);
  tone(PIN_BUZZER, 1800, 100);
}

void playGpsLockChirp() {
  tone(PIN_BUZZER, 1000, 60);
  delay(80);
  tone(PIN_BUZZER, 1500, 60);
  delay(80);
  tone(PIN_BUZZER, 2000, 100);
}

// Checksum Generator
uint8_t calculateChecksum(String body) {
  uint8_t c = 0;
  for (int i = 0; i < body.length(); i++) {
    c ^= body[i];
  }
  return c;
}

// Build LoRa Wire Frame: v1|<TYPE>|<SRC>|<DEST>|<MSGID>|<TTL>|<PAYLOAD>|<CHK>
String buildPacket(String type, String dest, String payload) {
  static int msgSeq = 0;
  msgSeq++;
  String body = "v1|" + type + "|" + NODE_ID + "|" + dest + "|" + String(msgSeq) + "|4|" + payload;
  char chkHex[4];
  sprintf(chkHex, "%02x", calculateChecksum(body));
  return body + "|" + String(chkHex);
}

void sendLoRaFrame(String frame) {
  LoRa.beginPacket();
  LoRa.print(frame);
  LoRa.endPacket();
}

void updateOled() {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  // Top Bar
  display.print("NODE A | ");
  display.print(currentStatus);
  display.setCursor(100, 0);
  display.print(isSosActive ? "!SOS!" : "OK");

  display.drawLine(0, 10, 128, 10, SSD1306_WHITE);

  // GPS Info
  display.setCursor(0, 14);
  if (gps.location.isValid()) {
    display.print("Lat: "); display.println(gps.location.lat(), 4);
    display.print("Lon: "); display.println(gps.location.lng(), 4);
    display.print("Sats: "); display.println(gps.satellites.value());
  } else {
    display.println("GPS: Searching...");
    display.print("Fix: NO FIX (Bench)");
  }

  // Last Message
  display.drawLine(0, 44, 128, 44, SSD1306_WHITE);
  display.setCursor(0, 48);
  if (lastRxMsg.length() > 0) {
    display.print(lastRxSrc); display.print(": "); display.println(lastRxMsg.substring(0, 14));
  } else {
    display.println("Mesh Active - Ready");
  }

  display.display();
}

void setup() {
  Serial.begin(115200);
  gpsSerial.begin(9600, SERIAL_8N1, 16, 17);

  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_BTN_SOS, INPUT_PULLUP);
  pinMode(PIN_BTN_STAT, INPUT_PULLUP);

  playBuzzerTone(1500, 100);

  // OLED Init
  Wire.begin(21, 22);
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED init failed!");
  }
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 20);
  display.println("SAR Node A Booting...");
  display.display();

  // LoRa Init
  LoRa.setPins(PIN_LORA_SS, PIN_LORA_RST, PIN_LORA_DIO0);
  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa init failed!");
    display.println("LoRa Fail!"); display.display();
    while (1);
  }
  LoRa.setSpreadingFactor(LORA_SF);
  LoRa.setSignalBandwidth(LORA_BW);
  LoRa.setCodingRate4(LORA_CR);
  LoRa.setSyncWord(LORA_SYNC);
  LoRa.enableCrc();

  playGpsLockChirp();
  updateOled();
}

void handleButtons() {
  unsigned long now = millis();

  // Button 1: SOS (GPIO 4)
  bool sosCurr = digitalRead(PIN_BTN_SOS);
  if (sosCurr == LOW && sosBtnPrevState == HIGH) {
    sosBtnPressStart = now;
    playBuzzerTone(2000, 30);
  } else if (sosCurr == HIGH && sosBtnPrevState == LOW) {
    unsigned long duration = now - sosBtnPressStart;
    if (duration >= 3000) {
      // Toggle SOS
      isSosActive = !isSosActive;
      if (isSosActive) {
        playSosTonePattern();
        sendLoRaFrame(buildPacket("SOS", "*", "MAYDAY EMERGENCY"));
      } else {
        sendLoRaFrame(buildPacket("CMD", "*", "SOSCLR"));
        playBuzzerTone(1000, 200);
      }
    } else {
      // Short press: Wake OLED
      updateOled();
    }
  }
  sosBtnPrevState = sosCurr;

  // Button 2: Status Cycle (GPIO 13)
  bool statCurr = digitalRead(PIN_BTN_STAT);
  if (statCurr == LOW && statBtnPrevState == HIGH) {
    statBtnPressStart = now;
    playBuzzerTone(2200, 30);
  } else if (statCurr == HIGH && statBtnPrevState == LOW) {
    unsigned long duration = now - statBtnPressStart;
    if (duration >= 2000) {
      // Long press: Quick Rescue Report
      String rptPayload = "VICTIM_FOUND," + String(gps.location.lat(), 5) + "," + String(gps.location.lng(), 5);
      sendLoRaFrame(buildPacket("RPT", "PI", rptPayload));
      playBuzzerTone(2500, 200);
    } else {
      // Single tap: Cycle status
      if (currentStatus == "AVAILABLE") currentStatus = "SEARCHING";
      else if (currentStatus == "SEARCHING") currentStatus = "VICTIM_FOUND";
      else if (currentStatus == "VICTIM_FOUND") currentStatus = "NEED_ASSIST";
      else currentStatus = "AVAILABLE";

      sendLoRaFrame(buildPacket("STAT", "PI", currentStatus));
      updateOled();
    }
  }
  statBtnPrevState = statCurr;
}

void parseIncomingLoRa() {
  int packetSize = LoRa.parsePacket();
  if (!packetSize) return;

  String incoming = "";
  while (LoRa.available()) {
    incoming += (char)LoRa.read();
  }

  // Parse simple packet fields
  if (incoming.startsWith("v1|")) {
    int firstPipe = incoming.indexOf('|');
    int secondPipe = incoming.indexOf('|', firstPipe + 1);
    int thirdPipe = incoming.indexOf('|', secondPipe + 1);
    int fourthPipe = incoming.indexOf('|', thirdPipe + 1);
    int fifthPipe = incoming.indexOf('|', fourthPipe + 1);
    int sixthPipe = incoming.indexOf('|', fifthPipe + 1);
    int seventhPipe = incoming.indexOf('|', sixthPipe + 1);

    String ptype = incoming.substring(firstPipe + 1, secondPipe);
    String src = incoming.substring(secondPipe + 1, thirdPipe);
    String dest = incoming.substring(thirdPipe + 1, fourthPipe);

    if (dest == NODE_ID || dest == "*") {
      playMsgRxChirp();
      lastRxSrc = src;
      if (ptype == "DATA") {
        lastRxMsg = incoming.substring(sixthPipe + 1, seventhPipe);
      } else {
        lastRxMsg = ptype;
      }
      updateOled();
    }
  }
}

void loop() {
  while (gpsSerial.available()) {
    gps.encode(gpsSerial.read());
  }

  handleButtons();
  parseIncomingLoRa();

  unsigned long now = millis();

  // Heartbeat every 25 seconds
  if (now - lastHbTime >= 25000) {
    lastHbTime = now;
    String hbPayload = String(millis() / 1000) + "," + String(ESP.getFreeHeap());
    sendLoRaFrame(buildPacket("HB", "PI", hbPayload));
  }

  // GPS broadcast every 30 seconds
  if (now - lastGpsTime >= 30000) {
    lastGpsTime = now;
    if (gps.location.isValid()) {
      String posPayload = String(gps.location.lat(), 6) + "," + String(gps.location.lng(), 6) + ",1," + String(gps.satellites.value());
      sendLoRaFrame(buildPacket("GPS", "PI", posPayload));
    }
  }
}
