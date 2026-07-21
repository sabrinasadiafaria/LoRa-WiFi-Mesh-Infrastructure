# Progress Tracker

Use this document to track your progress as you test each phase of the project.

---

## 🟢 Phase 6: Automatic Neighbor Discovery (Completed ✅)

- [x] Node A dynamically discovers Node B and prints `>>> NEW NEIGHBOR DISCOVERED: NODE_B`.
- [x] Node B dynamically discovers Node A and prints `>>> NEW NEIGHBOR DISCOVERED: NODE_A`.
- [x] Neighbor Table tracks active count, last seen timestamps, and RSSI.
- [x] Disconnect & Reconnect handling verified.

---

## 📈 Phase 7: Dynamic Routing Table Tracker

Check these off as you test Phase 7:

- [ ] Node A broadcasts route vector `RT:NODE_A:NODE_A,0;...`.
- [ ] Node B broadcasts route vector `RT:NODE_B:NODE_B,0;...`.
- [ ] Both nodes build dynamic routing tables and print them cleanly to Serial Monitor:
  ```text
  ========== ROUTING TABLE (NODE_A) ==========
  DEST        NEXT_HOP    HOPS   RSSI    STATUS
  NODE_B      NODE_B      1      -32dBm  ACTIVE
  ```
- [ ] OLED renders current active route count, destination, next hop, and distance in hops.
- [ ] Test disconnect (power off Node B): Route entry expires after 15s (`>>> ALERT: Route Expired for Dest: NODE_B`).
