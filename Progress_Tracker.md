# Progress Tracker

Use this document to track your progress as you test each phase of the project.

---

## 🟢 Phase 10: Real-Time GPS Tracking & Telemetry (Completed ✅)

- [x] Hardware Serial NMEA GPS parsing configured for Node A (`Serial2` RX=16, TX=17).
- [x] Telemetry broadcasting format: `GPS:SENDER_ID:LAT:LON:BAT:UPTIME`.
- [x] Live OLED rendering of Latitude, Longitude, Satellite Count, and Battery %.
- [x] Bench-test indoor fallback mode (`GPS: SIM/INDOOR`).

---

## 📈 Phase 11: Rescue Messaging & SOS Alert System Tracker

Check these off as you test Phase 11:

- [ ] Upload Phase 11 Rescue Messaging sketch to Node A, Node B, and Node C.
- [ ] Observe targeted text messaging across LoRa mesh (`TEXT:NODE_A:NODE_C:1:Survivor Found Sector 4`).
- [ ] **Hardware SOS Trigger Test**: Press the **BOOT button (GPIO 0)** on Node A or Node B.
- [ ] Verify node immediately broadcasts 3x emergency SOS packets (`SOS:NODE_A:23.797810:90.449720:MAYDAY INJURED RESCUER`).
- [ ] Verify ALL nodes in range (Node B and Node C) trigger a full-screen **`🚨 SOS EMERGENCY ALERT 🚨`** on OLED showing victim's Node ID and exact GPS location!
