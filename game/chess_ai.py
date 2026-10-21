"""Built-in chess AI.

A classic alpha-beta engine written in pure Python on top of python-chess:
iterative deepening, principal variation search, quiescence search,
transposition table, null-move pruning, late-move reductions, killer/history
move ordering, an opening book and tapered piece-square evaluation.

Strength is limited by Python's speed, which is perfect for a game: the top
level is a solid club player, the lowest level is very beatable.
If a ``stockfish`` executable is found next to the game (or in ./engines),
an extra "Stockfish" level becomes available.
"""
from __future__ import annotations

import os
import random
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

import chess

from . import openings

MATE = 100_000
MATE_BOUND = MATE - 1_000
INF = 10 ** 9
EXACT, LOWER, UPPER = 0, 1, 2

VAL = [0, 100, 320, 330, 500, 900, 0]
PHASE_W = [0, 0, 1, 1, 2, 4, 0]

# Piece-square tables, written from White's point of view with rank 8 first.
_PST = {
    chess.PAWN: [
        0, 0, 0, 0, 0, 0, 0, 0,
        50, 50, 50, 50, 50, 50, 50, 50,
        10, 10, 20, 30, 30, 20, 10, 10,
        5, 5, 10, 25, 25, 10, 5, 5,
        0, 0, 0, 20, 20, 0, 0, 0,
        5, -5, -10, 0, 0, -10, -5, 5,
        5, 10, 10, -20, -20, 10, 10, 5,
        0, 0, 0, 0, 0, 0, 0, 0],
    chess.KNIGHT: [
        -50, -40, -30, -30, -30, -30, -40, -50,
        -40, -20, 0, 0, 0, 0, -20, -40,
        -30, 0, 10, 15, 15, 10, 0, -30,
        -30, 5, 15, 20, 20, 15, 5, -30,
        -30, 0, 15, 20, 20, 15, 0, -30,
        -30, 5, 10, 15, 15, 10, 5, -30,
        -40, -20, 0, 5, 5, 0, -20, -40,
        -50, -40, -30, -30, -30, -30, -40, -50],
    chess.BISHOP: [
        -20, -10, -10, -10, -10, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 10, 10, 5, 0, -10,
        -10, 5, 5, 10, 10, 5, 5, -10,
        -10, 0, 10, 10, 10, 10, 0, -10,
        -10, 10, 10, 10, 10, 10, 10, -10,
        -10, 5, 0, 0, 0, 0, 5, -10,
        -20, -10, -10, -10, -10, -10, -10, -20],
    chess.ROOK: [
        0, 0, 0, 0, 0, 0, 0, 0,
        5, 10, 10, 10, 10, 10, 10, 5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        0, 0, 0, 5, 5, 0, 0, 0],
    chess.QUEEN: [
        -20, -10, -10, -5, -5, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 5, 5, 5, 0, -10,
        -5, 0, 5, 5, 5, 5, 0, -5,
        0, 0, 5, 5, 5, 5, 0, -5,
        -10, 5, 5, 5, 5, 5, 0, -10,
        -10, 0, 5, 0, 0, 0, 0, -10,
        -20, -10, -10, -5, -5, -10, -10, -20],
}
_KING_MG = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    20, 20, 0, 0, 0, 0, 20, 20,
    20, 30, 10, 0, 0, 10, 30, 20]
_KING_EG = [
    -50, -40, -30, -20, -20, -30, -40, -50,
    -30, -20, -10, 0, 0, -10, -20, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -30, 0, 0, 0, 0, -30, -30,
    -50, -30, -30, -30, -30, -30, -30, -50]

# Tables indexed by python-chess square (a1 = 0). White uses the mirrored index.
W_PST = [[0] * 64 for _ in range(7)]
B_PST = [[0] * 64 for _ in range(7)]
for _pt, _table in _PST.items():
    for _sq in range(64):
        W_PST[_pt][_sq] = VAL[_pt] + _table[_sq ^ 56]
        B_PST[_pt][_sq] = VAL[_pt] + _table[_sq]
W_KMG = [_KING_MG[s ^ 56] for s in range(64)]
B_KMG = [_KING_MG[s] for s in range(64)]
W_KEG = [_KING_EG[s ^ 56] for s in range(64)]
B_KEG = [_KING_EG[s] for s in range(64)]
CENTER_DIST = [max(3 - (s & 7), (s & 7) - 4) + max(3 - (s >> 3), (s >> 3) - 4) for s in range(64)]

_scan = chess.scan_forward


def evaluate(board: chess.Board) -> int:
    """Static evaluation in centipawns from the side to move's point of view."""
    occ_w = board.occupied_co[chess.WHITE]
    occ_b = board.occupied_co[chess.BLACK]
    score = 0
    phase = 0
    mat_w = mat_b = 0
    for pt, bb in ((1, board.pawns), (2, board.knights), (3, board.bishops),
                   (4, board.rooks), (5, board.queens)):
        w = bb & occ_w
        b = bb & occ_b
        if w:
            tw = W_PST[pt]
            for sq in _scan(w):
                score += tw[sq]
            cnt = w.bit_count()
            mat_w += VAL[pt] * cnt
            phase += PHASE_W[pt] * cnt
        if b:
            tb = B_PST[pt]
            for sq in _scan(b):
                score -= tb[sq]
            cnt = b.bit_count()
            mat_b += VAL[pt] * cnt
            phase += PHASE_W[pt] * cnt
    if (board.bishops & occ_w).bit_count() >= 2:
        score += 30
    if (board.bishops & occ_b).bit_count() >= 2:
        score -= 30

    if phase > 24:
        phase = 24
    wk = board.king(chess.WHITE)
    bk = board.king(chess.BLACK)
    if wk is not None and bk is not None:
        mg = W_KMG[wk] - B_KMG[bk]
        eg = W_KEG[wk] - B_KEG[bk]
        score += (mg * phase + eg * (24 - phase)) // 24
        # Mop-up: when winning an endgame, drive the enemy king to the edge.
        if phase <= 8:
            diff = mat_w - mat_b
            if diff >= 300:
                score += 10 * CENTER_DIST[bk] + 4 * (14 - chess.square_manhattan_distance(wk, bk))
            elif diff <= -300:
                score -= 10 * CENTER_DIST[wk] + 4 * (14 - chess.square_manhattan_distance(wk, bk))

    score += 10 if board.turn else -10  # tempo
    return score if board.turn == chess.WHITE else -score


def _tkey(board: chess.Board):
    return board._transposition_key()  # noqa: SLF001 - fast position key


class SearchTimeout(Exception):
    pass


@dataclass
class SearchResult:
    move: chess.Move | None
    score: int = 0            # centipawns, side to move's point of view
    depth: int = 0
    pv: list = field(default_factory=list)
    nodes: int = 0
    seconds: float = 0.0
    book: bool = False

    @property
    def mate_in(self) -> int | None:
        """Moves to mate: positive = side to move mates, negative = gets mated."""
        if self.score >= MATE_BOUND:
            return (MATE - self.score + 1) // 2
        if self.score <= -MATE_BOUND:
            return -((MATE + self.score + 1) // 2)
        return None

    def score_text(self) -> str:
        m = self.mate_in
        if m is not None:
            return f"#{m}" if m > 0 else f"#-{abs(m)}"
        return f"{self.score / 100:+.2f}"


class Engine:
    """Alpha-beta searcher. Not thread safe: use one instance per thread."""

    def __init__(self):
        self.tt: dict = {}
        self.nodes = 0
        self.deadline = 0.0
        self.stop_event: threading.Event | None = None
        self.killers: list = []
        self.history: dict = {}
        self.rep: dict = {}

    # ------------------------------------------------------------------ public
    def search(self, board: chess.Board, max_depth: int = 4, time_limit: float = 2.0,
               stop_event: threading.Event | None = None) -> SearchResult:
        board = board.copy()
        start = time.perf_counter()
        self._prepare(board, time_limit, stop_event)

        root_moves = self._order(board, None, 0)
        if not root_moves:
            return SearchResult(None, -MATE if board.is_check() else 0)
        if len(root_moves) == 1:
            return SearchResult(root_moves[0], evaluate(board), 1, [root_moves[0]], 1,
                                time.perf_counter() - start)

        best_move, best_score, done_depth = root_moves[0], 0, 0
        root_len = len(board.move_stack)
        for depth in range(1, max_depth + 1):
            try:
                score, move = self._root(board, depth, root_moves)
            except SearchTimeout:
                while len(board.move_stack) > root_len:
                    board.pop()
                break
            best_move, best_score, done_depth = move, score, depth
            root_moves.remove(move)
            root_moves.insert(0, move)
            elapsed = time.perf_counter() - start
            if abs(score) >= MATE_BOUND or elapsed > time_limit * 0.5:
                break
        pv = self._pv(board, best_move, done_depth)
        return SearchResult(best_move, best_score, done_depth, pv, self.nodes,
                            time.perf_counter() - start)

    def score_moves(self, board: chess.Board, depth: int, time_limit: float = 2.0,
                    stop_event: threading.Event | None = None) -> list[tuple[int, chess.Move]]:
        """Exact-ish score for every root move (used by the weaker levels)."""
        board = board.copy()
        self._prepare(board, time_limit, stop_event)
        results = []
        root_key = _tkey(board)
        self.rep[root_key] = self.rep.get(root_key, 0) + 1
        for move in self._order(board, None, 0):
            board.push(move)
            try:
                score = -self._negamax(board, depth - 1, -INF, INF, 1, True)
            except SearchTimeout:
                board.pop()
                break
            board.pop()
            results.append((score, move))
        return results

    # ---------------------------------------------------------------- internals
    def _prepare(self, board, time_limit, stop_event):
        self.deadline = time.perf_counter() + time_limit
        self.stop_event = stop_event
        self.nodes = 0
        self.killers = [[None, None] for _ in range(130)]
        self.history = {}
        if len(self.tt) > 600_000:
            self.tt.clear()
        # Count earlier positions so the search knows about repetition draws.
        self.rep = {}
        tmp = board.copy()
        while tmp.move_stack:
            tmp.pop()
            k = _tkey(tmp)
            self.rep[k] = self.rep.get(k, 0) + 1

    def _check_time(self):
        if time.perf_counter() > self.deadline or (self.stop_event and self.stop_event.is_set()):
            raise SearchTimeout

    def _root(self, board, depth, moves):
        alpha, beta = -INF, INF
        best_move, best = moves[0], -INF
        key = _tkey(board)
        self.rep[key] = self.rep.get(key, 0) + 1
        try:
            for i, move in enumerate(moves):
                board.push(move)
                if i == 0:
                    score = -self._negamax(board, depth - 1, -beta, -alpha, 1, True)
                else:
                    score = -self._negamax(board, depth - 1, -alpha - 1, -alpha, 1, True)
                    if alpha < score < beta:
                        score = -self._negamax(board, depth - 1, -beta, -alpha, 1, True)
                board.pop()
                if score > best:
                    best, best_move = score, move
                if score > alpha:
                    alpha = score
        finally:
            self.rep[key] -= 1
        self.tt[key] = (depth, EXACT, best, best_move)
        return best, best_move

    def _negamax(self, board, depth, alpha, beta, ply, can_null):
        self.nodes += 1
        if not self.nodes & 1023:
            self._check_time()
        key = _tkey(board)
        if board.halfmove_clock >= 100 or self.rep.get(key):
            return 0
        if ply >= 64:
            return evaluate(board)

        in_check = board.is_check()
        if in_check:
            depth += 1
        if depth <= 0:
            return self._quiesce(board, alpha, beta, ply, 0)

        tt_move = None
        entry = self.tt.get(key)
        if entry is not None:
            e_depth, e_flag, e_score, tt_move = entry
            if e_depth >= depth:
                if e_score >= MATE_BOUND:
                    e_score -= ply
                elif e_score <= -MATE_BOUND:
                    e_score += ply
                if e_flag == EXACT:
                    return e_score
                if e_flag == LOWER and e_score >= beta:
                    return e_score
                if e_flag == UPPER and e_score <= alpha:
                    return e_score

        if (can_null and not in_check and depth >= 3 and beta < MATE_BOUND
                and (board.occupied_co[board.turn] & ~board.pawns & ~board.kings)):
            board.push(chess.Move.null())
            score = -self._negamax(board, depth - 3, -beta, -beta + 1, ply + 1, False)
            board.pop()
            if score >= beta:
                return beta

        moves = self._order(board, tt_move, ply)
        if not moves:
            return -MATE + ply if in_check else 0

        alpha_orig = alpha
        best, best_move = -INF, None
        self.rep[key] = self.rep.get(key, 0) + 1
        for i, move in enumerate(moves):
            quiet = move.promotion is None and not board.is_capture(move)
            board.push(move)
            if i == 0:
                score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1, True)
            else:
                if i >= 4 and depth >= 3 and quiet and not in_check and not board.is_check():
                    score = -self._negamax(board, depth - 2, -alpha - 1, -alpha, ply + 1, True)
                else:
                    score = alpha + 1
                if score > alpha:
                    score = -self._negamax(board, depth - 1, -alpha - 1, -alpha, ply + 1, True)
                    if alpha < score < beta:
                        score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1, True)
            board.pop()
            if score > best:
                best, best_move = score, move
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        if quiet:
                            k = self.killers[ply]
                            if k[0] != move:
                                k[1], k[0] = k[0], move
                            hk = (move.from_square, move.to_square)
                            self.history[hk] = self.history.get(hk, 0) + depth * depth
                        break
        self.rep[key] -= 1

        flag = EXACT
        if best <= alpha_orig:
            flag = UPPER
        elif best >= beta:
            flag = LOWER
        stored = best
        if stored >= MATE_BOUND:
            stored += ply
        elif stored <= -MATE_BOUND:
            stored -= ply
        self.tt[key] = (depth, flag, stored, best_move)
        return best

    def _quiesce(self, board, alpha, beta, ply, qdepth):
        self.nodes += 1
        if not self.nodes & 1023:
            self._check_time()
        if board.is_check():
            moves = self._order(board, None, min(ply, 127))
            if not moves:
                return -MATE + ply
            if qdepth > 6:
                return evaluate(board)
            best = -INF
            for move in moves:
                board.push(move)
                score = -self._quiesce(board, -beta, -alpha, ply + 1, qdepth + 1)
                board.pop()
                if score > best:
                    best = score
                    if score > alpha:
                        alpha = score
                        if alpha >= beta:
                            break
            return best

        stand = evaluate(board)
        if stand >= beta:
            return stand
        if stand > alpha:
            alpha = stand
        if qdepth > 8:
            return stand

        caps = []
        for move in board.generate_legal_captures():
            victim = board.piece_type_at(move.to_square) or chess.PAWN
            if stand + VAL[victim] + 200 < alpha and not move.promotion:
                continue  # delta pruning: even winning this piece can't help
            attacker = board.piece_type_at(move.from_square)
            caps.append((VAL[victim] * 10 - VAL[attacker], move))
        caps.sort(key=lambda c: c[0], reverse=True)
        for _, move in caps:
            board.push(move)
            score = -self._quiesce(board, -beta, -alpha, ply + 1, qdepth + 1)
            board.pop()
            if score >= beta:
                return score
            if score > alpha:
                alpha = score
        return alpha

    def _order(self, board, tt_move, ply):
        killers = self.killers[ply] if ply < len(self.killers) else (None, None)
        history = self.history
        scored = []
        for m in board.legal_moves:
            if m == tt_move:
                s = 10_000_000
            elif board.is_capture(m):
                victim = board.piece_type_at(m.to_square) or chess.PAWN
                s = 1_000_000 + VAL[victim] * 10 - VAL[board.piece_type_at(m.from_square)] // 10
            elif m.promotion:
                s = 900_000 + VAL[m.promotion]
            elif m == killers[0] or m == killers[1]:
                s = 800_000
            else:
                s = history.get((m.from_square, m.to_square), 0)
            scored.append((s, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored]

    def _pv(self, board, first, depth):
        pv = []
        if first is None:
            return pv
        b = board.copy(stack=False)
        move = first
        seen = set()
        for _ in range(max(depth, 1) + 4):
            if move is None or move not in b.legal_moves:
                break
            pv.append(move)
            b.push(move)
            k = _tkey(b)
            if k in seen:
                break
            seen.add(k)
            entry = self.tt.get(k)
            move = entry[3] if entry else None
        return pv


# ---------------------------------------------------------------- difficulty
@dataclass(frozen=True)
class Level:
    number: int
    name: str
    depth: int
    time: float
    noise: int = 0          # random centipawn noise added to root moves
    blunder: float = 0.0    # chance of a purely random move
    description: str = ""


LEVELS = [
    Level(1, "Apprentice", 1, 1.0, noise=160, blunder=0.12,
          description="Just learning spells. Makes plenty of mistakes."),
    Level(2, "Adept", 2, 1.5, noise=60, blunder=0.04,
          description="Knows the basics, still drops pieces sometimes."),
    Level(3, "Sorcerer", 3, 1.5,
          description="Solid tactics. A real challenge for beginners."),
    Level(4, "Archmage", 6, 3.0,
          description="Strong club-level play. Thinks a few seconds."),
    Level(5, "Grand Wizard", 10, 6.0,
          description="The strongest built-in mage. Takes its time."),
]


def find_stockfish() -> str | None:
    """Look for a Stockfish binary next to the program, in ./engines or PATH."""
    roots = []
    if getattr(sys, "frozen", False):
        roots.append(os.path.dirname(sys.executable))
    roots.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    roots.append(os.getcwd())
    for root in roots:
        for folder in (root, os.path.join(root, "engines")):
            if not os.path.isdir(folder):
                continue
            for name in sorted(os.listdir(folder)):
                low = name.lower()
                if low.startswith("stockfish") and (low.endswith(".exe") or "." not in low):
                    path = os.path.join(folder, name)
                    if os.path.isfile(path):
                        return path
    return shutil.which("stockfish")


class StockfishPlayer:
    """Thin wrapper around a UCI engine process (optional)."""

    def __init__(self, path: str):
        import chess.engine
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        self._engine = chess.engine.SimpleEngine.popen_uci(path, **kwargs)
        self._lock = threading.Lock()

    def search(self, board: chess.Board, time_limit: float) -> SearchResult:
        import chess.engine
        with self._lock:
            info = self._engine.analyse(board, chess.engine.Limit(time=time_limit))
        pv = info.get("pv", [])
        pov = info["score"].pov(board.turn)
        if pov.is_mate():
            m = pov.mate()
            score = MATE - (2 * m - 1) if m > 0 else -MATE + 2 * abs(m)
        else:
            score = pov.score()
        return SearchResult(pv[0] if pv else None, score, info.get("depth", 0), pv,
                            info.get("nodes", 0), time_limit)

    def close(self):
        try:
            self._engine.quit()
        except Exception:
            pass


_stockfish: StockfishPlayer | None = None
_stockfish_checked = False


def stockfish() -> StockfishPlayer | None:
    global _stockfish, _stockfish_checked
    if not _stockfish_checked:
        _stockfish_checked = True
        path = find_stockfish()
        if path:
            try:
                _stockfish = StockfishPlayer(path)
            except Exception:
                _stockfish = None
    return _stockfish


STOCKFISH_LEVEL = Level(6, "Stockfish", 20, 2.0, description="External Stockfish engine.")


def available_levels() -> list[Level]:
    return LEVELS + ([STOCKFISH_LEVEL] if find_stockfish() else [])


def level_by_number(n: int) -> Level:
    for lv in available_levels():
        if lv.number == n:
            return lv
    return LEVELS[2]


def choose_move(board: chess.Board, level: Level, engine: Engine | None = None,
                stop_event: threading.Event | None = None,
                rng: random.Random | None = None) -> SearchResult:
    """Pick the AI's move for ``board`` at the given difficulty."""
    rng = rng or random.Random()
    engine = engine or Engine()

    # Opening book (only from the standard start position).
    if board.ply() < 12 and _from_start(board):
        uci = openings.book_move([m.uci() for m in board.move_stack], rng)
        if uci:
            move = chess.Move.from_uci(uci)
            if move in board.legal_moves:
                time.sleep(0.35)  # feels more natural than an instant reply
                return SearchResult(move, evaluate(board), 0, [move], 0, 0.35, book=True)

    if level.number == STOCKFISH_LEVEL.number and stockfish():
        return stockfish().search(board, level.time)

    if level.blunder and rng.random() < level.blunder:
        moves = list(board.legal_moves)
        if moves:
            time.sleep(0.3)
            move = rng.choice(moves)
            return SearchResult(move, evaluate(board), 0, [move])

    if level.noise:
        scored = engine.score_moves(board, level.depth, level.time, stop_event)
        if scored:
            pick = max(scored, key=lambda sm: sm[0] + rng.gauss(0, level.noise))
            return SearchResult(pick[1], pick[0], level.depth, [pick[1]], engine.nodes)

    return engine.search(board, level.depth, level.time, stop_event)


def analyse(board: chess.Board, time_limit: float = 1.0, engine: Engine | None = None,
            stop_event: threading.Event | None = None, depth: int = 12) -> SearchResult:
    """Best move + evaluation, used for hints, the coach and the eval bar."""
    sf = stockfish()
    if sf is not None:
        try:
            return sf.search(board, min(time_limit, 0.8))
        except Exception:
            pass
    engine = engine or Engine()
    return engine.search(board, depth, time_limit, stop_event)


def _from_start(board: chess.Board) -> bool:
    root = board.root()
    return root.board_fen() == chess.STARTING_BOARD_FEN and root.turn == chess.WHITE
