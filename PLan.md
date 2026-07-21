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

PHASE 4 — Reliable Communication 🔄

Goal
Guarantee delivery with ACKs & Retries.

Features
- Packet format: MSG:ID:Payload / ACK:ID
- Automatic ACK replies upon packet receipt
- Duplicate packet detection & filtering
- Retry logic: If no ACK received within 1.5s, retry up to 3 times
- Failure detection: If 3 retries fail, report "ACK FAILED!"

Deliverable
Reliable Messaging Layer

--------------------------------------------------

PHASE 5 — Heartbeat System

Goal
Know which nodes are alive.

Every node broadcasts ONLINE every 5 seconds.

Features
Heartbeat
Node Timeout
Last Seen
Connection Status

Deliverable
Network Health Monitoring

--------------------------------------------------

PHASE 6 — Node Discovery

Goal
Automatically discover nearby nodes.

Each node maintains Neighbor Table.

Deliverable
Automatic Neighbor Discovery

--------------------------------------------------

PHASE 7 — Routing Table

Goal
Learn routes.

Deliverable
Dynamic Routing Table

--------------------------------------------------

PHASE 8 — Packet Forwarding

Now introduce Node C.
Node B forwards automatically.

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