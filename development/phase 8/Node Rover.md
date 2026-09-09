// ===========================================================================
//  PHASE 8  -  AUTONOMOUS RESCUE ROVER  -  NODE R (Rover)
//  ESP32 + LoRa SX1278 (433 MHz) + 0.96" SSD1306 OLED + NEO-M8N GPS
//  + L298N/TB6612 motor driver (2WD/4WD) + HC-SR04 ultrasonic + SOS button
//
//  Complete standalone sketch - paste the whole file into the Arduino IDE.
//
//  Libraries: LoRa (Sandeep Mistry), Adafruit GFX, Adafruit SSD1306
//  Board:     ESP32 Dev Module
//
//  WHAT THIS IS - a fourth mesh node, identical to A/B/C in every way that
//  matters to the mesh (same packet format, same radio layer, same routing,
//  same self-healing, same GPS/SOS), PLUS it drives. It is not a separate
//  "rover protocol" bolted on - it is Node C's firmware with the Wi-Fi
//  portal removed (the Pi dashboard is the remote control, not a phone on
//  the rover itself) and a motor + ultrasonic layer added.
//
//  THREE MODES (default on boot: MANUAL - it must not drive away on its own
//  the moment it is powered on):
//    MANUAL  drive commands come from the Pi dashboard (or serial, on the
//            bench) as CMD:FWD/BACK/LEFT/RIGHT/STOP. Every drive command is
//            a bounded PULSE (MANUAL_PULSE_MS) - if the dashboard button is
//            released, or the link drops, the rover coasts to a stop within
//            one pulse on its own. Nothing here can make it "run away".
//    AUTO    non-blocking bump-turn: drive forward; if the ultrasonic sensor
//            reports something closer than AUTO_OBSTACLE_CM, back up, turn
//            a random direction, resume.
//    RELAY   motors held off, obstacle scanning off. The rover is driven
//            into position in MANUAL, then switched to RELAY to sit still
//            and be a pure LoRa relay - the mesh's forwarding logic already
//            does the rest, because every mesh node forwards regardless of
//            mode; RELAY just stops this one from also being a moving robot.
//  Any received command, mode switch, or the SOS button is an immediate
//  motor cut - see roverEmergencyStop().
//
//  WHY NO WI-FI PORTAL HERE - three radios (LoRa RX, an AP, and now two
//  motors + an ultrasonic sensor all sharing one core) is more moving parts
//  than this node needs. Every drive/mode command reaches the rover exactly
//  like any other command already reaches a node in this mesh: as a routed
//  `CMD:` packet (introduced in Phase 5 for WHERE/PING/SOS/SOSCLR from the
//  Pi), forwarded by A/B/C's existing generic "not for me, route it on"
//  logic - so A/B/C did not need to learn anything new to relay a drive
//  command to the rover. Only the rover's own new verbs are new here.
//
//  ROVER: TELEMETRY - broadcast periodically (mode,obstacle_cm,battery_pct),
//  forwarded hop by hop the same way SOS/RPT are (A/B/C were given a small,
//  mechanical forward-only branch for it - see their Phase 8 header note).
//  Position is NOT duplicated into this packet - the rover already sends a
//  normal `GPS:` broadcast like every other node, and the Pi joins the two
//  by node id.
//
//  HARDWARE - pins not already used by A/B/C's LoRa/OLED/GPS/SOS-button:
//    Motors (H-bridge, e.g. L298N):
//      LEFT_IN1  27    LEFT_IN2  25    LEFT_EN  (PWM) 13
//      RIGHT_IN1 33    RIGHT_IN2 32    RIGHT_EN (PWM)  2
//    Ultrasonic (HC-SR04):
//      TRIG 15    ECHO 35   <-- ECHO is 5V logic out of the HC-SR04 and the
//                               ESP32 is NOT 5V tolerant. USE A VOLTAGE
//                               DIVIDER (e.g. 1k/2k) ON ECHO or you will
//                               damage the pin. TRIG is fine direct (it's an
//                               ESP32 output).
//    Battery sense (optional): ADC1 pin 36 (VP) via a voltage divider sized
//      for YOUR pack. BATTERY_ADC_VMIN/VMAX below are a starting point for a
//      2S Li-ion motor pack (6.4-8.4V) - measure your actual divider and
//      correct them, or the reported percentage will be fiction.
//
//  MANDATORY, from the Phase 6/7 hardware notes, doubly true with motors:
//    - SEPARATE BATTERY FOR MOTORS vs LOGIC, COMMON GROUND. Motor stall
//      current through a shared supply browns out the ESP32 - it will look
//      like a random reset mid-drive, not a motor problem.
//    - Flyback diodes / decoupling caps on the H-bridge if your board
//      doesn't already have them (most L298N breakouts do).
//    - First power-up: wheels OFF THE GROUND. Confirm FWD/BACK/LEFT/RIGHT
//      each move the correct wheels the correct way over serial before the
//      rover ever touches the floor.
//
//  Serial (all of Node C's commands, PLUS):
//    m           cycle mode MANUAL -> AUTO -> RELAY -> MANUAL
//    i k j l o   drive: forward / back / left / right / stop (MANUAL only,
//                same bounded pulse as a dashboard command)
//    u           print the current ultrasonic reading
//  Everything else (n r g s a|b|c t p S C 1-4 5-8 v N R T h) is unchanged.
// ===========================================================================

#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <esp_task_wdt.h>
#include <esp_system.h>

#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT  64
#define OLED_ADDR    0x3C

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// ------------------------------- identity ---------------------------------
#define MY_ID          "R"
#define FW_VERSION      8
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

#define PIN_SOS_BUTTON  4    // also doubles as a physical motor E-STOP here
#define PIN_ENTROPY    34    // ADC1, input-only, floats -> good random seed

#define GPS_RX_PIN     16    // ESP32 RX2  <- GPS TX
#define GPS_TX_PIN     17    // ESP32 TX2  -> GPS RX
#define GPS_BAUD     9600

// ---- motors (H-bridge, e.g. L298N / TB6612) -------------------------------
// EN pins are driven HIGH/LOW as a hard enable, not PWM-speed-controlled -
// one less thing that can silently misbehave on a board whose Arduino core
// version has a different LEDC API. Full speed, direction-only, like the
// plan's "fwd/back/left/right/stop" spec. If you want variable speed later,
// these are already separate pins - add ledcAttach/ledcWrite to them.
#define PIN_LEFT_IN1   27
#define PIN_LEFT_IN2   25
#define PIN_LEFT_EN    13
#define PIN_RIGHT_IN1  33
#define PIN_RIGHT_IN2  32
#define PIN_RIGHT_EN    2    // shares the boot-strapping/onboard-LED pin on
                             // many boards; harmless as an output post-boot,
                             // the LED will just blink with the right motor

// ---- ultrasonic (HC-SR04) --------------------------------------------------
#define PIN_TRIG       15
#define PIN_ECHO       35    // INPUT ONLY pin - and needs a voltage divider,
                             // see the header note above

// ---- battery sense (optional) ---------------------------------------------
#define PIN_BATTERY_ADC     36            // ADC1_CH0 / "VP", input-only
#define BATTERY_ADC_VMIN   6.4f           // volts AT THE ADC PIN at "empty" -
#define BATTERY_ADC_VMAX   8.4f           // and "full" - CALIBRATE FOR YOUR
                                          // OWN DIVIDER AND PACK. Defaults
                                          // assume a 2S Li-ion motor pack and
                                          // an unspecified divider ratio -
                                          // treat the % as illustrative until
                                          // you measure it with a multimeter.
#define BATTERY_ADC_DIVIDER 2.0f          // (R1+R2)/R2 of your divider

// ------------------------------- LoRa PHY ---------------------------------
// MUST MATCH A/B/C AND THE PI EXACTLY - see the PHY box printed at boot.
#define LORA_FREQ      433E6
#define LORA_SF        7        // same as A/B/C - see their Phase 7 notes on
                                // why this is not SF9/SF8. Change it here
                                // ONLY together with all three other sketches
                                // and pi/sx1278.py.
#define LORA_BW        125000L
#define LORA_CR        5
#define LORA_TXPOWER   17
#define LORA_SYNCWORD  0x2A
#define LORA_PREAMBLE  8

// ---------------------------- power / heat --------------------------------
#define CPU_MHZ        240             // stock, matching A/B/C

// ------------------------------ location ----------------------------------
// No portal here, so LOC_PHONE never actually gets set - this node's own
// GPS module is its only location source. The fields still exist so this
// file stays a near-identical diff of Node C's, not a rewrite.
#define LOCATION_PREFER_PHONE   1
#define GPS_FRESH_MS        30000UL
#define PHONE_FRESH_MS     300000UL

#define LOC_NONE   0
#define LOC_GPS    1
#define LOC_PHONE  2

// -------------------------------- timing ----------------------------------
#define HB_INTERVAL_MS       15000UL
#define HB_JITTER_MS          3000UL
#define GPS_INTERVAL_MS      45000UL
#define GPS_JITTER_MS         4000UL
#define RT_INTERVAL_MS       30000UL
#define RT_JITTER_MS          4000UL
#define ROUTE_TIMEOUT_MS    120000UL
#define NEIGHBOR_TIMEOUT_MS  75000UL
#define AUTO_DATA_MS         15000UL
#define OLED_REFRESH_MS       1000UL
#define UI_PAGE_MS            4000UL
#define RECONNECT_HB_MS       6000UL
#define RECONNECT_WINDOW_MS  90000UL

#define DUTY_WINDOW_MS       60000UL
#define DUTY_BUDGET_PERMIL      100
#define I2C_HZ              100000L
#define I2C_TIMEOUT_MS           50
#define STAT_LOG_MS          30000UL
#define TX_MIN_GAP_MS          150UL
#define TX_GAP_JITTER_MS       250UL
#define TX_AIRTIME_MARGIN_MS    80UL
#define RADIO_RETRY_MS        5000UL
#define RADIO_WEDGE_MS      120000UL

// --------------------------------- sizes ----------------------------------
#define MAX_NEIGHBORS      8
#define MAX_ROUTES         8
#define MAX_HOPS           4

// -------------------------- SOS / reports --------------------------------
#define SOS_BURST_COUNT       3
#define SOS_BURST_GAP_MS   1200UL
#define SOS_SCREEN_MS     60000UL
#define SOS_BUTTON_HOLD_MS 1500UL
#define SOS_DEBOUNCE_MS      50UL
#define MAX_PACKET_LEN   200
#define MAX_PAYLOAD_LEN  160
#define SEEN_CACHE_SIZE   32
#define TX_QUEUE_DEPTH     6
#define NMEA_BUF_LEN     100
#define UI_PAGES           6    // one more than A/B/C: page 5 is ROVER status
#define WDT_TIMEOUT_S     30
#define SERIAL_BAUD   115200

// ------------------------------- rover -------------------------------------
#define ROVER_MANUAL  0
#define ROVER_AUTO    1
#define ROVER_RELAY   2

#define MANUAL_PULSE_MS       600UL   // one drive command moves it this long,
                                      // then it auto-stops - see the header
                                      // note on why this is the safety model
#define AUTO_OBSTACLE_CM        25    // closer than this -> back off + turn
#define AUTO_BACK_MS            500UL
#define AUTO_TURN_MS_MIN        350UL
#define AUTO_TURN_MS_MAX        700UL
#define ULTRASONIC_INTERVAL_MS  100UL // >= HC-SR04's ~60ms recommended gap
#define ULTRASONIC_ECHO_TIMEOUT_MS 30UL  // no echo by then = "clear", not "unknown forever"
#define ROVER_TELEMETRY_MS   10000UL
#define ROVER_TELEMETRY_JITTER_MS 2000UL

// ===========================================================================
//  NON-BLOCKING TIMER  (replaces every delay() in loop)
// ===========================================================================
struct Interval {
  uint32_t last;
  uint32_t period;

  void begin(uint32_t periodMs, uint32_t firstDelayMs) {
    period = periodMs;
    uint32_t back = (periodMs > firstDelayMs) ? (periodMs - firstDelayMs) : 0;
    last = millis() - back;
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
Interval roverTelemetryTimer;

// ===========================================================================
//  PACKET FRAMING     v<VER>|<TYPE>|<SRC>|<DEST>|<MSGID>|<TTL>|<PAYLOAD>|<CHK>
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

void pktSanitize(char *s) {
  for (char *p = s; *p; ++p)
    if (*p == '|' || *p == '\\' || *p == '\r' || *p == '\n') *p = '/';
}

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

bool pktParse(char *in, Packet &p) {
  size_t len = strlen(in);
  if (len < 12 || len >= MAX_PACKET_LEN) return false;

  char *lastBar = strrchr(in, '|');
  if (!lastBar) return false;
  if (strlen(lastBar + 1) != 2) return false;

  uint8_t want = (uint8_t)strtoul(lastBar + 1, NULL, 16);
  *lastBar = '\0';
  if (pktChecksum(in, strlen(in)) != want) return false;

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
  uint32_t h = 2166136261UL;
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
//  NEIGHBOUR TABLE
// ===========================================================================
struct Neighbor {
  char     id[4];
  int      rssi;
  float    snr;
  uint32_t lastSeen;
  uint32_t uptime;
  uint32_t heap;
  double   lat, lon;
  uint8_t  locSrc;
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

bool anyNeighborMissing() {
  for (uint8_t i = 0; i < MAX_NEIGHBORS; i++)
    if (neighbors[i].used && !neighbors[i].active) return true;
  return false;
}

void seenForget(const char *src) {
  for (uint8_t i = 0; i < SEEN_CACHE_SIZE; i++) {
    if (!seenKeys[i]) continue;
    for (uint16_t m = 1; m <= 128; m++) {
      if (seenKeys[i] == seenKey(src, m)) { seenKeys[i] = 0; break; }
    }
  }
}

// ===========================================================================
//  ROUTING TABLE  -  distance vector with split horizon (see Node C.md for
//  the full design rationale - unchanged here)
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

int routeUpdate(const char *dest, const char *via, uint8_t hops, int rssi) {
  if (!dest || !*dest || !via || !*via) return RT_NONE;
  if (strcmp(dest, MY_ID) == 0) return RT_NONE;
  if (hops == 0 || hops > MAX_HOPS) return RT_NONE;

  uint32_t now = millis();
  int i = routeIndex(dest);

  if (i >= 0) {
    bool wasValid = routes[i].valid;
    bool sameHop  = (strcmp(routes[i].nextHop, via) == 0);

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
//  RADIO LAYER  (byte-for-byte Node C - see its comments for the design
//  rationale behind the async TX queue, the wedge watchdog and the computed
//  airtime wait)
// ===========================================================================
bool     radioOk = false;
char     txQueue[TX_QUEUE_DEPTH][MAX_PACKET_LEN];
uint8_t  txHead = 0, txTail = 0, txCount = 0;
uint32_t txLast = 0;
uint32_t txGap  = TX_MIN_GAP_MS;
bool     txInFlight = false;
uint32_t txStart = 0;
uint32_t txAirtimeMs = 500;
uint16_t msgIdCounter = 0;

uint32_t statTx = 0, statRx = 0, statBad = 0, statDrop = 0;
uint32_t statWedge = 0;
uint32_t statFwd = 0, statDataTx = 0, statDataRx = 0;
uint32_t statTxStuck = 0;

char     lastMsgFrom[4] = "";
char     lastMsgText[40] = "";
uint32_t lastMsgTime = 0;

bool     autoData = false;
char     autoTarget[4] = "";
uint8_t  uiPage = 0;

uint8_t  bootBeacons = 4;
uint32_t missingSinceMs = 0;
uint32_t lastTxOkMs = 0;

uint32_t maxLoopMs = 0;
uint32_t loopStartMs = 0;

bool     verboseRx = false;

bool     radioTest = false;
uint32_t testLast  = 0;

// ---- SOS / rescue-report / team-status state -------------------------------
bool     sosSending    = false;
uint8_t  sosBurstLeft  = 0;
uint16_t sosBurstId    = 0;
char     sosBurstMsg[48] = "";
Interval sosBurstTimer;

bool     sosAlert      = false;
char     sosVictim[4]  = "";
double   sosLat = 0, sosLon = 0;
char     sosText[48]   = "";
uint32_t sosAlertStart = 0;
char     sosAcks[16]   = "";

bool     btnPrev       = true;
uint32_t btnChangeTime = 0;
bool     btnHeldHandled = false;

struct PeerReport {
  char     id[4];
  char     code[14];
  char     status[14];
  uint32_t reportTime;
  uint32_t statusTime;
  bool     used;
};
PeerReport peerRep[MAX_NEIGHBORS + 1];

char myStatus[14] = "AVAILABLE";
char myTeam[8]    = "T1";

int peerRepIndex(const char *id) {
  for (uint8_t i = 0; i < MAX_NEIGHBORS + 1; i++)
    if (peerRep[i].used && strcmp(peerRep[i].id, id) == 0) return (int)i;
  for (uint8_t i = 0; i < MAX_NEIGHBORS + 1; i++)
    if (!peerRep[i].used) {
      strncpy(peerRep[i].id, id, sizeof(peerRep[i].id) - 1);
      peerRep[i].id[sizeof(peerRep[i].id) - 1] = '\0';
      peerRep[i].code[0] = '\0';
      peerRep[i].status[0] = '\0';
      peerRep[i].used = true;
      return (int)i;
    }
  return -1;
}

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
      radioOk = true;
      return true;
    }
    delay(200);                       // setup only - never inside loop()
  }
  radioOk = false;
  return false;
}

uint32_t loraAirtimeMs(uint16_t len) {
  const double tSym = (double)(1UL << LORA_SF) * 1000.0 / (double)LORA_BW;
  const uint8_t DE  = (tSym > 16.0) ? 1 : 0;
  const uint8_t CR  = LORA_CR - 4;
  double tPre = ((double)LORA_PREAMBLE + 4.25) * tSym;

  long num = 8L * (long)len - 4L * LORA_SF + 28 + 16;
  long den = 4L * (LORA_SF - 2 * DE);
  long nPay = 8;
  if (num > 0) nPay += ((num + den - 1) / den) * (CR + 4);

  return (uint32_t)(tPre + (double)nPay * tSym + 0.5);
}

uint32_t dutyUsedMs   = 0;
uint32_t dutyWinStart = 0;
uint32_t statDuty     = 0;

bool dutyAllows(uint16_t len) {
  uint32_t now = millis();
  if (now - dutyWinStart >= DUTY_WINDOW_MS) { dutyWinStart = now; dutyUsedMs = 0; }
  const uint32_t budgetMs = (DUTY_WINDOW_MS / 1000UL) * (uint32_t)DUTY_BUDGET_PERMIL;
  if (dutyUsedMs + loraAirtimeMs(len) <= budgetMs) return true;

  statDuty++;
  static uint32_t lastMoan = 0;
  if (now - lastMoan > 30000UL) {
    lastMoan = now;
    Serial.printf("[duty] channel busy - %lu of %lu ms used this minute, "
                  "%lu beacons skipped so far\n",
                  (unsigned long)dutyUsedMs, (unsigned long)budgetMs,
                  (unsigned long)statDuty);
  }
  return false;
}

void radioWatchdog() {
  if (!radioOk) return;
  if (millis() - lastTxOkMs < RADIO_WEDGE_MS) return;

  statWedge++;
  Serial.printf("[radio] WEDGED - no successful TX in %lus, forcing reinit (#%lu)\n",
                (unsigned long)(RADIO_WEDGE_MS / 1000UL), (unsigned long)statWedge);
  radioOk = false;
  if (radioBegin()) {
    Serial.println("[radio] reinit OK");
    bootBeacons = 4;
    hbTimer.begin(3000UL, 0);
  } else {
    Serial.println("[radio] reinit FAILED - will keep retrying");
  }
  lastTxOkMs = millis();
}

void manualRescan(const char *why) {
  Serial.printf("[radio] manual rescan requested (%s) - reinit + fast beacon\n", why);
  radioOk = false;
  radioBegin();
  bootBeacons = 4;
  hbTimer.begin(1000UL, 0);
  rtTimer.begin(2000UL, 0);
  lastTxOkMs = millis();
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

void radioService() {
  if (txInFlight) {
    if (millis() - txStart < txAirtimeMs) return;
    txInFlight = false;
    statTx++;
    lastTxOkMs = millis();
    dutyUsedMs += txAirtimeMs;
    txLast = millis();
    txGap  = TX_MIN_GAP_MS + (uint32_t)random(0, TX_GAP_JITTER_MS);
    return;
  }

  if (!radioOk || txCount == 0) return;
  if (millis() - txLast < txGap) return;

  if (LoRa.beginPacket() == 0) {
    statTxStuck++;
    txLast = millis() - txGap + 40;
    return;
  }

  uint16_t len = (uint16_t)strlen(txQueue[txHead]);
  LoRa.print(txQueue[txHead]);
  LoRa.endPacket(true);
  txInFlight  = true;
  txStart     = millis();
  txAirtimeMs = loraAirtimeMs(len) + TX_AIRTIME_MARGIN_MS;

  txHead = (uint8_t)((txHead + 1) % TX_QUEUE_DEPTH);
  txCount--;
}

bool radioPoll(Packet &out) {
  if (!radioOk) return false;
  if (txInFlight) return false;
  int sz = LoRa.parsePacket();
  if (sz <= 0) return false;

  char buf[MAX_PACKET_LEN];
  int n = 0;
  while (LoRa.available() && n < (int)sizeof(buf) - 1) buf[n++] = (char)LoRa.read();
  buf[n] = '\0';
  while (LoRa.available()) LoRa.read();

  int   rssi = LoRa.packetRssi();
  float snr  = LoRa.packetSnr();

  if (!pktParse(buf, out)) {
    statBad++;
    Serial.printf("[rx-raw] unparsed  rssi=%d snr=%.1f len=%d  \"%.60s\"\n",
                  rssi, (double)snr, n, buf);
    return false;
  }
  out.rssi = rssi;
  out.snr  = snr;
  statRx++;
  return true;
}

// ===========================================================================
//  GPS MODULE  -  non-blocking NMEA reader (unchanged from Node C)
// ===========================================================================
char     nmeaBuf[NMEA_BUF_LEN];
uint8_t  nmeaLen = 0;

double   gpsLat = 0.0, gpsLon = 0.0;
bool     gpsHasFix = false;
uint32_t gpsFixTime = 0;
int      gpsSats = 0;
uint32_t gpsSentences = 0;

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

  if (strncmp(line + 3, "RMC", 3) == 0) {
    char status[4];
    if (!nmeaField(line, 2, status, sizeof(status))) return;
    if (status[0] != 'A') { gpsHasFix = false; return; }

    char la[16], ns[4], lo[16], ew[4];
    if (!nmeaField(line, 3, la, sizeof(la))) return;
    if (!nmeaField(line, 4, ns, sizeof(ns))) return;
    if (!nmeaField(line, 5, lo, sizeof(lo))) return;
    if (!nmeaField(line, 6, ew, sizeof(ew))) return;
    if (!la[0] || !lo[0] || !ns[0] || !ew[0]) return;

    gpsLat = nmeaCoord(la, ns);
    gpsLon = nmeaCoord(lo, ew);
    gpsHasFix = true;
    gpsFixTime = millis();
  }
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
      nmeaLen = 0;
    }
  }
}

// ===========================================================================
//  LOCATION  -  GPS module only here (no portal = no phone source, see the
//  header note). locBest() etc. are kept so this stays a near-identical diff
//  of the other three sketches.
// ===========================================================================
double   phoneLat = 0.0, phoneLon = 0.0;
bool     phoneValid = false;
uint32_t phoneTime = 0;
float    phoneAcc = 0.0;
uint32_t phoneUpdates = 0;

uint8_t locBest(double &lat, double &lon, uint32_t &ageMs) {
  uint32_t now = millis();
  bool gFresh = gpsHasFix  && gpsFixTime && (now - gpsFixTime < GPS_FRESH_MS);

  if (gFresh) { lat = gpsLat; lon = gpsLon; ageMs = now - gpsFixTime; return LOC_GPS; }
  if (gpsFixTime) { lat = gpsLat; lon = gpsLon; ageMs = now - gpsFixTime; return LOC_GPS; }
  lat = 0.0; lon = 0.0; ageMs = 0;
  return LOC_NONE;
}

const char *locSrcName(uint8_t src) {
  if (src == LOC_GPS)   return "GPS";
  if (src == LOC_PHONE) return "PHONE";
  return "NONE";
}

bool locValid(double lat, double lon) {
  if (lat < -90.0 || lat > 90.0)   return false;
  if (lon < -180.0 || lon > 180.0) return false;
  if (lat == 0.0 && lon == 0.0)    return false;
  return true;
}

// ===========================================================================
//  OLED  (unchanged from Node C)
// ===========================================================================
bool oledOk = false;

char uiPrev[5][26];
bool uiPrevValid = false;

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
  uiPrevValid = false;
}

void oledPush(char l[5][26]) {
  if (uiPrevValid) {
    bool same = true;
    for (uint8_t i = 0; i < 5 && same; i++)
      if (strcmp(uiPrev[i], l[i]) != 0) same = false;
    if (same) return;
  }
  for (uint8_t i = 0; i < 5; i++) {
    strncpy(uiPrev[i], l[i], sizeof(uiPrev[i]) - 1);
    uiPrev[i][sizeof(uiPrev[i]) - 1] = '\0';
  }
  uiPrevValid = true;

  oledClear();
  for (uint8_t i = 0; i < 5; i++) oledLine(i, l[i]);
  oledShow();
}

void oledInvalidate() { uiPrevValid = false; }

// ===========================================================================
//  MOTOR LAYER  -  direction-only H-bridge control, no PWM speed dependency
//  (see the header note on why ENA/ENB are plain digitalWrite, not LEDC).
//  Every function here is instant and non-blocking - state is driven by
//  roverService()/autoService()/manualDriveService() below, never by delay().
// ===========================================================================
void motorInit() {
  pinMode(PIN_LEFT_IN1, OUTPUT);
  pinMode(PIN_LEFT_IN2, OUTPUT);
  pinMode(PIN_LEFT_EN,  OUTPUT);
  pinMode(PIN_RIGHT_IN1, OUTPUT);
  pinMode(PIN_RIGHT_IN2, OUTPUT);
  pinMode(PIN_RIGHT_EN,  OUTPUT);
  digitalWrite(PIN_LEFT_EN, LOW);
  digitalWrite(PIN_RIGHT_EN, LOW);
}

void motorStop() {
  digitalWrite(PIN_LEFT_EN, LOW);
  digitalWrite(PIN_RIGHT_EN, LOW);
  digitalWrite(PIN_LEFT_IN1, LOW);
  digitalWrite(PIN_LEFT_IN2, LOW);
  digitalWrite(PIN_RIGHT_IN1, LOW);
  digitalWrite(PIN_RIGHT_IN2, LOW);
}

void motorForward() {
  digitalWrite(PIN_LEFT_IN1, HIGH);  digitalWrite(PIN_LEFT_IN2, LOW);
  digitalWrite(PIN_RIGHT_IN1, HIGH); digitalWrite(PIN_RIGHT_IN2, LOW);
  digitalWrite(PIN_LEFT_EN, HIGH);   digitalWrite(PIN_RIGHT_EN, HIGH);
}

void motorBackward() {
  digitalWrite(PIN_LEFT_IN1, LOW);  digitalWrite(PIN_LEFT_IN2, HIGH);
  digitalWrite(PIN_RIGHT_IN1, LOW); digitalWrite(PIN_RIGHT_IN2, HIGH);
  digitalWrite(PIN_LEFT_EN, HIGH);  digitalWrite(PIN_RIGHT_EN, HIGH);
}

// Tank turns - one side forward, one side back. Works in place, no need for
// room to arc, which matters for the bump-turn obstacle response.
void motorLeft() {
  digitalWrite(PIN_LEFT_IN1, LOW);   digitalWrite(PIN_LEFT_IN2, HIGH);
  digitalWrite(PIN_RIGHT_IN1, HIGH); digitalWrite(PIN_RIGHT_IN2, LOW);
  digitalWrite(PIN_LEFT_EN, HIGH);   digitalWrite(PIN_RIGHT_EN, HIGH);
}

void motorRight() {
  digitalWrite(PIN_LEFT_IN1, HIGH);  digitalWrite(PIN_LEFT_IN2, LOW);
  digitalWrite(PIN_RIGHT_IN1, LOW);  digitalWrite(PIN_RIGHT_IN2, HIGH);
  digitalWrite(PIN_LEFT_EN, HIGH);   digitalWrite(PIN_RIGHT_EN, HIGH);
}

// ===========================================================================
//  ULTRASONIC LAYER  (HC-SR04)  -  interrupt-timed, fully non-blocking.
//
//  The obvious HC-SR04 code (pulseIn()) BLOCKS for up to its timeout - tens
//  of ms with nothing connected - which is exactly the kind of stall this
//  whole codebase is built to avoid (see the "no delay() in loop()" rule and
//  the I2C/GPS blocking bugs fixed in Phases 6-7). Instead: TRIG is a tiny,
//  bounded ~12us pulse (the HC-SR04 datasheet's own minimum, four orders of
//  magnitude shorter than a loop iteration budget - the same category as the
//  I2C/SPI transaction time already spent elsewhere in this sketch, not the
//  kind of blocking call the project is trying to eliminate), and ECHO's
//  rising/falling edges are timestamped by an interrupt, so loop() is never
//  waiting on the sensor.
// ===========================================================================
volatile uint32_t echoRiseUs = 0;
volatile uint32_t echoFallUs = 0;
volatile bool     echoNewReading = false;

int      ultrasonicCm = -1;          // -1 = unknown / nothing in range
uint32_t ultrasonicLastTrigMs = 0;
bool     ultrasonicWaiting = false;

void IRAM_ATTR echoIsr() {
  if (digitalRead(PIN_ECHO) == HIGH) {
    echoRiseUs = micros();
  } else {
    echoFallUs = micros();
    echoNewReading = true;
  }
}

void ultrasonicInit() {
  pinMode(PIN_TRIG, OUTPUT);
  digitalWrite(PIN_TRIG, LOW);
  pinMode(PIN_ECHO, INPUT);
  attachInterrupt(digitalPinToInterrupt(PIN_ECHO), echoIsr, CHANGE);
}

void ultrasonicTrigger() {
  // The 3 digitalWrite()s + two delayMicroseconds() below cost ~12us total -
  // see the section header for why that is not the blocking-call problem.
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  ultrasonicWaiting = true;
  ultrasonicLastTrigMs = millis();
}

// Called every loop. Fires a new ping at most every ULTRASONIC_INTERVAL_MS
// and reads back whatever the ISR captured since - never blocks.
void ultrasonicService() {
  uint32_t now = millis();

  if (ultrasonicWaiting) {
    if (echoNewReading) {
      noInterrupts();
      uint32_t rise = echoRiseUs, fall = echoFallUs;
      echoNewReading = false;
      interrupts();
      uint32_t widthUs = fall - rise;          // wraps harmlessly at ~71 min
      ultrasonicCm = (int)(widthUs / 58UL);    // ~58us per cm, round trip
      ultrasonicWaiting = false;
    } else if (now - ultrasonicLastTrigMs > ULTRASONIC_ECHO_TIMEOUT_MS) {
      ultrasonicCm = -1;                       // nothing came back - clear
      ultrasonicWaiting = false;
    }
    return;
  }

  if (now - ultrasonicLastTrigMs >= ULTRASONIC_INTERVAL_MS) ultrasonicTrigger();
}

// ===========================================================================
//  ROVER  -  mode state machine, dead-man manual driving, bump-turn AUTO,
//  and the periodic ROVER: telemetry broadcast.
// ===========================================================================
uint8_t  roverMode = ROVER_MANUAL;     // safe default - see header note

// ---- manual (dashboard/serial) driving, dead-man-switch pulsed -----------
bool     manualDriving = false;
uint32_t manualDriveUntilMs = 0;

// ---- AUTO bump-turn state machine -----------------------------------------
#define RA_FORWARD 0
#define RA_BACK    1
#define RA_TURN    2
uint8_t  autoState = RA_FORWARD;
uint32_t autoStateSince = 0;

const char *roverModeName(uint8_t m) {
  if (m == ROVER_AUTO)  return "AUTO";
  if (m == ROVER_RELAY) return "RELAY";
  return "MANUAL";
}

// Immediate motor cut, from any cause: an explicit STOP, a mode switch away
// from whatever was driving, or the SOS button. Always safe to call.
void roverEmergencyStop(const char *why) {
  motorStop();
  manualDriving = false;
  Serial.printf("[rover] STOP (%s)\n", why);
}

void roverSetMode(uint8_t newMode, const char *why) {
  if (newMode == roverMode) return;
  roverEmergencyStop("mode change");
  roverMode = newMode;
  autoState = RA_FORWARD;
  autoStateSince = millis();
  Serial.printf("[rover] mode -> %s (%s)\n", roverModeName(roverMode), why);
}

// One MANUAL drive command = a bounded pulse. See the header note: this is
// the entire safety model for remote driving - no command, or a dropped
// link, and the rover stops on its own within MANUAL_PULSE_MS.
void roverManualDrive(const char *verb) {
  if (roverMode != ROVER_MANUAL) {
    Serial.printf("[rover] drive command ignored - mode is %s, not MANUAL\n",
                  roverModeName(roverMode));
    return;
  }
  if      (!strcmp(verb, "FWD"))   motorForward();
  else if (!strcmp(verb, "BACK"))  motorBackward();
  else if (!strcmp(verb, "LEFT"))  motorLeft();
  else if (!strcmp(verb, "RIGHT")) motorRight();
  else if (!strcmp(verb, "STOP"))  { roverEmergencyStop("STOP command"); return; }
  else return;

  manualDriving = true;
  manualDriveUntilMs = millis() + MANUAL_PULSE_MS;
  Serial.printf("[rover] drive %s (pulse %lums)\n", verb, (unsigned long)MANUAL_PULSE_MS);
}

void manualDriveService() {
  if (manualDriving && millis() > manualDriveUntilMs) {
    motorStop();
    manualDriving = false;
  }
}

// Non-blocking bump-turn. Forward until something is closer than
// AUTO_OBSTACLE_CM, then back off and turn a random way, then resume.
void autoService() {
  uint32_t now = millis();
  bool obstacle = (ultrasonicCm > 0 && ultrasonicCm < AUTO_OBSTACLE_CM);

  if (autoState == RA_FORWARD) {
    motorForward();
    if (obstacle) {
      Serial.printf("[rover] obstacle at %dcm - backing off\n", ultrasonicCm);
      motorBackward();
      autoState = RA_BACK;
      autoStateSince = now;
    }
  } else if (autoState == RA_BACK) {
    if (now - autoStateSince > AUTO_BACK_MS) {
      bool turnRight = (random(0, 2) == 0);
      if (turnRight) motorRight(); else motorLeft();
      Serial.printf("[rover] turning %s\n", turnRight ? "right" : "left");
      autoState = RA_TURN;
      autoStateSince = now;
    }
  } else { // RA_TURN
    uint32_t turnMs = AUTO_TURN_MS_MIN +
                      (uint32_t)random(0, AUTO_TURN_MS_MAX - AUTO_TURN_MS_MIN);
    if (now - autoStateSince > turnMs) {
      motorForward();
      autoState = RA_FORWARD;
      autoStateSince = now;
    }
  }
}

// Dispatch by mode. Called every loop.
void roverService() {
  ultrasonicService();

  if      (roverMode == ROVER_AUTO)   autoService();
  else if (roverMode == ROVER_MANUAL) manualDriveService();
  else                                motorStop();   // RELAY: hold position
}

// Raw ADC -> rough percentage. See the header note: CALIBRATE
// BATTERY_ADC_VMIN/VMAX/DIVIDER for your actual pack and divider, or treat
// this as illustrative only. Returns -1 if the pin reads implausibly (no
// divider wired) so the telemetry can say "n/a" rather than lie.
int roverBatteryPercent() {
  int raw = analogRead(PIN_BATTERY_ADC);          // 0-4095, 0-3.3V at the pin
  float vAtPin = (raw / 4095.0f) * 3.3f;
  float vPack  = vAtPin * BATTERY_ADC_DIVIDER;
  if (vPack < 1.0f) return -1;                    // nothing plausible wired
  float pct = (vPack - BATTERY_ADC_VMIN) / (BATTERY_ADC_VMAX - BATTERY_ADC_VMIN) * 100.0f;
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  return (int)(pct + 0.5f);
}

// payload: mode,obstacle_cm,battery_pct  - position is NOT repeated here,
// it already goes out in this node's own GPS: broadcast (see header note).
void sendRoverTelemetry() {
  roverTelemetryTimer.setPeriod(ROVER_TELEMETRY_MS +
                                (uint32_t)random(0, ROVER_TELEMETRY_JITTER_MS));

  int batt = roverBatteryPercent();
  char payload[48];
  snprintf(payload, sizeof(payload), "%s,%d,%d",
           roverModeName(roverMode), ultrasonicCm, batt);

  char frame[MAX_PACKET_LEN];
  if (pktBuild(frame, sizeof(frame), "ROVER", MY_ID, "*", nextMsgId(), MAX_HOPS, payload)
      && dutyAllows((uint16_t)strlen(frame)))
    radioEnqueue(frame);
}

// ===========================================================================
//  WATCHDOG / BOOT DIAGNOSTICS  (unchanged from Node C)
// ===========================================================================
const char *resetReasonName() {
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON:   return "POWERON (normal power-up / EN button)";
    case ESP_RST_EXT:       return "EXT (external reset pin)";
    case ESP_RST_SW:        return "SW (software restart)";
    case ESP_RST_PANIC:     return "PANIC - crash/exception  <<< SOFTWARE BUG";
    case ESP_RST_INT_WDT:   return "INT_WDT - interrupt watchdog  <<< SOMETHING BLOCKED";
    case ESP_RST_TASK_WDT:  return "TASK_WDT - loop stalled  <<< SOMETHING BLOCKED";
    case ESP_RST_WDT:       return "WDT - other watchdog  <<< SOMETHING BLOCKED";
    case ESP_RST_DEEPSLEEP: return "DEEPSLEEP wake";
    case ESP_RST_BROWNOUT:  return "BROWNOUT - 3.3V rail sagged  <<< POWER PROBLEM (check the motor supply first on this node)";
    case ESP_RST_SDIO:      return "SDIO";
    default:                return "UNKNOWN";
  }
}

const char *resetReasonShort() {
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON:   return "POWERON";
    case ESP_RST_EXT:       return "EXT";
    case ESP_RST_SW:        return "SW";
    case ESP_RST_PANIC:     return "PANIC";
    case ESP_RST_INT_WDT:   return "INT_WDT";
    case ESP_RST_TASK_WDT:  return "TASK_WDT";
    case ESP_RST_WDT:       return "WDT";
    case ESP_RST_DEEPSLEEP: return "DEEPSLEEP";
    case ESP_RST_BROWNOUT:  return "BROWNOUT";
    default:                return "UNKNOWN";
  }
}

void wdtBegin() {
  esp_err_t e;
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  esp_task_wdt_config_t cfg;
  cfg.timeout_ms     = WDT_TIMEOUT_S * 1000;
  cfg.idle_core_mask = 0;
  cfg.trigger_panic  = true;
  e = esp_task_wdt_reconfigure(&cfg);
  if (e != ESP_OK) e = esp_task_wdt_init(&cfg);
#else
  e = esp_task_wdt_init(WDT_TIMEOUT_S, true);
#endif
  esp_task_wdt_add(NULL);
  Serial.printf("[wdt] task watchdog set to %us (%s)\n",
                (unsigned)WDT_TIMEOUT_S, (e == ESP_OK) ? "ok" : "NOT APPLIED");
}

// ===========================================================================
//  APPLICATION  (unchanged from Node C, minus the AP-station count on the
//  stat line - there's no AP here)
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
    bootBeacons--;
    hbTimer.setPeriod(3000UL);
  } else if (anyNeighborMissing()) {
    if (missingSinceMs == 0) missingSinceMs = millis();
    bool burst = (millis() - missingSinceMs < RECONNECT_WINDOW_MS) &&
                 dutyAllows(64);
    hbTimer.setPeriod(burst ? RECONNECT_HB_MS + (uint32_t)random(0, 800)
                            : HB_INTERVAL_MS + (uint32_t)random(0, HB_JITTER_MS));
  } else {
    missingSinceMs = 0;
    hbTimer.setPeriod(HB_INTERVAL_MS + (uint32_t)random(0, HB_JITTER_MS));
  }
}

void sendLocation() {
  gpsTimer.setPeriod(GPS_INTERVAL_MS + (uint32_t)random(0, GPS_JITTER_MS));

  double lat, lon;
  uint32_t ageMs;
  uint8_t src = locBest(lat, lon, ageMs);
  if (src == LOC_NONE) return;

  char payload[64];
  snprintf(payload, sizeof(payload), "%.6f,%.6f,%d,%u,%lu",
           lat, lon, gpsSats, (unsigned)src, (unsigned long)(ageMs / 1000UL));

  char frame[MAX_PACKET_LEN];
  if (pktBuild(frame, sizeof(frame), "GPS", MY_ID, "*", nextMsgId(), 0, payload)
      && dutyAllows((uint16_t)strlen(frame)))
    radioEnqueue(frame);
}

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

  char frame[MAX_PACKET_LEN];
  if (pktBuild(frame, sizeof(frame), "RT", MY_ID, "*", nextMsgId(), 0, payload)
      && dutyAllows((uint16_t)strlen(frame)))
    radioEnqueue(frame);
}

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

// ===========================================================================
//  SOS  (unchanged from Node C)
// ===========================================================================
void sosShowAlert(const char *victim, double lat, double lon, const char *text) {
  sosAlert = true;
  sosAlertStart = millis();
  strncpy(sosVictim, victim, sizeof(sosVictim) - 1);
  sosVictim[sizeof(sosVictim) - 1] = '\0';
  sosLat = lat;
  sosLon = lon;
  strncpy(sosText, text, sizeof(sosText) - 1);
  sosText[sizeof(sosText) - 1] = '\0';
}

void sosClearAlert(const char *why) {
  if (!sosAlert) return;
  sosAlert = false;
  sosAcks[0] = '\0';
  Serial.printf("[sos] alert cleared (%s)\n", why);
}

void sosTrigger(const char *reason) {
  double lat, lon;
  uint32_t ageMs;
  uint8_t src = locBest(lat, lon, ageMs);

  char loctag[40];
  if (src == LOC_NONE) {
    lat = 0; lon = 0;
    snprintf(loctag, sizeof(loctag), "NO-FIX");
  } else {
    snprintf(loctag, sizeof(loctag), "%s%s",
             locSrcName(src), (ageMs > 120000UL) ? "-STALE" : "");
  }

  snprintf(sosBurstMsg, sizeof(sosBurstMsg), "%s", reason);
  sosBurstId   = nextMsgId();
  sosBurstLeft = SOS_BURST_COUNT;
  sosSending   = true;
  sosBurstTimer.begin(SOS_BURST_GAP_MS, 0);

  sosShowAlert(MY_ID, lat, lon, reason);

  Serial.printf("\n[sos] *** SOS TRIGGERED (%s) *** pos %.6f,%.6f (%s)\n",
                reason, lat, lon, loctag);
}

void sosSendCopy() {
  double lat, lon;
  uint32_t ageMs;
  locBest(lat, lon, ageMs);

  char payload[80];
  snprintf(payload, sizeof(payload), "%.6f,%.6f,%s", lat, lon, sosBurstMsg);

  char frame[MAX_PACKET_LEN];
  if (pktBuild(frame, sizeof(frame), "SOS", MY_ID, "*", sosBurstId, MAX_HOPS, payload))
    radioEnqueue(frame);

  Serial.printf("[sos] broadcast copy %u/%u\n",
                (unsigned)(SOS_BURST_COUNT - sosBurstLeft + 1), (unsigned)SOS_BURST_COUNT);
}

void sosService() {
  if (sosSending && sosBurstTimer.due()) {
    sosSendCopy();
    if (--sosBurstLeft == 0) sosSending = false;
  }
  if (sosAlert && (millis() - sosAlertStart > SOS_SCREEN_MS))
    sosClearAlert("timeout");
}

void sosSendAck(const char *victim, uint16_t origId) {
  char payload[16];
  snprintf(payload, sizeof(payload), "%s,%u", victim, (unsigned)origId);
  char frame[MAX_PACKET_LEN];
  if (pktBuild(frame, sizeof(frame), "SOSACK", MY_ID, victim, nextMsgId(), MAX_HOPS, payload))
    radioEnqueue(frame);
}

// ===========================================================================
//  SOS BUTTON  -  edge detected, hold-to-clear. On the Rover it is ALSO an
//  immediate physical motor E-STOP on every press, independent of whatever
//  the SOS latch state ends up doing - a moving robot needs a hardware
//  override that cannot be blocked by any software state.
// ===========================================================================
void buttonService() {
  bool now = (digitalRead(PIN_SOS_BUTTON) == HIGH);
  uint32_t t = millis();

  if (now != btnPrev) {
    if (t - btnChangeTime < SOS_DEBOUNCE_MS) return;
    btnChangeTime = t;

    if (!now) {                       // just pressed
      btnHeldHandled = false;
      roverEmergencyStop("SOS button pressed");
    } else {                          // just released
      if (!btnHeldHandled) {
        if (sosAlert && strcmp(sosVictim, MY_ID) != 0)
          sosClearAlert("button tap on a received alert");
        else
          sosTrigger("BUTTON");
      }
    }
    btnPrev = now;
    return;
  }

  if (!now && !btnHeldHandled && (t - btnChangeTime > SOS_BUTTON_HOLD_MS)) {
    btnHeldHandled = true;
    if (sosAlert) sosClearAlert("button held");
    else          sosTrigger("BUTTON-HOLD");
  }
}

// ===========================================================================
//  RESCUE REPORT + TEAM STATUS  (unchanged from Node C)
// ===========================================================================
bool reportCodeValid(const char *c) {
  return !strcmp(c, "VICTIM_FOUND") || !strcmp(c, "MEDICAL") ||
         !strcmp(c, "BLOCKED")      || !strcmp(c, "DANGER");
}
bool statusValid(const char *s) {
  return !strcmp(s, "AVAILABLE")    || !strcmp(s, "SEARCHING") ||
         !strcmp(s, "VICTIM_FOUND") || !strcmp(s, "NEED_ASSIST") ||
         !strcmp(s, "EMERGENCY");
}

void sendReport(const char *code) {
  if (!reportCodeValid(code)) { Serial.printf("[rpt] bad code %s\n", code); return; }
  double lat, lon; uint32_t ageMs;
  locBest(lat, lon, ageMs);

  char payload[64];
  snprintf(payload, sizeof(payload), "%s,%.6f,%.6f,%s", code, lat, lon, myTeam);
  char frame[MAX_PACKET_LEN];
  if (pktBuild(frame, sizeof(frame), "RPT", MY_ID, "*", nextMsgId(), MAX_HOPS, payload))
    radioEnqueue(frame);

  int i = peerRepIndex(MY_ID);
  if (i >= 0) { strncpy(peerRep[i].code, code, sizeof(peerRep[i].code) - 1);
                peerRep[i].reportTime = millis(); }
  Serial.printf("[rpt] sent %s\n", code);
}

void sendStatus(const char *st) {
  if (!statusValid(st)) { Serial.printf("[stat] bad status %s\n", st); return; }
  strncpy(myStatus, st, sizeof(myStatus) - 1);
  myStatus[sizeof(myStatus) - 1] = '\0';

  char payload[24];
  snprintf(payload, sizeof(payload), "%s,%s", myTeam, myStatus);
  char frame[MAX_PACKET_LEN];
  if (pktBuild(frame, sizeof(frame), "STAT", MY_ID, "*", nextMsgId(), 0, payload))
    radioEnqueue(frame);

  int i = peerRepIndex(MY_ID);
  if (i >= 0) { strncpy(peerRep[i].status, myStatus, sizeof(peerRep[i].status) - 1);
                peerRep[i].statusTime = millis(); }
  Serial.printf("[team] status -> %s\n", myStatus);
}

// ===========================================================================
//  RECEIVE DISPATCH
// ===========================================================================
void handleOneRx() {
  Packet p;
  if (!radioPoll(p)) return;
  if (strcmp(p.src, MY_ID) == 0) return;

  bool forwardable = !strcmp(p.type, "DATA")   || !strcmp(p.type, "SOS")    ||
                     !strcmp(p.type, "CMD")    ||
                     !strcmp(p.type, "SOSACK") || !strcmp(p.type, "RPT")   ||
                     !strcmp(p.type, "ROVER");   // another rover, in theory - also relayed
  if (forwardable && seenOrAdd(p.src, p.msgId)) return;

  int ev = neighborSeen(p.src, p.rssi, p.snr);
  if      (ev == NB_NEW)         Serial.printf("[mesh] NEW neighbour %s  %d dBm\n", p.src, p.rssi);
  else if (ev == NB_RECONNECTED) {
    seenForget(p.src);
    Serial.printf("[mesh] RECONNECTED %s  %d dBm\n", p.src, p.rssi);
  }
  else if (ev == NB_FULL)        Serial.println("[mesh] neighbour table FULL");

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
    char buf[MAX_PAYLOAD_LEN];
    strncpy(buf, p.payload, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';

    char *tok = strtok(buf, ";");
    while (tok) {
      char d[4], v[4];
      unsigned h = 0;
      if (routeParseEntry(tok, d, sizeof(d), &h, v, sizeof(v))) {
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

  } else if (strcmp(p.type, "SOS") == 0) {
    double la = 0, lo = 0;
    char msg[48] = "";
    char *c1 = strchr(p.payload, ',');
    char *c2 = c1 ? strchr(c1 + 1, ',') : NULL;
    if (c2) {
      *c1 = *c2 = '\0';
      la = atof(p.payload);
      lo = atof(c1 + 1);
      strncpy(msg, c2 + 1, sizeof(msg) - 1);
    }
    sosShowAlert(p.src, la, lo, msg);
    sosSendAck(p.src, p.msgId);
    Serial.printf("\n>>> SOS FROM %s : %s  @ %.6f,%.6f  (rssi %d)\n\n",
                  p.src, msg, la, lo, p.rssi);
    if (p.ttl > 0) {
      char frame[MAX_PACKET_LEN];
      if (pktBuild(frame, sizeof(frame), "SOS", p.src, "*",
                   p.msgId, (uint8_t)(p.ttl - 1), p.payload)) {
        radioEnqueue(frame);
        statFwd++;
      }
    }

  } else if (strcmp(p.type, "SOSACK") == 0) {
    char who[4] = ""; unsigned oid = 0;
    if (sscanf(p.payload, "%3[^,],%u", who, &oid) >= 1) {
      if (sosAlert && strcmp(sosVictim, MY_ID) == 0 && oid == sosBurstId) {
        if (!strstr(sosAcks, p.src)) {
          if (sosAcks[0]) strncat(sosAcks, ",", sizeof(sosAcks) - strlen(sosAcks) - 1);
          strncat(sosAcks, p.src, sizeof(sosAcks) - strlen(sosAcks) - 1);
        }
        Serial.printf("[sos] ACK from %s - someone heard our SOS\n", p.src);
      }
    }
    if (strcmp(p.dest, MY_ID) != 0 && p.ttl > 0) {
      char frame[MAX_PACKET_LEN];
      if (pktBuild(frame, sizeof(frame), "SOSACK", p.src, p.dest,
                   p.msgId, (uint8_t)(p.ttl - 1), p.payload)) {
        radioEnqueue(frame); statFwd++;
      }
    }

  } else if (strcmp(p.type, "RPT") == 0) {
    char code[14] = ""; double la = 0, lo = 0; char team[8] = "";
    if (sscanf(p.payload, "%13[^,],%lf,%lf,%7s", code, &la, &lo, team) >= 1) {
      int i = peerRepIndex(p.src);
      if (i >= 0) { strncpy(peerRep[i].code, code, sizeof(peerRep[i].code) - 1);
                    peerRep[i].code[sizeof(peerRep[i].code) - 1] = '\0';
                    peerRep[i].reportTime = millis(); }
      if (locValid(la, lo)) neighborSetLoc(p.src, la, lo, LOC_PHONE);
      Serial.printf(">>> REPORT from %s (team %s): %s  @ %.6f,%.6f\n",
                    p.src, team, code, la, lo);
    }
    if (p.ttl > 0) {
      char frame[MAX_PACKET_LEN];
      if (pktBuild(frame, sizeof(frame), "RPT", p.src, "*",
                   p.msgId, (uint8_t)(p.ttl - 1), p.payload)) {
        radioEnqueue(frame); statFwd++;
      }
    }

  } else if (strcmp(p.type, "STAT") == 0) {
    char team[8] = ""; char st[14] = "";
    if (sscanf(p.payload, "%7[^,],%13s", team, st) == 2) {
      int i = peerRepIndex(p.src);
      if (i >= 0) { strncpy(peerRep[i].status, st, sizeof(peerRep[i].status) - 1);
                    peerRep[i].status[sizeof(peerRep[i].status) - 1] = '\0';
                    peerRep[i].statusTime = millis(); }
      Serial.printf("[team] %s (team %s) is now %s\n", p.src, team, st);
    }

  } else if (strcmp(p.type, "CMD") == 0) {
    // Commands from the Pi command centre (src "PI"), payload = verb[,arg].
    // WHERE/PING/SOS/SOSCLR are unchanged from Phase 5; FWD/BACK/LEFT/RIGHT/
    // STOP/MODE are new here - and ONLY here, A/B/C did not need to learn
    // these verbs, they already forward any CMD not addressed to them.
    if (strcmp(p.dest, MY_ID) == 0) {
      char verb[12] = "", arg[12] = "";
      sscanf(p.payload, "%11[^,],%11s", verb, arg);
      Serial.printf("[cmd] %s%s%s from %s\n", verb, arg[0] ? "," : "", arg, p.src);

      if (!strcmp(verb, "WHERE")) {
        sendLocation();
      } else if (!strcmp(verb, "PING")) {
        char frame[MAX_PACKET_LEN];
        if (pktBuild(frame, sizeof(frame), "DATA", MY_ID, p.src,
                     nextMsgId(), MAX_HOPS, "pong"))
          radioEnqueue(frame);
      } else if (!strcmp(verb, "SOS")) {
        sosTrigger("REMOTE");
      } else if (!strcmp(verb, "SOSCLR")) {
        sosClearAlert("command centre");
      } else if (!strcmp(verb, "FWD") || !strcmp(verb, "BACK") ||
                 !strcmp(verb, "LEFT") || !strcmp(verb, "RIGHT") ||
                 !strcmp(verb, "STOP")) {
        roverManualDrive(verb);
      } else if (!strcmp(verb, "MODE")) {
        if      (!strcmp(arg, "AUTO"))   roverSetMode(ROVER_AUTO, "command centre");
        else if (!strcmp(arg, "RELAY"))  roverSetMode(ROVER_RELAY, "command centre");
        else if (!strcmp(arg, "MANUAL")) roverSetMode(ROVER_MANUAL, "command centre");
      }
    } else if (p.ttl > 0 && routeBestHop(p.dest)) {
      char frame[MAX_PACKET_LEN];
      if (pktBuild(frame, sizeof(frame), "CMD", p.src, p.dest,
                   p.msgId, (uint8_t)(p.ttl - 1), p.payload)) {
        radioEnqueue(frame); statFwd++;
      }
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

  } else if (strcmp(p.type, "ROVER") == 0) {
    // Another rover's telemetry, if this mesh ever has more than one -
    // nothing to act on locally, just relay it the same way A/B/C do.
    if (p.ttl > 0) {
      char frame[MAX_PACKET_LEN];
      if (pktBuild(frame, sizeof(frame), "ROVER", p.src, "*",
                   p.msgId, (uint8_t)(p.ttl - 1), p.payload)) {
        radioEnqueue(frame); statFwd++;
      }
    }
  }

  if (verboseRx)
    Serial.printf("[rx] %s from %s id=%u ttl=%u rssi=%d snr=%.1f : %s\n",
                  p.type, p.src, (unsigned)p.msgId, (unsigned)p.ttl,
                  p.rssi, (double)p.snr, p.payload);
}

void handleRx() {
  for (uint8_t i = 0; i < 4; i++) handleOneRx();
}

// ===========================================================================
//  OLED PAGES  (Node C's 5 pages, unchanged, plus a 6th ROVER STATUS page)
// ===========================================================================
const char *sigBars(int rssi) {
  if (rssi >= -85)  return "||||";
  if (rssi >= -100) return "|||.";
  if (rssi >= -110) return "||..";
  if (rssi >= -118) return "|...";
  return "....";
}

void fmtAge(uint32_t ms, char *out, size_t n) {
  uint32_t s = ms / 1000UL;
  if (s < 60)        snprintf(out, n, "%lus", (unsigned long)s);
  else if (s < 3600) snprintf(out, n, "%lum", (unsigned long)(s / 60));
  else               snprintf(out, n, "%luh", (unsigned long)(s / 3600));
}

void drawPage0() {
  char l[5][26];
  char list[20], upStr[8];
  neighborActiveList(list, sizeof(list));
  fmtAge(millis(), upStr, sizeof(upStr));

  double lat, lon;
  uint32_t ageMs;
  uint8_t src = locBest(lat, lon, ageMs);

  snprintf(l[0], sizeof(l[0]), "NODE %s  SF%d  %-6s 1/6",
           MY_ID, (int)LORA_SF, roverModeName(roverMode));

  snprintf(l[1], sizeof(l[1]), "Peers %u  Routes %u%s",
           (unsigned)neighborActiveCount(), (unsigned)routeValidCount(),
           radioOk ? "" : " !RF");

  if (src == LOC_NONE) {
    snprintf(l[2], sizeof(l[2]), "LOC   none yet");
    snprintf(l[3], sizeof(l[3]), "GPS %s sat%d nmea%lu",
             gpsHasFix ? "FIX" : "--", gpsSats, (unsigned long)gpsSentences);
  } else {
    char ageStr[8];
    fmtAge(ageMs, ageStr, sizeof(ageStr));
    snprintf(l[2], sizeof(l[2]), "LOC %s %s", locSrcName(src), ageStr);
    snprintf(l[3], sizeof(l[3]), "%.5f %.5f", lat, lon);
  }

  snprintf(l[4], sizeof(l[4]), "up %s  heap %luk", upStr,
           (unsigned long)(ESP.getFreeHeap() / 1024));

  oledPush(l);
}

void drawPage1() {
  char l[5][26];
  snprintf(l[0], sizeof(l[0]), "-- LINKS --   %u up 2/6",
           (unsigned)neighborActiveCount());

  uint8_t row = 1;
  for (uint8_t i = 0; i < MAX_NEIGHBORS && row < 5; i++) {
    if (!neighbors[i].used) continue;
    char ageStr[8];
    fmtAge(millis() - neighbors[i].lastSeen, ageStr, sizeof(ageStr));
    if (neighbors[i].active)
      snprintf(l[row], sizeof(l[row]), "%-2s %s %4d %s",
               neighbors[i].id, sigBars(neighbors[i].rssi),
               neighbors[i].rssi, ageStr);
    else
      snprintf(l[row], sizeof(l[row]), "%-2s LOST     %s",
               neighbors[i].id, ageStr);
    row++;
  }
  if (row == 1) { snprintf(l[1], sizeof(l[1]), "searching..."); row = 2; }
  while (row < 5) { l[row][0] = '\0'; row++; }
  oledPush(l);
}

void drawPage2() {
  char l[5][26];
  snprintf(l[0], sizeof(l[0]), "-- ROUTES --  %u   3/6",
           (unsigned)routeValidCount());

  uint8_t row = 1;
  for (uint8_t i = 0; i < MAX_ROUTES && row < 5; i++) {
    if (!routes[i].used) continue;
    snprintf(l[row], sizeof(l[row]), "%-2s via %-2s %uhop %s",
             routes[i].dest, routes[i].nextHop, (unsigned)routes[i].hops,
             routes[i].valid ? "ok" : "X");
    row++;
  }
  if (row == 1) { snprintf(l[1], sizeof(l[1]), "no routes yet"); row = 2; }
  while (row < 5) { l[row][0] = '\0'; row++; }
  oledPush(l);
}

void drawPage3() {
  char l[5][26];
  snprintf(l[0], sizeof(l[0]), "-- POSITIONS --   4/6");

  uint8_t row = 1;
  for (uint8_t i = 0; i < MAX_NEIGHBORS && row < 5; i++) {
    if (!neighbors[i].used) continue;
    if (neighbors[i].hasLoc)
      snprintf(l[row], sizeof(l[row]), "%-2s %.4f %.4f",
               neighbors[i].id, neighbors[i].lat, neighbors[i].lon);
    else
      snprintf(l[row], sizeof(l[row]), "%-2s no fix", neighbors[i].id);
    row++;
  }
  if (row == 1) { snprintf(l[1], sizeof(l[1]), "no peers heard"); row = 2; }
  while (row < 5) { l[row][0] = '\0'; row++; }
  oledPush(l);
}

void drawPage4() {
  char l[5][26];
  snprintf(l[0], sizeof(l[0]), "-- GPS / TEAM --  5/6");

  if (gpsSentences == 0)
    snprintf(l[1], sizeof(l[1]), "GPS SILENT - wiring!");
  else if (!gpsHasFix)
    snprintf(l[1], sizeof(l[1]), "GPS no fix sat%d", gpsSats);
  else
    snprintf(l[1], sizeof(l[1]), "GPS FIX  sat%d", gpsSats);

  char fixAge[8];
  if (gpsFixTime) {
    fmtAge(millis() - gpsFixTime, fixAge, sizeof(fixAge));
    snprintf(l[2], sizeof(l[2]), "nmea %lu  fix %s",
             (unsigned long)gpsSentences, fixAge);
  } else {
    snprintf(l[2], sizeof(l[2]), "nmea %lu  no fix yet",
             (unsigned long)gpsSentences);
  }

  uint8_t row = 3;
  for (uint8_t i = 0; i < MAX_NEIGHBORS + 1 && row < 5; i++) {
    if (!peerRep[i].used || !peerRep[i].status[0]) continue;
    snprintf(l[row], sizeof(l[row]), "%-2s %.14s",
             peerRep[i].id, peerRep[i].status);
    row++;
  }
  while (row < 5) { l[row][0] = '\0'; row++; }
  oledPush(l);
}

// ---- page 5: ROVER STATUS - new in Phase 8 --------------------------------
void drawPage5() {
  char l[5][26];
  snprintf(l[0], sizeof(l[0]), "-- ROVER --       6/6");
  snprintf(l[1], sizeof(l[1]), "mode: %s", roverModeName(roverMode));

  if (ultrasonicCm < 0) snprintf(l[2], sizeof(l[2]), "range: clear/unknown");
  else                  snprintf(l[2], sizeof(l[2]), "range: %dcm%s",
                                 ultrasonicCm,
                                 (ultrasonicCm < AUTO_OBSTACLE_CM) ? " !" : "");

  int batt = roverBatteryPercent();
  if (batt < 0) snprintf(l[3], sizeof(l[3]), "batt: n/a (no divider?)");
  else          snprintf(l[3], sizeof(l[3]), "batt: %d%%", batt);

  snprintf(l[4], sizeof(l[4]), "drive: %s",
           manualDriving ? "ACTIVE" :
           (roverMode == ROVER_AUTO ? (autoState == RA_FORWARD ? "auto-fwd" :
                                       autoState == RA_BACK    ? "auto-back" : "auto-turn")
                                     : "stopped"));
  oledPush(l);
}

void drawSosScreen() {
  char l[5][26];
  bool mine = (strcmp(sosVictim, MY_ID) == 0);
  snprintf(l[0], sizeof(l[0]), "***   S O S   ***");
  snprintf(l[1], sizeof(l[1]), mine ? "FROM THIS NODE (%s)" : "VICTIM:  %s", sosVictim);
  if (sosLat == 0 && sosLon == 0)
    snprintf(l[2], sizeof(l[2]), "position: NO FIX");
  else
    snprintf(l[2], sizeof(l[2]), "%.5f %.5f", sosLat, sosLon);
  snprintf(l[3], sizeof(l[3]), "%.20s", sosText[0] ? sosText : "MAYDAY");
  uint32_t left = (millis() - sosAlertStart < SOS_SCREEN_MS)
                  ? (SOS_SCREEN_MS - (millis() - sosAlertStart)) / 1000UL : 0;
  if (mine && sosAcks[0])
    snprintf(l[4], sizeof(l[4]), "heard by: %.11s", sosAcks);
  else
    snprintf(l[4], sizeof(l[4]), "clears %lus - hold btn", (unsigned long)left);
  oledPush(l);
}

void drawUI() {
  if (sosAlert) { drawSosScreen(); return; }
  if      (uiPage == 1) drawPage1();
  else if (uiPage == 2) drawPage2();
  else if (uiPage == 3) drawPage3();
  else if (uiPage == 4) drawPage4();
  else if (uiPage == 5) drawPage5();
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
      snprintf(pos, sizeof(pos), "-");
    Serial.printf("%-4s %-6d %-6.1f %-7lu %-25s %s\n",
                  neighbors[i].id, neighbors[i].rssi, (double)neighbors[i].snr,
                  (unsigned long)((millis() - neighbors[i].lastSeen) / 1000UL),
                  pos, locSrcName(neighbors[i].locSrc));
  }
  if (!any) Serial.println("(no neighbours yet)");
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
  Serial.printf("  GPS module: %s  sats=%d  nmea lines=%lu",
                gpsHasFix ? "FIX" : "no fix", gpsSats, (unsigned long)gpsSentences);
  if (gpsFixTime) Serial.printf("  last fix %lus ago",
                                (unsigned long)((millis() - gpsFixTime) / 1000UL));
  Serial.println();
  if (gpsSentences == 0)
    Serial.println("             ^ no NMEA at all - check GPS TX -> GPIO16 and 9600 baud");
  Serial.println("  phone     : n/a - this node has no captive portal");
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
  double lat, lon; uint32_t ageMs;
  Serial.printf(" loc=%s gps=%s/%d nmea=%lu maxloop=%lums minheap=%lu stack=%lu txstuck=%lu wedge=%lu rst=%s",
                locSrcName(locBest(lat, lon, ageMs)),
                gpsHasFix ? "FIX" : "nofix", gpsSats,
                (unsigned long)gpsSentences,
                (unsigned long)maxLoopMs,
                (unsigned long)esp_get_minimum_free_heap_size(),
                (unsigned long)uxTaskGetStackHighWaterMark(NULL),
                (unsigned long)statTxStuck,
                (unsigned long)statWedge,
                resetReasonShort());
  int batt = roverBatteryPercent();
  Serial.printf(" mode=%s range=%dcm batt=%s\n",
                roverModeName(roverMode), ultrasonicCm,
                batt < 0 ? "n/a" : String(batt).c_str());
  maxLoopMs = 0;
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
    char dest[2] = { (char)(c - 32), '\0' };
    sendTestTo(dest);

  } else if (c == 't') {
    autoData = !autoData;
    if (autoData && !autoTarget[0]) {
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

  } else if (c == 'S') {
    sosTrigger("SERIAL");

  } else if (c == 'C') {
    sosClearAlert("serial C");

  } else if (c == '1') { sendReport("VICTIM_FOUND");
  } else if (c == '2') { sendReport("MEDICAL");
  } else if (c == '3') { sendReport("BLOCKED");
  } else if (c == '4') { sendReport("DANGER");

  } else if (c == '5') { sendStatus("AVAILABLE");
  } else if (c == '6') { sendStatus("SEARCHING");
  } else if (c == '7') { sendStatus("NEED_ASSIST");
  } else if (c == '8') { sendStatus("EMERGENCY");

  } else if (c == 'R') {
    manualRescan("serial");

  } else if (c == 'T') {
    radioTest = !radioTest;
    Serial.printf("[test] radio test mode %s - plain PING every 3 s.\n",
                  radioTest ? "ON" : "off");

  } else if (c == 'v') {
    verboseRx = !verboseRx;
    Serial.printf("[ui] per-packet rx logging %s\n", verboseRx ? "ON" : "off");

  } else if (c == 'N') {
    Serial.println("\n---- RAW NMEA (5 s) --------------------------------");
    uint32_t until = millis() + 5000;
    while (millis() < until) {
      esp_task_wdt_reset();
      while (Serial2.available()) Serial.write((char)Serial2.read());
    }
    Serial.println("\n----------------------------------------------------\n");

  } else if (c == 'm') {
    uint8_t next = (uint8_t)((roverMode + 1) % 3);
    roverSetMode(next, "serial 'm'");

  } else if (c == 'i') {
    roverManualDrive("FWD");
  } else if (c == 'k') {
    roverManualDrive("BACK");
  } else if (c == 'j') {
    roverManualDrive("LEFT");
  } else if (c == 'l') {
    roverManualDrive("RIGHT");
  } else if (c == 'o') {
    roverManualDrive("STOP");

  } else if (c == 'u') {
    Serial.printf("[rover] ultrasonic: %dcm\n", ultrasonicCm);

  } else if (c == 'h' || c == '?') {
    Serial.println("commands: n=neighbours r=routes g=GPS s=stats  a|b|c=send msg to that node");
    Serial.println("          t=toggle repeat send  p=next OLED page  x=bad frame");
    Serial.println("  SOS/E-STOP:  S=trigger SOS  C=clear alert  (button always E-STOPs)");
    Serial.println("  report 1=VictimFound 2=Medical 3=Blocked 4=Danger");
    Serial.println("  status 5=Available 6=Searching 7=NeedAssist 8=Emergency");
    Serial.println("  diag:  v=toggle rx log  N=raw NMEA dump (5s)  R=manual rescan/reconnect");
    Serial.println("  rover: m=cycle mode  i/k/j/l=fwd/back/left/right  o=stop  u=ultrasonic reading");
  }
}

// ===========================================================================
//  SETUP
// ===========================================================================
void setup() {
  setCpuFrequencyMhz(CPU_MHZ);

  Serial.begin(SERIAL_BAUD);
  delay(200);

  pinMode(PIN_SOS_BUTTON, INPUT_PULLUP);
  motorInit();
  ultrasonicInit();

  randomSeed(((uint32_t)analogRead(PIN_ENTROPY) << 16) ^ micros());

  memset(seenKeys, 0, sizeof(seenKeys));
  neighborInit();
  routeInit();
  for (uint8_t i = 0; i < MAX_NEIGHBORS + 1; i++) peerRep[i].used = false;
  peerRepIndex(MY_ID);

  // STEP 1: display
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setTimeOut(I2C_TIMEOUT_MS);
  Wire.setClock(I2C_HZ);
  oledOk = display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  if (!oledOk) oledOk = display.begin(SSD1306_SWITCHCAPVCC, 0x3D);
  if (oledOk) {
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
  } else {
    Serial.println("[oled] init FAILED - check SDA21 / SCL22");
  }
  oledBanner("Booting...", "Rover " MY_ID);

  Serial.printf("\n[boot] Node %s (Rover) fw v%u  heap=%lu\n",
                MY_ID, (unsigned)FW_VERSION, (unsigned long)ESP.getFreeHeap());
  Serial.printf("[boot] last reset: %s\n", resetReasonName());
  Serial.println("\n############################################################");
  Serial.printf ("#  WHY DID THIS NODE LAST RESTART?\n");
  Serial.printf ("#     %s\n", resetReasonName());
  Serial.println("############################################################\n");

  Serial.println("############################################################");
  Serial.println("#  RADIO PHY - MUST BE IDENTICAL ON ALL 3 NODES, THE ROVER, AND THE PI");
  Serial.printf ("#     freq %ld Hz    SF%d    BW %ld Hz    CR 4/%d\n",
                 (long)LORA_FREQ, (int)LORA_SF, (long)LORA_BW, (int)LORA_CR);
  Serial.printf ("#     sync 0x%02X    preamble %d    CRC on    TX %d dBm\n",
                 (int)LORA_SYNCWORD, (int)LORA_PREAMBLE, (int)LORA_TXPOWER);
  Serial.printf ("#     CPU %u MHz\n", (unsigned)getCpuFrequencyMhz());
  Serial.println("#  Pi must match: SF/BW/CR/sync in development/pi/sx1278.py");
  Serial.println("############################################################\n");

  Serial.println("############################################################");
  Serial.println("#  ROVER SAFETY CHECK - do this BEFORE the wheels touch the ground");
  Serial.println("#    Mode boots as MANUAL (will not move on its own).");
  Serial.println("#    With wheels off the ground: press i/k/j/l on serial and confirm");
  Serial.println("#    forward/back/left/right are each what you expect, THEN test 'm'");
  Serial.println("#    to reach AUTO near a real obstacle.");
  Serial.println("############################################################\n");

  // STEP 2: GPS serial
  Serial2.setRxBufferSize(1024);
  Serial2.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
  Serial.printf("[gps] Serial2 %d baud on RX%d/TX%d (1KB rx buffer)\n",
                GPS_BAUD, GPS_RX_PIN, GPS_TX_PIN);

  // STEP 3: radio
  lastTxOkMs = millis();
  if (radioBegin()) {
    Serial.printf("[radio] LoRa OK  SF%d BW125 CRC=on sync=0x%02X pwr=%ddBm\n",
                  (int)LORA_SF, (int)LORA_SYNCWORD, (int)LORA_TXPOWER);
    char l1[24];
    snprintf(l1, sizeof(l1), "SF%d CRC on", (int)LORA_SF);
    oledBanner("LoRa OK", l1);
  } else {
    Serial.println("[radio] LoRa FAIL - check SPI wiring and 3.3V (never 5V)");
    oledBanner("LoRa FAIL", "check SPI / 3V3");
  }

  {
    char rl[24];
    snprintf(rl, sizeof(rl), "rst:%s", resetReasonShort());
    oledBanner("Last restart was", rl);
  }

  wdtBegin();

  hbTimer.begin(3000UL, 500UL + (uint32_t)random(0, 1200));
  gpsTimer.begin(GPS_INTERVAL_MS, 4000UL + (uint32_t)random(0, GPS_JITTER_MS));
  rtTimer.begin(RT_INTERVAL_MS, 2000UL + (uint32_t)random(0, RT_JITTER_MS));
  pageTimer.begin(UI_PAGE_MS, UI_PAGE_MS);
  autoTimer.begin(AUTO_DATA_MS, AUTO_DATA_MS);
  uiTimer.begin(OLED_REFRESH_MS, OLED_REFRESH_MS);
  statTimer.begin(STAT_LOG_MS, STAT_LOG_MS);
  retryTimer.begin(RADIO_RETRY_MS, RADIO_RETRY_MS);
  roverTelemetryTimer.begin(ROVER_TELEMETRY_MS, 5000UL + (uint32_t)random(0, ROVER_TELEMETRY_JITTER_MS));

  Serial.println("[boot] ready. type 'h' for commands. mode=MANUAL.");
}

// ===========================================================================
//  LOOP   -   no delay() anywhere below this line (the ultrasonic trigger's
//  ~12us pulse is the one exception, and it is bounded and documented above)
// ===========================================================================
void loop() {
  esp_task_wdt_reset();
  loopStartMs = millis();

  // 1. drain the GPS serial buffer (never blocks)
  gpsService();

  // 1b. SOS button / E-STOP (edge detected) and the SOS burst/auto-clear
  //     state machine
  buttonService();
  sosService();

  // 1c. drive the rover: ultrasonic ping/read, AUTO bump-turn or MANUAL
  //     pulse timeout or RELAY hold - all non-blocking
  roverService();

  // 2. receive LoRa
  handleRx();

  // 3. age out silent neighbours
  char lost[4];
  while (neighborPrune(lost, sizeof(lost)))
    Serial.printf("[mesh] LOST %s (no packet for %lus)\n",
                  lost, (unsigned long)(NEIGHBOR_TIMEOUT_MS / 1000UL));

  // 3b. invalidate routes whose advertiser has gone quiet - self-healing
  char deadDest[4];
  while (routeExpire(deadDest, sizeof(deadDest)))
    Serial.printf("[route] LOST %s - no advert for %lus, invalidating  <<< SELF-HEALING\n",
                  deadDest, (unsigned long)(ROUTE_TIMEOUT_MS / 1000UL));

  // 4. periodic broadcasts
  if (radioTest && millis() - testLast > 3000UL) {
    testLast = millis();
    char t[48];
    snprintf(t, sizeof(t), "PING %s %lu", MY_ID, (unsigned long)(millis() / 1000UL));
    radioEnqueue(t);
    Serial.printf("[test] sent \"%s\"\n", t);
  }

  if (hbTimer.due())             sendHeartbeat();
  if (gpsTimer.due())            sendLocation();
  if (rtTimer.due())             sendRoutes();
  if (roverTelemetryTimer.due()) sendRoverTelemetry();
  if (autoData && autoTarget[0] && autoTimer.due()) sendTestTo(autoTarget);

  // 5. transmit pump
  radioService();

  // 6. display + periodic statistics
  if (pageTimer.due()) uiPage = (uint8_t)((uiPage + 1) % UI_PAGES);
  if (uiTimer.due())   drawUI();
  if (statTimer.due()) printStats();

  // 7. recover a radio that failed at boot, or force a reinit if it wedged
  if (!radioOk && retryTimer.due()) {
    Serial.println("[radio] retrying init...");
    if (radioBegin()) Serial.println("[radio] recovered");
  }
  radioWatchdog();

  // 8. serial commands
  handleSerial();

  // 9. how long did this pass take?
  uint32_t dt = millis() - loopStartMs;
  if (dt > maxLoopMs) maxLoopMs = dt;
}
