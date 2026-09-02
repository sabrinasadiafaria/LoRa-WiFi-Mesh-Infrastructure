#ifndef NODE_CORE_H
#define NODE_CORE_H

#include <Arduino.h>
#include <esp_task_wdt.h>

#include "config.h"
#include "scheduler.h"
#include "packet.h"
#include "radio_layer.h"
#include "neighbors.h"
#include "oled_ui.h"

// ============================================================================
//  Phase 1 - Shared Core - NODE BEHAVIOUR
//
//  This is the entire node program. Node A / Node B / Node C differ ONLY by
//  the two #defines at the top of their sketch - there is no duplicated logic
//  to keep in sync (the old project had the same neighbour code copy-pasted
//  into six files, which had already drifted apart).
//
//  What a Phase 1 node does:
//    * broadcasts a heartbeat  HB | uptime,freeheap,fwversion
//    * learns its neighbours from other nodes' heartbeats (RSSI + SNR)
//    * ages neighbours out after NEIGHBOR_TIMEOUT_MS
//    * rejects any frame with a bad checksum or wrong protocol version
//    * shows live status on the OLED and a soak-test line on serial
//    * never blocks, never hangs, feeds a hardware watchdog
//
//  Routing / multi-hop / GPS / SOS / portal arrive in later phases and plug
//  into the same loop.
// ============================================================================

RadioLayer     radio;
NeighborTable  neighbors;
OledUI         oled;
SeenCache      seen;

Interval hbTimer;      // heartbeat broadcast
Interval uiTimer;      // OLED refresh
Interval statTimer;    // periodic serial statistics
Interval retryTimer;   // radio re-init attempts if it failed at boot

// ---------------------------------------------------------------- watchdog --
static void wdtBegin() {
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

// --------------------------------------------------------------- heartbeat --
static void sendHeartbeat() {
  char payload[48];
  snprintf(payload, sizeof(payload), "%lu,%lu,%u",
           (unsigned long)(millis() / 1000UL),
           (unsigned long)ESP.getFreeHeap(),
           (unsigned)FW_VERSION);

  char frame[MAX_PACKET_LEN];
  if (pktBuild(frame, sizeof(frame), "HB", MY_ID, "*",
               radio.nextMsgId(), 0, payload)) {
    radio.enqueue(frame);
  }

  // Re-jitter every period so two nodes that happen to line up drift apart
  // again instead of colliding forever.
  hbTimer.setPeriod(HB_INTERVAL_MS + (uint32_t)random(0, HB_JITTER_MS));
}

// ---------------------------------------------------------------- receive ---
static void handleRx() {
  Packet p;
  if (!radio.poll(p)) return;

  if (strcmp(p.src, MY_ID) == 0) return;                 // our own echo
  if (seen.seenOrAdd(p.src, p.msgId)) return;            // duplicate

  if (strcmp(p.type, "HB") == 0) {
    unsigned long up = 0, hp = 0;
    unsigned      fw = 0;
    sscanf(p.payload, "%lu,%lu,%u", &up, &hp, &fw);

    int ev = neighbors.update(p.src, p.rssi, p.snr, (uint32_t)up, (uint32_t)hp);
    if      (ev == NB_NEW)         Serial.printf("[mesh] NEW neighbour %s  %d dBm\n", p.src, p.rssi);
    else if (ev == NB_RECONNECTED) Serial.printf("[mesh] RECONNECTED %s  %d dBm\n", p.src, p.rssi);
    else if (ev == NB_FULL)        Serial.println(F("[mesh] neighbour table FULL"));
  }

  Serial.printf("[rx] %s from %s id=%u ttl=%u rssi=%d snr=%.1f : %s\n",
                p.type, p.src, (unsigned)p.msgId, (unsigned)p.ttl,
                p.rssi, (double)p.snr, p.payload);
}

// -------------------------------------------------------------------- UI ----
static void drawUI() {
  char l[5][24];
  char list[20];
  neighbors.activeList(list, sizeof(list));

  snprintf(l[0], sizeof(l[0]), "NODE %s   fw%u %s",
           MY_ID, (unsigned)FW_VERSION, radio.ok() ? "" : "!RF");
  snprintf(l[1], sizeof(l[1]), "Conn: %s", list);

  const Neighbor *f = neighbors.firstActive();
  if (f) snprintf(l[2], sizeof(l[2]), "%s %ddBm snr%.0f", f->id, f->rssi, (double)f->snr);
  else   snprintf(l[2], sizeof(l[2]), "scanning...");

  snprintf(l[3], sizeof(l[3]), "tx%lu rx%lu bad%lu",
           (unsigned long)radio.txCount(),
           (unsigned long)radio.rxCount(),
           (unsigned long)radio.badCount());
  snprintf(l[4], sizeof(l[4]), "heap %lu  up%lus",
           (unsigned long)ESP.getFreeHeap(),
           (unsigned long)(millis() / 1000UL));

  oled.clear();
  for (uint8_t i = 0; i < 5; i++) oled.line(i, l[i]);
  oled.show();
}

// ------------------------------------------------------- serial commands ----
static void printNeighbours() {
  Serial.println(F("\n---- NEIGHBOURS ----------------------------------"));
  Serial.println(F("ID   RSSI   SNR    AGE(s)  UPTIME(s)  THEIR HEAP  STATE"));
  bool any = false;
  for (uint8_t i = 0; i < MAX_NEIGHBORS; i++) {
    const Neighbor *n = neighbors.at(i);
    if (!n) continue;
    any = true;
    Serial.printf("%-4s %-6d %-6.1f %-7lu %-10lu %-11lu %s\n",
                  n->id, n->rssi, (double)n->snr,
                  (unsigned long)((millis() - n->lastSeen) / 1000UL),
                  (unsigned long)n->uptime, (unsigned long)n->heap,
                  n->active ? "ACTIVE" : "lost");
  }
  if (!any) Serial.println(F("(none discovered yet)"));
  Serial.println(F("--------------------------------------------------\n"));
}

static void printStats() {
  Serial.printf("[stat] up=%lus heap=%lu neigh=%u tx=%lu rx=%lu bad=%lu drop=%lu q=%u\n",
                (unsigned long)(millis() / 1000UL),
                (unsigned long)ESP.getFreeHeap(),
                (unsigned)neighbors.activeCount(),
                (unsigned long)radio.txCount(),
                (unsigned long)radio.rxCount(),
                (unsigned long)radio.badCount(),
                (unsigned long)radio.dropCount(),
                (unsigned)radio.queued());
}

static void handleSerial() {
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
    if (pktBuild(frame, sizeof(frame), "HB", MY_ID, "*",
                 radio.nextMsgId(), 0, "0,0,1")) {
      size_t len = strlen(frame);
      frame[len - 1] = (frame[len - 1] == '0') ? '1' : '0';   // corrupt checksum
      radio.enqueue(frame);
      Serial.println(F("[test] queued a BAD-CHECKSUM frame - peers must reject it"));
    }

  } else if (c == 'h' || c == '?') {
    Serial.println(F("commands:  n=neighbours  s=stats  x=send bad-checksum frame  h=help"));
  }
}

// ----------------------------------------------------------------- setup ----
inline void nodeSetup() {
  Serial.begin(SERIAL_BAUD);
  delay(200);

  pinMode(PIN_SOS_BUTTON, INPUT_PULLUP);      // used from Phase 3

  // Seed from a floating ADC1 pin, not GPIO 0. GPIO 0 is a strapping pin and
  // reads nearly the same on every board, so the old code gave all three nodes
  // correlated "random" jitter.
  randomSeed(((uint32_t)analogRead(PIN_ENTROPY) << 16) ^ micros());

  seen.begin();
  neighbors.begin();

  if (!oled.begin()) Serial.println(F("[oled] init FAILED - check SDA21/SCL22"));
  oled.banner("Booting...", "Node " MY_ID);

  Serial.printf("\n[boot] Node %s fw v%u  heap=%lu\n",
                MY_ID, (unsigned)FW_VERSION, (unsigned long)ESP.getFreeHeap());

  if (radio.begin()) {
    Serial.printf("[radio] LoRa OK  SF%d BW125 CRC=on sync=0x%02X pwr=%ddBm\n",
                  (int)LORA_SF, (int)LORA_SYNCWORD, (int)LORA_TXPOWER);
    char l1[24];
    snprintf(l1, sizeof(l1), "SF%d CRC on", (int)LORA_SF);
    oled.banner("LoRa OK", l1);
  } else {
    // Deliberately NOT while(1). The old sketches hung here with a frozen
    // screen and no watchdog; this one keeps running and keeps retrying.
    Serial.println(F("[radio] LoRa FAIL - check SPI wiring and 3.3V (never 5V)"));
    oled.banner("LoRa FAIL", "check SPI / 3V3");
  }

  wdtBegin();

  hbTimer.begin(HB_INTERVAL_MS, (uint32_t)random(0, HB_JITTER_MS));  // staggered start
  uiTimer.begin(OLED_REFRESH_MS, OLED_REFRESH_MS);
  statTimer.begin(STAT_LOG_MS, STAT_LOG_MS);
  retryTimer.begin(5000UL, 5000UL);

  Serial.println(F("[boot] ready. type 'h' for commands."));
}

// ------------------------------------------------------------------ loop ----
inline void nodeLoop() {
  esp_task_wdt_reset();

  handleRx();

  char lost[4];
  while (neighbors.prune(lost, sizeof(lost)))
    Serial.printf("[mesh] LOST %s (no heartbeat for %lus)\n",
                  lost, (unsigned long)(NEIGHBOR_TIMEOUT_MS / 1000UL));

  if (hbTimer.due()) sendHeartbeat();

  radio.service();

  if (uiTimer.due())   drawUI();
  if (statTimer.due()) printStats();

  if (!radio.ok() && retryTimer.due()) {
    Serial.println(F("[radio] retrying init..."));
    if (radio.retry()) Serial.println(F("[radio] recovered"));
  }

  handleSerial();
}

#endif
