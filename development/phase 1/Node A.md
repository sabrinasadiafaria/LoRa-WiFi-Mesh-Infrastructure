// ============================================================================
//  Phase 1 - Shared Core - NODE A   (main sketch tab)
//
//  Node A: ESP32 + SX1278 (433 MHz) + 1.3" SH1106 OLED + NEO-6M GPS + button.
//
//  Tabs this sketch needs (create each with the IDE's New Tab, name it
//  EXACTLY as shown including the .h, and paste the matching file):
//      config.h        scheduler.h     packet.h
//      radio_layer.h   neighbors.h     oled_ui.h    node_core.h
//
//  If your Node A actually has the 0.96" SSD1306 instead of the 1.3" SH1106,
//  change OLED_SH1106 to OLED_SSD1306 below. Nothing else changes.
// ============================================================================

#define NODE_IS_A
#define OLED_SH1106

#include "node_core.h"

void setup() {
  nodeSetup();
}

void loop() {
  nodeLoop();
}
