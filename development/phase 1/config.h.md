#ifndef CONFIG_H
#define CONFIG_H

// ============================================================================
//  Phase 1 - Shared Core - CONFIGURATION
//  Every tunable constant in the whole node lives here. Nothing else hardcodes
//  a pin, a timeout or a radio setting.
//
//  The main sketch (Node A/B/C) MUST define, before including anything:
//     NODE_IS_A | NODE_IS_B | NODE_IS_C | NODE_IS_GW | NODE_IS_RV
//     OLED_SH1106 | OLED_SSD1306
// ============================================================================

#define FW_VERSION      1
#define PROTO_VERSION   1     // must match docs/PACKET_SPEC.md

// ---------------------------------------------------------------- identity --
#if   defined(NODE_IS_A)
  #define MY_ID "A"
#elif defined(NODE_IS_B)
  #define MY_ID "B"
#elif defined(NODE_IS_C)
  #define MY_ID "C"
#elif defined(NODE_IS_GW)
  #define MY_ID "GW"
#elif defined(NODE_IS_RV)
  #define MY_ID "RV"
#else
  #error "Define NODE_IS_A / NODE_IS_B / NODE_IS_C in the main sketch"
#endif

// ------------------------------------------------- LoRa SPI pins (ESP32) ----
// Matches ../../Hardware_Connections.md - identical on all three nodes.
#define LORA_SCK    18
#define LORA_MISO   19
#define LORA_MOSI   23
#define LORA_SS      5
#define LORA_RST    14
#define LORA_DIO0   26

// ------------------------------------------------------------- LoRa PHY -----
// TUNE THESE AFTER PHASE 0 (docs/PHASE0_FINDINGS.md "Go / No-Go decisions").
// Defaults below are a safe starting point, NOT the library defaults:
//  - the stock LoRa library leaves CRC OFF and uses the public sync word 0x12,
//    so any other SX127x nearby collides with us. Both are fixed here.
#define LORA_FREQ        433E6
#define LORA_SF          8        // 7 = faster/shorter, 12 = slower/longer
#define LORA_BW          125000L  // Hz
#define LORA_CR          5        // 4/5
#define LORA_TXPOWER     17       // dBm
#define LORA_SYNCWORD    0x2A     // private to this mesh
#define LORA_PREAMBLE    8

// ------------------------------------------------------------ I2C / OLED ----
#define I2C_SDA     21
#define I2C_SCL     22
#define OLED_ADDR   0x3C          // 0x3D is tried automatically as a fallback

// --------------------------------------------------------------- buttons ----
// GPIO 4 with an external button to GND. Do NOT use GPIO 0 (BOOT strapping pin).
#define PIN_SOS_BUTTON  4

// ------------------------------------------------------------------- GPS ----
// Used from Phase 3 onwards. Wired now so the pins are reserved.
#define GPS_RX_PIN  16            // ESP32 RX2  <- GPS TX
#define GPS_TX_PIN  17            // ESP32 TX2  -> GPS RX
#define GPS_BAUD    9600

// ---------------------------------------------------- ADC for random seed ---
// GPIO 34 is input-only on ADC1 and floats -> good entropy.
// (The old phase 11 code seeded from GPIO 0, a strapping pin that reads almost
//  the same value on every node, so all three jittered in lockstep.)
#define PIN_ENTROPY  34

// ---------------------------------------------------------------- timing ----
#define HB_INTERVAL_MS       12000UL   // heartbeat period
#define HB_JITTER_MS          3000UL   // random extra added to every period
#define NEIGHBOR_TIMEOUT_MS  40000UL   // ~3 missed heartbeats -> mark inactive
#define OLED_REFRESH_MS       1000UL
#define STAT_LOG_MS          30000UL   // periodic soak-test line on serial
#define TX_MIN_GAP_MS          400UL   // min spacing between queued transmits
#define TX_GAP_JITTER_MS       250UL

// ----------------------------------------------------------------- sizes ----
#define MAX_NEIGHBORS       8
#define MAX_PACKET_LEN    200          // full on-air frame, incl. checksum
#define MAX_PAYLOAD_LEN   160
#define SEEN_CACHE_SIZE    32          // duplicate-suppression ring
#define TX_QUEUE_DEPTH      6
#define DEFAULT_TTL         4

// -------------------------------------------------------------- watchdog ----
#define WDT_TIMEOUT_S      15

// ---------------------------------------------------------------- serial ----
#define SERIAL_BAUD    115200

#endif
