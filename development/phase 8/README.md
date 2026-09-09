# Phase 8 — Autonomous Rescue Rover (+ mobile LoRa relay)

**Goal:** a fourth, mobile mesh node - motors + an ultrasonic sensor bolted onto the same
mesh/radio/GPS/SOS core every other node already runs - that can drive itself around obstacles,
be driven from the Pi dashboard, and (parked) act as a physical relay that bridges two nodes too
far apart to hear each other directly.

**Deliverable:** the rover joins the mesh as node `R`, shows up on the Pi dashboard with live
mode/obstacle/battery telemetry and a position marker, can be driven with on-screen arrow buttons,
avoids obstacles on its own in AUTO mode, and visibly restores an A↔C link when parked between
them in RELAY mode.

---

## What's in this folder

| File | What |
|---|---|
| `Node A.md`, `Node B.md`, `Node C.md` | Phase 7's node sketches, **unchanged except one thing**: they now relay the rover's `ROVER:` telemetry broadcast, the same way they already relay `SOS:`/`RPT:`. See the "PHASE 8 ADDITION" note at the top of each file. Flash these if you are updating A/B/C from Phase 7. |
| `Node Rover.md` | The new node. Complete standalone sketch, same copy-paste convention as every other phase. |

The Pi side (`development/pi/`) also changed this phase - see below. There is no separate
`phase 8/pi/`; like every phase since 6, Pi fixes land directly in the canonical `development/pi/`.

---

## Why the rover doesn't have its own Wi-Fi portal

Every other portal-capable node (A, C) runs LoRa RX + a SoftAP + HTTP concurrently, which is
already proven to coexist. The rover adds two motors and an ultrasonic sensor to that same single
core, and the plan's own instruction was to keep remote control coming from the **Pi dashboard**,
not a phone connected directly to the rover. So `Node Rover.md` drops Wi-Fi entirely and drive/mode
commands arrive exactly the way `WHERE`/`SOS`/`SOSCLR` already arrive at a node from the Pi:
as a routed `CMD:` packet, introduced in Phase 5, forwarded by **any** node whose destination isn't
itself. That generic "not for me, pass it on" logic in A/B/C already existed and needed **zero
changes** to carry the rover's new verbs (`FWD`/`BACK`/`LEFT`/`RIGHT`/`STOP`/`MODE`) - only the
rover itself had to learn what they mean.

The one thing A/B/C *did* need is on the other direction: the rover's own `ROVER:` telemetry
broadcast (mode/obstacle/battery) needs to reach the Pi even when the rover is out of the Pi's
direct range - which is the entire point of driving it around as a mobile relay. Broadcasts like
`GPS:`/`HB:`/`RT:` are direct-hop-only in this codebase (see `mesh.py`'s `CONSUMED_NO_FWD`), so
without a change `ROVER:` would have the same one-hop-only limitation. A/B/C were given a small,
mechanical forward-only branch for it (mirrors how `RPT:` is already relayed) so the rover's status
reaches the dashboard through whichever node is bridging.

## The safety model for driving it

The rover boots in **MANUAL** mode and will not move on its own. There is no mode where an
un-commanded rover starts driving:

- **MANUAL** - every drive command (`FWD`/`BACK`/`LEFT`/`RIGHT`) moves it for a bounded
  `MANUAL_PULSE_MS` (600 ms) and then it stops **on its own**, command or no command. The dashboard
  re-sends the held direction every 400 ms (inside that window) to keep it moving smoothly; if the
  button is released, or the connection drops entirely, the rover coasts to a stop within 600 ms.
  There is no failure mode where a dropped link leaves it driving.
- **AUTO** - non-blocking bump-turn: forward until the ultrasonic sensor reports something closer
  than `AUTO_OBSTACLE_CM` (25 cm), back off, turn a random direction, resume.
- **RELAY** - motors held off, obstacle scanning off. Drive it into position in MANUAL, then switch
  to RELAY to hold still and be a pure LoRa relay - every mesh node forwards `DATA`/`SOS`/`RPT`/`CMD`
  regardless of mode, so RELAY just means "and don't also drive around while doing it."
- **The SOS button is also a hardware E-STOP.** Every press cuts the motors immediately,
  independent of whatever the SOS-alert logic does with the press. A moving robot needs an override
  that no software state can block.

**Before the wheels ever touch the ground:** power it up, confirm `mode=MANUAL` in the boot banner,
and test `i`/`k`/`j`/`l`/`o` (or the dashboard buttons) on the bench. Confirm forward/back/left/right
are each what you expect. Only then let it drive on the floor, and only then try AUTO near a real
obstacle.

---

## Hardware

**Additional to what A/B/C already use** (LoRa SPI 18/19/23/5/14/26, I2C 21/22, GPS 16/17, SOS
button 4, entropy 34):

| Component | Pins | Notes |
|---|---|---|
| Left motor (H-bridge) | IN1=27, IN2=25, EN=13 | direction-only, EN is a hard on/off, not PWM speed |
| Right motor (H-bridge) | IN1=33, IN2=32, EN=2 | GPIO2 also drives the onboard LED on many boards - harmless, it'll just blink with the right motor |
| Ultrasonic (HC-SR04) | TRIG=15, ECHO=35 | **ECHO is 5V logic and the ESP32 is not 5V tolerant - use a voltage divider (e.g. 1k/2k) or you will damage the pin.** TRIG is a direct ESP32 output, no divider needed. |
| Battery sense (optional) | ADC=36 (VP) | Via a voltage divider sized for your pack. `BATTERY_ADC_VMIN/VMAX/DIVIDER` in the sketch are a starting point for a 2S Li-ion motor pack - **measure your actual divider with a multimeter and correct them**, or the reported percentage is fiction, not a real reading. |

**Mandatory, doubly true with motors on board (see Phase 6/7's brownout notes):**
- **Separate battery for the motors vs the logic (ESP32 + LoRa + GPS + OLED), common ground.**
  Motor stall current pulled through a shared supply will brown out the ESP32 mid-drive - that
  looks exactly like a random reset, not a motor problem, and the boot banner's `BROWNOUT` line is
  where you'll actually see it.
- Flyback diodes / decoupling caps on the H-bridge if your breakout doesn't already have them (most
  L298N boards do).
- **First power-up: wheels off the ground.** See the safety model above.

---

## Test procedure

### Test 1 — joins the mesh like any other node
Flash `Node Rover.md`. Within ~15 s it should appear in A/B/C's `Conn:`/routing table as `R`, and
on the Pi dashboard's node table as `online`.
**Pass:** `R` visible everywhere the mesh already shows A/B/C.

### Test 2 — telemetry reaches the dashboard
Leave the rover running. The dashboard's Rover panel should appear (it's hidden until a rover has
reported in) showing mode, obstacle range, and battery, refreshing roughly every 10 s.
**Pass:** panel appears and updates; `mode=MANUAL` initially.

### Test 3 — manual bench test (wheels OFF the ground)
Press `i`/`k`/`j`/`l`/`o` on serial, or use the dashboard's arrow buttons.
**Pass:** each direction spins the correct wheels the correct way; the rover stops within ~600 ms
of releasing a held dashboard button even without pressing STOP.

### Test 4 — AUTO obstacle avoidance
Wheels on the ground, clear floor space. Switch to AUTO (serial `m`, or dashboard mode select).
Place an obstacle in its path.
**Pass:** it backs off and turns before contact, for at least 5 minutes without a collision or a
reset (`[boot] last reset:` still `POWERON`/`SW`, not `BROWNOUT`).

### Test 5 — the physical E-STOP
While driving in AUTO, press the SOS button.
**Pass:** motors cut immediately regardless of what AUTO was doing; mode does not change (it stays
AUTO but stopped) - switch modes explicitly to resume.

### Test 6 — mobile relay
Separate Node A and Node C beyond direct LoRa range (confirm first: `r` on A shows no route to C
except via B, then also move B out of range too). Drive the rover into position between A and C
with MANUAL, then set it to RELAY.
**Pass:** A↔C traffic (e.g. `c` on A / a DATA send) flows via the rover once it's in position and
not before; `r` on A shows `C via R`.

### Test 7 — multi-hop telemetry
Drive the rover out of the Pi's direct range but still reachable via A/B/C.
**Pass:** the dashboard's Rover panel keeps updating - confirms A/B/C are relaying `ROVER:`, not
just receiving it directly.

## Completion criteria

- [ ] Test 1 — rover joins the mesh, visible on all nodes and the dashboard
- [ ] Test 2 — telemetry (mode/obstacle/battery) reaches the dashboard
- [ ] **Test 3 — bench drive test passes, wheels off the ground, before it ever touches the floor**
- [ ] Test 4 — 5 min collision-free AUTO run
- [ ] Test 5 — SOS button E-STOPs the motors instantly, every time
- [ ] **Test 6 — mobile relay visibly restores an A↔C link**
- [ ] Test 7 — telemetry still reaches the Pi when the rover is only reachable via A/B/C

Record results in `../docs/TEST_REPORT.md`.

## Serial commands (new this phase)

| Key | Does |
|---|---|
| `m` | cycle mode MANUAL → AUTO → RELAY → MANUAL |
| `i` `k` `j` `l` | drive forward / back / left / right (MANUAL only, same bounded pulse as a dashboard command) |
| `o` | stop |
| `u` | print the current ultrasonic reading |

Everything else (`n r g s a|b|c t p S C 1-4 5-8 v N R T h`) is unchanged from Node C.

## Dashboard / Pi changes this phase

- `mesh.py` parses `ROVER:` telemetry (`mode,obstacle_cm,battery_pct`) into a `rover` event.
- `db.py` gets a `rover_status` table and its reading is included in `/api/state`.
- `server.py`'s `/api/command` now accepts `dest: "R"` with verbs `FWD`/`BACK`/`LEFT`/`RIGHT`/
  `STOP`/`MODE` (with `arg` one of `MANUAL`/`AUTO`/`RELAY`), alongside the existing `WHERE`/`SOS`/
  `SOSCLR`/`PING`.
- The dashboard gets a Rover panel (mode/obstacle/battery pills + a directional pad + a mode
  selector). It stays hidden until a rover has actually reported in, so nothing changes for a
  deployment without one.
