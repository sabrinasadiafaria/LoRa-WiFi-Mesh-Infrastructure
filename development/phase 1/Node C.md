// ============================================================================
//  Phase 1 - Shared Core - NODE C   (main sketch tab)
//
//  Node C: ESP32 + SX1278 (433 MHz) + 0.96" SSD1306 OLED + NEO-M8N GPS + button.
//
//  NOTE ON HARDWARE: the old phase 8/9 sketches had Node C on an Arduino
//  Uno/Nano (ATmega328P, 2 KB RAM), which is why that node needed a string of
//  "power stabilization delay" and "I2C init order" patches. All development/
//  firmware targets three IDENTICAL ESP32 boards, matching
//  ../../Hardware_Connections.md. Use an ESP32 for Node C.
//
//  Tabs this sketch needs (create each with the IDE's New Tab, name it
//  EXACTLY as shown including the .h, and paste the matching file):
//      config.h        scheduler.h     packet.h
//      radio_layer.h   neighbors.h     oled_ui.h    node_core.h
// ============================================================================

#define NODE_IS_C
#define OLED_SSD1306

#include "node_core.h"

void setup() {
  nodeSetup();
}

void loop() {
  nodeLoop();
}
