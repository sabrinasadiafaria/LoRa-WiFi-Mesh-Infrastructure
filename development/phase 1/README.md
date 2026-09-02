# Phase 1 — Shared Core Firmware

**Goal:** a clean, non-blocking node program with a framed, CRC-checked packet layer — the
foundation every later phase builds on.

**Deliverable:** three ESP32 nodes that discover each other by heartbeat, show a live neighbour
list with RSSI/SNR, reject corrupted packets, and run for an hour with a flat heap.

---

## Files

| File | Node | Display |
|---|---|---|
| `Node A.md` | A | 1.3" SH1106 (U8g2) |
| `Node B.md` | B | 0.96" SSD1306 (Adafruit) |
| `Node C.md` | C | 0.96" SSD1306 (Adafruit) |

Each file is a **complete standalone sketch** — select all, paste into the Arduino IDE, upload.
No tabs, no extra files. Same convention as the root `phase 10/` and `phase 11/` sketches.

**Libraries:** `LoRa` (Sandeep Mistry) · `U8g2` (Node A) · `Adafruit GFX` + `Adafruit SSD1306`
(Nodes B & C).
**Board:** ESP32 Dev Module.
**Wiring:** `../../Hardware_Connections.md`. LoRa VCC on **3.3 V — never 5 V**.

> Node A/B/C are the same program; only `MY_ID` and the display driver differ. If you change a
> constant (e.g. `LORA_SF`), change it in **all three** files.

## Expected serial output (115200 baud)

```
[boot] Node A fw v1  heap=298372
[radio] LoRa OK  SF8 BW125 CRC=on sync=0x2A pwr=17dBm
[boot] ready. type 'h' for commands.
[mesh] NEW neighbour B  -41 dBm
[rx] HB from B id=1 ttl=0 rssi=-41 snr=9.8 : 14,297180,1
[stat] up=30s heap=298104 neigh=1 tx=3 rx=2 bad=0 drop=0 q=0
```

## OLED layout

```
NODE A  fw1
Conn: B,C
B -41dBm snr10
tx12 rx23 bad0
heap 298104 up145s
```

## Serial commands

| Key | Does |
|---|---|
| `n` | print the neighbour table |
| `s` | print stats now |
| `x` | transmit a frame with a **deliberately corrupted checksum** |
| `h` | help |

---

## Test procedure

### Test 1 — three-node discovery
Power all three. Within ~15 s each OLED should read `Conn: B,C` / `Conn: A,C` / `Conn: A,B`
and each serial log should show two `[mesh] NEW neighbour` lines.
**Pass:** every node sees the other two.

### Test 2 — checksum rejection
On Node A press `x`. On Nodes B and C press `s` before and after.
**Pass:** `bad` increments by 1 on both peers, `rx` does **not**, and no new neighbour appears.

### Test 3 — stagger (the old bug, fixed)
Power all three at the same instant and watch the `[rx]` timestamps.
**Pass:** their first heartbeats are spread out, not simultaneous. (The old phase 10/11 code
transmitted all at once because it set its timer into the future — see the comment above
`struct Interval`.)

### Test 4 — neighbour ageing and reconnect
Power off Node C. Within 40 s (`NEIGHBOR_TIMEOUT_MS`) A and B log `[mesh] LOST C` and drop it
from `Conn:`. Power C back on.
**Pass:** both log `[mesh] RECONNECTED C` and it returns to the list.

### Test 5 — 60-minute soak  ← the real gate
Leave all three running for 60 minutes. Record `heap` from the `[stat]` line every 10 minutes.

| Time | Node A heap | Node B heap | Node C heap | resets? |
|---|---|---|---|---|
| 0 | | | | |
| 10 | | | | |
| 20 | | | | |
| 30 | | | | |
| 45 | | | | |
| 60 | | | | |

**Pass:** heap is flat (a few hundred bytes of wobble is fine, a steady downward slope is not),
no node reboots, `bad` and `drop` stay near zero, and all three still list each other.

### Test 6 — radio-failure recovery
Unplug the LoRa module's `NSS` wire and reset the node.
**Pass:** it prints `[radio] LoRa FAIL`, shows it on the OLED, keeps refreshing the display, and
retries every 5 s — it does **not** freeze (the old sketches sat in `while(1);` forever).
Reconnect the wire; within 5 s it should log `[radio] recovered`.

---

## Completion criteria

- [ ] Test 1 — all three nodes discover each other
- [ ] Test 2 — corrupted frames counted as `bad`, never accepted
- [ ] Test 3 — heartbeats are genuinely staggered
- [ ] Test 4 — ageing + reconnect both work
- [ ] Test 5 — **60-minute soak, heap flat, zero resets**
- [ ] Test 6 — radio failure degrades gracefully and self-recovers
- [ ] `../docs/PACKET_SPEC.md` marked **frozen at v1**

Record results in `../docs/TEST_REPORT.md`. Once these pass, Phase 2 adds routing, multi-hop
forwarding and self-healing to the same loop.

## What changed vs the old `phase N/` code

| Old behaviour | Phase 1 |
|---|---|
| `lastBroadcastTime = millis() + jitter` → underflow, fires immediately | `Interval::begin()` moves the timestamp into the *past* |
| `while(1);` on LoRa init failure | reported, retried every 5 s, watchdog still fed |
| CRC off, public sync word `0x12` | `enableCrc()` + private sync word `0x2A` |
| PHY left at library defaults | SF/BW/CR/power set explicitly |
| `String incoming += (char)LoRa.read()` per byte | fixed `char[]` buffers, zero heap churn |
| No packet integrity check | XOR checksum + protocol version, both verified |
| Duplicates re-processed every time | `seenOrAdd()` ring |
| `randomSeed(analogRead(0))` — a strapping pin, same on every board | ADC1 GPIO 34 |
| Emoji on a bitmap font | ASCII only |
| No watchdog | `esp_task_wdt`, 15 s |
| Blocking SOS burst deafens radio ~3.5 s | queued TX with gap + jitter, loop never blocks |
