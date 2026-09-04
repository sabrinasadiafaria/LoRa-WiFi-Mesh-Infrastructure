# Phase 6 — Reliability & GPS

Everything Phase 5 did, plus fixes for the three problems that showed up on the bench once the Pi
joined the mesh:

1. nodes randomly got lost — no single culprit, any of A/B/C
2. a lost node could not rejoin
3. the GPS module "should work properly"

**Flash all three node sketches, and re-copy `pi/` to the Pi** (its timings changed to match).

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
| `x` `h` | corrupt-frame test · help |

## Pi side

`pi/` is unchanged except `mesh.py`: timings aligned with the nodes (HB 8 s, neighbour 45 s,
route 60 s) and `_seen_forget()` added so the Pi also re-accepts a rebooted node immediately.
Copy the folder over and restart the service.
