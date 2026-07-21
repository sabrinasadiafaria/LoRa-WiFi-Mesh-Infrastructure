# Progress Tracker

Use this document to track your progress as you test each phase of the project.

---

## 🟢 Phase 4: Reliable Communication (ACKs & Retries) (Completed ✅)

- [x] Node A transmits message formatted as `MSG:ID:DATA`.
- [x] Node B receives message and automatically replies with `ACK:ID`.
- [x] Node A receives `ACK` and displays "ACK Received!" on OLED and Serial.
- [x] Test disconnect: ACK timeouts and retries work cleanly.
- [x] Duplicate detection: Verified duplicate IDs are not re-processed.

---

## 📈 Phase 5: Heartbeat System Tracker

Check these off as you test Phase 5:

- [ ] Node A broadcasts heartbeat `HB:NODE_A:uptime` every 5 seconds.
- [ ] Node B broadcasts heartbeat `HB:NODE_B:uptime` every 5 seconds.
- [ ] Node A receives Node B's heartbeat and displays `NODE_B: ONLINE` and `Last Seen: X sec ago` on OLED.
- [ ] Node B receives Node A's heartbeat and displays `NODE_A: ONLINE` and `Last Seen: X sec ago` on OLED.
- [ ] Test disconnect (unplug Node B): After 12 seconds of missing heartbeats, Node A updates OLED to `NODE_B: OFFLINE` and alerts `TIMEOUT!`.
- [ ] Reconnect test: Plug Node B back in, Node A should automatically return to `NODE_B: ONLINE`.
