"""The battlefield: QGraphicsScene + QGraphicsView with camera, effects and input."""
from __future__ import annotations

import math
import random
import time

import chess
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath,
                         QPen, QPixmap, QRadialGradient, QTransform)
from PyQt6.QtWidgets import (QGraphicsItem, QGraphicsObject, QGraphicsScene, QGraphicsView)

from animations import capture as capture_anim
from animations import cinematics, movement
from animations.animator import Animator, Tween, ease_in_out
from effects.particles import ParticleSystem
from game import rules

from .environments import (BOARD, FRAME, BoardItem, BrazierItem, CoordItem, FogLayer, RuneRingItem,
                           ambient_spawner, flame_spawner, render_background)
from .piece_graphics import PieceItem, PieceRenderer
from .theme import ARMY_STYLES, DEFAULT_ENV, DEFAULT_STYLE, ENVIRONMENTS, TITLE_FONT

SQ = 100.0
CENTER = (BOARD / 2, BOARD / 2)


# ====================================================================== camera
class Camera:
    def __init__(self, world: QGraphicsItem):
        self.world = world
        self.zoom = 1.0
        self.fx, self.fy = CENTER
        self.enabled = True
        self.floating = True
        self._tw = None   # (from, to, duration, elapsed)
        self.shake_amp = 0.0
        self.shake_left = 0.0
        self.shake_total = 1.0
        self.t = 0.0

    def focus(self, point, zoom=1.1, duration=0.4):
        if not self.enabled:
            return
        self._tw = ((self.fx, self.fy, self.zoom), (point[0], point[1], zoom), duration, 0.0)

    def reset(self, duration=0.4):
        self._tw = ((self.fx, self.fy, self.zoom), (CENTER[0], CENTER[1], 1.0), max(0.01, duration), 0.0)

    def snap_reset(self):
        self._tw = None
        self.fx, self.fy = CENTER
        self.zoom = 1.0

    def shake(self, amount, duration=0.25):
        if not self.enabled:
            return
        if amount >= self.shake_amp * (self.shake_left / max(self.shake_total, 0.01)):
            self.shake_amp = amount
            self.shake_left = self.shake_total = duration

    def tick(self, dt):
        self.t += dt
        if self._tw:
            a, b, dur, el = self._tw
            el += dt
            k = ease_in_out(min(1.0, el / dur))
            self.fx = a[0] + (b[0] - a[0]) * k
            self.fy = a[1] + (b[1] - a[1]) * k
            self.zoom = a[2] + (b[2] - a[2]) * k
            self._tw = None if el >= dur else (a, b, dur, el)
        sx = sy = 0.0
        if self.shake_left > 0:
            self.shake_left -= dt
            amp = self.shake_amp * max(0.0, self.shake_left / self.shake_total)
            sx, sy = random.uniform(-amp, amp), random.uniform(-amp, amp)
        fl = math.sin(self.t * 0.9) * 3.0 if self.floating else 0.0
        t = QTransform()
        t.translate(CENTER[0] + sx, CENTER[1] + sy + fl)
        t.scale(self.zoom, self.zoom)
        t.translate(-self.fx, -self.fy)
        self.world.setTransform(t)


# ================================================================= world items
class WorldItem(QGraphicsObject):
    def __init__(self):
        super().__init__()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemHasNoContents, True)

    def boundingRect(self) -> QRectF:
        return QRectF()

    def paint(self, *args):
        pass


class Overlay(QGraphicsObject):
    """Darkens the battlefield for cinematics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.level = 0.0
        self.setZValue(80)

    def set_level(self, v):
        self.level = max(0.0, min(1.0, v))
        self.setVisible(self.level > 0.005)
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-3000, -3000, 7000, 7000)

    def paint(self, painter, option, widget=None):
        painter.fillRect(self.boundingRect(), QColor(5, 2, 12, int(255 * self.level)))


class ScreenFlash(QGraphicsObject):
    def __init__(self):
        super().__init__()
        self.color = QColor(255, 255, 255)
        self.level = 0.0
        self.decay = 4.0
        self.setZValue(300)
        self.setVisible(False)

    def flash(self, rgb, strength, duration):
        self.color = QColor(*rgb)
        self.level = max(self.level, strength)
        self.decay = strength / max(0.05, duration)
        self.setVisible(True)

    def tick(self, dt):
        if self.level > 0:
            self.level = max(0.0, self.level - self.decay * dt)
            self.setVisible(self.level > 0.003)
            self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-3000, -3000, 7000, 7000)

    def paint(self, painter, option, widget=None):
        c = QColor(self.color)
        c.setAlphaF(min(1.0, self.level))
        painter.fillRect(self.boundingRect(), c)


class Banner(QGraphicsObject):
    """Big animated title text (CHECK!, CHECKMATE, VICTORY...)."""

    def __init__(self):
        super().__init__()
        self.setZValue(250)
        self.title = ""
        self.subtitle = ""
        self.color = (255, 220, 120)
        self.size = 90
        self.age = 0.0
        self.hold = None
        self.setVisible(False)
        self.setPos(BOARD / 2, BOARD / 2 - 20)

    def show(self, title, subtitle="", color=(255, 220, 120), hold=1.0, size=90):
        self.title, self.subtitle, self.color, self.size = title, subtitle, color, size
        self.hold = hold
        self.age = 0.0
        self.setVisible(True)
        self.update()

    def hide_now(self):
        self.setVisible(False)
        self.title = ""

    def tick(self, dt):
        if not self.isVisible():
            return
        self.age += dt
        if self.hold is not None and self.age > self.hold + 0.5:
            self.setVisible(False)
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-700, -200, 1400, 400)

    def paint(self, painter: QPainter, option, widget=None):
        if not self.title:
            return
        a = min(1.0, self.age / 0.25)
        if self.hold is not None and self.age > self.hold:
            a = max(0.0, 1.0 - (self.age - self.hold) / 0.5)
        t = min(1.0, self.age / 0.45)
        s = 1.0 + 0.6 * (1 - t) ** 3 - 0.08 * math.sin(min(1.0, t) * math.pi)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(a)
        painter.scale(s, s)
        font = QFont(TITLE_FONT)
        font.setPixelSize(int(self.size))
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
        path = QPainterPath()
        path.addText(0, 0, font, self.title)
        br = path.boundingRect()
        path.translate(-br.center().x(), -br.center().y())
        r, g, b = self.color
        # dark plate
        plate = QRectF(-br.width() / 2 - 60, -br.height() / 2 - 26, br.width() + 120,
                       br.height() + (90 if self.subtitle else 52))
        pg = QLinearGradient(plate.left(), 0, plate.right(), 0)
        pg.setColorAt(0, QColor(0, 0, 0, 0))
        pg.setColorAt(0.2, QColor(8, 4, 16, 190))
        pg.setColorAt(0.8, QColor(8, 4, 16, 190))
        pg.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(plate, QBrush(pg))
        for w, al in ((26, 30), (16, 50), (8, 90)):
            painter.setPen(QPen(QColor(r, g, b, al), w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                                Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
        fill = QLinearGradient(0, br.top() - br.center().y(), 0, br.bottom() - br.center().y())
        fill.setColorAt(0, QColor(255, 255, 255))
        fill.setColorAt(0.55, QColor(r, g, b))
        fill.setColorAt(1, QColor(int(r * 0.5), int(g * 0.5), int(b * 0.5)))
        painter.setPen(QPen(QColor(20, 10, 5, 230), 3))
        painter.setBrush(QBrush(fill))
        painter.drawPath(path)
        if self.subtitle:
            f2 = QFont(TITLE_FONT)
            f2.setPixelSize(int(self.size * 0.3))
            f2.setBold(True)
            painter.setFont(f2)
            painter.setPen(QColor(240, 232, 255))
            painter.drawText(QRectF(-600, br.height() / 2 - 4, 1200, self.size * 0.5),
                             Qt.AlignmentFlag.AlignCenter, self.subtitle)


class HighlightLayer(QGraphicsObject):
    """Everything drawn on the squares: last move, selection, legal moves, hints..."""

    def __init__(self, scene: "ChessScene", parent=None):
        super().__init__(parent)
        self.cs = scene
        self.t = 0.0
        self.setZValue(5)

    def boundingRect(self) -> QRectF:
        return QRectF(-20, -20, BOARD + 40, BOARD + 40)

    def _rect(self, sq) -> QRectF:
        x, y = self.cs.square_xy(sq)
        return QRectF(x, y, SQ, SQ)

    def paint(self, painter: QPainter, option, widget=None):
        cs = self.cs
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pulse = 0.5 + 0.5 * math.sin(self.t * 4)

        if cs.last_move and cs.show_last_move:
            for sq in (cs.last_move.from_square, cs.last_move.to_square):
                r = self._rect(sq)
                painter.fillRect(r, QColor(255, 214, 90, 62))
                painter.setPen(QPen(QColor(255, 214, 90, 120), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(r.adjusted(1, 1, -1, -1))

        for sq, rgb in cs.square_marks.items():
            r = self._rect(sq)
            g = QRadialGradient(r.center(), SQ * 0.7)
            g.setColorAt(0, QColor(*rgb, 120))
            g.setColorAt(1, QColor(*rgb, 20))
            painter.fillRect(r, QBrush(g))

        if cs.check_square is not None:
            r = self._rect(cs.check_square)
            g = QRadialGradient(r.center(), SQ * 0.75)
            g.setColorAt(0, QColor(255, 40, 40, int(170 + 80 * pulse)))
            g.setColorAt(0.6, QColor(200, 0, 30, int(90 + 50 * pulse)))
            g.setColorAt(1, QColor(120, 0, 0, 0))
            painter.fillRect(r.adjusted(-12, -12, 12, 12), QBrush(g))

        if cs.selected is not None:
            r = self._rect(cs.selected)
            painter.fillRect(r, QColor(255, 225, 130, 70))
            painter.setPen(QPen(QColor(255, 225, 130, 230), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r.adjusted(2, 2, -2, -2))

        for sq in cs.targets:
            r = self._rect(sq)
            c = r.center()
            g = QRadialGradient(c, SQ * 0.55)
            g.setColorAt(0, QColor(255, 230, 140, int(150 + 80 * pulse)))
            g.setColorAt(1, QColor(255, 200, 80, 0))
            painter.fillRect(r, QBrush(g))
            painter.setPen(QPen(QColor(255, 240, 180, 230), 2.5))
            painter.drawEllipse(c, 18 + 6 * pulse, 18 + 6 * pulse)

        if cs.show_legal and cs.selected is not None:
            pal = cs.style.palette(cs.board.color_at(cs.selected) if cs.board.color_at(cs.selected) is not None else True)
            for sq, is_cap in cs.legal_targets.items():
                r = self._rect(sq)
                c = r.center()
                hover = sq == cs.hover_square
                if is_cap:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor(255, 80, 60, 70), 14))
                    painter.drawEllipse(c, 40, 40)
                    painter.setPen(QPen(QColor(255, 120, 80, int(170 + 70 * pulse)), 4))
                    painter.drawEllipse(c, 42, 42)
                else:
                    g = QRadialGradient(c, 22)
                    g.setColorAt(0, QColor(*pal.core, 255))
                    g.setColorAt(0.35, QColor(*pal.main, 220))
                    g.setColorAt(1, QColor(*pal.main, 0))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(g))
                    rad = 20 + 3 * pulse
                    painter.drawEllipse(c, rad, rad)
                if hover:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor(255, 255, 255, 200), 3))
                    painter.drawRect(r.adjusted(3, 3, -3, -3))

        for sq, rgb in cs.threat_marks.items():
            r = self._rect(sq)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(*rgb, int(120 + 110 * pulse)), 4, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(r.adjusted(5, 5, -5, -5), 12, 12)

        for (a, b), rgb in cs.arrows.items():
            self._arrow(painter, a, b, rgb, 150)
        if cs.hint_move is not None:
            self._arrow(painter, cs.hint_move.from_square, cs.hint_move.to_square, (90, 210, 255),
                        int(150 + 90 * pulse), glow=True)
        for sq in cs.circles:
            r = self._rect(sq)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(90, 220, 120, 210), 5))
            painter.drawEllipse(r.center(), 43, 43)
        if cs.drawing_arrow is not None and cs.hover_square is not None and cs.hover_square != cs.drawing_arrow:
            self._arrow(painter, cs.drawing_arrow, cs.hover_square, (255, 170, 60), 110)

    def _arrow(self, painter, a, b, rgb, alpha, glow=False):
        ra, rb = self._rect(a), self._rect(b)
        p1, p2 = ra.center(), rb.center()
        dx, dy = p2.x() - p1.x(), p2.y() - p1.y()
        d = math.hypot(dx, dy) or 1.0
        ux, uy = dx / d, dy / d
        start = QPointF(p1.x() + ux * 22, p1.y() + uy * 22)
        tip = QPointF(p2.x() - ux * 8, p2.y() - uy * 8)
        base = QPointF(tip.x() - ux * 34, tip.y() - uy * 34)
        if glow:
            painter.setPen(QPen(QColor(*rgb, 60), 30, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(start, base)
        painter.setPen(QPen(QColor(*rgb, alpha), 15, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(start, base)
        nx, ny = -uy, ux
        head = [tip, QPointF(base.x() + nx * 24, base.y() + ny * 24), QPointF(base.x() - nx * 24, base.y() - ny * 24)]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(*rgb, alpha))
        painter.drawPolygon(head)


# ====================================================================== scene
class ChessScene(QGraphicsScene):
    move_requested = pyqtSignal(object)      # chess.Move
    piece_selected = pyqtSignal(int)         # square
    illegal_attempt = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.renderer = PieceRenderer()
        self.env = ENVIRONMENTS[DEFAULT_ENV]
        self.style = ARMY_STYLES[DEFAULT_STYLE]
        self.board = chess.Board()
        self.flipped = False
        self.interactive = True
        self.human_colors = {chess.WHITE, chess.BLACK}
        self.anim_mode = "full"          # full | quick | off
        self.show_legal = True
        self.show_last_move = True
        self.learning_tooltips = False
        self.promotion_handler = None    # callable(color) -> piece type | None
        self.sound_cb = None

        self.items_by_sq: dict[int, PieceItem] = {}
        self.selected: int | None = None
        self.legal_targets: dict[int, bool] = {}
        self.last_move: chess.Move | None = None
        self.check_square: int | None = None
        self.hint_move: chess.Move | None = None
        self.targets: list[int] = []
        self.threat_marks: dict[int, tuple] = {}
        self.square_marks: dict[int, tuple] = {}
        self.arrows: dict[tuple, tuple] = {}
        self.circles: set[int] = set()
        self.hover_square: int | None = None
        self.drawing_arrow: int | None = None
        self._press_world = None
        self._dragging = False
        self._drag_item: PieceItem | None = None
        self._check_circle = None
        self._dropped_move = None

        self.setSceneRect(QRectF(-FRAME - 40, -FRAME - 90, BOARD + 2 * FRAME + 80, BOARD + 2 * FRAME + 130))
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)

        self.world = WorldItem()
        self.addItem(self.world)
        area = QRectF(-FRAME - 150, -FRAME - 150, BOARD + 2 * FRAME + 300, BOARD + 2 * FRAME + 300)
        self.fog_back = FogLayer(self.env, area, 1.0, 7, self.world)
        self.fog_back.setZValue(-10)
        self.board_item = BoardItem(self.env, self.world)
        self.board_item.setZValue(0)
        self.runes = RuneRingItem(self.env, self.world)
        self.runes.setZValue(2)
        self.rune_ring = self.runes
        self.coords = CoordItem(self.env, self.world)
        self.coords.setZValue(4)
        self.highlights = HighlightLayer(self, self.world)
        self.braziers = []
        for x, y in ((-FRAME / 2, -FRAME / 2), (BOARD + FRAME / 2, -FRAME / 2),
                     (-FRAME / 2, BOARD + FRAME / 2), (BOARD + FRAME / 2, BOARD + FRAME / 2)):
            b = BrazierItem((x, y), self.env.torch, self.world)
            b.setZValue(3)
            self.braziers.append(b)
        self.particles = ParticleSystem(area.adjusted(-500, -900, 500, 500), self.world)
        self.particles.setZValue(100)
        self.ambient = ParticleSystem(area, self.world)
        self.ambient.setZValue(70)
        self.fog_front = FogLayer(self.env, area, 0.35, 4, self.world)
        self.fog_front.setZValue(72)
        self.overlay = Overlay(self.world)
        self.overlay.set_level(0)
        self.flash = ScreenFlash()
        self.addItem(self.flash)
        self.banner = Banner()
        self.addItem(self.banner)

        self.camera = Camera(self.world)
        self.animator = Animator()
        self.ambient_on = True
        self._ambient_emitters = []
        self._start_ambient()

        self._last = time.perf_counter()
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)
        self.set_position(chess.Board())

    # ---------------------------------------------------------- appearance
    def set_environment(self, key: str):
        self.env = ENVIRONMENTS.get(key, self.env)
        self.board_item.set_env(self.env)
        self.runes.env = self.env
        self.coords.env = self.env
        self.coords.update()
        self.fog_back.set_env(self.env)
        self.fog_front.set_env(self.env)
        for b in self.braziers:
            b.palette = self.env.torch
        self._start_ambient()
        for v in self.views():
            if hasattr(v, "refresh_background"):
                v.refresh_background()

    def set_style(self, key: str):
        self.style = ARMY_STYLES.get(key, self.style)
        self.set_position(self.board, self.last_move)

    def set_ambient(self, on: bool):
        self.ambient_on = on
        self.camera.floating = on
        self._start_ambient()

    def _start_ambient(self):
        for em in self._ambient_emitters:
            em.stop()
        self._ambient_emitters = []
        self.ambient.clear(keep_emitters=False)
        self.fog_back.setVisible(self.ambient_on)
        self.fog_front.setVisible(self.ambient_on)
        for b in self.braziers:
            self._ambient_emitters.append(
                self.ambient.add_emitter(flame_spawner(self.env.torch), 34 if self.ambient_on else 14,
                                         None, (b.pos().x(), b.pos().y() - 4)))
        if self.ambient_on:
            area = QRectF(-FRAME - 100, -FRAME - 60, BOARD + 2 * FRAME + 200, BOARD + 2 * FRAME + 120)
            rate = {"embers": 5, "ash": 7, "fireflies": 3, "runes": 3, "stars": 4}.get(self.env.ambient, 4)
            self._ambient_emitters.append(self.ambient.add_emitter(ambient_spawner(self.env, area), rate))

    def set_flipped(self, flipped: bool):
        if flipped == self.flipped:
            return
        self.flipped = flipped
        self.coords.flipped = flipped
        self.coords.update()
        self.set_position(self.board, self.last_move)

    def set_learning_tooltips(self, on: bool):
        self.learning_tooltips = on
        for item in self.items_by_sq.values():
            self._apply_tooltip(item)

    def _apply_tooltip(self, item: PieceItem):
        if not self.learning_tooltips:
            item.setToolTip("")
            return
        pt = item.piece.piece_type
        side = self.style.army(item.piece.color)
        value = rules.PIECE_VALUES[pt]
        item.setToolTip(f"<b>{rules.PIECE_NAMES[pt]}</b> - {rules.PIECE_TITLES[pt]} of the {side}<br>"
                        f"It {rules.PIECE_MOVES_HELP[pt]}<br>"
                        + (f"Value: {value}" if value else "Value: the whole game!"))

    # ---------------------------------------------------------- geometry
    def square_xy(self, sq: int) -> tuple[float, float]:
        f, r = chess.square_file(sq), chess.square_rank(sq)
        if self.flipped:
            return (7 - f) * SQ, r * SQ
        return f * SQ, (7 - r) * SQ

    def square_center(self, sq: int) -> tuple[float, float]:
        x, y = self.square_xy(sq)
        return x + SQ / 2, y + SQ / 2

    def square_at_world(self, x: float, y: float) -> int | None:
        if not (0 <= x < BOARD and 0 <= y < BOARD):
            return None
        col, row = int(x // SQ), int(y // SQ)
        if self.flipped:
            return chess.square(7 - col, row)
        return chess.square(col, 7 - row)

    def to_world(self, scene_pos: QPointF) -> QPointF:
        return self.world.mapFromScene(scene_pos)

    # ---------------------------------------------------------- pieces
    def piece_items(self) -> list[PieceItem]:
        return list(self.items_by_sq.values())

    def _make_item(self, piece: chess.Piece, sq: int) -> PieceItem:
        variants = self.renderer.variants(piece.piece_type, piece.color, self.style)
        item = PieceItem(piece, sq, variants, self.style.material(piece.color).glow, self.world)
        x, y = self.square_xy(sq)
        item.setPos(x, y)
        item.setZValue(movement.piece_z(y))
        self._apply_tooltip(item)
        return item

    def retexture(self, item: PieceItem, piece: chess.Piece):
        item.piece = piece
        v = self.renderer.variants(piece.piece_type, piece.color, self.style)
        item.variants = v
        item.frames = v["frames"]
        item.sprite.setPixmap(v["normal"])
        item.frost.setPixmap(v["frozen"])
        item.flash.setPixmap(v["flash"])
        self._apply_tooltip(item)

    def remove_item(self, item: PieceItem):
        for sq, it in list(self.items_by_sq.items()):
            if it is item:
                del self.items_by_sq[sq]
        if item.scene() is self:
            self.removeItem(item)

    def set_position(self, board: chess.Board, last_move: chess.Move | None = None, keep: bool = False):
        """Show ``board`` immediately (no animation)."""
        self.board = board.copy()
        self.last_move = last_move
        if not keep:
            for item in list(self.items_by_sq.values()):
                if item.scene() is self:
                    self.removeItem(item)
            self.items_by_sq = {}
        # remove stray items that are not tracked anymore
        tracked = set(map(id, self.items_by_sq.values()))
        for it in list(self.world.childItems()):
            if isinstance(it, PieceItem) and id(it) not in tracked:
                self.removeItem(it)
        pmap = self.board.piece_map()
        for sq, item in list(self.items_by_sq.items()):
            if pmap.get(sq) != item.piece:
                self.removeItem(item)
                del self.items_by_sq[sq]
        for sq, piece in pmap.items():
            item = self.items_by_sq.get(sq)
            if item is None:
                self.items_by_sq[sq] = self._make_item(piece, sq)
            else:
                x, y = self.square_xy(sq)
                item.setPos(x, y)
                item.square = sq
                item.setZValue(movement.piece_z(y))
                item.lift = item.target_lift = 0
                item.idle = True
                item.sprite.setOpacity(1.0)
                item.set_flash(0)
        self.clear_selection()
        self._update_check_square()

    def _update_check_square(self):
        self.check_square = self.board.king(self.board.turn) if self.board.is_check() else None

    def reset_effects(self):
        """Clear cinematics: overlay, banners, frost, persistent circles."""
        self.animator.cancel_all()
        self.particles.clear(keep_emitters=False)
        self.overlay.set_level(0)
        self.banner.hide_now()
        self.camera.snap_reset()
        self._check_circle = None
        for it in self.items_by_sq.values():
            it.set_frozen(0)
            it.set_flash(0)
            it.idle = True

    # ---------------------------------------------------------- moves
    @property
    def busy(self) -> bool:
        return self.animator.busy

    def play_move(self, record, board_after: chess.Board, on_done=None):
        """Animate a move (record from GameState) and end on ``board_after``."""
        self.clear_selection()
        self.hint_move = None
        self.threat_marks = {}
        if self._check_circle is not None:
            self._check_circle.dismiss()
            self._check_circle = None
        self.check_square = None
        dropped = self._dropped_move == record.move
        self._dropped_move = None

        def finish():
            self.set_position(board_after, record.move, keep=True)
            if board_after.is_check() and not board_after.is_checkmate():
                king = self.items_by_sq.get(board_after.king(board_after.turn))
                if king is not None and self.anim_mode != "off":
                    self._check_circle = cinematics.check_warning(self, king)
                else:
                    self.sound("check")
            if on_done:
                on_done()

        if self.anim_mode == "off":
            self.set_position(board_after, record.move, keep=False)
            self.sound("capture" if record.captured else ("castle" if record.castle_rook else "move"))
            QTimer.singleShot(0, finish)
            return
        self.animator.run(self._move_script(record, dropped or self.anim_mode == "quick"), on_done=finish)

    def _move_script(self, record, quick):
        move = record.move
        mover = self.items_by_sq.pop(move.from_square, None)
        if mover is None:
            return
        color = record.color
        to_xy = self.square_xy(move.to_square)
        victim = None
        rook = None
        if record.captured_sq is not None:
            victim = self.items_by_sq.pop(record.captured_sq, None)
        if record.castle_rook:
            rf, rt = record.castle_rook
            rook = self.items_by_sq.pop(rf, None)
            if rook is not None:
                self.items_by_sq[rt] = rook
                rook.square = rt
        self.items_by_sq[move.to_square] = mover
        mover.square = move.to_square
        mover.set_selected(False)

        if rook is not None:
            yield from movement.castle(self, mover, rook, to_xy, self.square_xy(record.castle_rook[1]), color, quick)
        elif victim is not None:
            yield from capture_anim.capture(self, mover, victim, to_xy, record.piece_type, color, quick)
        else:
            yield from movement.move_item(self, mover, to_xy, record.piece_type, color, quick)
        if record.promotion:
            if quick:
                self.retexture(mover, chess.Piece(record.promotion, color))
                self.sound("promote")
            else:
                yield from cinematics.promotion(self, mover, chess.Piece(record.promotion, color))

    def play_script(self, gen, on_done=None):
        return self.animator.run(gen, on_done)

    # ---------------------------------------------------------- highlights API
    def clear_selection(self):
        if self.selected is not None:
            item = self.items_by_sq.get(self.selected)
            if item:
                item.set_selected(False)
        self.selected = None
        self.legal_targets = {}

    def show_hint(self, move: chess.Move | None):
        self.hint_move = move
        if move is not None:
            item = self.items_by_sq.get(move.from_square)
            if item:
                pal = self.style.palette(item.piece.color)
                from effects.magic import sparkle
                x, y = item.center()
                sparkle(self.particles, (x, y), pal, 1.0, 40)

    def clear_marks(self):
        self.arrows.clear()
        self.circles.clear()

    def flash_screen(self, rgb, strength=0.3, duration=0.2):
        if self.camera.enabled:
            self.flash.flash(rgb, strength, duration)

    def sound(self, name: str):
        if self.sound_cb:
            self.sound_cb(name)

    # ---------------------------------------------------------- input
    def can_move(self, sq: int) -> bool:
        piece = self.board.piece_at(sq)
        return (self.interactive and not self.busy and piece is not None and piece.color == self.board.turn
                and piece.color in self.human_colors)

    def _select(self, sq: int):
        self.clear_selection()
        self.selected = sq
        item = self.items_by_sq.get(sq)
        if item:
            item.set_selected(True)
        self.legal_targets = {}
        for m in self.board.legal_moves:
            if m.from_square == sq:
                self.legal_targets[m.to_square] = self.board.is_capture(m)
        # allow "king takes own rook" style castling clicks
        for m in self.board.legal_moves:
            if m.from_square == sq and self.board.is_castling(m):
                rook_sq = rules.castling_rook_squares(self.board, m)[0]
                self.legal_targets.setdefault(rook_sq, False)
        self.sound("select")
        self.piece_selected.emit(sq)

    def _find_move(self, frm: int, to: int) -> chess.Move | None:
        candidates = [m for m in self.board.legal_moves if m.from_square == frm and m.to_square == to]
        if not candidates:
            for m in self.board.legal_moves:
                if m.from_square == frm and self.board.is_castling(m):
                    if rules.castling_rook_squares(self.board, m)[0] == to:
                        return m
            return None
        if len(candidates) == 1:
            return candidates[0]
        # promotion choice
        color = self.board.turn
        choice = self.promotion_handler(color) if self.promotion_handler else chess.QUEEN
        if not choice:
            return None
        for m in candidates:
            if m.promotion == choice:
                return m
        return candidates[0]

    def _try_move(self, frm: int, to: int, dropped: bool = False) -> bool:
        move = self._find_move(frm, to)
        if move is None:
            return False
        if dropped:
            self._dropped_move = move
        self.move_requested.emit(move)
        return True

    def mousePressEvent(self, event):
        wp = self.to_world(event.scenePos())
        sq = self.square_at_world(wp.x(), wp.y())
        if event.button() == Qt.MouseButton.RightButton:
            self.drawing_arrow = sq
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.clear_marks()
        if sq is None:
            self.clear_selection()
            return
        if self.selected is not None and sq in self.legal_targets and sq != self.selected:
            if self._try_move(self.selected, sq):
                return
        if self.can_move(sq):
            if self.selected != sq:
                self._select(sq)
            self._press_world = (wp.x(), wp.y())
            self._drag_item = self.items_by_sq.get(sq)
            self._dragging = False
        else:
            if self.board.piece_at(sq) is not None and self.interactive and not self.busy:
                piece = self.board.piece_at(sq)
                if piece.color in self.human_colors and piece.color != self.board.turn:
                    self.illegal_attempt.emit()
            self.clear_selection()
        event.accept()

    def mouseMoveEvent(self, event):
        wp = self.to_world(event.scenePos())
        self.hover_square = self.square_at_world(wp.x(), wp.y())
        if self._press_world and self._drag_item is not None:
            dx = wp.x() - self._press_world[0]
            dy = wp.y() - self._press_world[1]
            if not self._dragging and math.hypot(dx, dy) > 7:
                self._dragging = True
                self._drag_item.setZValue(90)
                self._drag_item.idle = False
            if self._dragging:
                self._drag_item.setPos(wp.x() - SQ / 2, wp.y() - SQ * 0.62)
        for v in self.views():
            if self._dragging:
                v.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            elif self.hover_square is not None and self.can_move(self.hover_square):
                v.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            elif self.hover_square is not None and self.hover_square in self.legal_targets:
                v.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                v.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        event.accept()

    def mouseReleaseEvent(self, event):
        wp = self.to_world(event.scenePos())
        sq = self.square_at_world(wp.x(), wp.y())
        if event.button() == Qt.MouseButton.RightButton:
            start = self.drawing_arrow
            self.drawing_arrow = None
            if start is not None and sq is not None:
                if start == sq:
                    self.circles.symmetric_difference_update({sq})
                else:
                    key = (start, sq)
                    if key in self.arrows:
                        del self.arrows[key]
                    else:
                        self.arrows[key] = (255, 170, 60)
            return
        if self._dragging and self._drag_item is not None:
            item = self._drag_item
            frm = self.selected
            self._dragging = False
            self._drag_item = None
            self._press_world = None
            item.idle = True
            if frm is not None and sq is not None and sq != frm and sq in self.legal_targets:
                if self._try_move(frm, sq, dropped=True):
                    return
            # snap back
            x, y = self.square_xy(frm if frm is not None else item.square)
            sx, sy = item.pos().x(), item.pos().y()
            item.setZValue(movement.piece_z(y))
            self.animator.run(self._snap(item, sx, sy, x, y))
            if sq is not None and sq != frm:
                self.illegal_attempt.emit()
            return
        self._press_world = None
        self._drag_item = None

    def _snap(self, item, sx, sy, x, y):
        yield Tween(0.14, lambda t: item.setPos(sx + (x - sx) * t, sy + (y - sy) * t))

    # ---------------------------------------------------------- shared board-view API
    @property
    def widget(self) -> "ChessView":
        if getattr(self, "_view", None) is None:
            self._view = ChessView(self)
        return self._view

    def set_threats(self, marks: dict):
        self.threat_marks = dict(marks)

    def set_targets(self, squares: list):
        self.targets = list(squares)

    def set_square_marks(self, marks: dict):
        self.square_marks = dict(marks)

    def play_checkmate(self, loser: bool, title: str, subtitle: str, rgb, on_done=None):
        king = self.items_by_sq.get(self.board.king(loser))
        if king is None or self.anim_mode == "off":
            self.banner.show(title, subtitle, rgb, None, 104)
            if on_done:
                on_done()
            return
        self.animator.run(cinematics.checkmate(self, king, loser, title, subtitle, rgb), on_done)

    def play_draw(self, title: str, subtitle: str, on_done=None):
        self.animator.run(cinematics.draw_cinematic(self, title, subtitle), on_done)

    def celebrate(self, color: bool):
        if self.anim_mode != "off":
            self.animator.run(cinematics.victory_flourish(self, color))

    def lesson_success(self, sq: int):
        self.animator.run(cinematics.lesson_success(self, self.square_center(sq)))

    def show_banner(self, title, subtitle="", rgb=(255, 210, 120), hold=1.0, size=90):
        self.banner.show(title, subtitle, rgb, hold, size)

    def hide_banner(self):
        self.banner.hide_now()

    def view_white(self):
        self.set_flipped(False)

    def view_black(self):
        self.set_flipped(True)

    def view_top(self):
        pass

    def view_side(self):
        pass

    def toggle_orbit(self):
        pass

    def set_graphics(self, **kwargs):
        pass

    def pause(self):
        self._timer.stop()

    def resume(self):
        self._last = time.perf_counter()
        self._timer.start(16)

    # ---------------------------------------------------------- loop
    def _tick(self):
        now = time.perf_counter()
        dt = min(0.05, now - self._last)
        self._last = now
        self.animator.step(dt)
        self.camera.tick(dt)
        t = self.camera.t
        for item in list(self.items_by_sq.values()):
            item.tick(t, dt, self.ambient_on)
        for item in self.world.childItems():
            if isinstance(item, PieceItem) and item.square not in self.items_by_sq:
                item.tick(t, dt, False)
        self.particles.step(dt)
        self.ambient.step(dt)
        self.runes.tick(dt)
        for b in self.braziers:
            b.tick(dt)
        if self.ambient_on:
            self.fog_back.tick(dt)
            self.fog_front.tick(dt)
        self.highlights.t = t
        self.highlights.update()
        self.banner.tick(dt)
        self.flash.tick(dt)


# ====================================================================== view
class ChessView(QGraphicsView):
    def __init__(self, scene: ChessScene, parent=None):
        super().__init__(scene, parent)
        self.cs = scene
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontSavePainterState, False)
        self.setMouseTracking(True)
        self.setMinimumSize(420, 420)
        self.setStyleSheet("background: transparent; border: none;")
        self._bg: QPixmap | None = None
        self._bg_timer = QTimer(self)
        self._bg_timer.setSingleShot(True)
        self._bg_timer.timeout.connect(self.refresh_background)

    def refresh_background(self):
        vp = self.viewport()
        self._bg = render_background(self.cs.env, vp.width(), vp.height())
        self.viewport().update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self.cs.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._bg_timer.start(60)

    def showEvent(self, event):
        super().showEvent(event)
        self.fitInView(self.cs.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        if self._bg is None:
            self.refresh_background()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.resetTransform()
        vp = self.viewport().rect()
        if self._bg is not None:
            painter.drawPixmap(vp, self._bg, QRectF(self._bg.rect()).toRect())
        else:
            painter.fillRect(vp, QColor(self.cs.env.bg_bottom))
        painter.restore()

    def contextMenuEvent(self, event):
        event.accept()  # right button is used for arrows
