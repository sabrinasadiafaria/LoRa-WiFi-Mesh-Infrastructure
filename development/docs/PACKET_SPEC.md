# PACKET_SPEC — LoRa wire format for `development/` firmware

**Status:** v1 DRAFT — freeze after Phase 0, before Phase 1 code is written.
**Scope:** every LoRa packet sent by any `development/` node (A, B, C, Gateway, Rover).
The legacy `phase N/` sketches use their own ad-hoc formats and are **not** covered here.

---

## 1. Design goals

- Human-readable ASCII (easy to debug on a serial monitor and in the Pi dashboard log).
- One fixed field layout for every packet type — parsed once, in one place (`packet.h`).
- Integrity: LoRa hardware CRC **on** + a private sync word, plus an app-level checksum.
- Loop-safe: a **seen-ID cache** so duplicates and already-forwarded packets are dropped.
- Versioned: a leading version field so the protocol can change without silent breakage.
- Short: keep every packet well under 120 bytes (SX1278 handles 255, but airtime matters).

## 2. Frame format

```
v<VER>|<TYPE>|<SRC>|<DEST>|<MSGID>|<TTL>|<PAYLOAD>|<CHK>
```

Fields are separated by `|` (pipe). `|` and `\` are **not allowed** inside any field; the sender
replaces them with `/` before transmit. Fields:

| Field | Type | Notes |
|---|---|---|
| `VER` | int | Protocol version. **v1** for this spec. Receiver drops mismatched major versions. |
| `TYPE` | 3–5 char | See §3. |
| `SRC` | node id | `A` `B` `C` `GW` `RV` (short form; no `NODE_` prefix). |
| `DEST` | node id or `*` | `*` = broadcast to all. |
| `MSGID` | uint16 | Per-source monotonically increasing. `SRC`+`MSGID` = globally unique packet id. Wraps at 65535 → 1 (never 0). |
| `TTL` | uint8 | Remaining hops. Sender sets it (default 4). Each forwarder decrements. 0 = do not forward. |
| `PAYLOAD` | type-specific | See §3. May be empty. |
| `CHK` | 2 hex chars | XOR of all bytes of the frame **before** `|<CHK>`, lowercase hex. Receiver recomputes and drops on mismatch. |

Example:
```
v1|SOS|A|*|41|4|23.797810,90.449720,MAYDAY INJURED RESCUER|7c
```

## 3. Packet types

| TYPE | Introduced | DEST | PAYLOAD | Forwarded? | Purpose |
|---|---|---|---|---|---|
| `HB`   | Phase 1 | `*` | `<uptime_s>,<free_heap>,<fw_ver>` | no (TTL 0) | Heartbeat / neighbour keepalive. Every N s (Phase 0 decides N). |
| `RT`   | Phase 2 | `*` | `<dest>,<hops>;<dest>,<hops>;…` | no (TTL 0) | Distance-vector route advertisement. Split-horizon: a route is omitted from the advert sent toward its own next-hop. |
| `DATA` | Phase 2 | node | `<application bytes>` | yes | Generic end-to-end delivered payload (used for relayed TEXT, etc.). |
| `GPS`  | Phase 3 | `*` | `<lat>,<lon>,<sats>,<fix>,<batt_pct>,<age_s>` | no | Position telemetry. `fix` = `1`/`0`. `age_s` = seconds since last real fix (`0` if live). |
| `TEXT` | Phase 3 | node or `*` | `<free text>` | yes | Rescuer message. Directed or broadcast. |
| `SOS`  | Phase 3 | `*` | `<lat>,<lon>,<message>` | yes (TTL 4) | Emergency. Sent 3× with jittered spacing (non-blocking). Coords are the sender's current fix, or last-known with `age_s` appended as `,STALE:<age>`. |
| `SOSACK` | Phase 3 | node | `<acking_node>,<original_msgid>` | yes | Optional: confirms an SOS was seen by the command center / another node. |
| `RPT`  | Phase 4 | `*` | `<code>,<lat>,<lon>,<team>` | yes | Quick rescue report. `code` ∈ `VICTIM_FOUND` `MEDICAL` `BLOCKED` `DANGER`. |
| `STAT` | Phase 4 | `*` | `<team>,<state>` | no | Team status. `state` ∈ `AVAILABLE` `SEARCHING` `VICTIM_FOUND` `NEED_ASSIST` `EMERGENCY`. |
| `MOVE` | Phase 6 | `RV` | `<cmd>` (`FWD` `BACK` `LEFT` `RIGHT` `STOP` `AUTO` `RELAY`) | yes | Rover drive command from dashboard/portal. |
| `ROVER`| Phase 6 | `*` | `<mode>,<obstacle_cm>,<batt_pct>,<lat>,<lon>` | no | Rover telemetry. |

New types are added by later phases **without** changing existing ones. If a field layout must
change, bump `VER` to `v2` and update this table.

## 4. Forwarding rules (mesh_core, Phase 2)

1. Receive frame → check `CHK` → check `VER` → parse.
2. Compute packet id = `SRC:MSGID`. If in the **seen-ID cache** (ring buffer, ~32 entries) → drop.
   Else add it.
3. Update neighbour table (sender is a 1-hop neighbour; stamp RSSI + `millis()`).
4. If `TYPE` is a routing/telemetry type (`HB` `RT` `GPS` `STAT` `ROVER`) → consume, do not forward.
5. If `DEST` is me or `*` → deliver to the app layer (and still forward if `*` and TTL > 0).
6. If `DEST` is not me and `TTL > 0` and I have a valid route to `DEST` → decrement TTL, re-emit
   via the send scheduler (one TX per tick + jitter). Otherwise drop.

## 5. LoRa PHY settings (radio_layer, Phase 1)

| Setting | Value | Note |
|---|---|---|
| Frequency | `433E6` | matches existing hardware; single region |
| Spreading factor | **TBD in Phase 0** (SF7–SF9) | |
| Signal bandwidth | `125E3` | |
| Coding rate | `5` (4/5) | |
| TX power | **TBD in Phase 0** (e.g. 17 dBm) | |
| Sync word | `0x2A` | private — isolates this mesh from other SX127x traffic |
| CRC | **enabled** (`LoRa.enableCrc()`) | |
| Preamble | default (8) | |

## 6. Airtime / duty-cycle sanity

At SF8/BW125, a ~90-byte packet ≈ 150 ms airtime. With 5 nodes each sending `HB` every 12 s plus
occasional `RT`/`GPS`, aggregate airtime is well under 1% — fine for a lab demo. SOS bursts (3×)
and rover telemetry are the peak load; the send scheduler serialises them per node.

## 7. Change log

| Version | Date | Change |
|---|---|---|
| v1 draft | 2026-09-03 | Initial spec. Freeze pending Phase 0. |
