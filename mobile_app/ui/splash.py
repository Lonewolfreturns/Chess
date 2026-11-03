"""Loading screen shown while the game builds its 3D battlefield, sounds and menus."""
from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QGuiApplication, QLinearGradient, QPainter,
                           QPen, QRadialGradient)
from PySide6.QtWidgets import QApplication, QWidget

from platform_info import IS_MOBILE, IS_PHONE_OS

from .theme import GOLD, TITLE_FONT

TIPS = [
    "Tip: pinch to zoom the battlefield, drag with two fingers to circle it.",
    "Tip: tap a piece, then tap a glowing square to move.",
    "Tip: stuck? Press 💡 Hint and Merlin shows the best move.",
    "Tip: red rings mark your pieces in danger.",
    "Tip: the Training Academy teaches every piece step by step.",
    "Tip: try the Spell Puzzles to sharpen your tactics.",
] if IS_MOBILE else [
    "Tip: drag on empty space to orbit the camera, scroll to zoom.",
    "Tip: press H for a hint, Ctrl+Z to undo.",
    "Tip: red rings mark your pieces in danger.",
    "Tip: the Training Academy teaches every piece step by step.",
]


class Splash(QWidget):
    """Bright animated splash: crest, title, progress bar and a rotating tip."""

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Wizard War Chess")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.progress = 0.0
        self.shown_progress = 0.0
        self.status = "Opening the spellbook…"
        self.tip = random.choice(TIPS)
        self.t0 = time.perf_counter()
        rng = random.Random(7)
        self.sparks = [(rng.random(), rng.random(), rng.uniform(1.0, 3.2), rng.uniform(0, math.tau),
                        rng.uniform(0.3, 1.0)) for _ in range(70)]
        self.crest = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(33)

    # ------------------------------------------------------------ show / progress
    def present(self):
        if IS_PHONE_OS:
            self.showFullScreen()
        elif IS_MOBILE:
            from platform_info import phone_window_size
            self.resize(*phone_window_size())
            self.show()
        else:
            self.resize(560, 380)
            scr = QGuiApplication.primaryScreen().availableGeometry()
            self.move(scr.center().x() - 280, scr.center().y() - 190)
            self.show()
        self.pump()

    def step(self, progress: float, status: str):
        """Advance the bar (0..1) and let the screen redraw before the next slow step."""
        self.progress = max(self.progress, min(1.0, progress))
        self.status = status
        self.pump()

    def pump(self, seconds: float = 0.0):
        end = time.perf_counter() + seconds
        while True:
            self.repaint()
            QApplication.processEvents()
            if time.perf_counter() >= end:
                break

    def finish(self, window):
        self.step(1.0, "To battle!")
        self._timer.stop()
        QTimer.singleShot(150, self.close)

    # ------------------------------------------------------------ drawing
    def _make_crest(self, size: int):
        try:
            import chess
            from .piece_graphics import PieceRenderer
            from .theme import ARMY_STYLES
            from .widgets import avatar_pixmap
            self.crest = avatar_pixmap(PieceRenderer(), ARMY_STYLES["celestial_arcane"], chess.WHITE, size)
        except Exception:
            self.crest = False

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        t = time.perf_counter() - self.t0
        self.shown_progress += (self.progress - self.shown_progress) * 0.25
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # twilight sky: violet top, warm amber glow at the horizon
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0.0, QColor("#2a1b5e"))
        g.setColorAt(0.55, QColor("#5b2a7a"))
        g.setColorAt(0.85, QColor("#c2563f"))
        g.setColorAt(1.0, QColor("#f0a24a"))
        p.fillRect(self.rect(), QBrush(g))
        glow = QRadialGradient(w / 2, h * 0.36, max(w, h) * 0.55)
        glow.setColorAt(0.0, QColor(255, 225, 150, 120))
        glow.setColorAt(0.4, QColor(255, 180, 110, 40))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), QBrush(glow))

        # drifting golden sparks
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, r, ph, sp in self.sparks:
            yy = (y - t * 0.04 * sp) % 1.0
            a = int(90 + 90 * math.sin(t * 2 * sp + ph))
            p.setBrush(QColor(255, 220, 140, max(0, a)))
            p.drawEllipse(QPointF(x * w, yy * h), r * (1.4 if IS_MOBILE else 1.0), r * (1.4 if IS_MOBILE else 1.0))

        # crest with a slow pulse and a rotating rune ring
        cs = int(min(w * 0.42, h * 0.26))
        if self.crest is None:
            self._make_crest(cs)
        cx, cy = w / 2, h * (0.34 if IS_MOBILE else 0.32)
        ring_r = cs * 0.62
        p.setPen(QPen(QColor(255, 215, 140, 150), max(2.0, cs * 0.012)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(24):
            a0 = math.radians(i * 15 + t * 20)
            p.drawLine(QPointF(cx + math.cos(a0) * ring_r, cy + math.sin(a0) * ring_r),
                       QPointF(cx + math.cos(a0) * (ring_r + cs * 0.05), cy + math.sin(a0) * (ring_r + cs * 0.05)))
        halo = QRadialGradient(cx, cy, cs * 0.75)
        halo.setColorAt(0.0, QColor(255, 230, 160, 150 + int(40 * math.sin(t * 2.2))))
        halo.setColorAt(1.0, QColor(255, 200, 120, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(cx, cy), cs * 0.75, cs * 0.75)
        if self.crest:
            p.drawPixmap(QRectF(cx - cs / 2, cy - cs / 2, cs, cs), self.crest, QRectF(self.crest.rect()))

        # title
        f = QFont(TITLE_FONT)
        f.setBold(True)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        size = int(min(w * 0.085, 46))
        while size > 12:                     # shrink until the title fits the screen width
            f.setPixelSize(size)
            if QFontMetricsF(f).horizontalAdvance("WIZARD WAR CHESS") <= w * 0.9:
                break
            size -= 1
        p.setFont(f)
        title_rect = QRectF(0, cy + cs * 0.62, w, f.pixelSize() * 1.5)
        p.setPen(QColor(60, 25, 10, 160))
        p.drawText(title_rect.translated(2, 3), Qt.AlignmentFlag.AlignCenter, "WIZARD WAR CHESS")
        p.setPen(QColor(GOLD).lighter(115))
        p.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, "WIZARD WAR CHESS")
        f2 = QFont()
        f2.setPixelSize(int(min(w * 0.04, 16)))
        p.setFont(f2)
        p.setPen(QColor(255, 240, 220, 220))
        p.drawText(QRectF(0, title_rect.bottom(), w, f2.pixelSize() * 1.8), Qt.AlignmentFlag.AlignCenter,
                   "Command your army. Cast spells. Conquer the realm.")

        # progress bar
        bw = min(w * 0.72, 420)
        bh = max(8.0, h * 0.011)
        bx, by = (w - bw) / 2, h * (0.78 if IS_MOBILE else 0.8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(40, 15, 40, 150))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), bh / 2, bh / 2)
        fill = QLinearGradient(bx, 0, bx + bw, 0)
        fill.setColorAt(0, QColor("#ffe39a"))
        fill.setColorAt(1, QColor("#ffb347"))
        p.setBrush(QBrush(fill))
        p.drawRoundedRect(QRectF(bx, by, max(bh, bw * self.shown_progress), bh), bh / 2, bh / 2)
        shimmer = (t * 0.6) % 1.0
        sx = bx + bw * self.shown_progress * shimmer
        p.setBrush(QColor(255, 255, 255, 110))
        p.drawEllipse(QPointF(sx, by + bh / 2), bh * 0.9, bh * 0.6)

        f3 = QFont()
        f3.setPixelSize(int(min(w * 0.042, 17)))
        f3.setBold(True)
        p.setFont(f3)
        p.setPen(QColor(255, 248, 235))
        p.drawText(QRectF(0, by + bh + 8, w, f3.pixelSize() * 1.8), Qt.AlignmentFlag.AlignCenter, self.status)
        f4 = QFont()
        f4.setPixelSize(int(min(w * 0.036, 14)))
        p.setFont(f4)
        p.setPen(QColor(255, 236, 214, 210))
        p.drawText(QRectF(w * 0.08, h * 0.88, w * 0.84, h * 0.1),
                   int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop) | int(Qt.TextFlag.TextWordWrap),
                   self.tip)
        p.end()
