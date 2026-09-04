# Phase 6 — Reliability & GPS

Everything Phase 5 did, plus fixes for the three problems that showed up on the bench once the Pi
joined the mesh:

1. nodes randomly got lost — no single culprit, any of A/B/C
2. a lost node could not rejoin
3. the GPS module "should work properly"
4. *(added in a later revision below)* disconnects that only a power cycle fixed, and a manual
   "search nearby nodes" button

**Flash all three node sketches.** The Pi side of this phase now lives in
[`development/pi/`](../pi/) — see the note there and the Revision section below.

---

## 1. Why nodes randomly got lost

`parsePacket()` arms the SX1278 in **`RX_SINGLE`**: it listens for roughly 100 ms, then drops to
`STANDBY` until the next poll. **The radio is only listening while the loop keeps calling it.**
Anything that stalls `loop()` therefore makes the node deaf — and the worst offender was the
display:

> A 128×64 frame is **1 KB over I2C**. The ESP32's default Wire clock is **100 kHz**, so pushing
> one frame takes **~100 ms with the loop blocked** — *every second*. Add the per-packet
> `Serial.printf` (~10 ms each at 115200) and the radio could be listening barely half the time.

That produces exactly the reported symptom: random nodes dropping, no pattern, no crash, no
watchdog reset.

### Fixes

| Change | Effect |
|---|---|
| `Wire.setClock(400000)` | frame push ~100 ms → ~25 ms |
| `oledPush()` skips the redraw when the 5 lines are **identical** to the last frame | most seconds cost nothing at all |
| per-packet `[rx]` log **off by default**, `v` toggles it | removes ~10 ms per received packet |

### And it is now measured

The `[stat]` line carries **`maxloop=`** — the longest single `loop()` pass since the last stat
print:

```
[stat] up=300s heap=214668 neigh=3 tx=28 rx=91 bad=0 drop=0 q=0 wifi=0
       loc=PHONE gps=FIX/7 nmea=4821 maxloop=6ms minheap=169200 stack=5408
       txstuck=0 rst=POWERON
```

**`maxloop` in single-digit ms → the radio is listening essentially all the time.** If it climbs
into the tens or hundreds, that is the packet loss, and tell me the number.

---

## 2. Why a lost node could not rejoin

Two separate causes, both fixed:

**Timeouts were too twitchy.** Loss was declared after ~3 missed heartbeats. A couple of unlucky
collisions could evict a perfectly healthy node.

| | Was | Now |
|---|---|---|
| `HB_INTERVAL_MS` | 10 s | **8 s** |
| `NEIGHBOR_TIMEOUT_MS` | 35 s (~3 missed) | **45 s (~5 missed)** |
| `ROUTE_TIMEOUT_MS` | 50 s | **60 s** |

**Nothing accelerated the reunion.** Now, while *any* known node is missing, every node beacons
every **`RECONNECT_HB_MS` (4 s)** instead of 8 s — both sides hunt for each other, so they meet in
seconds instead of waiting out a slow heartbeat cycle.

**And the stale-msgId trap, properly closed this time.** Phase 4 stopped deduplicating heartbeats,
which handled the common case. Phase 6 adds `seenForget(node)` on reconnection: when a node comes
back, its old `(src, msgId)` entries are purged from the ring, so a node that rebooted and
restarted its counter at 1 can never be filtered as a duplicate. The same fix is in the Pi
(`mesh.py: _seen_forget`).

---

## 3. GPS

The parser was already correct — the problem is visibility. Two additions:

**`N` — raw NMEA dump (5 s).** The fastest way to tell a miswired module from one that simply has
no sky view:

```
---- RAW NMEA (5 s) --------------------------------
nothing at all  -> check GPS TX -> GPIO16, and 9600 baud
$G..GGA with 00 sats -> module fine, no sky view yet
$GNRMC,,V,,,,,,,,,,N*4D
$GNGGA,,,,,,0,00,99.99,,,,,,*56
```

**GPS state on the `[stat]` line** — `gps=FIX/7 nmea=4821`:
- `nmea` climbing → module wired and talking
- `nmea` stuck at 0 → GPS TX is not on GPIO 16, or it is not at 9600 baud
- `nofix` with `nmea` climbing → module fine, needs sky view. A cold start outdoors is 30 s to a
  few minutes; **indoors it will never fix.** That is physics, not firmware.

### One thing worth knowing

`LOCATION_PREFER_PHONE` is still **1**, which you chose in Phase 2 — a phone position wins for
5 minutes. So a **perfectly working GPS fix can look ignored**, because the node keeps reporting
`PHONE`. Press **`g`** to see both sources side by side:

```
---- LOCATION ------------------------------------------
  in use   : PHONE  23.797810, 90.449720  (42s old)
  preference: PHONE first
  GPS module: FIX  sats=7  nmea lines=4821  last fix 2s ago
  phone     : have position  23.797810, 90.449720  acc 12m  42s ago  (1 updates)
```

If you would rather the module win when it has a live fix, set
`#define LOCATION_PREFER_PHONE 0` **in all three sketches**.

---

## Test procedure

### Test 1 — measure the loop  ← do this first
Flash all three, let them run 5 minutes, press `s` on each.
**Pass:** `maxloop=` in single-digit ms on all three. If any node shows tens of ms, tell me which
and what it was doing.

### Test 2 — stability soak
Leave all three plus the Pi running **30 minutes**, phone on one portal. Press `s` every 10 min.
**Pass:** `neigh=3` on every node throughout (A, B, C and PI all see each other), no `[mesh] LOST`
lines, `minheap` flat, `rst=POWERON`.

### Test 3 — deliberate loss and rejoin
Power Node C off. Wait for `[mesh] LOST C` on A and B (~45 s). Power C back on.
**Pass:** within **~5 seconds** A and B log `[mesh] RECONNECTED C` and `[route] RECOVERED C`, and
C reappears on the Pi dashboard. No manual intervention.

### Test 4 — repeat it
Do Test 3 five times in a row, on different nodes.
**Pass:** rejoins every time. This is the one that was failing.

### Test 5 — GPS diagnosis
Press `N` on a node with a GPS attached.
**Pass:** NMEA sentences scroll. Then take it outdoors/to a window for 5–10 min and press `g`.
**Pass:** `GPS module: FIX sats=N`.

### Test 6 — verbose trace still available
Press `v`, confirm `[rx]` lines resume; press `v` again to silence them.
**Pass:** toggles, and `maxloop` rises while it is on — which is the point.

---

## Completion criteria

- [ ] Test 1 — `maxloop` single-digit ms on all three nodes
- [ ] Test 2 — 30-min soak, `neigh=3` throughout, no LOST lines
- [ ] **Test 3 — a powered-off node rejoins within ~5 s**
- [ ] **Test 4 — rejoins reliably, 5 times out of 5**
- [ ] Test 5 — `N` shows NMEA; module reaches `FIX` outdoors
- [ ] Test 6 — `v` toggles the rx trace

Record results in `../docs/TEST_REPORT.md`.

---

## Serial commands (full list)

| Key | Does |
|---|---|
| `n` `r` `g` `s` | neighbours · routes · location detail · stats |
| `a` `b` `c` | send a test message to that node |
| `t` `p` | repeat-send toggle · next OLED page |
| `S` `C` | trigger SOS · clear alert |
| `1`–`4` | reports: Victim Found / Medical / Blocked / Danger |
| `5`–`8` | status: Available / Searching / Need Assist / Emergency |
| **`v`** | **toggle per-packet rx logging** (off by default now) |
| **`N`** | **raw NMEA dump, 5 s** |
| **`R`** | **manual rescan/reconnect** — reinit the radio + rebroadcast now (also on the portal) |
| `x` `h` | corrupt-frame test · help |

## Pi side

The Pi codebase moved to [`development/pi/`](../pi/) — one canonical copy instead of duplicating
it into every phase folder (see the Revision below for why). Changes this phase:
`mesh.py` timings aligned with the nodes (HB 8 s, neighbour 45 s, route 60 s) and `_seen_forget()`
added so the Pi also re-accepts a rebooted node immediately.

---

## Revision — critical fix: `oledPush()` was calling itself

**Root cause of "nodes rebooting, not rejoining, OLED stuck."** The change-detecting display
function introduced earlier in this phase had a copy-paste defect: instead of drawing, it called
**itself**:

```c
void oledPush(char l[5][26]) {
  ...
  oledPush(l);   // <-- should have been oledClear(); ...; oledShow();
}
```

Every time anything on screen changed — which is most seconds, since the uptime counter alone
changes — this recursed until the stack overflowed, crashing the node. The watchdog or a stack-guard
trap then reset it, and because the crash happened mid-draw, the OLED was left showing whatever
was on it before the crash: **stuck**. This also explains why nodes struggled to be found again —
a node stuck in a reboot loop is off the air far more than it's on it.

Fixed in all three sketches: `oledPush()` now actually clears, draws, and shows.

## Revision — Pi: GPIO25 "already claimed" + one canonical `pi/`

Two Pi-side fixes, from a report that `main.py` failed with the RST pin (GPIO25) already held by
another process, and that testing a change meant re-downloading Leaflet and the Dhaka map tiles.

**Restructured to one location.** `development/pi/` is now canonical — it is *not* copied into
`phase 5/pi/` or `phase 6/pi/` any more (those now just point here). Vendor Leaflet and run
`download_tiles.py` **once**, here; every future phase's Pi fixes land in the same folder and the
cache is never touched again.

**Fixed the actual GPIO leak.** `main.py` blocks in `server.app.run()`; a `KeyboardInterrupt`
(Ctrl+C) propagated straight past the `m.stop(); radio.close()` lines that were written *after*
it, so they never ran — the RST `OutputDevice` was never released, and the next launch found
GPIO25 still claimed. Fixed:
- `app.run()` is now wrapped in `try/finally`, so cleanup always runs
- a `SIGTERM` handler is registered too (`systemctl stop` doesn't raise `KeyboardInterrupt` on its
  own)
- `SX1278.close()` now actually calls `self._rst.close()` — it never did before, it only closed
  the SPI handle
- if the pin genuinely is held by something else, `SX1278()` now raises a message with the exact
  commands to find and stop it, instead of a bare gpiozero traceback

If you still see the claim error after pulling this: something is already running.
```bash
ps aux | grep main.py          # find it
kill <pid>                     # or: sudo pkill -f main.py
systemctl is-active sar-pi      # a service instance too?
sudo systemctl stop sar-pi
```

---

## Revision — nodes disconnect at random, and only a power cycle fixed it

The tell was in that phrasing: **only a power cycle fixed it.** That means the radio was reaching
a bad *internal* state — one only a real hardware reset clears — and nothing in software was
watching for it.

### The gap

`radioOk` is set `true` once, in `radioBegin()` at boot, and **nothing ever set it back to
`false` while the node was running.** The one existing recovery path —
`if (!radioOk && retryTimer.due()) radioBegin();` — could therefore never fire after boot,
no matter how wedged the SX1278 got. A node that lost its radio internally looked, to its own
firmware, exactly like a node with a perfectly healthy radio and no traffic. Only power-cycling
(a real hardware reset pin toggle at power-on) could clear it.

### The fix — a radio-health watchdog that does what your power cycle was doing

One signal cannot lie: **this node's own heartbeat is generated every `HB_INTERVAL_MS`
regardless of whether any other node is nearby.** If it has not gone out successfully in a long
time, the local radio is broken — not the RF link, not the other end. (Using "have I *received*
anything" instead would false-trigger constantly on a node with no peers in range yet, which is
why that signal isn't used.)

`radioWatchdog()` runs every loop:

```c
if (millis() - lastTxOkMs > RADIO_WEDGE_MS) {   // 90s, ~11 missed heartbeats
  radioOk = false;
  radioBegin();                                  // the exact reinit a power cycle forces
  bootBeacons = 4;                                // announce fast, like a real reboot
}
```

`lastTxOkMs` is stamped every time a transmit actually completes. If it goes stale, the node
reinitialises its own radio and immediately re-announces itself — in software, in seconds,
instead of waiting for someone to notice and cycle the power. `wedge=` on the `[stat]` line
counts how many times this has fired; if it climbs, the radio genuinely is glitching (see the
power/decoupling note in the Phase 3 README) — but the node now recovers on its own either way.

### Also added — manual "Search / Reconnect" (as requested)

A **"Search / Reconnect Nearby Nodes"** button is now on the portal, and `R` on serial does the
same thing. Both call `manualRescan()`: force a radio reinit (in case it's the same wedge, caught
early by hand) and rebroadcast immediately rather than waiting for the next scheduled heartbeat.
Use it if a node has vanished from another node's `Conn:` list and hasn't come back on its own.

## Test procedure — verify the fix

### Test 8 — the watchdog actually fires
Force a wedge is hard to do on demand, so instead confirm the mechanism: leave a node running,
watch `wedge=` on `s` stay at `0` for 30+ minutes of normal operation (it should — this is a
last-resort net, not something that should trip in normal conditions).

### Test 9 — manual rescan works
Press `R` on serial (or the portal button). **Pass:**
```
[radio] manual rescan requested (serial) - reinit + fast beacon
[radio] LoRa OK  SF7 BW125 CRC=on sync=0x2A pwr=17dBm
```
and peers log `[mesh] RECONNECTED <id>` within a couple of seconds.

### Test 10 — the long unattended soak
This is the real test for the original report. Run all three nodes **unattended for several
hours** (the failure was intermittent, so 30 minutes may not reproduce it). **Pass:** no node
ever needs a manual power cycle; if one does wedge, `wedge=` increments and `[mesh] LOST` /
`RECONNECTED` bracket it within `RADIO_WEDGE_MS` (90 s) with no human involved.

## Completion criteria (added)

- [ ] Test 8 — `wedge=0` through a normal 30-min run
- [ ] Test 9 — manual rescan (button and `R`) reinitialises and reconnects
- [ ] **Test 10 — an unattended multi-hour run needs zero power cycles**
