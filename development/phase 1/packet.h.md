#ifndef PACKET_H
#define PACKET_H

#include <Arduino.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include "config.h"

// ============================================================================
//  Phase 1 - Shared Core - PACKET FRAMING
//  Implements docs/PACKET_SPEC.md v1:
//
//      v<VER>|<TYPE>|<SRC>|<DEST>|<MSGID>|<TTL>|<PAYLOAD>|<CHK>
//
//  All char buffers - no String anywhere in the receive/parse/forward path,
//  so the ESP32 heap stays flat over a long run.
// ============================================================================

struct Packet {
  uint8_t  ver;
  char     type[8];
  char     src[4];
  char     dest[4];
  uint16_t msgId;
  uint8_t  ttl;
  char     payload[MAX_PAYLOAD_LEN];
  int      rssi;     // filled in by the radio layer
  float    snr;      // filled in by the radio layer
};

// XOR of the first n bytes.
inline uint8_t pktChecksum(const char *s, size_t n) {
  uint8_t c = 0;
  for (size_t i = 0; i < n; i++) c ^= (uint8_t)s[i];
  return c;
}

// '|' is the field separator, so it must never appear inside a field.
// Call this on any free text before putting it in a payload.
inline void pktSanitize(char *s) {
  for (char *p = s; *p; ++p) {
    if (*p == '|' || *p == '\\' || *p == '\r' || *p == '\n') *p = '/';
  }
}

// Build a frame into `out`. Returns the length written, or 0 if it would not fit.
inline size_t pktBuild(char *out, size_t outSize,
                       const char *type, const char *src, const char *dest,
                       uint16_t msgId, uint8_t ttl, const char *payload) {
  int n = snprintf(out, outSize, "v%u|%s|%s|%s|%u|%u|%s",
                   (unsigned)PROTO_VERSION, type, src, dest,
                   (unsigned)msgId, (unsigned)ttl,
                   payload ? payload : "");
  if (n < 0 || (size_t)n + 4 > outSize) return 0;      // need room for "|xx\0"

  uint8_t chk = pktChecksum(out, (size_t)n);
  int m = snprintf(out + n, outSize - (size_t)n, "|%02x", chk);
  if (m < 0) return 0;
  return (size_t)(n + m);
}

// Parse a frame IN PLACE (the buffer is modified). Returns false and leaves
// `p` untouched if the frame is malformed, the version is wrong, or the
// checksum does not match.
inline bool pktParse(char *in, Packet &p) {
  size_t len = strlen(in);
  if (len < 12 || len >= MAX_PACKET_LEN) return false;

  char *lastBar = strrchr(in, '|');
  if (!lastBar) return false;
  if (strlen(lastBar + 1) != 2) return false;

  uint8_t want = (uint8_t)strtoul(lastBar + 1, NULL, 16);
  *lastBar = '\0';                                  // body ends here
  if (pktChecksum(in, strlen(in)) != want) return false;

  // Split the body on the first 6 pipes. Field 7 (payload) keeps whatever is
  // left, so a stray separator in a payload cannot shift the other fields.
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

  strncpy(p.type, f[1], sizeof(p.type) - 1);  p.type[sizeof(p.type) - 1] = '\0';
  strncpy(p.src,  f[2], sizeof(p.src)  - 1);  p.src[sizeof(p.src)   - 1] = '\0';
  strncpy(p.dest, f[3], sizeof(p.dest) - 1);  p.dest[sizeof(p.dest) - 1] = '\0';
  p.msgId = (uint16_t)strtoul(f[4], NULL, 10);
  p.ttl   = (uint8_t) strtoul(f[5], NULL, 10);
  strncpy(p.payload, f[6], sizeof(p.payload) - 1);
  p.payload[sizeof(p.payload) - 1] = '\0';

  if (p.type[0] == '\0' || p.src[0] == '\0' || p.dest[0] == '\0') return false;
  return true;
}

// ---------------------------------------------------------------------------
//  Duplicate suppression.
//  SRC + MSGID uniquely identifies a packet. A small ring of recently seen
//  keys stops us from acting on a repeat and - from Phase 2 - stops us from
//  forwarding the same packet twice (the duplicate-storm bug in phase 8/9,
//  where every node with a route re-broadcast the same DATA packet).
// ---------------------------------------------------------------------------
struct SeenCache {
  uint32_t keys[SEEN_CACHE_SIZE];
  uint8_t  idx;

  void begin() { memset(keys, 0, sizeof(keys)); idx = 0; }

  static uint32_t key(const char *src, uint16_t msgId) {
    uint32_t h = 2166136261u;                       // FNV-1a over the node id
    for (const char *p = src; *p; ++p) { h ^= (uint8_t)*p; h *= 16777619u; }
    uint32_t k = (h << 16) ^ msgId;
    return k ? k : 1;                               // 0 means "empty slot"
  }

  // Returns true if this packet was already seen; otherwise records it.
  bool seenOrAdd(const char *src, uint16_t msgId) {
    uint32_t k = key(src, msgId);
    for (uint8_t i = 0; i < SEEN_CACHE_SIZE; i++) if (keys[i] == k) return true;
    keys[idx] = k;
    idx = (uint8_t)((idx + 1) % SEEN_CACHE_SIZE);
    return false;
  }
};

#endif
