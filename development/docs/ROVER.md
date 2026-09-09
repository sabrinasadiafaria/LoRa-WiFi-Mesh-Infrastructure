# ROVER

Design notes for the Phase 8 autonomous rescue rover (`development/phase 8/Node Rover.md`). For
wiring, test procedure and completion criteria see `../phase 8/README.md` - this file is the
"why", that one is the "how to run it".

## What it is

The rover is not a separate protocol bolted onto the mesh - it's Node C's Phase 7 firmware (mesh,
radio, routing, self-healing, GPS, SOS) with the Wi-Fi portal removed and a motor + ultrasonic
layer added. It joins as node `R`, is subject to the same duplicate suppression, routing, and
self-healing as A/B/C, and every other node forwards its traffic without knowing anything special
about it.

## Two new wire additions

**`ROVER:` (broadcast, `dest "*"`, forwarded)** - periodic telemetry, payload
`mode,obstacle_cm,battery_pct`, e.g. `AUTO,23,87`. Position is deliberately **not** repeated in
this packet - the rover already sends a normal `GPS:` broadcast like every other node, and the Pi
joins the two by node id (`R`) rather than duplicating fields across two packet types.

`ROVER:` needed A/B/C to gain a forward-only branch (mirroring how `SOS:`/`RPT:` are already
relayed) because broadcast telemetry in this codebase (`GPS`/`HB`/`RT`) is normally **one-hop
only** - `mesh.py`'s `CONSUMED_NO_FWD` and the equivalent `else if` branches on the ESP32 side never
call the forward path for those types. That's fine for HB/RT (every node sends its own, so a
multi-hop node's *neighbour* still hears a fresh one every interval) but wrong for a payload whose
whole point is "here's what's happening at a node that might only be reachable through you right
now" - which is exactly the mobile-relay scenario. So `ROVER:` is forwarded with a decrementing TTL
like `SOS`/`RPT`, not treated like `GPS`/`HB`.

**`CMD:` new verbs (routed, unicast to `R`)** - `FWD`/`BACK`/`LEFT`/`RIGHT`/`STOP` and
`MODE,<MANUAL|AUTO|RELAY>`. These reuse the `CMD:` mechanism Phase 5 introduced for
`WHERE`/`PING`/`SOS`/`SOSCLR` rather than inventing a parallel `MOVE:` packet type, because `CMD:`
already does exactly what driving needs - routed to one destination, forwarded by any node that
isn't the destination, never governed by the duty-cycle limiter (latency matters for a live drive
command the same way it matters for an SOS). The practical win: **A/B/C needed no changes at all**
to carry rover drive commands - their existing "not for me, pass it on" `CMD:` forwarding already
covers it.

## The safety model

Three deliberate layers, each independent of the others:

1. **Bounded manual-drive pulses.** A `FWD`/`BACK`/`LEFT`/`RIGHT` command drives for
   `MANUAL_PULSE_MS` (600 ms) and then stops **on its own**, whether or not another command
   arrives. The dashboard keeps a held direction moving by re-sending inside that window (every
   400 ms); release the button, close the tab, or lose the link entirely, and the rover coasts to a
   stop within one pulse. There is no "the dashboard forgot to send stop" failure mode, because
   stopping is the default outcome, not something that has to be commanded.
2. **Mode gates driving.** `roverManualDrive()` only acts while `roverMode == ROVER_MANUAL`;
   `autoService()` only runs in `ROVER_AUTO`; `RELAY` forces `motorStop()` every loop. Switching
   modes always calls `roverEmergencyStop()` first, so a mode change never inherits whatever the
   previous mode had the motors doing.
3. **Hardware E-STOP.** The SOS button cuts motors on every press (`roverEmergencyStop()`),
   unconditionally, before the existing SOS-alert logic even runs. It cannot be blocked by any
   software state - not a wedged mode, not a stuck AUTO turn, nothing.

Default boot mode is **MANUAL**, specifically so a freshly-powered rover sitting on a bench or
table does not start driving on its own the moment it boots.

## Ultrasonic sensing is interrupt-timed, not `pulseIn()`

The obvious HC-SR04 code blocks on `pulseIn()` for up to its timeout - tens of milliseconds with
nothing in range - which is precisely the class of stall this codebase has spent three phases
(6 and 7's I2C timeout, GPS buffer, and airtime-wait fixes) eliminating from `loop()`. Instead,
`TRIG` fires a bounded ~12 µs pulse (the HC-SR04's own datasheet minimum - the same order of
magnitude as an SPI/I2C transaction already happening elsewhere in this sketch, not the kind of
blocking call being avoided) and `ECHO`'s rising/falling edges are timestamped by a `CHANGE`
interrupt, so `loop()` never waits on the sensor. `ultrasonicService()` polls the result and
re-triggers on a timer, all non-blocking.

## Battery telemetry is a real ADC read, honestly labelled

Per the project plan's own instruction ("add battery ADC read... or clearly label the value
simulated"), `roverBatteryPercent()` reads the actual ADC pin and applies a linear map you
calibrate (`BATTERY_ADC_VMIN`/`VMAX`/`DIVIDER`) - it is not a hardcoded stub. If nothing plausible
is wired (voltage reads near zero) it reports `-1` ("n/a") rather than a fabricated percentage, and
the dashboard shows `n/a` rather than a fake number.

## What was deliberately left out

- **No Wi-Fi portal on the rover itself** - see the Phase 8 README's "Why" section. Remote control
  goes through the Pi dashboard's `CMD:` channel, which every node already forwards.
- **No PWM speed control** - `EN` pins are a hard on/off, not `ledcWrite()`-driven. This sidesteps
  an ESP32 Arduino core version dependency (the LEDC API changed between core 2.x and 3.x) for a
  feature the plan's own spec ("fwd/back/left/right/stop") didn't ask for. The pins are already
  broken out separately, so PWM speed is a drop-in addition later if wanted.
- **Position is not duplicated into `ROVER:`** - see the wire-format note above.
