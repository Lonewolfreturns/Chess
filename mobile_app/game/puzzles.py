"""Spell Puzzles.

kind == "mate": any move that keeps a forced mate in the remaining moves is
accepted, and the defender replies with its most stubborn defence.
kind == "win":  play the exact solution line (player moves and scripted replies
alternate).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Puzzle:
    id: str
    title: str
    fen: str
    kind: str                 # "mate" or "win"
    moves: int = 1            # mate in N (kind == "mate")
    solution: tuple[str, ...] = ()
    rating: int = 800
    theme: str = ""
    hint: str = ""

    @property
    def goal_text(self) -> str:
        side = "White" if " w " in self.fen else "Black"
        if self.kind == "mate":
            return f"{side} to move - checkmate in {self.moves}."
        return f"{side} to move - win material."


PUZZLES: list[Puzzle] = [
    Puzzle("p01", "Back-Rank Strike", "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1", "mate", 1,
           rating=500, theme="Back rank", hint="The 8th rank is undefended."),
    Puzzle("p02", "The Scholar's Spell", "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
           "mate", 1, rating=550, theme="f7 weakness", hint="f7 is only defended by the King."),
    Puzzle("p03", "Fool's Fate", "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2",
           "mate", 1, rating=500, theme="Exposed king", hint="The e1-h4 diagonal is wide open."),
    Puzzle("p04", "Smothered!", "6rk/6pp/8/6N1/8/8/8/6K1 w - - 0 1", "mate", 1,
           rating=650, theme="Smothered mate", hint="A Knight jump."),
    Puzzle("p05", "Royal Escort", "k7/8/1K6/8/8/8/7Q/8 w - - 0 1", "mate", 1,
           rating=550, theme="Queen mate", hint="Control the whole back rank."),
    Puzzle("p06", "The Corridor", "1k6/ppp5/8/8/8/8/8/4R1K1 w - - 0 1", "mate", 1,
           rating=500, theme="Back rank", hint="The King is boxed in by his own Pawns."),
    Puzzle("p07", "Anastasia's Mate", "5r2/4Nppk/8/R7/8/8/8/4K3 w - - 0 1", "mate", 1,
           rating=900, theme="Knight + Rook", hint="The Knight already guards g8 and g6."),
    Puzzle("p08", "Arabian Nights", "7k/R7/5N2/8/8/8/8/6K1 w - - 0 1", "mate", 1,
           rating=800, theme="Knight + Rook", hint="The Knight protects h7."),
    Puzzle("p09", "Ladder of Doom", "k7/7R/8/8/8/8/8/K5R1 w - - 0 1", "mate", 1,
           rating=450, theme="Two rooks", hint="One Rook holds the 7th, the other strikes."),
    Puzzle("p10", "Epaulette", "3rkr2/8/8/8/8/8/Q7/6K1 w - - 0 1", "mate", 1,
           rating=850, theme="Epaulette mate", hint="The King's own Rooks are his prison bars."),
    Puzzle("p11", "Kiss of Death", "6k1/5p1p/5PpQ/8/8/8/8/6K1 w - - 0 1", "mate", 1,
           rating=700, theme="Queen + pawn", hint="The f6 Pawn supports the Queen."),
    Puzzle("p12", "Shadow's Revenge", "2r3k1/8/8/8/8/8/5PPP/6K1 b - - 0 1", "mate", 1,
           rating=450, theme="Back rank", hint="White forgot to make luft."),
    Puzzle("p13", "Rook Roller", "6k1/8/8/8/8/8/R7/1R4K1 w - - 0 1", "mate", 2,
           rating=900, theme="Two rooks", hint="First cut off the 7th rank."),
    Puzzle("p14", "King's March", "7k/8/8/5K2/8/8/8/6Q1 w - - 0 1", "mate", 2,
           rating=1000, theme="Queen mate", hint="Bring your King closer first."),
    Puzzle("p15", "Philidor's Legacy", "r6k/6pp/7N/8/2Q5/8/8/6K1 w - - 0 1", "mate", 2,
           rating=1300, theme="Queen sacrifice", hint="Sacrifice the Queen on g8!"),
    Puzzle("p16", "Knight's Fork", "r3k3/8/8/3N4/8/8/8/4K3 w - - 0 1", "win",
           solution=("d5c7", "e8d7", "c7a8"), rating=700, theme="Fork", hint="Check the King and hit the Rook."),
    Puzzle("p17", "Diagonal Skewer", "6q1/8/8/3k4/8/8/8/1B5K w - - 0 1", "win",
           solution=("b1a2", "d5d6", "a2g8"), rating=900, theme="Skewer", hint="Check along the a2-g8 diagonal."),
    Puzzle("p18", "Discovered Fury", "q3k3/8/8/8/4B3/8/8/4R1K1 w - - 0 1", "win",
           solution=("e4d5", "e8f8", "d5a8"), rating=1000, theme="Discovered attack",
           hint="Move the Bishop to reveal the Rook's check."),
    Puzzle("p19", "Pawn Fork", "4k3/8/3n1n2/8/4P3/8/8/4K3 w - - 0 1", "win",
           solution=("e4e5", "f6d5", "e5d6"), rating=750, theme="Fork", hint="Even a Pawn can fork!"),
    Puzzle("p20", "The Pin", "4k3/8/2n5/1B6/3P4/8/8/4K3 w - - 0 1", "win",
           solution=("d4d5", "e8e7", "d5c6"), rating=800, theme="Pin", hint="The Knight cannot move."),
]


def puzzle_by_id(pid: str) -> Puzzle | None:
    return next((p for p in PUZZLES if p.id == pid), None)
