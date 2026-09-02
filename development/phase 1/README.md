# Phase 1 — Shared Core Firmware

**Goal:** one clean, non-blocking node skeleton with a framed, CRC-checked packet layer and a
reusable OLED renderer — the foundation every later phase plugs into.

**Deliverable:** three ESP32 nodes that discover each other by heartbeat, show a live neighbour
list with RSSI/SNR, reject corrupted packets, and run for an hour with a flat heap.

---

## Files in this folder

| File | Arduino tab name | What it is |
|---|---|---|
| `config.h.md` | `config.h` | Every pin, timeout and radio setting. The only place constants live. |
| `scheduler.h.md` | `scheduler.h` | `Interval` non-blocking timer — replaces `delay()`. Fixes the stagger-underflow bug. |
| `packet.h.md` | `packet.h` | Frame build/parse per `../docs/PACKET_SPEC.md`, XOR checksum, `SeenCache` duplicate ring. |
| `radio_layer.h.md` | `radio_layer.h` | SX1278 init with explicit PHY, TX queue with gap+jitter, RX pump. |
| `neighbors.h.md` | `neighbors.h` | The single neighbour table (replaces 6 copy-pasted versions). |
| `oled_ui.h.md` | `oled_ui.h` | One API over SH1106 (U8g2) and SSD1306 (Adafruit). |
| `node_core.h.md` | `node_core.h` | The whole node program: `nodeSetup()` / `nodeLoop()`. |
| `Node A.md` | *main `.ino` tab* | 2 `#define`s + `setup`/`loop`. |
| `Node B.md` | *main `.ino` tab* | 2 `#define`s + `setup`/`loop`. |
| `Node C.md` | *main `.ino` tab* | 2 `#define`s + `setup`/`loop`. |

The seven shared tabs are **byte-identical on all three nodes**. Only the two `#define`s in the
main tab differ. Never fork a shared tab per node — that is exactly how the old `phase N/` code
drifted apart.

## How to build one node

1. Arduino IDE → **New Sketch**, save as `Node_A`.
2. For each shared file: **⋮ → New Tab**, name it `config.h` (etc., *including* the `.h`), then
   paste the whole contents of the matching `.md` file.
3. Paste `Node A.md` into the main `Node_A.ino` tab (replacing the empty `setup`/`loop`).
4. **Tools → Board → ESP32 Dev Module**, select the port, Upload.
5. Repeat for Node B and Node C with their own main tabs.

**Libraries required** (Library Manager): `LoRa` (Sandeep Mistry), `U8g2` (Node A),
`Adafruit GFX Library` + `Adafruit SSD1306` (Nodes B & C).

**Wiring:** `../../Hardware_Connections.md`. LoRa VCC on **3.3 V — never 5 V**.

## Expected serial output (115200 baud)

```
[boot] Node A fw v1  heap=298372
[radio] LoRa OK  SF8 BW125 CRC=on sync=0x2A pwr=17dBm
[boot] ready. type 'h' for commands.
[mesh] NEW neighbour B  -41 dBm
[rx] HB from B id=1 ttl=0 rssi=-41 snr=9.8 : 14,297180,1
[stat] up=30s heap=298104 neigh=1 tx=3 rx=2 bad=0 drop=0 q=0
```

## Serial commands

| Key | Does |
|---|---|
| `n` | print the neighbour table |
| `s` | print stats now |
| `x` | transmit a frame with a **deliberately corrupted checksum** |
| `h` | help |

---

## Phase 1 test procedure

### Test 1 — three-node discovery
Power all three. Within ~15 s each OLED should read `Conn: B,C` / `Conn: A,C` / `Conn: A,B`
and each serial log should show two `[mesh] NEW neighbour` lines.
**Pass:** every node sees the other two.

### Test 2 — checksum rejection
On Node A, press `x`. On Nodes B and C, press `s` before and after.
**Pass:** `bad` increments by 1 on both peers, `rx` does **not**, and no new neighbour appears.

### Test 3 — stagger (the old bug, fixed)
Power all three at the same instant and watch the `[rx]` timestamps.
**Pass:** their first heartbeats are spread out, not simultaneous. (The old phase 10/11 code
transmitted all at once because it set its timer into the future — see the comment at the top
of `scheduler.h.md`.)

### Test 4 — neighbour ageing and reconnect
Power off Node C. Within `NEIGHBOR_TIMEOUT_MS` (40 s) A and B log
`[mesh] LOST C` and drop it from `Conn:`. Power C back on.
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
retries every 5 s — it does **not** freeze (the old sketches sat in `while(1);` forever). Reconnect
the wire; within 5 s it should log `[radio] recovered`.

---

## Completion criteria

- [ ] Test 1 — all three nodes discover each other
- [ ] Test 2 — corrupted frames counted as `bad`, never accepted
- [ ] Test 3 — heartbeats are genuinely staggered
- [ ] Test 4 — ageing + reconnect both work
- [ ] Test 5 — **60-minute soak, heap flat, zero resets**
- [ ] Test 6 — radio failure degrades gracefully and self-recovers
- [ ] `../docs/PACKET_SPEC.md` marked **frozen at v1**

Record the results in `../docs/TEST_REPORT.md`. Once these pass, Phase 2 adds routing,
multi-hop forwarding and self-healing on top of this same loop.

## What changed vs the old `phase N/` code

| Old behaviour | Phase 1 |
|---|---|
| `lastBroadcastTime = millis() + jitter` → underflow, fires immediately | `Interval::begin()` moves the timestamp into the *past* |
| `while(1);` on LoRa init failure | reported, retried every 5 s, watchdog still fed |
| CRC off, public sync word `0x12` | `enableCrc()` + private sync word `0x2A` |
| PHY left at library defaults | SF/BW/CR/power set explicitly in `config.h` |
| `String incoming += (char)LoRa.read()` per byte | fixed `char[]` buffers, zero heap churn |
| Neighbour code copy-pasted into 6 files | one `neighbors.h` |
| Duplicates re-processed every time | `SeenCache` ring |
| Emoji on a bitmap font | ASCII only |
| No watchdog | `esp_task_wdt`, 15 s |
