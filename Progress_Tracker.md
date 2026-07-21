# Progress Tracker

Use this document to track your progress as you test each phase of the project.

---

## 🟢 Phase 5: Heartbeat System (Completed ✅)

- [x] Node A broadcasts heartbeat `HB:NODE_A:uptime` every 5 seconds.
- [x] Node B broadcasts heartbeat `HB:NODE_B:uptime` every 5 seconds.
- [x] Node A receives Node B's heartbeat and displays `NODE_B: ONLINE` and `Last Seen: X sec ago` on OLED.
- [x] Node B receives Node A's heartbeat and displays `NODE_A: ONLINE` and `Last Seen: X sec ago` on OLED.
- [x] Verified zero collision and stable heartbeat exchanges.

---

## 📈 Phase 6: Automatic Neighbor Discovery Tracker

Check these off as you test Phase 6:

- [ ] Node A dynamically discovers Node B and prints `>>> NEW NEIGHBOR DISCOVERED: NODE_B`.
- [ ] Node B dynamically discovers Node A and prints `>>> NEW NEIGHBOR DISCOVERED: NODE_A`.
- [ ] Neighbor Table tracks active count, last seen timestamps, and RSSI for each discovered node.
- [ ] Test disconnect (power off Node B): Node A logs `>>> ALERT: Neighbor Lost (Timeout): NODE_B` after 12s.
- [ ] Test reconnect: Node A logs `>>> RECONNECTED Neighbor: NODE_B` when Node B powers back on.
