# BUILD_AND_FLASH

## Prerequisites

- **Arduino IDE** 2.x
- **ESP32 board package** (Espressif) — Boards Manager → "esp32". Bundles `WiFi`, `WebServer`,
  `DNSServer`, `HardwareSerial`, `esp_task_wdt`, so Phases 4–6 need no extra installs.
- **Libraries** (Library Manager):
  | Library | Author | Used by |
  |---|---|---|
  | `LoRa` | Sandeep Mistry | all nodes |
  | `U8g2` | oliver kraus | nodes with a 1.3" SH1106 OLED |
  | `Adafruit GFX Library` | Adafruit | nodes with a 0.96" SSD1306 OLED |
  | `Adafruit SSD1306` | Adafruit | nodes with a 0.96" SSD1306 OLED |
- **Board setting:** "ESP32 Dev Module", 240 MHz, Flash 4 MB, Partition "Default 4MB with spiffs".

## Flashing a node

Every node sketch in `development/phase N/` is a **complete standalone program** — the same
convention as the root `phase 10/` and `phase 11/` files.

1. Open `phase N/Node A.md`, select all, copy.
2. Arduino IDE → new sketch → select all → paste over it.
3. Choose the board and port, Upload.
4. Repeat with `Node B.md` and `Node C.md` on the other two boards.

The `.md` files contain raw code only — no Markdown fences or headings — so a straight
select-all-paste works.

**Do not mix phases across nodes.** All three boards must run the same phase, or they will not
understand each other's packets (the protocol version is checked and mismatches are dropped).

## Per-node roles

| Node | id | Display | GPS | Portal | Extra |
|---|---|---|---|---|---|
| Node A | `A` | SH1106 1.3" | yes | yes (Phase 4) | SOS button GPIO 4 |
| Node B | `B` | SSD1306 0.96" | optional | no | relay; SOS button GPIO 4 |
| Node C | `C` | SSD1306 0.96" | yes | yes (Phase 4) | SOS button GPIO 4 |
| Gateway | `GW` | optional | no | no | USB serial bridge to the Pi (Phase 5) |
| Rover | `RV` | optional | yes | no | L298N + HC-SR04, separate motor battery (Phase 6) |

Wiring: `../../Hardware_Connections.md` and `WIRING.md`.

## Editing shared constants

Because each node is a standalone file, the tunable block (pins, `LORA_SF`, `LORA_TXPOWER`,
timeouts, table sizes) is repeated near the top of all three sketches. **If you change one,
change all three** — mismatched radio settings mean the nodes cannot hear each other at all.

The block to keep in sync starts at `// ------- identity -------` and ends at
`// ------- sizes -------`.

## Sanity check after flashing

Every node prints on boot (115200 baud):
```
[boot] Node A fw v1  heap=298372
[radio] LoRa OK  SF8 BW125 CRC=on sync=0x2A pwr=17dBm
[boot] ready. type 'h' for commands.
```
If you see `[radio] LoRa FAIL` — check the SPI wiring (SCK 18, MISO 19, MOSI 23, SS 5, RST 14,
DIO0 26) and that LoRa VCC is on **3.3 V, not 5 V**. The new firmware retries every 5 s and keeps
the watchdog fed instead of hanging, so the display stays readable while you fix it.
