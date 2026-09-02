#ifndef SCHEDULER_H
#define SCHEDULER_H

#include <Arduino.h>

// ============================================================================
//  Phase 1 - Shared Core - NON-BLOCKING TIMER
//  This replaces every delay() in the main loop.
//
//  WHY THIS EXISTS
//  The phase 10/11 sketches did this to stagger their first transmission:
//
//      lastBroadcastTime = millis() + random(0, 2000);   // BUG
//      if (millis() - lastBroadcastTime > interval) { ... }
//
//  Setting the timestamp into the FUTURE makes (millis() - last) underflow to
//  a huge unsigned number on the very first pass, so the guard is immediately
//  true and the node transmits at once - the stagger never happened, and all
//  three nodes keyed up together. Interval::begin() below gets the same effect
//  correctly, by moving the timestamp into the PAST by a controlled amount.
// ============================================================================

struct Interval {
  uint32_t last;
  uint32_t period;

  // Start the timer. The first fire happens after firstDelayMs (0 = at once);
  // every fire after that is one period apart.
  void begin(uint32_t periodMs, uint32_t firstDelayMs = 0) {
    period = periodMs;
    uint32_t back = (periodMs > firstDelayMs) ? (periodMs - firstDelayMs) : 0;
    last = millis() - back;          // always into the past - never the future
  }

  // True once per period. Safe across the 49-day millis() rollover because the
  // subtraction is done in unsigned arithmetic on the difference, not on the
  // absolute values.
  bool due() {
    uint32_t now = millis();
    if (now - last >= period) { last = now; return true; }
    return false;
  }

  void setPeriod(uint32_t p) { period = p; }
  void reset()               { last = millis(); }
  uint32_t elapsed() const   { return millis() - last; }
};

#endif
