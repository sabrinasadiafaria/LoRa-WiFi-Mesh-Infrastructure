#ifndef NEIGHBORS_H
#define NEIGHBORS_H

#include <Arduino.h>
#include <string.h>
#include "config.h"

// ============================================================================
//  Phase 1 - Shared Core - NEIGHBOUR TABLE
//
//  One table, used by every node. Replaces the four slightly different
//  copy-pasted versions in phase 6 / phase 10 / phase 11 (which had already
//  drifted apart: 15 s vs 30 s timeouts, substring(5) vs replace("NODE_","")).
//
//  Fixed-size, char-based - no String members, so entries do not fragment the
//  heap as nodes come and go.
// ============================================================================

struct Neighbor {
  char     id[4];
  int      rssi;
  float    snr;
  uint32_t lastSeen;      // millis()
  uint32_t uptime;        // seconds, as reported by that node
  uint32_t heap;          // free bytes, as reported by that node
  bool     used;
  bool     active;
};

enum NeighborEvent { NB_UPDATED = 0, NB_NEW = 1, NB_RECONNECTED = 2, NB_FULL = -1 };

class NeighborTable {
public:

  void begin() {
    for (uint8_t i = 0; i < MAX_NEIGHBORS; i++) {
      _n[i].used = false;
      _n[i].active = false;
      _n[i].id[0] = '\0';
    }
  }

  // Record a heartbeat from `id`. Returns a NeighborEvent so the caller can
  // log NEW / RECONNECTED without the table having to know about Serial.
  int update(const char *id, int rssi, float snr, uint32_t uptime, uint32_t heap) {
    if (!id || !*id) return NB_UPDATED;
    uint32_t now = millis();

    for (uint8_t i = 0; i < MAX_NEIGHBORS; i++) {
      if (_n[i].used && strcmp(_n[i].id, id) == 0) {
        bool wasActive = _n[i].active;
        _n[i].rssi = rssi;  _n[i].snr = snr;
        _n[i].lastSeen = now;
        _n[i].uptime = uptime;  _n[i].heap = heap;
        _n[i].active = true;
        return wasActive ? NB_UPDATED : NB_RECONNECTED;
      }
    }

    for (uint8_t i = 0; i < MAX_NEIGHBORS; i++) {
      if (!_n[i].used) {
        strncpy(_n[i].id, id, sizeof(_n[i].id) - 1);
        _n[i].id[sizeof(_n[i].id) - 1] = '\0';
        _n[i].rssi = rssi;  _n[i].snr = snr;
        _n[i].lastSeen = now;
        _n[i].uptime = uptime;  _n[i].heap = heap;
        _n[i].used = true;  _n[i].active = true;
        return NB_NEW;
      }
    }
    return NB_FULL;     // table full - reported, not silently dropped
  }

  // Marks ONE stale neighbour inactive per call and copies its id into
  // `lostId`. Call in a while() loop to drain all of them.
  bool prune(char *lostId, size_t n) {
    uint32_t now = millis();
    for (uint8_t i = 0; i < MAX_NEIGHBORS; i++) {
      if (_n[i].used && _n[i].active &&
          (now - _n[i].lastSeen > NEIGHBOR_TIMEOUT_MS)) {
        _n[i].active = false;
        if (lostId && n) {
          strncpy(lostId, _n[i].id, n - 1);
          lostId[n - 1] = '\0';
        }
        return true;
      }
    }
    return false;
  }

  uint8_t activeCount() const {
    uint8_t c = 0;
    for (uint8_t i = 0; i < MAX_NEIGHBORS; i++) if (_n[i].used && _n[i].active) c++;
    return c;
  }

  // Comma-separated list of active neighbours, e.g. "B,C" - or "none".
  void activeList(char *out, size_t n) const {
    if (!out || n == 0) return;
    out[0] = '\0';
    size_t used = 0;
    for (uint8_t i = 0; i < MAX_NEIGHBORS; i++) {
      if (!_n[i].used || !_n[i].active) continue;
      size_t idLen = strlen(_n[i].id);
      size_t need  = idLen + (used ? 1 : 0);
      if (used + need + 1 >= n) break;
      if (used) out[used++] = ',';
      memcpy(out + used, _n[i].id, idLen);
      used += idLen;
      out[used] = '\0';
    }
    if (used == 0) {
      strncpy(out, "none", n - 1);
      out[n - 1] = '\0';
    }
  }

  const Neighbor *firstActive() const {
    for (uint8_t i = 0; i < MAX_NEIGHBORS; i++)
      if (_n[i].used && _n[i].active) return &_n[i];
    return NULL;
  }

  const Neighbor *at(uint8_t i) const {
    if (i >= MAX_NEIGHBORS || !_n[i].used) return NULL;
    return &_n[i];
  }

private:
  Neighbor _n[MAX_NEIGHBORS];
};

#endif
