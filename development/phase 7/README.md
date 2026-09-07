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

`LORA_SF` is now the one knob that matters, and everything adapts to it automatically:

| Situation | Set `LORA_SF` |
|---|---|
| Indoors, short range, want speed | 7 |
| **Mixed indoor + outdoor (default)** | **9** |
| Maximum range, slow | 10 or 11 |

**Change it in all three sketches AND in `pi/sx1278.py` (`SF = 9`).** Nodes on different spreading
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
