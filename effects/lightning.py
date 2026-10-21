"""Lightning bolts and energy beams (effect objects for the ParticleSystem)."""
from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen

from .particles import Effect


def bolt_points(x1, y1, x2, y2, displace, detail=6.0, rng=random):
    """Midpoint-displacement lightning between two points."""
    pts = [(x1, y1), (x2, y2)]
    disp = displace
    while disp > detail:
        new = [pts[0]]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            mx, my = (ax + bx) / 2, (ay + by) / 2
            dx, dy = bx - ax, by - ay
            length = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / length, dx / length
            off = rng.uniform(-disp, disp)
            new.append((mx + nx * off, my + ny * off))
            new.append((bx, by))
        pts = new
        disp /= 2
    return pts


class LightningBolt(Effect):
    def __init__(self, start, end, color=(170, 200, 255), life=0.45, width=7.0,
                 branches=3, flicker=0.05, delay=0.0):
        self.start, self.end = start, end
        self.color = color
        self.life = life
        self.age = -delay
        self.width = width
        self.branches = branches
        self.flicker = flicker
        self._next = 0.0
        self.paths: list[QPainterPath] = []
        self._build()

    def _build(self):
        (x1, y1), (x2, y2) = self.start, self.end
        length = math.hypot(x2 - x1, y2 - y1)
        main = bolt_points(x1, y1, x2, y2, length * 0.18)
        self.paths = [self._path(main)]
        for _ in range(self.branches):
            if len(main) < 4:
                break
            i = random.randint(1, len(main) - 3)
            bx, by = main[i]
            ang = math.atan2(y2 - y1, x2 - x1) + random.uniform(-0.9, 0.9)
            bl = length * random.uniform(0.15, 0.35)
            ex, ey = bx + math.cos(ang) * bl, by + math.sin(ang) * bl
            self.paths.append(self._path(bolt_points(bx, by, ex, ey, bl * 0.2)))

    @staticmethod
    def _path(points):
        path = QPainterPath(QPointF(*points[0]))
        for p in points[1:]:
            path.lineTo(QPointF(*p))
        return path

    def step(self, dt):
        self.age += dt
        if self.age >= self.life:
            self.alive = False
            return
        if self.age >= 0:
            self._next -= dt
            if self._next <= 0:
                self._next = self.flicker
                self._build()

    def paint(self, painter: QPainter):
        if self.age < 0:
            return
        t = self.age / self.life
        alpha = (1.0 - t) * (0.7 + 0.3 * random.random())
        r, g, b = self.color
        painter.setOpacity(alpha)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i, path in enumerate(self.paths):
            w = self.width if i == 0 else self.width * 0.5
            for width, col in ((w * 3.2, QColor(r, g, b, 60)), (w * 1.4, QColor(r, g, b, 200)),
                               (w * 0.45, QColor(255, 255, 255, 255))):
                pen = QPen(col, width)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.drawPath(path)
        painter.setOpacity(1.0)


class Beam(Effect):
    """A straight energy beam that grows from start to end, then fades."""

    def __init__(self, start, end, color=(255, 220, 120), core=(255, 255, 240),
                 life=0.6, width=16.0, grow=0.15):
        self.start, self.end = start, end
        self.color, self.core = color, core
        self.life, self.age = life, 0.0
        self.width, self.grow = width, grow

    def step(self, dt):
        self.age += dt
        if self.age >= self.life:
            self.alive = False

    def paint(self, painter: QPainter):
        t = self.age / self.life
        g = min(1.0, self.age / self.grow) if self.grow else 1.0
        fade = 1.0 if t < 0.6 else max(0.0, 1.0 - (t - 0.6) / 0.4)
        (x1, y1), (x2, y2) = self.start, self.end
        ex, ey = x1 + (x2 - x1) * g, y1 + (y2 - y1) * g
        wobble = 1.0 + 0.15 * math.sin(self.age * 60)
        r, gg, b = self.color
        painter.setOpacity(fade)
        for width, col in ((self.width * 2.6, QColor(r, gg, b, 50)),
                           (self.width * 1.2, QColor(r, gg, b, 170)),
                           (self.width * 0.45, QColor(*self.core, 255))):
            pen = QPen(col, width * wobble)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(x1, y1), QPointF(ex, ey))
        painter.setOpacity(1.0)
