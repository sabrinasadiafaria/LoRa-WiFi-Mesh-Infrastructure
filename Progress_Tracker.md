# Progress Tracker

Use this document to track your progress as you test each phase of the project.

---

## 🟢 Phase 7: Dynamic Routing Table (Completed ✅)

- [x] Node A broadcasts route vector `RT:NODE_A:NODE_A,0;...`.
- [x] Node B broadcasts route vector `RT:NODE_B:NODE_B,0;...`.
- [x] Clean loop-free routing table rendered on Serial Monitor:
  ```text
  ========== ROUTING TABLE (NODE_A) ==========
  DEST        NEXT_HOP    HOPS   RSSI    STATUS
  NODE_B      NODE_B      1      -38dBm  ACTIVE
  ```
- [x] Verified zero count-to-infinity / loop errors.

---

## 📈 Phase 8: Multi-Hop Packet Forwarding Tracker

Check these off as you test Phase 8:

- [ ] Node A transmits packet formatted as `DATA:NODE_A:NODE_C:1:ID:Payload`.
- [ ] Node B receives packet meant for `NODE_C`.
- [ ] Node B checks its routing table and automatically forwards the packet: `>>> FORWARDED packet: NODE_A -> NODE_C via NODE_C (Hop 2)`.
- [ ] Final destination node receives packet and logs `>>> RECEIVED FINAL DATA`.
- [ ] Hop limit (TTL) check prevents infinite forwarding loops.
