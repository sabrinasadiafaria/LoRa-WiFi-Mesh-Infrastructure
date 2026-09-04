# Pi code moved

The Raspberry Pi code used to be copied into every phase folder (`phase 5/pi/`,
`phase 6/pi/`, ...). That meant re-vendoring Leaflet and re-downloading the
Dhaka map tiles every time a phase changed a single Python file.

**It now lives in one place: [`development/pi/`](../../pi/).**

That folder is cumulative, like the node sketches — it already contains every
fix from Phase 5 and Phase 6 (Pi-as-mesh-node, dashboard, plus the Phase 6
reconnect-timing and GPIO-cleanup fixes). Point `sar-pi.service` and your
`venv` at `development/pi/`, not here.
