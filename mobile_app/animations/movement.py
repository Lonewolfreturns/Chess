"""How each piece travels across the board.

Pawn   - marches, one hop per square
Knight - leaps in a high arc with a wind trail
Bishop - glides with a sparkle trail
Rook   - heavy slide, dust and a little quake when it lands
Queen  - takes flight leaving stardust
King   - a short dignified float
"""
from __future__ import annotations

import math
import random

import chess

from effects.magic import Ring, trail_spawner, wind
from effects.particles import SMOKE, Particle

from .animator import Tween, ease_in_out, ease_out, linear


def piece_z(y: float) -> float:
    return 10 + y / 100.0


def _dust(scene, x, y, amount=8):
    for _ in range(scene.particles.count(amount)):
        ang = random.uniform(math.pi * 0.9, math.pi * 2.1)
        sp = random.uniform(30, 90)
        scene.particles.add(Particle(x + random.uniform(-25, 25), y + 40, math.cos(ang) * sp, math.sin(ang) * sp * 0.4,
                                     life=random.uniform(0.4, 0.8), size=18, size_end=46, color=(150, 135, 120),
                                     alpha=0.35, kind=SMOKE))


def move_item(scene, item, to_xy, piece_type: int, color: bool, quick: bool = False,
              arc: float | None = None, duration: float | None = None, trail: bool = True,
              sound: bool = True):
    """Generator: animate ``item`` to world position ``to_xy`` in the piece's style."""
    fx, fy = item.pos().x(), item.pos().y()
    tx, ty = to_xy
    dist = math.hypot(tx - fx, ty - fy) / 100.0
    palette = scene.style.palette(color)

    if duration is None:
        if quick:
            duration = 0.16 + 0.025 * dist
        else:
            duration = {
                chess.PAWN: 0.20 + 0.11 * dist,
                chess.KNIGHT: 0.42,
                chess.BISHOP: 0.22 + 0.055 * dist,
                chess.ROOK: 0.24 + 0.055 * dist,
                chess.QUEEN: 0.28 + 0.05 * dist,
                chess.KING: 0.30,
            }.get(piece_type, 0.3)
    if arc is None:
        arc = 0.0 if quick else {chess.KNIGHT: 58.0, chess.QUEEN: 26.0, chess.BISHOP: 12.0,
                                 chess.KING: 10.0}.get(piece_type, 0.0)

    item.setZValue(60)
    item.idle = False
    emitter = None
    if not quick and trail and piece_type in (chess.KNIGHT, chess.BISHOP, chess.QUEEN):
        emitter = scene.particles.add_emitter(trail_spawner(palette, 16 if piece_type == chess.QUEEN else 12),
                                              110, None, follow=item.center)
    if not quick and piece_type == chess.ROOK:
        _dust(scene, fx + 50, fy + 50, 6)
    if sound:
        scene.sound("whoosh" if piece_type in (chess.KNIGHT, chess.QUEEN) and not quick else "move_start")

    hops = max(1, round(dist))

    def update(t):
        x = fx + (tx - fx) * t
        y = fy + (ty - fy) * t
        if piece_type == chess.PAWN and not quick:
            h = abs(math.sin(math.pi * hops * t)) * 9
        else:
            h = math.sin(math.pi * t) * arc
        item.setPos(x, y)
        item.lift = item.target_lift = h

    ease = linear if piece_type == chess.PAWN and not quick else (ease_out if quick else ease_in_out)
    yield Tween(duration, update, ease)

    if emitter:
        emitter.stop()
    item.lift = item.target_lift = 0.0
    item.setZValue(piece_z(ty))
    item.idle = True
    cx, cy = tx + 50, ty + 50
    if not quick:
        if piece_type in (chess.KNIGHT, chess.ROOK, chess.QUEEN):
            scene.particles.add_effect(Ring((cx, cy + 32), (200, 190, 170), 10, 55, 0.35, 4, additive=False))
            _dust(scene, tx + 50, ty + 50, 5)
        if piece_type == chess.ROOK:
            scene.camera.shake(3.0, 0.15)
        if piece_type == chess.KNIGHT:
            wind(scene.particles, (cx, cy + 20), 0.4, 0.5, palette, radius=40)
    if sound:
        scene.sound("move")


def castle(scene, king_item, rook_item, king_to, rook_to, color, quick=False):
    """King walks, the rook vaults over him."""
    rook_task = scene.animator.run(move_item(scene, rook_item, rook_to, chess.ROOK, color, quick,
                                             arc=0 if quick else 70, duration=0.45 if not quick else None,
                                             sound=False))
    yield from move_item(scene, king_item, king_to, chess.KING, color, quick)
    while not rook_task.done:
        yield None
    if not quick:
        scene.sound("castle")
        pal = scene.style.palette(color)
        kx, ky = king_item.center()
        scene.particles.add_effect(Ring((kx, ky + 30), pal.main, 20, 160, 0.6, 6))
