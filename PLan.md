PHASE 1 — Hardware Verification ✅

(Currently completed)

Node A
ESP32
SH1106 OLED
SX1278
Test
OLED
LoRa Initialization

Node B
ESP32-S3
SSD1306 OLED
SX1278
Test
OLED
LoRa Initialization

Deliverable
Both Nodes Ready

--------------------------------------------------

PHASE 2 — Basic LoRa Communication ✅

(Currently completed)

Features
Node A sends
Node B receives
RSSI shown
OLED updated

Deliverable
Reliable One-Way Communication

--------------------------------------------------

PHASE 3 — Two-Way Communication ✅

(Currently completed)

Features
Node A ←→ Node B
Bi-directional messaging
Independent non-blocking timers
OLED updates with received data and RSSI

Deliverable
Bi-directional Communication

--------------------------------------------------

PHASE 4 — Reliable Communication ✅

(Currently completed)

Features
- Packet format: MSG:ID:Payload / ACK:ID
- Automatic ACK replies upon packet receipt
- Duplicate packet detection & filtering
- Retry logic with 100ms ACK delay and randomized backoff jitter
- Verified delivery confirmation & timeout alert

Deliverable
Reliable Messaging Layer

--------------------------------------------------

PHASE 5 — Heartbeat System ✅

(Currently completed)

Features
- Periodic Heartbeat Broadcast (`HB:NODE_ID:UPTIME`)
- Target Node Online/Offline State Tracking
- Timeout Detection (12 seconds threshold)
- OLED display live update

Deliverable
Network Health Monitoring

--------------------------------------------------

PHASE 6 — Node Discovery ✅

(Currently completed)

Features
- Dynamic Neighbor Table array (`struct Neighbor`)
- Auto-discovery on incoming heartbeat packets
- Automatic neighbor list expansion (`NEW NEIGHBOR DISCOVERED`)
- Active/Inactive status management & Timeout pruning (`Neighbor Lost`)
- Reconnection detection (`RECONNECTED`)
- Live OLED rendering of active neighbors & RSSI

Deliverable
Automatic Neighbor Discovery

--------------------------------------------------

PHASE 7 — Routing Table ✅

(Currently completed)

Features
- Distance-Vector Route Advertisement (`RT:SENDER:DEST1,HOPS1;...`)
- Routing Table array (`struct RouteEntry`)
- Distance-Vector loop avoidance algorithm
- Formatted Serial Monitor Routing Table printout

Deliverable
Dynamic Routing Table

--------------------------------------------------

PHASE 8 — Packet Forwarding ✅

(Currently completed)

Features
- Mesh Packet Format: `DATA:SRC:DEST:HOPS:MSG_ID:PAYLOAD`
- Destination check & Multi-Hop Forwarding Engine
- Cross-platform support (ESP32, ESP32-S3, Arduino Nano)
- Max Hop TTL limit protection

Deliverable
First Multi-Hop Network

--------------------------------------------------

PHASE 9 — Self-Healing Mesh ✅

(Currently completed)

Features
- Active Link Health & Timeout Detection (12s threshold)
- Automatic invalidation of dead routes (`ALERT [SELF-HEALING]: Node NODE_B failed!`)
- Dynamic Failover / Re-routing (`>>> SELF-HEALED FORWARD`)
- Automatic Route Recovery upon node reconnection (`>>> RECOVERED ROUTE`)
- Live OLED startup diagnostics on all 3 nodes

Deliverable
Self-Healing Routing

--------------------------------------------------

PHASE 10 — GPS Integration 🔄

Goal
Every node parses real GPS (or simulated backup GPS) and broadcasts telemetry packets across the mesh.

Features
- Hardware Serial GPS Parsing (Neo-6M support via Serial2)
- Telemetry Packet Format: `GPS:SENDER_ID:LAT:LON:BAT:UPTIME`
- Bench test simulated GPS drift fallback (`GPS: SIM` vs `GPS: FIX`)
- Live OLED telemetry rendering (Latitude, Longitude, Battery %)

Deliverable
Real-Time Node Tracking

--------------------------------------------------

PHASE 11 — Rescue Messaging

TEXT MESSAGE: Node → Node, Central → Node, SOS.

Deliverable
Field Communication System

--------------------------------------------------

PHASE 12 — Rover

Autonomous / Manual Search Rover.

Deliverable
Autonomous Search Rover

--------------------------------------------------

PHASE 13 — Raspberry Pi Command Center

Gateway ESP32 + Raspberry Pi + Database.

Deliverable
Mission Command Center

--------------------------------------------------

PHASE 14 — Rescue Dashboard

Web Dashboard with Live Map & Node Health.

Deliverable
Web Dashboard

--------------------------------------------------

PHASE 15 — Final Optimization

Deliverable
Presentation Ready

--------------------------------------------------

PHASE 16 — Documentation

Deliverable
Final Report & Documentation