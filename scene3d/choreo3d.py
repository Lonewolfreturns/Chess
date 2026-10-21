"""3D battle choreography: movement styles, per-piece attacks and cinematics.

Movement
  Pawn   (foot knight)  - marches, one hop per square
  Knight (war horse)    - turns, rears and leaps in a high arc
  Bishop (battle-mage)  - levitates and glides, leaving stardust
  Rook   (war elephant) - heavy stomping walk, dust, ground shakes
  Queen                 - takes flight
  King                  - dignified walk

Attacks
  Pawn   - sword lunge + elemental burst
  Knight - cavalry charge (leaps onto the target)
  Bishop - beam from the staff
  Rook   - cannon fire from the howdah tower
  Queen  - lightning storm
  King   - royal shockwave
"""
from __future__ import annotations

import math
import random

import chess
from PyQt6.QtGui import QColor, QQuaternion, QVector3D

from animations.animator import Tween, ease_in, ease_in_out, ease_out, linear

DUST = "#8a7a6a"


def _facing(color):
    return 0.0 if color == chess.WHITE else 180.0


def _yaw_to(dx, dz):
    return math.degrees(math.atan2(-dx, -dz))


def _short(a, b):
    return a + ((b - a + 180) % 360 - 180)


def turn(view, p, yaw, duration=0.14):
    start = p.yaw
    goal = _short(start, yaw)
    if abs(goal - start) < 2:
        return
    yield Tween(duration, lambda t: p.set_yaw(start + (goal - start) * t), ease_in_out)


def flash_light(view, pos, color, brightness=6.0, duration=0.45):
    def run():
        yield Tween(duration, lambda t: view.light("fx", (pos[0], pos[1] + 0.6, pos[2]), color,
                                                   brightness * (1 - t)), ease_out)
    view.animator.run(run())


# ================================================================ movement
def move_piece(view, p, to_xz, pt, color, quick=False, duration=None, arc=None, sound=True, turn_back=True):
    fx, fz = p.x, p.z
    tx, tz = to_xz
    dist = math.hypot(tx - fx, tz - fz)
    pal = view.palette(color)
    p.set("idle", False)
    if not quick and dist > 0.05:
        yield from turn(view, p, _yaw_to(tx - fx, tz - fz))
    if duration is None:
        duration = (0.16 + 0.03 * dist) if quick else {
            chess.PAWN: 0.24 + 0.14 * dist, chess.KNIGHT: 0.5, chess.BISHOP: 0.26 + 0.07 * dist,
            chess.ROOK: 0.32 + 0.1 * dist, chess.QUEEN: 0.3 + 0.06 * dist, chess.KING: 0.4}.get(pt, 0.35)
    if arc is None:
        arc = 0.0 if quick else {chess.KNIGHT: 0.95, chess.QUEEN: 0.55, chess.BISHOP: 0.18, chess.KING: 0.05}.get(pt, 0.0)
    if sound:
        view.sound("whoosh" if (pt in (chess.KNIGHT, chess.QUEEN) and not quick) else "move_start")
    steps = max(1, round(dist * (1.0 if pt == chess.PAWN else 1.4)))
    trail = not quick and pt in (chess.BISHOP, chess.QUEEN, chess.KNIGHT)
    state = {"next": 0.0}

    def update(t):
        x = fx + (tx - fx) * t
        z = fz + (tz - fz) * t
        if quick:
            h = 0.0
        elif pt == chess.PAWN:
            h = abs(math.sin(math.pi * steps * t)) * 0.07
        elif pt == chess.ROOK:
            h = abs(math.sin(math.pi * steps * t)) * 0.035
        elif pt == chess.KING:
            h = arc + abs(math.sin(math.pi * steps * t)) * 0.03
        else:
            h = math.sin(math.pi * t) * arc
        p.set_pos(x, 0.0, z)
        p.lift = p.target_lift = h
        p.set("lift", h)
        if pt == chess.KNIGHT and not quick:
            p.set("tilt", -25 * math.sin(math.pi * t) if t < 0.5 else -25 * math.sin(math.pi * t) * 0.6)
        if trail and t >= state["next"]:
            state["next"] = t + 0.08
            view.burst("magic", p.center(0.4), 4, pal["glow"], 0.4, 0.3, 0.8)

    ease = linear if (pt in (chess.PAWN, chess.ROOK) and not quick) else (ease_out if quick else ease_in_out)
    yield Tween(duration, update, ease)
    p.lift = p.target_lift = 0.0
    p.set("lift", 0.0)
    p.set("tilt", 0.0)
    if not quick:
        if pt in (chess.KNIGHT, chess.ROOK, chess.QUEEN):
            view.burst("smoke", (tx, 0.05, tz), 8, DUST, 0.5, 0.6, 0.6)
        if pt == chess.ROOK:
            view.camera.shake(4.0, 0.2)
        if pt == chess.KNIGHT:
            view.camera.shake(2.5, 0.15)
            view.burst("spark", (tx, 0.1, tz), 10, pal["glow"], 2.0, 1.5, 0.8)
        if turn_back:
            yield from turn(view, p, _facing(color), 0.16)
    else:
        p.set_yaw(_facing(color))
    p.set("idle", True)
    if sound:
        view.sound("move")


def castle(view, king, rook, king_to, rook_to, color, quick=False):
    rook_task = view.animator.run(move_piece(view, rook, rook_to, chess.ROOK, color, quick,
                                             duration=None if quick else 0.55, sound=False))
    yield from move_piece(view, king, king_to, chess.KING, color, quick)
    while not rook_task.done:
        yield None
    if not quick:
        pal = view.palette(color)
        view.sound("castle")
        m = view.spawn_marker(tex=view.tex["circle"], color=pal["glow"], size=1.0, alpha=1.0, spin=90, glow=3.0,
                              position=QVector3D(king.x, 0.03, king.z))
        yield Tween(0.6, lambda t: (m.setProperty("size", 1.0 + 1.8 * t), m.setProperty("alpha", 1 - t)), ease_out)
        view.kill(m)


# ================================================================ effects
def explosion(view, pos, color, intensity=1.0, debris=None):
    view.burst("spark", pos, int(55 * intensity), color, 4.5 * intensity, 4.0 * intensity, 1.0)
    view.burst("fire", pos, int(22 * intensity), color, 1.2, 1.3 * intensity, intensity)
    view.burst("smoke", pos, int(10 * intensity), "#2a2226", 0.8, 0.8, intensity)
    if debris:
        for c in debris:
            view.burst("debris", pos, int(6 * intensity), c)
    flash_light(view, pos, color, 7.0 * intensity, 0.5)
    view.camera.shake(5 + 6 * intensity, 0.3)


def shockwave(view, pos, color, size=2.5, duration=0.5):
    m = view.spawn_marker(tex=view.tex["ring"], color=color, size=0.3, alpha=1.0, glow=3.0,
                          position=QVector3D(pos[0], 0.05, pos[2]))

    def run():
        yield Tween(duration, lambda t: (m.setProperty("size", 0.3 + size * t), m.setProperty("alpha", 1 - t)), ease_out)
        view.kill(m)
    view.animator.run(run())


def beam(view, start, end, color, width=0.07, duration=0.55):
    s, e = QVector3D(*start), QVector3D(*end)
    d = e - s
    length = d.length()
    rot = QQuaternion.rotationTo(QVector3D(0, 1, 0), d.normalized())
    b = view.spawn_fx("beam", color=QColor(color), intensity=6.0, alpha=1.0, rotation=rot)

    def run():
        def grow(t):
            cur = length * t
            mid = s + d.normalized() * (cur / 2)
            b.setProperty("position", mid)
            b.setProperty("scale", QVector3D(width / 50 * (1 + 0.2 * math.sin(t * 40)), cur / 100, width / 50))
        yield Tween(0.12, grow, ease_out)
        yield Tween(duration, lambda t: (b.setProperty("alpha", 1 - t * t),
                                         b.setProperty("scale", QVector3D(width / 50 * (1 + 0.5 * t), length / 100,
                                                                          width / 50 * (1 + 0.5 * t)))))
        view.kill(b)
    return view.animator.run(run())


def projectile(view, start, end, color, size=0.16, duration=0.3, arc=0.0):
    orb = view.spawn_fx("orb", color=QColor(color), intensity=7.0, alpha=1.0,
                        scale=QVector3D(size / 50, size / 50, size / 50), position=QVector3D(*start))
    state = {"next": 0.0}

    def update(t):
        pos = [start[i] + (end[i] - start[i]) * t for i in range(3)]
        pos[1] += math.sin(math.pi * t) * arc
        orb.setProperty("position", QVector3D(*pos))
        if t >= state["next"]:
            state["next"] = t + 0.05
            view.burst("fire", pos, 4, color, 0.3, 0.2, size * 2.2)
    yield Tween(duration, update, ease_in)
    view.kill(orb)


def lightning(view, start, end, color, duration=0.4):
    geo = view.bolt_geometry(start, end)
    bolt = view.spawn_fx("bolt", geo=geo, color=QColor(color), intensity=9.0, alpha=1.0)
    keep = [geo]

    def run():
        el = 0.0
        while el < duration:
            yield 0.05
            el += 0.05
            g = view.bolt_geometry(start, end)
            keep.append(g)
            bolt.setProperty("geo", g)
            bolt.setProperty("alpha", max(0.0, 1 - el / duration) * random.uniform(0.6, 1.0))
        view.kill(bolt)
        keep.clear()
    view.animator.run(run())


def dissolve(view, victim, color, delay=0.0):
    if delay:
        yield delay
    vpal = view.palette(victim.piece.color)
    c = victim.center(0.4)
    view.burst("magic", c, 40, vpal["glow"], 1.2, 0.6, 1.2)
    view.burst("debris", c, 10, vpal["body"])
    view.burst("debris", c, 6, vpal["metal"])
    view.sound("shatter")
    victim.set("idle", False)

    def fade(t):
        victim.set("flash", 1.0 - t)
        victim.set("fade", 1.0 - t)
        victim.lift = victim.target_lift = 0.25 * t
        victim.set("lift", victim.lift)
        victim.set("tilt", 35 * t)
    yield Tween(0.55, fade, ease_in)
    view.remove_item(victim)


def hit(view, victim, color, intensity=1.0):
    vpal = view.palette(victim.piece.color)
    explosion(view, victim.center(0.4), color, intensity, debris=[vpal["body"], vpal["metal"]])
    victim.set("flash", 1.0)
    view.sound("boom" if intensity > 0.9 else "impact")
    return view.animator.run(dissolve(view, victim, color, 0.05))


# ================================================================ captures
def capture(view, attacker, victim, to_xz, pt, color, quick=False):
    pal = view.palette(color)
    glow = pal["glow"]
    ax, az = attacker.x, attacker.z
    vx, vz = victim.x, victim.z

    if quick:
        yield from move_piece(view, attacker, to_xz, pt, color, quick=True, sound=False)
        task = hit(view, victim, glow, 0.7)
        view.sound("capture")
        while not task.done:
            yield None
        return

    view.camera.focus(((ax + vx) / 2, 0.5, (az + vz) / 2), distance=9.5, duration=0.4)
    attacker.set("idle", False)
    yield from turn(view, attacker, _yaw_to(vx - ax, vz - az), 0.16)

    if pt == chess.KNIGHT:
        view.sound("charge")
        view.burst("smoke", (ax, 0.05, az), 10, DUST, 0.6, 0.8, 0.7)
        yield from move_piece(view, attacker, to_xz, chess.KNIGHT, color, duration=0.42, arc=1.1, sound=False,
                              turn_back=False)
        task = hit(view, victim, glow, 1.0)
        shockwave(view, (vx, 0, vz), glow, 2.6)

    elif pt == chess.PAWN:
        # sword lunge
        view.sound("charge_small")
        lx, lz = ax + (vx - ax) * 0.42, az + (vz - az) * 0.42
        yield Tween(0.16, lambda t: attacker.set_pos(ax + (lx - ax) * t, 0, az + (lz - az) * t), ease_in)
        attacker.set("tilt", -18)
        view.sound("zap")
        view.burst("spark", victim.center(0.45), 30, glow, 3.5, 2.5, 0.9)
        view.burst("fire", victim.center(0.45), 12, glow, 1.0, 0.6, 0.7)
        task = hit(view, victim, glow, 0.6)
        yield 0.12
        attacker.set("tilt", 0)
        yield Tween(0.12, lambda t: attacker.set_pos(lx + (ax - lx) * t, 0, lz + (az - lz) * t), ease_out)
        yield from move_piece(view, attacker, to_xz, chess.PAWN, color, sound=False, turn_back=False)

    elif pt == chess.BISHOP:
        attacker.target_lift = 0.2
        yield 0.12
        staff = attacker.local(0.2, 0.93, -0.05)
        view.burst("magic", staff, 30, glow, 0.6, 0.8, 1.0)
        view.sound("charge")
        flash_light(view, staff, glow, 4.0, 0.5)
        yield 0.3
        beam(view, staff, victim.center(0.45), glow, 0.06, 0.5)
        view.sound("beam")
        yield 0.14
        task = hit(view, victim, glow, 0.9)
        yield 0.3
        attacker.target_lift = 0.0
        yield from move_piece(view, attacker, to_xz, chess.BISHOP, color, sound=False, turn_back=False)

    elif pt == chess.ROOK:
        tower = attacker.local(0.0, 0.62, -0.15)
        view.burst("fire", tower, 20, glow, 0.5, 0.4, 0.6)
        view.sound("charge")
        yield 0.28
        view.sound("cannon")
        view.camera.shake(5, 0.2)
        view.burst("smoke", tower, 14, "#3a3030", 1.2, 0.6, 0.8)
        yield from projectile(view, tower, victim.center(0.45), glow, 0.2, 0.3, arc=0.6)
        task = hit(view, victim, glow, 1.35)
        yield 0.3
        yield from move_piece(view, attacker, to_xz, chess.ROOK, color, sound=False, turn_back=False)

    elif pt == chess.QUEEN:
        attacker.target_lift = 0.45
        circle = view.spawn_marker(tex=view.tex["circle"], color=glow, size=1.6, alpha=1.0, spin=120, glow=3.0,
                                   position=QVector3D(ax, 0.04, az))
        view.burst("magic", attacker.center(0.9), 40, glow, 0.8, 1.2, 1.2)
        view.sound("charge")
        yield 0.42
        top = victim.center(0.5)
        for i in range(3):
            lightning(view, (top[0] + random.uniform(-1.5, 1.5), 9.0, top[2] + random.uniform(-1.5, 1.5)), top, glow, 0.4)
        lightning(view, attacker.center(1.0), top, pal["metal"], 0.35)
        view.sound("thunder")
        flash_light(view, top, "#e8f0ff", 9.0, 0.5)
        view.camera.shake(12, 0.35)
        yield 0.15
        task = hit(view, victim, glow, 1.3)
        yield 0.3
        view.kill(circle)
        attacker.target_lift = 0.0
        yield from move_piece(view, attacker, to_xz, chess.QUEEN, color, sound=False, turn_back=False)

    else:  # King: royal shockwave
        circle = view.spawn_marker(tex=view.tex["circle"], color=glow, size=1.2, alpha=1.0, spin=200, glow=3.0,
                                   position=QVector3D(ax, 0.04, az))
        view.sound("shield")
        shockwave(view, (ax, 0, az), glow, 3.5, 0.6)
        view.burst("magic", attacker.center(0.6), 40, glow, 1.5, 2.0, 1.0)
        yield 0.3
        task = hit(view, victim, glow, 0.8)
        yield 0.2
        view.kill(circle)
        yield from move_piece(view, attacker, to_xz, chess.KING, color, sound=False, turn_back=False)

    yield from turn(view, attacker, _facing(color), 0.2)
    attacker.set("idle", True)
    while not task.done:
        yield None
    view.camera.restore(0.5)


# ================================================================ big moments
def promotion(view, p, new_piece, quick=False):
    pal = view.palette(new_piece.color)
    view.sound("promote")
    if quick:
        view.retexture(p, new_piece)
        return
    c = p.center(0.4)
    beam(view, (c[0], 0.0, c[2]), (c[0], 6.0, c[2]), pal["glow"], 0.35, 0.7)
    view.burst("magic", c, 60, pal["glow"], 1.5, 1.0, 1.3)
    yield Tween(0.2, lambda t: p.set("flash", t))
    view.retexture(p, new_piece)
    yield Tween(0.45, lambda t: p.set("flash", 1 - t))


def check_warning(view, king):
    """Red runic circle + danger light around the King (kept until the next move)."""
    view.sound("check")
    circle = view.spawn_marker(tex=view.tex["circle"], color=QColor("#ff3030"), size=1.25, alpha=0.95, spin=70,
                               pulse=1.0, glow=3.5, position=QVector3D(king.x, 0.035, king.z))
    view.light("danger", (king.x, 1.2, king.z), "#ff2020", 4.0)
    view.burst("spark", king.center(0.5), 25, "#ff4040", 2.0, 1.5, 0.8)
    view.show_banner("CHECK!", "", (255, 90, 80), 0.8, 64)
    view.camera.shake(3, 0.2)
    return [circle]


def checkmate(view, king, loser, title, subtitle, rgb):
    winner = not loser
    pal = view.palette(winner)
    r = view.root
    view.sound("doom")
    view.light("danger", (king.x, 1.2, king.z), "#ff2020", 0)
    yield Tween(0.8, lambda t: (r.setProperty("darkness", 0.6 * t), r.setProperty("runeGlow", 1 + 2 * t)), ease_in_out)
    view.camera.focus((king.x, 0.6, king.z), distance=6.5, duration=0.9, pitch=24)
    c1 = view.spawn_marker(tex=view.tex["circle"], color=pal["glow"], size=1.6, alpha=1.0, spin=55, glow=4.0,
                           position=QVector3D(king.x, 0.04, king.z))
    c2 = view.spawn_marker(tex=view.tex["circle"], color=pal["metal"], size=2.6, alpha=0.8, spin=-30, glow=3.0,
                           position=QVector3D(king.x, 0.05, king.z))
    for _ in range(6):
        view.burst("magic", king.center(0.6), 15, pal["glow"], 0.8, 1.2, 1.2)
        yield 0.12
    top = king.center(0.7)
    for i in range(4):
        lightning(view, (top[0] + random.uniform(-2, 2), 10.0, top[2] + random.uniform(-2, 2)), top, pal["glow"], 0.4)
        view.sound("thunder")
        flash_light(view, top, "#e8f0ff", 10.0, 0.35)
        view.camera.shake(8 + 3 * i, 0.25)
        yield Tween(0.25, lambda t: king.set("flash", 1 - t))
    view.sound("freeze")
    frozen = [p for p in view.piece_items() if p.piece.color == loser]
    for p in frozen:
        p.set("idle", False)
        view.burst("magic", p.center(0.4), 8, "#bfe8ff", 0.6, 0.4, 0.8)
    yield Tween(0.8, lambda t: [p.set("frost", t) for p in frozen], ease_out)
    view.show_banner(title, subtitle, rgb, None, 92)
    view.sound("victory_horn")
    yield 0.6
    view.camera.restore(1.2)
    yield Tween(1.0, lambda t: r.setProperty("darkness", 0.6 - 0.3 * t), ease_in_out)


def draw(view, title, subtitle):
    view.sound("draw")
    r = view.root
    yield Tween(0.6, lambda t: r.setProperty("darkness", 0.35 * t))
    for p in view.piece_items():
        p.set("idle", False)
    view.show_banner(title, subtitle, (200, 215, 235), None, 84)


def celebrate(view, color):
    pal = view.palette(color)
    for _ in range(6):
        x, z = random.uniform(-3.5, 3.5), random.uniform(-3.5, 3.5)
        view.burst("magic", (x, 0.5, z), 30, pal["glow"], 2.5, 1.5, 1.2)
        view.burst("spark", (x, 0.5, z), 30, pal["metal"], 4.0, 3.0, 1.0)
        flash_light(view, (x, 0.5, z), pal["glow"], 4.0, 0.4)
        yield 0.2


def lesson_success(view, sq):
    from .view3d import sq_xz
    x, z = sq_xz(sq)
    view.sound("success")
    shockwave(view, (x, 0, z), "#ffd27a", 3.0, 0.7)
    view.burst("magic", (x, 0.6, z), 60, "#ffe9a8", 2.0, 1.5, 1.2)
    yield 0.5
