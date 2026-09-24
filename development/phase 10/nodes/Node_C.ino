/*
 * Node C Firmware — Phase 10 Production Release
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
#define NODE_ID         "C"
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

// Captive Portal
WebServer server(80);
DNSServer dns;
IPAddress apIP(192, 168, 4, 1);
const char* AP_SSID = "SOS_Node_C";

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
String peersJson = "[]"; // simple peer tracking for portal

const char PORTAL_HTML[] PROGMEM =
  "<!DOCTYPE html><html lang=\"en\"><head>"
  "<meta charset=\"utf-8\">"
  "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">"
  "<title>SAR Rescue Portal</title><style>"
  "*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}"
  "body{margin:0;padding:0 0 28px;font:15px/1.45 system-ui,-apple-system,sans-serif;"
  "background:#0b0d10;color:#e8edf3}"
  ".wrap{max-width:640px;margin:0 auto;padding:0 14px}"
  "header{position:sticky;top:0;z-index:20;background:rgba(11,13,16,.94);"
  "border-bottom:1px solid #252d38;padding:12px 0 10px}"
  ".card{background:#151a21;border:1px solid #252d38;border-radius:14px;padding:14px;margin-top:12px}"
  "button{font:inherit;border:0;border-radius:11px;padding:13px;font-weight:650;"
  "cursor:pointer;width:100%}"
  ".sos{background:linear-gradient(135deg,#ff3b3b,#c81e1e);color:#fff;font-size:18px}"
  ".sec{background:#1b222b;color:#e8edf3;border:1px solid #252d38;margin-top:8px}"
  ".big{font-size:21px;font-family:monospace;font-weight:600}"
  "</style></head><body>"
  "<div class=\"wrap\">"
  "<header><h1>Rescue Portal</h1><div id=\"sub\">Node " NODE_ID "</div></header>"
  "<div class=\"card\" style=\"text-align:center\">"
  "<button class=\"sos\" onclick=\"fetch('/api/sos')\">SEND SOS</button>"
  "</div>"
  "<div class=\"card\">"
  "<div>This node's position</div>"
  "<div class=\"big\" id=\"pos\">--</div>"
  "</div>"
  "<div class=\"card\">"
  "<div>Team status <span id=\"mystat\">--</span></div>"
  "  <button class=\"sec\" onclick=\"fetch('/api/teamstatus?state=AVAILABLE')\">Available</button>"
  "  <button class=\"sec\" onclick=\"fetch('/api/teamstatus?state=SEARCHING')\">Searching</button>"
  "  <button class=\"sec\" onclick=\"fetch('/api/teamstatus?state=NEED_ASSIST')\">Need Assist</button>"
  "  <button class=\"sec\" onclick=\"fetch('/api/teamstatus?state=EMERGENCY')\">Emergency</button>"
  "</div>"
  "</div>"
  "<script>"
  "function tick(){"
  " fetch('/api/status').then(r=>r.json()).then(d=>{"
  "   document.getElementById('pos').textContent = (d.gpsfix ? d.lat.toFixed(6)+', '+d.lon.toFixed(6) : 'no fix');"
  "   document.getElementById('mystat').textContent = d.mystatus;"
  " });"
  "}"
  "setInterval(tick,2000); tick();"
  "</script></body></html>";

void handlePortal() { server.send_P(200, "text/html", PORTAL_HTML); }
void handleStatus() {
  char json[300];
  snprintf(json, sizeof(json), 
           "{\"id\":\"%s\",\"gpsfix\":%d,\"lat\":%.6f,\"lon\":%.6f,\"mystatus\":\"%s\"}",
           NODE_ID, gps.location.isValid() ? 1 : 0, gps.location.lat(), gps.location.lng(), currentStatus.c_str());
  server.send(200, "application/json", json);
}
void handleSos() {
  isSosActive = !isSosActive;
  if(isSosActive) {
    sendLoRaFrame(buildPacket("SOS", "*", "MAYDAY EMERGENCY"));
    playSosTonePattern();
  } else {
    sendLoRaFrame(buildPacket("CMD", "*", "SOSCLR"));
  }
  server.send(200, "text/plain", "SOS toggled");
}
void handleTeamStatus() {
  if (server.hasArg("state")) {
    currentStatus = server.arg("state");
    sendLoRaFrame(buildPacket("STAT", "PI", currentStatus));
    updateOled();
  }
  server.send(200, "text/plain", "Status updated");
}

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
  display.print("NODE C | ");
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
    display.print("Fix: NO FIX");
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
  display.println("SAR Node C Booting...");
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

  // Captive Portal setup
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(apIP, apIP, IPAddress(255, 255, 255, 0));
  WiFi.softAP(AP_SSID);
  dns.start(53, "*", apIP);
  
  server.on("/", handlePortal);
  server.on("/api/status", handleStatus);
  server.on("/api/sos", handleSos);
  server.on("/api/teamstatus", handleTeamStatus);
  server.onNotFound(handlePortal); // redirect all
  server.begin();

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
  dns.processNextRequest();
  server.handleClient();

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
