# Progress Tracker

Use this document to track your progress as you test each phase of the project.

---

## 📈 Phase 3: Two-Way Communication Tracker

Check these off as you test the two-way communication:

- [ ] Node A powers on successfully.
- [ ] Node A OLED initializes and displays "NODE A (Two-Way)".
- [ ] Node A successfully initializes the LoRa module.
- [ ] Node B powers on successfully.
- [ ] Node B OLED initializes and displays "NODE B (Two-Way)".
- [ ] Node B successfully initializes the LoRa module.
- [ ] Node A successfully transmits a packet every 5 seconds.
- [ ] Node B successfully receives the packet from Node A and updates its OLED.
- [ ] Node B successfully transmits a packet every 6 seconds.
- [ ] Node A successfully receives the packet from Node B and updates its OLED.
- [ ] RSSI values are displayed correctly on both OLEDs.

> **Troubleshooting Tip:** If the LoRa module fails to initialize, double check the `MISO`, `MOSI`, and `SCK` jumper wires. These are the most common culprits for initialization failures. If the OLED doesn't turn on, verify the `SDA` and `SCL` pins.
