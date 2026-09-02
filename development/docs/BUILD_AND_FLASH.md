# BUILD_AND_FLASH

How to assemble a `development/` node sketch in the Arduino IDE from the Markdown tab files.

## Prerequisites

- **Arduino IDE** 2.x
- **ESP32 board package** (Espressif) — Boards Manager → "esp32". Bundles `WiFi`, `WebServer`,
  `DNSServer`, `HardwareSerial`, `esp_task_wdt` (no extra install for Phases 4–6).
- **Libraries** (Library Manager):
  | Library | Author | Used by |
  |---|---|---|
  | `LoRa` | Sandeep Mistry | all nodes |
  | `U8g2` | oliver kraus | nodes with an SH1106 1.3" OLED |
  | `Adafruit GFX Library` | Adafruit | nodes with an SSD1306 0.96" OLED |
  | `Adafruit SSD1306` | Adafruit | nodes with an SSD1306 0.96" OLED |
- **Board setting:** "ESP32 Dev Module", 240 MHz, Flash 4 MB, Partition "Default 4MB with spiffs".

## Assembling a sketch

Each `development/` node is one Arduino "sketch" made of **multiple tabs**. The main tab is the
node file (`firmware/nodes/Node_X.md`); the other tabs are the shared modules it needs.

1. Create a new sketch. Name it e.g. `Node_A`.
2. For each shared module the node needs, use the IDE's **⋮ → New Tab** and name it **exactly**
   as the file's base name **including `.h`** — e.g. tab name `radio_layer.h`. Paste the code
   block from `firmware/common/radio_layer.h.md` into it.
3. Paste the node file's code into the main `.ino` tab.
4. In the main tab, set the per-node config `#define`s at the top (node id, OLED type, whether
   this node has GPS / a portal). Each node file documents its switches.
5. Compile & upload.

### Tab order per phase

| Phase | Tabs required (create in this order) |
|---|---|
| 1 | `config.h`, `scheduler.h`, `packet.h`, `radio_layer.h`, `oled_ui.h` + main |
| 2 | + `mesh_core.h` |
| 3 | + `gps_layer.h`, `app_sos.h`, `app_msg.h` |
| 4 | + `portal_layer.h`, `portal_pages.h`  (Node A & C only) |
| 5 | Gateway node: phase-2 tab set + main; Pi side is separate (`pi/README.md`) |
| 6 | Rover node: phase-3 tab set + `motor_layer.h`, `ultrasonic_layer.h` + main |

Tabs are `#include`d by filename from the main sketch (`#include "radio_layer.h"`), so the names
must match. The `.md` wrapper is only for the repo — never paste the Markdown fences or headings.

## Per-node roles

| Node | id | OLED | GPS | Portal | Extra |
|---|---|---|---|---|---|
| Node A | `A` | SH1106 (U8g2) | yes | yes | SOS button GPIO 4 |
| Node B | `B` | SSD1306 | optional | no | relay; SOS button GPIO 4 |
| Node C | `C` | SSD1306 | yes | yes | SOS button GPIO 4 |
| Gateway | `GW` | optional | no | no | USB serial framing to the Pi |
| Rover | `RV` | optional | yes | no | L298N + HC-SR04, separate motor battery |

Wiring: see `../Hardware_Connections.md` and `docs/WIRING.md`.

## Sanity check after flashing

Every node prints on boot (115200 baud):
```
[boot] Node <id> fw v<n>  heap=<bytes>
[radio] LoRa OK  SF<n> BW125 CRC=on sync=0x2A
```
If `[radio] LoRa FAIL` — check SPI wiring (SCK18 MISO19 MOSI23 SS5 RST14 DIO0 26) and that LoRa
VCC is on **3.3 V, not 5 V**. The new firmware retries and keeps the watchdog fed instead of
hanging.
