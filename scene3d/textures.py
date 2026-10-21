"""Procedural textures for the 3D scene, cached as PNG files."""
from __future__ import annotations

import math
import os
import random

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
                         QRadialGradient)

from effects.particles import rune_paths

from .locations import Location3D

TEX_VERSION = "t5"


def cache_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "WizardWarChess", f"tex_{TEX_VERSION}")
    os.makedirs(path, exist_ok=True)
    return path


def _cached(name: str, painter_fn, w: int, h: int, fmt=QImage.Format.Format_ARGB32) -> str:
    path = os.path.join(cache_dir(), name)
    if not os.path.isfile(path):
        img = QImage(w, h, fmt)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter_fn(p, w, h)
        p.end()
        img.save(path)
    return path


# ------------------------------------------------------------------ board
BOARD_FRAC = 8 / 9.6     # squares occupy this fraction of the board top


def board_texture(loc: Location3D) -> str:
    def paint(p: QPainter, w, h):
        rng = random.Random(7)
        frame = QColor(loc.frame)
        g = QLinearGradient(0, 0, w, h)
        g.setColorAt(0, frame.lighter(140))
        g.setColorAt(0.5, frame)
        g.setColorAt(1, frame.darker(130))
        p.fillRect(0, 0, w, h, QBrush(g))
        _speckle(p, QRectF(0, 0, w, h), rng, 6000, 0.08)
        m = w * (1 - BOARD_FRAC) / 2
        sq = (w - 2 * m) / 8
        light, dark = QColor(loc.light_sq), QColor(loc.dark_sq)
        for f in range(8):
            for r in range(8):
                rect = QRectF(m + f * sq, m + r * sq, sq, sq)
                base = light if (f + r) % 2 == 0 else dark
                k = rng.uniform(0.94, 1.06)
                c = QColor(min(255, int(base.red() * k)), min(255, int(base.green() * k)),
                           min(255, int(base.blue() * k)))
                sg = QLinearGradient(rect.topLeft(), rect.bottomRight())
                sg.setColorAt(0, c.lighter(106))
                sg.setColorAt(1, c.darker(108))
                p.fillRect(rect, QBrush(sg))
                # marble veins
                p.setPen(QPen(QColor(255, 255, 255, 34 if (f + r) % 2 else 50), 2))
                path = QPainterPath(QPointF(rect.left(), rng.uniform(rect.top(), rect.bottom())))
                path.cubicTo(QPointF(rect.left() + sq * 0.3, rng.uniform(rect.top(), rect.bottom())),
                             QPointF(rect.left() + sq * 0.7, rng.uniform(rect.top(), rect.bottom())),
                             QPointF(rect.right(), rng.uniform(rect.top(), rect.bottom())))
                p.drawPath(path)
                _speckle(p, rect, rng, 90, 0.07)
        p.setPen(QPen(QColor(0, 0, 0, 70), 3))
        for i in range(9):
            p.drawLine(QPointF(m + i * sq, m), QPointF(m + i * sq, h - m))
            p.drawLine(QPointF(m, m + i * sq), QPointF(w - m, m + i * sq))
        p.setPen(QPen(QColor(0, 0, 0, 160), 8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(m - 4, m - 4, w - 2 * m + 8, h - 2 * m + 8))
        # coordinates on the frame (white's view: a-h left->right at the bottom, rank 1 bottom)
        f = QFont("Palatino Linotype")
        f.setPixelSize(int(m * 0.42))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(235, 220, 190, 230))
        for i in range(8):
            cx = m + (i + 0.5) * sq
            p.drawText(QRectF(cx - sq / 2, h - m, sq, m * 0.95), Qt.AlignmentFlag.AlignCenter, "abcdefgh"[i])
            p.drawText(QRectF(cx - sq / 2, 0, sq, m), Qt.AlignmentFlag.AlignCenter, "abcdefgh"[i])
            cy = m + (i + 0.5) * sq
            p.drawText(QRectF(0, cy - sq / 2, m, sq), Qt.AlignmentFlag.AlignCenter, str(8 - i))
            p.drawText(QRectF(w - m, cy - sq / 2, m, sq), Qt.AlignmentFlag.AlignCenter, str(8 - i))
    return _cached(f"board_{loc.key}.png", paint, 2048, 2048)


def rune_texture(loc: Location3D) -> str:
    """Emissive map: glowing rune ring around the squares (black elsewhere)."""
    def paint(p: QPainter, w, h):
        p.fillRect(0, 0, w, h, QColor(0, 0, 0))
        m = w * (1 - BOARD_FRAC) / 2
        r, g, b = loc.rune
        runes = rune_paths()
        rng = random.Random(3)
        p.setBrush(Qt.BrushStyle.NoBrush)
        # inner glowing border line
        for width, a in ((14, 60), (5, 255)):
            p.setPen(QPen(QColor(r, g, b, a), width))
            p.drawRect(QRectF(m - 22, m - 22, w - 2 * m + 44, h - 2 * m + 44))
        n = 22
        for side in range(4):
            for i in range(n):
                t = (i + 0.5) / n
                pos = m + t * (w - 2 * m)
                if side == 0:
                    x, y = pos, m * 0.2
                elif side == 1:
                    x, y = w - m * 0.2, pos
                elif side == 2:
                    x, y = pos, h - m * 0.2
                else:
                    x, y = m * 0.2, pos
                if 0.3 < (i % 4) < 2.5:
                    continue  # leave room for coordinate letters
                p.save()
                p.translate(x, y)
                p.rotate(side * 90)
                p.scale(m * 0.2, m * 0.2)
                for width, a in ((0.3, 70), (0.1, 255)):
                    pen = QPen(QColor(r, g, b, a), width)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    p.setPen(pen)
                    p.drawPath(runes[rng.randint(0, 23)])
                p.restore()
    return _cached(f"runes_{loc.key}.png", paint, 1024, 1024, QImage.Format.Format_RGB32)


def _speckle(p: QPainter, rect: QRectF, rng, n, strength):
    p.setPen(Qt.PenStyle.NoPen)
    for _ in range(n):
        x = rng.uniform(rect.left(), rect.right())
        y = rng.uniform(rect.top(), rect.bottom())
        s = rng.uniform(0.8, 3.0)
        v = rng.choice((0, 255))
        p.setBrush(QColor(v, v, v, int(255 * strength * rng.uniform(0.3, 1.0))))
        p.drawEllipse(QPointF(x, y), s, s)


# -------------------------------------------------------------------- sky
def sky_texture(loc: Location3D) -> str:
    """Equirectangular sky (used as skybox and image-based light)."""
    s = loc.sky

    def paint(p: QPainter, w, h):
        rng = random.Random(hash(loc.key) & 0xFFFF)
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0.0, QColor(s["top"]))
        g.setColorAt(0.32, QColor(s["mid"]))
        g.setColorAt(0.5, QColor(s["horizon"]))
        g.setColorAt(0.56, QColor(s["mid"]).darker(130))
        g.setColorAt(1.0, QColor(s["bottom"]))
        p.fillRect(0, 0, w, h, QBrush(g))
        if s.get("nebula"):
            for _ in range(26):
                col = rng.choice(((120, 60, 255), (200, 60, 200), (60, 120, 255), (255, 80, 160)))
                x, y = rng.uniform(0, w), rng.uniform(h * 0.1, h * 0.9)
                r = rng.uniform(0.05, 0.16) * w
                _blob(p, x, y, r, r * 0.5, col, rng.randint(25, 55))
        for _ in range(s.get("stars", 0)):
            x, y = rng.uniform(0, w), rng.uniform(0, h * (0.98 if s.get("nebula") else 0.45))
            r = rng.uniform(0.4, 1.6)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, rng.randint(90, 255)))
            p.drawEllipse(QPointF(x, y), r, r)
        if s.get("aurora"):
            for k in range(3):
                path = QPainterPath()
                y0 = h * (0.16 + 0.06 * k)
                path.moveTo(0, y0)
                for i in range(1, 41):
                    x = w * i / 40
                    path.lineTo(x, y0 + math.sin(i * 0.5 + k) * h * 0.04)
                col = QColor(80, 255, 190, 70) if k != 1 else QColor(140, 120, 255, 60)
                p.setPen(QPen(col, h * 0.05))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)
        if s.get("clouds"):
            for _ in range(160):
                x, y = rng.uniform(0, w), rng.uniform(h * 0.5, h * 0.75)
                _blob(p, x, y, rng.uniform(0.03, 0.08) * w, rng.uniform(0.01, 0.025) * h, (255, 236, 205),
                      rng.randint(40, 110))
        if s.get("smoke"):
            for _ in range(70):
                x, y = rng.uniform(0, w), rng.uniform(h * 0.15, h * 0.5)
                _blob(p, x, y, rng.uniform(0.04, 0.1) * w, rng.uniform(0.02, 0.05) * h,
                      rng.choice(((40, 20, 18), (70, 30, 20), (20, 10, 10))), rng.randint(60, 140))
            for _ in range(8):  # distant eruptions glowing on the horizon
                x = rng.uniform(0, w)
                _blob(p, x, h * 0.5, w * 0.03, h * 0.05, (255, 90, 20), 120)
        sx, sy = s.get("sun", (0.5, 0.45))
        sun = QColor(s.get("sun_color", "#ffffff"))
        sr = s.get("sun_size", 0.04) * w
        _blob(p, sx * w, sy * h, sr * 6, sr * 4, (sun.red(), sun.green(), sun.blue()), 70)
        _blob(p, sx * w, sy * h, sr * 2, sr * 2, (sun.red(), sun.green(), sun.blue()), 200)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 245))
        p.drawEllipse(QPointF(sx * w, sy * h), sr * 0.45, sr * 0.45)
        gc = QColor(s.get("glow_color", "#ffffff"))
        hg = QLinearGradient(0, h * 0.42, 0, h * 0.58)
        hg.setColorAt(0, QColor(gc.red(), gc.green(), gc.blue(), 0))
        hg.setColorAt(0.5, QColor(gc.red(), gc.green(), gc.blue(), 90))
        hg.setColorAt(1, QColor(gc.red(), gc.green(), gc.blue(), 0))
        p.fillRect(QRectF(0, h * 0.42, w, h * 0.16), QBrush(hg))
    return _cached(f"sky_{loc.key}.png", paint, 2048, 1024, QImage.Format.Format_RGB32)


def _blob(p: QPainter, x, y, rx, ry, rgb, alpha):
    g = QRadialGradient(0, 0, 1)
    g.setColorAt(0, QColor(*rgb, alpha))
    g.setColorAt(1, QColor(*rgb, 0))
    p.save()
    p.translate(x, y)
    p.scale(rx, ry)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(QPointF(0, 0), 1, 1)
    p.restore()


# ---------------------------------------------------------------- sprites
def sprite(kind: str) -> str:
    def paint(p: QPainter, w, h):
        c = QPointF(w / 2, h / 2)
        if kind == "glow":
            g = QRadialGradient(c, w / 2)
            g.setColorAt(0, QColor(255, 255, 255, 255))
            g.setColorAt(0.25, QColor(255, 255, 255, 190))
            g.setColorAt(0.6, QColor(255, 255, 255, 50))
            g.setColorAt(1, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(g))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(c, w / 2, h / 2)
        elif kind == "spark":
            g = QRadialGradient(c, w / 2)
            g.setColorAt(0, QColor(255, 255, 255, 255))
            g.setColorAt(0.15, QColor(255, 255, 255, 230))
            g.setColorAt(0.4, QColor(255, 255, 255, 40))
            g.setColorAt(1, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(g))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(c, w / 2, h / 2)
        elif kind == "smoke":
            rng = random.Random(11)
            for _ in range(26):
                x = w / 2 + rng.uniform(-0.22, 0.22) * w
                y = h / 2 + rng.uniform(-0.22, 0.22) * h
                r = rng.uniform(0.12, 0.28) * w
                g = QRadialGradient(QPointF(x, y), r)
                g.setColorAt(0, QColor(255, 255, 255, 60))
                g.setColorAt(1, QColor(255, 255, 255, 0))
                p.setBrush(QBrush(g))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(x, y), r, r)
        elif kind == "star":
            p.setPen(Qt.PenStyle.NoPen)
            g = QRadialGradient(c, w / 2)
            g.setColorAt(0, QColor(255, 255, 255, 255))
            g.setColorAt(1, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(g))
            s = w / 2
            k = s * 0.14
            p.drawPolygon([QPointF(c.x(), c.y() - s), QPointF(c.x() + k, c.y() - k), QPointF(c.x() + s, c.y()),
                           QPointF(c.x() + k, c.y() + k), QPointF(c.x(), c.y() + s), QPointF(c.x() - k, c.y() + k),
                           QPointF(c.x() - s, c.y()), QPointF(c.x() - k, c.y() - k)])
            p.drawEllipse(c, s * 0.25, s * 0.25)
        elif kind == "snow":
            g = QRadialGradient(c, w / 2)
            g.setColorAt(0, QColor(255, 255, 255, 255))
            g.setColorAt(0.5, QColor(255, 255, 255, 200))
            g.setColorAt(1, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(g))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(c, w / 2, h / 2)
    return _cached(f"sprite_{kind}.png", paint, 128, 128)


def magic_circle_texture() -> str:
    def paint(p: QPainter, w, h):
        c = QPointF(w / 2, h / 2)
        R = w / 2 - 8
        runes = rune_paths()
        p.setBrush(Qt.BrushStyle.NoBrush)
        for width, a in ((22, 50), (7, 255)):
            p.setPen(QPen(QColor(255, 255, 255, a), width))
            p.drawEllipse(c, R, R)
            p.drawEllipse(c, R * 0.74, R * 0.74)
            p.drawEllipse(c, R * 0.3, R * 0.3)
            for k in range(2):
                pts = [QPointF(c.x() + math.cos(math.radians(90 + 120 * i + 60 * k)) * R * 0.72,
                               c.y() + math.sin(math.radians(90 + 120 * i + 60 * k)) * R * 0.72) for i in range(3)]
                p.drawPolygon(pts)
        n = 16
        for i in range(n):
            p.save()
            p.translate(c)
            p.rotate(360 * i / n)
            p.translate(0, -R * 0.87)
            p.scale(R * 0.12, R * 0.12)
            for width, a in ((0.32, 60), (0.11, 255)):
                pen = QPen(QColor(255, 255, 255, a), width)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawPath(runes[i % 24])
            p.restore()
    return _cached("magic_circle.png", paint, 1024, 1024)


def marker_texture(kind: str) -> str:
    """Square markers: 'dot' legal move, 'ring' capture, 'square' highlight, 'target' lesson goal."""
    def paint(p: QPainter, w, h):
        c = QPointF(w / 2, h / 2)
        if kind == "dot":
            g = QRadialGradient(c, w * 0.2)
            g.setColorAt(0, QColor(255, 255, 255, 255))
            g.setColorAt(0.5, QColor(255, 255, 255, 200))
            g.setColorAt(1, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(g))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(c, w * 0.2, h * 0.2)
        elif kind == "ring":
            p.setBrush(Qt.BrushStyle.NoBrush)
            for width, a in ((w * 0.1, 70), (w * 0.035, 255)):
                p.setPen(QPen(QColor(255, 255, 255, a), width))
                p.drawEllipse(c, w * 0.42, h * 0.42)
        elif kind == "square":
            g = QRadialGradient(c, w * 0.75)
            g.setColorAt(0, QColor(255, 255, 255, 150))
            g.setColorAt(1, QColor(255, 255, 255, 40))
            p.fillRect(0, 0, w, h, QBrush(g))
            p.setPen(QPen(QColor(255, 255, 255, 255), w * 0.04))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(w * 0.02, h * 0.02, w * 0.96, h * 0.96))
        elif kind == "target":
            for r, a in ((0.45, 90), (0.3, 160), (0.15, 255)):
                p.setPen(QPen(QColor(255, 255, 255, a), w * 0.04))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(c, w * r, h * r)
        elif kind == "arrow":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 235))
            p.drawRect(QRectF(w * 0.4, h * 0.3, w * 0.2, h * 0.7))
            p.drawPolygon([QPointF(w * 0.5, 0), QPointF(w * 0.92, h * 0.32), QPointF(w * 0.08, h * 0.32)])
    return _cached(f"marker_{kind}.png", paint, 256, 256)
