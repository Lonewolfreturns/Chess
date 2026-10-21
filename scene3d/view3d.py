"""The 3D battlefield widget: Qt Quick 3D stage + Python game bridge.

Board3D exposes the same interface as the 2D ChessScene, so the game
controller can drive either view.
"""
from __future__ import annotations

import math
import os
import random
import sys
import time

import chess
from PyQt6.QtCore import (Q_ARG, Q_RETURN_ARG, QMetaObject, QObject, Qt, QTimer, QUrl, pyqtSignal,
                          pyqtSlot)
from PyQt6.QtGui import QColor, QQuaternion, QVector3D
from PyQt6.QtQuickWidgets import QQuickWidget

from animations.animator import Animator, Tween, ease_in_out, ease_out
from game import rules

from . import choreo3d, textures
from .geometry import GeometryLibrary, MeshGeometry
from .locations import ARMIES_3D, DEFAULT_ARMY, DEFAULT_LOCATION, LOCATIONS
from .meshes import tube

PIECE_SCALE = 1.12


def qml_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "scene3d", "qml", name)


def _url(path: str) -> str:
    return QUrl.fromLocalFile(path).toString()


def sq_xz(sq: int) -> tuple[float, float]:
    return chess.square_file(sq) - 3.5, 3.5 - chess.square_rank(sq)


def xz_sq(x: float, z: float) -> int | None:
    f, r = math.floor(x + 4), math.floor(4 - z)
    if 0 <= f < 8 and 0 <= r < 8:
        return chess.square(f, r)
    return None


def facing_yaw(color: bool) -> float:
    return 0.0 if color == chess.WHITE else 180.0


def yaw_towards(dx: float, dz: float) -> float:
    return math.degrees(math.atan2(-dx, -dz))


def shortest(a: float, b: float) -> float:
    """Target angle equivalent to b that is closest to a."""
    d = (b - a + 180) % 360 - 180
    return a + d


# ====================================================================== pieces
class Piece3D:
    def __init__(self, obj: QObject, piece: chess.Piece, square: int):
        self.obj = obj
        self.piece = piece
        self.square = square
        self.x = self.y = self.z = 0.0
        self.yaw = facing_yaw(piece.color)
        self.lift = 0.0
        self.target_lift = 0.0
        self._props: dict = {}

    def set(self, name: str, value):
        if self._props.get(name) == value:
            return
        self._props[name] = value
        try:
            self.obj.setProperty(name, value)
        except RuntimeError:
            pass

    def set_pos(self, x: float, y: float, z: float):
        self.x, self.y, self.z = x, y, z
        self.set("position", QVector3D(x, y, z))

    def set_yaw(self, yaw: float):
        self.yaw = yaw
        self.set("eulerRotation", QVector3D(0, yaw, 0))

    def center(self, h: float = 0.45) -> tuple[float, float, float]:
        return self.x, self.y + (self.lift + h) * PIECE_SCALE, self.z

    def local(self, ox: float, oy: float, oz: float) -> tuple[float, float, float]:
        """Point in the piece's local frame (facing -Z) -> world."""
        a = math.radians(self.yaw)
        c, s = math.cos(a), math.sin(a)
        ox, oy, oz = ox * PIECE_SCALE, oy * PIECE_SCALE, oz * PIECE_SCALE
        return self.x + c * ox + s * oz, self.y + oy + self.lift * PIECE_SCALE, self.z - s * ox + c * oz

    @property
    def is_alive(self) -> bool:
        try:
            self.obj.objectName()
            return True
        except RuntimeError:
            return False


# ====================================================================== camera
class CameraRig:
    def __init__(self, view: "Board3D"):
        self.view = view
        self.enabled = True
        self._tw = None
        self._home = None
        self.shake_amp = 0.0
        self.shake_left = 0.0
        self.shake_total = 1.0
        self.auto_orbit = False

    def _get(self) -> dict:
        r = self.view.root
        t = r.property("target")
        return {"yaw": float(r.property("yaw")), "pitch": float(r.property("pitch")),
                "distance": float(r.property("distance")), "target": (t.x(), t.y(), t.z())}

    def go(self, yaw=None, pitch=None, distance=None, target=None, duration=0.9):
        cur = self._get()
        goal = dict(cur)
        if yaw is not None:
            goal["yaw"] = shortest(cur["yaw"], yaw)
        if pitch is not None:
            goal["pitch"] = pitch
        if distance is not None:
            goal["distance"] = distance
        if target is not None:
            goal["target"] = tuple(target)
        self._tw = (cur, goal, max(0.01, duration), 0.0)

    def focus(self, point, distance=9.0, duration=0.45, pitch=None):
        if not self.enabled:
            return
        if self._home is None:
            self._home = self._get()
        self.go(target=(point[0], max(0.2, point[1] * 0.6), point[2]), distance=distance, pitch=pitch,
                duration=duration)

    def restore(self, duration=0.6):
        if self._home is not None:
            h = self._home
            self._home = None
            self.go(h["yaw"], h["pitch"], h["distance"], h["target"], duration)

    def shake(self, amount: float, duration: float = 0.25):
        if not self.enabled:
            return
        amount *= 0.012
        if amount >= self.shake_amp * (self.shake_left / max(0.01, self.shake_total)):
            self.shake_amp, self.shake_left, self.shake_total = amount, duration, duration

    def tick(self, dt: float):
        r = self.view.root
        if self._tw:
            a, b, dur, el = self._tw
            el += dt
            k = ease_in_out(min(1.0, el / dur))
            r.setProperty("yaw", a["yaw"] + (b["yaw"] - a["yaw"]) * k)
            r.setProperty("pitch", a["pitch"] + (b["pitch"] - a["pitch"]) * k)
            r.setProperty("distance", a["distance"] + (b["distance"] - a["distance"]) * k)
            ta, tb = a["target"], b["target"]
            r.setProperty("target", QVector3D(*(ta[i] + (tb[i] - ta[i]) * k for i in range(3))))
            self._tw = None if el >= dur else (a, b, dur, el)
        elif self.auto_orbit:
            r.setProperty("yaw", float(r.property("yaw")) + dt * 6.0)
        if self.shake_left > 0:
            self.shake_left -= dt
            amp = self.shake_amp * max(0.0, self.shake_left / self.shake_total)
            r.setProperty("shake", QVector3D(random.uniform(-amp, amp), random.uniform(-amp, amp),
                                             random.uniform(-amp, amp)))
            if self.shake_left <= 0:
                r.setProperty("shake", QVector3D(0, 0, 0))


# ====================================================================== bridge
class Bridge(QObject):
    fx = pyqtSignal(str, list)

    def __init__(self, view: "Board3D"):
        super().__init__()
        self.view = view

    @pyqtSlot(float, float, int, result=bool)
    def pressAt(self, x, z, sq):
        return self.view._press(x, z, sq)

    @pyqtSlot(float, float)
    def dragTo(self, x, z):
        self.view._drag(x, z)

    @pyqtSlot(float, float, int)
    def releaseAt(self, x, z, sq):
        self.view._release(x, z, sq)

    @pyqtSlot(float, float, int)
    def hoverAt(self, x, z, sq):
        self.view._hover(x, z, sq)

    @pyqtSlot(float, float, int)
    def rightPress(self, x, z, sq):
        self.view._right_press(x, z, sq)

    @pyqtSlot(float, float, int)
    def rightRelease(self, x, z, sq):
        self.view._right_release(x, z, sq)

    @pyqtSlot()
    def cameraMoved(self):
        self.view.camera.auto_orbit = False


# ====================================================================== view
class Board3D(QObject):
    move_requested = pyqtSignal(object)
    piece_selected = pyqtSignal(int)
    illegal_attempt = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lib = GeometryLibrary()
        self.bridge = Bridge(self)
        self.widget = QQuickWidget()
        self.widget.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.widget.setClearColor(QColor("#05030a"))
        self.widget.setMinimumSize(480, 400)
        self.widget.rootContext().setContextProperty("bridge", self.bridge)
        self.widget.setSource(QUrl.fromLocalFile(qml_path("Battlefield.qml")))
        errors = self.widget.errors()
        if errors or self.widget.rootObject() is None:
            raise RuntimeError("3D scene failed: " + "; ".join(e.toString() for e in errors))
        self.root = self.widget.rootObject()
        self._piece_url = _url(qml_path("Piece3D.qml"))
        self._marker_url = _url(qml_path("Marker3D.qml"))
        self._fx_url = _url(qml_path("Fx3D.qml"))
        self._keeper_url = _url(qml_path("Keeper3D.qml"))
        self._kept: dict[int, object] = {}
        self.tex = {k: _url(textures.marker_texture(k)) for k in ("dot", "ring", "square", "target", "arrow")}
        self.tex["circle"] = _url(textures.magic_circle_texture())
        for k in ("glow", "smoke", "star", "snow"):
            self.root.setProperty("tex" + k.capitalize(), _url(textures.sprite(k)))

        # state mirrored from the 2D scene API
        self.board = chess.Board()
        self.flipped = False
        self.interactive = True
        self.human_colors = {chess.WHITE, chess.BLACK}
        self.anim_mode = "full"
        self.show_legal = True
        self.show_last_move = True
        self.learning_tooltips = False
        self.promotion_handler = None
        self.sound_cb = None
        self.location = LOCATIONS[DEFAULT_LOCATION]
        self.army_key = DEFAULT_ARMY
        self.army = ARMIES_3D[DEFAULT_ARMY]

        self.items: dict[int, Piece3D] = {}
        self.dying: list[Piece3D] = []
        self.selected: int | None = None
        self.legal_targets: dict[int, bool] = {}
        self.last_move: chess.Move | None = None
        self.hint_move: chess.Move | None = None
        self.targets: list[int] = []
        self.threat_marks: dict[int, tuple] = {}
        self.square_marks: dict[int, tuple] = {}
        self.arrows: dict[tuple, tuple] = {}
        self.circles: set[int] = set()
        self.hover_square: int | None = None
        self._right_start: int | None = None
        self._drag_piece: Piece3D | None = None
        self._drag_start = None
        self._dragging = False
        self._dropped_move = None
        self._marker_pool: list[QObject] = []
        self._markers_used = 0
        self._check_fx: list = []
        self._markers_dirty = True
        self.fx_objects: list = []

        self.camera = CameraRig(self)
        self.animator = Animator()
        for pt in chess.PIECE_TYPES:
            for geo in self.lib.piece_set(pt).values():
                self._keep_alive(geo)
        self.set_environment(DEFAULT_LOCATION)
        self.set_position(chess.Board())
        self._last = time.perf_counter()
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    # ------------------------------------------------------------ helpers
    def call(self, fn: str, *args):
        return QMetaObject.invokeMethod(self.root, fn, Qt.ConnectionType.DirectConnection,
                                        Q_RETURN_ARG("QVariant"), *[Q_ARG("QVariant", a) for a in args])

    def sound(self, name: str):
        if self.sound_cb:
            self.sound_cb(name)

    def palette(self, color: bool) -> dict:
        th = self.army["white" if color == chess.WHITE else "black"]
        return {k: QColor(th[k]) for k in ("body", "metal", "cloth", "glow", "dark")}

    def burst(self, kind, pos, count, color, speed=3.0, spread=2.0, scale=1.0):
        if self.anim_mode == "off":
            return
        c = QColor(color) if not isinstance(color, QColor) else color
        self.bridge.fx.emit("burst", [kind, float(pos[0]), float(pos[1]), float(pos[2]), int(count), c,
                                      float(speed), float(spread), float(scale)])

    def light(self, name, pos, color, brightness):
        c = QColor(color)
        self.bridge.fx.emit("light", [name, float(pos[0]), float(pos[1]), float(pos[2]),
                                      c.redF(), c.greenF(), c.blueF(), float(brightness)])

    def spawn_fx(self, kind: str, **props) -> QObject | None:
        props["kind"] = kind
        obj = self.call("spawn", self._fx_url, "fx", props)
        if obj is not None:
            self.fx_objects.append(obj)
        return obj

    def spawn_marker(self, **props) -> QObject | None:
        obj = self.call("spawn", self._marker_url, "fx", props)
        if obj is not None:
            self.fx_objects.append(obj)
        return obj

    @staticmethod
    def _destroy(obj):
        try:
            obj.setProperty("visible", False)
            obj.deleteLater()
        except RuntimeError:
            pass

    def kill(self, obj):
        if obj is None:
            return
        if obj in self.fx_objects:
            self.fx_objects.remove(obj)
        self._destroy(obj)

    def _keep_alive(self, geo):
        """Pin a shared geometry to a hidden model so it stays uploaded to the GPU."""
        if geo is None or id(geo) in self._kept:
            return
        self._kept[id(geo)] = (geo, self.call("spawn", self._keeper_url, "keeper", {"geo": geo}))

    def bolt_geometry(self, start, end, jag=0.35) -> MeshGeometry:
        pts = [start, end]
        disp = math.dist(start, end) * jag
        while disp > 0.06:
            new = [pts[0]]
            for a, b in zip(pts, pts[1:]):
                m = [(a[i] + b[i]) / 2 + random.uniform(-disp, disp) * (0.5 if i == 1 else 1.0) for i in range(3)]
                new += [tuple(m), b]
            pts = new
            disp /= 2
        return MeshGeometry(tube(pts, 0.035, 6, caps=False))

    # ------------------------------------------------------------ look
    def set_environment(self, key: str):
        loc = LOCATIONS.get(key, self.location)
        self.location = loc
        r = self.root
        r.setProperty("skyUrl", _url(textures.sky_texture(loc)))
        r.setProperty("boardUrl", _url(textures.board_texture(loc)))
        r.setProperty("runeUrl", _url(textures.rune_texture(loc)))
        for prop, val in (("frameColor", QColor(loc.frame)), ("rockColor", QColor(loc.rock)),
                          ("rockEmissive", QColor(loc.rock_emissive)), ("accentColor", QColor(loc.accent)),
                          ("terrainGlowColor", QColor(loc.glow)), ("terrainGlowStrength", loc.glow_strength),
                          ("orbitColor", QColor(loc.orbit)), ("orbitOpacity", loc.orbit_opacity),
                          ("orbitSpeed", loc.orbit_speed), ("fogColor", QColor(loc.fog)),
                          ("fogDensity", loc.fog_density), ("sunColor", QColor(loc.sun_color)),
                          ("sunBrightness", loc.sun_brightness), ("sunRotation", QVector3D(*loc.sun_rotation)),
                          ("probeExposure", loc.probe_exposure), ("ambientKind", loc.ambient)):
            r.setProperty(prop, val)
        t = self.lib.terrain(loc.key)
        for name in ("rock", "accent", "glow", "orbit", "lake"):
            self._keep_alive(t[name])
        for name, prop in (("rock", "terrainRock"), ("accent", "terrainAccent"), ("glow", "terrainGlow"),
                           ("orbit", "terrainOrbit"), ("lake", "terrainLake")):
            r.setProperty(prop, t[name])
        r.setProperty("craters", [QVector3D(*c) for c in t["craters"]])

    def set_style(self, key: str):
        if key in ARMIES_3D:
            self.army_key = key
            self.army = ARMIES_3D[key]
            self.set_position(self.board, self.last_move)

    def set_ambient(self, on: bool):
        self.root.setProperty("ambientOn", on)

    def set_graphics(self, bloom: bool = True, shadows: bool = True, msaa: bool = True):
        self.root.setProperty("bloom", bloom)
        self.root.setProperty("shadows", shadows)
        self.root.setProperty("msaa", msaa)

    def set_learning_tooltips(self, on: bool):
        self.learning_tooltips = on

    # ------------------------------------------------------------ camera
    def set_flipped(self, flipped: bool, duration: float = 1.2):
        self.flipped = flipped
        self.camera.go(yaw=180.0 if flipped else 0.0, pitch=36, distance=15.5,
                       target=(0, 0.2, -0.5 if flipped else 0.5), duration=duration)

    def view_white(self):
        self.set_flipped(False)

    def view_black(self):
        self.set_flipped(True)

    def view_top(self):
        self.camera.go(yaw=180.0 if self.flipped else 0.0, pitch=84, distance=14.5, target=(0, 0, 0), duration=1.0)

    def view_side(self):
        self.camera.go(yaw=90.0, pitch=26, distance=14.0, target=(0, 0.3, 0), duration=1.0)

    def toggle_orbit(self):
        self.camera.auto_orbit = not self.camera.auto_orbit

    # ------------------------------------------------------------ pieces
    def piece_items(self) -> list[Piece3D]:
        return list(self.items.values())

    def _spawn_piece(self, piece: chess.Piece, sq: int) -> Piece3D:
        th = self.army["white" if piece.color else "black"]
        geos = self.lib.piece_set(piece.piece_type)
        props = {"square": sq, "geoBody": geos["body"], "geoMetal": geos["metal"], "geoCloth": geos["cloth"],
                 "geoGlow": geos["glow"], "geoDark": geos["dark"], "bodyColor": QColor(th["body"]),
                 "bodyMetal": th["bodyMetal"], "bodyRough": th["bodyRough"], "metalColor": QColor(th["metal"]),
                 "clothColor": QColor(th["cloth"]), "glowColor": QColor(th["glow"]),
                 "darkColor": QColor(th["dark"]), "ringTex": self.tex["ring"], "pieceScale": PIECE_SCALE}
        obj = self.call("spawn", self._piece_url, "pieces", props)
        p = Piece3D(obj, piece, sq)
        x, z = sq_xz(sq)
        p.set_pos(x, 0.0, z)
        p.set_yaw(facing_yaw(piece.color))
        return p

    def retexture(self, p: Piece3D, piece: chess.Piece):
        p.piece = piece
        geos = self.lib.piece_set(piece.piece_type)
        for part, prop in (("body", "geoBody"), ("metal", "geoMetal"), ("cloth", "geoCloth"), ("glow", "geoGlow"),
                           ("dark", "geoDark")):
            p.obj.setProperty(prop, geos[part])

    def remove_item(self, p: Piece3D):
        for sq, it in list(self.items.items()):
            if it is p:
                del self.items[sq]
        if p in self.dying:
            self.dying.remove(p)
        self._destroy(p.obj)

    def set_position(self, board: chess.Board, last_move: chess.Move | None = None, keep: bool = False):
        self.board = board.copy()
        self.last_move = last_move
        pmap = self.board.piece_map()
        if not keep:
            for p in list(self.items.values()) + self.dying:
                self._destroy(p.obj)
            self.items = {}
            self.dying = []
        for sq, p in list(self.items.items()):
            if pmap.get(sq) != p.piece:
                self.remove_item(p)
        for sq, piece in pmap.items():
            p = self.items.get(sq)
            if p is None:
                self.items[sq] = self._spawn_piece(piece, sq)
            else:
                x, z = sq_xz(sq)
                p.square = sq
                p.set("square", sq)
                p.set_pos(x, 0.0, z)
                p.set_yaw(facing_yaw(piece.color))
                p.lift = p.target_lift = 0.0
                p.set("lift", 0.0)
                p.set("fade", 1.0)
                p.set("flash", 0.0)
                p.set("tilt", 0.0)
                p.set("idle", True)
        self.clear_selection()
        self._markers_dirty = True

    def reset_effects(self):
        self.animator.cancel_all()
        for obj in list(self.fx_objects):
            self.kill(obj)
        self._check_fx = []
        self.root.setProperty("darkness", 0.0)
        self.root.setProperty("bannerAlpha", 0.0)
        self.root.setProperty("runeGlow", 1.0)
        self.light("fx", (0, 2, 0), "#ffffff", 0)
        self.light("danger", (0, 1, 0), "#ff2a2a", 0)
        self.camera.restore(0.4)
        for p in self.items.values():
            p.set("frost", 0.0)
            p.set("flash", 0.0)
            p.set("idle", True)

    # ------------------------------------------------------------ moves
    @property
    def busy(self) -> bool:
        return self.animator.busy

    def play_move(self, record, board_after: chess.Board, on_done=None):
        self.clear_selection()
        self.hint_move = None
        self.threat_marks = {}
        self._clear_check_fx()
        dropped = self._dropped_move == record.move
        self._dropped_move = None
        self._markers_dirty = True

        def finish():
            self.set_position(board_after, record.move, keep=True)
            if board_after.is_check() and not board_after.is_checkmate():
                king = self.items.get(board_after.king(board_after.turn))
                if king is not None:
                    self._check_fx = choreo3d.check_warning(self, king)
            if on_done:
                on_done()

        if self.anim_mode == "off":
            self.set_position(board_after, record.move, keep=False)
            self.sound("capture" if record.captured else ("castle" if record.castle_rook else "move"))
            QTimer.singleShot(0, finish)
            return
        quick = dropped or self.anim_mode == "quick"
        self.animator.run(self._move_script(record, quick), on_done=finish)

    def _move_script(self, record, quick):
        move = record.move
        mover = self.items.pop(move.from_square, None)
        if mover is None:
            return
        color = record.color
        victim = self.items.pop(record.captured_sq, None) if record.captured_sq is not None else None
        rook = None
        if record.castle_rook:
            rf, rt = record.castle_rook
            rook = self.items.pop(rf, None)
            if rook is not None:
                self.items[rt] = rook
                rook.square = rt
        self.items[move.to_square] = mover
        mover.square = move.to_square
        mover.target_lift = 0.0
        mover.set("selectGlow", 0.0)
        to_xz = sq_xz(move.to_square)
        if victim is not None:
            self.dying.append(victim)
        if rook is not None:
            yield from choreo3d.castle(self, mover, rook, to_xz, sq_xz(record.castle_rook[1]), color, quick)
        elif victim is not None:
            yield from choreo3d.capture(self, mover, victim, to_xz, record.piece_type, color, quick)
        else:
            yield from choreo3d.move_piece(self, mover, to_xz, record.piece_type, color, quick)
        if record.promotion:
            yield from choreo3d.promotion(self, mover, chess.Piece(record.promotion, color), quick)

    def play_script(self, gen, on_done=None):
        return self.animator.run(gen, on_done)

    # big moments (called by the game controller)
    def play_checkmate(self, loser: bool, title: str, subtitle: str, rgb, on_done=None):
        king = self.items.get(self.board.king(loser))
        if king is None or self.anim_mode == "off":
            self.show_banner(title, subtitle, rgb, None)
            if on_done:
                on_done()
            return
        self.animator.run(choreo3d.checkmate(self, king, loser, title, subtitle, rgb), on_done)

    def play_draw(self, title: str, subtitle: str, on_done=None):
        self.animator.run(choreo3d.draw(self, title, subtitle), on_done)

    def celebrate(self, color: bool):
        if self.anim_mode != "off":
            self.animator.run(choreo3d.celebrate(self, color))

    def lesson_success(self, sq: int):
        if self.anim_mode != "off":
            self.animator.run(choreo3d.lesson_success(self, sq))
        else:
            self.sound("success")

    def show_banner(self, title: str, subtitle: str = "", rgb=(255, 210, 120), hold: float | None = 1.0,
                    size: int = 90):
        r = self.root
        r.setProperty("bannerTitle", title)
        r.setProperty("bannerSub", subtitle)
        r.setProperty("bannerColor", QColor(*rgb))
        r.setProperty("bannerSize", size)

        def anim():
            yield Tween(0.35, lambda t: (r.setProperty("bannerAlpha", t), r.setProperty("bannerScale", 1.6 - 0.6 * t)),
                        ease_out)
            if hold is not None:
                yield hold
                yield Tween(0.4, lambda t: r.setProperty("bannerAlpha", 1 - t))
        self.animator.run(anim())

    def hide_banner(self):
        self.root.setProperty("bannerAlpha", 0.0)

    # ------------------------------------------------------------ highlights
    def clear_selection(self):
        if self.selected is not None:
            p = self.items.get(self.selected)
            if p:
                p.target_lift = 0.0
                p.set("selectGlow", 0.0)
        self.selected = None
        self.legal_targets = {}
        self._markers_dirty = True

    def show_hint(self, move: chess.Move | None):
        self.hint_move = move
        self._markers_dirty = True
        if move is not None:
            p = self.items.get(move.from_square)
            if p:
                self.burst("magic", p.center(0.6), 25, "#8fe0ff", 1.5, 0.8, 1.0)

    def set_threats(self, marks: dict):
        self.threat_marks = dict(marks)
        self._markers_dirty = True

    def set_targets(self, squares: list):
        self.targets = list(squares)
        self._markers_dirty = True

    def set_square_marks(self, marks: dict):
        self.square_marks = dict(marks)
        self._markers_dirty = True

    def clear_marks(self):
        self.arrows.clear()
        self.circles.clear()
        self._markers_dirty = True

    def flash_screen(self, rgb, strength=0.3, duration=0.2):
        pass  # bloom + point light flashes do this job in 3D

    def _clear_check_fx(self):
        for obj in self._check_fx:
            self.kill(obj)
        self._check_fx = []
        self.light("danger", (0, 1, 0), "#ff2a2a", 0)

    def _marker(self, tex, x, z, color, alpha=1.0, size=1.0, spin=0.0, pulse=0.0, y=0.02, angle=0.0, glow=1.5):
        if self._markers_used < len(self._marker_pool):
            m = self._marker_pool[self._markers_used]
        else:
            m = self.call("spawn", self._marker_url, "markers", {})
            self._marker_pool.append(m)
        self._markers_used += 1
        m.setProperty("visible", True)
        m.setProperty("tex", self.tex[tex])
        m.setProperty("position", QVector3D(x, y, z))
        m.setProperty("color", QColor(*color) if isinstance(color, tuple) else QColor(color))
        m.setProperty("alpha", alpha)
        m.setProperty("size", size)
        m.setProperty("spin", spin)
        m.setProperty("pulse", pulse)
        m.setProperty("angle", angle)
        m.setProperty("glow", glow)
        return m

    def _refresh_markers(self):
        self._markers_dirty = False
        self._markers_used = 0
        if self.last_move and self.show_last_move:
            for sq in (self.last_move.from_square, self.last_move.to_square):
                x, z = sq_xz(sq)
                self._marker("square", x, z, (255, 205, 90), 0.32, 0.98, y=0.006)
        for sq, rgb in self.square_marks.items():
            x, z = sq_xz(sq)
            self._marker("square", x, z, rgb, 0.45, 0.98, y=0.008)
        if self.selected is not None:
            x, z = sq_xz(self.selected)
            self._marker("square", x, z, (255, 225, 130), 0.5, 0.98, y=0.009)
            if self.show_legal:
                piece = self.board.piece_at(self.selected)
                glow = self.palette(piece.color if piece else True)["glow"]
                for sq, cap in self.legal_targets.items():
                    x, z = sq_xz(sq)
                    if cap:
                        self._marker("ring", x, z, (255, 90, 60), 0.95, 0.95, spin=40, pulse=1.0, y=0.03)
                    else:
                        self._marker("dot", x, z, glow, 0.95, 0.9, pulse=1.0, y=0.03, glow=2.5)
                if self.hover_square in self.legal_targets:
                    x, z = sq_xz(self.hover_square)
                    self._marker("square", x, z, (255, 255, 255), 0.4, 0.98, y=0.012)
        for sq in self.targets:
            x, z = sq_xz(sq)
            self._marker("target", x, z, (255, 220, 120), 1.0, 0.95, spin=50, pulse=1.0, y=0.025, glow=2.5)
        for sq, rgb in self.threat_marks.items():
            x, z = sq_xz(sq)
            self._marker("ring", x, z, rgb, 0.9, 1.0, spin=-30, pulse=1.0, y=0.035)
        if self.hint_move is not None:
            self._path(self.hint_move.from_square, self.hint_move.to_square, (90, 210, 255))
        for (a, b), rgb in self.arrows.items():
            self._path(a, b, rgb)
        for sq in self.circles:
            x, z = sq_xz(sq)
            self._marker("ring", x, z, (90, 220, 120), 1.0, 1.0, y=0.04)
        for m in self._marker_pool[self._markers_used:]:
            m.setProperty("visible", False)

    def _path(self, a, b, rgb):
        x1, z1 = sq_xz(a)
        x2, z2 = sq_xz(b)
        n = max(2, int(math.dist((x1, z1), (x2, z2)) / 0.33))
        for i in range(1, n):
            t = i / n
            self._marker("dot", x1 + (x2 - x1) * t, z1 + (z2 - z1) * t, rgb, 0.9, 0.35 + 0.35 * t, y=0.05,
                         glow=3.0)
        self._marker("ring", x2, z2, rgb, 1.0, 1.0, spin=60, pulse=1.0, y=0.05, glow=2.5)

    # ------------------------------------------------------------ input
    def can_move(self, sq: int) -> bool:
        piece = self.board.piece_at(sq)
        return (self.interactive and not self.busy and piece is not None and piece.color == self.board.turn
                and piece.color in self.human_colors)

    def _select(self, sq: int):
        self.clear_selection()
        self.selected = sq
        p = self.items.get(sq)
        if p:
            p.target_lift = 0.12
            p.set("selectGlow", 1.0)
        for m in self.board.legal_moves:
            if m.from_square == sq:
                self.legal_targets[m.to_square] = self.board.is_capture(m)
                if self.board.is_castling(m):
                    self.legal_targets.setdefault(rules.castling_rook_squares(self.board, m)[0], False)
        self._markers_dirty = True
        self.sound("select")
        self.piece_selected.emit(sq)

    def _find_move(self, frm: int, to: int) -> chess.Move | None:
        candidates = [m for m in self.board.legal_moves if m.from_square == frm and m.to_square == to]
        if not candidates:
            for m in self.board.legal_moves:
                if m.from_square == frm and self.board.is_castling(m) and \
                        rules.castling_rook_squares(self.board, m)[0] == to:
                    return m
            return None
        if len(candidates) == 1:
            return candidates[0]
        choice = self.promotion_handler(self.board.turn) if self.promotion_handler else chess.QUEEN
        if not choice:
            return None
        return next((m for m in candidates if m.promotion == choice), candidates[0])

    def _try_move(self, frm: int, to: int, dropped=False) -> bool:
        move = self._find_move(frm, to)
        if move is None:
            return False
        if dropped:
            self._dropped_move = move
        self.move_requested.emit(move)
        return True

    def _square_from(self, x, z, sq_hint) -> int | None:
        if sq_hint is not None and sq_hint >= 0:
            return sq_hint
        if x > 50:
            return None
        return xz_sq(x, z)

    def _press(self, x, z, sq_hint) -> bool:
        self.clear_marks()
        self.camera.auto_orbit = False
        sq = self._square_from(x, z, sq_hint)
        if sq is None:
            self.clear_selection()
            return False
        if self.selected is not None and sq in self.legal_targets and sq != self.selected:
            if self._try_move(self.selected, sq):
                return False
        if self.can_move(sq):
            if self.selected != sq:
                self._select(sq)
            self._drag_piece = self.items.get(sq)
            self._drag_start = (x, z)
            self._dragging = False
            return True
        piece = self.board.piece_at(sq)
        if piece is not None and self.interactive and not self.busy and piece.color in self.human_colors \
                and piece.color != self.board.turn:
            self.illegal_attempt.emit()
        self.clear_selection()
        return False

    def _drag(self, x, z):
        p = self._drag_piece
        if p is None:
            return
        if not self._dragging and math.dist((x, z), self._drag_start) > 0.25:
            self._dragging = True
            p.set("idle", False)
        if self._dragging:
            p.set_pos(x, 0.0, z)
            p.target_lift = 0.35
            sq = xz_sq(x, z)
            if sq != self.hover_square:
                self.hover_square = sq
                self._markers_dirty = True

    def _release(self, x, z, sq_hint):
        p = self._drag_piece
        self._drag_piece = None
        if p is None or not self._dragging:
            return
        self._dragging = False
        p.set("idle", True)
        frm = self.selected
        sq = xz_sq(x, z) if x < 50 else None
        if frm is not None and sq is not None and sq != frm and sq in self.legal_targets:
            if self._try_move(frm, sq, dropped=True):
                return
        hx, hz = sq_xz(frm if frm is not None else p.square)
        sx, sz = p.x, p.z
        self.animator.run(self._snap(p, sx, sz, hx, hz))
        p.target_lift = 0.12 if frm is not None else 0.0
        if sq is not None and sq != frm:
            self.illegal_attempt.emit()

    def _snap(self, p, sx, sz, x, z):
        yield Tween(0.15, lambda t: p.set_pos(sx + (x - sx) * t, 0.0, sz + (z - sz) * t))

    def _hover(self, x, z, sq_hint):
        sq = self._square_from(x, z, sq_hint)
        if sq != self.hover_square:
            self.hover_square = sq
            if self.selected is not None:
                self._markers_dirty = True
        if sq is not None and (self.can_move(sq) or sq in self.legal_targets):
            self.widget.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.widget.setCursor(Qt.CursorShape.ArrowCursor)

    def _right_press(self, x, z, sq_hint):
        self._right_start = self._square_from(x, z, -1)

    def _right_release(self, x, z, sq_hint):
        start, end = self._right_start, self._square_from(x, z, -1)
        self._right_start = None
        if start is None or end is None:
            return
        if start == end:
            self.circles.symmetric_difference_update({end})
        else:
            key = (start, end)
            if key in self.arrows:
                del self.arrows[key]
            else:
                self.arrows[key] = (255, 170, 60)
        self._markers_dirty = True

    def pause(self):
        self._timer.stop()

    def resume(self):
        self._last = time.perf_counter()
        self._timer.start(16)

    # ------------------------------------------------------------ loop
    def _tick(self):
        now = time.perf_counter()
        dt = min(0.05, now - self._last)
        self._last = now
        self.animator.step(dt)
        self.camera.tick(dt)
        for p in list(self.items.values()):
            if abs(p.lift - p.target_lift) > 0.002:
                p.lift += (p.target_lift - p.lift) * min(1.0, dt * 12)
                p.set("lift", round(p.lift, 4))
        if self._markers_dirty:
            self._refresh_markers()
