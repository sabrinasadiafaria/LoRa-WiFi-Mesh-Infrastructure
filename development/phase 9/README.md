# Phase 9 — Integration, Tuning & Field / Range Test

**Goal:** every subsystem from Phases 1–8 running together, tuned with measured numbers, and
validated at outdoor range — turning four demoable pieces into one coherent system.

This phase has **no firmware changes and no dashboard changes**. It is purely about *running*
what's already there, *measuring* what it actually does, *tuning* the few constants that need
tuning, and *writing the test report*. Anything new that turns up in the test that *requires*
code work is filed as a bug and addressed in a follow-up phase, not silently patched here.

---

## What's in this folder

| File | What |
|---|---|
| `README.md` | this file |
| `TUNING.md` | which constants to measure, in what order, with the knobs table copied from `docs/TUNING.md` |
| `TEST_REPORT.md` | the actual filled-in soak + range + end-to-end results |
| `TEMPLATES/` | copy-paste log capture sheets (RSSI table, heap log template, packet-loss counter template) |

Everything Pi-side lives in `development/pi/` as usual. There is no `phase 9/pi/`.

---

## Why this phase exists separately

Phases 1–8 each verified their piece in isolation. The rover works on the bench. The dashboard
shows the mesh. The portal works on a phone. None of those tests proves the **whole** system
stays up for two hours with a phone attached and the rover driving between two separated nodes.
That's the gap Phase 9 closes.

Three things can only be found by integration:

1. **Resource contention between subsystems.** Phase 0 test 7 confirmed `softAP + LoRa RX`
   coexist on one ESP32, but does not say what happens with `softAP + LoRa RX + GPS + NMEA
   parser + WebServer + telemetry broadcast + serial monitor` all on one core. The answer
   surfaces during a 2 h soak as a rising loop counter or a heap that trends down.
2. **LoRa congestion when everyone talks.** All three static nodes are broadcasting; the rover
   is broadcasting; the gateway is broadcasting. The Phase 7 collision measurement was three
   radios, not five. The full-system number is the one that matters for the demo.
3. **Behaviour under realistic path loss.** Indoor bench tests at 2 m show perfect RSSI. An
   outdoor test with a node behind a brick wall is what proves the demo will work in the
   room where it's actually given.

---

## What "done" means for Phase 9

There is exactly one completion gate, and it is a *scripted end-to-end run*: see
`TEST_REPORT.md` §A. Everything else (soak, range, tuning) feeds into whether that run passes.

The end-to-end scenario is the one called out in `docs/PLAN.md` §12 Phase 7 and reproduced
in `docs/DEMO_SCRIPT.md`. It exercises every proposal "demonstrated capability" line:

1. Phone joins Node A's portal → shares GPS → sends a message.
2. Node A raises SOS from the portal.
3. SOS + location appear on every node OLED and on the Pi dashboard map within ~2 s.
4. Commander dispatches the rover from the dashboard's Rover panel.
5. Node B is powered off → mesh self-heals → dashboard shows it.
6. A TEXT reply from the dashboard reaches Node C.
7. Node B restored → route recovers.

Phase 9 calls this the **E2E scenario** and runs it **three times consecutively**. Any single
failure is a fail for the whole phase.

In parallel:

- A **2-hour soak** with the full system powered and quiet (no commands) shows no watchdog
  reset, no monotonic heap decline, no missed heartbeats.
- An **outdoor range test** with logged RSSI/distance at the chosen SF gives a real usable
  radius for the day of the demo.
- A **tuning pass** records which constants were changed and to what, with the measurement
  that motivated each change.

---

## Test method

### Step 1 — bench pre-flight (do this first, do not skip)

Before the full E2E scenario, confirm every piece individually still works:

- [ ] Node A, B, C boot and join the mesh (routing tables converge in <60 s).
- [ ] Rover joins as `R`, mode `MANUAL`, no drive commands on bench.
- [ ] Pi dashboard loads in <3 s, all four panels render, SOS banner hidden, rover panel visible.
- [ ] Portal auto-pops on a real Android phone, all five portal actions work.
- [ ] Watchdog log on every node is clean (last reset reason `POWERON` or `SW`, not `BROWNOUT`).

This is the same checklist every previous phase ended on, run one final time. **If any of
these fails, fix it before running the scenario.** Phase 9 is not the place to discover a
broken portal.

### Step 2 — capture the soak

| Property | Value |
|---|---|
| Duration | 2 h minimum |
| Nodes powered | A, B, C, R, Pi |
| User activity | none (no commands, no portal connections) |
| Logs captured | each node serial @ 115 200 baud; Pi `journalctl -u sar-dashboard`; RSSI every minute |
| Measured | watchdog resets; `getFreeHeap()` trend; missed HB count (Pi-side); packet-loss %; mesh route stability |

A simple Python tick on the Pi can scrape `getFreeHeap()` from the SSE stream and write a CSV.
The template is in `TEMPLATES/heap_log_template.csv`.

### Step 3 — outdoor range test

Walk one node away from the others, logging RSSI every 5 m. The Phase 0 test 6 was a sanity
check; this is the real number for the demo. Fill `TEMPLATES/rssi_table.csv`.

| Distance (m) | RSSI (dBm) | SNR | Packet-loss % | Notes |
|---|---|---|---|---|
| 5  | | | | line of sight |
| 25 | | | | line of sight |
| 50 | | | | line of sight |
| 100| | | | line of sight |
| 200| | | | line of sight |
| 100| | | | one brick wall between |
| 50 | | | | two brick walls / floor between |

If the line-of-sight radius is shorter than the demo room, **change the demo, not the
modulation** — SF9 is already what Phase 7 chose. Going to SF10/SF11 buys a few metres and
costs ~3× airtime. The right answer for a small room is "drive the rover between them",
which is what the proposal promised.

### Step 4 — end-to-end scenario (the gate)

Run `docs/DEMO_SCRIPT.md` end-to-end, with the rover driving in `AUTO` while the scenario
runs in parallel. Time each step. Record pass/fail per step in `TEST_REPORT.md` §A.

**Three consecutive runs.** Any one failure → phase fail. No "but it worked the second time"
credit; the script must be reliable enough to give live in front of graders.

### Step 5 — tuning pass

After the soak + range + E2E numbers are in, walk `TUNING.md` and only change a knob if the
measurement says to. Typical changes after a real test:

- **Beacon interval**: raise if packet loss is mostly self-inflicted collisions.
- **Heartbeat timeout**: raise if nodes are flapping during normal load.
- **`AUTO_OBSTACLE_CM`**: tune to the rover's actual stopping distance at the chosen speed.
- **Portal's HTTP keep-alive**: shorten if the dashboard's SSE is starved when a phone is
  actively sharing location.

Anything else is "looks wrong to me", which is not a tuning criterion.

---

## What is *not* in Phase 9

- **No new features.** Encryption, duty-cycle enforcement, solar, real field trials are all
  out of scope (proposal §"Future Scope").
- **No refactor.** If the integration test surfaces ugly code, that's a Phase 11 task.
- **No dashboard redesign.** Phase 9 just landed; leave it alone for the demo.
- **No new packets, no protocol changes.** The packet spec is frozen at v3 (`docs/PACKET_SPEC.md`).

---

## Completion criteria

- [ ] Bench pre-flight checklist all green.
- [ ] 2 h soak: zero watchdog resets, heap trend < ±2 KB over the run, missed-HB count
      (Pi-side) = 0, packet-loss % recorded.
- [ ] Outdoor range test: at least three distance + obstacle rows logged with real numbers.
- [ ] E2E scenario passes **3 times consecutively** with timing recorded.
- [ ] `docs/TUNING.md` populated with only the constants that were actually changed and why.
- [ ] `docs/TEST_REPORT.md` filled in (this phase's deliverable).
- [ ] All numbers from above copied into `docs/DEMO_SCRIPT.md` so the demo runner knows
      what to expect on the day.

A reviewer who has never seen the project should be able to read `TEST_REPORT.md` and
understand exactly how well the system works and under what conditions.

---

## Carry-over to Phase 10

Phase 10 = `docs/DEMO_SCRIPT.md`, `docs/ARCHITECTURE.md`, `docs/WIRING.md`,
`docs/LIMITATIONS.md`, `docs/FINAL_REPORT.md`, `development/README.md` rewrite, root
`README.md` pointer. Phase 10 needs Phase 9's numbers to be honest, so the two phases
share a `TEST_REPORT.md` boundary: Phase 9 fills it, Phase 10 quotes it.
