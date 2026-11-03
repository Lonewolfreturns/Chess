"""The Coach: grades moves, explains ideas in plain language, warns about threats.

Everything here is pure python-chess + the built-in engine, so it works in the
.exe with no internet and no external engine.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import chess

from . import rules
from .chess_ai import MATE_BOUND, SearchResult

N = rules.PIECE_NAMES

CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
CENTER_MASK = chess.BB_D4 | chess.BB_E4 | chess.BB_D5 | chess.BB_E5

# (max win-probability loss, label, symbol, colour)
GRADES = [
    (0.010, "Best", "!", "#5eead4"),
    (0.030, "Excellent", "", "#86efac"),
    (0.060, "Good", "", "#bef264"),
    (0.120, "Inaccuracy", "?!", "#facc15"),
    (0.220, "Mistake", "?", "#fb923c"),
    (9.999, "Blunder", "??", "#f87171"),
]


@dataclass
class MoveReview:
    label: str
    symbol: str
    color: str
    wp_loss: float
    cp_loss: int
    best_san: str
    html: str
    is_best: bool = False


@dataclass
class Features:
    good: list[str] = field(default_factory=list)
    bad: list[str] = field(default_factory=list)
    mate: bool = False
    check: bool = False
    wins_material: bool = False


def win_prob(cp: int) -> float:
    """Expected score for the side whose score this is (0..1)."""
    cp = max(-2000, min(2000, cp))
    return 1.0 / (1.0 + math.pow(10, -cp / 400.0))


def _score_cp(score: int) -> int:
    if score >= MATE_BOUND:
        return 3000
    if score <= -MATE_BOUND:
        return -3000
    return score


def _sq(sq: int) -> str:
    return chess.square_name(sq)


def _list(items: list[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


# ----------------------------------------------------------- move features
def move_features(board: chess.Board, move: chess.Move) -> Features:
    """Describe what a move does, from the mover's point of view."""
    f = Features()
    us = board.turn
    piece = board.piece_at(move.from_square)
    if piece is None:
        return f
    pt = piece.piece_type
    pname = N[pt]
    cap = rules.captured_piece_type(board, move)
    hanging_before = set(rules.hanging_pieces(board, us))

    if board.is_castling(move):
        f.good.append("castles - the King hides behind his pawns and a Rook joins the fight")
    if cap:
        csq = rules.captured_square(board, move)
        defended = bool(board.attackers(not us, csq))
        if not defended:
            f.good.append(f"captures a free {N[cap]}")
            f.wins_material = True
        elif rules.value(cap) > rules.value(pt):
            f.good.append(f"wins material - the {pname} takes a more valuable {N[cap]}")
            f.wins_material = True
        elif rules.value(cap) == rules.value(pt):
            f.good.append(f"trades {pname} for {N[cap]}")
        else:
            f.good.append(f"captures the {N[cap]}")
    if move.promotion:
        f.good.append(f"promotes the Pawn into a {N[move.promotion]}")

    after = board.copy(stack=False)
    after.push(move)
    if after.is_checkmate():
        f.mate = True
        f.good.insert(0, "delivers CHECKMATE")
        return f
    if after.is_check():
        f.check = True
        f.good.append("gives check")

    # Threats created by the moved piece (forks, attacks on bigger pieces).
    to = move.to_square
    moved_type = move.promotion or pt
    targets = []
    for sq in chess.scan_forward(after.attacks_mask(to) & after.occupied_co[not us]):
        t = after.piece_type_at(sq)
        if t == chess.KING:
            continue
        if rules.value(t) > rules.value(moved_type) or not after.attackers(not us, sq):
            targets.append(N[t])
    if after.is_check() and targets:
        f.good.append(f"forks the King and the {targets[0]}")
    elif len(targets) >= 2:
        f.good.append(f"forks the {targets[0]} and the {targets[1]}")
    elif targets:
        f.good.append(f"attacks the {targets[0]}")

    hanging_after = set(rules.hanging_pieces(after, us))
    if move.from_square in hanging_before and to not in hanging_after:
        f.good.append(f"moves the threatened {pname} to safety")
    saved = [s for s in hanging_before if s != move.from_square and s not in hanging_after]
    if saved:
        f.good.append(f"protects the {N[board.piece_type_at(saved[0])]} on {_sq(saved[0])}")

    # Opening principles.
    early = board.fullmove_number <= 12
    back_rank = 0 if us == chess.WHITE else 7
    if early and pt in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(move.from_square) == back_rank:
        f.good.append("develops a piece")
    if pt == chess.PAWN and to in CENTER:
        f.good.append("fights for the centre")
    elif pt in (chess.KNIGHT, chess.BISHOP) and after.attacks_mask(to) & CENTER_MASK:
        if early:
            f.good.append("eyes the centre")

    # Problems.
    if to in hanging_after and not (cap and rules.value(cap) >= rules.value(moved_type)):
        f.bad.append(f"the {N[moved_type]} on {_sq(to)} can be captured")
    new_hanging = [s for s in hanging_after if s != to and s not in hanging_before]
    if new_hanging:
        s = new_hanging[0]
        f.bad.append(f"it leaves the {N[after.piece_type_at(s)]} on {_sq(s)} unprotected")
    if early and pt == chess.KING and not board.is_castling(move) and after.queens:
        f.bad.append("moving the King early gives up castling and exposes him")
    if board.fullmove_number <= 5 and pt == chess.QUEEN:
        f.bad.append("bringing the Queen out early lets the enemy gain time by attacking her")
    if not after.is_check():
        threat = enemy_mate_threat(after)
        if threat:
            f.bad.append(f"it allows the enemy to checkmate with {threat}")
    return f


def enemy_mate_threat(board: chess.Board) -> str | None:
    """If the side to move can mate in one, return that move in SAN."""
    mate = rules.find_mate(board, 1)
    return board.san(mate) if mate else None


def threatened_mate_against(board: chess.Board) -> str | None:
    """If the opponent of the side to move threatens mate-in-1, return it."""
    if board.is_check():
        return None
    b = board.copy(stack=False)
    b.push(chess.Move.null())
    mate = rules.find_mate(b, 1)
    return b.san(mate) if mate else None


def describe(board: chess.Board, move: chess.Move) -> str:
    piece = board.piece_at(move.from_square)
    if board.is_castling(move):
        side = "kingside" if board.is_kingside_castling(move) else "queenside"
        return f"castle {side} ({board.san(move)})"
    return (f"{N[piece.piece_type]} {_sq(move.from_square)} → {_sq(move.to_square)} "
            f"({board.san(move)})")


# ----------------------------------------------------------------- reviews
def review_move(board_before: chess.Board, move: chess.Move,
                best: SearchResult, after: SearchResult) -> MoveReview:
    """Grade ``move`` using the best line before it and the evaluation after it."""
    best_move = best.move or move
    best_cp = _score_cp(best.score)
    played_cp = -_score_cp(after.score)
    is_best = move == best_move
    if is_best:
        played_cp = max(played_cp, best_cp)
    wp_loss = max(0.0, win_prob(best_cp) - win_prob(played_cp))
    cp_loss = max(0, best_cp - played_cp)

    label, symbol, color = GRADES[-1][1:]
    for limit, lb, sym, col in GRADES:
        if wp_loss <= limit:
            label, symbol, color = lb, sym, col
            break

    feats = move_features(board_before, move)
    if is_best and feats.bad and any("captured" in b for b in feats.bad) and not feats.mate:
        moved = board_before.piece_type_at(move.from_square)
        if rules.value(moved) >= 3 and best_cp > 50:
            label, symbol, color = "Brilliant", "!!", "#38bdf8"

    san = board_before.san(move)
    best_san = board_before.san(best_move)
    parts = [f"<b style='color:{color}'>{label} {symbol}</b> &nbsp;<b>{san}</b>"]

    what = _list(feats.good[:3])
    if what:
        parts.append(f"This move {what}.")
    if feats.mate:
        parts.append("The enemy King has nowhere to run. Glorious victory!")
    elif label in ("Inaccuracy", "Mistake", "Blunder"):
        if feats.bad:
            parts.append("<span style='color:#fca5a5'>Careful: " + _list(feats.bad[:2]) + ".</span>")
        if best.mate_in and best.mate_in > 0 and not feats.mate:
            parts.append(f"You missed a forced checkmate in {best.mate_in} starting with <b>{best_san}</b>!")
        else:
            bf = move_features(board_before, best_move)
            why = _list(bf.good[:2])
            parts.append(f"Better was <b>{best_san}</b>" + (f": it {why}." if why else "."))
    elif label in ("Good", "Excellent") and not is_best:
        parts.append(f"The top choice was <b>{best_san}</b>, but this is a fine move.")
    elif feats.bad and not is_best:
        parts.append("<span style='color:#fca5a5'>Note: " + _list(feats.bad[:1]) + ".</span>")

    return MoveReview(label, symbol, color, wp_loss, cp_loss, best_san, " ".join(parts), is_best)


def explain_hint(board: chess.Board, result: SearchResult) -> str:
    move = result.move
    if move is None:
        return "No moves available."
    feats = move_features(board, move)
    text = f"<b style='color:#7dd3fc'>Hint:</b> {describe(board, move)}."
    why = _list(feats.good[:3])
    if feats.mate:
        text += " It's <b>checkmate</b>!"
    elif result.mate_in and result.mate_in > 0:
        text += f" It starts a forced checkmate in {result.mate_in}!"
    elif why:
        text += f" It {why}."
    else:
        text += " It quietly improves your position and keeps your pieces safe."
    if len(result.pv) >= 2:
        b = board.copy(stack=False)
        line = []
        for m in result.pv[:4]:
            if m not in b.legal_moves:
                break
            line.append(b.san(m))
            b.push(m)
        if len(line) >= 2:
            text += f"<br><span style='color:#a8a29e'>Expected line: {' '.join(line)}</span>"
    return text


def threat_report(board: chess.Board) -> list[str]:
    """Warnings for the side to move about pieces in danger and mate threats."""
    us = board.turn
    alerts = []
    mate = threatened_mate_against(board)
    if mate:
        alerts.append(f"⚠ The enemy threatens <b>checkmate</b> with {mate}! Defend!")
    for sq in rules.hanging_pieces(board, us)[:2]:
        pt = board.piece_type_at(sq)
        attackers = board.attackers(not us, sq)
        att = min(attackers, key=lambda s: rules.value(board.piece_type_at(s)))
        alerts.append(f"⚠ Your {N[pt]} on {_sq(sq)} is attacked by the enemy "
                      f"{N[board.piece_type_at(att)]} on {_sq(att)}.")
    for sq in rules.hanging_pieces(board, not us)[:1]:
        pt = board.piece_type_at(sq)
        alerts.append(f"✦ Opportunity: the enemy {N[pt]} on {_sq(sq)} is weak - can you win it?")
    return alerts


def eval_text(score_white: int, mate_in_white: int | None = None) -> str:
    if mate_in_white is not None:
        side = "Celestial" if mate_in_white > 0 else "Arcane"
        return f"{side} mates in {abs(mate_in_white)}"
    pawns = score_white / 100
    if abs(pawns) < 0.4:
        return "Balanced battle"
    side = "Celestial" if pawns > 0 else "Arcane"
    a = abs(pawns)
    if a < 1.2:
        return f"{side} slightly better"
    if a < 2.5:
        return f"{side} clearly better"
    return f"{side} winning"


def accuracy(wp_losses: list[float]) -> float:
    """Lichess-style accuracy percentage from per-move win-probability losses."""
    if not wp_losses:
        return 100.0
    avg = sum(wp_losses) / len(wp_losses) * 100
    acc = 103.1668 * math.exp(-0.04354 * avg) - 3.1669
    return max(0.0, min(100.0, acc))
