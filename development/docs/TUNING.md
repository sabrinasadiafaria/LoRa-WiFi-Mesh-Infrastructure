# Tuning

Every constant in the project that affects *behaviour* lives in
`firmware/common/config.h.md` (each node's sketch also re-states the
tunable block at the top — **change one, change all three**).

This file is the playbook for the Phase 9 tuning pass. It says which
knobs are worth touching, what to measure before and after, and the
default starting values so a fresh reviewer can tell whether a value is
"deliberate" or "left over from a copy-paste".

Nothing here changes code. Tuning is a measurement-first activity: change
a knob only when a number says you should.

---

## Tuning order

Do them in this order. Each step has a measurement that gates the next.

1. **SF + BW + TX power** — radio PHY. Decides range, airtime, and the
   baseline collision rate. Once set, almost everything else measures
   against it.
2. **Beacon / heartbeat interval** — how often every node broadcasts
   `HB:` and `GPS:`. The single biggest knob for collision rate and for
   how fast a dead node is noticed.
3. **Dead-node timeout** — how long a node is silent before the others
   flip it to offline. Must be ≥ 3× the beacon interval to ride out one
   dropped packet.
4. **Route timeout + route-flush jitter** — how long a route survives
   without being refreshed. Drives how fast the mesh self-heals.
5. **Text/SOS retry counts + backoff** — application-layer reliability
   for messages.
6. **Rover-specific** — `MANUAL_PULSE_MS`, `AUTO_OBSTACLE_CM`,
   `AUTO_TURN_MS_MIN/MAX`, `ULTRASONIC_FAULT_MISSES`.

Items 7–11 (memory, UI, watchdog, portal) are not "tuned" — they are
either correct or they are a bug.

---

## Knobs table

The values below are the **starting defaults** that ship in
`firmware/common/config.h.md`. Do not change a value without a row in
the Phase 9 `TEST_REPORT.md` saying why.

| Constant | Where | Default | What it controls | How to measure |
|---|---|---|---|---|
| `LORA_FREQUENCY` | config.h | 433 MHz | RF carrier | n/a — must match the band the modules are tuned for |
| `LORA_SPREADING_FACTOR` | config.h | 7 | SF7..SF12 | range vs airtime trade; SF7 = ~1×, SF12 = ~64× airtime |
| `LORA_BANDWIDTH` | config.h | 125 kHz | 7.8–500 kHz | narrower = more sensitive, less throughput |
| `LORA_CODING_RATE` | config.h | 4/5 | 4/5..4/8 | forward-error-correction overhead |
| `LORA_TX_POWER` | config.h | 17 dBm | 2..20 dBm | regulatory cap at 433 MHz is 10 mW EIRP in many regions; 17 dBm exceeds it |
| `LORA_SYNC_WORD` | config.h | 0xF3 | private | set to anything ≠ 0x12 (the LoRa library default) so we don't hear neighbours |
| `LORA_CRC` | config.h | on | on/off | **must be on**. Off = corrupted packets delivered as data |
| `BEACON_INTERVAL_MS` | config.h | 2 000 | ms | how often `HB:` goes out |
| `GPS_BEACON_INTERVAL_MS` | config.h | 5 000 | ms | how often `GPS:` goes out (longer than HB — GPS payloads are bigger) |
| `DEAD_NODE_TIMEOUT_MS` | config.h | 12 000 | ms | offline threshold |
| `ROUTE_REFRESH_MS` | config.h | 15 000 | ms | RT advertisement period |
| `ROUTE_TIMEOUT_MS` | config.h | 45 000 | ms | route is dropped after this many ms without refresh |
| `SEEN_ID_CACHE_SIZE` | config.h | 32 | entries | duplicate-suppression window |
| `TEXT_RETRY_MAX` | config.h | 3 | retries | per-message |
| `TEXT_RETRY_BACKOFF_MS` | config.h | 500..1500 | ms with jitter | retry wait |
| `MANUAL_PULSE_MS` | rover only | 600 | ms | bounded dead-man-switch drive duration |
| `MANUAL_PULSE_RESEND_MS` | dashboard | 400 | ms | dashboard re-sends a held direction every N ms |
| `AUTO_OBSTACLE_CM` | rover only | 25 | cm | bump threshold; calibrate to actual stopping distance |
| `AUTO_TURN_MS_MIN/MAX` | rover only | 400..900 | ms | random turn duration range |
| `ULTRASONIC_FAULT_MISSES` | rover only | 20 | pings | how many missing echoes = "sensor dead" |

---

## Measurement recipes

### Range vs SF (Step 1)

Walk one node away from a stationary receiver. Log RSSI every 5 m. Fill
`phase 9/TEMPLATES/rssi_table_template.csv`. The headline number is the
**90 % packet-loss distance** at the chosen SF.

| SF | Airtime (50 B packet) | Typical 90 % loss radius (433 MHz, urban) |
|---|---|---|
| 7 | ~50 ms | 200–400 m LOS |
| 9 | ~200 ms | 500–800 m LOS |
| 11 | ~700 ms | 1–2 km LOS |
| 12 | ~1 500 ms | 1.5–3 km LOS (duty-cycle bound) |

If the demo room is 30 m and SF7 is already over-budget on airtime at 4
nodes, **don't raise SF** — that's the wrong knob. Move the nodes, or
add the rover as a relay (which is exactly what it's for).

### Collision rate vs beacon rate (Step 2)

Pick a fixed SF. Vary `BEACON_INTERVAL_MS`. Measure packet-loss % at
each rate over a 5-minute quiet window with all nodes on the bench.

```
loss = (packets_in - packets_out_at_Pi) / packets_in
```

Target: < 2 % at the chosen beacon rate. If higher, the answer is
*longer beacons*, not "tune harder".

### Dead-node flapping (Step 3)

Set a node's range so it's just barely visible (RSSI around −100 dBm).
Watch its state on the dashboard. If it flaps ONLINE/OFFLINE/ONLINE
during a quiet window, raise `DEAD_NODE_TIMEOUT_MS` to ≥ 3×
`BEACON_INTERVAL_MS`. If it stays OFFLINE forever when it should
rejoin, lower it (but not below 2× beacon interval).

### Self-heal latency (Step 4)

Power off Node B. Time from power-off to "Node C says `via PI` or `via R`"
appearing on the dashboard. Target: < 1 minute. If longer, the answer
is *faster route advertisements*, not more aggressive timeouts — the
timeout just makes the apparent heal happen later.

### Rover stopping distance (Step 6)

Place a marker 50 cm in front of the rover. Send `FWD`. Measure how
far past the marker the front bumper rolls before stopping (under
`MANUAL_PULSE_MS` then coast). Set `AUTO_OBSTACLE_CM` to that distance
+ 10 cm safety margin. If the rover still hits things in AUTO, the
problem is the bump-turn logic, not this knob.

---

## What *not* to tune

- **Heap size.** If heap is the limiter, you have a leak. Fix the leak.
- **Serial baud.** 115 200 is the standard. Lower only for diagnostic
  cables that can't keep up.
- **LoRa library defaults.** Any field left at "library default" should
  be set explicitly in `config.h`. The defaults exist for the library
  author's bench, not ours.
- **The packet spec.** v3 is frozen (`docs/PACKET_SPEC.md`). Any change
  here is a protocol-version bump, not a tuning pass.

---

## Tuning workflow

1. Run the Phase 9 bench pre-flight. Confirm everything works.
2. Run the soak at current defaults. Save the numbers.
3. Identify the single biggest source of loss or unreliability from
   those numbers.
4. Change **one** knob.
5. Run the soak again. Compare to step 2.
6. If the change helped, keep it and update `config.h` (and the per-node
   sketch header) and log it in `TEST_REPORT.md` §B.
7. If it didn't help, revert and pick the next-biggest source.

The point of one-at-a-time is so that the recorded number for each knob
actually means something. A pass that touches six knobs in one commit
gives no information.
