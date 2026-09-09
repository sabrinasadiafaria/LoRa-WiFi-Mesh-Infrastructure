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

## Hardware — the rover is an ESP32-S3, not a classic ESP32

**Nodes A, B and C stay on the classic ESP32. Only the rover is an S3, and the two pin maps are
completely different — you cannot flash the rover sketch to a classic ESP32 or vice versa.**

Most of the pin numbers A/B/C use simply don't work on an S3:

| Classic ESP32 pins | On the ESP32-S3 |
|---|---|
| 22, 23, 24, 25 | **do not exist** |
| 26–32 | the SPI bus to the flash/PSRAM — touching them crashes the chip |
| 33–37 | used by the **octal PSRAM** on N8R8/N16R8 modules (most DevKitC-1 boards) |
| 34–39 "input-only" | the S3 has **no input-only pins**; all of these are ordinary GPIO |
| ADC on 32–39 | S3 **ADC1 is GPIO 1–10 only** |

Also reserved on the S3 and left unused here: **19/20** (native USB D−/D+), **43/44** (UART0 /
serial monitor), **0, 3, 45, 46** (strapping pins), **38 and 48** (onboard RGB LED — which one
depends on board revision). Everything below comes from the safe set **1–18, 21, 39–42, 47**.
GPIO 39–42 are also the JTAG pins; fine as GPIO, it only matters if you want hardware JTAG.

**Board setting in the Arduino IDE: "ESP32S3 Dev Module".** If the serial monitor stays blank
after upload, enable **USB CDC On Boot**.

### Full wiring — Node Rover (ESP32-S3)

| Component | Pin on part | → ESP32-S3 GPIO | Notes |
|---|---|---|---|
| **LoRa SX1278** | SCK | **12** | SPI2 / "FSPI" defaults |
| | MISO | **13** | |
| | MOSI | **11** | |
| | NSS / CS | **10** | |
| | RST | **14** | |
| | DIO0 | **21** | |
| | VCC | **3V3** | **never 5 V** |
| | GND | GND | |
| **OLED SSD1306** | SDA | **8** | I2C defaults |
| | SCL | **9** | |
| | VCC / GND | 3V3 / GND | |
| **NEO-M8N GPS** | TX (module out) | **17** | Serial2 RX |
| | RX (module in) | **18** | Serial2 TX |
| | VCC / GND | 3V3 / GND | |
| **L298N** | IN1 | **5** | left pair direction |
| | IN2 | **6** | |
| | ENA | **4** | **remove the ENA jumper** |
| | IN3 | **7** | right pair direction |
| | IN4 | **16** | |
| | ENB | **42** | **remove the ENB jumper** |
| | +12V terminal | motor battery **+** | see power notes |
| | GND terminal | motor battery **−** *and* ESP32 GND | **common ground is mandatory** |
| | OUT1 / OUT2 | front-left **+** rear-left motors, in parallel | |
| | OUT3 / OUT4 | front-right **+** rear-right motors, in parallel | |
| **HC-SR04** | TRIG | **40** | direct, it's an ESP32 output |
| | ECHO | **41** | **through a divider — see below** |
| | VCC | 5 V | it will not work reliably on 3.3 V |
| | GND | GND | |
| **Servo (SG90/MG90S)** | signal | **39** | 3.3 V signal is fine for these |
| | VCC | 5 V rail, **not** 3V3 | see power notes |
| | GND | GND | |
| **SOS button / E-STOP** | one leg | **15** | other leg to GND; internal pull-up, no resistor |
| **Battery sense** (optional) | divider midpoint | **2** | ADC1_CH1 |
| **Entropy** | — | **1** | **leave unconnected** — it must float |

### The ECHO divider is not optional

The HC-SR04 drives ECHO at **5 V** and the ESP32-S3 is **not 5 V tolerant**. Connecting it directly
will damage the pin.

```
HC-SR04 ECHO ──[ 1k ]──┬── GPIO 41
                       │
                    [ 2k ]
                       │
                      GND
```

That gives 5 V × 2/(1+2) = 3.3 V. Any pair with roughly a 1:2 ratio works (1k/2k, 10k/20k).
TRIG needs no divider — it's an output from the ESP32 into the sensor.

### Four motors on a two-channel L298N

The L298N has two channels and there are four motors, so they go on in **pairs, in parallel**:
both left motors to OUT1/OUT2, both right motors to OUT3/OUT4. Each channel then drives two.

- A 6 V 100 RPM BO gear motor draws roughly **150 mA** free-running and **~700–800 mA** stalled, so
  a channel sees ~300 mA normally and up to ~1.6 A if both wheels on that side jam. That is inside
  the L298N's 2 A per channel, but **fit the heatsink** — it will get hot.
- **The L298N drops about 1.4–2 V.** To actually get 6 V at the motors you need roughly **7.5–8 V
  in** — a 2S Li-ion pack (7.4 V) is close to ideal, 6×AA (9 V) also works. Feeding it 5 V leaves
  only ~3.5 V at the motors and they will be weak and stall easily.
- **Remove the ENA and ENB jumpers.** With them fitted the driver ignores GPIO 4 and 42 and the
  motors are permanently enabled — the sketch's stop and E-STOP would do nothing.
- If Vin is above 12 V, also remove the on-board 5 V regulator jumper.

### Power — two supplies, one ground

**This matters more here than anywhere else in the project.** Motor inrush pulled through a shared
supply browns out the ESP32 mid-drive, and it looks exactly like a random reset rather than a motor
problem. Phases 6 and 7 already chased this on the static nodes.

- **Motor battery** → L298N `+12V`/`GND` only.
- **Logic supply** (separate power bank or BEC) → ESP32-S3, LoRa, OLED, GPS.
- **Tie the two grounds together.** Without a common ground the L298N inputs float and the motors
  behave randomly.
- Do **not** run the ESP32 off the L298N's on-board 5 V output while the motors are moving.
- The **servo** also belongs on the 5 V rail, not on the ESP32's 3V3 pin — an SG90 can pull several
  hundred mA when it stalls and will drag the 3.3 V rail down with it.
- The boot banner's `WHY DID THIS NODE LAST RESTART?` box says `BROWNOUT` when this is happening.
- **First power-up: wheels off the ground.**

## Bugs found in the rover code (all fixed)

Four real defects, found reviewing `Node Rover.md` before the S3 port. Two of them are safety
issues on a machine that drives itself.

### 1. A dead ultrasonic sensor read as "path clear" *(safety)*

`ultrasonicCm = -1` was used for both "nothing within range" and "no echo came back", and AUTO
tested `ultrasonicCm > 0 && ultrasonicCm < AUTO_OBSTACLE_CM`. So an **unplugged or failed sensor
meant no obstacle was ever detected** and the rover drove forward until it hit something.

The fix distinguishes the two, which is possible because a working HC-SR04 with an empty room in
front of it **still pulses ECHO** (~38 ms). The ISR now records whether ECHO rose *at all*:

- rising edge seen, no falling edge in time → nothing in range. Keep driving.
- **no rising edge at all**, `ULTRASONIC_FAULT_MISSES` (20 pings ≈ 2 s) in a row → the sensor is
  not answering. AUTO stops the motors and refuses to drive until it comes back.

### 2. The random turn wasn't random — and was always the shortest *(behaviour)*

```c
} else { // RA_TURN
  uint32_t turnMs = AUTO_TURN_MS_MIN + random(0, AUTO_TURN_MS_MAX - AUTO_TURN_MS_MIN);
  if (now - autoStateSince > turnMs) { ... }
```

`turnMs` was drawn **fresh on every loop pass**. The turn ended as soon as the elapsed time beat
*any one* low draw, so with a loop running ~1000×/s it ended at essentially `AUTO_TURN_MS_MIN`
every time. The rover always turned the same short amount, which is exactly the behaviour that
leaves it nose-into-a-corner. The duration is now **latched once** when the turn starts.

### 3. `millis() + MANUAL_PULSE_MS` stored in the future *(latent)*

```c
manualDriveUntilMs = millis() + MANUAL_PULSE_MS;   // ...
if (manualDriving && millis() > manualDriveUntilMs) { motorStop(); }
```

This is the same unsigned-wrap pattern the project's own `Interval` helper exists to avoid — it is
documented as bug #2 in the Phase 0 audit. Now stores the **start** time and compares elapsed.

### 4. A late echo was credited to the next ping

`echoNewReading` was never cleared before triggering, so an echo that arrived after its own
timeout was consumed as the *next* ping's reading — a stale distance reported as current. It is now
cleared in `ultrasonicTrigger()`.

### Also changed

- **AUTO now looks before it turns.** With the sensor on a servo, hitting an obstacle triggers
  back off → stop → look left → look right → **turn toward whichever side is actually clearer**,
  instead of guessing. Random choice is kept only as the tie-break.
- Drive pins are no longer rewritten on every loop pass while going straight.
- `roverEmergencyStop()` clears the new `motorsMoving` flag, so an E-STOP during AUTO cannot be
  undone by the next loop pass re-asserting forward.

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

### Test 3b — the servo actually moves
Press `w` three times and watch the sensor head. It must physically swing left and right.
**Pass:** it moves. If it does not, AUTO cannot choose a turn direction and falls back to a random
one - and check the servo is on 5V, not the ESP32 3V3 pin.

### Test 3c — ultrasonic fault detection
Unplug the HC-SR04 ECHO wire, then switch to AUTO.
**Pass:** the rover does NOT drive. Serial repeats `AUTO HALTED - ultrasonic not responding`.
Reconnect it and AUTO resumes. This is the check that a dead sensor cannot read as "path clear".

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
| `u` | print the ultrasonic reading, plus the consecutive-miss count |
| `w` | sweep the servo centre -> left -> right (one step per press) |

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
