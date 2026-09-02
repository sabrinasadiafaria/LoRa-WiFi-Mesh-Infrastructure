// ===========================================================================
//  PHASE 1  -  SHARED CORE  -  NODE B
//  ESP32 + LoRa SX1278 (433 MHz) + 0.96" SSD1306 OLED
//
//  Complete standalone sketch - paste the whole file into the Arduino IDE.
//
//  Libraries: LoRa (Sandeep Mistry), Adafruit GFX, Adafruit SSD1306
//  Board:     ESP32 Dev Module
//
//  In the final system Node B is the middle relay of the A - B - C chain.
//
//  What this node does:
//    * broadcasts a heartbeat   HB | uptime,freeheap,fwversion
//    * discovers neighbours from other nodes' heartbeats (RSSI + SNR)
//    * ages neighbours out after 40 s of silence, detects reconnection
//    * rejects any frame with a bad checksum or wrong protocol version
//    * never blocks, never hangs, feeds a hardware watchdog
//
//  Serial commands (115200):  n = neighbours   s = stats
//                             x = send a deliberately corrupted frame
//                             h = help
// ===========================================================================

#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <esp_task_wdt.h>

#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT  64
#define OLED_ADDR    0x3C

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// ------------------------------- identity ---------------------------------
#define MY_ID          "B"
#define FW_VERSION      1
#define PROTO_VERSION   1

// --------------------------------- pins -----------------------------------
#define LORA_SCK       18
#define LORA_MISO      19
#define LORA_MOSI      23
#define LORA_SS         5
#define LORA_RST       14
#define LORA_DIO0      26

#define I2C_SDA        21
#define I2C_SCL        22

#define PIN_SOS_BUTTON  4    // external push button to GND (used from Phase 3)
#define PIN_ENTROPY    34    // ADC1, input-only, floats -> good random seed

#define GPS_RX_PIN     16    // reserved for Phase 3
#define GPS_TX_PIN     17

// ------------------------------- LoRa PHY ---------------------------------
// Tune SF / TX power after the Phase 0 bench test.
// NOTE: the stock LoRa library leaves CRC OFF and uses the public sync word
// 0x12, so any other SX127x nearby collides with us. Both are fixed here.
#define LORA_FREQ      433E6
#define LORA_SF        8
#define LORA_BW        125000L
#define LORA_CR        5
#define LORA_TXPOWER   17
#define LORA_SYNCWORD  0x2A
#define LORA_PREAMBLE  8

// -------------------------------- timing ----------------------------------
#define HB_INTERVAL_MS       12000UL
#define HB_JITTER_MS          3000UL
#define NEIGHBOR_TIMEOUT_MS  40000UL
#define OLED_REFRESH_MS       1000UL
#define STAT_LOG_MS          30000UL
#define TX_MIN_GAP_MS          400UL
#define TX_GAP_JITTER_MS       250UL
#define RADIO_RETRY_MS        5000UL

// --------------------------------- sizes ----------------------------------
#define MAX_NEIGHBORS      8
#define MAX_PACKET_LEN   200
#define MAX_PAYLOAD_LEN  160
#define SEEN_CACHE_SIZE   32
#define TX_QUEUE_DEPTH     6
#define WDT_TIMEOUT_S     15
#define SERIAL_BAUD   115200

// ===========================================================================
//  NON-BLOCKING TIMER  (replaces every delay() in loop)
//
//  The phase 10/11 sketches staggered their first transmit like this:
//      lastBroadcastTime = millis() + random(0, 2000);          // BUG
//      if (millis() - lastBroadcastTime > interval) { ... }
//  Putting the timestamp in the FUTURE makes (millis() - last) underflow to a
//  huge unsigned value on the first pass, so the guard is immediately true and
//  the node transmits at once - the stagger never happened and all the nodes
//  keyed up together. begin() below gets the same effect correctly, by moving
//  the timestamp into the PAST by a controlled amount.
// ===========================================================================
struct Interval {
  uint32_t last;
  uint32_t period;

  void begin(uint32_t periodMs, uint32_t firstDelayMs) {
    period = periodMs;
    uint32_t back = (periodMs > firstDelayMs) ? (periodMs - firstDelayMs) : 0;
    last = millis() - back;               // always the past, never the future
  }
  bool due() {
    uint32_t now = millis();
    if (now - last >= period) { last = now; return true; }
    return false;
  }
  void setPeriod(uint32_t p) { period = p; }
};

Interval hbTimer, uiTimer, statTimer, retryTimer;

// ===========================================================================
//  PACKET FRAMING     v<VER>|<TYPE>|<SRC>|<DEST>|<MSGID>|<TTL>|<PAYLOAD>|<CHK>
//
//  All char buffers - no String anywhere in the receive/parse path, so the
//  ESP32 heap stays flat over a long run.
// ===========================================================================
struct Packet {
  uint8_t  ver;
  char     type[8];
  char     src[4];
  char     dest[4];
  uint16_t msgId;
  uint8_t  ttl;
  char     payload[MAX_PAYLOAD_LEN];
  int      rssi;
  float    snr;
};

uint8_t pktChecksum(const char *s, size_t n) {
  uint8_t c = 0;
  for (size_t i = 0; i < n; i++) c ^= (uint8_t)s[i];
  return c;
}

// '|' is the field separator, so it must never appear inside a field.
void pktSanitize(char *s) {
  for (char *p = s; *p; ++p)
    if (*p == '|' || *p == '\\' || *p == '\r' || *p == '\n') *p = '/';
}

// Build a frame. Returns length written, or 0 if it would not fit.
size_t pktBuild(char *out, size_t outSize,
                const char *type, const char *src, const char *dest,
                uint16_t msgId, uint8_t ttl, const char *payload) {
  int n = snprintf(out, outSize, "v%u|%s|%s|%s|%u|%u|%s",
                   (unsigned)PROTO_VERSION, type, src, dest,
                   (unsigned)msgId, (unsigned)ttl, payload ? payload : "");
  if (n < 0 || (size_t)n + 4 > outSize) return 0;
  uint8_t chk = pktChecksum(out, (size_t)n);
  int m = snprintf(out + n, outSize - (size_t)n, "|%02x", chk);
  if (m < 0) return 0;
  return (size_t)(n + m);
}

// Parse a frame IN PLACE. False if malformed, wrong version, or bad checksum.
bool pktParse(char *in, Packet &p) {
  size_t len = strlen(in);
  if (len < 12 || len >= MAX_PACKET_LEN) return false;

  char *lastBar = strrchr(in, '|');
  if (!lastBar) return false;
  if (strlen(lastBar + 1) != 2) return false;

  uint8_t want = (uint8_t)strtoul(lastBar + 1, NULL, 16);
  *lastBar = '\0';
  if (pktChecksum(in, strlen(in)) != want) return false;

  // Split on the first 6 pipes; field 7 keeps the rest, so a stray separator
  // inside a payload cannot shift the other fields.
  char *f[7];
  int nf = 0;
  f[nf++] = in;
  for (char *q = in; *q && nf < 7; ++q) {
    if (*q == '|') { *q = '\0'; f[nf++] = q + 1; }
  }
  if (nf != 7) return false;
  if (f[0][0] != 'v') return false;

  p.ver = (uint8_t)atoi(f[0] + 1);
  if (p.ver != PROTO_VERSION) return false;

  strncpy(p.type, f[1], sizeof(p.type) - 1); p.type[sizeof(p.type) - 1] = '\0';
  strncpy(p.src,  f[2], sizeof(p.src)  - 1); p.src[sizeof(p.src)   - 1] = '\0';
  strncpy(p.dest, f[3], sizeof(p.dest) - 1); p.dest[sizeof(p.dest) - 1] = '\0';
  p.msgId = (uint16_t)strtoul(f[4], NULL, 10);
  p.ttl   = (uint8_t) strtoul(f[5], NULL, 10);
  strncpy(p.payload, f[6], sizeof(p.payload) - 1);
  p.payload[sizeof(p.payload) - 1] = '\0';

  if (!p.type[0] || !p.src[0] || !p.dest[0]) return false;
  return true;
}

// ===========================================================================
//  DUPLICATE SUPPRESSION
//  SRC + MSGID uniquely identifies a packet. This ring stops us acting on a
//  repeat, and from Phase 2 stops us forwarding the same packet twice.
// ===========================================================================
uint32_t seenKeys[SEEN_CACHE_SIZE];
uint8_t  seenIdx = 0;

uint32_t seenKey(const char *src, uint16_t msgId) {
  uint32_t h = 2166136261UL;                       // FNV-1a over the node id
  for (const char *p = src; *p; ++p) { h ^= (uint8_t)*p; h *= 16777619UL; }
  uint32_t k = (h << 16) ^ msgId;
  return k ? k : 1;                                // 0 means "empty slot"
}

bool seenOrAdd(const char *src, uint16_t msgId) {
  uint32_t k = seenKey(src, msgId);
  for (uint8_t i = 0; i < SEEN_CACHE_SIZE; i++) if (seenKeys[i] == k) return true;
  seenKeys[seenIdx] = k;
  seenIdx = (uint8_t)((seenIdx + 1) % SEEN_CACHE_SIZE);
  return false;
}

// ===========================================================================
//  NEIGHBOUR TABLE
//  Fixed size, char based - no String members, so entries do not fragment the
//  heap as nodes come and go.
// ===========================================================================
struct Neighbor {
  char     id[4];
  int      rssi;
  float    snr;
  uint32_t lastSeen;
  uint32_t uptime;
  uint32_t heap;
  bool     used;
  bool     active;
};

Neighbor neighbors[MAX_NEIGHBORS];

#define NB_UPDATED      0
#define NB_NEW          1
#define NB_RECONNECTED  2
#define NB_FULL        -1

void neighborInit() {
  for (uint8_t i = 0; i < MAX_NEIGHBORS; i++) {
    neighbors[i].used = false;
    neighbors[i].active = false;
    neighbors[i].id[0] = '\0';
  }
}

int neighborUpdate(const char *id, int rssi, float snr, uint32_t uptime, uint32_t heap) {
  if (!id || !*id) return NB_UPDATED;
  uint32_t now = millis();

  for (uint8_t i = 0; i < MAX_NEIGHBORS; i++) {
    if (neighbors[i].used && strcmp(neighbors[i].id, id) == 0) {
      bool wasActive = neighbors[i].active;
      neighbors[i].rssi = rssi;
      neighbors[i].snr  = snr;
      neighbors[i].lastSeen = now;
      neighbors[i].uptime = uptime;
      neighbors[i].heap = heap;
      neighbors[i].active = true;
      return wasActive ? NB_UPDATED : NB_RECONNECTED;
    }
  }
  for (uint8_t i = 0; i < MAX_NEIGHBORS; i++) {
    if (!neighbors[i].used) {
      strncpy(neighbors[i].id, id, sizeof(neighbors[i].id) - 1);
      neighbors[i].id[sizeof(neighbors[i].id) - 1] = '\0';
      neighbors[i].rssi = rssi;
      neighbors[i].snr  = snr;
      neighbors[i].lastSeen = now;
      neighbors[i].uptime = uptime;
      neighbors[i].heap = heap;
      neighbors[i].used = true;
      neighbors[i].active = true;
      return NB_NEW;
    }
  }
  return NB_FULL;
}

// Marks ONE stale neighbour inactive per call. Drain it with a while() loop.
bool neighborPrune(char *lostId, size_t n) {
  uint32_t now = millis();
  for (uint8_t i = 0; i < MAX_NEIGHBORS; i++) {
    if (neighbors[i].used && neighbors[i].active &&
        (now - neighbors[i].lastSeen > NEIGHBOR_TIMEOUT_MS)) {
      neighbors[i].active = false;
      if (lostId && n) {
        strncpy(lostId, neighbors[i].id, n - 1);
        lostId[n - 1] = '\0';
      }
      return true;
    }
  }
  return false;
}

uint8_t neighborActiveCount() {
  uint8_t c = 0;
  for (uint8_t i = 0; i < MAX_NEIGHBORS; i++)
    if (neighbors[i].used && neighbors[i].active) c++;
  return c;
}

// Comma separated list of active neighbours, e.g. "A,C" - or "none".
void neighborActiveList(char *out, size_t n) {
  if (!out || n == 0) return;
  out[0] = '\0';
  size_t used = 0;
  for (uint8_t i = 0; i < MAX_NEIGHBORS; i++) {
    if (!neighbors[i].used || !neighbors[i].active) continue;
    size_t idLen = strlen(neighbors[i].id);
    if (used + idLen + (used ? 1 : 0) + 1 >= n) break;
    if (used) out[used++] = ',';
    memcpy(out + used, neighbors[i].id, idLen);
    used += idLen;
    out[used] = '\0';
  }
  if (used == 0) { strncpy(out, "none", n - 1); out[n - 1] = '\0'; }
}

int neighborFirstActive() {
  for (uint8_t i = 0; i < MAX_NEIGHBORS; i++)
    if (neighbors[i].used && neighbors[i].active) return (int)i;
  return -1;
}

// ===========================================================================
//  RADIO LAYER
//  All transmits go through one queue with a minimum gap + jitter, so a burst
//  never blocks the loop or stomps on itself.
// ===========================================================================
bool     radioOk = false;
char     txQueue[TX_QUEUE_DEPTH][MAX_PACKET_LEN];
uint8_t  txHead = 0, txTail = 0, txCount = 0;
uint32_t txLast = 0;
uint32_t txGap  = TX_MIN_GAP_MS;
uint16_t msgIdCounter = 0;

uint32_t statTx = 0, statRx = 0, statBad = 0, statDrop = 0;

uint16_t nextMsgId() {
  if (++msgIdCounter == 0) msgIdCounter = 1;
  return msgIdCounter;
}

bool radioBegin() {
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  for (uint8_t attempt = 0; attempt < 3; attempt++) {
    if (LoRa.begin(LORA_FREQ)) {
      LoRa.setSpreadingFactor(LORA_SF);
      LoRa.setSignalBandwidth(LORA_BW);
      LoRa.setCodingRate4(LORA_CR);
      LoRa.setTxPower(LORA_TXPOWER);
      LoRa.setSyncWord(LORA_SYNCWORD);
      LoRa.setPreambleLength(LORA_PREAMBLE);
      LoRa.enableCrc();
      LoRa.receive();
      radioOk = true;
      return true;
    }
    delay(200);                       // setup only - never inside loop()
  }
  radioOk = false;
  return false;
}

bool radioEnqueue(const char *frame) {
  if (!frame || !*frame) return false;
  if (txCount >= TX_QUEUE_DEPTH) { statDrop++; return false; }
  strncpy(txQueue[txTail], frame, MAX_PACKET_LEN - 1);
  txQueue[txTail][MAX_PACKET_LEN - 1] = '\0';
  txTail = (uint8_t)((txTail + 1) % TX_QUEUE_DEPTH);
  txCount++;
  return true;
}

// Sends at most one queued frame per call, respecting the gap.
void radioService() {
  if (!radioOk || txCount == 0) return;
  if (millis() - txLast < txGap) return;

  LoRa.beginPacket();
  LoRa.print(txQueue[txHead]);
  int r = LoRa.endPacket();
  LoRa.receive();                     // always go back to listening

  if (r == 1) statTx++; else statDrop++;

  txHead = (uint8_t)((txHead + 1) % TX_QUEUE_DEPTH);
  txCount--;
  txLast = millis();
  txGap  = TX_MIN_GAP_MS + (uint32_t)random(0, TX_GAP_JITTER_MS);
}

bool radioPoll(Packet &out) {
  if (!radioOk) return false;
  int sz = LoRa.parsePacket();
  if (sz <= 0) return false;

  char buf[MAX_PACKET_LEN];
  int n = 0;
  while (LoRa.available() && n < (int)sizeof(buf) - 1) buf[n++] = (char)LoRa.read();
  buf[n] = '\0';
  while (LoRa.available()) LoRa.read();          // discard overflow

  int   rssi = LoRa.packetRssi();
  float snr  = LoRa.packetSnr();

  if (!pktParse(buf, out)) { statBad++; return false; }
  out.rssi = rssi;
  out.snr  = snr;
  statRx++;
  return true;
}

// ===========================================================================
//  OLED  (SSD1306 via Adafruit)  -  5 rows, ASCII only.
//  The emoji the old phase 11 screens tried to draw cannot render in a bitmap
//  font, which is why those lines came out as boxes.
// ===========================================================================
bool oledOk = false;

void oledClear() { if (oledOk) display.clearDisplay(); }
void oledLine(uint8_t row, const char *txt) {
  if (oledOk && row < 5 && txt) {
    display.setCursor(0, row * 12);
    display.print(txt);
  }
}
void oledShow() { if (oledOk) display.display(); }

void oledBanner(const char *l0, const char *l1) {
  oledClear();
  oledLine(0, l0);
  if (l1) oledLine(1, l1);
  oledShow();
}

// ===========================================================================
//  WATCHDOG   (guarded for ESP32 Arduino core 2.x and 3.x)
// ===========================================================================
void wdtBegin() {
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  esp_task_wdt_config_t cfg;
  cfg.timeout_ms     = WDT_TIMEOUT_S * 1000;
  cfg.idle_core_mask = 0;
  cfg.trigger_panic  = true;
  if (esp_task_wdt_init(&cfg) != ESP_OK) esp_task_wdt_reconfigure(&cfg);
#else
  esp_task_wdt_init(WDT_TIMEOUT_S, true);
#endif
  esp_task_wdt_add(NULL);
}

// ===========================================================================
//  APPLICATION
// ===========================================================================
void sendHeartbeat() {
  char payload[48];
  snprintf(payload, sizeof(payload), "%lu,%lu,%u",
           (unsigned long)(millis() / 1000UL),
           (unsigned long)ESP.getFreeHeap(),
           (unsigned)FW_VERSION);

  char frame[MAX_PACKET_LEN];
  if (pktBuild(frame, sizeof(frame), "HB", MY_ID, "*", nextMsgId(), 0, payload))
    radioEnqueue(frame);

  // Re-jitter every period so two nodes that happen to line up drift apart
  // again instead of colliding forever.
  hbTimer.setPeriod(HB_INTERVAL_MS + (uint32_t)random(0, HB_JITTER_MS));
}

void handleRx() {
  Packet p;
  if (!radioPoll(p)) return;
  if (strcmp(p.src, MY_ID) == 0) return;              // our own echo
  if (seenOrAdd(p.src, p.msgId)) return;              // duplicate

  if (strcmp(p.type, "HB") == 0) {
    unsigned long up = 0, hp = 0;
    unsigned      fw = 0;
    sscanf(p.payload, "%lu,%lu,%u", &up, &hp, &fw);

    int ev = neighborUpdate(p.src, p.rssi, p.snr, (uint32_t)up, (uint32_t)hp);
    if      (ev == NB_NEW)         Serial.printf("[mesh] NEW neighbour %s  %d dBm\n", p.src, p.rssi);
    else if (ev == NB_RECONNECTED) Serial.printf("[mesh] RECONNECTED %s  %d dBm\n", p.src, p.rssi);
    else if (ev == NB_FULL)        Serial.println("[mesh] neighbour table FULL");
  }

  Serial.printf("[rx] %s from %s id=%u ttl=%u rssi=%d snr=%.1f : %s\n",
                p.type, p.src, (unsigned)p.msgId, (unsigned)p.ttl,
                p.rssi, (double)p.snr, p.payload);
}

void drawUI() {
  char l0[24], l1[24], l2[24], l3[24], l4[24], list[20];
  neighborActiveList(list, sizeof(list));

  snprintf(l0, sizeof(l0), "NODE %s  fw%u %s",
           MY_ID, (unsigned)FW_VERSION, radioOk ? "" : "!RF");
  snprintf(l1, sizeof(l1), "Conn: %s", list);

  int fi = neighborFirstActive();
  if (fi >= 0)
    snprintf(l2, sizeof(l2), "%s %ddBm snr%.0f",
             neighbors[fi].id, neighbors[fi].rssi, (double)neighbors[fi].snr);
  else
    snprintf(l2, sizeof(l2), "scanning...");

  snprintf(l3, sizeof(l3), "tx%lu rx%lu bad%lu",
           (unsigned long)statTx, (unsigned long)statRx, (unsigned long)statBad);
  snprintf(l4, sizeof(l4), "heap %lu up%lus",
           (unsigned long)ESP.getFreeHeap(),
           (unsigned long)(millis() / 1000UL));

  oledClear();
  oledLine(0, l0); oledLine(1, l1); oledLine(2, l2);
  oledLine(3, l3); oledLine(4, l4);
  oledShow();
}

void printNeighbours() {
  Serial.println("\n---- NEIGHBOURS ----------------------------------");
  Serial.println("ID   RSSI   SNR    AGE(s)  UPTIME(s)  THEIR HEAP  STATE");
  bool any = false;
  for (uint8_t i = 0; i < MAX_NEIGHBORS; i++) {
    if (!neighbors[i].used) continue;
    any = true;
    Serial.printf("%-4s %-6d %-6.1f %-7lu %-10lu %-11lu %s\n",
                  neighbors[i].id, neighbors[i].rssi, (double)neighbors[i].snr,
                  (unsigned long)((millis() - neighbors[i].lastSeen) / 1000UL),
                  (unsigned long)neighbors[i].uptime,
                  (unsigned long)neighbors[i].heap,
                  neighbors[i].active ? "ACTIVE" : "lost");
  }
  if (!any) Serial.println("(none discovered yet)");
  Serial.println("--------------------------------------------------\n");
}

void printStats() {
  Serial.printf("[stat] up=%lus heap=%lu neigh=%u tx=%lu rx=%lu bad=%lu drop=%lu q=%u\n",
                (unsigned long)(millis() / 1000UL),
                (unsigned long)ESP.getFreeHeap(),
                (unsigned)neighborActiveCount(),
                (unsigned long)statTx, (unsigned long)statRx,
                (unsigned long)statBad, (unsigned long)statDrop,
                (unsigned)txCount);
}

void handleSerial() {
  if (!Serial.available()) return;
  int c = Serial.read();

  if (c == 'n') {
    printNeighbours();

  } else if (c == 's') {
    printStats();

  } else if (c == 'x') {
    // Integrity test: send a frame whose checksum is deliberately wrong.
    // Every peer must count it under "bad" and must NOT add a neighbour.
    char frame[MAX_PACKET_LEN];
    if (pktBuild(frame, sizeof(frame), "HB", MY_ID, "*", nextMsgId(), 0, "0,0,1")) {
      size_t len = strlen(frame);
      frame[len - 1] = (frame[len - 1] == '0') ? '1' : '0';
      radioEnqueue(frame);
      Serial.println("[test] queued a BAD-CHECKSUM frame - peers must reject it");
    }

  } else if (c == 'h' || c == '?') {
    Serial.println("commands:  n=neighbours  s=stats  x=send bad-checksum frame  h=help");
  }
}

// ===========================================================================
//  SETUP
// ===========================================================================
void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(200);

  pinMode(PIN_SOS_BUTTON, INPUT_PULLUP);      // used from Phase 3

  // Seed from a floating ADC1 pin, not GPIO 0. GPIO 0 is a strapping pin and
  // reads nearly the same on every board, so the old code gave all the nodes
  // correlated "random" jitter.
  randomSeed(((uint32_t)analogRead(PIN_ENTROPY) << 16) ^ micros());

  memset(seenKeys, 0, sizeof(seenKeys));
  neighborInit();

  // STEP 1: display  (0x3D is tried automatically as a fallback)
  Wire.begin(I2C_SDA, I2C_SCL);
  oledOk = display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  if (!oledOk) oledOk = display.begin(SSD1306_SWITCHCAPVCC, 0x3D);
  if (oledOk) {
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    oledBanner("Booting...", "Node " MY_ID);
  } else {
    Serial.println("[oled] init FAILED - check SDA21 / SCL22");
  }

  Serial.printf("\n[boot] Node %s fw v%u  heap=%lu\n",
                MY_ID, (unsigned)FW_VERSION, (unsigned long)ESP.getFreeHeap());

  // STEP 2: radio
  if (radioBegin()) {
    Serial.printf("[radio] LoRa OK  SF%d BW125 CRC=on sync=0x%02X pwr=%ddBm\n",
                  (int)LORA_SF, (int)LORA_SYNCWORD, (int)LORA_TXPOWER);
    char l1[24];
    snprintf(l1, sizeof(l1), "SF%d CRC on", (int)LORA_SF);
    oledBanner("LoRa OK", l1);
  } else {
    // Deliberately NOT while(1). The old sketches hung here with a frozen
    // screen and no watchdog; this one keeps running and keeps retrying.
    Serial.println("[radio] LoRa FAIL - check SPI wiring and 3.3V (never 5V)");
    oledBanner("LoRa FAIL", "check SPI / 3V3");
  }

  wdtBegin();

  hbTimer.begin(HB_INTERVAL_MS, (uint32_t)random(0, HB_JITTER_MS));  // staggered
  uiTimer.begin(OLED_REFRESH_MS, OLED_REFRESH_MS);
  statTimer.begin(STAT_LOG_MS, STAT_LOG_MS);
  retryTimer.begin(RADIO_RETRY_MS, RADIO_RETRY_MS);

  Serial.println("[boot] ready. type 'h' for commands.");
}

// ===========================================================================
//  LOOP   -   no delay() anywhere below this line
// ===========================================================================
void loop() {
  esp_task_wdt_reset();

  // 1. receive
  handleRx();

  // 2. age out silent neighbours
  char lost[4];
  while (neighborPrune(lost, sizeof(lost)))
    Serial.printf("[mesh] LOST %s (no heartbeat for %lus)\n",
                  lost, (unsigned long)(NEIGHBOR_TIMEOUT_MS / 1000UL));

  // 3. heartbeat
  if (hbTimer.due()) sendHeartbeat();

  // 4. transmit pump
  radioService();

  // 5. display + periodic statistics
  if (uiTimer.due())   drawUI();
  if (statTimer.due()) printStats();

  // 6. recover a radio that failed at boot
  if (!radioOk && retryTimer.due()) {
    Serial.println("[radio] retrying init...");
    if (radioBegin()) Serial.println("[radio] recovered");
  }

  // 7. serial commands
  handleSerial();
}
