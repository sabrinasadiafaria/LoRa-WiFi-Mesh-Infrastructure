# Demo Script — 12–15 minute live run

A step-by-step script for the day-of presentation. Every step has a
**visible cue** (something the audience should see on a screen, OLED,
or dashboard), a **spoken line** the presenter can use, and a **timing
budget** that adds up to ~12 minutes for the core script plus optional
extras for extra credit.

Headline numbers in this script come from
`docs/TEST_REPORT.md`. Where Phase 9 hasn't been run yet, the script
keeps a clearly-marked `[PHASE9: …]` placeholder so a real run fills
it in without rewriting the flow.

---

## Setup (T-15 min, before the audience walks in)

| Step | Visible result |
|---|---|
| Power on Nodes A, B, C (separate power banks) | each OLED shows `Last restart was POWERON`, then the LINKS page populating with B / C / R within 30 s |
| Power on Rover (separate motor battery + separate logic battery, common ground) | OLED shows `mode=MANUAL`, joins mesh as `R` |
| Boot the Pi gateway (`sar-pi` service already enabled, or `python3 main.py`) | boot banner lists SF/BW/CRC/sync word — verify it matches the nodes' PHY box printed earlier |
| Open `http://<pi-ip>:8000/` on the projector laptop | dashboard loads in <3 s; 4 panels render; SOS banner hidden; rover panel visible bottom-right |
| Connect a demo phone to `SOS_Node_A` Wi-Fi | portal auto-pops; team picker visible |

If the dashboard is not showing all three static nodes within 60 s of
power-up, **stop the setup, do not start the demo**. Debug first
(check `journalctl -u sar-pi -n 50`, then check the node PHY box on
serial). A broken warmup guarantees a broken demo.

---

## Part 1 — "the network" (~3 min)

Goal: show the mesh is alive, self-discovering, and routed.

### Step 1.1 — auto discovery (1 min)

**Cue:** dashboard NODES panel shows `A`, `B`, `C`, `R` all green /
online; the map shows their last known positions; the LINKS page on
each OLED shows the same list.

> "The four nodes found each other automatically. No one told them
> who's the master. Each one is broadcasting a heartbeat every
> fifteen seconds; each one builds its own neighbour table from what
> it hears."

**Capability:** auto neighbour discovery.

### Step 1.1b — long-range link (30 s)

**Cue:** on the LINKS page of any node, point at the RSSI bar beside
a neighbour's row. Read the dBm number aloud — for the indoor bench
this is typically in the -55 to -75 range, on the outdoor range test
(`docs/TEST_REPORT.md` §D) the same nodes regularly hit -100 dBm at
the edge of the 90 %-loss radius `[PHASE9: ___ m]`. Open the dashboard
NODES panel; the same RSSI is shown in the per-node table.

> "LoRa's range depends on spreading factor and the air. We pin SF7
> for the demo because the airtime-vs-sensitivity trade is right for
> indoor reliability. Flip the spreading factor up in
> `development/phase 9/Node *.md` and the same hardware pushes past
> a kilometre outdoors — measured, not theoretical. The number on
> the OLED is the same physical quantity the radio chip reports."

**Capability:** long-range link, RSSI observability.

### Step 1.2 — heartbeat + RSSI (1 min)

**Cue:** on a Node A or C OLED, cycle to the LINKS page. Point at the
signal bars beside B's row. Open the dashboard NODES panel and point
at the same RSSI number.

> "Every heartbeat carries the sender's ID, uptime, and the
> signal-to-noise ratio of the last packet we heard from them. The
> bar graph on the OLED and the table on the dashboard read the same
> number from the same source."

**Capability:** heartbeat monitoring, RSSI observability.

### Step 1.3 — multi-hop forwarding (1 min)

**Cue:** walk the rover (R) between Node A and Node C so that A↔C
becomes unreachable direct. Open Node A's serial monitor, type `r`
to dump the routing table. Point at `C via R` and the hop count.
Send `TEXT:PI:C:99:hello from A` from the Pi dashboard's
`/api/send`. Watch Node C's OLED scroll the message.

> "When A and C are out of range of each other, the rover acts as a
> mobile LoRa relay. The routing table rebuilt itself — the same
> code that did static multi-hop in Phase 8 now treats the rover as
> just another hop."

**Capability:** multi-hop routing, **mobile relay**.

---

## Part 2 — "the rescue app" (~5 min)

Goal: portal → mesh → dashboard, end-to-end. This is the part the
audience remembers.

### Step 2.1 — phone joins the portal (30 s)

**Cue:** phone already connected from setup. Confirm portal banner
says `Connected to SOS_Node_A`. Refresh; the live peer table shows
A / B / C / R.

> "No app to install. Just connect to the node's Wi-Fi and open the
> browser. On a modern phone the portal auto-pops; otherwise open
> 192.168.4.1."

**Capability:** Wi-Fi captive portal, no app required.

### Step 2.2 — share location (45 s)

**Cue:** tap "Share Location" on the phone. The portal banner goes
green for ~2 s, then returns to ready. The dashboard's POSITIONS
panel updates within 2 s showing `PHONE: <lat>,<lon>`. The phone
marker appears on the map with a `phone` badge.

> "The phone's GPS is injected into the mesh as the new node PHONE.
> Every other node and the Pi see it without anyone running a
> native app."

**Capability:** mobile GPS sharing.

### Step 2.3 — raise SOS from the portal (1 min)

**Cue:** tap "SEND SOS" on the phone. Within 2 s:

- SOS banner slides in red at the top of the dashboard with the
  sender's coordinates.
- Map marker turns into a flashing red ring at the SOS location.
- Node A's OLED (the portal host) flashes the SOS screen.
- Nodes B and C (if they're in mesh range) show the full-screen
  SOS screen with the phone's coordinates.

> "One tap on the phone. The SOS appears on the dashboard, on the
> map with the exact coordinates, and on every other node's OLED.
> Watch the SOS banner."

**Capability:** SOS alerts, captive portal trigger.

### Step 2.4 — acknowledge / clear (30 s)

**Cue:** press the SOS button on Node A once (short press = clear).
SOS banner disappears from the dashboard, ring fades, OLEDs return
to their normal pages.

> "The SOS button is also the clear button. No menu diving, no
> serial command, no reboot. The same physical input is the
> override everywhere on the mesh."

**Capability:** hardware SOS override, SOS auto-clear.

### Step 2.5 — file a rescue report (45 s)

**Cue:** from the phone portal, tap "Victim Found" (or any quick-
report preset). The portal shows a confirmation toast; the
dashboard's REPORTS panel lists the entry; the map shows the
report location.

> "Reports are typed on the phone, sent into the mesh, and shown
> on the command centre. The same UI is also on the Pi's `/portal`
> page for anyone connected to the Pi's own AP."

**Capability:** rescue reports (one-tap presets).

### Step 2.6 — team status (45 s)

**Cue:** on the phone, pick a team from the dropdown and a status
(`SEARCHING` / `OK` / `NEED HELP`). The dashboard's TEAM STATUS
panel updates.

> "Each portal user picks a team once; their current status shows
> up live on the dashboard. This is how the commander knows who's
> where and doing what."

**Capability:** team status board.

### Step 2.7 — text message to a specific node (45 s)

**Cue:** from the phone's send-message field, send
`text to B: confirm position`. Watch Node B's OLED scroll the
message; nothing arrives at A or C.

> "It's routed by node ID, not broadcast. A → B, single hop,
> exactly one recipient. The packet is reliable: it retries with
> ACK, the seen-ID cache suppresses duplicates, and the
> destination node acknowledges receipt."

**Capability:** reliable messaging (ACK + dedup + directed routing).

---

## Part 3 — "the resilience" (~3 min)

Goal: kill a node, watch the mesh route around it.

### Step 3.1 — power off Node B (1 min)

**Cue:** pull Node B's power. Within 12 s:

- Node B's row in the dashboard NODES panel flips to grey /
  `offline`.
- After ~45 s (the route timeout), the routing tables on A, C,
  and R invalidate `via B` entries.
- The dashboard's MESH panel shows the heal: any R route that
  used to say `via B` now says `via R` (rover bridging).

> "Watch Node B drop. Twelve seconds is the heartbeat timeout —
> long enough that a single dropped packet doesn't false-alarm,
> short enough that the operator doesn't sit watching a stale
> screen. Then the routes invalidate at forty-five seconds."

### Step 3.2 — send a message during the gap (45 s)

**Cue:** during the gap, send a TEXT A → C from the phone or
dashboard. The Pi's mesh log shows the route picked the rover
(`via R`).

> "Even mid-event the mesh is finding a new path. There's no
> controller to phone home to and ask for a new route — the
> distance-vector protocol converged by itself."

**Capability:** self-healing rerouting.

### Step 3.3 — restore Node B (1 min)

**Cue:** power Node B back on. Within ~30 s the routing table on
A and C shows `B` directly reachable again, hop count 1. The
message log shows the B row back online in the dashboard.

> "Recovery is symmetric — when the node comes back, the routes
> pick it up. No operator action, no router reboot."

---

## Part 4 — "the rover" (~2 min)

Goal: show the autonomous mesh member with obstacle avoidance and
dashboard control.

### Step 4.1 — manual drive from dashboard (1 min)

**Cue:** click the rover panel's `↑` arrow on the dashboard. The
rover drives forward for ~600 ms then stops on its own. Click
`←` / `→` / `↓`. The rover panel's obstacle distance updates as
the ultrasonic sensor reads.

> "The rover is a full mesh member. Drive commands leave the Pi
> over LoRa, route through whichever node is bridging, and land
> at the rover as a CMD: packet. The rover applies them with a
> bounded pulse — release the button or drop the link and the
> rover stops within 600 ms."

**Capability:** rover drive from dashboard (manual).

### Step 4.2 — autonomous obstacle avoidance (1 min)

**Cue:** click `MODE: AUTO`. Place an obstacle in front of the
rover. It backs off, scans left and right with the servo-mounted
ultrasonic sensor, and turns toward the clearer side. Let it run
for the rest of the demo time.

> "It avoids obstacles on its own. Watch the sensor head sweep
> before each turn — it's not blindly random, it's measuring.
> That's what the look-then-turn upgrade buys over a coin-flip
> turn."

**Capability:** autonomous rover, sensor-guided turning.

### Step 4.3 — rover as physical relay (carry-over)

Already shown in Step 1.3. Mention again at the end:

> "The same rover that just dodged the chair was, two minutes ago,
> the only way Node A and Node C could talk. The robot *is* the
> network."

**Capability:** mobile relay (re-stated as the closing line).

---

## Part 5 — "the limitations" (~1 min, optional but recommended)

Goal: leave the audience with an honest picture.

> "Three things this project is honest about. **One**: the LoRa
> link is not encrypted. The proposal defers encryption to future
> scope; for a campus demo on an open band that's the right call,
> for a real field deployment it would be the first thing to add.
> **Two**: GPS won't get a fix indoors. That's why every node can
> also take a phone location from the portal — the phone GPS is
> the primary source for indoor demos. **Three**: this is a
> half-duplex radio. No node can talk while it's listening, and
> you can hear the consequences in the airtime budget on the
> dashboard. None of those limits are blockers for the demo;
> they're the honest next steps. They're spelled out in
> `docs/LIMITATIONS.md`."

**Capability:** limitations section, honest framing.

---

## Timing budget

| Part | Time | Cumulative |
|---|---|---|
| 1 network | 3.5 min | 3.5 min |
| 2 rescue app | 5 min | 8.5 min |
| 3 resilience | 3 min | 11.5 min |
| 4 rover | 2 min | 13.5 min |
| 5 limitations | 1 min | 14.5 min |
| **Total** | | **~14.5 min** |

Add 5–10 min for Q&A. If running short, **skip Part 5** — the
limitations doc still ships. If running long, **compress Part 2.5**
(reports) and **Part 2.7** (text message) — the same routing
infrastructure is already proven by Part 2.3.

---

## Mapping back to the proposal

Every step in this script is one line in the proposal's
"Demonstrated Capabilities" list (slide 12):

| Step | Capability |
|---|---|
| 1.1 | auto neighbour discovery |
| 1.1b | long-range link, RSSI observability |
| 1.2 | heartbeat monitoring |
| 1.3 | multi-hop routing, mobile relay |
| 2.1 | captive portal, no app |
| 2.2 | mobile GPS sharing |
| 2.3 | SOS alerts (phone → mesh) |
| 2.4 | hardware SOS / clear |
| 2.5 | rescue reports (one-tap presets) |
| 2.6 | team status |
| 2.7 | reliable messaging |
| 3.1–3.3 | self-healing rerouting |
| 4.1 | rover manual drive |
| 4.2 | autonomous rover |
| 4.3 | mobile relay (closing line) |

That's thirteen lines for twelve proposal bullets (long-range link
gets its own 30-second slot). The other twelve are in the order
they make narrative sense.

---

## Pre-demo checklist

Bring this printed:

- [ ] All four nodes powered, on the bench, dashboards green.
- [ ] Pi gateway up, dashboard URL known, projector working.
- [ ] Demo phone charged, Wi-Fi known, GPS on, browser cache cleared.
- [ ] Rover batteries: motor battery fully charged, logic battery
      fully charged.
- [ ] Two obstacles for the rover demo (a chair, a box).
- [ ] The obstacle-avoidance path is clear of cables / bags / feet.
- [ ] `docs/TEST_REPORT.md` §A end-to-end scenario has been signed
      off within the last 24 h (otherwise re-run §0 pre-flight).
- [ ] Headline numbers from `docs/TEST_REPORT.md` ready to quote if
      asked:
  - usable demo radius `[PHASE9: m]`
  - 2 h soak result `[PHASE9: 0 watchdog resets / 0% packet loss]`
  - rover obstacle distance `[PHASE9: AUTO_OBSTACLE_CM = N cm]`

If any of those is missing, do not start the demo. The 12–15 minutes
in front of the audience are not the place to discover a stale
state.
