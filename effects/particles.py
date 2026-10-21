"""Particle system: a single QGraphicsObject that simulates and paints every
particle and effect object. One item is far faster than thousands of items.

Coordinates are in the parent's (world) units.
"""
from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QPainter, QPainterPath, QPen, QPixmap,
                         QRadialGradient)
from PyQt6.QtWidgets import QGraphicsObject

# Particle kinds
GLOW = 0     # soft additive light blob
SPARK = 1    # additive streak aligned with velocity
SMOKE = 2    # soft normal-blended puff
SHARD = 3    # rotating polygon debris
RUNE = 4     # rotating glowing rune glyph
STAR = 5     # four-point twinkle

MAX_PARTICLES = 1800

_sprite_cache: dict = {}


def glow_sprite(r: int, g: int, b: int, hard: bool = False) -> QPixmap:
    """Radial-gradient sprite used for glows and smoke (cached per colour)."""
    key = (r >> 3, g >> 3, b >> 3, hard)
    pix = _sprite_cache.get(key)
    if pix is None:
        size = 64
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QRadialGradient(size / 2, size / 2, size / 2)
        core = QColor(min(255, r + (255 - r) // 2), min(255, g + (255 - g) // 2), min(255, b + (255 - b) // 2))
        if hard:
            grad.setColorAt(0.0, QColor(r, g, b, 230))
            grad.setColorAt(0.6, QColor(r, g, b, 140))
            grad.setColorAt(1.0, QColor(r, g, b, 0))
        else:
            grad.setColorAt(0.0, core)
            grad.setColorAt(0.25, QColor(r, g, b, 235))
            grad.setColorAt(0.6, QColor(r, g, b, 90))
            grad.setColorAt(1.0, QColor(r, g, b, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(0, 0, size, size)
        p.end()
        _sprite_cache[key] = pix
    return pix


# ------------------------------------------------------------------- runes
_rune_cache: list[QPainterPath] = []


def rune_paths() -> list[QPainterPath]:
    """24 procedurally generated rune glyphs in a unit box centred on 0,0."""
    if not _rune_cache:
        rng = random.Random(1337)
        pts = [(x * 0.5 - 0.5, y * 0.5 - 0.5) for y in range(3) for x in range(3)]
        for _ in range(24):
            path = QPainterPath()
            # a vertical stave plus 2-3 branches
            sx = rng.choice((-0.25, 0.0, 0.25))
            path.moveTo(sx, -0.5)
            path.lineTo(sx, 0.5)
            for _ in range(rng.randint(2, 3)):
                a = rng.choice(pts)
                b = rng.choice(pts)
                if a != b:
                    path.moveTo(*a)
                    path.lineTo(*b)
            _rune_cache.append(path)
    return _rune_cache


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "ax", "ay", "drag", "life", "age", "s0", "s1",
                 "r", "g", "b", "a0", "a1", "kind", "rot", "vrot", "fade_in", "rune")

    def __init__(self, x, y, vx=0.0, vy=0.0, life=1.0, size=10.0, size_end=None,
                 color=(255, 255, 255), alpha=1.0, alpha_end=0.0, kind=GLOW,
                 ax=0.0, ay=0.0, drag=0.0, rot=0.0, vrot=0.0, fade_in=0.0, rune=0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.ax, self.ay, self.drag = ax, ay, drag
        self.life, self.age = max(0.01, life), 0.0
        self.s0 = size
        self.s1 = size if size_end is None else size_end
        self.r, self.g, self.b = color
        self.a0, self.a1 = alpha, alpha_end
        self.kind = kind
        self.rot, self.vrot = rot, vrot
        self.fade_in = fade_in
        self.rune = rune


class Emitter:
    """Spawns particles continuously. ``spawn(emitter, dt)`` adds particles."""

    def __init__(self, system: "ParticleSystem", spawn, rate: float, duration: float | None = None,
                 pos=(0.0, 0.0), follow=None):
        self.system = system
        self.spawn_fn = spawn
        self.rate = rate
        self.remaining = duration
        self.pos = pos
        self.follow = follow      # optional callable returning (x, y)
        self.alive = True
        self._acc = 0.0

    def position(self):
        if self.follow is not None:
            try:
                return self.follow()
            except RuntimeError:  # followed item deleted
                self.alive = False
        return self.pos

    def step(self, dt):
        if not self.alive:
            return
        if self.remaining is not None:
            self.remaining -= dt
            if self.remaining <= 0:
                self.alive = False
                return
        self._acc += self.rate * dt
        n = int(self._acc)
        self._acc -= n
        if n and len(self.system.particles) < MAX_PARTICLES:
            x, y = self.position()
            for _ in range(n):
                self.spawn_fn(self.system, x, y)

    def stop(self):
        self.alive = False


class Effect:
    """Base class for non-particle effect objects (bolts, beams, rings...)."""
    additive = True
    alive = True

    def step(self, dt: float) -> None:  # pragma: no cover - interface
        pass

    def paint(self, painter: QPainter) -> None:  # pragma: no cover - interface
        pass


class ParticleSystem(QGraphicsObject):
    def __init__(self, bounds: QRectF, parent=None):
        super().__init__(parent)
        self._bounds = bounds
        self.particles: list[Particle] = []
        self.emitters: list[Emitter] = []
        self.effects: list[Effect] = []
        self.timers: list[list] = []   # [remaining, callback]
        self.quality = 1.0             # 0.4 .. 1.0 scales particle counts

    # ------------------------------------------------------------- API
    def add(self, p: Particle):
        if len(self.particles) < MAX_PARTICLES:
            self.particles.append(p)

    def add_effect(self, fx: Effect) -> Effect:
        self.effects.append(fx)
        return fx

    def add_emitter(self, spawn, rate, duration=None, pos=(0, 0), follow=None) -> Emitter:
        em = Emitter(self, spawn, rate, duration, pos, follow)
        self.emitters.append(em)
        return em

    def after(self, seconds: float, callback):
        self.timers.append([seconds, callback])

    def count(self, n: float) -> int:
        return max(1, int(n * self.quality))

    def clear(self, keep_emitters: bool = True):
        self.particles.clear()
        self.effects.clear()
        self.timers.clear()
        if not keep_emitters:
            self.emitters.clear()

    @property
    def busy(self) -> bool:
        return bool(self.effects or self.timers)

    # ------------------------------------------------------------- simulation
    def step(self, dt: float):
        if self.timers:
            due = []
            for t in self.timers:
                t[0] -= dt
                if t[0] <= 0:
                    due.append(t)
            for t in due:
                self.timers.remove(t)
                t[1]()
        for em in self.emitters:
            em.step(dt)
        if self.emitters:
            self.emitters = [e for e in self.emitters if e.alive]

        alive = []
        for p in self.particles:
            p.age += dt
            if p.age >= p.life:
                continue
            if p.drag:
                k = max(0.0, 1.0 - p.drag * dt)
                p.vx *= k
                p.vy *= k
            p.vx += p.ax * dt
            p.vy += p.ay * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            if p.vrot:
                p.rot += p.vrot * dt
            alive.append(p)
        self.particles = alive

        if self.effects:
            for fx in self.effects:
                fx.step(dt)
            self.effects = [fx for fx in self.effects if fx.alive]
        if self.particles or self.effects or self.emitters:
            self.update()

    # ------------------------------------------------------------- painting
    def boundingRect(self) -> QRectF:
        return self._bounds

    def paint(self, painter: QPainter, option, widget=None):
        if not self.particles and not self.effects:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        normal = [p for p in self.particles if p.kind in (SMOKE, SHARD)]
        additive = [p for p in self.particles if p.kind not in (SMOKE, SHARD)]

        for p in normal:
            self._draw(painter, p)
        for fx in self.effects:
            if not fx.additive:
                fx.paint(painter)

        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        for p in additive:
            self._draw(painter, p)
        for fx in self.effects:
            if fx.additive:
                fx.paint(painter)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setOpacity(1.0)

    def _draw(self, painter: QPainter, p: Particle):
        t = p.age / p.life
        a = p.a0 + (p.a1 - p.a0) * t
        if p.fade_in and p.age < p.fade_in:
            a *= p.age / p.fade_in
        if a <= 0.01:
            return
        size = p.s0 + (p.s1 - p.s0) * t
        painter.setOpacity(min(1.0, a))
        kind = p.kind
        if kind == GLOW or kind == SMOKE:
            pix = glow_sprite(p.r, p.g, p.b, hard=(kind == SMOKE))
            painter.drawPixmap(QRectF(p.x - size / 2, p.y - size / 2, size, size), pix,
                               QRectF(0, 0, 64, 64))
        elif kind == SPARK:
            speed = math.hypot(p.vx, p.vy) or 1.0
            length = min(size * 4, 0.045 * speed + size)
            dx, dy = p.vx / speed * length, p.vy / speed * length
            pen = QPen(QColor(p.r, p.g, p.b), max(0.8, size * 0.45))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(p.x - dx, p.y - dy), QPointF(p.x, p.y))
        elif kind == SHARD:
            painter.save()
            painter.translate(p.x, p.y)
            painter.rotate(p.rot)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(p.r, p.g, p.b))
            s = size / 2
            painter.drawPolygon([QPointF(-s, -s * 0.4), QPointF(s * 0.6, -s), QPointF(s, s * 0.5),
                                 QPointF(-s * 0.3, s)])
            painter.restore()
        elif kind == STAR:
            painter.save()
            painter.translate(p.x, p.y)
            painter.rotate(p.rot)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(p.r, p.g, p.b))
            s = size / 2
            w = s * 0.18
            painter.drawPolygon([QPointF(0, -s), QPointF(w, -w), QPointF(s, 0), QPointF(w, w),
                                 QPointF(0, s), QPointF(-w, w), QPointF(-s, 0), QPointF(-w, -w)])
            painter.restore()
        elif kind == RUNE:
            painter.save()
            painter.translate(p.x, p.y)
            painter.rotate(p.rot)
            painter.scale(size, size)
            pen = QPen(QColor(p.r, p.g, p.b), 0.09)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(rune_paths()[p.rune % 24])
            painter.restore()


# ------------------------------------------------------------- helpers
def rand_dir(speed_min: float, speed_max: float, rng=random) -> tuple[float, float]:
    a = rng.uniform(0, math.tau)
    s = rng.uniform(speed_min, speed_max)
    return math.cos(a) * s, math.sin(a) * s


def mix(c1, c2, t: float):
    return (int(c1[0] + (c2[0] - c1[0]) * t), int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))
