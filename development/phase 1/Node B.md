// ============================================================================
//  Phase 1 - Shared Core - NODE B   (main sketch tab)
//
//  Node B: ESP32 + SX1278 (433 MHz) + 0.96" SSD1306 OLED + NEO-M8N GPS + button.
//  In the final system Node B is the middle relay of the A - B - C chain.
//
//  Tabs this sketch needs (create each with the IDE's New Tab, name it
//  EXACTLY as shown including the .h, and paste the matching file):
//      config.h        scheduler.h     packet.h
//      radio_layer.h   neighbors.h     oled_ui.h    node_core.h
//
//  NOTE: the shared tabs are byte-identical on all three nodes. Only the two
//  #defines below differ. Do not fork the shared files per node.
// ============================================================================

#define NODE_IS_B
#define OLED_SSD1306

#include "node_core.h"

void setup() {
  nodeSetup();
}

void loop() {
  nodeLoop();
}
