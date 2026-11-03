"""Medieval 3D chess pieces, modelled procedurally.

Pawn   - foot knight: great helm with plume, heater shield, sword
Knight - armoured war horse with spiked chanfron and mane
Bishop - battle-mage bishop: mitre, beard, glowing staff
Rook   - war elephant ("Haathi") carrying a castle tower
Queen  - gown, cape, necklace and pearl crown with an orb
King   - robe, ermine collar, cape, sceptre and cross crown

Units: one board square = 1.0. Pieces stand on y = 0 and face -Z.
Each piece is split into material parts: body, metal, cloth, glow, dark.
"""
from __future__ import annotations

import math

import chess

from .meshes import (RX, RY, RZ, S, T, Mesh, box, cylinder, ellipsoid, extrude, lathe, loft,
                     merge, sphere, torus, tube)

PARTS = ("body", "metal", "cloth", "glow", "dark")


def _pedestal(r: float, h: float = 0.1) -> tuple[Mesh, Mesh]:
    body = lathe([(0, 0), (r, 0), (r, 0.022), (r * 0.97, 0.04), (r * 0.9, 0.055), (r * 0.86, 0.075),
                  (r * 0.82, h), (0, h)], 40, sharp=(1, 2, 6))
    metal = torus(r * 0.93, 0.013, 40, 8).transformed(T(0, 0.052, 0))
    return body, metal


def _arm(a, b, r=0.028):
    mid = ((a[0] + b[0]) / 2 + 0.01 * (1 if a[0] > 0 else -1), (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
    return tube([a, mid, b], [r, r * 0.95, r * 0.85], 10)


# --------------------------------------------------------------------- pawn
def pawn() -> dict:
    body, metal = _pedestal(0.27)
    cloth = lathe([(0.165, 0.095), (0.155, 0.16), (0.125, 0.27), (0.115, 0.30)], 32)
    armour = lathe([(0.0, 0.255), (0.118, 0.255), (0.128, 0.30), (0.132, 0.36), (0.122, 0.40), (0.09, 0.43),
                    (0.05, 0.445), (0.0, 0.445)], 32)
    belt = torus(0.121, 0.013, 32, 8).transformed(T(0, 0.275, 0))
    pauldrons = merge((ellipsoid(0.062, 0.046, 0.066), T(0.118, 0.415, 0)),
                      (ellipsoid(0.062, 0.046, 0.066), T(-0.118, 0.415, 0)))
    arms = merge(_arm((0.13, 0.40, 0.0), (0.16, 0.30, -0.06)), _arm((-0.13, 0.40, 0.0), (-0.15, 0.31, -0.05)))
    neck = cylinder(0.04, 0.04, 0.03, 12).transformed(T(0, 0.44, 0))
    helm = lathe([(0.0, 0.455), (0.072, 0.455), (0.08, 0.47), (0.082, 0.53), (0.077, 0.56), (0.056, 0.585),
                  (0.0, 0.596)], 28)
    visor = merge(box(0.12, 0.013, 0.03).transformed(T(0, 0.528, -0.074)),
                  box(0.012, 0.045, 0.02).transformed(T(0, 0.5, -0.079)))
    plume = tube([(0, 0.585, -0.03), (0, 0.625, 0.0), (0, 0.62, 0.045), (0, 0.585, 0.08), (0, 0.54, 0.095)],
                 [0.018, 0.026, 0.025, 0.02, 0.01], 10)
    shield_poly = [(-0.085, 0.12), (0.085, 0.12), (0.085, 0.04), (0.06, -0.04), (0.0, -0.115), (-0.06, -0.04),
                   (-0.085, 0.04)]
    place = T(-0.165, 0.33, -0.075) @ RY(-20)
    shield_face = extrude(shield_poly, 0.02).transformed(place @ RY(90))
    shield_rim = extrude([(u * 1.13, v * 1.1) for u, v in shield_poly], 0.012).transformed(
        place @ T(0, 0, 0.012) @ RY(90))
    emblem = extrude([(0, 0.05), (0.035, 0.0), (0, -0.05), (-0.035, 0.0)], 0.03).transformed(place @ RY(90))
    blade = box(0.024, 0.31, 0.008).transformed(T(0.17, 0.455, -0.07))
    tip = extrude([(-0.012, 0), (0.012, 0), (0, 0.04)], 0.008).transformed(T(0.17, 0.61, -0.07) @ RY(90))
    guard = box(0.095, 0.017, 0.017).transformed(T(0.17, 0.295, -0.07))
    grip = cylinder(0.011, 0.011, 0.06, 8).transformed(T(0.17, 0.23, -0.07))
    pommel = sphere(0.018, 10, 6).transformed(T(0.17, 0.225, -0.07))
    return {
        "body": body,
        "metal": merge(metal, armour, pauldrons, arms, helm, shield_rim, blade, tip, guard, pommel),
        "cloth": merge(cloth, plume, shield_face),
        "glow": emblem,
        "dark": merge(belt, neck, visor, grip),
    }


# ------------------------------------------------------------------- knight
HORSE = [(-0.20, 0.10), (0.16, 0.10), (0.15, 0.20), (0.09, 0.32), (0.08, 0.40), (0.13, 0.47), (0.22, 0.52),
         (0.30, 0.55), (0.345, 0.585), (0.345, 0.63), (0.29, 0.675), (0.20, 0.725), (0.11, 0.77), (0.04, 0.80),
         (-0.03, 0.79), (-0.09, 0.74), (-0.15, 0.62), (-0.20, 0.46), (-0.23, 0.30), (-0.23, 0.18)]


def knight() -> dict:
    body, metal = _pedestal(0.3)
    head = loft(HORSE, 0.21, layers=8, bulge=0.32)
    ears = merge((cylinder(0.026, 0.0, 0.085, 10), T(0.045, 0.765, 0.0) @ RX(-18) @ RZ(-12)),
                 (cylinder(0.026, 0.0, 0.085, 10), T(-0.045, 0.765, 0.0) @ RX(-18) @ RZ(12)))
    eyes = merge((sphere(0.021, 10, 6), T(0.078, 0.695, -0.165)), (sphere(0.021, 10, 6), T(-0.078, 0.695, -0.165)))
    nostrils = merge((sphere(0.014, 8, 5), T(0.05, 0.6, -0.335)), (sphere(0.014, 8, 5), T(-0.05, 0.6, -0.335)))
    chanfron = box(0.13, 0.014, 0.23).transformed(T(0, 0.735, -0.205) @ RX(-30))
    spike = cylinder(0.022, 0.0, 0.1, 10).transformed(T(0, 0.775, -0.12) @ RX(-55))
    bridle = torus(0.1, 0.012, 24, 6).transformed(T(0, 0.6, -0.27) @ S(1.08, 0.55, 1) @ RX(90))
    cheek = merge(box(0.012, 0.16, 0.012).transformed(T(0.103, 0.63, -0.2) @ RX(25)),
                  box(0.012, 0.16, 0.012).transformed(T(-0.103, 0.63, -0.2) @ RX(25)))
    mane = tube([(0, 0.80, 0.01), (0, 0.765, 0.075), (0, 0.66, 0.145), (0, 0.5, 0.2), (0, 0.32, 0.235),
                 (0, 0.2, 0.245)], [0.03, 0.04, 0.042, 0.04, 0.035, 0.03], 10)
    collar = lathe([(0.225, 0.095), (0.215, 0.14), (0.175, 0.215), (0.14, 0.25)], 32)
    collar_trim = torus(0.2, 0.012, 32, 6).transformed(T(0, 0.15, 0))
    return {
        "body": merge(body, head, ears),
        "metal": merge(metal, chanfron, spike, collar_trim),
        "cloth": merge(mane, collar),
        "glow": eyes,
        "dark": merge(bridle, cheek, nostrils),
    }


# ------------------------------------------------------------------- bishop
def bishop() -> dict:
    body, metal = _pedestal(0.28)
    robe = lathe([(0.19, 0.095), (0.185, 0.14), (0.15, 0.28), (0.122, 0.42), (0.112, 0.52), (0.12, 0.56),
                  (0.1, 0.6), (0.06, 0.62), (0, 0.622)], 32)
    hem = torus(0.183, 0.013, 32, 6).transformed(T(0, 0.135, 0))
    belt = torus(0.12, 0.018, 32, 8).transformed(T(0, 0.42, 0))
    stole = box(0.055, 0.30, 0.014).transformed(T(0, 0.29, -0.142) @ RX(-11))
    capelet = lathe([(0.0, 0.602), (0.145, 0.585), (0.155, 0.55), (0.135, 0.515)], 32)
    head = sphere(0.064, 18, 12).transformed(T(0, 0.672, 0))
    beard = cylinder(0.05, 0.0, 0.13, 14).transformed(T(0, 0.665, -0.04) @ RX(170))
    mitre = lathe([(0, 0.705), (0.07, 0.705), (0.082, 0.75), (0.078, 0.82), (0.052, 0.885), (0.0, 0.94)], 28)
    slit = box(0.014, 0.12, 0.2).transformed(T(0, 0.875, 0))
    band = torus(0.073, 0.012, 28, 6).transformed(T(0, 0.71, 0))
    cross = merge(box(0.014, 0.07, 0.012).transformed(T(0, 0.79, -0.08)),
                  box(0.045, 0.014, 0.012).transformed(T(0, 0.8, -0.08)))
    sleeve = _arm((0.12, 0.56, 0.0), (0.19, 0.46, -0.05), 0.034)
    sleeve2 = _arm((-0.12, 0.56, 0.0), (-0.12, 0.43, -0.1), 0.034)
    staff = cylinder(0.012, 0.012, 0.79, 8).transformed(T(0.2, 0.1, -0.05))
    crook = torus(0.045, 0.011, 20, 6).transformed(T(0.2, 0.925, -0.05) @ RX(90))
    orb = sphere(0.03, 14, 10).transformed(T(0.2, 0.925, -0.05))
    return {
        "body": merge(body, robe, head, beard, mitre),
        "metal": merge(metal, hem, band, cross, staff, crook),
        "cloth": merge(belt, stole, capelet, sleeve, sleeve2),
        "glow": orb,
        "dark": slit,
    }


# --------------------------------------------------------------------- rook
def rook() -> dict:
    body, metal = _pedestal(0.33)
    torso = ellipsoid(0.17, 0.15, 0.24, 24, 14).transformed(T(0, 0.37, 0.03))
    legs = merge(*[(cylinder(0.058, 0.052, 0.24, 12), T(x, 0.095, z))
                   for x in (-0.1, 0.1) for z in (-0.11, 0.15)])
    anklets = merge(*[(torus(0.058, 0.012, 14, 6), T(x, 0.13, z)) for x in (-0.1, 0.1) for z in (-0.11, 0.15)])
    head = ellipsoid(0.11, 0.12, 0.11, 18, 12).transformed(T(0, 0.43, -0.22))
    trunk = tube([(0, 0.42, -0.31), (0, 0.36, -0.355), (0, 0.27, -0.372), (0, 0.19, -0.365), (0, 0.14, -0.335),
                  (0, 0.135, -0.29)], [0.048, 0.042, 0.036, 0.03, 0.025, 0.02], 12)
    tusks = merge(*[tube([(sx * 0.05, 0.36, -0.29), (sx * 0.062, 0.3, -0.36), (sx * 0.058, 0.28, -0.43),
                          (sx * 0.045, 0.305, -0.475)], [0.019, 0.016, 0.011, 0.004], 8) for sx in (-1, 1)])
    ears = merge((ellipsoid(0.02, 0.1, 0.085, 12, 8), T(0.12, 0.45, -0.18) @ RY(28)),
                 (ellipsoid(0.02, 0.1, 0.085, 12, 8), T(-0.12, 0.45, -0.18) @ RY(-28)))
    eyes = merge((sphere(0.016, 8, 6), T(0.074, 0.47, -0.3)), (sphere(0.016, 8, 6), T(-0.074, 0.47, -0.3)))
    plate = ellipsoid(0.075, 0.075, 0.03, 16, 10).transformed(T(0, 0.49, -0.315) @ RX(-22))
    blanket = ellipsoid(0.185, 0.12, 0.25, 24, 10, v_min=-0.15, v_max=1.0).transformed(T(0, 0.40, 0.03))
    fringe = torus(0.2, 0.014, 32, 6).transformed(T(0, 0.385, 0.03) @ S(0.93, 1, 1.25))
    # castle tower on the back
    tower_y = 0.5
    tower = box(0.25, 0.15, 0.26, y0=tower_y)
    merlons = []
    for x, z in ((-0.1, -0.105), (0.1, -0.105), (-0.1, 0.105), (0.1, 0.105), (0, -0.105), (0, 0.105),
                 (-0.1, 0), (0.1, 0)):
        merlons.append(box(0.055, 0.06, 0.055, y0=tower_y + 0.15).transformed(T(x, 0, z)))
    band = box(0.27, 0.018, 0.28, y0=tower_y + 0.14)
    windows = merge(box(0.025, 0.06, 0.01, y0=tower_y + 0.05).transformed(T(-0.055, 0, -0.131)),
                    box(0.025, 0.06, 0.01, y0=tower_y + 0.05).transformed(T(0.055, 0, -0.131)))
    pole = cylinder(0.008, 0.008, 0.25, 8).transformed(T(0.08, tower_y + 0.15, 0.08))
    flag = extrude([(0.0, 0.0), (0.13, -0.035), (0.0, -0.075)], 0.006).transformed(
        T(0.08, tower_y + 0.39, 0.08) @ RY(-150))
    gem = sphere(0.024, 12, 8).transformed(T(0, tower_y + 0.1, -0.135))
    return {
        "body": merge(body, torso, legs, head, trunk, ears, tower, *merlons),
        "metal": merge(metal, anklets, tusks, plate, fringe, band, pole),
        "cloth": merge(blanket, flag),
        "glow": merge(eyes, gem),
        "dark": windows,
    }


# -------------------------------------------------------------------- queen
def queen() -> dict:
    body, metal = _pedestal(0.31)
    gown = lathe([(0.225, 0.095), (0.218, 0.14), (0.172, 0.26), (0.122, 0.40), (0.085, 0.50), (0.076, 0.54),
                   (0.087, 0.58), (0.102, 0.64), (0.096, 0.672), (0.06, 0.70), (0, 0.708)], 36)
    cape = lathe([(0.235, 0.105), (0.19, 0.27), (0.135, 0.46), (0.11, 0.6), (0.115, 0.66), (0.095, 0.695)], 24,
                 arc=(20, 160))
    cape_in = Mesh().add(cape).flip()
    hem = torus(0.215, 0.013, 36, 6).transformed(T(0, 0.135, 0))
    belt = torus(0.078, 0.012, 28, 6).transformed(T(0, 0.538, 0))
    necklace = torus(0.088, 0.008, 28, 6).transformed(T(0, 0.668, 0) @ RX(8))
    pendant = sphere(0.016, 10, 6).transformed(T(0, 0.65, -0.093))
    sleeves = merge(_arm((0.095, 0.655, 0.0), (0.15, 0.52, -0.06), 0.03),
                    _arm((-0.095, 0.655, 0.0), (-0.15, 0.52, -0.06), 0.03))
    neck = cylinder(0.034, 0.03, 0.05, 12).transformed(T(0, 0.7, 0))
    head = sphere(0.062, 18, 12).transformed(T(0, 0.79, 0))
    hair = merge(ellipsoid(0.066, 0.06, 0.066, 18, 10, v_min=0.0).transformed(T(0, 0.795, 0.006)),
                 sphere(0.045, 12, 8).transformed(T(0, 0.79, 0.07)))
    crown_band = lathe([(0.064, 0.832), (0.07, 0.832), (0.076, 0.868), (0.07, 0.868)], 28)
    spikes = []
    pearls = []
    for k in range(8):
        a = math.tau * k / 8
        x, z = math.cos(a) * 0.072, math.sin(a) * 0.072
        spikes.append(cylinder(0.012, 0.004, 0.06, 6).transformed(T(x, 0.862, z) @ RZ(-math.degrees(a) * 0) ))
        pearls.append(sphere(0.011, 8, 6).transformed(T(x * 1.04, 0.925, z * 1.04)))
    orb = sphere(0.026, 14, 10).transformed(T(0, 0.93, 0))
    return {
        "body": merge(body, gown, neck, head),
        "metal": merge(metal, hem, belt, necklace, crown_band, *spikes),
        "cloth": merge(cape, cape_in, sleeves),
        "glow": merge(pendant, orb, *pearls),
        "dark": hair,
    }


# --------------------------------------------------------------------- king
def king() -> dict:
    body, metal = _pedestal(0.32)
    robe = lathe([(0.228, 0.095), (0.22, 0.14), (0.185, 0.26), (0.152, 0.40), (0.137, 0.52), (0.142, 0.6),
                  (0.15, 0.66), (0.13, 0.72), (0.07, 0.75), (0, 0.755)], 36)
    cape = lathe([(0.245, 0.105), (0.21, 0.3), (0.18, 0.5), (0.168, 0.66), (0.13, 0.735)], 24, arc=(15, 165))
    cape_in = Mesh().add(cape).flip()
    fur = torus(0.122, 0.036, 32, 10).transformed(T(0, 0.725, 0))
    hem = torus(0.222, 0.014, 36, 6).transformed(T(0, 0.135, 0))
    belt = torus(0.147, 0.016, 32, 6).transformed(T(0, 0.43, 0))
    buckle = box(0.05, 0.04, 0.02).transformed(T(0, 0.43, -0.152))
    emblem = extrude([(0, 0.055), (0.04, 0.0), (0, -0.055), (-0.04, 0.0)], 0.02).transformed(
        T(0, 0.6, -0.142) @ RY(90))
    sleeves = merge(_arm((0.14, 0.68, 0.0), (0.2, 0.5, -0.07), 0.036),
                    _arm((-0.14, 0.68, 0.0), (-0.17, 0.5, -0.08), 0.036))
    sceptre = cylinder(0.013, 0.013, 0.46, 8).transformed(T(0.205, 0.33, -0.08))
    sceptre_orb = sphere(0.03, 14, 10).transformed(T(0.205, 0.8, -0.08))
    head = sphere(0.07, 18, 12).transformed(T(0, 0.815, 0))
    beard = cylinder(0.058, 0.0, 0.12, 14).transformed(T(0, 0.81, -0.045) @ RX(170))
    crown_band = lathe([(0.07, 0.862), (0.079, 0.862), (0.084, 0.915), (0.075, 0.915)], 28)
    points = []
    for k in range(5):
        a = math.tau * k / 5 + math.pi / 2
        x, z = math.cos(a) * 0.078, math.sin(a) * 0.078
        points.append(cylinder(0.018, 0.0, 0.05, 8).transformed(T(x, 0.91, z)))
    velvet = ellipsoid(0.068, 0.06, 0.068, 18, 8, v_min=0.0).transformed(T(0, 0.88, 0))
    cross = merge(box(0.02, 0.09, 0.02, y0=0.935), box(0.06, 0.02, 0.02, y0=0.985))
    gem = sphere(0.02, 10, 8).transformed(T(0, 0.888, -0.082))
    return {
        "body": merge(body, robe, head, beard),
        "metal": merge(metal, hem, belt, buckle, sceptre, crown_band, *points, cross),
        "cloth": merge(cape, cape_in, sleeves, velvet),
        "glow": merge(emblem, sceptre_orb, gem),
        "dark": fur,
    }


BUILDERS = {chess.PAWN: pawn, chess.KNIGHT: knight, chess.BISHOP: bishop,
            chess.ROOK: rook, chess.QUEEN: queen, chess.KING: king}

NAMES = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
         chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}

_cache: dict = {}


def piece_parts(piece_type: int) -> dict:
    if piece_type not in _cache:
        _cache[piece_type] = BUILDERS[piece_type]()
    return _cache[piece_type]
