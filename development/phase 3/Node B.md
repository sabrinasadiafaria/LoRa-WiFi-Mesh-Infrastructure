// ===========================================================================
//  PHASE 3  -  MULTI-HOP MESH  -  NODE B
//  ESP32 + LoRa SX1278 (433 MHz) + 0.96" SSD1306 OLED + NEO-M8N GPS + Wi-Fi portal
//
//  Complete standalone sketch - paste the whole file into the Arduino IDE.
//
//  Libraries: LoRa (Sandeep Mistry), Adafruit GFX, Adafruit SSD1306
//  Board:     ESP32 Dev Module
//
//  Everything Phase 2 did, plus the capability this project is named for:
//    * DISTANCE-VECTOR ROUTING - each node advertises what it can reach
//    * MULTI-HOP FORWARDING    - A talks to C through B, past direct range
//    * SELF-HEALING            - a dead relay is detected, its routes go
//                                invalid, traffic re-routes, and the route
//                                recovers by itself when the relay returns
//    * SPLIT HORIZON           - a route is never accepted back through the
//                                node it already goes through, which is what
//                                actually prevents count-to-infinity
//    * 3-PAGE OLED             - status / routing table / node positions
//
//  HOW TO SEE MULTI-HOP: separate A and C far enough (or shield one) that
//  they cannot hear each other directly, leaving B in the middle. Watch A's
//  routing table learn "C via B 2h", then press 'c' on A - the message
//  reaches C through B, and B prints the forward.
//
//  HOW TO SEE SELF-HEALING: with that working, power B off. Within ~45 s A
//  logs "[route] LOST C ... invalidating" and refuses to send. Power B back
//  on and A logs "RECOVERED" and starts delivering again.
//
//  WI-FI PORTAL: connect a phone to "SOS_Node_B" (open, no password). The
//  rescue portal pops up automatically; if not, open http://192.168.4.1
//
//  WHY THERE IS A MANUAL COORDINATE BOX: browsers only allow
//  navigator.geolocation on a SECURE origin (HTTPS). A captive portal is
//  plain HTTP, so Chrome and Safari usually REFUSE the "Use Phone GPS"
//  button. That is browser policy, not a bug here, and a self-signed
//  certificate does not help. Manual entry always works.
//
//  Serial commands (115200):
//     n = neighbours   r = routing table   g = GPS/location   s = stats
//     a / b / c = send a test message to that node
//     t = toggle automatic repeat send     p = next OLED page
//     x = send a deliberately corrupted frame                 h = help
// ===========================================================================

#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <esp_task_wdt.h>
#include <esp_system.h>

#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT  64
#define OLED_ADDR    0x3C

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// ------------------------------- identity ---------------------------------
#define MY_ID          "B"
#define FW_VERSION      3
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

#define GPS_RX_PIN     16    // ESP32 RX2  <- GPS TX
#define GPS_TX_PIN     17    // ESP32 TX2  -> GPS RX
#define GPS_BAUD     9600

// ------------------------------- LoRa PHY ---------------------------------
// NOTE: the stock LoRa library leaves CRC OFF and uses the public sync word
// 0x12, so any other SX127x nearby collides with us. Both are fixed here.
#define LORA_FREQ      433E6
#define LORA_SF        7        // was 8; measured SNR 10-13 dB leaves plenty of margin
#define LORA_BW        125000L
#define LORA_CR        5
#define LORA_TXPOWER   17
#define LORA_SYNCWORD  0x2A
#define LORA_PREAMBLE  8

// ------------------------------ Wi-Fi portal ------------------------------
#define ENABLE_PORTAL   1              // set 0 to make this a LoRa-only relay
#define AP_SSID        "SOS_Node_B"
#define AP_PASSWORD    NULL            // NULL = open network (captive portal)
#define AP_CHANNEL      1
#define AP_MAX_CLIENTS  4

// ------------------------------ location ----------------------------------
// A phone fix is preferred while it is fresh; the GPS module is the fallback.
// Set LOCATION_PREFER_PHONE to 0 to reverse that.
#define LOCATION_PREFER_PHONE   1
#define GPS_FRESH_MS        30000UL    // module fix counts as "live" this long
#define PHONE_FRESH_MS     300000UL    // phone fix counts as "live" this long

#define LOC_NONE   0
#define LOC_GPS    1
#define LOC_PHONE  2

// -------------------------------- timing ----------------------------------
#define HB_INTERVAL_MS       10000UL
#define HB_JITTER_MS          3000UL
#define GPS_INTERVAL_MS      30000UL
#define GPS_JITTER_MS         4000UL
#define RT_INTERVAL_MS       15000UL   // routing advertisement period
#define RT_JITTER_MS          4000UL
#define ROUTE_TIMEOUT_MS     50000UL   // ~3 missed adverts -> route invalid
#define NEIGHBOR_TIMEOUT_MS  35000UL   // ~3 missed heartbeats
#define AUTO_DATA_MS         15000UL   // repeat-send period when t is toggled on
#define OLED_REFRESH_MS       1000UL
#define UI_PAGE_MS            4000UL   // how long each OLED page is shown
#define STAT_LOG_MS          30000UL
#define TX_MIN_GAP_MS          400UL
#define TX_GAP_JITTER_MS       250UL
#define TX_TIMEOUT_MS         3000UL   // give up on a transmit that never completes
#define RADIO_RETRY_MS        5000UL

// --------------------------------- sizes ----------------------------------
#define MAX_NEIGHBORS      8
#define MAX_ROUTES         8
#define MAX_HOPS           4           // also the initial TTL of a DATA packet
#define MAX_PACKET_LEN   200
#define MAX_PAYLOAD_LEN  160
#define SEEN_CACHE_SIZE   32
#define TX_QUEUE_DEPTH     6
#define NMEA_BUF_LEN     100
#define UI_PAGES           3
#define WDT_TIMEOUT_S     30       // transmits are bounded now, so this can be tight again
#define SERIAL_BAUD   115200

// ===========================================================================
//  NON-BLOCKING TIMER  (replaces every delay() in loop)
//
//  The phase 10/11 sketches staggered their first transmit like this:
//      lastBroadcastTime = millis() + random(0, 2000);          // BUG
//      if (millis() - lastBroadcastTime > interval) { ... }
//  Putting the timestamp in the FUTURE makes (millis() - last) underflow to a
//  huge unsigned value on the first pass, so the guard is immediately true and
//  the node transmits at once - the stagger never happened. begin() below gets
//  the same effect correctly, by moving the timestamp into the PAST.
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

Interval hbTimer, gpsTimer, rtTimer, autoTimer;
Interval uiTimer, pageTimer, statTimer, retryTimer;

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
// ===========================================================================
uint32_t seenKeys[SEEN_CACHE_SIZE];
uint8_t  seenIdx = 0;

uint32_t seenKey(const char *src, uint16_t msgId) {
  uint32_t h = 2166136261UL;                       // FNV-1a over the node id
  for (const char *p = src; *p; ++p) { h ^= (uint8_t)*p; h *= 16777619UL; }
  uint32_t k = (h << 16) ^ msgId;
  return k ? k : 1;
}

bool seenOrAdd(const char *src, uint16_t msgId) {
  uint32_t k = seenKey(src, msgId);
  for (uint8_t i = 0; i < SEEN_CACHE_SIZE; i++) if (seenKeys[i] == k) return true;
  seenKeys[seenIdx] = k;
  seenIdx = (uint8_t)((seenIdx + 1) % SEEN_CACHE_SIZE);
  return false;
}

// ===========================================================================
//  NEIGHBOUR TABLE   (now also stores each peer's reported position)
// ===========================================================================
struct Neighbor {
  char     id[4];
  int      rssi;
  float    snr;
  uint32_t lastSeen;
  uint32_t uptime;
  uint32_t heap;
  double   lat, lon;
  uint8_t  locSrc;      // LOC_NONE / LOC_GPS / LOC_PHONE
  bool     hasLoc;
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
    neighbors[i].hasLoc = false;
    neighbors[i].locSrc = LOC_NONE;
    neighbors[i].id[0] = '\0';
  }
}

int neighborIndex(const char *id) {
  for (uint8_t i = 0; i < MAX_NEIGHBORS; i++)
    if (neighbors[i].used && strcmp(neighbors[i].id, id) == 0) return (int)i;
  return -1;
}

// Any packet from a peer proves it is alive. Returns NB_NEW / NB_RECONNECTED /
// NB_UPDATED / NB_FULL.
int neighborSeen(const char *id, int rssi, float snr) {
  if (!id || !*id) return NB_UPDATED;
  uint32_t now = millis();

  int i = neighborIndex(id);
  if (i >= 0) {
    bool wasActive = neighbors[i].active;
    neighbors[i].rssi = rssi;
    neighbors[i].snr  = snr;
    neighbors[i].lastSeen = now;
    neighbors[i].active = true;
    return wasActive ? NB_UPDATED : NB_RECONNECTED;
  }
  for (uint8_t k = 0; k < MAX_NEIGHBORS; k++) {
    if (!neighbors[k].used) {
      strncpy(neighbors[k].id, id, sizeof(neighbors[k].id) - 1);
      neighbors[k].id[sizeof(neighbors[k].id) - 1] = '\0';
      neighbors[k].rssi = rssi;
      neighbors[k].snr  = snr;
      neighbors[k].lastSeen = now;
      neighbors[k].uptime = 0;
      neighbors[k].heap = 0;
      neighbors[k].hasLoc = false;
      neighbors[k].locSrc = LOC_NONE;
      neighbors[k].used = true;
      neighbors[k].active = true;
      return NB_NEW;
    }
  }
  return NB_FULL;
}

void neighborSetStats(const char *id, uint32_t uptime, uint32_t heap) {
  int i = neighborIndex(id);
  if (i < 0) return;
  neighbors[i].uptime = uptime;
  neighbors[i].heap = heap;
}

void neighborSetLoc(const char *id, double lat, double lon, uint8_t src) {
  int i = neighborIndex(id);
  if (i < 0) return;
  neighbors[i].lat = lat;
  neighbors[i].lon = lon;
  neighbors[i].locSrc = src;
  neighbors[i].hasLoc = (src != LOC_NONE);
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

// Comma separated list of active neighbours, e.g. "B,C" - or "none".
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

// ===========================================================================
//  ROUTING TABLE  -  distance vector with split horizon
//
//  Each node keeps ONE entry per destination: who to hand the packet to
//  (nextHop) and how many hops away it is. Entries are learned two ways:
//
//    1. any packet heard directly from X  ->  X is reachable in 1 hop via X
//    2. an RT advertisement from S saying "I can reach D in h hops via V"
//       ->  D is reachable in h+1 hops via S
//
//  SPLIT HORIZON is the reason the advert carries V (the advertiser's own
//  next hop). If V is us, that route only exists because of us, and taking
//  it back would create a loop whose hop count climbs forever - the classic
//  count-to-infinity. The old phase 7-9 code claimed split horizon in its
//  comments but never actually implemented it; it only bounded the damage
//  with MAX_HOPS and a timeout. Here the entry is genuinely discarded.
//
//  A route that stops being advertised goes invalid after ROUTE_TIMEOUT_MS.
//  That is the self-healing trigger: traffic through a dead relay stops
//  immediately rather than disappearing into a black hole, and the route
//  recovers by itself when the relay comes back.
// ===========================================================================
struct Route {
  char     dest[4];
  char     nextHop[4];
  uint8_t  hops;
  int      rssi;
  uint32_t lastUpdated;
  bool     used;
  bool     valid;
};

Route routes[MAX_ROUTES];

#define RT_NONE       0
#define RT_NEW        1
#define RT_RECOVERED  2
#define RT_BETTER     3
#define RT_FULL      -1

void routeInit() {
  for (uint8_t i = 0; i < MAX_ROUTES; i++) {
    routes[i].used = false;
    routes[i].valid = false;
    routes[i].dest[0] = '\0';
    routes[i].nextHop[0] = '\0';
  }
}

int routeIndex(const char *dest) {
  for (uint8_t i = 0; i < MAX_ROUTES; i++)
    if (routes[i].used && strcmp(routes[i].dest, dest) == 0) return (int)i;
  return -1;
}

// Accept an advertised path. Returns RT_NEW / RT_RECOVERED / RT_BETTER /
// RT_NONE / RT_FULL so the caller can log the interesting transitions.
int routeUpdate(const char *dest, const char *via, uint8_t hops, int rssi) {
  if (!dest || !*dest || !via || !*via) return RT_NONE;
  if (strcmp(dest, MY_ID) == 0) return RT_NONE;      // never route to self
  if (hops == 0 || hops > MAX_HOPS) return RT_NONE;  // bounds count-to-infinity

  uint32_t now = millis();
  int i = routeIndex(dest);

  if (i >= 0) {
    bool wasValid = routes[i].valid;
    bool sameHop  = (strcmp(routes[i].nextHop, via) == 0);

    // Take the update if it comes from the hop we already use (so a path is
    // allowed to legitimately get longer), or if it is strictly shorter, or
    // if we had given up on this destination entirely.
    if (sameHop || hops < routes[i].hops || !wasValid) {
      strncpy(routes[i].nextHop, via, sizeof(routes[i].nextHop) - 1);
      routes[i].nextHop[sizeof(routes[i].nextHop) - 1] = '\0';
      routes[i].hops = hops;
      routes[i].rssi = rssi;
      routes[i].lastUpdated = now;
      routes[i].valid = true;
      if (!wasValid) return RT_RECOVERED;
      if (!sameHop)  return RT_BETTER;
    }
    return RT_NONE;
  }

  for (uint8_t k = 0; k < MAX_ROUTES; k++) {
    if (!routes[k].used) {
      strncpy(routes[k].dest, dest, sizeof(routes[k].dest) - 1);
      routes[k].dest[sizeof(routes[k].dest) - 1] = '\0';
      strncpy(routes[k].nextHop, via, sizeof(routes[k].nextHop) - 1);
      routes[k].nextHop[sizeof(routes[k].nextHop) - 1] = '\0';
      routes[k].hops = hops;
      routes[k].rssi = rssi;
      routes[k].lastUpdated = now;
      routes[k].used = true;
      routes[k].valid = true;
      return RT_NEW;
    }
  }
  return RT_FULL;
}

// Invalidates ONE stale route per call and reports it. Drain with a while().
bool routeExpire(char *lostDest, size_t n) {
  uint32_t now = millis();
  for (uint8_t i = 0; i < MAX_ROUTES; i++) {
    if (routes[i].used && routes[i].valid &&
        (now - routes[i].lastUpdated > ROUTE_TIMEOUT_MS)) {
      routes[i].valid = false;
      if (lostDest && n) {
        strncpy(lostDest, routes[i].dest, n - 1);
        lostDest[n - 1] = '\0';
      }
      return true;
    }
  }
  return false;
}

// Who do we hand a packet for `dest` to? NULL means we have no way there.
const char *routeBestHop(const char *dest) {
  int i = routeIndex(dest);
  if (i < 0 || !routes[i].valid) return NULL;
  return routes[i].nextHop;
}

uint8_t routeValidCount() {
  uint8_t c = 0;
  for (uint8_t i = 0; i < MAX_ROUTES; i++)
    if (routes[i].used && routes[i].valid) c++;
  return c;
}

// Split one advertised "dest,hops,via" triple.
bool routeParseEntry(char *tok, char *d, size_t dn, unsigned *h, char *v, size_t vn) {
  char *c1 = strchr(tok, ',');
  if (!c1) return false;
  *c1 = '\0';
  char *c2 = strchr(c1 + 1, ',');
  if (!c2) return false;
  *c2 = '\0';
  strncpy(d, tok, dn - 1);      d[dn - 1] = '\0';
  strncpy(v, c2 + 1, vn - 1);   v[vn - 1] = '\0';
  *h = (unsigned)strtoul(c1 + 1, NULL, 10);
  return d[0] && v[0];
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
bool     txInFlight = false;      // a transmission is on air right now
uint32_t txStart = 0;             // when it started, for the timeout
uint16_t msgIdCounter = 0;

uint32_t statTx = 0, statRx = 0, statBad = 0, statDrop = 0;
uint32_t statFwd = 0, statDataTx = 0, statDataRx = 0;
uint32_t statTxStuck = 0;         // transmits that never reported TX_DONE

// last application message delivered to this node (shown on the OLED/portal)
char     lastMsgFrom[4] = "";
char     lastMsgText[40] = "";
uint32_t lastMsgTime = 0;

// repeat-send test state, driven by the a/b/c and t serial commands
bool     autoData = false;
char     autoTarget[4] = "";
uint8_t  uiPage = 0;

// A node that has just booted sends a few quick heartbeats so its peers
// rediscover it in seconds instead of waiting a whole HB_INTERVAL_MS.
uint8_t  bootBeacons = 4;

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

// Transmit is ASYNCHRONOUS and bounded.
//
// WHY: LoRa.endPacket() with no argument spins here, inside the library:
//
//     while ((readRegister(REG_IRQ_FLAGS) & IRQ_TX_DONE_MASK) == 0) yield();
//
// There is no timeout. If the SX1278 never raises TX_DONE - a SPI glitch, or
// the 3.3V rail dipping because the Wi-Fi AP transmitted at the same instant -
// that loop NEVER RETURNS and the task watchdog kills the node. That is the
// "TASK_WDT - loop stalled" reset, and it is why the node with a phone on its
// portal died while the one without a phone did not.
//
// endPacket(true) returns immediately instead; we poll isTransmitting() and,
// if TX_DONE has not arrived within TX_TIMEOUT_MS, we reinitialise the radio
// and carry on rather than hanging.
void radioService() {
  // ---- finish an in-flight transmission -----------------------------------
  if (txInFlight) {
    if (!LoRa.isTransmitting()) {
      txInFlight = false;
      statTx++;
      LoRa.receive();                 // back to listening
      txLast = millis();
      txGap  = TX_MIN_GAP_MS + (uint32_t)random(0, TX_GAP_JITTER_MS);
    } else if (millis() - txStart > TX_TIMEOUT_MS) {
      Serial.println("[radio] TX never completed - resetting radio (this would "
                     "have hung the node before)");
      txInFlight = false;
      statTxStuck++;
      statDrop++;
      radioOk = false;
      radioBegin();                   // bounded: 3 attempts, then gives up
      txLast = millis();
    }
    return;                           // never start a second transmit
  }

  // ---- start the next queued transmission ---------------------------------
  if (!radioOk || txCount == 0) return;
  if (millis() - txLast < txGap) return;

  LoRa.beginPacket();
  LoRa.print(txQueue[txHead]);
  LoRa.endPacket(true);               // async - returns straight away
  txInFlight = true;
  txStart    = millis();

  txHead = (uint8_t)((txHead + 1) % TX_QUEUE_DEPTH);
  txCount--;
}

bool radioPoll(Packet &out) {
  if (!radioOk) return false;
  if (txInFlight) return false;       // half duplex - not while we transmit
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
//  GPS MODULE  -  non-blocking NMEA reader
//
//  The old phase 10 code used Serial2.readStringUntil('\n'), which BLOCKS for
//  up to 1000 ms whenever the GPS is unplugged or silent - stalling the whole
//  loop and dropping LoRa packets. This assembles lines character by character
//  and never waits.
// ===========================================================================
char     nmeaBuf[NMEA_BUF_LEN];
uint8_t  nmeaLen = 0;

double   gpsLat = 0.0, gpsLon = 0.0;
bool     gpsHasFix = false;
uint32_t gpsFixTime = 0;        // millis() of the last valid fix (0 = never)
int      gpsSats = 0;
uint32_t gpsSentences = 0;      // NMEA lines seen - proves the module is wired

// Copy field `idx` (comma separated) out of an NMEA sentence.
bool nmeaField(const char *s, int idx, char *out, size_t outN) {
  int field = 0;
  const char *p = s;
  const char *start = s;
  while (1) {
    if (*p == ',' || *p == '*' || *p == '\0') {
      if (field == idx) {
        size_t len = (size_t)(p - start);
        if (len >= outN) len = outN - 1;
        memcpy(out, start, len);
        out[len] = '\0';
        return true;
      }
      if (*p == '*' || *p == '\0') return false;
      field++;
      start = p + 1;
    }
    p++;
  }
}

// NMEA gives ddmm.mmmm / dddmm.mmmm - always exactly 2 digits of whole minutes
// before the decimal point.
double nmeaCoord(const char *val, const char *dir) {
  size_t vl = strlen(val);
  if (vl < 4) return 0.0;
  const char *dot = strchr(val, '.');
  if (!dot) return 0.0;
  int degLen = (int)(dot - val) - 2;
  if (degLen <= 0 || degLen > 3) return 0.0;

  char degBuf[8];
  memcpy(degBuf, val, (size_t)degLen);
  degBuf[degLen] = '\0';

  double deg = atof(degBuf);
  double mins = atof(val + degLen);
  double d = deg + mins / 60.0;
  if (dir[0] == 'S' || dir[0] == 'W') d = -d;
  return d;
}

void nmeaParse(const char *line) {
  size_t len = strlen(line);
  if (len < 7 || line[0] != '$') return;
  gpsSentences++;

  // $GPRMC / $GNRMC  - position and validity
  if (strncmp(line + 3, "RMC", 3) == 0) {
    char status[4];
    if (!nmeaField(line, 2, status, sizeof(status))) return;
    if (status[0] != 'A') { gpsHasFix = false; return; }   // 'V' = not valid

    char la[16], ns[4], lo[16], ew[4];
    if (!nmeaField(line, 3, la, sizeof(la))) return;
    if (!nmeaField(line, 4, ns, sizeof(ns))) return;
    if (!nmeaField(line, 5, lo, sizeof(lo))) return;
    if (!nmeaField(line, 6, ew, sizeof(ew))) return;
    if (!la[0] || !lo[0] || !ns[0] || !ew[0]) return;

    // Validity comes from the 'A' status flag above, NOT from comparing the
    // coordinates against 0.0 - the old code did that and would have thrown
    // away a genuine fix on the equator or the prime meridian.
    gpsLat = nmeaCoord(la, ns);
    gpsLon = nmeaCoord(lo, ew);
    gpsHasFix = true;
    gpsFixTime = millis();
  }
  // $GPGGA / $GNGGA  - satellites in use
  else if (strncmp(line + 3, "GGA", 3) == 0) {
    char sats[8];
    if (nmeaField(line, 7, sats, sizeof(sats)) && sats[0]) gpsSats = atoi(sats);
  }
}

void gpsService() {
  while (Serial2.available()) {
    char c = (char)Serial2.read();
    if (c == '\n' || c == '\r') {
      if (nmeaLen > 6) { nmeaBuf[nmeaLen] = '\0'; nmeaParse(nmeaBuf); }
      nmeaLen = 0;
    } else if (nmeaLen < NMEA_BUF_LEN - 1) {
      nmeaBuf[nmeaLen++] = c;
    } else {
      nmeaLen = 0;                    // overlong sentence - discard
    }
  }
}

// ===========================================================================
//  HYBRID LOCATION MANAGER
//
//  Two independent sources:
//     LOC_PHONE  a position handed to us by a phone through the captive portal
//     LOC_GPS    a live fix from the NEO-6M / NEO-M8N module
//
//  The GPS module cannot get a fix indoors, under debris or beneath a roof -
//  exactly where a rescue node is most likely to be - so a fresh phone fix is
//  preferred and the module is the fallback. Flip LOCATION_PREFER_PHONE to
//  reverse that. If neither is fresh, the most recent of the two is used and
//  reported with its age so nobody mistakes it for live.
// ===========================================================================
double   phoneLat = 0.0, phoneLon = 0.0;
bool     phoneValid = false;
uint32_t phoneTime = 0;
float    phoneAcc = 0.0;
uint32_t phoneUpdates = 0;

// Returns LOC_NONE / LOC_GPS / LOC_PHONE and fills lat/lon/ageMs.
uint8_t locBest(double &lat, double &lon, uint32_t &ageMs) {
  uint32_t now = millis();
  bool gFresh = gpsHasFix  && gpsFixTime && (now - gpsFixTime < GPS_FRESH_MS);
  bool pFresh = phoneValid && phoneTime  && (now - phoneTime  < PHONE_FRESH_MS);

#if LOCATION_PREFER_PHONE
  if (pFresh) { lat = phoneLat; lon = phoneLon; ageMs = now - phoneTime;  return LOC_PHONE; }
  if (gFresh) { lat = gpsLat;   lon = gpsLon;   ageMs = now - gpsFixTime; return LOC_GPS;   }
#else
  if (gFresh) { lat = gpsLat;   lon = gpsLon;   ageMs = now - gpsFixTime; return LOC_GPS;   }
  if (pFresh) { lat = phoneLat; lon = phoneLon; ageMs = now - phoneTime;  return LOC_PHONE; }
#endif

  // Neither is fresh - fall back to whichever we heard most recently.
  if (gpsFixTime || phoneTime) {
    if (gpsFixTime >= phoneTime && gpsFixTime) {
      lat = gpsLat; lon = gpsLon; ageMs = now - gpsFixTime; return LOC_GPS;
    }
    if (phoneTime) {
      lat = phoneLat; lon = phoneLon; ageMs = now - phoneTime; return LOC_PHONE;
    }
  }
  lat = 0.0; lon = 0.0; ageMs = 0;
  return LOC_NONE;
}

const char *locSrcName(uint8_t src) {
  if (src == LOC_GPS)   return "GPS";
  if (src == LOC_PHONE) return "PHONE";
  return "NONE";
}

// Reject obviously bad input from the portal.
bool locValid(double lat, double lon) {
  if (lat < -90.0 || lat > 90.0)   return false;
  if (lon < -180.0 || lon > 180.0) return false;
  if (lat == 0.0 && lon == 0.0)    return false;   // null island = not a fix
  return true;
}

// ===========================================================================
//  OLED  (SSD1306 via Adafruit)  -  5 rows, ASCII only.
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
//  CAPTIVE PORTAL
// ===========================================================================
#if ENABLE_PORTAL
WebServer server(80);
DNSServer dns;
IPAddress apIP(192, 168, 4, 1);
bool portalOk = false;

const char PORTAL_HTML[] PROGMEM = R"HTML(<!DOCTYPE html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SAR Rescue Portal</title><style>
*{box-sizing:border-box}
body{margin:0;padding:14px;font:15px system-ui,-apple-system,sans-serif;background:#111;color:#eee}
h1{font-size:19px;margin:0 0 2px}
.sub{color:#888;font-size:12px;margin-bottom:14px}
.card{background:#1c1c1e;border:1px solid #2c2c2e;border-radius:10px;padding:12px;margin-bottom:12px}
.k{color:#8a8a8e;font-size:11px;letter-spacing:.06em;text-transform:uppercase}
.v{font-size:18px;font-family:ui-monospace,Menlo,monospace;margin:4px 0}
button{width:100%;padding:13px;border:0;border-radius:8px;font-size:16px;font-weight:600;margin-top:8px}
.p{background:#ff6a00;color:#fff}.s{background:#2c2c2e;color:#eee}
input{width:100%;padding:11px;margin:5px 0;border-radius:8px;border:1px solid #3a3a3c;background:#000;color:#eee;font-size:15px}
#m{font-size:13px;color:#ffb37a;min-height:16px;margin-top:8px;line-height:1.4}
.n{font-family:ui-monospace,Menlo,monospace;font-size:13px;color:#bbb;line-height:1.6}
.hint{color:#6a6a6e;font-size:11px;margin-top:6px;line-height:1.4}
</style></head><body>
<h1>SAR Rescue Portal</h1>
<div class="sub" id="hdr">connecting...</div>

<div class="card">
<div class="k">This node's position</div>
<div class="v" id="pos">--</div>
<div class="k" id="psrc">no fix yet</div>
</div>

<div class="card">
<div class="k">Share your phone's location</div>
<button class="p" onclick="share()">Use Phone GPS</button>
<div id="m"></div>
<div class="k" style="margin-top:14px">Or enter coordinates manually</div>
<input id="la" placeholder="latitude  e.g. 23.797810" inputmode="decimal">
<input id="lo" placeholder="longitude e.g. 90.449720" inputmode="decimal">
<button class="s" onclick="manual()">Send Coordinates</button>
<div class="hint">Phone browsers only allow GPS access over HTTPS. If the
button above is refused, copy your coordinates from a maps app and paste
them here - this always works.</div>
</div>

<div class="card"><div class="k">Mesh nodes</div><div class="n" id="nb">--</div></div>

<script>
function msg(t){document.getElementById('m').textContent=t}
function send(a,b,c){
 fetch('/api/loc?lat='+a+'&lon='+b+'&acc='+(c||0))
 .then(r=>r.text()).then(t=>{msg(t);tick()})
 .catch(e=>msg('Send failed - still connected to the node?'));
}
function share(){
 if(!navigator.geolocation){msg('This browser has no geolocation API. Use manual entry below.');return}
 msg('Requesting location...');
 navigator.geolocation.getCurrentPosition(
  function(p){send(p.coords.latitude.toFixed(6),p.coords.longitude.toFixed(6),Math.round(p.coords.accuracy))},
  function(e){msg('Browser refused: '+e.message+' - use manual entry below.')},
  {enableHighAccuracy:true,timeout:10000,maximumAge:0});
}
function manual(){
 var a=parseFloat(document.getElementById('la').value);
 var b=parseFloat(document.getElementById('lo').value);
 if(isNaN(a)||isNaN(b)){msg('Enter both latitude and longitude.');return}
 send(a.toFixed(6),b.toFixed(6),0);
}
function tick(){
 fetch('/api/status').then(r=>r.json()).then(function(d){
  document.getElementById('hdr').textContent='Node '+d.id+' | LoRa '+(d.lora?'OK':'FAIL')+' | heap '+d.heap+' | up '+d.up+'s';
  document.getElementById('pos').textContent=d.src?(d.lat.toFixed(6)+', '+d.lon.toFixed(6)):'no location yet';
  document.getElementById('psrc').textContent=d.src
   ?((d.src==1?'GPS module ('+d.sats+' sats)':'phone')+' - '+d.age+'s ago')
   :'waiting for a GPS fix or a phone position';
  document.getElementById('nb').innerHTML=d.neigh?d.neigh:'(none heard yet)';
 }).catch(function(e){});
}
setInterval(tick,6000);tick();
</script></body></html>)HTML";

void handlePortal() {
  server.send_P(200, "text/html", PORTAL_HTML);
}

void handleLoc() {
  if (!server.hasArg("lat") || !server.hasArg("lon")) {
    server.send(400, "text/plain", "missing lat/lon");
    return;
  }
  double la = server.arg("lat").toDouble();
  double lo = server.arg("lon").toDouble();
  if (!locValid(la, lo)) {
    server.send(400, "text/plain", "Coordinates out of range - check and retry.");
    return;
  }
  phoneLat = la;
  phoneLon = lo;
  phoneAcc = server.hasArg("acc") ? server.arg("acc").toFloat() : 0.0f;
  phoneValid = true;
  phoneTime = millis();
  phoneUpdates++;

  Serial.printf("[portal] phone position %.6f,%.6f (acc %.0fm)\n", la, lo, (double)phoneAcc);
  server.send(200, "text/plain", "Location received - thank you.");
}

void handleStatus() {
  double lat = 0, lon = 0;
  uint32_t ageMs = 0;
  uint8_t src = locBest(lat, lon, ageMs);

  static char nb[240];
  nb[0] = '\0';
  size_t used = 0;
  for (uint8_t i = 0; i < MAX_NEIGHBORS; i++) {
    if (!neighbors[i].used || !neighbors[i].active) continue;
    char row[80];
    if (neighbors[i].hasLoc)
      snprintf(row, sizeof(row), "%s %ddBm %.5f,%.5f (%s)<br>",
               neighbors[i].id, neighbors[i].rssi,
               neighbors[i].lat, neighbors[i].lon, locSrcName(neighbors[i].locSrc));
    else
      snprintf(row, sizeof(row), "%s %ddBm no fix<br>", neighbors[i].id, neighbors[i].rssi);
    size_t rl = strlen(row);
    if (used + rl + 1 >= sizeof(nb)) break;
    memcpy(nb + used, row, rl);
    used += rl;
    nb[used] = '\0';
  }

  static char json[520];
  snprintf(json, sizeof(json),
           "{\"id\":\"%s\",\"lora\":%d,\"lat\":%.6f,\"lon\":%.6f,\"src\":%u,"
           "\"age\":%lu,\"sats\":%d,\"heap\":%lu,\"up\":%lu,\"neigh\":\"%s\"}",
           MY_ID, radioOk ? 1 : 0, lat, lon, (unsigned)src,
           (unsigned long)(ageMs / 1000UL), gpsSats,
           (unsigned long)ESP.getFreeHeap(),
           (unsigned long)(millis() / 1000UL), nb);
  server.send(200, "application/json", json);
}

void portalBegin() {
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(apIP, apIP, IPAddress(255, 255, 255, 0));
  portalOk = WiFi.softAP(AP_SSID, AP_PASSWORD, AP_CHANNEL, 0, AP_MAX_CLIENTS);
  if (!portalOk) { Serial.println("[portal] softAP FAILED"); return; }

  // Answer every DNS query with our own IP - that is what makes the phone
  // believe it has hit a captive portal and pop the browser open.
  dns.start(53, "*", apIP);

  server.on("/", handlePortal);
  server.on("/api/loc", handleLoc);
  server.on("/api/status", handleStatus);

  // Connectivity-check URLs the phones probe. Returning our page (rather than
  // the 204 / "Success" they expect) is what triggers the portal popup.
  server.on("/generate_204", handlePortal);              // Android
  server.on("/gen_204", handlePortal);                   // Android
  server.on("/hotspot-detect.html", handlePortal);       // iOS / macOS
  server.on("/library/test/success.html", handlePortal); // iOS
  server.on("/ncsi.txt", handlePortal);                  // Windows
  server.on("/connecttest.txt", handlePortal);           // Windows
  server.on("/fwlink", handlePortal);                    // Windows
  server.onNotFound(handlePortal);

  server.begin();
  Serial.printf("[portal] AP \"%s\" up at %s\n", AP_SSID, apIP.toString().c_str());
}

void portalService() {
  if (!portalOk) return;
  dns.processNextRequest();
  server.handleClient();
}
#endif  // ENABLE_PORTAL

// ===========================================================================
// ===========================================================================
//  WATCHDOG
//
//  IMPORTANT: the Arduino ESP32 core ALREADY starts the task watchdog before
//  setup() runs, with its own default timeout. Calling esp_task_wdt_init()
//  therefore fails with "TWDT already initialized" and our WDT_TIMEOUT_S is
//  silently ignored - the earlier build printed exactly that error and nobody
//  noticed. Reconfigure first, fall back to init, and print what we actually
//  ended up with so it can never be silently wrong again.
// ===========================================================================
void wdtBegin() {
  esp_err_t e;
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  esp_task_wdt_config_t cfg;
  cfg.timeout_ms     = WDT_TIMEOUT_S * 1000;
  cfg.idle_core_mask = 0;
  cfg.trigger_panic  = true;
  e = esp_task_wdt_reconfigure(&cfg);          // the TWDT is already running
  if (e != ESP_OK) e = esp_task_wdt_init(&cfg);
#else
  e = esp_task_wdt_init(WDT_TIMEOUT_S, true);
#endif
  esp_task_wdt_add(NULL);
  Serial.printf("[wdt] task watchdog set to %us (%s)\n",
                (unsigned)WDT_TIMEOUT_S, (e == ESP_OK) ? "ok" : "NOT APPLIED");
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

  if (bootBeacons > 0) {
    bootBeacons--;                       // fast rediscovery right after a boot
    hbTimer.setPeriod(3000UL);
  } else {
    hbTimer.setPeriod(HB_INTERVAL_MS + (uint32_t)random(0, HB_JITTER_MS));
  }
}

// GPS payload:  lat,lon,sats,source,age_seconds
void sendLocation() {
  gpsTimer.setPeriod(GPS_INTERVAL_MS + (uint32_t)random(0, GPS_JITTER_MS));

  double lat, lon;
  uint32_t ageMs;
  uint8_t src = locBest(lat, lon, ageMs);
  if (src == LOC_NONE) return;              // nothing worth sharing yet

  char payload[64];
  snprintf(payload, sizeof(payload), "%.6f,%.6f,%d,%u,%lu",
           lat, lon, gpsSats, (unsigned)src, (unsigned long)(ageMs / 1000UL));

  char frame[MAX_PACKET_LEN];
  if (pktBuild(frame, sizeof(frame), "GPS", MY_ID, "*", nextMsgId(), 0, payload))
    radioEnqueue(frame);
}

// Advertise everything we can currently reach:  dest,hops,via;dest,hops,via;
// The `via` field is what lets a receiver apply split horizon - see the
// ROUTING TABLE section above.
void sendRoutes() {
  rtTimer.setPeriod(RT_INTERVAL_MS + (uint32_t)random(0, RT_JITTER_MS));

  char payload[MAX_PAYLOAD_LEN];
  payload[0] = '\0';
  size_t used = 0;
  for (uint8_t i = 0; i < MAX_ROUTES; i++) {
    if (!routes[i].used || !routes[i].valid) continue;
    char e[24];
    int n = snprintf(e, sizeof(e), "%s,%u,%s;",
                     routes[i].dest, (unsigned)routes[i].hops, routes[i].nextHop);
    if (n < 0 || used + (size_t)n + 1 >= sizeof(payload)) break;
    memcpy(payload + used, e, (size_t)n);
    used += (size_t)n;
    payload[used] = '\0';
  }

  // An empty advert is still worth sending - it announces we are alive and
  // gives our neighbours a 1-hop route to us.
  char frame[MAX_PACKET_LEN];
  if (pktBuild(frame, sizeof(frame), "RT", MY_ID, "*", nextMsgId(), 0, payload))
    radioEnqueue(frame);
}

// Send an application message to `dest`, possibly several hops away.
void sendData(const char *dest, const char *text) {
  if (strcmp(dest, MY_ID) == 0) {
    Serial.println("[data] that destination is this node");
    return;
  }
  const char *hop = routeBestHop(dest);
  if (!hop) {
    Serial.printf("[data] NO ROUTE to %s - nothing sent (press 'r' to see the table)\n", dest);
    return;
  }
  char frame[MAX_PACKET_LEN];
  if (pktBuild(frame, sizeof(frame), "DATA", MY_ID, dest,
               nextMsgId(), MAX_HOPS, text)) {
    radioEnqueue(frame);
    statDataTx++;
    Serial.printf("[data] TX -> %s via %s : %s\n", dest, hop, text);
  }
}

void sendTestTo(const char *dest) {
  static uint16_t seq = 1;
  char text[48];
  snprintf(text, sizeof(text), "ping #%u from %s", (unsigned)seq++, MY_ID);
  strncpy(autoTarget, dest, sizeof(autoTarget) - 1);
  autoTarget[sizeof(autoTarget) - 1] = '\0';
  sendData(dest, text);
}

void printRoutes() {
  Serial.println("\n---- ROUTING TABLE -------------------------------------");
  Serial.println("DEST  VIA   HOPS  RSSI    AGE(s)  STATE");
  bool any = false;
  for (uint8_t i = 0; i < MAX_ROUTES; i++) {
    if (!routes[i].used) continue;
    any = true;
    Serial.printf("%-5s %-5s %-5u %-7d %-7lu %s\n",
                  routes[i].dest, routes[i].nextHop, (unsigned)routes[i].hops,
                  routes[i].rssi,
                  (unsigned long)((millis() - routes[i].lastUpdated) / 1000UL),
                  routes[i].valid ? "VALID" : "invalid (self-healing)");
  }
  if (!any) Serial.println("(no routes learned yet)");
  Serial.printf("forwarded=%lu  sent=%lu  delivered-to-me=%lu\n",
                (unsigned long)statFwd, (unsigned long)statDataTx,
                (unsigned long)statDataRx);
  Serial.println("--------------------------------------------------------\n");
}

void handleRx() {
  Packet p;
  if (!radioPoll(p)) return;
  if (strcmp(p.src, MY_ID) == 0) return;              // our own echo
  if (seenOrAdd(p.src, p.msgId)) return;              // duplicate

  int ev = neighborSeen(p.src, p.rssi, p.snr);
  if      (ev == NB_NEW)         Serial.printf("[mesh] NEW neighbour %s  %d dBm\n", p.src, p.rssi);
  else if (ev == NB_RECONNECTED) Serial.printf("[mesh] RECONNECTED %s  %d dBm\n", p.src, p.rssi);
  else if (ev == NB_FULL)        Serial.println("[mesh] neighbour table FULL");

  // Anything heard directly is one hop away, whatever the packet type was.
  int rev = routeUpdate(p.src, p.src, 1, p.rssi);
  if      (rev == RT_NEW)       Serial.printf("[route] NEW       %s via %s 1h\n", p.src, p.src);
  else if (rev == RT_RECOVERED) Serial.printf("[route] RECOVERED %s via %s 1h  <<< SELF-HEALED\n", p.src, p.src);
  else if (rev == RT_BETTER)    Serial.printf("[route] BETTER    %s via %s 1h\n", p.src, p.src);

  if (strcmp(p.type, "HB") == 0) {
    unsigned long up = 0, hp = 0;
    unsigned      fw = 0;
    if (sscanf(p.payload, "%lu,%lu,%u", &up, &hp, &fw) >= 2)
      neighborSetStats(p.src, (uint32_t)up, (uint32_t)hp);

  } else if (strcmp(p.type, "RT") == 0) {
    // Everything the advertiser can reach becomes reachable through it.
    char buf[MAX_PAYLOAD_LEN];
    strncpy(buf, p.payload, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';

    char *tok = strtok(buf, ";");
    while (tok) {
      char d[4], v[4];
      unsigned h = 0;
      if (routeParseEntry(tok, d, sizeof(d), &h, v, sizeof(v))) {
        // SPLIT HORIZON: if the advertiser reaches d through US, that path
        // only exists because of us. Accepting it back is exactly how hop
        // counts climb to infinity, so drop it.
        if (strcmp(v, MY_ID) != 0 && strcmp(d, MY_ID) != 0) {
          int e = routeUpdate(d, p.src, (uint8_t)(h + 1), p.rssi);
          if      (e == RT_NEW)       Serial.printf("[route] NEW       %s via %s %uh\n", d, p.src, h + 1);
          else if (e == RT_BETTER)    Serial.printf("[route] BETTER    %s via %s %uh\n", d, p.src, h + 1);
          else if (e == RT_RECOVERED) Serial.printf("[route] RECOVERED %s via %s %uh  <<< SELF-HEALED\n", d, p.src, h + 1);
          else if (e == RT_FULL)      Serial.println("[route] table FULL");
        }
      }
      tok = strtok(NULL, ";");
    }

  } else if (strcmp(p.type, "DATA") == 0) {
    if (strcmp(p.dest, MY_ID) == 0) {
      // Arrived. MAX_HOPS was the starting TTL, so this is how far it came.
      unsigned hops = (unsigned)(MAX_HOPS - p.ttl);
      statDataRx++;
      snprintf(lastMsgFrom, sizeof(lastMsgFrom), "%s", p.src);
      snprintf(lastMsgText, sizeof(lastMsgText), "%s", p.payload);
      lastMsgTime = millis();
      Serial.printf("\n>>> MESSAGE from %s after %u hop(s): %s\n\n",
                    p.src, hops, p.payload);

    } else if (p.ttl > 0) {
      const char *hop = routeBestHop(p.dest);
      if (!hop) {
        // Not a silent black hole - say so, because this is what a broken
        // mesh looks like and it should be visible during a demo.
        Serial.printf("[fwd] DROP %s->%s : no route from here\n", p.src, p.dest);
      } else {
        char frame[MAX_PACKET_LEN];
        if (pktBuild(frame, sizeof(frame), "DATA", p.src, p.dest,
                     p.msgId, (uint8_t)(p.ttl - 1), p.payload)) {
          radioEnqueue(frame);
          statFwd++;
          Serial.printf("[fwd] %s->%s via %s (ttl %u)\n",
                        p.src, p.dest, hop, (unsigned)(p.ttl - 1));
        }
      }
    } else {
      Serial.printf("[fwd] DROP %s->%s : TTL expired\n", p.src, p.dest);
    }

  } else if (strcmp(p.type, "GPS") == 0) {
    double la = 0, lo = 0;
    int sats = 0;
    unsigned src = 0;
    unsigned long age = 0;
    if (sscanf(p.payload, "%lf,%lf,%d,%u,%lu", &la, &lo, &sats, &src, &age) >= 2) {
      if (locValid(la, lo)) {
        neighborSetLoc(p.src, la, lo, (uint8_t)src);
        Serial.printf("[loc] %s is at %.6f,%.6f via %s (%lus old)\n",
                      p.src, la, lo, locSrcName((uint8_t)src), age);
      }
    }
  }

  Serial.printf("[rx] %s from %s id=%u ttl=%u rssi=%d snr=%.1f : %s\n",
                p.type, p.src, (unsigned)p.msgId, (unsigned)p.ttl,
                p.rssi, (double)p.snr, p.payload);
}

void drawPage0() {
  char l0[26], l1[26], l2[26], l3[26], l4[26], list[20];
  neighborActiveList(list, sizeof(list));

  double lat, lon;
  uint32_t ageMs;
  uint8_t src = locBest(lat, lon, ageMs);

#if ENABLE_PORTAL
  snprintf(l0, sizeof(l0), "NODE %s %s wifi%d",
           MY_ID, radioOk ? "" : "!RF", (int)WiFi.softAPgetStationNum());
#else
  snprintf(l0, sizeof(l0), "NODE %s %s", MY_ID, radioOk ? "" : "!RF");
#endif
  snprintf(l1, sizeof(l1), "Conn:%s R:%u", list, (unsigned)routeValidCount());

  if (src == LOC_NONE) {
    snprintf(l2, sizeof(l2), "no location yet");
    snprintf(l3, sizeof(l3), "GPS sats:%d nmea:%lu", gpsSats, (unsigned long)gpsSentences);
  } else {
    snprintf(l2, sizeof(l2), "%.5f,%.5f", lat, lon);
    snprintf(l3, sizeof(l3), "%s s%d age%lus",
             locSrcName(src), gpsSats, (unsigned long)(ageMs / 1000UL));
  }
  snprintf(l4, sizeof(l4), "heap %lu up%lus",
           (unsigned long)ESP.getFreeHeap(),
           (unsigned long)(millis() / 1000UL));

  oledClear();
  oledLine(0, l0); oledLine(1, l1); oledLine(2, l2);
  oledLine(3, l3); oledLine(4, l4);
  oledShow();
}

// Page 1: the routing table - what this node can reach and through whom.
void drawPage1() {
  char l[5][26];
  snprintf(l[0], sizeof(l[0]), "-- ROUTES (%u) --", (unsigned)routeValidCount());

  uint8_t row = 1;
  for (uint8_t i = 0; i < MAX_ROUTES && row < 5; i++) {
    if (!routes[i].used) continue;
    snprintf(l[row], sizeof(l[row]), "%s via %s %uh%s",
             routes[i].dest, routes[i].nextHop, (unsigned)routes[i].hops,
             routes[i].valid ? "" : " X");
    row++;
  }
  if (row == 1) { snprintf(l[1], sizeof(l[1]), "no routes yet"); row = 2; }
  while (row < 5) { l[row][0] = '\0'; row++; }

  oledClear();
  for (uint8_t i = 0; i < 5; i++) oledLine(i, l[i]);
  oledShow();
}

// Page 2: where the other nodes are, as reported over LoRa.
void drawPage2() {
  char l[5][26];
  snprintf(l[0], sizeof(l[0]), "-- NODE POSITIONS --");

  uint8_t row = 1;
  for (uint8_t i = 0; i < MAX_NEIGHBORS && row < 5; i++) {
    if (!neighbors[i].used) continue;
    if (neighbors[i].hasLoc)
      snprintf(l[row], sizeof(l[row]), "%s %.4f,%.4f",
               neighbors[i].id, neighbors[i].lat, neighbors[i].lon);
    else
      snprintf(l[row], sizeof(l[row]), "%s no fix", neighbors[i].id);
    row++;
  }
  if (row == 1) { snprintf(l[1], sizeof(l[1]), "no peers heard"); row = 2; }
  while (row < 5) { l[row][0] = '\0'; row++; }

  oledClear();
  for (uint8_t i = 0; i < 5; i++) oledLine(i, l[i]);
  oledShow();
}

// The display cycles through the pages every UI_PAGE_MS; 'p' skips ahead.
void drawUI() {
  if      (uiPage == 1) drawPage1();
  else if (uiPage == 2) drawPage2();
  else                  drawPage0();
}

void printNeighbours() {
  Serial.println("\n---- NEIGHBOURS ----------------------------------------");
  Serial.println("ID   RSSI   SNR    AGE(s)  POSITION                  SRC");
  bool any = false;
  for (uint8_t i = 0; i < MAX_NEIGHBORS; i++) {
    if (!neighbors[i].used) continue;
    any = true;
    char pos[32];
    if (neighbors[i].hasLoc)
      snprintf(pos, sizeof(pos), "%.5f,%.5f", neighbors[i].lat, neighbors[i].lon);
    else
      snprintf(pos, sizeof(pos), "no fix");
    Serial.printf("%-4s %-6d %-6.1f %-7lu %-25s %-6s %s\n",
                  neighbors[i].id, neighbors[i].rssi, (double)neighbors[i].snr,
                  (unsigned long)((millis() - neighbors[i].lastSeen) / 1000UL),
                  pos, locSrcName(neighbors[i].locSrc),
                  neighbors[i].active ? "ACTIVE" : "lost");
  }
  if (!any) Serial.println("(none discovered yet)");
  Serial.println("--------------------------------------------------------\n");
}

void printLocation() {
  double lat, lon;
  uint32_t ageMs;
  uint8_t src = locBest(lat, lon, ageMs);

  Serial.println("\n---- LOCATION ------------------------------------------");
  Serial.printf("  in use   : %s", locSrcName(src));
  if (src != LOC_NONE) Serial.printf("  %.6f, %.6f  (%lus old)",
                                     lat, lon, (unsigned long)(ageMs / 1000UL));
  Serial.println();
  Serial.printf("  preference: %s first\n",
                LOCATION_PREFER_PHONE ? "PHONE" : "GPS module");
  Serial.printf("  GPS module: %s  sats=%d  nmea lines=%lu",
                gpsHasFix ? "FIX" : "no fix", gpsSats, (unsigned long)gpsSentences);
  if (gpsFixTime) Serial.printf("  last fix %lus ago",
                                (unsigned long)((millis() - gpsFixTime) / 1000UL));
  Serial.println();
  if (gpsSentences == 0)
    Serial.println("             ^ no NMEA at all - check GPS TX -> GPIO16 and 9600 baud");
  Serial.printf("  phone     : %s", phoneValid ? "have position" : "none received");
  if (phoneValid) Serial.printf("  %.6f, %.6f  acc %.0fm  %lus ago  (%lu updates)",
                                phoneLat, phoneLon, (double)phoneAcc,
                                (unsigned long)((millis() - phoneTime) / 1000UL),
                                (unsigned long)phoneUpdates);
  Serial.println();
  Serial.println("--------------------------------------------------------\n");
}

void printStats() {
  Serial.printf("[stat] up=%lus heap=%lu neigh=%u tx=%lu rx=%lu bad=%lu drop=%lu q=%u",
                (unsigned long)(millis() / 1000UL),
                (unsigned long)ESP.getFreeHeap(),
                (unsigned)neighborActiveCount(),
                (unsigned long)statTx, (unsigned long)statRx,
                (unsigned long)statBad, (unsigned long)statDrop,
                (unsigned)txCount);
#if ENABLE_PORTAL
  Serial.printf(" wifi=%d", (int)WiFi.softAPgetStationNum());
#endif
  double lat, lon; uint32_t ageMs;
  Serial.printf(" loc=%s minheap=%lu stack=%lu txstuck=%lu rst=%s\n",
                locSrcName(locBest(lat, lon, ageMs)),
                (unsigned long)esp_get_minimum_free_heap_size(),
                (unsigned long)uxTaskGetStackHighWaterMark(NULL),
                (unsigned long)statTxStuck,
                resetReasonShort());
}

void handleSerial() {
  if (!Serial.available()) return;
  int c = Serial.read();

  if (c == 'n') {
    printNeighbours();

  } else if (c == 's') {
    printStats();

  } else if (c == 'g') {
    printLocation();

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

  } else if (c == 'r') {
    printRoutes();

  } else if (c == 'a' || c == 'b' || c == 'c') {
    char dest[2] = { (char)(c - 32), '\0' };      // 'a' -> "A"
    sendTestTo(dest);

  } else if (c == 't') {
    autoData = !autoData;
    if (autoData && !autoTarget[0]) {
      // no target chosen yet - use the first destination we know a way to
      for (uint8_t i = 0; i < MAX_ROUTES; i++) {
        if (routes[i].used && routes[i].valid) {
          strncpy(autoTarget, routes[i].dest, sizeof(autoTarget) - 1);
          autoTarget[sizeof(autoTarget) - 1] = '\0';
          break;
        }
      }
    }
    if (autoData && autoTarget[0]) {
      autoTimer.begin(AUTO_DATA_MS, 1000UL);
      Serial.printf("[auto] repeat send to %s every %lus - press 't' to stop\n",
                    autoTarget, (unsigned long)(AUTO_DATA_MS / 1000UL));
    } else {
      autoData = false;
      Serial.println("[auto] off (pick a target first with a/b/c)");
    }

  } else if (c == 'p') {
    uiPage = (uint8_t)((uiPage + 1) % UI_PAGES);
    pageTimer.begin(UI_PAGE_MS, UI_PAGE_MS);
    drawUI();
    Serial.printf("[ui] page %u\n", (unsigned)uiPage);

  } else if (c == 'h' || c == '?') {
    Serial.println("commands: n=neighbours r=routes g=GPS s=stats  a|b|c=send msg to that node");
    Serial.println("          t=toggle repeat send  p=next OLED page  x=bad frame  h=help");
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
  routeInit();

  // STEP 1: display
  Wire.begin(I2C_SDA, I2C_SCL);
  oledOk = display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  if (!oledOk) oledOk = display.begin(SSD1306_SWITCHCAPVCC, 0x3D);
  if (oledOk) {
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
  } else {
    Serial.println("[oled] init FAILED - check SDA21 / SCL22");
  }
  oledBanner("Booting...", "Node " MY_ID);

  Serial.printf("\n[boot] Node %s fw v%u  heap=%lu\n",
                MY_ID, (unsigned)FW_VERSION, (unsigned long)ESP.getFreeHeap());
  Serial.printf("[boot] last reset: %s\n", resetReasonName());
  // Print the reason for the LAST reset in a box that cannot be scrolled past.
  // If a node is restarting by itself, this single line identifies the cause.
  Serial.println("\n############################################################");
  Serial.printf ("#  WHY DID THIS NODE LAST RESTART?\n");
  Serial.printf ("#     %s\n", resetReasonName());
  Serial.println("############################################################\n");

  // STEP 2: GPS serial
  Serial2.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
  Serial.printf("[gps] Serial2 %d baud on RX%d/TX%d\n", GPS_BAUD, GPS_RX_PIN, GPS_TX_PIN);

  // STEP 3: radio
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

  // STEP 4: Wi-Fi captive portal
#if ENABLE_PORTAL
  portalBegin();
  oledBanner("WiFi AP up", AP_SSID);
#endif

  {
    char rl[24];
    snprintf(rl, sizeof(rl), "rst:%s", resetReasonShort());
    oledBanner("Last restart was", rl);
  }

  wdtBegin();

  hbTimer.begin(3000UL, 500UL + (uint32_t)random(0, 1200));   // fast first beacons
  gpsTimer.begin(GPS_INTERVAL_MS, 4000UL + (uint32_t)random(0, GPS_JITTER_MS));
  rtTimer.begin(RT_INTERVAL_MS, 2000UL + (uint32_t)random(0, RT_JITTER_MS));
  pageTimer.begin(UI_PAGE_MS, UI_PAGE_MS);
  autoTimer.begin(AUTO_DATA_MS, AUTO_DATA_MS);
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

  // 1. drain the GPS serial buffer (never blocks)
  gpsService();

  // 2. serve the captive portal (both calls are non-blocking)
#if ENABLE_PORTAL
  portalService();
#endif

  // 3. receive LoRa
  handleRx();

  // 4. age out silent neighbours
  char lost[4];
  while (neighborPrune(lost, sizeof(lost)))
    Serial.printf("[mesh] LOST %s (no packet for %lus)\n",
                  lost, (unsigned long)(NEIGHBOR_TIMEOUT_MS / 1000UL));

  // 4b. invalidate routes whose advertiser has gone quiet - this is the
  //     self-healing trigger, and it is what stops traffic vanishing into a
  //     relay that is no longer there
  char deadDest[4];
  while (routeExpire(deadDest, sizeof(deadDest)))
    Serial.printf("[route] LOST %s - no advert for %lus, invalidating  <<< SELF-HEALING\n",
                  deadDest, (unsigned long)(ROUTE_TIMEOUT_MS / 1000UL));

  // 5. periodic broadcasts
  if (hbTimer.due())  sendHeartbeat();
  if (gpsTimer.due()) sendLocation();
  if (rtTimer.due())  sendRoutes();
  if (autoData && autoTarget[0] && autoTimer.due()) sendTestTo(autoTarget);

  // 6. transmit pump
  radioService();

  // 7. display + periodic statistics
  if (pageTimer.due()) uiPage = (uint8_t)((uiPage + 1) % UI_PAGES);
  if (uiTimer.due())   drawUI();
  if (statTimer.due()) printStats();

  // 8. recover a radio that failed at boot
  if (!radioOk && retryTimer.due()) {
    Serial.println("[radio] retrying init...");
    if (radioBegin()) Serial.println("[radio] recovered");
  }

  // 9. serial commands
  handleSerial();
}
