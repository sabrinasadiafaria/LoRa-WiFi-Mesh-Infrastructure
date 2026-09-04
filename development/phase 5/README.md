# Phase 5 — Raspberry Pi Command Centre

**Goal:** the Pi joins the mesh as a node (`PI`) with its own SX1278, receives every node's
position / SOS / report / status — directly if in range, multi-hop otherwise — stores it, and
shows it on a live web dashboard with a map. The dashboard can also send messages and commands
back out to any node.

```
   Node C  --LoRa-->  Node B  --LoRa-->  Node A  --LoRa-->  [ PI + SX1278 ]
   (far)              (relay)            (near Pi)                |
                                                           SQLite + Flask
                                                                 |
                                                     http://<pi-ip>:8000  (map dashboard)
```

No USB gateway. The Pi is a peer: it sends `HB` and `RT` so the mesh keeps a route to it, and it
relays traffic like any node.

> **Run the Pi code from [`development/pi/`](../pi/), not from inside this phase folder.**
> It used to be duplicated into every phase (`phase 5/pi/`, `phase 6/pi/`), which meant
> re-vendoring Leaflet and re-downloading the Dhaka map tiles on every change. It now lives in
> one canonical location that accumulates every phase's fixes, the same way the node sketches do.

---

## Two parts

### 1. ESP32 nodes — `Node A.md` / `Node B.md` / `Node C.md`

Phase 4 firmware **plus** a `CMD` handler so the Pi can command a node:

| CMD verb | Node does |
|---|---|
| `WHERE` | replies with a fresh `GPS` packet |
| `PING` | replies `DATA` "pong" |
| `SOS` | raises an SOS on that node (remote trigger) |
| `SOSCLR` | clears that node's alert |

Everything else (SOS button, portal, reports, status, multi-hop, self-healing, reconnect) is
unchanged from Phase 4. Flash all three as before.

### 2. The Pi — `development/pi/` (canonical, not copied per phase — see note below)

| File | What |
|---|---|
| `sx1278.py` | minimal SX1278 SPI driver, PHY hard-matched to the nodes |
| `mesh.py` | the Pi as a mesh node — same wire protocol, routing, forwarding, seen-cache |
| `db.py` | SQLite store (nodes, positions, sos, messages, reports, status, raw log) |
| `server.py` | Flask: dashboard + `/api/state` + `/api/events` (SSE) + `/api/send` + `/api/command` |
| `main.py` | entry point — starts the mesh thread and the web server |
| `fake_radio.py` | `--fake-radio`: synthetic traffic, so the dashboard runs on any laptop |
| `download_tiles.py` | one-time offline map-tile cache for Dhaka |
| `dashboard/` | Leaflet map, node table, SOS banner, reports, messages, send controls |
| `sar-pi.service` | systemd unit to run on boot |
| `requirements.txt` | `flask`, `spidev`, `gpiozero` (+ `lgpio` on Pi 5) |

---

## Wiring — SX1278 to the Pi (SPI0, BCM numbering)

| SX1278 | Pi pin | BCM |
|---|---|---|
| VCC | 3V3 (pin 1 or 17) | — **never 5V** |
| GND | GND | — |
| SCK | pin 23 | GPIO11 |
| MISO | pin 21 | GPIO9 |
| MOSI | pin 19 | GPIO10 |
| NSS | pin 24 | GPIO8 (CE0) |
| RST | pin 22 | GPIO25 |
| DIO0 | — | not required (the driver polls the IRQ register) |

`sudo raspi-config` → Interface Options → **SPI → enable**. Reboot.

## PHY — must match the nodes exactly

`sx1278.py` sets: **433 MHz, SF7, BW 125 kHz, CR 4/5, explicit header, CRC on, sync word 0x2A,
preamble 8, PA_BOOST 17 dBm.** These are the same constants as `development/phase 5/Node *.md`.
If you change `LORA_SF` in the sketches, change `SF` in `sx1278.py` too.

---

## Install & run (Pi has internet)

```bash
cd "LoRa-WiFi-Mesh-Infrastructure/development/pi"
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# vendor Leaflet (see dashboard/leaflet/PUT_LEAFLET_HERE.txt)
cd dashboard/leaflet
curl -LO https://unpkg.com/leaflet@1.9.4/dist/leaflet.js
curl -LO https://unpkg.com/leaflet@1.9.4/dist/leaflet.css
cd ../..

python3 download_tiles.py          # one-time, ~5 min, caches Dhaka tiles
python3 main.py                    # dashboard: http://<pi-ip>:8000/
```

Run on boot: edit paths in `sar-pi.service`, then
`sudo cp sar-pi.service /etc/systemd/system/ && sudo systemctl enable --now sar-pi`.

**No hardware yet?** `python3 main.py --fake-radio` runs the whole dashboard on any PC with
synthetic node traffic.

---

## Test procedure

### Test 1 — Pi hears the mesh (nodes in direct range)
Nodes running Phase 5, Pi running `main.py`. Open the dashboard.
**Pass:** A, B, C appear in the node table as `online` within ~15 s; their `GPS` positions
(send one from a phone portal) show as markers on the map.

### Test 2 — the Pi is routable
On Node A serial, press `r`.
**Pass:** the routing table lists `PI  via PI  1  ...  VALID` (or `via A 2h` from Node C).

### Test 3 — multi-hop to the Pi
Move Node C out of the Pi's range, A near the Pi, B between. Send a position from Node C's portal.
**Pass:** C's marker still updates on the dashboard; Node A (or B) logs a `[fwd]` for C's `GPS`.
*(GPS is broadcast so it may also arrive directly — the point is it arrives even when it can't.)*

### Test 4 — SOS on the dashboard
Press an SOS button on any node.
**Pass:** the red SOS bar appears at the top of the dashboard within ~2 s with the victim ID and
coordinates; clicking it centres the map there; a red ring is drawn at the location.

### Test 5 — send a message from the Pi
Dashboard → "Send to node" → dest `B`, type a message, Send.
**Pass:** Node B's OLED shows `>>> MESSAGE from PI`, and the message appears in the dashboard's
Messages list as `PI → B`.

### Test 6 — command a node
Dashboard → dest `A` → "Ask position".
**Pass:** Node A logs `[cmd] WHERE from PI` and immediately broadcasts a `GPS` packet; A's marker
refreshes on the map. Try "Trigger SOS" and "Clear SOS" too.

### Test 7 — survives a Pi reboot
`sudo reboot` the Pi (or restart `main.py`).
**Pass:** dashboard comes back with the node table and last-known positions intact (read from
`sar.db`); live updates resume.

### Test 8 — 30-minute soak
Everything running, a phone on one portal, an SOS every few minutes.
**Pass:** no node reboots (`rst=POWERON`), dashboard stays `live`, `sar.db` grows steadily,
Pi CPU stays low.

---

## Completion criteria

- [ ] Test 1 — all three nodes show `online` on the dashboard with map markers
- [ ] Test 2 — `PI` is in every node's routing table
- [ ] Test 3 — a node's position reaches the Pi multi-hop
- [ ] Test 4 — SOS surfaces on the dashboard with map location
- [ ] Test 5 — dashboard → node message shows on the node OLED
- [ ] Test 6 — `WHERE` / `SOS` / `SOSCLR` commands work
- [ ] Test 7 — dashboard survives a Pi reboot
- [ ] Test 8 — 30-min soak clean

Record results in `../docs/TEST_REPORT.md`.

---

## Notes

- The Flask dev server is fine for one or two dashboard viewers in a lab. For more,
  `pip install waitress` and run `waitress-serve --port 8000 --call server:app` alongside the
  mesh (or split `main.py` into two processes).
- The dashboard map degrades gracefully: if a tile isn't cached and there's no internet, Leaflet
  shows a grey grid and the markers/trails still work.
- `raw_log` in `sar.db` records every event for the post-mission report — `sqlite3 sar.db
  "SELECT * FROM raw_log ORDER BY ts DESC LIMIT 50"`.
