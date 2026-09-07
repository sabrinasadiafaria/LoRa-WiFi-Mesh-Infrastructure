# Phase 7 — Range, GPS & New UI

Two real bugs were stopping the nodes linking up outdoors, plus a GPS problem that made a working
module look dead. All three are fixed here, and the OLED and captive portal are redesigned.

**Flash all three node sketches, and `git pull` on the Pi** — the Pi's radio settings changed too
and it will hear nothing until you do.

---

## Bug 1 — the spreading factor was tuned for a desk, not a field

`LORA_SF` was set to **7** back in Phase 3, based on bench measurements with the nodes about
**2 metres apart** (RSSI −62…−71 dBm, SNR 10–13 dB). At that distance almost anything works.

SF7 has the **worst sensitivity** of the usable settings:

| SF | Sensitivity @ BW125 | Airtime, 60-byte frame | Relative range |
|---|---|---|---|
| **7** | −123 dBm | 113 ms | baseline |
| 8 | −126 dBm | 205 ms | ~1.4× |
| **9 ← now** | **−129 dBm** | **370 ms** | **~2×** |
| 10 | −132 dBm | 698 ms | ~2.8× |

Outdoors at distance that 6 dB matters enormously — it's roughly **double the range**. Node A
failing to reach B or C in an open field is exactly what running out of link margin looks like.

**Now `LORA_SF 9`.** Beacon rates were slowed to pay for the longer airtime, keeping the channel
around **18 % busy** with four nodes:

| | Was | Now |
|---|---|---|
| `HB_INTERVAL_MS` | 8 s | **15 s** |
| `RT_INTERVAL_MS` | 15 s | **30 s** |
| `GPS_INTERVAL_MS` | 30 s | **45 s** |
| `NEIGHBOR_TIMEOUT_MS` | 45 s | **75 s** (~5 missed) |
| `ROUTE_TIMEOUT_MS` | 60 s | **120 s** |
| `RADIO_WEDGE_MS` | 90 s | **120 s** |

## Bug 2 — the airtime wait was hardcoded (a latent bug that SF9 would have exposed)

After `endPacket(true)` the sketch waited a **fixed 420 ms** before handing the radio back to
`parsePacket()`. That was sized for SF7, whose biggest frame is ~318 ms.

**At SF9 a full frame needs ~1005 ms.** The fixed wait would have expired *mid-transmission* and
`parsePacket()` would have yanked the radio out of TX — corrupting every large packet. Raising the
SF without fixing this would have made things worse, not better.

Airtime is now **computed per frame** from its length and `LORA_SF` using the standard Semtech
time-on-air formula (`loraAirtimeMs()`), so the spreading factor can be changed freely.

## Bug 3 — GPS serial buffer too small

`Serial2`'s default RX buffer is **256 bytes**. A NEO-M8N with several constellations enabled
emits more than that per second in bursts. Whenever `loop()` was briefly busy — and an SF9
transmit is ~370 ms — the buffer overran and NMEA sentences arrived **truncated**, which looks
exactly like a dead GPS.

Now **1 KB**, set with `Serial2.setRxBufferSize(1024)` *before* `begin()`.

> **On "the GPS won't turn on":** most NEO-6M/M8N modules only blink their LED **once they have a
> fix**. No fix = no blink = looks dead. Press **`N`** for a raw NMEA dump — if sentences scroll,
> the module is alive and simply has no sky view. `nmea=` on the `[stat]` line and OLED page 5
> show the same thing continuously. Indoors it will essentially never fix; that's physics.

---

## Redesigned OLED — 5 organised pages

Cycles every 4 s, `p` skips ahead, each page marked `n/5`.

```
1/5 OVERVIEW              2/5 LINKS  <- watch this during a range test
NODE A  SF9  w1  1/5      -- LINKS --   2 up 2/5
Peers 2  Routes 2         B  |||. -98  12s
LOC PHONE 12s             C  ||.. -107 31s
23.79781 90.44972         PI LOST      2m
up 12m  heap 210k

3/5 ROUTES                4/5 POSITIONS           5/5 GPS / TEAM
-- ROUTES --  2   3/5     -- POSITIONS --   4/5   -- GPS / TEAM --  5/5
B  via B  1hop ok         B  23.7978 90.4497      GPS FIX  sat7
C  via B  2hop ok         C  no fix               nmea 4821  fix 3s
PI via B  2hop X          PI 23.7981 90.4501      A  SEARCHING
```

The **LINKS page** is the one that matters when you're walking apart: signal bars plus the raw
dBm per peer, and how long since each was last heard.

## Redesigned captive portal

Rebuilt as a proper mobile UI:

- **Live peer table** with signal bars, dBm, last-seen and position per node
- **Position card** with source badges (GPS module / phone / no fix) and a stale warning
- **Sticky header** with a live connection dot and node/SF/uptime summary
- **Flashing SOS banner** when an alert is active anywhere in the mesh
- **Toast notifications** instead of a static text line
- **Collapsible diagnostics** — firmware, GPS health, routes, radio counters, heap
- Polls `/api/status` every 4 s

The firmware now serves **structured JSON** (`peers` and `routes` as real arrays with
rssi/snr/age/position) instead of pre-formatted HTML, so the page renders it properly.

---

## Tuning for your site

`LORA_SF` is the one knob that matters, and everything adapts to it automatically:

| Situation | Set `LORA_SF` |
|---|---|
| Indoors, short range, want speed | 7 |
| **Mixed indoor + outdoor (default)** | **7 - the known-good value; raise one step at a time** |
| Maximum range, slow | 10 or 11 |

**Change it in all three sketches AND in `pi/sx1278.py` (`SF = 7`).** Nodes on different spreading
factors cannot hear each other at all — this is the single most common way to end up with a silent
mesh.

---

## Test procedure

### Test 1 — they still talk on the bench
All three plus the Pi on a desk. Wait ~60 s (beacons are slower now).
**Pass:** each node's OLED page 1 shows `Peers 2` (or 3 with the Pi), page 2 shows signal bars.

### Test 2 — open-space range  ← the point of this phase
Take two nodes outdoors with line of sight. Watch **OLED page 2 (LINKS)** on one while walking the
other away. Note the distance where the bars drop to one and where it goes `LOST`.
**Pass:** noticeably further than before. Record the distance and the dBm at the edge — that's the
number worth putting in the final report.

### Test 3 — indoors / through walls
Put one node inside a building, one outside. **Pass:** they hold the link at a distance where SF7
previously dropped.

### Test 4 — multi-hop still works
C out of A's range, B in the middle. `r` on A.
**Pass:** `C via B 2hop ok`, and `c` on A delivers to C.

### Test 5 — GPS
Press `N` on each node. **Pass:** NMEA scrolls (module alive). Then outdoors 5–10 min, press `g`.
**Pass:** `GPS module: FIX sats=N`. OLED page 5 shows `GPS FIX sat7`.

### Test 6 — the new portal
Connect a phone to `SOS_Node_A`. **Pass:** peer table populates with signal bars, position card
shows a source badge, the connection dot is green, diagnostics expand.

### Test 7 — stability
All three plus Pi, several hours unattended. **Pass:** `wedge=0`, no `TASK_WDT` in
`[boot] last reset:`, no manual power cycles.

## Completion criteria

- [ ] Test 1 — mesh forms on the bench at SF9
- [ ] **Test 2 — measurably longer open-space range; record metres and dBm**
- [ ] Test 3 — indoor/outdoor combination holds
- [ ] Test 4 — multi-hop A→C via B still works
- [ ] Test 5 — GPS produces NMEA, and a fix outdoors
- [ ] Test 6 — new portal renders and updates live
- [ ] Test 7 — multi-hour run, no wedges, no resets

---

## A note on what I could not verify

Node A specifically failing is consistent with everything above (it hits the same SF7 ceiling as
the others), but the three sketches are **identical apart from the display driver, node ID and
SSID** — there is no Node-A-specific logic that could single it out. If A still underperforms B
and C at the same distance after this, the remaining difference is **hardware**: its antenna,
antenna connector, or the SH1106 module's power draw. Swap Node A's antenna with Node B's and see
whether the problem follows the antenna or stays with the board — that isolates it in one test.

---

## Fix — the portal page would not compile in the Arduino IDE

Phase 7's first upload failed with:

```
error: expected constructor, destructor, or type conversion before '(' token
 function esc(s){return String(s).replace(/[&<>"]/g,function(c){
```

The C++ was valid — one `R"HTML(` opener, one `)HTML"` terminator, pure ASCII in between. The
problem is the **Arduino IDE's own sketch preprocessor** (the step that generates function
prototypes): it does not understand C++11 raw string literals and tracks `"` characters naively.
Phase 7 introduced a JavaScript escape helper containing a **lone `"`** inside a regex character
class, `/[&<>"]/g`. That single unpaired quote flipped the preprocessor's parity, so it stopped
recognising `)HTML"` as the end of the string and handed the compiler ~290 lines of HTML/CSS/JS
as if it were code.

Both halves are fixed:

1. **`esc()` no longer contains a quote.** It escapes `&`, `<`, `>` only — it is used solely on
   text nodes (peer IDs, SOS victim/text), never inside an HTML attribute, so `&quot;` was never
   needed.
2. **The page no longer uses a raw string literal at all.** `PORTAL_HTML` is now conventional
   adjacent string literals with escaped quotes:
   ```c
   const char PORTAL_HTML[] PROGMEM =
     "<!DOCTYPE html><html lang=\"en\"><head>\n"
     ...
   ```
   Same bytes, same `PROGMEM`, same `server.send_P()` — but nothing left for the preprocessor to
   misparse. The conversion was verified by reconstructing the original text from the literals and
   diffing it: byte-identical, 289 lines.

> **Rule going forward:** no `R"(...)"` in these sketches. Any future portal markup goes in as
> escaped literals.

`Multiple libraries were found for "WiFi.h"` in the same output is only a warning — the IDE
correctly picks the ESP32 core's copy. Nothing to do about it.

---

## Fix — the mesh congested itself into never re-forming (SF9 meltdown)

After flashing Phase 7 the nodes lost each other and could not reach the Pi. This was not a
range problem, and not the SF9 change on its own — it was a **positive feedback loop** that SF9
finally made fatal.

### The bug

`sendHeartbeat()` had this since Phase 6:

```c
} else if (anyNeighborMissing()) {
  hbTimer.setPeriod(RECONNECT_HB_MS + random(0, 800));   // every 6 s
}
```

`anyNeighborMissing()` is true for as long as **any node this board has ever met** is absent, and
nothing bounded it. So a node that lost a peer beaconed every 6 s **forever**.

| | airtime per HB | HB duty per node at 6 s |
|---|---|---|
| SF7 (phases 3–6) | ~113 ms | ~1.9 % — harmless |
| **SF9 (phase 7)** | **~330 ms** | **~5.5 %** |

With three nodes plus the Pi all in that state, and `RT` and `GPS` beacons on top, the channel
went past ~50 % occupancy. Then it feeds itself:

> lose a peer → beacon 2.5× faster → more collisions → lose more peers → beacon faster still

Once it tips, it never comes back on its own — which is exactly "nodes are lost, turning them off
and on is the only thing that helps". Power-cycling worked because a fresh boot has no known peers,
so `anyNeighborMissing()` is false until it learns some.

### The fixes

**1. The fast-reconnect burst is now bounded.** It runs for `RECONNECT_WINDOW_MS` (90 s) after a
peer goes missing, then falls back to the normal 15 s rate. A node that comes back announces itself
with `bootBeacons` anyway, so nothing is lost by giving up the burst.

**2. A duty-cycle governor.** Every completed transmission is charged to a rolling 60 s budget
(`DUTY_BUDGET_PERMIL`, 10 %). Routine beacons — `HB` in reconnect mode, `RT`, `GPS` — ask
`dutyAllows()` before queueing. **`SOS`, `DATA`, `SOSACK` and `CMD` are never governed.** Steady
state is ~2 %, so this never fires in normal operation; it exists so no future timing change can
congest the channel again. When it does fire you get one line every 30 s:

```
[duty] channel busy - 6120 of 6000 ms used this minute, 14 beacons skipped so far
```

**3. `LORA_SF` 9 → 8.** SF9 was a 3× airtime increase for a 2× range gain, and the airtime is what
broke things. SF8 is −126 dBm — still **+3 dB / ~1.4× the range of the SF7** used through Phase 6 —
at **half** SF9's airtime.

| | SF7 | **SF8 (now)** | SF9 |
|---|---|---|---|
| Sensitivity | −123 dBm | **−126 dBm** | −129 dBm |
| Airtime, 60-byte frame | 113 ms | **205 ms** | 370 ms |
| Range vs SF7 | 1× | **~1.4×** | ~2× |

> **`pi/sx1278.py` is now `SF = 8` too. `git pull` on the Pi or it will hear nothing** — nodes on
> different spreading factors are completely deaf to each other. This is the most common way to end
> up with a silent mesh.

If open-space range still isn't enough once the mesh is stable, raise `LORA_SF` to 9 **in all three
sketches and on the Pi** — airtime is computed from it and the governor adapts. It will be safe now
that the reconnect storm is bounded.

---

## The boards running hot

**Warm is normal. Too hot to keep a finger on is not, and it causes exactly these dropouts.**

A brown-out is a 3.3 V rail sagging below ~2.8 V, and the worst moment for it is *during a LoRa
transmit* — the SX1278 pulls ~120 mA on top of everything else. The node either resets or emits a
corrupted frame, so its peers hear nothing and time it out. **Heat and "the nodes keep losing each
other" are very likely the same fault.**

### What the firmware now does

| Change | Saves |
|---|---|
| `setCpuFrequencyMhz(80)` — was 240 MHz | ~30–40 mA continuous. 80 MHz is the lowest the Wi-Fi stack allows and is far more than this sketch needs |
| `WiFi.setTxPower(WIFI_POWER_11dBm)` | a large share of the AP's average current — the phone is a metre away |
| `LORA_SF` 9 → 8 | halves how long the PA is keyed on every transmit |

`LORA_TXPOWER` is deliberately left at 17 dBm — that is the range budget, and it is only on for
~200 ms at a time.

### What you have to fix in hardware

Firmware can only do so much. **Check which part is actually hot:**

- **The small 3-pin regulator next to the USB socket (AMS1117)** — this is the usual culprit. It
  drops 5 V to 3.3 V linearly, so with the LoRa module, OLED and GPS all fed from the board's `3V3`
  pin it burns roughly `(5 − 3.3) × 0.4 A ≈ 0.7 W` in a part the size of a grain of rice. It will be
  genuinely painful to touch and it will sag under load.
  - **Fix:** power the SX1278 (and ideally the GPS) from a **separate 3.3 V supply** with a common
    ground, not from the ESP32 board's `3V3` pin. Or feed the board from a good 5 V source and keep
    the peripheral load off that pin.
- **The ESP32 module itself (the metal can)** — 50–60 °C with an AP running is normal and fine.
- **The LoRa module** — should be barely warm. If it is hot, check you have not wired it to 5 V,
  and that the antenna is actually connected. **Transmitting without an antenna damages the PA** and
  is a good way to end up with one node that has poor range for no visible reason.

### Confirming it

The boot banner already tells you. Watch for this on a node that dropped out:

```
############################################################
#  WHY DID THIS NODE LAST RESTART?
#     BROWNOUT - 3.3V rail sagged  <<< POWER PROBLEM
############################################################
```

If you see `BROWNOUT`, it is power, not radio — a better USB cable, a better power bank, a 470 µF
capacitor across the LoRa module's 3V3/GND, or a separate supply for the module. If you see
`POWERON` or `SW_RESET` instead, the node was not resetting and the problem was the congestion
above.

---

## Correction — the spreading factor is back to SF7

After the SF8 build, **nothing connected to anything** — no node to node, no node to Pi. That is a
different failure from the congestion above. Congestion degrades a mesh: links come and go, some
pairs work, it limps. A **clean, total failure across every pair at once** is the signature of a
**PHY mismatch** — and the PHY is what I changed.

Two spreading-factor changes were made in Phase 7 (7 → 9, then 9 → 8) and the mesh got worse both
times. So `LORA_SF` is back to **7** — the value phases 3–6 ran, which linked up reliably on this
hardware — and `pi/sx1278.py` is `SF = 7` to match. The congestion fixes (bounded reconnect burst,
duty governor) are **kept**: those only change how *often* beacons are sent, never the PHY, and the
unbounded reconnect storm was a genuine bug regardless of SF.

`CPU_MHZ` is also back to the stock **240**. Dropping it to 80 is a real heat fix, but it went in at
the same time as the SF change and it should not be confounded with the radio problem. Turn it back
down once the mesh is confirmed linking. The Wi-Fi TX power reduction is kept — it is a different
radio and cannot affect LoRa.

> **Why a spreading-factor mismatch is invisible.** There is no error, anywhere. A radio listening
> on the wrong SF hears *nothing* — and that looks exactly like a radio with nobody in range. If
> even one of the four devices is running an older build, the whole mesh looks dead.

### New: the PHY box

Every node now prints this at boot, and `main.py` prints the matching one on the Pi:

```
############################################################
#  RADIO PHY - MUST BE IDENTICAL ON ALL 3 NODES AND THE PI
#     freq 433000000 Hz    SF7    BW 125000 Hz    CR 4/5
#     sync 0x2A    preamble 8    CRC on    TX 17 dBm
#     CPU 240 MHz
############################################################
```

**Compare all four boxes. Any difference in freq / SF / BW / CR / sync is the whole problem.** The
Pi reads its numbers straight out of `sx1278.py`, so that box can never drift from what the driver
actually programs.

### New: `T` — radio test mode

Press **`T`** on a node's serial monitor. It sends a plain `PING A 42` every 3 s — deliberately not
a protocol frame.

### New: `[rx-raw]` logging

A frame that arrives with a **valid hardware CRC** but does not parse is now printed instead of
being silently counted:

```
[rx-raw] unparsed  rssi=-47 snr=9.5 len=12  "PING A 42"
```

Together these separate the two failures that otherwise look identical:

| On the other node you see | Meaning |
|---|---|
| `[rx-raw] ... "PING A 42"` | **The radios hear each other.** The PHY is fine and the fault is in the mesh/protocol layer |
| **nothing at all** | The PHY does not match, or a radio is dead, or an antenna is missing |

That second row is the one to check first, and it takes about a minute.

### Raising the range later

Once the mesh is provably stable at SF7, `LORA_SF` can go up **one step at a time**, changed in
**all three sketches and `pi/sx1278.py` together**, re-flashing everything and confirming the PHY
boxes match before testing range. Airtime is computed from it and the duty governor adapts, so SF8
is safe from a congestion point of view — the discipline that was missing was changing one thing at
a time and verifying it.
