"""Big moments: check warning, checkmate cinematic, promotion, draws."""
from __future__ import annotations

import random

import chess

from effects.magic import DANGER, MagicCircle, Ring, holy, ice, lightning, sparkle, teleport, dark

from .animator import Tween, ease_in_out, ease_out


def check_warning(scene, king_item):
    """The King's square lights up with a warning circle (stays while in check)."""
    kx, ky = king_item.center()
    circle = MagicCircle((kx, ky + 22), DANGER.main, 58, life=None, spin=70, runes=8,
                         follow=lambda: (king_item.center()[0], king_item.center()[1] + 22))
    scene.particles.add_effect(circle)
    scene.particles.add_effect(Ring((kx, ky + 20), DANGER.main, 70, 15, 0.5, 8))
    scene.banner.show("CHECK!", "", DANGER.main, hold=0.8, size=72)
    scene.sound("check")
    scene.camera.shake(4, 0.2)
    return circle


def promotion(scene, item, new_piece: chess.Piece):
    pal = scene.style.palette(new_piece.color)
    x, y = item.center()
    teleport(scene.particles, (x, y), 0.9, 1.0, pal)
    scene.sound("promote")
    yield Tween(0.18, lambda t: item.set_flash(t), ease_out)
    scene.retexture(item, new_piece)
    sparkle(scene.particles, (x, y), pal, 1.6, 50)
    yield Tween(0.35, lambda t: item.set_flash(1 - t), ease_in_out)


def checkmate(scene, king_item, loser: bool, title: str, subtitle: str, title_color):
    """Board darkens -> magic surrounds the King -> lightning -> armies freeze -> CHECKMATE."""
    win_pal = scene.style.palette(not loser)
    scene.sound("doom")
    king_item.setZValue(95)
    yield Tween(0.7, lambda t: scene.overlay.set_level(0.62 * t), ease_in_out)

    kx, ky = king_item.center()
    scene.camera.focus((kx, ky), 1.16, 0.8)
    scene.particles.add_effect(MagicCircle((kx, ky + 20), win_pal.main, 78, life=None, spin=55, runes=12, seed=3))
    scene.particles.add_effect(MagicCircle((kx, ky + 20), win_pal.accent, 112, life=None, spin=-30, runes=16,
                                           seed=7))
    scene.rune_ring.boost = 1.0
    emitter = scene.particles.add_emitter(
        lambda s, x, y: sparkle(s, (x + random.uniform(-60, 60), y + random.uniform(-50, 40)), win_pal, 0.25, 20),
        14, 2.6, (kx, ky))
    yield 0.7

    for i in range(4):
        lightning(scene.particles, (kx + random.uniform(-14, 14), ky + random.uniform(-10, 10)), 1.1 + 0.2 * i,
                  win_pal, bolts=2)
        scene.sound("thunder")
        scene.camera.shake(9 + i * 3, 0.25)
        scene.flash_screen((235, 240, 255), 0.35, 0.2)
        king_item.set_flash(1.0)
        yield Tween(0.26, lambda t: king_item.set_flash(1 - t))

    scene.sound("freeze")
    frozen = [it for it in scene.piece_items() if it.piece.color == loser]
    for it in frozen:
        it.idle = False
        x, y = it.center()
        ice(scene.particles, (x, y), 0.6, 0.35)
    yield Tween(0.7, lambda t: [it.set_frozen(0.85 * t) for it in frozen], ease_out)
    emitter.stop()

    scene.banner.show(title, subtitle, title_color, hold=None, size=104)
    scene.sound("victory_horn")
    yield 0.5
    scene.camera.reset(1.0)
    yield Tween(1.0, lambda t: scene.overlay.set_level(0.62 - 0.27 * t), ease_in_out)


def draw_cinematic(scene, title: str, subtitle: str):
    scene.sound("draw")
    yield Tween(0.6, lambda t: scene.overlay.set_level(0.4 * t), ease_in_out)
    for it in scene.piece_items():
        it.idle = False
    scene.banner.show(title, subtitle, (200, 210, 230), hold=None, size=96)
    yield 0.4


def victory_flourish(scene, color: bool):
    """Small celebration (used after resign / time-out wins and solved puzzles)."""
    pal = scene.style.palette(color)
    for _ in range(5):
        x = random.uniform(100, 700)
        y = random.uniform(100, 700)
        (holy if color == chess.WHITE else dark)(scene.particles, (x, y), 0.7, 0.6, pal)
        yield 0.18


def lesson_success(scene, square_center):
    pal = scene.style.palette(chess.WHITE)
    sparkle(scene.particles, square_center, pal, 2.2, 70)
    scene.particles.add_effect(Ring(square_center, pal.main, 20, 220, 0.8, 10))
    scene.sound("success")
    yield 0.5
