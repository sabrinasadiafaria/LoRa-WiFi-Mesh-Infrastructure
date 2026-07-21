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

PHASE 8 — Packet Forwarding 🔄

Goal
Enable automatic packet forwarding across intermediate nodes to achieve multi-hop mesh communication.

Features
- Mesh Packet Format: `DATA:SRC:DEST:HOPS:MSG_ID:PAYLOAD`
- Destination check: If packet is for self -> process as final receiver.
- Forwarding engine: If packet is for another node -> lookup next hop in Routing Table and forward (`>>> FORWARDED packet: SRC -> DEST`).
- Max Hop TTL limit: Drop packets exceeding max hops (e.g. 5) to prevent infinite loops.
- Live OLED rendering of forwarded packet counters and destination status.

Deliverable
First Multi-Hop Network

--------------------------------------------------

PHASE 9 — Self-Healing Mesh

Kill Node B.
Network automatically updates routing tables.

Deliverable
Self-Healing Routing

--------------------------------------------------

PHASE 10 — GPS Integration

Every node has GPS.
Each heartbeat includes Node ID, Latitude, Longitude, Battery.

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