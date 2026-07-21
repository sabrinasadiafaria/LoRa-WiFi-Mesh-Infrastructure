# Progress Tracker

Use this document to track your progress as you test each phase of the project.

---

## 🟢 Phase 3: Two-Way Communication (Completed ✅)

- [x] Node A powers on successfully.
- [x] Node A OLED initializes and displays "NODE A (Two-Way)".
- [x] Node A successfully initializes the LoRa module.
- [x] Node B powers on successfully.
- [x] Node B OLED initializes and displays "NODE B (Two-Way)".
- [x] Node B successfully initializes the LoRa module.
- [x] Node A successfully transmits a packet every 5 seconds.
- [x] Node B successfully receives the packet from Node A and updates its OLED.
- [x] Node B successfully transmits a packet every 6 seconds.
- [x] Node A successfully receives the packet from Node B and updates its OLED.
- [x] RSSI values are displayed correctly on both OLEDs.

---

## 📈 Phase 4: Reliable Communication (ACK & Retries)

Check these off as you test Phase 4:

- [ ] Node A transmits message formatted as `MSG:ID:DATA`.
- [ ] Node B receives message and automatically replies with `ACK:ID`.
- [ ] Node A receives `ACK` and displays "ACK Received!" on OLED and Serial.
- [ ] Test disconnect (power off Node B): Node A should retry up to 3 times before displaying "ACK FAILED!".
- [ ] Duplicate detection: Verify duplicate IDs are not re-processed on OLED.
