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
