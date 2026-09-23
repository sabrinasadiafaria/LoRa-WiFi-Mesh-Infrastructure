"""
A stand-in for SX1278 — Phase 10.

Emits synthetic HB / GPS / SOS / RPT / STAT / ROVER frames from
fake nodes around Dhaka, and swallows transmits. Extended from
Phase 9 to also generate rover telemetry with GPS navigation data.

Clearly labeled: ALL DATA FROM THIS MODULE IS SIMULATED.
"""

import time
import random
import mesh

class FakeRadio:
    """SIMULATED radio — no real hardware. All data is synthetic."""

    NODES = ["A", "B", "C"]
    BASE = (23.7979, 90.4497)

    def __init__(self):
        self._q = []
        self._next = time.time() + 1
        self._msgid = {n: 0 for n in self.NODES + ["R"]}
        self._pos = {n: (self.BASE[0] + random.uniform(-0.002, 0.002),
                         self.BASE[1] + random.uniform(-0.002, 0.002))
                     for n in self.NODES}
        # Rover starts near the base
        self._pos["R"] = (self.BASE[0] + 0.001, self.BASE[1] + 0.001)
        self._rover_mode = "MANUAL"
        self._rover_target = None
        self._rover_battery = 85

    def begin(self):
        print("[fake radio] *** SIMULATED — no hardware — synthetic traffic ***")

    def receive(self):
        pass

    def close(self):
        pass

    def send(self, data: bytes):
        # Check for GOTO commands to simulate rover response
        try:
            s = data.decode("ascii", "replace")
            if "GOTO" in s:
                parts = s.split("|")
                if len(parts) >= 7 and "GOTO" in parts[6]:
                    payload = parts[6]
                    if "," in payload.split("GOTO,", 1)[-1] if "GOTO," in payload else "":
                        self._rover_mode = "AUTO_GPS"
        except Exception:
            pass
        return True

    def _mid(self, n):
        self._msgid[n] += 1
        return self._msgid[n]

    def poll(self):
        now = time.time()
        if now < self._next:
            return None
        self._next = now + random.uniform(1.5, 4.0)

        # 80% chance regular node, 20% rover
        if random.random() < 0.2:
            return self._rover_packet(now)

        n = random.choice(self.NODES)
        la, lo = self._pos[n]
        la += random.uniform(-0.0002, 0.0002)
        lo += random.uniform(-0.0002, 0.0002)
        self._pos[n] = (la, lo)

        roll = random.random()
        if roll < 0.40:
            frame = mesh.build("HB", n, "*", self._mid(n), 0,
                               f"{int(now)},{200000 + random.randint(-2000, 2000)},8")
        elif roll < 0.75:
            frame = mesh.build("GPS", n, "*", self._mid(n), 0,
                               f"{la:.6f},{lo:.6f},{random.randint(4,9)},1,0")
        elif roll < 0.85:
            frame = mesh.build("STAT", n, "*", self._mid(n), 0,
                               f"ALPHA,{random.choice(['AVAILABLE','SEARCHING','NEED_ASSIST'])}")
        elif roll < 0.93:
            frame = mesh.build("RPT", n, "*", self._mid(n), 4,
                               f"{random.choice(['VICTIM_FOUND','MEDICAL','BLOCKED','DANGER'])},"
                               f"{la:.6f},{lo:.6f},ALPHA")
        else:
            frame = mesh.build("SOS", n, "*", self._mid(n), 4,
                               f"{la:.6f},{lo:.6f},MAYDAY test injection")

        rssi = random.randint(-95, -55)
        snr = round(random.uniform(6, 12), 1)
        return frame, rssi, snr

    def _rover_packet(self, now):
        """Generate rover telemetry."""
        la, lo = self._pos["R"]
        la += random.uniform(-0.0001, 0.0001)
        lo += random.uniform(-0.0001, 0.0001)
        self._pos["R"] = (la, lo)
        self._rover_battery = max(0, self._rover_battery - random.uniform(0, 0.1))

        obstacle = random.randint(20, 200)
        dist_m = random.randint(5, 500) if self._rover_mode == "AUTO_GPS" else -1
        heading_err = random.randint(-45, 45) if self._rover_mode == "AUTO_GPS" else -999

        roll = random.random()
        if roll < 0.5:
            # ROVER telemetry
            frame = mesh.build("ROVER", "R", "*", self._mid("R"), 4,
                               f"{self._rover_mode},{obstacle},{int(self._rover_battery)}"
                               f",{dist_m},{heading_err}")
        else:
            # GPS from rover
            frame = mesh.build("GPS", "R", "*", self._mid("R"), 0,
                               f"{la:.6f},{lo:.6f},{random.randint(4,8)},1,0")

        rssi = random.randint(-90, -60)
        snr = round(random.uniform(6, 12), 1)
        return frame, rssi, snr
