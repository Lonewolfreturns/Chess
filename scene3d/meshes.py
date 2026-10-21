"""Procedural mesh toolkit (pure Python, no numpy).

Meshes are indexed triangle lists with per-vertex normals. Primitives:
lathe (surface of revolution), ellipsoid, cylinder, torus, box, extrude,
loft (rounded extrusion), tube (swept circle) plus transforms and merging.
"""
from __future__ import annotations

import math
import random
import struct


# ------------------------------------------------------------------ matrices
class Mat:
    """Affine 3D transform stored as a 3x4 row-major matrix."""

    __slots__ = ("m",)

    def __init__(self, m=None):
        self.m = m or [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0]

    def __matmul__(self, o: "Mat") -> "Mat":
        a, b = self.m, o.m
        r = [0.0] * 12
        for i in range(3):
            for j in range(4):
                r[i * 4 + j] = (a[i * 4] * b[j] + a[i * 4 + 1] * b[4 + j] + a[i * 4 + 2] * b[8 + j]
                                + (a[i * 4 + 3] if j == 3 else 0.0))
        return Mat(r)

    def point(self, x, y, z):
        m = self.m
        return (m[0] * x + m[1] * y + m[2] * z + m[3],
                m[4] * x + m[5] * y + m[6] * z + m[7],
                m[8] * x + m[9] * y + m[10] * z + m[11])

    def normal_matrix(self):
        m = self.m
        a, b, c, d, e, f, g, h, i = m[0], m[1], m[2], m[4], m[5], m[6], m[8], m[9], m[10]
        det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
        if abs(det) < 1e-12:
            det = 1e-12
        # inverse transpose of the 3x3 part
        return [(e * i - f * h) / det, -(d * i - f * g) / det, (d * h - e * g) / det,
                -(b * i - c * h) / det, (a * i - c * g) / det, -(a * h - b * g) / det,
                (b * f - c * e) / det, -(a * f - c * d) / det, (a * e - b * d) / det]


def T(x=0.0, y=0.0, z=0.0) -> Mat:
    return Mat([1, 0, 0, x, 0, 1, 0, y, 0, 0, 1, z])


def S(x=1.0, y=None, z=None) -> Mat:
    y = x if y is None else y
    z = x if z is None else z
    return Mat([x, 0, 0, 0, 0, y, 0, 0, 0, 0, z, 0])


def RX(deg) -> Mat:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return Mat([1, 0, 0, 0, 0, c, -s, 0, 0, s, c, 0])


def RY(deg) -> Mat:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return Mat([c, 0, s, 0, 0, 1, 0, 0, -s, 0, c, 0])


def RZ(deg) -> Mat:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return Mat([c, -s, 0, 0, s, c, 0, 0, 0, 0, 1, 0])


def _norm(x, y, z):
    l = math.sqrt(x * x + y * y + z * z) or 1.0
    return x / l, y / l, z / l


def _cross(a, b):
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _sub(a, b):
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


# --------------------------------------------------------------------- mesh
class Mesh:
    def __init__(self):
        self.pos: list[tuple] = []
        self.nrm: list[tuple] = []
        self.uv: list[tuple] = []
        self.idx: list[int] = []

    def v(self, p, n=(0.0, 1.0, 0.0), uv=(0.0, 0.0)) -> int:
        self.pos.append(p)
        self.nrm.append(n)
        self.uv.append(uv)
        return len(self.pos) - 1

    def tri(self, a, b, c):
        self.idx += (a, b, c)

    def quad(self, a, b, c, d):
        self.idx += (a, b, c, a, c, d)

    def add(self, other: "Mesh", m: Mat | None = None) -> "Mesh":
        base = len(self.pos)
        if m is None:
            self.pos += other.pos
            self.nrm += other.nrm
        else:
            nm = m.normal_matrix()
            for p in other.pos:
                self.pos.append(m.point(*p))
            for n in other.nrm:
                self.nrm.append(_norm(nm[0] * n[0] + nm[1] * n[1] + nm[2] * n[2],
                                      nm[3] * n[0] + nm[4] * n[1] + nm[5] * n[2],
                                      nm[6] * n[0] + nm[7] * n[1] + nm[8] * n[2]))
        self.uv += other.uv
        self.idx += [i + base for i in other.idx]
        return self

    def transformed(self, m: Mat) -> "Mesh":
        return Mesh().add(self, m)

    def flip(self) -> "Mesh":
        for i in range(0, len(self.idx), 3):
            self.idx[i + 1], self.idx[i + 2] = self.idx[i + 2], self.idx[i + 1]
        self.nrm = [(-x, -y, -z) for x, y, z in self.nrm]
        return self

    def smooth_normals(self) -> "Mesh":
        acc = [[0.0, 0.0, 0.0] for _ in self.pos]
        P = self.pos
        for i in range(0, len(self.idx), 3):
            a, b, c = self.idx[i:i + 3]
            n = _cross(_sub(P[b], P[a]), _sub(P[c], P[a]))
            for k in (a, b, c):
                acc[k][0] += n[0]
                acc[k][1] += n[1]
                acc[k][2] += n[2]
        self.nrm = [_norm(*n) for n in acc]
        return self

    def displace(self, fn) -> "Mesh":
        """Move each vertex by fn(x, y, z) -> (dx, dy, dz) then recompute normals."""
        self.pos = [(x + d[0], y + d[1], z + d[2]) for (x, y, z) in self.pos for d in (fn(x, y, z),)]
        return self.smooth_normals()

    def bounds(self):
        if not self.pos:
            return (0, 0, 0), (0, 0, 0)
        xs, ys, zs = zip(*self.pos)
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def pack(self, with_uv: bool = False) -> tuple[bytes, bytes, int]:
        """Interleaved float32 position+normal(+uv) bytes, uint32 index bytes, stride."""
        out = bytearray()
        if with_uv:
            pk = struct.Struct("<8f").pack
            for p, n, t in zip(self.pos, self.nrm, self.uv):
                out += pk(p[0], p[1], p[2], n[0], n[1], n[2], t[0], t[1])
            stride = 32
        else:
            pk = struct.Struct("<6f").pack
            for p, n in zip(self.pos, self.nrm):
                out += pk(p[0], p[1], p[2], n[0], n[1], n[2])
            stride = 24
        idx = struct.pack(f"<{len(self.idx)}I", *self.idx)
        return bytes(out), idx, stride


def merge(*meshes) -> Mesh:
    m = Mesh()
    for x in meshes:
        if isinstance(x, tuple):
            m.add(x[0], x[1])
        elif x is not None:
            m.add(x)
    return m


# --------------------------------------------------------------- primitives
def lathe(profile, seg: int = 32, sharp: tuple = (), arc: tuple | None = None) -> Mesh:
    """Revolve a 2D profile [(radius, y), ...] (bottom to top) around the Y axis.

    Indices listed in ``sharp`` become hard creases. ``arc`` = (start_deg, end_deg)
    makes a partial revolution (angle 0 = +X, 90 = +Z).
    """
    a_start, a_span = (0.0, math.tau) if arc is None else (math.radians(arc[0]),
                                                           math.radians(arc[1] - arc[0]))
    pts = list(profile)
    n = len(pts)
    seg_n = []
    for i in range(n - 1):
        (r0, y0), (r1, y1) = pts[i], pts[i + 1]
        dr, dy = r1 - r0, y1 - y0
        l = math.hypot(dr, dy) or 1.0
        seg_n.append((dy / l, -dr / l))
    m = Mesh()
    rings = []
    for i, (r, y) in enumerate(pts):
        variants = []
        if i in sharp and 0 < i < n - 1:
            variants = [seg_n[i - 1], seg_n[i]]
        else:
            if i == 0:
                nr, ny = seg_n[0]
            elif i == n - 1:
                nr, ny = seg_n[-1]
            else:
                a, b = seg_n[i - 1], seg_n[i]
                nr, ny = a[0] + b[0], a[1] + b[1]
            l = math.hypot(nr, ny) or 1.0
            variants = [(nr / l, ny / l)]
        ring_set = []
        for nr, ny in variants:
            ring = []
            for s in range(seg + 1):
                a = a_start + a_span * s / seg
                c, sn = math.cos(a), math.sin(a)
                ring.append(m.v((r * c, y, r * sn), (nr * c, ny, nr * sn), (s / seg, i / (n - 1))))
            ring_set.append(ring)
        rings.append(ring_set)
    for i in range(n - 1):
        lo = rings[i][-1]
        hi = rings[i + 1][0]
        for s in range(seg):
            m.quad(lo[s], hi[s], hi[s + 1], lo[s + 1])
    return m


def cylinder(r_bottom: float, r_top: float, h: float, seg: int = 24, caps: bool = True) -> Mesh:
    if caps:
        return _cyl(r_bottom, r_top, h, seg)
    return lathe([(r_bottom, 0), (r_top, h)], seg)


def _cyl(rb, rt, h, seg):
    m = Mesh()
    side = lathe([(rb, 0), (rt, h)], seg)
    m.add(side)
    for y, r, ny in ((0.0, rb, -1.0), (h, rt, 1.0)):
        if r <= 0:
            continue
        c = m.v((0, y, 0), (0, ny, 0))
        ring = [m.v((r * math.cos(math.tau * s / seg), y, r * math.sin(math.tau * s / seg)), (0, ny, 0))
                for s in range(seg + 1)]
        for s in range(seg):
            if ny > 0:
                m.tri(c, ring[s + 1], ring[s])
            else:
                m.tri(c, ring[s], ring[s + 1])
    return m


def ellipsoid(rx: float, ry: float, rz: float, seg_u: int = 24, seg_v: int = 14,
              v_min: float = -1.0, v_max: float = 1.0) -> Mesh:
    m = Mesh()
    rows = []
    a0 = math.asin(max(-1.0, min(1.0, v_min)))
    a1 = math.asin(max(-1.0, min(1.0, v_max)))
    for j in range(seg_v + 1):
        lat = a0 + (a1 - a0) * j / seg_v
        cy, sy = math.cos(lat), math.sin(lat)
        row = []
        for i in range(seg_u + 1):
            lon = math.tau * i / seg_u
            x, z = cy * math.cos(lon), cy * math.sin(lon)
            row.append(m.v((rx * x, ry * sy, rz * z), _norm(x / rx, sy / ry, z / rz), (i / seg_u, j / seg_v)))
        rows.append(row)
    for j in range(seg_v):
        for i in range(seg_u):
            m.quad(rows[j][i], rows[j + 1][i], rows[j + 1][i + 1], rows[j][i + 1])
    return m


def sphere(r: float, seg_u: int = 20, seg_v: int = 12) -> Mesh:
    return ellipsoid(r, r, r, seg_u, seg_v)


def torus(R: float, r: float, seg_u: int = 32, seg_v: int = 12) -> Mesh:
    m = Mesh()
    rows = []
    for i in range(seg_u + 1):
        u = math.tau * i / seg_u
        cu, su = math.cos(u), math.sin(u)
        row = []
        for j in range(seg_v + 1):
            v = math.tau * j / seg_v
            cv, sv = math.cos(v), math.sin(v)
            row.append(m.v(((R + r * cv) * cu, r * sv, (R + r * cv) * su), (cv * cu, sv, cv * su)))
        rows.append(row)
    for i in range(seg_u):
        for j in range(seg_v):
            m.quad(rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j])
    return m


def box(w: float, h: float, d: float, y0: float | None = None) -> Mesh:
    """Axis aligned box centred on origin (or with bottom at y0)."""
    m = Mesh()
    x, z = w / 2, d / 2
    lo, hi = (-h / 2, h / 2) if y0 is None else (y0, y0 + h)
    faces = [
        ((0, 0, 1), [(-x, lo, z), (x, lo, z), (x, hi, z), (-x, hi, z)]),
        ((0, 0, -1), [(x, lo, -z), (-x, lo, -z), (-x, hi, -z), (x, hi, -z)]),
        ((1, 0, 0), [(x, lo, z), (x, lo, -z), (x, hi, -z), (x, hi, z)]),
        ((-1, 0, 0), [(-x, lo, -z), (-x, lo, z), (-x, hi, z), (-x, hi, -z)]),
        ((0, 1, 0), [(-x, hi, z), (x, hi, z), (x, hi, -z), (-x, hi, -z)]),
        ((0, -1, 0), [(-x, lo, -z), (x, lo, -z), (x, lo, z), (-x, lo, z)]),
    ]
    for n, quad in faces:
        ids = [m.v(p, n, uv) for p, uv in zip(quad, ((0, 0), (1, 0), (1, 1), (0, 1)))]
        m.tri(ids[0], ids[1], ids[2])
        m.tri(ids[0], ids[2], ids[3])
    return m


def _area(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly))) / 2


def triangulate(poly) -> list[tuple[int, int, int]]:
    """Ear clipping for a simple polygon (returns CCW triangles as index triples)."""
    idx = list(range(len(poly)))
    if _area(poly) < 0:
        idx.reverse()
    tris = []

    def inside(p, a, b, c):
        d1 = (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])
        d2 = (p[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (p[1] - c[1])
        d3 = (p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1])
        neg = d1 < 0 or d2 < 0 or d3 < 0
        pos = d1 > 0 or d2 > 0 or d3 > 0
        return not (neg and pos)

    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        n = len(idx)
        for k in range(n):
            i0, i1, i2 = idx[(k - 1) % n], idx[k], idx[(k + 1) % n]
            a, b, c = poly[i0], poly[i1], poly[i2]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross <= 1e-12:
                continue
            if any(inside(poly[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            break
        else:
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris


def extrude(poly, depth: float) -> Mesh:
    """Extrude a 2D polygon [(u, v)] along X: u -> -Z (forward), v -> Y (up)."""
    m = Mesh()
    hx = depth / 2
    tris = triangulate(poly)

    def P(u, v, x):
        return (x, v, -u)

    for side, nx in ((hx, 1.0), (-hx, -1.0)):
        ids = [m.v(P(u, v, side), (nx, 0, 0)) for u, v in poly]
        for a, b, c in tris:
            if nx > 0:
                m.tri(ids[a], ids[b], ids[c])
            else:
                m.tri(ids[a], ids[c], ids[b])
    ccw = _area(poly) > 0
    n = len(poly)
    for i in range(n):
        (u0, v0), (u1, v1) = poly[i], poly[(i + 1) % n]
        du, dv = u1 - u0, v1 - v0
        l = math.hypot(du, dv) or 1.0
        # outward normal in (u, v) space
        nu, nv = (dv / l, -du / l) if ccw else (-dv / l, du / l)
        nrm = (0.0, nv, -nu)
        a = m.v(P(u0, v0, hx), nrm)
        b = m.v(P(u1, v1, hx), nrm)
        c = m.v(P(u1, v1, -hx), nrm)
        d = m.v(P(u0, v0, -hx), nrm)
        m.quad(a, d, c, b) if ccw else m.quad(a, b, c, d)
    _fix_winding(m)
    return m


def loft(poly, depth: float, layers: int = 6, bulge: float = 0.35) -> Mesh:
    """Rounded extrusion: the profile is shrunk towards its centre near the sides."""
    if _area(poly) < 0:
        poly = poly[::-1]
    cu = sum(p[0] for p in poly) / len(poly)
    cv = sum(p[1] for p in poly) / len(poly)
    m = Mesh()
    hx = depth / 2
    rings = []
    for k in range(layers + 1):
        t = -1 + 2 * k / layers
        x = hx * t
        s = 1.0 - bulge * (1 - math.sqrt(max(0.0, 1 - t * t)))
        ring = [m.v((x, cv + (v - cv) * s, -(cu + (u - cu) * s))) for u, v in poly]
        rings.append(ring)
    n = len(poly)
    for k in range(layers):
        for i in range(n):
            j = (i + 1) % n
            m.quad(rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i])
    tris = triangulate(poly)
    for ring, first in ((rings[0], True), (rings[-1], False)):
        for a, b, c in tris:
            if first:
                m.tri(ring[a], ring[c], ring[b])
            else:
                m.tri(ring[a], ring[b], ring[c])
    _fix_winding(m)
    return m.smooth_normals()


def _fix_winding(m: Mesh):
    """Make triangles face away from the mesh centre (robust for convex-ish shapes)."""
    if not m.pos:
        return
    cx = sum(p[0] for p in m.pos) / len(m.pos)
    cy = sum(p[1] for p in m.pos) / len(m.pos)
    cz = sum(p[2] for p in m.pos) / len(m.pos)
    P = m.pos
    out = 0
    total = 0
    for i in range(0, len(m.idx), 3):
        a, b, c = m.idx[i:i + 3]
        n = _cross(_sub(P[b], P[a]), _sub(P[c], P[a]))
        mid = ((P[a][0] + P[b][0] + P[c][0]) / 3 - cx, (P[a][1] + P[b][1] + P[c][1]) / 3 - cy,
               (P[a][2] + P[b][2] + P[c][2]) / 3 - cz)
        d = n[0] * mid[0] + n[1] * mid[1] + n[2] * mid[2]
        total += abs(d)
        out += d
    if out < 0:  # mostly inward: flip all
        for i in range(0, len(m.idx), 3):
            m.idx[i + 1], m.idx[i + 2] = m.idx[i + 2], m.idx[i + 1]


def tube(path, radii, seg: int = 12, caps: bool = True) -> Mesh:
    """Sweep a circle along a 3D polyline. ``radii`` is a number or a per-point list."""
    if isinstance(radii, (int, float)):
        radii = [radii] * len(path)
    m = Mesh()
    n = len(path)
    tangents = []
    for i in range(n):
        a = path[max(0, i - 1)]
        b = path[min(n - 1, i + 1)]
        tangents.append(_norm(*_sub(b, a)))
    t0 = tangents[0]
    ref = (0, 1, 0) if abs(t0[1]) < 0.9 else (1, 0, 0)
    normal = _norm(*_cross(_cross(t0, ref), t0))
    rings = []
    for i in range(n):
        t = tangents[i]
        # parallel transport the normal
        d = normal[0] * t[0] + normal[1] * t[1] + normal[2] * t[2]
        normal = _norm(normal[0] - d * t[0], normal[1] - d * t[1], normal[2] - d * t[2])
        bi = _cross(t, normal)
        ring = []
        for s in range(seg + 1):
            a = math.tau * s / seg
            c, sn = math.cos(a), math.sin(a)
            nx = normal[0] * c + bi[0] * sn
            ny = normal[1] * c + bi[1] * sn
            nz = normal[2] * c + bi[2] * sn
            r = radii[i]
            ring.append(m.v((path[i][0] + nx * r, path[i][1] + ny * r, path[i][2] + nz * r), (nx, ny, nz)))
        rings.append(ring)
    for i in range(n - 1):
        for s in range(seg):
            m.quad(rings[i][s], rings[i][s + 1], rings[i + 1][s + 1], rings[i + 1][s])
    if caps:
        for i, sign in ((0, -1), (n - 1, 1)):
            t = tangents[i]
            c = m.v(path[i], (t[0] * sign, t[1] * sign, t[2] * sign))
            ring = rings[i]
            for s in range(seg):
                if sign > 0:
                    m.tri(c, ring[s], ring[s + 1])
                else:
                    m.tri(c, ring[s + 1], ring[s])
    return m


def noise3(x, y, z, seed=0) -> float:
    """Cheap smooth value noise in [-1, 1]."""
    def h(i, j, k):
        n = (i * 73856093) ^ (j * 19349663) ^ (k * 83492791) ^ (seed * 2654435761)
        n = (n << 13) ^ n
        return 1.0 - ((n * (n * n * 15731 + 789221) + 1376312589) & 0x7FFFFFFF) / 1073741824.0

    xi, yi, zi = math.floor(x), math.floor(y), math.floor(z)
    xf, yf, zf = x - xi, y - yi, z - zi
    u, v, w = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf), zf * zf * (3 - 2 * zf)

    def lerp(a, b, t):
        return a + (b - a) * t

    c000, c100 = h(xi, yi, zi), h(xi + 1, yi, zi)
    c010, c110 = h(xi, yi + 1, zi), h(xi + 1, yi + 1, zi)
    c001, c101 = h(xi, yi, zi + 1), h(xi + 1, yi, zi + 1)
    c011, c111 = h(xi, yi + 1, zi + 1), h(xi + 1, yi + 1, zi + 1)
    return lerp(lerp(lerp(c000, c100, u), lerp(c010, c110, u), v),
                lerp(lerp(c001, c101, u), lerp(c011, c111, u), v), w)


def fbm(x, y, z, octaves=4, seed=0) -> float:
    total, amp, freq = 0.0, 1.0, 1.0
    for o in range(octaves):
        total += amp * noise3(x * freq, y * freq, z * freq, seed + o)
        amp *= 0.5
        freq *= 2.0
    return total


def rock(radius: float, seed: int = 0, rough: float = 0.25, seg_u: int = 16, seg_v: int = 10,
         squash: float = 1.0) -> Mesh:
    m = ellipsoid(radius, radius * squash, radius, seg_u, seg_v)
    rng = random.Random(seed)
    off = rng.uniform(0, 100)
    return m.displace(lambda x, y, z: _radial(x, y, z, radius * rough * fbm(x / radius * 1.5 + off,
                                                                              y / radius * 1.5, z / radius * 1.5,
                                                                              3, seed)))


def _radial(x, y, z, d):
    l = math.sqrt(x * x + y * y + z * z) or 1.0
    return x / l * d, y / l * d, z / l * d
