"""Procedural terrain for the 3D locations.

Every builder returns a dict of material parts:
  rock   - main terrain material
  accent - secondary material (snow, marble, ice...)
  glow   - emissive (lava, crystals, magic)
plus ``craters`` (list of (x, y, z)) where volcano smoke/embers are emitted.
"""
from __future__ import annotations

import math
import random

from .meshes import RX, RY, RZ, T, Mesh, box, cylinder, ellipsoid, lathe, merge, rock, torus, tube
from .meshes import fbm as _fbm


def _smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def _rocky(m: Mesh, amp_fn, scale=0.35, seed=0) -> Mesh:
    def d(x, y, z):
        r = math.hypot(x, z) or 1.0
        a = amp_fn(y, r)
        if a == 0:
            return 0.0, 0.0, 0.0
        n = _fbm(x * scale, y * scale * 1.3, z * scale, 4, seed)
        return x / r * n * a, n * a * 0.25, z / r * n * a
    return m.displace(d)


def mountain_peak(top_r=7.1, seed=1, height=34.0, spread=26.0) -> Mesh:
    prof = [(0, -0.75), (top_r, -0.75), (top_r + 0.35, -1.3), (top_r + 1.2, -2.6), (top_r + 2.8, -5.0),
            (top_r + 5.5, -9.0), (top_r + 9.5, -15.0), (top_r + 15.0, -23.0), (top_r + spread, -height)]
    m = lathe(prof, 72)
    return _rocky(m, lambda y, r: _smooth(1.0, 4.0, -y) * (0.9 - y * 0.1), 0.3, seed)


def volcano(radius, height, crater, seed) -> tuple[Mesh, Mesh]:
    prof = [(radius, 0), (radius * 0.62, height * 0.42), (crater * 1.5, height * 0.9), (crater * 1.12, height),
            (crater * 0.95, height * 0.97), (crater * 0.7, height * 0.88), (0, height * 0.86)]
    m = lathe(prof, 40)
    m = _rocky(m, lambda y, r: (1.0 - y / height * 0.6) * radius * 0.08, 0.12, seed)
    lava = cylinder(crater * 0.72, crater * 0.72, 0.4, 24).transformed(T(0, height * 0.86, 0))
    return m, lava


def floating_island(top_r=7.2, seed=3) -> Mesh:
    prof = [(0, -0.75), (top_r, -0.75), (top_r + 0.5, -1.4), (top_r, -2.8), (top_r * 0.8, -5.0),
            (top_r * 0.55, -8.5), (top_r * 0.32, -12.5), (top_r * 0.12, -16.0), (0, -18.0)]
    m = lathe(prof, 64)
    return _rocky(m, lambda y, r: _smooth(1.0, 3.0, -y) * 1.6, 0.35, seed)


def crystal(h, w, seed) -> Mesh:
    rng = random.Random(seed)
    m = lathe([(0, 0), (w, h * 0.25), (w * 0.85, h * 0.7), (0, h)], 6)
    return m.transformed(RY(rng.uniform(0, 60)))


def snowy_peak(radius, height, seed) -> Mesh:
    prof = [(radius, 0), (radius * 0.55, height * 0.4), (radius * 0.2, height * 0.8), (0, height)]
    m = lathe(prof, 36)
    return _rocky(m, lambda y, r: radius * 0.12 * (1 - y / height * 0.5), 0.1, seed)


def column(height, radius=0.32) -> Mesh:
    base = box(radius * 2.8, 0.35, radius * 2.8, y0=0)
    shaft = lathe([(radius * 1.1, 0.35), (radius, 0.6), (radius * 0.92, height - 0.5), (radius * 1.05, height - 0.35)],
                  20)
    cap = box(radius * 3.0, 0.35, radius * 3.0, y0=height - 0.35)
    return merge(base, shaft, cap)


# ------------------------------------------------------------- locations
def build(key: str) -> dict:
    rng = random.Random(42)
    parts = {"rock": Mesh(), "accent": Mesh(), "glow": Mesh(), "craters": [], "orbit": Mesh(), "lake": Mesh()}
    if key == "volcano":
        parts["rock"].add(mountain_peak(seed=5))
        for i in range(7):
            a = math.tau * i / 7 + rng.uniform(-0.2, 0.2)
            dist = rng.uniform(85, 140)
            h = rng.uniform(30, 52)
            r = h * rng.uniform(0.75, 1.0)
            c = r * 0.16
            cone, lava = volcano(r, h, c, i + 10)
            base_y = -36.0
            m = T(math.cos(a) * dist, base_y, math.sin(a) * dist)
            parts["rock"].add(cone, m)
            parts["glow"].add(lava, m)
            parts["craters"].append((math.cos(a) * dist, base_y + h * 0.9, math.sin(a) * dist))
        # lake of fire far below
        parts["lake"].add(cylinder(500, 500, 0.5, 48).transformed(T(0, -36.5, 0)))
        # lava cracks running down the peak
        for i in range(6):
            a = math.tau * i / 6 + 0.3
            pts = []
            for k in range(9):
                d = 7.6 + k * 1.9
                y = -1.5 - k * 2.6
                jitter = rng.uniform(-0.15, 0.15)
                pts.append((math.cos(a + jitter) * d, y, math.sin(a + jitter) * d))
            parts["glow"].add(tube(pts, [0.12 + k * 0.03 for k in range(9)], 6))
    elif key == "void":
        parts["rock"].add(floating_island(seed=8))
        for i in range(14):
            a = rng.uniform(0, math.tau)
            d = rng.uniform(13, 34)
            y = rng.uniform(-14, 6)
            parts["orbit"].add(rock(rng.uniform(0.5, 2.4), i, 0.35, 12, 8, 0.8),
                               T(math.cos(a) * d, y, math.sin(a) * d) @ RY(rng.uniform(0, 360)))
        for i in range(12):
            a = math.tau * i / 12 + rng.uniform(-0.1, 0.1)
            d = rng.uniform(7.2, 8.0)
            h = rng.uniform(1.0, 2.6)
            parts["glow"].add(crystal(h, h * 0.18, i),
                              T(math.cos(a) * d, -1.0, math.sin(a) * d) @ RZ(rng.uniform(-25, 25)) @ RX(rng.uniform(-20, 20)))
        for i in range(10):
            a = rng.uniform(0, math.tau)
            d = rng.uniform(16, 40)
            parts["glow"].add(crystal(rng.uniform(1.5, 3.5), 0.4, 100 + i),
                              T(math.cos(a) * d, rng.uniform(-8, 8), math.sin(a) * d) @ RX(rng.uniform(0, 180)))
    elif key == "frozen":
        parts["accent"].add(mountain_peak(seed=11, height=30, spread=22))
        for i in range(10):
            a = math.tau * i / 10 + rng.uniform(-0.2, 0.2)
            dist = rng.uniform(60, 140)
            h = rng.uniform(35, 70)
            parts["accent"].add(snowy_peak(h * 0.6, h, i), T(math.cos(a) * dist, -40, math.sin(a) * dist))
        for i in range(10):
            a = math.tau * i / 10 + rng.uniform(-0.15, 0.15)
            d = rng.uniform(7.3, 8.2)
            h = rng.uniform(0.8, 2.2)
            parts["glow"].add(crystal(h, h * 0.2, 50 + i),
                              T(math.cos(a) * d, -1.2, math.sin(a) * d) @ RZ(rng.uniform(-30, 30)))
        for i in range(6):
            a = rng.uniform(0, math.tau)
            d = rng.uniform(8.5, 11)
            parts["rock"].add(rock(rng.uniform(0.6, 1.3), 70 + i, 0.3), T(math.cos(a) * d, -1.6, math.sin(a) * d))
    elif key == "sky":
        steps = lathe([(0, -0.75), (7.3, -0.75), (7.3, -1.2), (8.3, -1.2), (8.3, -1.65), (9.3, -1.65),
                       (9.3, -2.3), (8.6, -3.0), (0, -3.0)], 64, sharp=(1, 2, 3, 4, 5, 6, 7))
        parts["accent"].add(steps)
        underside = lathe([(0, -2.9), (8.4, -2.9), (7.5, -5.0), (5.0, -8.5), (2.0, -12.0), (0, -13.5)], 48)
        parts["rock"].add(_rocky(underside, lambda y, r: 1.0, 0.35, 21))
        for i in range(12):  # a ring of colossal columns standing on floating stones
            a = math.tau * (i + 0.5) / 12
            cx, cz = math.cos(a) * 21, math.sin(a) * 21
            h = 16.0 if i % 4 else rng.uniform(6.0, 10.0)  # some ruined
            parts["rock"].add(_rocky(lathe([(0, 0.2), (2.2, 0.2), (1.8, -1.5), (0.6, -3.5), (0, -4.2)], 16),
                                     lambda y, r: 0.4, 0.6, 30 + i), T(cx, -6.0, cz))
            parts["accent"].add(column(h, 0.75), T(cx, -5.8, cz))
            if i % 4:
                parts["glow"].add(ellipsoid(0.8, 0.45, 0.8, 14, 8), T(cx, -5.8 + h + 0.35, cz))
        for i in range(70):
            a = rng.uniform(0, math.tau)
            d = rng.uniform(22, 170)
            s = rng.uniform(5, 16)
            parts["orbit"].add(ellipsoid(s, s * 0.35, s * 0.8, 14, 8),
                               T(math.cos(a) * d, rng.uniform(-24, -16), math.sin(a) * d) @ RY(rng.uniform(0, 180)))
    return parts
