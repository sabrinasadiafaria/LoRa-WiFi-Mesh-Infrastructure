# Phase 4 — Rescue Messaging & SOS

**Goal:** the field-communication layer. A rescuer raises an SOS from a hardware button, the
portal, or serial; it carries the node's **real** position and reaches the whole mesh; every node
in range shows a full-screen alert **that clears itself**. Plus one-tap rescue reports and team
status.

This replaces the old root `phase 11` SOS code. Its bugs, all fixed here:

| Old phase 11 | Phase 4 |
|---|---|
| `sosAlertActive` set true, **never cleared** — screen stuck forever | clears after 60 s, or on a button press |
| SOS sent **hardcoded** Dhaka coordinates | carries `locBest()` — phone fix or GPS module, labelled, with staleness |
| 3× burst blocked the loop `delay(500)` ×3 | three copies queued 1.2 s apart, **non-blocking** |
| button level-triggered, re-fired while held | **edge-detected**; tap = trigger, hold = clear |
| no acknowledgement | ACKs flow back; victim's screen shows `heard by: B,C` |

---

## Files

| File | Node | Display | AP SSID |
|---|---|---|---|
| `Node A.md` | A | 1.3" SH1106 (U8g2) | `SOS_Node_A` |
| `Node B.md` | B | 0.96" SSD1306 (Adafruit) | `SOS_Node_B` |
| `Node C.md` | C | 0.96" SSD1306 (Adafruit) | `SOS_Node_C` |

Complete standalone sketches — select all, paste, upload. Same libraries as Phase 3.
**Flash all three.** Wiring adds the **SOS button: momentary switch from GPIO 4 to GND** (already
in the Phase 3 wiring notes; now actually used).

---

## New packets

```
SOS    | src | *    | id | 4 | lat,lon,message         (3x burst, forwarded)
SOSACK | src | dest | id | 4 | victim,originalMsgId     (relayed toward victim)
RPT    | src | *    | id | 4 | code,lat,lon,team        (forwarded)
STAT   | src | *    | id | 0 | team,state              (not forwarded)
```

`code` ∈ `VICTIM_FOUND` `MEDICAL` `BLOCKED` `DANGER`
`state` ∈ `AVAILABLE` `SEARCHING` `NEED_ASSIST` `EMERGENCY`

Directed text messaging is already there from Phase 3 as the `DATA` packet (`a`/`b`/`c` on serial).

---

## The SOS button

Momentary switch, GPIO 4 to GND (internal pull-up, so it idles HIGH).

| Action | Result |
|---|---|
| **tap** | raise an SOS — or, if a *received* alert is showing, dismiss it |
| **hold > 1.5 s** | dismiss any alert |

Edge-detected and debounced, so holding it does **not** spam SOS packets the way the old code did.

---

## Serial commands (added this phase)

| Key | Does |
|---|---|
| `S` | trigger an SOS (same as the button) |
| `C` | clear the alert screen |
| `1` `2` `3` `4` | rescue report: Victim Found / Medical / Blocked / Danger |
| `5` `6` `7` `8` | team status: Available / Searching / Need Assist / Emergency |

All Phase 3 commands (`n r g s a b c t p x h`) still work. `p` now cycles **4** OLED pages:
status · routes · positions · **team status**.

---

## Portal (new sections)

- **SEND SOS** — big red button, asks for confirmation, broadcasts with the node's position
- **Quick rescue report** — 4 one-tap buttons
- **Team status** — 4 one-tap buttons, current status shown
- **Active emergency** card — appears on every phone connected to any node while an alert is live

---

## Test procedure

### Test 1 — SOS from the button
Press the button on Node A once.
- Node A serial: `[sos] *** SOS TRIGGERED (BUTTON) *** pos 23.79...,90.44... (PHONE)` then `broadcast copy 1/3`, `2/3`, `3/3`
- Node A OLED: full-screen `** S O S ALERT **`, `THIS NODE (A)`, coordinates, `clears in 59s`
- Node B & C: same screen, `VICTIM: A`
- Node A OLED updates to `heard by: B,C` as the ACKs arrive
- After 60 s all three screens return to normal on their own

**Pass:** alert shows on all nodes, ACKs come back, **screen clears itself**.

### Test 2 — SOS with no fix
Before sending any phone position and with no GPS lock, press the button.
**Pass:** SOS still goes out, screen shows `position: NO FIX` — it does not send fake `0,0`.

### Test 3 — SOS from the portal
Connect a phone to `SOS_Node_C`, open the portal, tap **SEND SOS**, confirm.
**Pass:** same as Test 1, victim shows as `C`. The phone's "Active emergency" card appears.

### Test 4 — multi-hop SOS
With Node C out of Node A's direct range (B relaying — the Phase 3 Test 3 setup), send SOS from A.
**Pass:** C still shows the alert; B logs a forward.

### Test 5 — dismiss
While a *received* alert shows on Node B, tap Node B's button.
**Pass:** `[sos] alert cleared (button tap on a received alert)`, screen returns to normal.
The alert stays up on the other nodes until their own timeout.

### Test 6 — quick report + status
Portal on any node → tap **Victim Found**, then **Searching**.
**Pass:** peers log `>>> REPORT from X (team T1): VICTIM_FOUND @ ...` and
`[team] X (team T1) is now SEARCHING`. OLED page 4 (`p` to reach it) shows the status board.

### Test 7 — 30-minute soak
All three up, one phone on a portal, fire an SOS every few minutes. Record `s` every 10 min.
**Pass:** `minheap` flat, `bad`/`drop`/`txstuck` near zero, `rst=POWERON` unchanged, no reboots.

---

## Completion criteria

- [ ] Test 1 — button SOS: alert on all nodes, ACKs return, **auto-clears at 60 s**
- [ ] Test 2 — SOS with no fix shows `NO FIX`, not `0,0`
- [ ] Test 3 — portal SEND SOS works
- [ ] Test 4 — SOS reaches a node that is two hops away
- [ ] Test 5 — button dismisses a received alert
- [ ] Test 6 — reports and status propagate and show on OLED page 4
- [ ] Test 7 — 30-min soak with repeated SOS: heap flat, no reboots

Record results in `../docs/TEST_REPORT.md`.
