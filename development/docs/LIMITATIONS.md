# Limitations

What this project is, what it isn't, and where the honest line is.
Anything in the **future scope** section is something the project
explicitly *does not* do today.

For the bigger architectural picture see `docs/ARCHITECTURE.md`. For
the spec of the wire protocol see `docs/PACKET_SPEC.md`. For the
demo walkthrough see `docs/DEMO_SCRIPT.md`.

---

## What this project does

- Multi-hop LoRa mesh between ESP32 nodes with auto neighbour
  discovery, distance-vector routing, and self-healing on link loss.
- Real GPS telemetry broadcast over the mesh.
- A hardware SOS button on every static node, broadcast 3× and
  rendered on every other node's OLED, with auto-clear.
- A Wi-Fi captive portal on two of the static nodes and on the Pi,
  so any phone browser can share GPS, raise SOS, file a rescue
  report, pick a team, set a status, and send a TEXT message.
- A Raspberry Pi gateway with its own LoRa radio, a SQLite store, an
  offline-capable Leaflet dashboard, an SSE live event stream, and
  a JSON API for the dashboard + portal pages.
- An autonomous rover (ESP32-S3) with motors + ultrasonic sensor +
  GPS, which is a full mesh member, supports MANUAL/AUTO/RELAY modes,
  and doubles as a mobile LoRa relay.

All five of those were demoed in some form by the end of Phase 9.
Phase 10 ships the documentation so a reviewer can reproduce the
demo from scratch.

---

## What this project does **not** do

### 1. No encryption

LoRa packets are plaintext on the air. There is no AES, no MAC
filter, no replay protection, no key exchange. Anyone with an
SX127x tuned to the same frequency and the same sync word can
read every SOS and inject their own.

The proposal's slide 13 ("Future Scope") already defers this. For
a campus demo on an open band that is the right call — adding
encryption to a 50-byte frame eats airtime and battery. For any
real field deployment it is the **first** thing to add.

### 2. No regulatory duty-cycle enforcement

433 MHz in many regions is subject to duty-cycle limits (typically
1 % or 10 %, depending on the sub-band). The current beacon rate
(`HB` every 15 s + `GPS` every 45 s + `RT` every 30 s + on-demand
`DATA` / `SOS` / `CMD` / `TEXT` / `RPT` / `STAT` / `ROVER`) keeps
us well under any sensible duty cycle for a 3–5 node lab demo,
but there is no code that enforces it. A long burst of rescue
reports at SF9 could exceed 1 % on a sub-band that requires it.

This is a deployment concern, not a demo-day concern.

### 3. Indoor GPS won't fix

A NEO-6M / NEO-M8N needs a sky view. Indoors it will sit in
"Searching Sats" indefinitely. The firmware has a clean fallback
("Searching Sats" banner on the OLED, no `GPS:` broadcast until
the fix is real), and **every node can also accept a phone GPS
location from the captive portal** — for the indoor demo, the
phone's GPS is the primary location source, not the module's.

### 4. Half-duplex radio, no MAC

LoRa SX1278 is half-duplex. While one node is transmitting it
cannot receive, and vice versa. With four static-ish nodes + a
rover + a Pi all beaconing on the same channel, packet loss from
collisions is **expected**. Mitigations the code applies:

- randomized jitter on every periodic broadcast (interval timer
  fires `t = base + random(0, jitter)`),
- private sync word (`0x2A`) so other SX127x users on the band
  don't accidentally collide,
- CRC **on** so corrupted packets are dropped instead of
  delivered,
- seen-ID cache to suppress duplicate forwards,
- 32-entry cache so a packet can't be re-processed for ~16 s
  after first sight,
- beacon rates sized to keep the channel under ~5 % duty cycle.

These mitigate, they do not eliminate. Loss in Phase 9's bench
test was typically <2 % over a 5-minute quiet window. A noisy
real-world environment will see more.

### 5. Five nodes is the realistic ceiling on this code

Distance-vector routing with split horizon is fine for a small,
mostly-static mesh (3–5 nodes, <10 hops). It does not scale to
the 50+ nodes a real SAR operation might field. A real deployment
would want a more efficient protocol (AODV, B.A.T.M.A.N.-adv,
802.15.4g-style mesh) and a routing table backed by persistent
storage on each node. None of that is in scope.

### 6. No persistence on the nodes

Each ESP32 node forgets its node ID, neighbours, routes, last
known positions, and the time on reboot. There is no RTC and no
SPIFFS / LittleFS in the firmware. On power-cycle the node is
fresh; it re-learns everything from neighbours within ~30 s. The
**Pi** persists (SQLite), but the mesh itself does not. A
companion that has been off overnight is "a stranger" to its
neighbours until it beacons long enough to be re-recognised.

### 7. No watchdog across the LoRa link

The ESP32 watchdog (`esp_task_wdt`) protects each node from
single-CPU lockups. It does not protect the *mesh* — there is no
mechanism by which a node can ask "is the gateway alive?" and
reroute if the gateway is down. The Pi is a single point of
failure for the dashboard. The mesh itself continues to function
without it; the dashboard and the portal-injection path are
the things that need the Pi.

### 8. No team-id propagation end-to-end

The phone portal stores the chosen team and the current status in
the Pi's SQLite, and the dashboard reads it from there. That
information **does not** propagate to the mesh's `STAT:` packets
— those are owned by the ESP32 nodes, which don't know about the
phone's session. A real deployment would carry a session id in
`STAT:` so a phone-team can be distinguished from a node-team.

### 9. The rover's obstacle avoidance is deliberately simple

`bump-and-turn` with a single ultrasonic sensor on a panning
servo: drive forward, on obstacle < `AUTO_OBSTACLE_CM` (25 cm by
default) stop, back off, look left, look right, turn toward the
clearer side. It is **not** SLAM, not mapping, not path planning.
It will get stuck in U-shaped obstacles, against low furniture the
ultrasonic doesn't see (chair legs <25 cm tall), and on dark
surfaces that absorb the ultrasonic pulse.

The rover's strength is not its autonomy — it is that it is **also
the network**. The mobile-relay role is the project's signature
feature; the obstacle avoidance is enough to keep it moving.

### 10. Single half-duplex radio, single channel

The entire mesh runs on **one** LoRa channel (433 MHz, default
modulation). There is no frequency hopping, no channel scanning
on interference, no fallback channel. The dashboard's `/api/rescan`
endpoint re-tunes the SX1278 once; it doesn't scan a list. For
a campus demo on a quiet band that's fine; for a real urban
deployment with intermittent interferers it's not enough.

### 11. The ESP32 3V3 regulator is the power budget's bottleneck

A Node A or C running SoftAP + LoRa RX + OLED + GPS draws a
measurable amount of current; the board gets warm. We cut the CPU
to 80 MHz (`CPU_MHZ`) and the AP TX power to 11 dBm to keep the
junction temperature inside the safe zone. On a hot day in direct
sunlight with a black enclosure, that budget is tighter than it
looks.

### 12. No map tiles downloaded automatically

The Leaflet dashboard uses offline OSM tiles. They are downloaded
once by `pi/download_tiles.py` for the bounding box around the
demo location and committed under `dashboard/tiles/`. If the demo
moves to a new city, the tiles must be re-downloaded before the
demo. The Pi serves the tiles from disk; it does not phone home.

---

## Things that are deliberately copy-paste and that's OK

Every node sketch is a single ~3000-line `.md` file. There is no
build system, no shared library, no PlatformIO. This is **by
design**:

- a grader can paste a single file into the Arduino IDE and flash
  a node in two minutes,
- a bug fix in a phase is one git commit on one file, easy to
  review and easy to revert,
- the Markdown-copy-paste convention is preserved from the
  project's original `phase 1/` … `phase 11/` folders at the repo
  root.

The cost is duplication: neighbour code lives in 6 files, NMEA
parser code lives in 3 files, the routing state machine lives in
3. The Phase 9 plan acknowledges this and treats a future
extraction into shared "tabs" as a Phase 11 task — done **only**
if a bug in the shared code appears in two places, not as a
refactor for its own sake.

---

## Future scope (from the proposal)

These are explicitly out of scope for this project and would be the
obvious next things to build:

- camera + thermal + gas/smoke sensors on the rover
- AI victim detection (e.g. YOLO on a Pi attached to the rover)
- drones (the rover is the wheeled version; the same mesh + portal
  architecture extends cleanly to a quadcopter with the same LoRa
  payload)
- solar charging for unattended nodes
- encryption (AES-128 on the LoRa payload; key provisioning
  over the portal)
- offline maps with full region coverage (currently we cache the
  demo city only)
- real field trials outside the lab

---

## Acknowledging limits is part of the deliverable

The proposal's slide 12 ("Demonstrated Capabilities") lists twelve
things the demo must show. This document is the answer to the
implicit thirteenth question — "and what does it not show?" —
asked by anyone who has built a real system. A project that
doesn't know its limits doesn't know what to fix next.
