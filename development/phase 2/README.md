# Phase 2 — Hybrid Location (GPS module + phone via captive portal)

**Goal:** every node knows where it is — from its own GPS module *or* from a phone that connects
to its Wi-Fi and shares a position through a captive portal — and tells the rest of the mesh.

**Why hybrid:** the GPS module cannot get a fix indoors, under a roof or beneath debris, which is
exactly where a rescue node ends up. The phone becomes the primary source when it is available;
the module is the fallback. Whichever source is in use is always labelled with its age, so nobody
mistakes a stale position for a live one.

---

## Files

| File | Node | Display | AP SSID |
|---|---|---|---|
| `Node A.md` | A | 1.3" SH1106 (U8g2) | `SOS_Node_A` |
| `Node B.md` | B | 0.96" SSD1306 (Adafruit) | `SOS_Node_B` |
| `Node C.md` | C | 0.96" SSD1306 (Adafruit) | `SOS_Node_C` |

Each is a **complete standalone sketch** — select all, paste into the Arduino IDE, upload.

**Libraries:** `LoRa` (Sandeep Mistry) · `U8g2` (Node A) · `Adafruit GFX` + `Adafruit SSD1306`
(Nodes B & C). The Wi-Fi, web server and DNS server all ship with the ESP32 board package —
nothing extra to install.

**New wiring vs Phase 1:** the GPS module. `GPS TX → GPIO 16`, `GPS RX → GPIO 17`, VCC 3.3 V or
5 V, GND common. Everything else is unchanged.

---

## ⚠️ Read this before testing the "Use Phone GPS" button

Browsers only permit `navigator.geolocation` on a **secure origin (HTTPS)**. A captive portal is
plain HTTP at `http://192.168.4.1`, so **Chrome and Safari will usually refuse the button.** That
is browser policy, not a bug here, and a self-signed certificate does not help (an untrusted cert
is still not a secure context).

The portal therefore always offers **manual latitude/longitude entry** — open your maps app, copy
the coordinates, paste them in. That path works on every phone, every time, and is what you
should rely on for the demo. Try the button first; if it is refused the page tells you so and
points you at the boxes below it.

---

## How to test

### 1. Flash and check the boot log (115200 baud)
```
[boot] Node A fw v2  heap=298372
[gps] Serial2 9600 baud on RX16/TX17
[radio] LoRa OK  SF8 BW125 CRC=on sync=0x2A pwr=17dBm
[portal] AP "SOS_Node_A" up at 192.168.4.1
[boot] ready. type 'h' for commands.
```

### 2. Connect a phone
Wi-Fi settings → join **`SOS_Node_A`** (open, no password). The rescue portal should pop up on
its own. If it does not, open `http://192.168.4.1` in the browser.

### 3. Send a position
Tap **Use Phone GPS**. If the browser refuses, paste coordinates into the two boxes and tap
**Send Coordinates**. Either way you should see:
- portal: position card updates, source shows `phone`, age counts up
- serial: `[portal] phone position 23.797810,90.449720 (acc 12m)`
- OLED row 3: `PHONE s0 age4s`
- within ~20 s the other nodes log `[loc] A is at 23.797810,90.449720 via PHONE`

### 4. Check the GPS module
Press `g` on the serial monitor:
```
---- LOCATION ------------------------------------------
  in use   : PHONE  23.797810, 90.449720  (12s old)
  preference: PHONE first
  GPS module: no fix  sats=0  nmea lines=1843
  phone     : have position  23.797810, 90.449720  acc 12m  12s ago  (1 updates)
--------------------------------------------------------
```
- `nmea lines` climbing → the module is wired and talking. If it stays **0**, check GPS TX → GPIO 16 and that the module is 9600 baud.
- Put the antenna at a window. A cold fix takes 30 s to several minutes. When it locks, `GPS module: FIX  sats=7`.

### 5. Watch the fallback work
With a fresh phone position **and** a GPS fix, the node reports `PHONE` (that is the configured
preference). Wait 5 minutes without re-sending from the phone — the phone fix goes stale and the
node switches to `GPS`. That is the whole point of the hybrid: it degrades instead of going blank.

To reverse the priority, set `#define LOCATION_PREFER_PHONE 0` **in all three sketches**.

### 6. Wi-Fi / LoRa coexistence  ← the thing to watch
This is the first phase where both radios run together. With a phone connected and the portal
open, press `s` on each node every few minutes:
```
[stat] up=600s heap=248112 neigh=2 tx=48 rx=91 bad=0 drop=0 q=0 wifi=1 loc=PHONE
```
**Pass:** `bad` and `drop` stay near zero and `rx` keeps climbing while a phone is attached. If
`rx` stalls whenever someone is browsing the portal, tell me — we throttle the portal polling.

### 7. 30-minute soak
Leave all three running, one phone attached, and record `heap` every 10 min. WiFi + WebServer
costs roughly 45–50 KB, so expect ~250 KB free instead of ~300 KB. **Pass:** flat after that
one-time drop, no resets.

---

## Serial commands

| Key | Does |
|---|---|
| `n` | neighbour table, including each peer's last known position |
| `s` | stats (now with `wifi=` client count and `loc=` source) |
| `g` | **location detail** — which source is in use, GPS health, phone history |
| `x` | transmit a frame with a deliberately corrupted checksum |
| `h` | help |

## OLED layout

```
NODE A  wifi1        <- Wi-Fi clients connected
Conn: B,C
23.79781,90.44972
PHONE s0 age12s      <- source, satellites, age of fix
heap 248112 up600s
```

---

## Completion criteria

- [ ] Portal auto-opens on a real phone (or loads at `192.168.4.1`)
- [ ] Manual coordinate entry updates the node's position
- [ ] `navigator.geolocation` tried — result recorded (works / refused by browser)
- [ ] GPS module produces NMEA (`nmea lines` climbing) and eventually a fix outdoors
- [ ] Preference works: phone wins while fresh, module takes over when the phone fix ages out
- [ ] Peers learn each other's positions over LoRa (`[loc]` lines, `n` shows coordinates)
- [ ] **Wi-Fi + LoRa coexist:** `bad`/`drop` stay near zero with a phone attached
- [ ] 30-minute soak, heap flat after the one-time WiFi allocation, zero resets

Record results in `../docs/TEST_REPORT.md`.

## What's new vs Phase 1

| | Phase 1 | Phase 2 |
|---|---|---|
| Location | none (pins reserved) | GPS module + phone via portal, with priority and ageing |
| Wi-Fi | none | SoftAP + DNS wildcard + captive portal + JSON API |
| Packets | `HB` | `HB` + `GPS` (`lat,lon,sats,source,age`) |
| Neighbour table | id, RSSI, uptime, heap | + last known position and its source |
| GPS parsing | — | non-blocking NMEA; the old `readStringUntil()` blocked up to 1 s per loop |
| Fix validity | — | from the RMC `A` status flag, not `lat != 0.0` (which rejected the equator) |
| Watchdog | 15 s | 20 s (Wi-Fi stack adds jitter to loop timing) |
