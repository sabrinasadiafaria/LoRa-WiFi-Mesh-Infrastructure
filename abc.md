Project Title

Adaptive Self-Healing Hybrid LoRa Mesh Network for Post-Disaster Search and Rescue Communication System

Course: CSE 4326 – Microprocessors and Microcontrollers Laboratory

Institution: United International University (UIU)

1. Introduction

Natural disasters such as earthquakes, floods, landslides, industrial accidents, and large fires often destroy traditional communication infrastructures including cellular towers and internet services. During these emergencies, rescue teams struggle to maintain communication with each other, making coordination difficult and reducing the efficiency of search and rescue operations.

This project proposes an Adaptive Self-Healing Hybrid LoRa Mesh Network that enables long-range, infrastructure-independent communication between rescue personnel and a central command station. Every rescue member carries a portable ESP32-LoRa node capable of communicating directly with nearby nodes or forwarding messages through intermediate nodes when direct communication is unavailable.

Unlike traditional point-to-point LoRa communication, the proposed system creates a dynamic mesh network capable of automatically discovering neighboring nodes, selecting optimal communication paths, rerouting around failed nodes, and maintaining communication throughout the rescue operation.

A Raspberry Pi-based Mission Command Center acts as the central monitoring station, collecting data from the mesh network, displaying rescue team locations, monitoring network health, and providing a web-based dashboard for mission management.

2. Problem Statement

During large-scale disasters:

Cellular communication becomes unavailable.
Rescue members become isolated.
Communication range is limited.
Team coordination becomes difficult.
Rescue commanders cannot monitor team locations.
Network failure occurs when relay nodes fail.

Existing communication systems require expensive infrastructure or fixed repeaters that cannot adapt to changing rescue environments.

The proposed system addresses these challenges by creating an intelligent, portable, and self-organizing communication network.

3. Project Objectives

The primary objective is to design and develop a reliable search and rescue communication network capable of operating without existing communication infrastructure.

Specific objectives include:

Develop a portable ESP32-LoRa communication node.
Create an adaptive multi-hop mesh network.
Implement automatic shortest-path routing.
Detect failed nodes automatically.
Reroute communication without user intervention.
Enable direct messaging between rescue members.
Provide GPS-based rescue team tracking.
Develop a Raspberry Pi Mission Command Center.
Build a real-time web dashboard.
Design an autonomous search rover capable of transmitting environmental information.
4. Proposed System Overview

The proposed system consists of four major components.

4.1 Mission Command Center

Hardware:

Raspberry Pi 4
Gateway ESP32
LoRa SX1278
Wi-Fi
Local Database

Responsibilities:

Monitor entire network
Receive all rescue data
Display dashboard
Store mission logs
Display node status
Route monitoring
GPS visualization
4.2 Rescue Communication Nodes

Each rescue member carries one portable node.

Hardware:

ESP32
SX1278 LoRa
GPS Module
OLED Display
Battery Pack

Functions:

Send messages
Receive messages
Forward packets
Share GPS location
Broadcast heartbeat
Participate in routing

Every node has equal capability.

No node is permanently assigned as a relay.

4.3 Search Rover

Hardware

ESP32
GPS
SX1278
PIR Sensor
MQ-2 Gas Sensor
L298N
DC Motors

Functions

Autonomous navigation
Manual control
Environmental monitoring
Human presence detection
Gas detection
Route reporting
Return-to-base
4.4 Gateway Node

Gateway hardware

ESP32
SX1278

Functions

Connect mesh network with Raspberry Pi
Participate as a normal mesh node
Relay packets
Receive commands

Unlike traditional gateways, it is not the network controller.

5. System Architecture
                         Raspberry Pi
                   Mission Command Center
                              │
                      Gateway ESP32
                              │
               ───────────────┼──────────────
              /               │               \
         Rescue A         Rescue B          Rover
            │              /      \             │
            │             /        \            │
       Rescue C      Rescue D    Rescue E   Rescue F
             \            │          /
              ────────────┴─────────

Every node communicates directly whenever possible.

Otherwise packets travel through intermediate nodes.

6. Communication Architecture

The communication network supports

Node ↔ Node

Node ↔ Rover

Node ↔ Gateway

Node ↔ Raspberry Pi

Rover ↔ Central

Broadcast Messages

SOS Messages

7. Adaptive Mesh Routing

Every node periodically broadcasts a heartbeat packet containing:

Node ID
GPS Position
Battery Level
RSSI
Hop Count
Timestamp

Every node builds a routing table.

Example

Destination	Next Hop	Hops
Gateway	Direct	1
Rescue C	Rescue B	2
Rover	Rescue D	3

Communication always uses the route with:

Lowest hop count
Highest RSSI
Healthy node status
8. Self-Healing Mechanism

If a node disappears,

Before

A → B → C

Node B fails

After

A → D → C

The network automatically updates routing tables without human intervention.

9. GPS Tracking

Each node periodically sends

Node ID

Latitude

Longitude

Speed

Time

The Raspberry Pi displays

Live node positions
Movement history
Route traveled
Current rescue coverage
10. Messaging System

Supported messages

Individual Message

A → B

Central Command

Central → Rescue Team

Broadcast

Central → All Nodes

SOS

Emergency Medical Assistance

Message format

TYPE

FROM

TO

MESSAGE

PACKET ID

TIME

Maximum message length

64 Bytes

11. Heartbeat System

Every five seconds each node transmits

ONLINE

GPS

Battery

RSSI

If heartbeat is lost

Node Status

OFFLINE

Dashboard immediately updates.

12. Search Rover

Capabilities

Manual Movement

GPS Navigation

Autonomous Waypoint

Return Home

Gas Detection

Human Detection

Telemetry Reporting

13. Web Dashboard

Dashboard modules

Network Status

Node Health

GPS Tracking

Messaging

Alerts

Mission Logs

System Statistics

14. Major Features
Feature 1

Portable Rescue Communication Node

Feature 2

Adaptive Self-Healing Mesh Routing

Feature 3

GPS Based Team Tracking

Feature 4

Search Rover

Feature 5

Mission Command Dashboard

Feature 6

Real-Time Rescue Messaging

Feature 7

Network Health Monitoring

15. Hardware Components

Mission Command

Raspberry Pi 4
ESP32
SX1278

Rescue Node

ESP32
SX1278
GPS
OLED

Rover

ESP32
SX1278
GPS
MQ-2
PIR
L298N
Motors
16. Development Phases

Phase 1

Hardware Verification

Phase 2

Basic LoRa Communication

Phase 3

Two-Way Communication

Phase 4

Reliable Messaging (ACK)

Phase 5

Heartbeat System

Phase 6

Neighbor Discovery

Phase 7

Routing Table

Phase 8

Packet Forwarding

Phase 9

Adaptive Shortest Path Routing

Phase 10

Self-Healing Mesh

Phase 11

GPS Tracking

Phase 12

Rescue Messaging

Phase 13

Autonomous Rover

Phase 14

Mission Dashboard

Phase 15

System Integration

Phase 16

Testing & Demonstration

17. Expected Outcomes

The proposed system will provide:

Infrastructure-independent communication
Long-range LoRa networking
Automatic route optimization
Dynamic self-healing communication
GPS-based rescue tracking
Environmental monitoring
Autonomous rover support
Real-time mission dashboard
Reliable communication among rescue teams
18. Future Scope

The system can be extended by integrating:

AI-assisted victim detection using a camera
Thermal imaging sensors
Drone-based aerial relay nodes
Voice communication over LoRa (compressed audio)
AES-128 encrypted communication
Cloud synchronization when Internet becomes available
Android application for rescue personnel
Solar-powered portable nodes
Indoor localization for GPS-denied environments