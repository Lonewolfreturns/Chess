"""Procedural environments: backgrounds, the floating board, runes, braziers, fog.

All art is generated in code so the game needs no image files.
"""
from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath,
                         QPen, QPixmap, QRadialGradient)
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsObject

from effects.particles import GLOW, RUNE, SMOKE, SPARK, STAR, Particle, glow_sprite, rune_paths

from .theme import TITLE_FONT, Environment

SQ = 100.0
BOARD = 8 * SQ
FRAME = 58.0


def _c(hex_or_rgb, alpha=255) -> QColor:
    c = QColor(hex_or_rgb) if isinstance(hex_or_rgb, str) else QColor(*hex_or_rgb)
    c.setAlpha(alpha)
    return c


def _shade(hex_color: str, factor: float) -> QColor:
    c = QColor(hex_color)
    return QColor(max(0, min(255, int(c.red() * factor))), max(0, min(255, int(c.green() * factor))),
                  max(0, min(255, int(c.blue() * factor))))


# =============================================================== background
def render_background(env: Environment, w: int, h: int) -> QPixmap:
    w, h = max(64, w), max(64, h)
    pix = QPixmap(w, h)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor(env.bg_top))
    g.setColorAt(1, QColor(env.bg_bottom))
    p.fillRect(0, 0, w, h, QBrush(g))
    rng = random.Random(hash(env.key) & 0xFFFF)
    {"castle": _bg_castle, "forest": _bg_forest, "ruins": _bg_ruins,
     "celestial": _bg_celestial, "volcano": _bg_volcano}.get(env.key, lambda *a: None)(p, w, h, rng, env)
    # vignette
    v = QRadialGradient(w / 2, h / 2, max(w, h) * 0.75)
    v.setColorAt(0.0, QColor(0, 0, 0, 0))
    v.setColorAt(0.6, QColor(0, 0, 0, 40))
    v.setColorAt(1.0, QColor(0, 0, 0, 200))
    p.fillRect(0, 0, w, h, QBrush(v))
    p.end()
    return pix


def _glow(p: QPainter, x, y, r, color, alpha):
    g = QRadialGradient(x, y, r)
    g.setColorAt(0, _c(color, alpha))
    g.setColorAt(1, _c(color, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(QPointF(x, y), r, r)


def _bg_castle(p, w, h, rng, env):
    bh = max(28, h // 22)
    bw = bh * 2.4
    for row in range(int(h / bh) + 2):
        off = (row % 2) * bw / 2
        y = row * bh
        x = -off
        while x < w:
            shade = rng.randint(28, 48)
            p.fillRect(QRectF(x + 2, y + 2, bw - 4, bh - 4), QColor(shade + 10, shade + 2, shade - 4))
            p.fillRect(QRectF(x + 2, y + 2, bw - 4, 3), QColor(255, 255, 255, 12))
            x += bw
    for x in (w * 0.08, w * 0.92):
        _glow(p, x, h * 0.45, h * 0.55, (255, 150, 60), 70)
    _glow(p, w / 2, h * 0.5, h * 0.6, (255, 190, 120), 25)
    # banners
    for x in (w * 0.035, w * 0.965 - w * 0.05):
        bw2 = w * 0.05
        path = QPainterPath()
        path.moveTo(x, 0)
        path.lineTo(x + bw2, 0)
        path.lineTo(x + bw2, h * 0.42)
        path.lineTo(x + bw2 / 2, h * 0.36)
        path.lineTo(x, h * 0.42)
        path.closeSubpath()
        g = QLinearGradient(x, 0, x + bw2, 0)
        g.setColorAt(0, QColor(90, 15, 25))
        g.setColorAt(0.5, QColor(140, 25, 40))
        g.setColorAt(1, QColor(70, 10, 20))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(220, 170, 80), 2))
        p.drawPath(path)


def _bg_forest(p, w, h, rng, env):
    _glow(p, w * 0.5, -h * 0.05, h * 0.7, (190, 230, 255), 60)
    for layer, (col, alpha) in enumerate(((20, 45, 30), (12, 30, 20), (6, 16, 10))):
        n = 9 + layer * 3
        for i in range(n):
            x = rng.uniform(-0.05, 1.05) * w
            tw = rng.uniform(0.015, 0.035) * w * (1 + layer * 0.4)
            p.fillRect(QRectF(x - tw / 2, h * 0.15, tw, h), QColor(*col))
            for _ in range(5):
                cx = x + rng.uniform(-0.06, 0.06) * w
                cy = rng.uniform(0.0, 0.35) * h
                r = rng.uniform(0.05, 0.11) * w * (1 + layer * 0.3)
                p.setBrush(QColor(*col))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(cx, cy), r, r * 0.8)
    for i in range(3):
        y = h * (0.55 + i * 0.15)
        g = QLinearGradient(0, y - 60, 0, y + 60)
        g.setColorAt(0, QColor(180, 220, 200, 0))
        g.setColorAt(0.5, QColor(180, 220, 200, 28))
        g.setColorAt(1, QColor(180, 220, 200, 0))
        p.fillRect(QRectF(0, y - 60, w, 120), QBrush(g))


def _stars(p, w, h, rng, n, maxr=1.8):
    p.setPen(Qt.PenStyle.NoPen)
    for _ in range(n):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.uniform(0.4, maxr)
        p.setBrush(QColor(255, 255, 255, rng.randint(80, 230)))
        p.drawEllipse(QPointF(x, y), r, r)


def _bg_ruins(p, w, h, rng, env):
    _stars(p, w, h * 0.7, rng, 220)
    _glow(p, w * 0.78, h * 0.18, h * 0.25, (220, 200, 255), 70)
    p.setBrush(QColor(235, 228, 255))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(w * 0.78, h * 0.18), h * 0.06, h * 0.06)
    _glow(p, w * 0.5, h * 0.9, h * 0.6, (150, 80, 255), 50)
    for x, top in ((0.05, 0.25), (0.13, 0.45), (0.87, 0.35), (0.95, 0.2)):
        pw = w * 0.045
        xx = x * w - pw / 2
        g = QLinearGradient(xx, 0, xx + pw, 0)
        g.setColorAt(0, QColor(45, 35, 70))
        g.setColorAt(0.5, QColor(70, 58, 100))
        g.setColorAt(1, QColor(30, 22, 48))
        p.setBrush(QBrush(g))
        path = QPainterPath()
        path.moveTo(xx, h)
        path.lineTo(xx, top * h + 20)
        path.lineTo(xx + pw * 0.4, top * h)
        path.lineTo(xx + pw * 0.7, top * h + 25)
        path.lineTo(xx + pw, top * h + 10)
        path.lineTo(xx + pw, h)
        path.closeSubpath()
        p.drawPath(path)
        p.setPen(QPen(QColor(190, 140, 255, 90), 2))
        for k in range(4):
            y = top * h + 60 + k * 45
            rp = rune_paths()[(k * 5 + int(x * 100)) % 24]
            p.save()
            p.translate(xx + pw / 2, y)
            p.scale(16, 16)
            pen = QPen(QColor(200, 150, 255, 160), 0.1)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(rp)
            p.restore()
        p.setPen(Qt.PenStyle.NoPen)


def _bg_celestial(p, w, h, rng, env):
    for _ in range(9):
        col = rng.choice(((80, 120, 255), (160, 90, 255), (60, 200, 255), (255, 120, 200)))
        _glow(p, rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.15, 0.35) * max(w, h), col, 38)
    _stars(p, w, h, rng, 420, 2.2)
    p.setPen(Qt.PenStyle.NoPen)
    for _ in range(18):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        _glow(p, x, y, rng.uniform(4, 9), (200, 225, 255), 200)


def _bg_volcano(p, w, h, rng, env):
    _glow(p, w * 0.5, h * 1.05, h * 0.75, (255, 90, 20), 130)
    for layer, col in enumerate(((50, 18, 10), (32, 10, 6))):
        path = QPainterPath()
        path.moveTo(0, h)
        x = 0.0
        y = h * (0.35 + 0.15 * layer)
        path.lineTo(0, y)
        while x < w:
            x += rng.uniform(0.05, 0.12) * w
            y = h * (0.3 + 0.15 * layer) + rng.uniform(-0.1, 0.12) * h
            path.lineTo(x, y)
        path.lineTo(w, h)
        path.closeSubpath()
        p.setBrush(QColor(*col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)
    p.setPen(QPen(QColor(255, 120, 30, 170), 3))
    for _ in range(14):
        x = rng.uniform(0, w)
        y = rng.uniform(0.6, 1.0) * h
        path = QPainterPath(QPointF(x, y))
        for _ in range(4):
            x += rng.uniform(-40, 40)
            y += rng.uniform(10, 40)
            path.lineTo(x, y)
        p.drawPath(path)


# =================================================================== board
def render_board(env: Environment, scale: float = 1.3) -> QPixmap:
    """Board + frame in world units (-FRAME .. BOARD+FRAME), rendered at ``scale`` px/unit."""
    total = BOARD + 2 * FRAME
    size = int(total * scale)
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(scale, scale)
    p.translate(FRAME, FRAME)
    rng = random.Random(42)

    # --- frame
    outer = QRectF(-FRAME, -FRAME, total, total)
    path = QPainterPath()
    path.addRoundedRect(outer, 16, 16)
    g = QLinearGradient(outer.topLeft(), outer.bottomRight())
    g.setColorAt(0.0, _shade(env.frame, 1.35))
    g.setColorAt(0.5, QColor(env.frame))
    g.setColorAt(1.0, _shade(env.frame, 0.6))
    p.fillPath(path, QBrush(g))
    # stone blocks on the frame
    p.setPen(QPen(QColor(0, 0, 0, 70), 2))
    for i in range(0, 9):
        t = i * BOARD / 8
        for (x1, y1, x2, y2) in ((t, -FRAME, t, 0), (t, BOARD, t, BOARD + FRAME),
                                 (-FRAME, t, 0, t), (BOARD, t, BOARD + FRAME, t)):
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    _noise(p, outer, rng, 900, 0.07)
    # bevel
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(_c(env.frame_edge, 200), 3))
    p.drawRoundedRect(outer.adjusted(2, 2, -2, -2), 14, 14)
    p.setPen(QPen(QColor(0, 0, 0, 160), 4))
    p.drawRect(QRectF(-6, -6, BOARD + 12, BOARD + 12))
    p.setPen(QPen(_c(env.rune, 200), 2.5))
    p.drawRect(QRectF(-10, -10, BOARD + 20, BOARD + 20))

    # corner pillar caps (braziers stand on these)
    for cx, cy in ((-FRAME / 2, -FRAME / 2), (BOARD + FRAME / 2, -FRAME / 2),
                   (-FRAME / 2, BOARD + FRAME / 2), (BOARD + FRAME / 2, BOARD + FRAME / 2)):
        r = FRAME * 0.62
        rg = QRadialGradient(cx - 8, cy - 8, r * 1.4)
        rg.setColorAt(0, _shade(env.frame, 1.6))
        rg.setColorAt(1, _shade(env.frame, 0.5))
        p.setBrush(QBrush(rg))
        p.setPen(QPen(QColor(0, 0, 0, 150), 2))
        p.drawRoundedRect(QRectF(cx - r, cy - r, 2 * r, 2 * r), 8, 8)
        p.setPen(QPen(_c(env.frame_edge, 220), 2))
        p.setBrush(QColor(15, 10, 8))
        p.drawEllipse(QPointF(cx, cy), r * 0.62, r * 0.62)

    # --- squares
    light, dark = QColor(env.light), QColor(env.dark)
    for f in range(8):
        for r in range(8):
            rect = QRectF(f * SQ, r * SQ, SQ, SQ)
            base = light if (f + r) % 2 == 0 else dark
            var = rng.uniform(0.94, 1.06)
            c = QColor(min(255, int(base.red() * var)), min(255, int(base.green() * var)),
                       min(255, int(base.blue() * var)))
            sg = QLinearGradient(rect.topLeft(), rect.bottomRight())
            sg.setColorAt(0, c.lighter(108))
            sg.setColorAt(1, c.darker(108))
            p.fillRect(rect, QBrush(sg))
            _texture(p, env.texture, rect, rng, (f + r) % 2 == 1)
    # bevel per square
    p.setPen(QPen(QColor(0, 0, 0, 45), 1.2))
    for i in range(1, 8):
        p.drawLine(QPointF(i * SQ, 0), QPointF(i * SQ, BOARD))
        p.drawLine(QPointF(0, i * SQ), QPointF(BOARD, i * SQ))
    # inner shadow at board edge
    for i in range(10):
        p.setPen(QPen(QColor(0, 0, 0, 40 - i * 4), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(i, i, BOARD - 2 * i, BOARD - 2 * i))
    p.end()
    return pix


def _noise(p, rect, rng, n, strength):
    p.setPen(Qt.PenStyle.NoPen)
    for _ in range(n):
        x = rng.uniform(rect.left(), rect.right())
        y = rng.uniform(rect.top(), rect.bottom())
        s = rng.uniform(0.8, 3.0)
        v = rng.choice((0, 255))
        p.setBrush(QColor(v, v, v, int(255 * strength * rng.uniform(0.3, 1.0))))
        p.drawEllipse(QPointF(x, y), s, s)


def _texture(p, kind, rect, rng, is_dark):
    _noise(p, rect, rng, 26, 0.06)
    p.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "stone":
        if rng.random() < 0.35:
            p.setPen(QPen(QColor(0, 0, 0, 55), 1.2))
            x, y = rng.uniform(rect.left() + 10, rect.right() - 10), rng.uniform(rect.top() + 10, rect.bottom() - 10)
            path = QPainterPath(QPointF(x, y))
            for _ in range(3):
                x += rng.uniform(-18, 18)
                y += rng.uniform(-18, 18)
                path.lineTo(x, y)
            p.drawPath(path)
    elif kind == "moss":
        p.setPen(Qt.PenStyle.NoPen)
        for _ in range(rng.randint(1, 4)):
            x = rng.choice((rect.left(), rect.right())) + rng.uniform(-6, 6)
            y = rng.uniform(rect.top(), rect.bottom())
            g = QRadialGradient(x, y, 22)
            g.setColorAt(0, QColor(70, 120, 40, 90))
            g.setColorAt(1, QColor(70, 120, 40, 0))
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(x, y), 22, 22)
    elif kind == "marble":
        p.setPen(QPen(QColor(255, 255, 255, 50 if is_dark else 70), 1.3))
        path = QPainterPath(QPointF(rect.left(), rng.uniform(rect.top(), rect.bottom())))
        path.cubicTo(QPointF(rect.left() + 30, rng.uniform(rect.top(), rect.bottom())),
                     QPointF(rect.left() + 70, rng.uniform(rect.top(), rect.bottom())),
                     QPointF(rect.right(), rng.uniform(rect.top(), rect.bottom())))
        p.drawPath(path)
    elif kind == "crystal":
        g = QLinearGradient(rect.topLeft(), rect.bottomRight())
        g.setColorAt(0.0, QColor(255, 255, 255, 0))
        g.setColorAt(0.48, QColor(255, 255, 255, 0))
        g.setColorAt(0.5, QColor(255, 255, 255, 45))
        g.setColorAt(0.62, QColor(255, 255, 255, 0))
        p.fillRect(rect, QBrush(g))
    elif kind == "basalt" and is_dark and rng.random() < 0.5:
        p.setPen(QPen(QColor(255, 110, 30, 150), 1.6))
        x, y = rng.uniform(rect.left() + 10, rect.right() - 10), rect.top() + 4
        path = QPainterPath(QPointF(x, y))
        while y < rect.bottom() - 6:
            x += rng.uniform(-14, 14)
            y += rng.uniform(10, 22)
            path.lineTo(min(rect.right() - 4, max(rect.left() + 4, x)), min(y, rect.bottom() - 4))
        p.drawPath(path)


class BoardItem(QGraphicsObject):
    """Paints the pre-rendered board, its floating shadow and magical under-glow."""

    def __init__(self, env: Environment, parent=None):
        super().__init__(parent)
        self.env = env
        self.pix = render_board(env)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

    def set_env(self, env: Environment):
        self.env = env
        self.pix = render_board(env)
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-FRAME - 80, -FRAME - 80, BOARD + 2 * FRAME + 160, BOARD + 2 * FRAME + 200)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        total = BOARD + 2 * FRAME
        # under-glow and drop shadow -> the board floats
        g = QRadialGradient(BOARD / 2, BOARD / 2 + 50, total * 0.68)
        g.setColorAt(0.0, QColor(*self.env.rune, 70))
        g.setColorAt(0.7, QColor(*self.env.rune, 25))
        g.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(g))
        painter.drawEllipse(QRectF(-FRAME - 70, -FRAME - 40, total + 140, total + 150))
        shadow = QRectF(-FRAME + 10, -FRAME + 34, total, total)
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.drawRoundedRect(shadow, 18, 18)
        painter.drawPixmap(QRectF(-FRAME, -FRAME, total, total), self.pix, QRectF(self.pix.rect()))


class RuneRingItem(QGraphicsObject):
    """Glowing runes engraved around the frame; they pulse in a slow wave."""

    def __init__(self, env: Environment, parent=None):
        super().__init__(parent)
        self.env = env
        self.t = 0.0
        self.boost = 0.0     # flare up during big events
        rng = random.Random(9)
        self.slots = []
        n_side = 14
        for side in range(4):
            for i in range(n_side):
                u = (i + 0.5) / n_side * (BOARD + 2 * FRAME * 0.6) - FRAME * 0.6
                if side == 0:
                    x, y = u, -FRAME * 0.52
                elif side == 1:
                    x, y = BOARD + FRAME * 0.52, u
                elif side == 2:
                    x, y = BOARD - u, BOARD + FRAME * 0.52
                else:
                    x, y = -FRAME * 0.52, BOARD - u
                if (x < 0 or x > BOARD) and (y < 0 or y > BOARD):
                    continue  # skip corners (braziers)
                self.slots.append((x, y, rng.randint(0, 23), side * 90))

    def boundingRect(self) -> QRectF:
        return QRectF(-FRAME, -FRAME, BOARD + 2 * FRAME, BOARD + 2 * FRAME)

    def tick(self, dt):
        self.t += dt
        self.boost = max(0.0, self.boost - dt * 0.6)
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        runes = rune_paths()
        r, g, b = self.env.rune
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        n = len(self.slots)
        for i, (x, y, k, rot) in enumerate(self.slots):
            wave = 0.5 + 0.5 * math.sin(self.t * 1.6 - i * (math.tau / n) * 3)
            a = min(1.0, 0.22 + 0.55 * wave + self.boost)
            painter.save()
            painter.translate(x, y)
            painter.rotate(rot)
            painter.scale(17, 17)
            painter.setPen(QPen(QColor(r, g, b, int(70 * a)), 0.32, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawPath(runes[k])
            painter.setPen(QPen(QColor(min(255, r + 60), min(255, g + 60), min(255, b + 60), int(230 * a)),
                                0.09, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawPath(runes[k])
            painter.restore()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)


class CoordItem(QGraphicsItem):
    """File letters and rank numbers drawn inside the edge squares."""

    def __init__(self, env: Environment, parent=None):
        super().__init__(parent)
        self.env = env
        self.flipped = False

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, BOARD, BOARD)

    def paint(self, painter: QPainter, option, widget=None):
        font = QFont(TITLE_FONT)
        font.setPixelSize(17)
        font.setBold(True)
        painter.setFont(font)
        light, dark = QColor(self.env.light), QColor(self.env.dark)
        for i in range(8):
            f = 7 - i if self.flipped else i
            r = i if self.flipped else 7 - i
            # files along bottom row
            col_dark = (i + 7) % 2 == 1
            painter.setPen(light if col_dark else dark)
            painter.drawText(QRectF(i * SQ, BOARD - 24, SQ - 6, 22),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "abcdefgh"[f])
            row_dark = i % 2 == 1
            painter.setPen(light if row_dark else dark)
            painter.drawText(QRectF(5, i * SQ + 3, 30, 22), Qt.AlignmentFlag.AlignLeft, str(r + 1))


class BrazierItem(QGraphicsObject):
    """Flickering fire glow on a corner pillar (flame particles are emitted separately)."""

    def __init__(self, pos, palette, parent=None):
        super().__init__(parent)
        self.setPos(*pos)
        self.palette = palette
        self.t = random.uniform(0, 10)
        self.flicker = 1.0

    def boundingRect(self) -> QRectF:
        return QRectF(-160, -200, 320, 320)

    def tick(self, dt):
        self.t += dt
        self.flicker = 0.8 + 0.12 * math.sin(self.t * 13) + 0.08 * math.sin(self.t * 29 + 1)
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        r = 150 * self.flicker
        g = QRadialGradient(0, -20, r)
        g.setColorAt(0, QColor(*self.palette.main, 110))
        g.setColorAt(0.4, QColor(*self.palette.accent, 40))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(g))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        painter.drawEllipse(QPointF(0, -20), r, r)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        # coal bed
        cg = QRadialGradient(0, 0, 20)
        cg.setColorAt(0, QColor(*self.palette.core, 255))
        cg.setColorAt(0.5, QColor(*self.palette.main, 200))
        cg.setColorAt(1, QColor(*self.palette.deep, 0))
        painter.setBrush(QBrush(cg))
        painter.drawEllipse(QPointF(0, 0), 20, 11)


def flame_spawner(palette):
    def spawn(system, x, y):
        system.add(Particle(x + random.uniform(-10, 10), y + random.uniform(-3, 3), random.uniform(-12, 12),
                            random.uniform(-120, -70), life=random.uniform(0.4, 0.7),
                            size=random.uniform(30, 44), size_end=6,
                            color=random.choice((palette.main, palette.accent, palette.core)), alpha=0.85,
                            kind=GLOW, ax=random.uniform(-20, 20)))
        if random.random() < 0.12:
            system.add(Particle(x, y - 10, random.uniform(-30, 30), random.uniform(-160, -80), life=1.0,
                                size=2.5, color=palette.core, kind=SPARK, ay=20))
        if random.random() < 0.06:
            system.add(Particle(x, y - 30, random.uniform(-10, 10), -40, life=1.6, size=20, size_end=60,
                                color=palette.smoke, alpha=0.18, kind=SMOKE))
    return spawn


def ambient_spawner(env: Environment, area: QRectF):
    """Spawn function for floating ambient particles of an environment."""
    kind = env.ambient
    rune_col = env.rune

    def spawn(system, _x, _y):
        x = random.uniform(area.left(), area.right())
        y = random.uniform(area.top(), area.bottom())
        if kind == "embers":
            system.add(Particle(x, area.bottom(), random.uniform(-15, 15), random.uniform(-70, -30),
                                life=random.uniform(5, 9), size=random.uniform(3, 6), size_end=1,
                                color=random.choice(((255, 170, 70), (255, 120, 40))), alpha=0.9,
                                kind=GLOW, ax=random.uniform(-6, 6), fade_in=0.5))
        elif kind == "ash":
            system.add(Particle(x, area.bottom(), random.uniform(-20, 20), random.uniform(-90, -40),
                                life=random.uniform(4, 7), size=random.uniform(3, 7), size_end=1,
                                color=random.choice(((255, 140, 50), (255, 90, 30), (255, 200, 120))),
                                alpha=0.9, kind=GLOW, ax=random.uniform(-10, 10), fade_in=0.4))
        elif kind == "fireflies":
            system.add(Particle(x, y, random.uniform(-14, 14), random.uniform(-14, 14),
                                life=random.uniform(3, 6), size=random.uniform(7, 12), size_end=7,
                                color=random.choice(((210, 255, 120), (160, 255, 150))), alpha=0.9,
                                alpha_end=0.0, kind=GLOW, ax=random.uniform(-4, 4), ay=random.uniform(-4, 4),
                                fade_in=1.0))
        elif kind == "runes":
            if random.random() < 0.35:
                system.add(Particle(x, y, random.uniform(-6, 6), random.uniform(-18, -6), life=random.uniform(4, 7),
                                    size=random.uniform(10, 16), color=rune_col, alpha=0.55, kind=RUNE,
                                    rune=random.randint(0, 23), vrot=random.uniform(-20, 20), fade_in=1.5))
            else:
                system.add(Particle(x, y, random.uniform(-8, 8), random.uniform(-20, -6), life=random.uniform(4, 7),
                                    size=random.uniform(4, 8), color=rune_col, alpha=0.7, kind=GLOW, fade_in=1.0))
        elif kind == "stars":
            system.add(Particle(x, y, 0, random.uniform(-4, 4), life=random.uniform(2, 4),
                                size=random.uniform(8, 16), size_end=0, color=random.choice(((220, 235, 255), (255, 240, 200))),
                                alpha=0.8, kind=STAR, vrot=random.uniform(-40, 40), fade_in=0.8))
    return spawn


class FogLayer(QGraphicsObject):
    """Slowly drifting soft fog blobs."""

    def __init__(self, env: Environment, area: QRectF, strength: float = 1.0, count: int = 7, parent=None):
        super().__init__(parent)
        self.area = area
        self.strength = strength
        self.env = env
        rng = random.Random(count * 31)
        self.blobs = [[rng.uniform(area.left(), area.right()), rng.uniform(area.top(), area.bottom()),
                       rng.uniform(260, 520), rng.uniform(-14, 14), rng.uniform(-5, 5), rng.uniform(0, 6.28)]
                      for _ in range(count)]

    def set_env(self, env):
        self.env = env
        self.update()

    def boundingRect(self) -> QRectF:
        return self.area.adjusted(-400, -400, 400, 400)

    def tick(self, dt):
        a = self.area
        for b in self.blobs:
            b[0] += b[3] * dt
            b[1] += b[4] * dt
            b[5] += dt * 0.3
            if b[0] < a.left() - b[2]:
                b[0] = a.right() + b[2] * 0.5
            elif b[0] > a.right() + b[2]:
                b[0] = a.left() - b[2] * 0.5
            if b[1] < a.top() - b[2] or b[1] > a.bottom() + b[2]:
                b[4] = -b[4]
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        alpha = self.env.fog_alpha * self.strength
        if alpha <= 0.005:
            return
        sprite = glow_sprite(*self.env.fog, hard=True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for x, y, r, _vx, _vy, ph in self.blobs:
            painter.setOpacity(alpha * (0.7 + 0.3 * math.sin(ph)))
            painter.drawPixmap(QRectF(x - r, y - r * 0.6, 2 * r, 1.2 * r), sprite, QRectF(0, 0, 64, 64))
        painter.setOpacity(1.0)
