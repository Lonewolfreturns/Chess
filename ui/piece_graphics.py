"""Procedural fantasy piece art + the animated QGraphics piece item.

Pieces are drawn from chess glyph outlines, then given a faction material:
gradient body, metallic sheen, glowing detail lines, rim light, a soft aura
and gem accents. Variants for the hit-flash and frozen (checkmate) effects
are pre-rendered too.

Custom art: put PNG files in ``assets/pieces`` named wK.png, wQ.png ... bP.png
(or animated horizontal sprite sheets named wK_sheet.png with square frames)
and they are used automatically instead of the procedural pieces.
"""
from __future__ import annotations

import math
import os
import random
import sys

import chess
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QImage, QLinearGradient,
                         QPainter, QPainterPath, QPen, QPixmap, QRadialGradient, QTransform)
from PyQt6.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem, QGraphicsObject,
                             QGraphicsPixmapItem)

from .theme import ArmyStyle

SOLID = {chess.KING: "♚", chess.QUEEN: "♛", chess.ROOK: "♜",
         chess.BISHOP: "♝", chess.KNIGHT: "♞", chess.PAWN: "♟"}
OUTLINE = {chess.KING: "♔", chess.QUEEN: "♕", chess.ROOK: "♖",
           chess.BISHOP: "♗", chess.KNIGHT: "♘", chess.PAWN: "♙"}

PIX = 220          # rendered pixmap size for one square
SQUARE = 100.0     # world units per square


def resource_path(*parts: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)


def _blur(img: QImage, factor: int) -> QImage:
    w, h = img.width(), img.height()
    small = img.scaled(max(1, w // factor), max(1, h // factor), Qt.AspectRatioMode.IgnoreAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
    return small.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)


def _filled(path: QPainterPath, size: int, color: QColor) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.fillPath(path, color)
    p.end()
    return img


class PieceRenderer:
    def __init__(self):
        self.family = self._pick_font()
        self._cache: dict = {}
        self._paths: dict = {}
        self._scale = None

    @staticmethod
    def _pick_font() -> str:
        families = set(QFontDatabase.families())
        for name in ("Segoe UI Symbol", "DejaVu Sans", "Noto Sans Symbols2", "Noto Sans Symbols",
                     "Arial Unicode MS", "FreeSerif", "Symbola"):
            if name in families:
                return name
        return QFont().family()

    # -------------------------------------------------------------- geometry
    def _raw_path(self, ch: str) -> QPainterPath:
        if ch not in self._paths:
            font = QFont(self.family)
            font.setPixelSize(1000)
            path = QPainterPath()
            path.addText(0, 0, font, ch)
            self._paths[ch] = path
        return self._paths[ch]

    def _transform(self, pt: int, px: int) -> QTransform:
        if self._scale is None:
            kb = self._raw_path(SOLID[chess.KING]).boundingRect()
            self._scale = 1.0 / max(kb.height(), kb.width() * 1.05)
        s = self._scale * px * 0.80
        b = self._raw_path(SOLID[pt]).boundingRect()
        t = QTransform()
        t.translate(px / 2 - (b.center().x()) * s, px * 0.90 - b.bottom() * s)
        t.scale(s, s)
        return t

    def paths(self, pt: int, px: int) -> tuple[QPainterPath, QPainterPath]:
        t = self._transform(pt, px)
        solid = t.map(self._raw_path(SOLID[pt]))
        outline = t.map(self._raw_path(OUTLINE[pt]))
        solid.setFillRule(Qt.FillRule.WindingFill)
        return solid, outline

    # -------------------------------------------------------------- rendering
    def variants(self, pt: int, color: bool, style: ArmyStyle, px: int = PIX) -> dict:
        key = (pt, color, style.key, px)
        if key not in self._cache:
            custom = self._custom(pt, color, px)
            if custom:
                frames = custom
                normal = frames[0]
            else:
                normal = QPixmap.fromImage(self._render(pt, color, style, px))
                frames = [normal]
            self._cache[key] = {
                "normal": normal,
                "frames": frames,
                "flash": QPixmap.fromImage(self._tinted(normal.toImage(), QColor(255, 255, 255), 1.0)),
                "frozen": QPixmap.fromImage(self._frozen(normal.toImage())),
            }
        return self._cache[key]

    def pixmap(self, pt: int, color: bool, style: ArmyStyle, px: int = PIX) -> QPixmap:
        return self.variants(pt, color, style, px)["normal"]

    def _custom(self, pt: int, color: bool, px: int) -> list[QPixmap] | None:
        code = ("w" if color else "b") + chess.piece_symbol(pt).upper()
        folder = resource_path("assets", "pieces")
        sheet = os.path.join(folder, f"{code}_sheet.png")
        single = os.path.join(folder, f"{code}.png")
        if os.path.isfile(sheet):
            img = QPixmap(sheet)
            if not img.isNull() and img.height() > 0:
                n = max(1, img.width() // img.height())
                h = img.height()
                return [img.copy(i * h, 0, h, h).scaled(px, px, Qt.AspectRatioMode.KeepAspectRatio,
                                                         Qt.TransformationMode.SmoothTransformation)
                        for i in range(n)]
        if os.path.isfile(single):
            img = QPixmap(single)
            if not img.isNull():
                canvas = QPixmap(px, px)
                canvas.fill(Qt.GlobalColor.transparent)
                scaled = img.scaled(int(px * 0.92), int(px * 0.92), Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
                p = QPainter(canvas)
                p.drawPixmap((px - scaled.width()) // 2, int(px * 0.94) - scaled.height(), scaled)
                p.end()
                return [canvas]
        return None

    def _render(self, pt: int, color: bool, style: ArmyStyle, px: int) -> QImage:
        mat = style.material(color)
        solid, outline = self.paths(pt, px)
        bounds = solid.boundingRect()
        img = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 1. soft magical aura
        aura = _blur(_filled(solid, px, QColor(*mat.glow, 255)), 14)
        p.setOpacity(0.55)
        p.drawImage(0, 0, aura)
        p.setOpacity(1.0)

        # 2. dark under-outline for definition on any board colour
        p.setPen(QPen(QColor(0, 0, 0, 150), px * 0.022, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(solid)

        # 3. body gradient
        grad = QLinearGradient(bounds.topLeft(), bounds.bottomLeft())
        stops = mat.fill
        for i, c in enumerate(stops):
            grad.setColorAt(i / (len(stops) - 1), QColor(c))
        p.fillPath(solid, QBrush(grad))

        # 4. metallic sheen + side shading (clipped to body)
        p.save()
        p.setClipPath(solid)
        sheen = QLinearGradient(bounds.left(), bounds.top(), bounds.right(), bounds.bottom())
        sheen.setColorAt(0.0, QColor(255, 255, 255, 0))
        sheen.setColorAt(0.30, QColor(255, 255, 255, 90 if not mat.glowing_lines else 45))
        sheen.setColorAt(0.42, QColor(255, 255, 255, 0))
        sheen.setColorAt(0.75, QColor(0, 0, 0, 0))
        sheen.setColorAt(1.0, QColor(0, 0, 0, 90))
        p.fillRect(bounds, QBrush(sheen))
        shade = QLinearGradient(bounds.left(), 0, bounds.right(), 0)
        shade.setColorAt(0.0, QColor(255, 255, 255, 40))
        shade.setColorAt(0.5, QColor(0, 0, 0, 0))
        shade.setColorAt(1.0, QColor(0, 0, 0, 70))
        p.fillRect(bounds, QBrush(shade))
        p.restore()

        # 5. detail lines (glowing for dark/arcane materials)
        line_col = QColor(mat.line)
        if mat.glowing_lines:
            glow = _blur(_filled(outline, px, QColor(*mat.glow, 255)), 6)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            p.drawImage(0, 0, glow)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.fillPath(outline, line_col)

        # 6. rim light
        rim = QColor(mat.rim)
        rim.setAlpha(170)
        p.setPen(QPen(rim, px * 0.006))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(solid)

        # 7. gem / orb accents for the officers
        if pt in (chess.KING, chess.QUEEN, chess.BISHOP):
            cx = bounds.center().x()
            cy = bounds.top() + bounds.height() * (0.50 if pt == chess.BISHOP else 0.56)
            r = px * (0.035 if pt == chess.BISHOP else 0.042)
            g = QRadialGradient(cx - r * 0.3, cy - r * 0.3, r * 1.6)
            g.setColorAt(0.0, QColor(255, 255, 255))
            g.setColorAt(0.35, QColor(*mat.gem))
            g.setColorAt(1.0, QColor(*mat.gem, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(cx, cy), r * 1.6, r * 1.6)
        p.end()
        return img

    @staticmethod
    def _tinted(img: QImage, color: QColor, strength: float) -> QImage:
        out = QImage(img)
        p = QPainter(out)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
        c = QColor(color)
        c.setAlphaF(strength)
        p.fillRect(out.rect(), c)
        p.end()
        return out

    @staticmethod
    def _frozen(img: QImage) -> QImage:
        out = QImage(img)
        p = QPainter(out)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
        grad = QLinearGradient(0, 0, out.width(), out.height())
        grad.setColorAt(0.0, QColor(235, 250, 255, 220))
        grad.setColorAt(0.5, QColor(140, 200, 245, 190))
        grad.setColorAt(1.0, QColor(60, 120, 200, 210))
        p.fillRect(out.rect(), QBrush(grad))
        p.setPen(QPen(QColor(255, 255, 255, 200), 2))
        rng = random.Random(7)
        for _ in range(14):  # frost cracks
            x, y = rng.uniform(0.25, 0.75) * out.width(), rng.uniform(0.3, 0.85) * out.height()
            ang = rng.uniform(0, math.tau)
            ln = rng.uniform(8, 22)
            p.drawLine(QPointF(x, y), QPointF(x + math.cos(ang) * ln, y + math.sin(ang) * ln))
        p.end()
        return out


# ====================================================================== items
class AuraItem(QGraphicsItem):
    """Pulsing selection glow under a piece."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = QColor(255, 220, 120)
        self.strength = 0.0
        self.phase = 0.0

    def boundingRect(self) -> QRectF:
        return QRectF(-30, -40, SQUARE + 60, SQUARE + 70)

    def paint(self, painter: QPainter, option, widget=None):
        if self.strength <= 0.01:
            return
        pulse = 0.75 + 0.25 * math.sin(self.phase * 4)
        g = QRadialGradient(SQUARE / 2, SQUARE * 0.62, SQUARE * 0.62)
        c = QColor(self.color)
        c.setAlphaF(0.75 * self.strength * pulse)
        g.setColorAt(0.0, c)
        c2 = QColor(self.color)
        c2.setAlphaF(0.25 * self.strength * pulse)
        g.setColorAt(0.55, c2)
        g.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(g))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        painter.drawEllipse(QRectF(-12, -10, SQUARE + 24, SQUARE + 30))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)


class PieceItem(QGraphicsObject):
    """A chess piece on the board: container for shadow, aura, sprite and overlays."""

    def __init__(self, piece: chess.Piece, square: int, variants: dict, glow_rgb: tuple, parent=None):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemHasNoContents, True)
        self.piece = piece
        self.square = square
        self.variants = variants
        self.frames = variants["frames"]
        self.phase = random.uniform(0, math.tau)
        self.bob_amp = 2.2
        self.lift = 0.0            # extra height (selection / leaping)
        self.target_lift = 0.0
        self.selected = False
        self.idle = True
        self.squash = 1.0          # landing squash factor
        scale = SQUARE / variants["normal"].width()

        self.shadow = QGraphicsEllipseItem(QRectF(-32, -9, 64, 18), self)
        g = QRadialGradient(0, 0, 32)
        g.setColorAt(0.0, QColor(0, 0, 0, 150))
        g.setColorAt(1.0, QColor(0, 0, 0, 0))
        self.shadow.setBrush(QBrush(g))
        self.shadow.setPen(QPen(Qt.PenStyle.NoPen))
        self.shadow.setPos(SQUARE / 2, SQUARE * 0.88)

        self.aura = AuraItem(self)
        self.aura.color = QColor(*glow_rgb)

        self.sprite = QGraphicsPixmapItem(variants["normal"], self)
        self.sprite.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.sprite.setScale(scale)
        self.sprite.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

        self.frost = QGraphicsPixmapItem(variants["frozen"], self.sprite)
        self.frost.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.frost.setOpacity(0.0)
        self.frost.setVisible(False)
        self.flash = QGraphicsPixmapItem(variants["flash"], self.sprite)
        self.flash.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.flash.setOpacity(0.0)
        self.flash.setVisible(False)
        self._frame = 0

    def boundingRect(self) -> QRectF:
        return QRectF()

    def paint(self, painter, option, widget=None):
        pass

    # ------------------------------------------------------------- state
    def center(self) -> tuple[float, float]:
        p = self.pos()
        return p.x() + SQUARE / 2, p.y() + SQUARE * 0.55 - self.lift

    def set_selected(self, on: bool):
        self.selected = on
        self.target_lift = 12.0 if on else 0.0

    def set_frozen(self, amount: float):
        self.frost.setVisible(amount > 0.01)
        self.frost.setOpacity(amount)

    def set_flash(self, amount: float):
        self.flash.setVisible(amount > 0.01)
        self.flash.setOpacity(amount)

    def tick(self, t: float, dt: float, animate: bool = True):
        self.lift += (self.target_lift - self.lift) * min(1.0, dt * 12)
        bob = math.sin(t * 2.1 + self.phase) * self.bob_amp if (animate and self.idle) else 0.0
        if self.selected:
            bob *= 1.8
        h = self.lift + bob + 2.0
        self.sprite.setPos(0, -h)
        if self.squash != 1.0:
            self.squash += (1.0 - self.squash) * min(1.0, dt * 10)
            if abs(self.squash - 1.0) < 0.01:
                self.squash = 1.0
        s = max(0.55, 1.0 - h / 90.0)
        self.shadow.setScale(s)
        self.shadow.setOpacity(max(0.35, 1.0 - h / 80.0))
        target_aura = 1.0 if self.selected else 0.0
        self.aura.strength += (target_aura - self.aura.strength) * min(1.0, dt * 8)
        if self.aura.strength > 0.01:
            self.aura.phase = t
            self.aura.setPos(0, -h * 0.3)
            self.aura.update()
        if len(self.frames) > 1:
            f = int(t * 8) % len(self.frames)
            if f != self._frame:
                self._frame = f
                self.sprite.setPixmap(self.frames[f])
