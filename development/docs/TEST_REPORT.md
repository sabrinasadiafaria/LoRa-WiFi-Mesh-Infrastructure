# Test Report

This file is the deliverable for **Phase 9** (integration, tuning, range
test). Everything here is filled in from measurements taken during the
phase. The structure mirrors `phase 9/README.md` so a reviewer can find
any section in five seconds.

The numbers in this file are the source of truth for the day of the demo.
Anything quoted in `docs/DEMO_SCRIPT.md` or `docs/LIMITATIONS.md` should
come from here.

---

## §0 — bench pre-flight

Tick the box, paste the relevant line of serial output. *Do not skip this
even if "it worked yesterday".*

| Check | Pass / Fail | Evidence |
|---|---|---|
| Node A boots, joins mesh | | `RT:` routing entry for B, C within 60 s |
| Node B boots, joins mesh | | same |
| Node C boots, joins mesh | | same |
| Rover joins as `R`, mode MANUAL | | `MODE:MANUAL` on serial; dashboard Rover panel visible |
| Pi dashboard loads <3 s, 4 panels render, SOS banner hidden | | screenshot in `phase 9/EVIDENCE/` |
| Portal auto-pops on real phone | | `dhcp-discover` from phone MAC in Pi DHCP log |
| All five portal actions work | | list of `r n g s t S C` in Pi `cmd_out` table |
| Watchdog clean on every node | | `last reset: POWERON/SW` on each serial boot banner |
| Last reset reason not BROWNOUT anywhere | | grep all four boots |

**Block:** if any row fails, fix it before §A. Do not start the E2E run
with a known broken piece.

---

## §A — end-to-end scenario (the gate)

This is the run from `docs/PLAN.md` §12 Phase 7 / `docs/DEMO_SCRIPT.md`,
mapped to measured timings.

Run **three times**. Each run is its own table; paste the times in.

### Run 1 — date / operator / hardware rev

| Step | Time expected | Time observed | Pass | Notes |
|---|---|---|---|---|
| 1. Phone joins Node A portal | < 5 s | | | |
| 2. Phone shares GPS | < 2 s to mesh | | | |
| 3. Phone sends a TEXT | < 3 s to Node C | | | |
| 4. Portal SOS raised | < 2 s to dashboard SOS banner | | | |
| 5. SOS appears on every node OLED | < 3 s | | | |
| 6. Rover dispatched from dashboard | < 1 s to first FWD frame on R | | | |
| 7. Rover in AUTO, no collision | 5 min | | | |
| 8. Node B powered off | | | | |
| 9. Dashboard shows B offline + heal | < 60 s | | | |
| 10. TEXT from dashboard to C via alternate route | < 3 s | | | |
| 11. Node B restored | | | | |
| 12. Route recovered | < 90 s | | | |
| **Run 1 result** | | | **PASS / FAIL** | |

### Run 2 — same script, fresh power-on

(copy the table; aim for "boring" identical timings)

### Run 3 — same script, with rover mid-drive

(this is the one that catches resource contention — rover in AUTO at
the same time the phone is sharing location at the same time B is off)

**Phase 9 gate:** all three rows **PASS**. Any one failure = phase fail.
Re-run §0 before retrying.

---

## §B — tuning pass log

Filled in as each knob is changed. **One row per change.** See
`docs/TUNING.md` for what to measure.

| ts | knob | old value | new value | measurement before | measurement after | kept? | reason |
|---|---|---|---|---|---|---|---|

(Empty rows are fine if nothing was changed — that itself is data:
"the defaults held up under measurement".)

---

## §C — 2-hour soak

```
start ts        :
end ts          :
nodes powered   : A B C R Pi
user activity   : none
```

| Property | Target | Measured |
|---|---|---|
| Watchdog resets | 0 | |
| Heap trend (Pi) | flat within ±2 KB | |
| Heap trend (any node) | flat within ±2 KB | |
| Missed HBs counted by Pi | 0 | |
| Packet-loss % (HB stream) | < 2 % | |
| Route flaps | 0 | |
| Portal connections | 0 (no phone during soak) | |
| Rover telemetry freshness | every 10 s ± 2 s | |
| Total packets received by Pi | (sanity floor) | |

If any target is missed, §B is incomplete — re-run after tuning.

Raw heap trace: `phase 9/EVIDENCE/heap_<node>_runN.csv`.

---

## §D — outdoor range test

Filled in from `phase 9/TEMPLATES/rssi_table_template.csv`. Copy the
table in below, then summarise:

```
date            :
operator        :
node under test :
node id         : (e.g. R)
```

| distance (m) | obstacle | RSSI (dBm) | SNR (dB) | loss % | notes |
|---|---|---|---|---|---|

### Headline numbers

- **90 % packet-loss radius (line of sight):**        ___ m
- **90 % packet-loss radius (one brick wall):**       ___ m
- **90 % packet-loss radius (two walls / one floor):** ___ m
- **Usable demo radius at the chosen SF:**            ___ m
- **Demo room longest diagonal:**                     ___ m
- **Net headroom:**                                   ___ m  ← demo radius − usable radius; negative means demo needs the rover as relay

---

## §E — duplicate-forward check

Phase 0 bug #11 was about `forwardPacket()` having no seen-ID cache.
Phase 1's `packet.h.md` added one. Confirm it's still working: send a
single `DATA:` A→C through B, count how many times the Pi sees it.

| Expected forwards | Observed forwards | Δ | Pass? |
|---|---|---|---|
| 2 (A, B) | | | |

(Same for `CMD:`, `RPT:`, `SOS:` — one row per type.)

---

## §F — what I would change before the real demo

Anything surfaced in §A–§E that needs a code change, listed here so it
doesn't get lost. Don't patch from this file — file a defect and address
in a follow-up phase.

1. ...
2. ...

If this list is empty, Phase 9 is done.

---

## §G — sign-off

```
operator         :
date             :
reviewer         :
phase 9 status   : PASS / FAIL
demo radius OK   : yes / no (relay required / no)
```

The Phase 10 deliverable (`docs/DEMO_SCRIPT.md`,
`docs/FINAL_REPORT.md`) copies headline numbers from §A, §C and §D.
Phase 9 is not done until this file is signed.
