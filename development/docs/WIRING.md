# Wiring

Per-board wiring tables for the full system. The same numbers are in
each sketch's header comment (so a single Arduino IDE paste is
self-contained) — this file is the **one place** to look when wiring
the whole demo.

Conventions used:

- **VCC = 3V3** unless explicitly stated otherwise. **Never 5 V** to
  the SX1278, OLED, or GPS.
- **Common ground** between any two supplies that talk to each other.
- Pull-ups and pull-downs: explicit where they matter, omitted where
  they're internal to the module.

**Two ESP32 variants:** the three static nodes (A, B, C) use the
classic ESP32 (DevKitC-style). The **rover uses an ESP32-S3** — the
two chips have different pin maps and the rover sketch will not
flash onto a classic ESP32 or vice versa. The Pi is a Pi; no ESP32.

---

## 1. ESP32 node — A, B, C (classic ESP32, ESP32 Dev Module)

Identical pin map across A, B, C. The only difference between A/B/C
is **what software runs** on them (Node B is a relay, no portal;
Node A and C run a portal + GPS).

```
                             ┌──────────────┐
   LoRa SX1278 / RA-02       │   ESP32      │
   ┌──────────────┐          │              │
   │ SCK  ────────┼─────────►│ GPIO 18      │
   │ MISO ────────┼─────────►│ GPIO 19      │
   │ MOSI ────────┼─────────►│ GPIO 23      │
   │ NSS  ────────┼─────────►│ GPIO  5      │
   │ RST  ────────┼─────────►│ GPIO 14      │
   │ DIO0 ────────┼─────────►│ GPIO 26      │
   │ VCC  ────────┼─────────►│ 3V3          │  NEVER 5 V
   │ GND  ────────┼─────────►│ GND          │
   └──────────────┘          │              │
                             │              │
   OLED SH1106 / SSD1306     │              │
   ┌──────────────┐          │              │
   │ SDA  ────────┼─────────►│ GPIO 21      │  I2C
   │ SCL  ────────┼─────────►│ GPIO 22      │  I2C
   │ VCC  ────────┼─────────►│ 3V3          │
   │ GND  ────────┼─────────►│ GND          │
   └──────────────┘          │              │
                             │              │
   GPS (NEO-6M / NEO-M8N)    │              │
   ┌──────────────┐          │              │
   │ TX (mod out)─┼─────────►│ GPIO 16      │  Serial2 RX
   │ RX (mod in)──┼─────────►│ GPIO 17      │  Serial2 TX
   │ VCC  ────────┼─────────►│ 3V3          │
   │ GND  ────────┼─────────►│ GND          │
   └──────────────┘          │              │
                             │              │
   SOS button                │              │
   ┌──────────────┐          │              │
   │ one leg ─────┼─────────►│ GPIO  4      │  internal pull-up
   │ other leg ───┼─────────►│ GND          │
   └──────────────┘          │              │
                             │              │
   Entropy (optional)        │              │
   ┌──────────────┐          │              │
   │ leave open   │          │ GPIO 34      │  ADC1, input-only
   │ (must float) │          │              │
   └──────────────┘          │              │
                             │              │
   (A and C only:)           │              │
   SoftAP antenna            │ onboard      │  Wi-Fi 2.4 GHz
                             └──────────────┘
```

| Pin | Function |
|---|---|
| GPIO 5 / 14 / 18 / 19 / 23 / 26 | LoRa SPI bus (NSS, RST, SCK, MISO, MOSI, DIO0) |
| GPIO 21 / 22 | I²C OLED |
| GPIO 16 / 17 | Serial2 GPS |
| GPIO 4 | SOS button (active-low, internal pull-up) |
| GPIO 34 | (optional) entropy pin, leave floating |

**Power:** one 5 V power bank → ESP32 VIN (or USB). LoRa / OLED / GPS
draw so little that the on-board 3V3 regulator is fine for all three
together.

**Don't** daisy-chain the GPS power through the OLED's 3V3 output —
each module wants its own pin to the regulator.

---

## 2. ESP32-S3 rover — Node R (N8R8 / N16R8 DevKitC-1)

Same LoRa + OLED + GPS stack as the static nodes, plus motors and an
ultrasonic sensor. **The pin numbers are different** because the S3
has no GPIO 22–37, the octal PSRAM uses 33–37, ADC1 is GPIO 1–10,
and strapping pins (0, 3, 45, 46) need to stay clean. The rover
sketch uses only the safe set **1–18, 21, 39–42, 47**.

```
                             ┌──────────────┐
   LoRa SX1278 / RA-02       │  ESP32-S3    │
   ┌──────────────┐          │              │
   │ SCK  ────────┼─────────►│ GPIO 12      │
   │ MISO ────────┼─────────►│ GPIO 13      │
   │ MOSI ────────┼─────────►│ GPIO 11      │
   │ NSS  ────────┼─────────►│ GPIO 10      │
   │ RST  ────────┼─────────►│ GPIO 14      │
   │ DIO0 ────────┼─────────►│ GPIO 21      │
   │ VCC  ────────┼─────────►│ 3V3          │  NEVER 5 V
   │ GND  ────────┼─────────►│ GND          │
   └──────────────┘          │              │
                             │              │
   OLED SSD1306 0.96"        │              │
   ┌──────────────┐          │              │
   │ SDA  ────────┼─────────►│ GPIO  8      │  I2C
   │ SCL  ────────┼─────────►│ GPIO  9      │  I2C
   │ VCC  ────────┼─────────►│ 3V3          │
   │ GND  ────────┼─────────►│ GND          │
   └──────────────┘          │              │
                             │              │
   GPS NEO-M8N                │              │
   ┌──────────────┐          │              │
   │ TX (mod out)─┼─────────►│ GPIO 17      │  Serial2 RX
   │ RX (mod in)──┼─────────►│ GPIO 18      │  Serial2 TX
   │ VCC  ────────┼─────────►│ 3V3          │
   │ GND  ────────┼─────────►│ GND          │
   └──────────────┘          │              │
                             │              │
   L298N motor driver        │              │
   ┌──────────────┐          │              │
   │ IN1  ────────┼─────────►│ GPIO  5      │  left direction
   │ IN2  ────────┼─────────►│ GPIO  6      │
   │ ENA  ────────┼─────────►│ GPIO  4      │  REMOVE ENA jumper
   │ IN3  ────────┼─────────►│ GPIO  7      │  right direction
   │ IN4  ────────┼─────────►│ GPIO 16      │
   │ ENB  ────────┼─────────►│ GPIO 42      │  REMOVE ENB jumper
   │ +12V ────────┼─────────►│ motor batt + │
   │ GND  ────────┼─────────►│ motor batt - │  common ground with ESP32 GND
   │ OUT1/OUT2 ───┼──────────│ 2× left motors in parallel |
   │ OUT3/OUT4 ───┼──────────│ 2× right motors in parallel|
   └──────────────┘          │              │
                             │              │
   HC-SR04 ultrasonic        │              │
   ┌──────────────┐          │              │
   │ TRIG ────────┼─────────►│ GPIO 40      │  ESP32 → sensor (no divider)
   │ ECHO ─[1k]───┼─────┬───►│ GPIO 41      │  see "ECHO divider" below
   │             [2k]  │    │              │
   │              │   GND   │              │
   │ VCC  ────────┼─────────►│ 5 V rail    │  sensor needs 5 V
   │ GND  ────────┼─────────►│ GND         │
   └──────────────┘          │              │
                             │              │
   SG90 / MG90S servo        │              │
   ┌──────────────┐          │              │
   │ SIG  ────────┼─────────►│ GPIO 39      │  3V3 signal is fine
   │ VCC  ────────┼─────────►│ 5 V rail    │  NOT the ESP32 3V3 pin
   │ GND  ────────┼─────────►│ GND         │
   └──────────────┘          │              │
                             │              │
   SOS button / E-STOP       │              │
   ┌──────────────┐          │              │
   │ one leg ─────┼─────────►│ GPIO 15      │  internal pull-up
   │ other leg ───┼─────────►│ GND          │
   └──────────────┘          │              │
                             │              │
   Battery sense (optional)  │              │
   ┌──────────────┐          │              │
   │ divider mid ─┼─────────►│ GPIO  2      │  ADC1_CH1
   └──────────────┘          │              │
                             │              │
   Entropy                   │              │
   ┌──────────────┐          │              │
   │ leave open   │          │ GPIO  1      │  must float
   └──────────────┘          │              │
                             └──────────────┘
```

### The ECHO divider is **not** optional

The HC-SR04 drives ECHO at 5 V; the ESP32-S3 is **not 5 V tolerant**.
Connecting ECHO directly will damage GPIO 41.

```
HC-SR04 ECHO ──[ 1k ]──┬── GPIO 41
                       │
                    [ 2k ]
                       │
                      GND
```

5 V × 2/(1+2) = 3.3 V. Any pair with roughly a 1:2 ratio works
(1k/2k, 10k/20k). TRIG needs no divider — it's an output from the
ESP32 into the sensor.

### Motor battery is a separate supply

**Two supplies, one ground.** Motor inrush pulled through a shared
supply browns out the ESP32 mid-drive, and it looks exactly like a
random reset rather than a motor problem.

- Motor battery → L298N `+12V`/`GND` only.
- Logic battery (separate power bank or BEC) → ESP32-S3, LoRa, OLED,
  GPS.
- **Tie the two grounds together** at the L298N's GND terminal.
- Don't run the ESP32 off the L298N's on-board 5 V output while the
  motors are moving — the L298N's 5 V regulator isn't designed for
  motor-noise transients.
- The servo also belongs on the 5 V rail, not the ESP32's 3V3 pin —
  an SG90 can pull several hundred mA when it stalls.
- Remove both **ENA** and **ENB** jumpers from the L298N. With them
  fitted the driver ignores GPIO 4 and 42 and the motors are
  permanently enabled — the sketch's stop and E-STOP would do nothing.

### Four motors on a two-channel L298N

The L298N has two channels and there are four motors, so they go on
in **pairs, in parallel**: both left motors to OUT1/OUT2, both right
motors to OUT3/OUT4. Each channel drives two. The L298N drops about
1.4–2 V, so feed it **at least 7.5–8 V** for 6 V motors — a 2S
Li-ion pack (7.4 V) is close to ideal; 6×AA (9 V) also works.
Feeding it 5 V leaves only ~3.5 V at the motors and they will be
weak and stall easily. Fit the heatsink.

### SOS button is the hardware E-STOP

Wired exactly like the static nodes' SOS button (active-low,
internal pull-up). On the rover it serves two roles:
- regular SOS: press → broadcasts SOS packet like the static nodes
- **hardware E-STOP**: any press → motors cut immediately,
  independent of mode. A moving robot needs an override no software
  state can block.

### Board setting in the Arduino IDE

Board: **ESP32S3 Dev Module**. If the serial monitor stays blank
after upload, enable **USB CDC On Boot**.

### First power-up: wheels off the ground

Before the wheels ever touch the floor: power it up, confirm
`mode=MANUAL` in the boot banner, and test `i`/`k`/`j`/`l`/`o` on
serial (or the dashboard's arrow buttons). Confirm each direction
spins the correct wheels the correct way. **Only then** put it on
the floor, and **only then** try AUTO near a real obstacle.

---

## 3. Raspberry Pi gateway

The Pi is the command centre + dashboard host. It runs its own
SX1278 on SPI0 and serves Flask on `:8000`. The full SX1278 wiring
lives in the header of `pi/sx1278.py` — reproduced here:

```
                      ┌──────────────────────────┐
   SX1278 / RA-02     │  Raspberry Pi            │
   ┌──────────────┐   │                          │
   │ SCK  ────────┼───┼──► GPIO 11  (pin 23, SCLK)│
   │ MISO ────────┼───┼──► GPIO  9  (pin 21, MISO)│
   │ MOSI ────────┼───┼──► GPIO 10  (pin 19, MOSI)│
   │ NSS  ────────┼───┼──► GPIO  8  (pin 24, CE0) │
   │ RST  ────────┼───┼──► GPIO 25  (pin 22)      │
   │ DIO0 ────────┼───┼──► GPIO 24  (pin 18)      │
   │ VCC  ────────┼───┼──► 3V3 (pin 1)            │  NEVER 5 V
   │ GND  ────────┼───┼──► GND (pin 6)            │
   └──────────────┘   │                          │
                      │                          │
   (no GPS, no        │                          │
    OLED on the Pi)   │                          │
                      │                          │
                      │  Ethernet / Wi-Fi out    │  → commander's laptop
                      └──────────────────────────┘
```

| Pi pin | SX1278 | Function |
|---|---|---|
| 19 (GPIO 10) | MOSI | SPI data out |
| 21 (GPIO 9)  | MISO | SPI data in |
| 23 (GPIO 11) | SCK  | SPI clock |
| 24 (GPIO 8)  | NSS  | chip select (CE0) |
| 22 (GPIO 25) | RST  | radio reset |
| 18 (GPIO 24) | DIO0 | RX done interrupt |
| 1 (3V3)      | VCC  | 3.3 V supply |
| 6 (GND)      | GND  | ground |

### Enable SPI on the Pi

If `lsmod | grep spi_bcm2835` is empty:

```bash
sudo raspi-config     # → Interface Options → SPI → Enable
sudo reboot
```

### Allow the gateway user to talk to SPI without sudo

```bash
sudo usermod -a -G spi $USER
# log out and back in (or reboot)
```

`install.sh` does this for you.

### Pi 5 note

On a Pi 5, `spidev` works but `gpiozero` needs the `lgpio` backend.
Install the OS package: `sudo apt install python3-lgpio`. `install.sh`
does this too.

---

## 4. Power summary

| Board | Power source | Notes |
|---|---|---|
| Node A | 5 V power bank | USB or VIN; LoRa + OLED + GPS all on 3V3 |
| Node B | 5 V power bank | same |
| Node C | 5 V power bank | same |
| Rover (logic) | 5 V power bank | ESP32-S3, LoRa, OLED, GPS |
| Rover (motors) | 2S Li-ion (7.4 V) | **separate** from logic; common ground at L298N GND |
| Pi gateway | USB-C 5 V / official PSU | 3 A recommended |

Total: 5 power banks + 1 motor battery + 1 Pi PSU. Bring spares for
demo day.

---

## 5. Breadboard layout sketches

ASCII breadboard sketches for each board are in each phase's README
under that board's wiring section. There is no single PDF diagram
because every revision of the hardware moved something. The per-
phase sketches are the live truth.
