"""Magic effect library built on the particle engine.

    magic_effect(system, "lightning", (x, y), duration=800, intensity=1.5)

Kinds: fire, ice, lightning, dark, holy, heal, wind, explosion, teleport,
disintegrate, sparkle. Each faction has a palette so the same spell looks
celestial (gold/white/sky) or arcane (violet/magenta).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen

from .lightning import Beam, LightningBolt
from .particles import (GLOW, RUNE, SHARD, SMOKE, SPARK, STAR, Effect, Particle,
                        ParticleSystem, glow_sprite, mix, rand_dir, rune_paths)


@dataclass(frozen=True)
class Palette:
    core: tuple
    main: tuple
    accent: tuple
    deep: tuple
    smoke: tuple


CELESTIAL = Palette(core=(255, 250, 228), main=(255, 205, 90), accent=(125, 200, 255),
                    deep=(190, 135, 35), smoke=(235, 225, 205))
ARCANE = Palette(core=(250, 226, 255), main=(176, 92, 255), accent=(255, 72, 196),
                 deep=(70, 16, 125), smoke=(55, 28, 80))
FIRE = Palette(core=(255, 245, 200), main=(255, 150, 40), accent=(255, 70, 20),
               deep=(150, 30, 0), smoke=(70, 60, 55))
ICE = Palette(core=(240, 252, 255), main=(140, 215, 255), accent=(200, 240, 255),
              deep=(40, 110, 200), smoke=(200, 230, 255))
NATURE = Palette(core=(235, 255, 230), main=(110, 235, 140), accent=(200, 255, 120),
                 deep=(20, 120, 60), smoke=(180, 230, 190))
DANGER = Palette(core=(255, 230, 220), main=(255, 60, 60), accent=(255, 150, 60),
                 deep=(120, 0, 10), smoke=(60, 20, 20))


# ---------------------------------------------------------------- effects
class Ring(Effect):
    """Expanding shockwave ring."""

    def __init__(self, pos, color, r0=10.0, r1=120.0, life=0.5, width=10.0, additive=True):
        self.x, self.y = pos
        self.color = color
        self.r0, self.r1 = r0, r1
        self.life, self.age = life, 0.0
        self.width = width
        self.additive = additive

    def step(self, dt):
        self.age += dt
        if self.age >= self.life:
            self.alive = False

    def paint(self, painter: QPainter):
        t = self.age / self.life
        e = 1 - (1 - t) ** 3
        r = self.r0 + (self.r1 - self.r0) * e
        painter.setOpacity(max(0.0, 1.0 - t))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for w, a in ((self.width * (1 - t) * 2.5 + 1, 60), (self.width * (1 - t) + 0.5, 220)):
            painter.setPen(QPen(QColor(*self.color, a), w))
            painter.drawEllipse(QPointF(self.x, self.y), r, r)
        painter.setOpacity(1.0)


class MagicCircle(Effect):
    """Rotating runic circle. life=None keeps it until dismiss() is called."""

    def __init__(self, pos, color, radius=60.0, life: float | None = 1.5, spin=45.0,
                 runes=10, fade=0.35, seed=0, follow=None):
        self.x, self.y = pos
        self.color = color
        self.radius = radius
        self.life = life
        self.age = 0.0
        self.spin = spin
        self.runes = runes
        self.fade = fade
        self.seed = seed
        self.follow = follow
        self._dismiss_at: float | None = None

    def dismiss(self):
        if self._dismiss_at is None:
            self._dismiss_at = self.age

    def _alpha(self):
        a = min(1.0, self.age / self.fade) if self.fade else 1.0
        end = None
        if self.life is not None:
            end = self.life
        if self._dismiss_at is not None:
            end = self._dismiss_at + self.fade
        if end is not None:
            a = min(a, max(0.0, (end - self.age) / self.fade))
            if self.age >= end:
                self.alive = False
        return a

    def step(self, dt):
        self.age += dt
        if self.follow:
            try:
                self.x, self.y = self.follow()
            except RuntimeError:
                self.alive = False
        self._alpha()

    def paint(self, painter: QPainter):
        a = self._alpha()
        if a <= 0:
            return
        r = self.radius * (0.85 + 0.15 * min(1.0, self.age / 0.3))
        painter.save()
        painter.translate(self.x, self.y)
        painter.setOpacity(a * (0.8 + 0.2 * math.sin(self.age * 6)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        col = QColor(*self.color)
        glow = QColor(*self.color, 60)
        painter.rotate(self.age * self.spin)
        for pen_w, c in ((r * 0.10, glow), (r * 0.03, col)):
            painter.setPen(QPen(c, pen_w))
            painter.drawEllipse(QPointF(0, 0), r, r)
            painter.drawEllipse(QPointF(0, 0), r * 0.74, r * 0.74)
        # hexagram
        painter.setPen(QPen(col, r * 0.022))
        for k in range(2):
            pts = [QPointF(math.cos(math.radians(90 + 120 * i + 60 * k)) * r * 0.72,
                           math.sin(math.radians(90 + 120 * i + 60 * k)) * r * 0.72) for i in range(3)]
            painter.drawPolygon(pts)
        # runes in the band
        runes = rune_paths()
        pen = QPen(col, 0.09)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        for i in range(self.runes):
            ang = 360 * i / self.runes
            painter.save()
            painter.rotate(ang)
            painter.translate(0, -r * 0.87)
            painter.scale(r * 0.13, r * 0.13)
            painter.setPen(pen)
            painter.drawPath(runes[(i + self.seed) % len(runes)])
            painter.restore()
        painter.restore()
        painter.setOpacity(1.0)


class Projectile(Effect):
    """A glowing orb that flies from start to end leaving a trail, then calls on_hit."""

    def __init__(self, system: ParticleSystem, start, end, palette: Palette, life=0.35,
                 size=40.0, on_hit=None, arc=0.0, trail_rate=1.0):
        self.system = system
        self.start, self.end = start, end
        self.palette = palette
        self.life, self.age = life, 0.0
        self.size = size
        self.on_hit = on_hit
        self.arc = arc
        self.trail_rate = trail_rate
        self.x, self.y = start

    def step(self, dt):
        self.age += dt
        t = min(1.0, self.age / self.life)
        e = t * t * (3 - 2 * t) * 0.3 + t * 0.7
        (x1, y1), (x2, y2) = self.start, self.end
        self.x = x1 + (x2 - x1) * e
        self.y = y1 + (y2 - y1) * e - math.sin(math.pi * e) * self.arc
        pal = self.palette
        for _ in range(self.system.count(4 * self.trail_rate)):
            vx, vy = rand_dir(10, 60)
            self.system.add(Particle(self.x + random.uniform(-6, 6), self.y + random.uniform(-6, 6),
                                     vx, vy, life=random.uniform(0.25, 0.5), size=self.size * 0.55,
                                     size_end=2, color=random.choice((pal.main, pal.accent, pal.core)),
                                     alpha=0.8, kind=GLOW))
        if t >= 1.0:
            self.alive = False
            if self.on_hit:
                self.on_hit()

    def paint(self, painter: QPainter):
        pal = self.palette
        pulse = 1.0 + 0.12 * math.sin(self.age * 50)
        for s, c in ((self.size * 2.2, pal.main), (self.size * 1.1, pal.accent), (self.size * 0.6, pal.core)):
            s *= pulse
            painter.drawPixmap(QRectF(self.x - s / 2, self.y - s / 2, s, s), glow_sprite(*c),
                               QRectF(0, 0, 64, 64))


class Flash(Effect):
    """A big soft light flash at a point."""

    def __init__(self, pos, color, size=300.0, life=0.25):
        self.x, self.y = pos
        self.color, self.size = color, size
        self.life, self.age = life, 0.0

    def step(self, dt):
        self.age += dt
        if self.age >= self.life:
            self.alive = False

    def paint(self, painter: QPainter):
        t = self.age / self.life
        painter.setOpacity(max(0.0, 1.0 - t))
        s = self.size * (0.6 + 0.4 * t)
        painter.drawPixmap(QRectF(self.x - s / 2, self.y - s / 2, s, s), glow_sprite(*self.color),
                           QRectF(0, 0, 64, 64))
        painter.setOpacity(1.0)


# ---------------------------------------------------------------- spells
def sparkle(system, pos, palette=CELESTIAL, intensity=1.0, radius=40.0):
    x, y = pos
    for _ in range(system.count(14 * intensity)):
        vx, vy = rand_dir(10, 90)
        system.add(Particle(x + random.uniform(-radius, radius) * 0.5, y + random.uniform(-radius, radius) * 0.5,
                            vx, vy - 30, life=random.uniform(0.4, 0.9), size=random.uniform(8, 18), size_end=0,
                            color=random.choice((palette.core, palette.main, palette.accent)), kind=STAR,
                            vrot=random.uniform(-200, 200)))


def explosion(system, pos, palette=FIRE, intensity=1.0, debris=None):
    x, y = pos
    n = intensity
    system.add_effect(Flash(pos, palette.core, 260 * n, 0.22))
    system.add_effect(Flash(pos, palette.main, 380 * n, 0.4))
    system.add_effect(Ring(pos, palette.main, 10, 150 * n, 0.5, 12))
    system.add_effect(Ring(pos, palette.accent, 5, 100 * n, 0.35, 6))
    for _ in range(system.count(46 * n)):
        vx, vy = rand_dir(150, 650 * n)
        system.add(Particle(x, y, vx, vy, life=random.uniform(0.3, 0.7), size=random.uniform(3, 7),
                            color=random.choice((palette.core, palette.main, palette.accent)),
                            kind=SPARK, drag=3.5, ay=300))
    for _ in range(system.count(18 * n)):
        vx, vy = rand_dir(30, 160 * n)
        system.add(Particle(x, y, vx, vy - 40, life=random.uniform(0.5, 0.9), size=random.uniform(30, 60) * n,
                            size_end=90 * n, color=random.choice((palette.main, palette.accent)),
                            alpha=0.9, kind=GLOW, drag=2.5))
    for _ in range(system.count(12 * n)):
        vx, vy = rand_dir(20, 90)
        system.add(Particle(x, y, vx, vy - 50, life=random.uniform(0.9, 1.6), size=40 * n, size_end=110 * n,
                            color=palette.smoke, alpha=0.45, kind=SMOKE, drag=1.2, fade_in=0.1))
    if debris:
        for _ in range(system.count(14 * n)):
            vx, vy = rand_dir(120, 420)
            system.add(Particle(x, y, vx, vy - 150, life=random.uniform(0.6, 1.1), size=random.uniform(6, 14),
                                color=random.choice(debris), alpha=1.0, alpha_end=0.6, kind=SHARD,
                                ay=900, drag=0.8, rot=random.uniform(0, 360), vrot=random.uniform(-720, 720)))


def fire(system, pos, duration=0.8, intensity=1.0, palette=FIRE):
    x, y = pos

    def spawn(sys_, ex, ey):
        sys_.add(Particle(ex + random.uniform(-22, 22) * intensity, ey + random.uniform(-6, 6),
                          random.uniform(-25, 25), random.uniform(-160, -90) * intensity,
                          life=random.uniform(0.35, 0.7), size=random.uniform(26, 44) * intensity, size_end=4,
                          color=random.choice((palette.main, palette.accent, palette.core)), alpha=0.85,
                          kind=GLOW))
        if random.random() < 0.15:
            sys_.add(Particle(ex, ey - 20, random.uniform(-15, 15), -60, life=1.2, size=30, size_end=80,
                              color=palette.smoke, alpha=0.3, kind=SMOKE))
        if random.random() < 0.3:
            sys_.add(Particle(ex, ey, random.uniform(-40, 40), random.uniform(-240, -120), life=0.9,
                              size=3, color=palette.core, kind=SPARK, ay=60))

    system.add_emitter(spawn, 120 * intensity * system.quality, duration, (x, y))


def ice(system, pos, duration=0.8, intensity=1.0, palette=ICE):
    x, y = pos
    system.add_effect(Flash(pos, palette.main, 240 * intensity, 0.35))
    system.add_effect(Ring(pos, palette.accent, 10, 110 * intensity, 0.6, 8))
    for _ in range(system.count(26 * intensity)):
        vx, vy = rand_dir(80, 320)
        system.add(Particle(x, y, vx, vy, life=random.uniform(0.5, 1.0), size=random.uniform(6, 14),
                            color=random.choice((palette.main, palette.accent, palette.core)),
                            alpha=1.0, alpha_end=0.4, kind=SHARD, drag=2.0, rot=random.uniform(0, 360),
                            vrot=random.uniform(-300, 300)))
    for _ in range(system.count(10 * intensity)):
        vx, vy = rand_dir(10, 50)
        system.add(Particle(x, y, vx, vy, life=duration * 1.4, size=50, size_end=120, color=palette.smoke,
                            alpha=0.35, kind=SMOKE, fade_in=0.1))
    sparkle(system, pos, palette, intensity)


def lightning(system, pos, intensity=1.0, palette=None, origin=None, bolts=None):
    palette = palette or Palette((240, 245, 255), (160, 190, 255), (220, 230, 255), (60, 80, 200), (120, 120, 160))
    x, y = pos
    count = bolts or max(1, int(round(2 * intensity)))
    for i in range(count):
        if origin is not None:
            start = origin
        else:
            start = (x + random.uniform(-160, 160), y - random.uniform(650, 900))
        system.add_effect(LightningBolt(start, (x + random.uniform(-10, 10), y + random.uniform(-10, 10)),
                                        palette.main, life=0.4 + 0.1 * i, width=6 * intensity,
                                        branches=3, delay=i * 0.08))
    system.add_effect(Flash(pos, palette.core, 300 * intensity, 0.3))
    for _ in range(system.count(30 * intensity)):
        vx, vy = rand_dir(120, 520)
        system.add(Particle(x, y, vx, vy, life=random.uniform(0.2, 0.5), size=random.uniform(2, 5),
                            color=random.choice((palette.core, palette.main)), kind=SPARK, drag=4.0))


def dark(system, pos, duration=0.8, intensity=1.0, palette=ARCANE):
    """Implosion vortex of arcane energy."""
    x, y = pos
    system.add_effect(Ring(pos, palette.accent, 140 * intensity, 10, duration * 0.8, 8))
    for _ in range(system.count(60 * intensity)):
        ang = random.uniform(0, math.tau)
        dist = random.uniform(60, 160) * intensity
        px, py = x + math.cos(ang) * dist, y + math.sin(ang) * dist
        # inward + tangential velocity -> spiral
        speed = dist / (duration * 0.8)
        vx = -math.cos(ang) * speed - math.sin(ang) * speed * 0.6
        vy = -math.sin(ang) * speed + math.cos(ang) * speed * 0.6
        system.add(Particle(px, py, vx, vy, life=duration * 0.8, size=random.uniform(10, 22), size_end=4,
                            color=random.choice((palette.main, palette.accent, palette.deep)), alpha=0.9,
                            kind=GLOW, fade_in=0.1))
    for _ in range(system.count(6 * intensity)):
        system.add(Particle(x, y, random.uniform(-20, 20), random.uniform(-20, 20), life=duration * 1.2,
                            size=60, size_end=140, color=palette.smoke, alpha=0.5, kind=SMOKE, fade_in=0.2))
    system.after(duration * 0.75, lambda: explosion(system, pos, palette, 0.7 * intensity))


def holy(system, pos, duration=0.8, intensity=1.0, palette=CELESTIAL):
    x, y = pos
    system.add_effect(Beam((x, y - 900), (x, y), palette.main, palette.core, life=duration, width=36 * intensity,
                           grow=0.12))
    system.add_effect(Ring(pos, palette.main, 10, 140 * intensity, 0.7, 10))
    system.add_effect(Flash(pos, palette.core, 320 * intensity, 0.4))
    for _ in range(system.count(30 * intensity)):
        system.add(Particle(x + random.uniform(-50, 50), y + random.uniform(-20, 30), random.uniform(-20, 20),
                            random.uniform(-160, -60), life=random.uniform(0.6, 1.2), size=random.uniform(10, 20),
                            size_end=2, color=random.choice((palette.core, palette.main, palette.accent)),
                            kind=STAR, vrot=random.uniform(-180, 180)))


def heal(system, pos, duration=1.0, intensity=1.0, palette=NATURE):
    x, y = pos
    system.add_effect(Ring(pos, palette.main, 60, 10, 0.6, 6))
    for _ in range(system.count(24 * intensity)):
        system.add(Particle(x + random.uniform(-40, 40), y + random.uniform(-10, 30), random.uniform(-10, 10),
                            random.uniform(-110, -50), life=random.uniform(0.7, duration), size=random.uniform(10, 18),
                            color=random.choice((palette.main, palette.accent, palette.core)), kind=STAR,
                            fade_in=0.15))


def wind(system, pos, duration=0.8, intensity=1.0, palette=None, radius=70.0):
    x, y = pos
    col = palette.core if palette else (225, 235, 245)
    col2 = palette.accent if palette else (180, 210, 235)
    for _ in range(system.count(40 * intensity)):
        ang = random.uniform(0, math.tau)
        r = random.uniform(0.4, 1.0) * radius * intensity
        px, py = x + math.cos(ang) * r, y + math.sin(ang) * r
        speed = random.uniform(250, 450)
        vx, vy = -math.sin(ang) * speed, math.cos(ang) * speed
        system.add(Particle(px, py, vx, vy - 40, life=random.uniform(0.3, duration), size=random.uniform(2, 4),
                            color=random.choice((col, col2)), alpha=0.7, kind=SPARK, drag=1.5))


def teleport(system, pos, duration=0.8, intensity=1.0, palette=CELESTIAL):
    x, y = pos
    system.add_effect(Beam((x, y + 40), (x, y - 260), palette.main, palette.core, life=duration * 0.8,
                           width=50 * intensity, grow=0.1))
    system.add_effect(Ring(pos, palette.accent, 70, 5, 0.5, 6))
    system.add_effect(MagicCircle((x, y + 20), palette.main, 55 * intensity, life=duration, spin=180))
    sparkle(system, pos, palette, intensity * 1.5, 60)


def disintegrate(system, pos, colors, intensity=1.0, width=70.0, height=80.0):
    """Captured piece crumbling into glowing dust that drifts upward."""
    x, y = pos
    for _ in range(system.count(70 * intensity)):
        px = x + random.uniform(-width / 2, width / 2)
        py = y + random.uniform(-height / 2, height / 2)
        system.add(Particle(px, py, random.uniform(-40, 40), random.uniform(-120, -20),
                            life=random.uniform(0.6, 1.4), size=random.uniform(4, 10), size_end=1,
                            color=random.choice(colors), alpha=1.0, kind=GLOW, drag=0.5,
                            ax=random.uniform(-30, 30), ay=-40))
    for _ in range(system.count(10 * intensity)):
        system.add(Particle(x + random.uniform(-20, 20), y, random.uniform(-30, 30), random.uniform(-80, -20),
                            life=random.uniform(0.6, 1.2), size=random.uniform(10, 16), size_end=2,
                            color=random.choice(colors), kind=RUNE, rune=random.randint(0, 23),
                            rot=random.uniform(0, 360), vrot=random.uniform(-120, 120)))


def charge_up(system, pos, palette, duration=0.35, intensity=1.0, radius=90.0):
    """Energy converging into a point (spell casting wind-up)."""
    x, y = pos
    for _ in range(system.count(30 * intensity)):
        ang = random.uniform(0, math.tau)
        dist = random.uniform(0.6, 1.0) * radius
        px, py = x + math.cos(ang) * dist, y + math.sin(ang) * dist
        system.add(Particle(px, py, -math.cos(ang) * dist / duration, -math.sin(ang) * dist / duration,
                            life=duration, size=random.uniform(6, 12), size_end=2,
                            color=random.choice((palette.main, palette.accent, palette.core)), kind=GLOW,
                            fade_in=duration * 0.3))
    system.add_effect(Flash(pos, palette.main, 140 * intensity, duration))


def magic_effect(system: ParticleSystem, kind: str, position, duration: int = 800,
                 intensity: float = 1.0, palette: Palette | None = None, target=None):
    """Single entry point for every spell effect. ``duration`` is in milliseconds."""
    secs = duration / 1000.0
    kind = kind.lower()
    if kind == "fire":
        fire(system, position, secs, intensity, palette or FIRE)
    elif kind == "ice":
        ice(system, position, secs, intensity, palette or ICE)
    elif kind == "lightning":
        lightning(system, position, intensity, palette, origin=target)
    elif kind == "dark":
        dark(system, position, secs, intensity, palette or ARCANE)
    elif kind == "holy":
        holy(system, position, secs, intensity, palette or CELESTIAL)
    elif kind == "heal":
        heal(system, position, secs, intensity, palette or NATURE)
    elif kind == "wind":
        wind(system, position, secs, intensity, palette)
    elif kind == "explosion":
        explosion(system, position, palette or FIRE, intensity)
    elif kind == "teleport":
        teleport(system, position, secs, intensity, palette or CELESTIAL)
    elif kind == "sparkle":
        sparkle(system, position, palette or CELESTIAL, intensity)
    elif kind == "disintegrate":
        pal = palette or CELESTIAL
        disintegrate(system, position, [pal.main, pal.accent, pal.core], intensity)
    else:
        raise ValueError(f"Unknown magic effect: {kind}")


def trail_spawner(palette: Palette, size=14.0, kind=GLOW):
    """Spawn function for an Emitter that follows a moving piece."""
    def spawn(system, x, y):
        system.add(Particle(x + random.uniform(-12, 12), y + random.uniform(-12, 12), random.uniform(-20, 20),
                            random.uniform(-30, 10), life=random.uniform(0.25, 0.5), size=size, size_end=1,
                            color=random.choice((palette.main, palette.accent, palette.core)), alpha=0.8,
                            kind=kind))
    return spawn


__all__ = ["magic_effect", "Palette", "CELESTIAL", "ARCANE", "FIRE", "ICE", "NATURE", "DANGER",
           "Ring", "MagicCircle", "Projectile", "Flash", "Beam", "LightningBolt", "explosion", "fire", "ice",
           "lightning", "dark", "holy", "heal", "wind", "teleport", "disintegrate", "charge_up", "sparkle",
           "trail_spawner", "mix"]
