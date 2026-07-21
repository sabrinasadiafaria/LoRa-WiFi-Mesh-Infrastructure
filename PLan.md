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
PHASE 2 — Basic LoRa Communication ✅

(Currently completed)

Features
Node A sends
Node B receives
RSSI shown
OLED updated
Deliverable
Reliable One-Way Communication
PHASE 3 — Two-Way Communication
Goal

Every node can send and receive.

Node A ←→ Node B
Features
Manual message sending
Reply messages
OLED updates
Deliverables
Bi-directional Communication
PHASE 4 — Reliable Communication
Goal

Guarantee delivery.

Features

ACK packets

Node A

↓

Hello #15

↓

Node B

↓

ACK #15

↓

Node A

Retry

Packet Counter

Duplicate Detection

Timeout

Deliverable
Reliable Messaging Layer
PHASE 5 — Heartbeat System
Goal

Know which nodes are alive.

Every node broadcasts

ONLINE

every 5 seconds.

Features

Heartbeat

Node Timeout

Last Seen

Connection Status

OLED

NODE B

ONLINE

Last Seen

2 sec
Deliverable
Network Health Monitoring
PHASE 6 — Node Discovery
Goal

Automatically discover nearby nodes.

Each node maintains

Neighbor Table

Example

Node

RSSI

Last Seen

NODE B

-64

1 sec

NODE C

-82

4 sec
Deliverable
Automatic Neighbor Discovery
PHASE 7 — Routing Table
Goal

Learn routes.

Example

Destination

Next Hop

Hops

Gateway

Gateway

1

Node C

Node B

2
Deliverable
Dynamic Routing Table
PHASE 8 — Packet Forwarding

Now introduce

Node C

Example

Node A

↓

Node B

↓

Node C

Node B forwards automatically.

Deliverable
First Multi-Hop Network
PHASE 9 — Self-Healing Mesh

Kill Node B.

Network changes

Before

A

↓

B

↓

C

After

A

↓

D

↓

C

No manual configuration.

Deliverable
Self-Healing Routing
PHASE 10 — GPS Integration

Every node has GPS.

Each heartbeat includes

Node ID

Latitude

Longitude

Battery
Features

GPS Parsing

Location Broadcast

Map Coordinates

Deliverable
Real-Time Node Tracking
PHASE 11 — Rescue Messaging

Now add

TEXT MESSAGE
Features

Node → Node

Node → Central

Central → Node

Broadcast

Group Message

SOS

Limit message size to 64 bytes for reliable LoRa transmission.

Packet example

MSG

FROM:2

TO:5

TEXT:Need medical support
Deliverable
Field Communication System
PHASE 12 — Rover

Now add

GPS
PIR
MQ-2
Motors
L298N

Features

Autonomous Navigation

Waypoint

Return Home

Obstacle Detection (future)

Sensor Reporting

Deliverable
Autonomous Search Rover
PHASE 13 — Raspberry Pi Command Center

Features

Receive LoRa

Database

Dashboard

Node Status

GPS Map

Messages

Mission Logs

Deliverable
Mission Command Center
PHASE 14 — Rescue Dashboard

Dashboard Pages

Home

Network

Nodes

Messages

GPS

Alerts

Logs

Settings

Live Information

Node Status

RSSI

Battery

GPS

SOS

Heartbeat

Last Seen
Deliverable
Web Dashboard
PHASE 15 — Final Optimization

Improve

Memory

CPU

Packet Size

Retries

Routing

Power Consumption

Deliverable
Presentation Ready
PHASE 16 — Documentation

Create

README.md

Project Proposal

Architecture

Wiring

Component List

Protocol

Routing

GPS

Dashboard

Testing Report

Future Improvements