#ifndef RADIO_LAYER_H
#define RADIO_LAYER_H

#include <SPI.h>
#include <LoRa.h>
#include "config.h"
#include "packet.h"

// ============================================================================
//  Phase 1 - Shared Core - LoRa RADIO LAYER
//
//  Responsibilities:
//    * initialise SX1278 with an EXPLICIT PHY (CRC on, private sync word)
//    * never hang - a failed init is reported and retried, not while(1)
//    * serialise all transmits through one queue with a minimum gap + jitter,
//      so a burst (e.g. 3x SOS) never blocks the loop or stomps on itself
//    * pump receive and hand back only checksum-valid, correctly versioned
//      packets
//
//  NOTE ON BLOCKING: LoRa.endPacket() blocks until the frame is on air
//  (~150 ms at SF8). That is unavoidable with this library in synchronous
//  mode, but it happens at most once per TX_MIN_GAP_MS and only when the
//  queue is non-empty - versus the old code, which blocked for 3.5 s straight
//  during an SOS burst and went deaf to every other node.
// ============================================================================

class RadioLayer {
public:

  bool begin() {
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
        LoRa.enableCrc();                 // stock library leaves this OFF
        LoRa.receive();
        _ok = true;
        return true;
      }
      delay(200);                         // setup() only - never in loop()
    }
    _ok = false;
    return false;
  }

  // Retry a failed radio without rebooting. Called periodically from loop().
  bool retry() {
    if (_ok) return true;
    return begin();
  }

  bool ok() const { return _ok; }

  // Queue a fully built frame for transmission. Returns false if the queue is
  // full (counted as a drop) - callers should not busy-retry.
  bool enqueue(const char *frame) {
    if (!frame || !*frame) return false;
    if (_qCount >= TX_QUEUE_DEPTH) { _drop++; return false; }
    strncpy(_q[_qTail], frame, MAX_PACKET_LEN - 1);
    _q[_qTail][MAX_PACKET_LEN - 1] = '\0';
    _qTail = (uint8_t)((_qTail + 1) % TX_QUEUE_DEPTH);
    _qCount++;
    return true;
  }

  // Call every loop(). Sends at most one queued frame, respecting the gap.
  void service() {
    if (!_ok || _qCount == 0) return;
    uint32_t now = millis();
    if (now - _lastTx < _gap) return;

    LoRa.beginPacket();
    LoRa.print(_q[_qHead]);
    int r = LoRa.endPacket();             // 1 = success
    LoRa.receive();                       // always return to listening

    if (r == 1) _tx++; else _drop++;

    _qHead = (uint8_t)((_qHead + 1) % TX_QUEUE_DEPTH);
    _qCount--;
    _lastTx = millis();
    _gap = TX_MIN_GAP_MS + (uint32_t)random(0, TX_GAP_JITTER_MS);
  }

  // Call every loop(). Returns true when a valid packet is available in `out`.
  bool poll(Packet &out) {
    if (!_ok) return false;
    int sz = LoRa.parsePacket();
    if (sz <= 0) return false;

    char buf[MAX_PACKET_LEN];
    int n = 0;
    while (LoRa.available() && n < (int)sizeof(buf) - 1) buf[n++] = (char)LoRa.read();
    buf[n] = '\0';
    while (LoRa.available()) LoRa.read();          // discard any overflow

    int   rssi = LoRa.packetRssi();
    float snr  = LoRa.packetSnr();

    if (!pktParse(buf, out)) { _bad++; return false; }
    out.rssi = rssi;
    out.snr  = snr;
    _rx++;
    return true;
  }

  uint16_t nextMsgId() { if (++_msgId == 0) _msgId = 1; return _msgId; }

  uint32_t txCount()   const { return _tx;   }
  uint32_t rxCount()   const { return _rx;   }
  uint32_t badCount()  const { return _bad;  }   // checksum / version rejects
  uint32_t dropCount() const { return _drop; }   // queue full or TX failed
  uint8_t  queued()    const { return _qCount; }

private:
  bool     _ok     = false;
  char     _q[TX_QUEUE_DEPTH][MAX_PACKET_LEN];
  uint8_t  _qHead  = 0, _qTail = 0, _qCount = 0;
  uint32_t _lastTx = 0;
  uint32_t _gap    = TX_MIN_GAP_MS;
  uint16_t _msgId  = 0;
  uint32_t _tx = 0, _rx = 0, _bad = 0, _drop = 0;
};

#endif
