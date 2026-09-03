# Phase 3 — Multi-Hop Mesh (routing + forwarding + self-healing)

**Goal:** Node A can talk to Node C **through** Node B, even when A and C cannot hear each other
directly — and when B dies, the network notices and says so instead of silently swallowing traffic.

This is the capability the project is named for. It existed in the old root `phase 7`–`phase 9`
sketches but was **dropped** when `phase 10` and `phase 11` were written, so the shipping firmware
lost it. Phase 3 brings it back on the tested Phase 1/2 core, with the loop bugs fixed.

---

## Files

| File | Node | Display | AP SSID |
|---|---|---|---|
| `Node A.md` | A | 1.3" SH1106 (U8g2) | `SOS_Node_A` |
| `Node B.md` | B | 0.96" SSD1306 (Adafruit) | `SOS_Node_B` |
| `Node C.md` | C | 0.96" SSD1306 (Adafruit) | `SOS_Node_C` |

Complete standalone sketches — select all, paste, upload. Same libraries as Phase 2.
**Flash all three**; a Phase 2 node will ignore the new packet types.

---

## How routing works here

Two packet types are added:

```
RT   | src | *    | msgid | 0   | dest,hops,via;dest,hops,via;...
DATA | src | dest | msgid | ttl | <message text>
```

A node learns routes two ways:
1. **Anything heard directly** from X → X is reachable in **1 hop via X**.
2. An `RT` advert from S saying *"I reach D in h hops via V"* → D is reachable in **h+1 hops via S**.

**Split horizon** is why the advert carries `via`. If `V` is us, that path only exists *because of
us*, and taking it back would make the hop count climb forever — the classic count-to-infinity.
Phase 3 genuinely discards those entries.

> The old `phase 7`–`phase 9` code *claimed* split horizon in its comments but never implemented
> it. It only bounded the damage with `MAX_HOPS` and a timeout. It also carried a `msgId` on every
> forwarded packet and **never checked it**, so any two nodes with a route to the same destination
> would both re-forward the same packet — a duplicate storm. Phase 3 checks it against the seen-ID
> ring from Phase 1.

A route stops being refreshed → after `ROUTE_TIMEOUT_MS` (45 s) it goes **invalid**. That is the
self-healing trigger.

---

## Serial commands

| Key | Does |
|---|---|
| `r` | **routing table** — dest, via, hops, RSSI, age, valid/invalid |
| `a` `b` `c` | send a test message to that node (multi-hop if needed) |
| `t` | toggle automatic repeat send every 15 s to the last target |
| `p` | jump to the next OLED page |
| `n` | neighbours | 
| `g` | GPS / location detail |
| `s` | stats |
| `x` | send a deliberately corrupted frame |
| `h` | help |

## OLED — now 3 pages, cycling every 4 s

```
page 0            page 1               page 2
NODE A  wifi1     -- ROUTES (2) --     -- NODE POSITIONS --
Conn:B,C R:2      B via B 1h           B 23.7978,90.4497
23.79781,90.4497  C via B 2h           C no fix
PHONE s0 age12s
heap 208912 up600s
```

Page 2 answers the earlier question — you can now see the other nodes' positions on the OLED,
not just in the portal.

---

## Test procedure

### Test 1 — routes form on their own (all three in range)
Power all three, wait ~30 s, press `r` on Node A:
```
---- ROUTING TABLE -------------------------------------
DEST  VIA   HOPS  RSSI    AGE(s)  STATE
B     B     1     -66     4       VALID
C     C     1     -71     7       VALID
```
**Pass:** both peers listed at 1 hop.

### Test 2 — direct message
Press `c` on Node A. Node C should print:
```
>>> MESSAGE from A after 1 hop(s): ping #1 from A
```
**Pass:** message arrives, `1 hop(s)`.

### Test 3 — multi-hop  ← the headline test
Move Node C out of Node A's range, with B in the middle and in range of both. (Indoors: put C in
another room, or wrap it in aluminium foil for a quick fake.) Wait ~30 s, then `r` on A:
```
C     B     2     -66     6       VALID
```
Now press `c` on A. **Pass:**
- Node **B** prints `[fwd] A->C via C (ttl 2)`
- Node **C** prints `>>> MESSAGE from A after 2 hop(s):`
- Node A never hears C directly (`n` on A shows only B)

### Test 4 — self-healing  ← the second headline test
With Test 3 working, press `t` on Node A to start repeat sending, then **power Node B off**.
1. Within ~45 s Node A logs `[route] LOST C - no advert for 45s, invalidating  <<< SELF-HEALING`
2. Further sends print `[data] NO ROUTE to C - nothing sent` (visible failure, not a black hole)
3. Power B back on → within ~20 s Node A logs `[route] RECOVERED C via B 2h  <<< SELF-HEALED`
4. Messages start arriving at C again with no intervention

**Pass:** all four steps, in that order.

### Test 5 — no duplicate storm
With all three in range (so B and C both have routes to each other), press `t` on A and leave it
5 minutes. Press `r` on B and C.
**Pass:** `forwarded=` climbs at most **one per message sent**, not two or more. Any node
forwarding the same `msgId` twice would show as a much higher count.

### Test 6 — 30-minute soak
All three running, repeat-send on, phone attached to one portal. Record `s` every 10 min.
**Pass:** `minheap` levels off, `stack` stays above ~1000, `bad`/`drop` near zero, no reboots
(check `[boot] last reset:` if any node restarts).

---

## Completion criteria

- [ ] Test 1 — routes form automatically
- [ ] Test 2 — direct message delivered, 1 hop
- [ ] **Test 3 — multi-hop A→C via B**
- [ ] **Test 4 — route lost, send refused, route recovered, delivery resumes**
- [ ] Test 5 — no duplicate forwarding
- [ ] Test 6 — 30-min soak clean
- [ ] OLED page 2 shows peer positions

Record results in `../docs/TEST_REPORT.md`.

## What's new vs Phase 2

| | Phase 2 | Phase 3 |
|---|---|---|
| Reach | direct neighbours only | multi-hop, TTL 4 |
| Packets | `HB`, `GPS` | + `RT`, `DATA` |
| Routing | none | distance vector, one entry per destination |
| Loop prevention | — | split horizon + TTL + `MAX_HOPS` bound |
| Duplicate forwards | — | suppressed via the seen-ID ring |
| Failure behaviour | — | route invalidated and reported; recovers on its own |
| OLED | 1 page | 3 cycling pages |
| Forward delay | — | none — the old code did `delay(100)` before every forward |

---

## Revision — reboot and discovery fixes

Applied after Node B kept restarting and the nodes stopped finding each other.
**Node B is the one a phone was attached to; Node A had no phone.** That, plus the fact that the
three sketches are identical apart from the display driver, is what these changes target.

| Change | Was | Now | Why |
|---|---|---|---|
| `LORA_SF` | 8 | **7** | Measured link was −62…−71 dBm at SNR 10–13 dB. SF7 needs about −7.5 dB SNR, so there is ~18 dB of margin. SF7 roughly **halves airtime** (~137 ms → ~72 ms per packet), which halves the chance two nodes collide. Phase 3 added a third broadcast type, so airtime mattered more. |
| `WDT_TIMEOUT_S` | 20 | **60** | Too tight. Web server + DNS + a blocking `LoRa.endPacket()` can legitimately take seconds when a phone is on the portal. 60 s still catches a genuine hang. |
| `GPS_INTERVAL_MS` | 20 s | **30 s** | Fewer transmissions. |
| `HB_INTERVAL_MS` | 12 s | **10 s** | Cheaper at SF7, and faster discovery. |
| `NEIGHBOR_TIMEOUT_MS` | 40 s | **35 s** | Keeps it at ~3 missed heartbeats. |
| `ROUTE_TIMEOUT_MS` | 45 s | **50 s** | ~3 missed route adverts. |
| Portal poll | 3 s | **6 s** | Halves HTTP connection churn on the node serving a phone — the node that reboots. |
| Boot beacons | — | **4 × 3 s** | A node that just rebooted used to wait up to 15 s to announce itself, while peers took 40 s to age it out. It now sends four quick heartbeats, so rediscovery takes seconds. |

**"Nodes can't find each other" was largely a *symptom*:** a node that reboots every couple of
minutes spends much of its life either off-air or not yet re-announced. The boot beacon burst and
the shorter timeouts fix the visible symptom; the reboot itself still has to be identified.

### The reset reason is now impossible to miss

Every node prints this at boot, in a box:

```
############################################################
#  WHY DID THIS NODE LAST RESTART?
#     BROWNOUT - 3.3V rail sagged  <<< POWER PROBLEM
############################################################
```

It also appears on the OLED for a moment during boot (`rst:BROWNOUT`) and on every `[stat]` line
as `rst=BROWNOUT`.

| Reason shown | What it means | Who fixes it |
|---|---|---|
| `BROWNOUT` | the 3.3 V rail sagged under load | **hardware** — better USB supply/cable, and a 470 µF capacitor across 3V3–GND |
| `TASK_WDT` / `INT_WDT` | the loop stalled longer than 60 s | **code** — send me the log, something is blocking |
| `PANIC` | crash: null pointer, bad cast, stack overflow | **code** — send me the log |
| `POWERON` | you applied power or pressed EN | not a fault |

`minheap` on the stat line is the other half: if it keeps sliding toward zero over 30 minutes,
the reboot is memory exhaustion rather than power.

---

## Root cause found — `LoRa.endPacket()` hangs forever

The `TASK_WDT - loop stalled` reset from Node B identified it. Inside the LoRa library:

```cpp
int LoRaClass::endPacket(bool async) {
  ...
  while ((readRegister(REG_IRQ_FLAGS) & IRQ_TX_DONE_MASK) == 0) {
    yield();          // <-- no timeout, ever
  }
```

**There is no timeout.** If the SX1278 does not raise `TX_DONE` — a SPI glitch, or the 3.3 V rail
dipping because the Wi-Fi AP transmitted at the same instant — that loop never returns and the
task watchdog kills the node. `yield()` does not feed the task watchdog.

That is why **Node B died and Node A did not**: Node B had a phone associated, so its Wi-Fi radio
was actively transmitting alongside LoRa. Same code, different load.

### The fix

Transmission is now **asynchronous and bounded**:

```cpp
LoRa.endPacket(true);         // returns immediately
txInFlight = true;
```
then each loop pass polls `LoRa.isTransmitting()`. If `TX_DONE` has not arrived within
`TX_TIMEOUT_MS` (3 s), the radio is reinitialised and the node carries on instead of hanging.
`radioPoll()` also refuses to touch the receiver while a transmit is in flight — the SX1278 is
half duplex.

A counter `txstuck=` on the `[stat]` line records how often this happens. **If it climbs, the
radio really is glitching and the underlying cause is electrical** (supply, decoupling, wiring) —
but the node stays alive and the mesh keeps running either way.

### A second bug the log exposed

```
E (464) task_wdt: esp_task_wdt_init(517): TWDT already initialized
```

The Arduino ESP32 core starts the task watchdog **before `setup()` runs**, so
`esp_task_wdt_init()` fails and `WDT_TIMEOUT_S` was **silently ignored** in every build so far.
`wdtBegin()` now calls `esp_task_wdt_reconfigure()` first and prints what it actually got:

```
[wdt] task watchdog set to 30s (ok)
```

If that ever says `NOT APPLIED`, the timeout is not what the sketch says it is.

`WDT_TIMEOUT_S` is back down to **30 s** — with transmits bounded at 3 s, nothing should come
close, so a tight watchdog is useful again rather than a nuisance.
