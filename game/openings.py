"""Opening names and a small opening book.

Lines are stored as space separated UCI moves. ``opening_name`` finds the
longest known line that matches the game so far; ``book_move`` lets the AI
play varied, sound openings.
"""
from __future__ import annotations

import random

OPENINGS: dict[str, str] = {
    "e2e4": "King's Pawn Opening",
    "e2e4 e7e5": "Open Game",
    "e2e4 e7e5 g1f3": "King's Knight Opening",
    "e2e4 e7e5 g1f3 b8c6": "King's Knight Opening: Normal Variation",
    "e2e4 e7e5 g1f3 b8c6 f1b5": "Ruy Lopez (Spanish Game)",
    "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6": "Ruy Lopez: Morphy Defence",
    "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6": "Ruy Lopez: Morphy Defence, Main Line",
    "e2e4 e7e5 g1f3 b8c6 f1b5 g8f6": "Ruy Lopez: Berlin Defence",
    "e2e4 e7e5 g1f3 b8c6 f1c4": "Italian Game",
    "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5": "Italian Game: Giuoco Piano",
    "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5 c2c3": "Italian Game: Giuoco Piano, Main Line",
    "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5 b2b4": "Italian Game: Evans Gambit",
    "e2e4 e7e5 g1f3 b8c6 f1c4 g8f6": "Italian Game: Two Knights Defence",
    "e2e4 e7e5 g1f3 b8c6 d2d4": "Scotch Game",
    "e2e4 e7e5 g1f3 b8c6 d2d4 e5d4 f3d4": "Scotch Game: Main Line",
    "e2e4 e7e5 g1f3 b8c6 b1c3 g8f6": "Four Knights Game",
    "e2e4 e7e5 g1f3 g8f6": "Petrov's Defence",
    "e2e4 e7e5 g1f3 d7d6": "Philidor Defence",
    "e2e4 e7e5 f2f4": "King's Gambit",
    "e2e4 e7e5 f2f4 e5f4": "King's Gambit Accepted",
    "e2e4 e7e5 b1c3": "Vienna Game",
    "e2e4 e7e5 f1c4": "Bishop's Opening",
    "e2e4 e7e5 d2d4 e5d4": "Centre Game",
    "e2e4 c7c5": "Sicilian Defence",
    "e2e4 c7c5 g1f3": "Sicilian Defence: Open",
    "e2e4 c7c5 g1f3 d7d6": "Sicilian Defence: Modern Variations",
    "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 a7a6": "Sicilian Defence: Najdorf Variation",
    "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 g7g6": "Sicilian Defence: Dragon Variation",
    "e2e4 c7c5 g1f3 b8c6": "Sicilian Defence: Old Sicilian",
    "e2e4 c7c5 g1f3 e7e6": "Sicilian Defence: French Variation",
    "e2e4 c7c5 b1c3": "Sicilian Defence: Closed",
    "e2e4 c7c5 c2c3": "Sicilian Defence: Alapin Variation",
    "e2e4 e7e6": "French Defence",
    "e2e4 e7e6 d2d4 d7d5": "French Defence: Normal Variation",
    "e2e4 e7e6 d2d4 d7d5 e4e5": "French Defence: Advance Variation",
    "e2e4 e7e6 d2d4 d7d5 b1c3": "French Defence: Paulsen Variation",
    "e2e4 c7c6": "Caro-Kann Defence",
    "e2e4 c7c6 d2d4 d7d5": "Caro-Kann Defence: Main Line",
    "e2e4 c7c6 d2d4 d7d5 e4e5": "Caro-Kann Defence: Advance Variation",
    "e2e4 d7d5": "Scandinavian Defence",
    "e2e4 d7d5 e4d5 d8d5": "Scandinavian Defence: Main Line",
    "e2e4 g8f6": "Alekhine's Defence",
    "e2e4 d7d6": "Pirc Defence",
    "e2e4 g7g6": "Modern Defence",
    "d2d4": "Queen's Pawn Opening",
    "d2d4 d7d5": "Queen's Pawn Game",
    "d2d4 d7d5 c2c4": "Queen's Gambit",
    "d2d4 d7d5 c2c4 e7e6": "Queen's Gambit Declined",
    "d2d4 d7d5 c2c4 e7e6 b1c3 g8f6": "Queen's Gambit Declined: Main Line",
    "d2d4 d7d5 c2c4 d5c4": "Queen's Gambit Accepted",
    "d2d4 d7d5 c2c4 c7c6": "Slav Defence",
    "d2d4 d7d5 c1f4": "London System",
    "d2d4 d7d5 g1f3 g8f6 c1f4": "London System",
    "d2d4 g8f6": "Indian Defence",
    "d2d4 g8f6 c1f4": "London System",
    "d2d4 g8f6 c2c4": "Indian Defence: Normal Variation",
    "d2d4 g8f6 c2c4 g7g6": "King's Indian / Grünfeld",
    "d2d4 g8f6 c2c4 g7g6 b1c3 f8g7": "King's Indian Defence",
    "d2d4 g8f6 c2c4 g7g6 b1c3 f8g7 e2e4 d7d6": "King's Indian Defence: Main Line",
    "d2d4 g8f6 c2c4 g7g6 b1c3 d7d5": "Grünfeld Defence",
    "d2d4 g8f6 c2c4 e7e6": "Indian Defence: East Indian",
    "d2d4 g8f6 c2c4 e7e6 b1c3 f8b4": "Nimzo-Indian Defence",
    "d2d4 g8f6 c2c4 e7e6 g1f3 b7b6": "Queen's Indian Defence",
    "d2d4 g8f6 c2c4 c7c5": "Benoni Defence",
    "d2d4 f7f5": "Dutch Defence",
    "c2c4": "English Opening",
    "c2c4 e7e5": "English Opening: Reversed Sicilian",
    "c2c4 g8f6": "English Opening: Anglo-Indian",
    "g1f3": "Réti Opening",
    "g1f3 d7d5 c2c4": "Réti Opening: Main Line",
    "f2f4": "Bird's Opening",
    "b2b3": "Nimzo-Larsen Attack",
    "g2g3": "King's Fianchetto Opening",
}

# Lines the AI is happy to play from its book (all sound mainstream openings).
_BOOK_LINES = [
    line.split() for line in OPENINGS
    if not line.startswith(("f2f4", "b2b3", "g2g3", "e2e4 e7e5 f2f4", "e2e4 e7e5 d2d4 e5d4"))
]


def opening_name(moves_uci: list[str]) -> str:
    """Longest matching opening name for the given move list (or '')."""
    name = ""
    for n in range(1, min(len(moves_uci), 12) + 1):
        key = " ".join(moves_uci[:n])
        if key in OPENINGS:
            name = OPENINGS[key]
    return name


def book_move(moves_uci: list[str], rng: random.Random | None = None) -> str | None:
    """Pick a book continuation for the game so far, if there is one."""
    rng = rng or random
    n = len(moves_uci)
    candidates = [line[n] for line in _BOOK_LINES if len(line) > n and line[:n] == moves_uci]
    if not candidates:
        return None
    return rng.choice(candidates)
