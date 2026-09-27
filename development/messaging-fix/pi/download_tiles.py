#!/usr/bin/env python3
"""
One-time offline map-tile cache for the dashboard.

Run this ONCE on the Pi while it has internet:

    python3 download_tiles.py

Downloads OpenStreetMap tiles for the Dhaka demo area (zoom 11-16) into
dashboard/tiles/{z}/{x}/{y}.png . After that the dashboard map works with
no internet.

Edit BBOX / ZOOM below for a different area. ~1500 tiles, a few MB, ~5 min
at the 1 req/sec rate below (be polite to the free tile server).
"""

import math
import os
import time
import urllib.request

# (min_lat, min_lon, max_lat, max_lon) - Dhaka metro
BBOX = (23.66, 90.33, 23.92, 90.53)
ZOOM = range(11, 17)
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
OUT = os.path.join(os.path.dirname(__file__), "dashboard", "tiles")
UA = "SAR-Mesh-lab-project/1.0 (one-time cache)"
DELAY = 1.0


def deg2num(lat, lon, z):
    lat_r = math.radians(lat)
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def main():
    total = got = skip = 0
    for z in ZOOM:
        x0, y1 = deg2num(BBOX[0], BBOX[1], z)
        x1, y0 = deg2num(BBOX[2], BBOX[3], z)
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                total += 1
                path = os.path.join(OUT, str(z), str(x))
                fn = os.path.join(path, f"{y}.png")
                if os.path.exists(fn) and os.path.getsize(fn) > 0:
                    skip += 1
                    continue
                os.makedirs(path, exist_ok=True)
                url = TILE_URL.format(z=z, x=x, y=y)
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, timeout=20) as r:
                        data = r.read()
                    with open(fn, "wb") as f:
                        f.write(data)
                    got += 1
                    print(f"  {z}/{x}/{y}  ({got} downloaded, {skip} cached)")
                    time.sleep(DELAY)
                except Exception as e:
                    print(f"  !! {z}/{x}/{y}: {e}")
                    time.sleep(DELAY)
    print(f"\ndone. {got} downloaded, {skip} already cached, {total} total.")


if __name__ == "__main__":
    main()
