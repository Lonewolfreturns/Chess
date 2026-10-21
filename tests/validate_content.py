"""Check that every lesson and puzzle is valid and solvable.

Run from the project folder:  python tests/validate_content.py
"""
from __future__ import annotations

import os
import sys

import chess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import rules  # noqa: E402
from game.lessons import LESSONS  # noqa: E402
from game.puzzles import PUZZLES  # noqa: E402

errors: list[str] = []


def fail(where: str, msg: str):
    errors.append(f"{where}: {msg}")


def targets_done(board: chess.Board, player: bool, targets) -> bool:
    if targets:
        return all(board.color_at(chess.parse_square(t)) != (not player) for t in targets)
    return not board.occupied_co[not player]


def solvable_passive(board: chess.Board, goal: str, targets, par: int) -> int | None:
    """Breadth-first search with a passive opponent. Returns moves needed."""
    player = board.turn
    frontier = [board]
    seen = {board.board_fen()}
    for depth in range(1, max(par, 1) + 3):
        nxt = []
        for b in frontier:
            for move in b.legal_moves:
                c = b.copy(stack=False)
                c.push(move)
                if goal == "capture" and targets_done(c, player, targets):
                    return depth
                if goal == "reach" and any(c.color_at(chess.parse_square(t)) == player for t in targets):
                    return depth
                c.push(chess.Move.null())
                key = c.board_fen()
                if key not in seen:
                    seen.add(key)
                    nxt.append(c)
        frontier = nxt
    return None


for lesson in LESSONS:
    for i, step in enumerate(lesson.steps):
        where = f"lesson {lesson.id} step {i + 1}"
        try:
            board = chess.Board(step.fen)
        except ValueError as exc:
            fail(where, f"bad FEN {exc}")
            continue
        if step.goal in ("capture", "reach"):
            need = solvable_passive(board, step.goal, step.targets, step.par)
            if need is None:
                fail(where, "not solvable")
            elif step.par and need > step.par:
                fail(where, f"needs {need} moves but par is {step.par}")
        elif step.goal == "solution":
            b = board.copy()
            for uci in step.solution:
                move = chess.Move.from_uci(uci)
                if move not in b.legal_moves:
                    fail(where, f"illegal solution move {uci}")
                    break
                b.push(move)
        elif step.goal == "mate":
            if not board.is_valid():
                fail(where, f"invalid position {board.status()!r}")
            if rules.find_mate(board, 1) is None:
                fail(where, "no mate in 1")
        elif step.goal == "check":
            if not any(board.gives_check(m) for m in board.legal_moves):
                fail(where, "no checking move")
        elif step.goal == "any":
            if not board.is_check() or not any(True for _ in board.legal_moves):
                fail(where, "should be in check with legal moves")
        elif step.goal == "info":
            pass
        else:
            fail(where, f"unknown goal {step.goal}")
        if "stalemate" in step.title.lower() and not board.is_stalemate():
            fail(where, "expected a stalemate position")

for p in PUZZLES:
    where = f"puzzle {p.id}"
    board = chess.Board(p.fen)
    if not board.is_valid():
        fail(where, f"invalid position {board.status()!r}")
        continue
    if p.kind == "mate":
        if rules.find_mate(board, p.moves) is None:
            fail(where, f"no forced mate in {p.moves}")
        if p.moves > 1 and rules.find_mate(board, p.moves - 1):
            fail(where, f"has a shorter mate than {p.moves}")
    else:
        b = board.copy()
        mover = b.turn
        before = rules.material(b, mover) - rules.material(b, not mover)
        for uci in p.solution:
            move = chess.Move.from_uci(uci)
            if move not in b.legal_moves:
                fail(where, f"illegal solution move {uci}")
                break
            b.push(move)
        after = rules.material(b, mover) - rules.material(b, not mover)
        if after <= before:
            fail(where, "solution does not win material")

if errors:
    print("PROBLEMS FOUND:")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print(f"All good: {sum(len(l.steps) for l in LESSONS)} lesson steps, {len(PUZZLES)} puzzles.")
