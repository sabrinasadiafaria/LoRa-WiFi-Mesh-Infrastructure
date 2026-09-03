"""
A stand-in for SX1278 so the dashboard and DB can be demoed on any laptop
with no LoRa hardware. Emits synthetic HB / GPS / SOS / RPT / STAT frames
from three fake nodes around Dhaka, and swallows transmits.
"""

import time
import random
import mesh


class FakeRadio:
    NODES = ["A", "B", "C"]
    BASE = (23.7979, 90.4497)

    def __init__(self):
        self._q = []
        self._next = time.time() + 1
        self._msgid = {n: 0 for n in self.NODES}
        self._pos = {n: (self.BASE[0] + random.uniform(-0.002, 0.002),
                         self.BASE[1] + random.uniform(-0.002, 0.002))
                     for n in self.NODES}

    def begin(self):
        print("[fake radio] no hardware - emitting synthetic traffic")

    def receive(self):
        pass

    def close(self):
        pass

    def send(self, data: bytes):
        # pretend it went out
        return True

    def _mid(self, n):
        self._msgid[n] += 1
        return self._msgid[n]

    def poll(self):
        now = time.time()
        if now < self._next:
            time.sleep(0.02)
            return None
        self._next = now + random.uniform(1.5, 4.0)

        n = random.choice(self.NODES)
        # drift the fake position a little
        la, lo = self._pos[n]
        la += random.uniform(-0.0002, 0.0002)
        lo += random.uniform(-0.0002, 0.0002)
        self._pos[n] = (la, lo)

        roll = random.random()
        if roll < 0.45:
            frame = mesh.build("HB", n, "*", self._mid(n), 0,
                               f"{int(now)},{200000 + random.randint(-2000, 2000)},4")
        elif roll < 0.85:
            frame = mesh.build("GPS", n, "*", self._mid(n), 0,
                               f"{la:.6f},{lo:.6f},{random.randint(4,9)},2,0")
        elif roll < 0.92:
            frame = mesh.build("STAT", n, "*", self._mid(n), 0,
                               f"T1,{random.choice(['AVAILABLE','SEARCHING','NEED_ASSIST'])}")
        elif roll < 0.97:
            frame = mesh.build("RPT", n, "*", self._mid(n), 4,
                               f"{random.choice(['VICTIM_FOUND','MEDICAL','BLOCKED','DANGER'])},"
                               f"{la:.6f},{lo:.6f},T1")
        else:
            frame = mesh.build("SOS", n, "*", self._mid(n), 4,
                               f"{la:.6f},{lo:.6f},MAYDAY test injection")

        rssi = random.randint(-95, -55)
        snr = round(random.uniform(6, 12), 1)
        return frame, rssi, snr
