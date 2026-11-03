"""Capture choreography - every piece fights with its own magic.

Piece   Attack
Pawn    small elemental bolt
Knight  magical charge (leaps straight through the target)
Bishop  holy / dark beam
Rook    energy cannon
Queen   lightning storm
King    defensive shockwave
"""
from __future__ import annotations

import math
import random

import chess

from effects.magic import (Beam, Flash, LightningBolt, MagicCircle, Projectile, Ring,
                           charge_up, disintegrate, explosion, lightning, wind)

from .animator import Tween, ease_in, ease_out
from .movement import move_item


def dissolve(scene, victim, palette, delay=0.0):
    """Victim flashes, shrinks and crumbles into glowing dust."""
    if delay:
        yield delay
    vx, vy = victim.center()
    disintegrate(scene.particles, (vx, vy - 5), [palette.main, palette.accent, palette.core], 1.0, 60, 70)
    victim.idle = False
    scene.sound("shatter")

    def fade(t):
        victim.set_flash(1.0 - t)
        victim.sprite.setOpacity(1.0 - t)
        victim.shadow.setOpacity(0.6 * (1.0 - t))
        victim.lift = victim.target_lift = 10 * t

    yield Tween(0.45, fade, ease_in)
    scene.remove_item(victim)


def hit(scene, victim, attacker_palette, victim_palette, intensity=1.0, debris=True):
    vx, vy = victim.center()
    explosion(scene.particles, (vx, vy), attacker_palette, intensity,
              debris=[victim_palette.main, victim_palette.deep, victim_palette.accent] if debris else None)
    victim.set_flash(1.0)
    scene.camera.shake(5 + 6 * intensity, 0.25)
    scene.flash_screen(attacker_palette.core, 0.12 * intensity, 0.18)
    scene.sound("boom" if intensity > 0.9 else "impact")
    return scene.animator.run(dissolve(scene, victim, victim_palette, 0.05))


def capture(scene, attacker, victim, to_xy, piece_type: int, color: bool, quick: bool = False):
    pal = scene.style.palette(color)
    vpal = scene.style.palette(not color)
    ax, ay = attacker.center()
    vx, vy = victim.center()

    if quick:
        yield from move_item(scene, attacker, to_xy, piece_type, color, quick=True, sound=False)
        task = hit(scene, victim, pal, vpal, 0.7)
        scene.sound("capture")
        while not task.done:
            yield None
        return

    scene.camera.focus(((ax + vx) / 2, (ay + vy) / 2), 1.08, 0.35)

    if piece_type == chess.KNIGHT:
        wind(scene.particles, (ax, ay + 10), 0.5, 0.8, pal, radius=50)
        scene.sound("charge")
        yield 0.12
        # the charge: leap onto the target
        yield from move_item(scene, attacker, to_xy, chess.KNIGHT, color, arc=75, duration=0.4, sound=False)
        task = hit(scene, victim, pal, vpal, 1.0)
        scene.particles.add_effect(Ring((vx, vy + 20), pal.main, 20, 170, 0.5, 10))

    elif piece_type == chess.PAWN:
        attacker.target_lift = 10
        charge_up(scene.particles, (ax, ay - 12), pal, 0.22, 0.6, 50)
        scene.sound("charge_small")
        yield 0.22
        landed = []
        scene.particles.add_effect(Projectile(scene.particles, (ax, ay - 12), (vx, vy), pal, 0.18, 24,
                                              on_hit=lambda: landed.append(1)))
        scene.sound("zap")
        while not landed:
            yield None
        task = hit(scene, victim, pal, vpal, 0.6)
        attacker.target_lift = 0
        yield 0.12
        yield from move_item(scene, attacker, to_xy, chess.PAWN, color, sound=False)

    elif piece_type == chess.BISHOP:
        attacker.target_lift = 18
        charge_up(scene.particles, (ax, ay - 18), pal, 0.32, 1.0, 70)
        scene.sound("charge")
        yield 0.32
        scene.particles.add_effect(Beam((ax, ay - 18), (vx, vy), pal.main, pal.core, life=0.55, width=15, grow=0.12))
        scene.particles.add_effect(Flash((ax, ay - 18), pal.core, 120, 0.4))
        scene.sound("beam")
        yield 0.14
        task = hit(scene, victim, pal, vpal, 0.9)
        yield 0.3
        attacker.target_lift = 0
        yield from move_item(scene, attacker, to_xy, chess.BISHOP, color, sound=False)

    elif piece_type == chess.ROOK:
        charge_up(scene.particles, (ax, ay - 8), pal, 0.3, 1.3, 90)
        scene.sound("charge")
        yield 0.3
        dx, dy = vx - ax, vy - ay
        d = math.hypot(dx, dy) or 1.0
        ox, oy = attacker.pos().x(), attacker.pos().y()
        rx, ry = -dx / d * 9, -dy / d * 9
        landed = []
        scene.particles.add_effect(Projectile(scene.particles, (ax, ay - 8), (vx, vy), pal, 0.22, 52,
                                              on_hit=lambda: landed.append(1), trail_rate=1.6))
        scene.sound("cannon")
        yield Tween(0.07, lambda t: attacker.setPos(ox + rx * t, oy + ry * t), ease_out)
        yield Tween(0.18, lambda t: attacker.setPos(ox + rx * (1 - t), oy + ry * (1 - t)), ease_in)
        while not landed:
            yield None
        task = hit(scene, victim, pal, vpal, 1.35)
        yield 0.3
        yield from move_item(scene, attacker, to_xy, chess.ROOK, color, sound=False)

    elif piece_type == chess.QUEEN:
        attacker.target_lift = 30
        circle = MagicCircle((ax, ay + 30), pal.main, 62, life=1.3, spin=120, runes=10)
        scene.particles.add_effect(circle)
        charge_up(scene.particles, (ax, ay - 30), pal, 0.4, 1.4, 100)
        scene.sound("charge")
        yield 0.4
        lightning(scene.particles, (vx, vy), 1.3, pal, bolts=3)
        scene.particles.add_effect(LightningBolt((ax, ay - 30), (vx, vy), pal.accent, life=0.4, width=6))
        scene.sound("thunder")
        scene.camera.shake(12, 0.3)
        yield 0.16
        task = hit(scene, victim, pal, vpal, 1.3)
        yield 0.32
        attacker.target_lift = 0
        yield from move_item(scene, attacker, to_xy, chess.QUEEN, color, sound=False)

    else:  # King: defensive magic
        scene.particles.add_effect(MagicCircle((ax, ay + 25), pal.main, 55, life=0.9, spin=200))
        scene.particles.add_effect(Ring((ax, ay + 10), pal.accent, 15, 190, 0.5, 12))
        scene.sound("shield")
        yield 0.25
        task = hit(scene, victim, pal, vpal, 0.8)
        yield 0.2
        yield from move_item(scene, attacker, to_xy, chess.KING, color, sound=False)

    while not task.done:
        yield None
    scene.camera.reset(0.45)
