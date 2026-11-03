"""Chess rule helpers built on top of python-chess.

python-chess does the heavy lifting (legal moves, castling, en passant,
promotion, check/mate/draw detection). This module adds the small pieces of
knowledge the UI, coach and lessons need: names, values, safety checks and a
tiny forced-mate solver.
"""
from __future__ import annotations

import chess

PIECE_NAMES = {
    chess.PAWN: "Pawn",
    chess.KNIGHT: "Knight",
    chess.BISHOP: "Bishop",
    chess.ROOK: "Rook",
    chess.QUEEN: "Queen",
    chess.KING: "King",
}

# Fantasy titles shown next to the classic names.
PIECE_TITLES = {
    chess.PAWN: "Acolyte",
    chess.KNIGHT: "Spell-Knight",
    chess.BISHOP: "Sorcerer",
    chess.ROOK: "Golem Tower",
    chess.QUEEN: "Archmage",
    chess.KING: "High King",
}

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

PIECE_MOVES_HELP = {
    chess.PAWN: "moves 1 square forward (2 on its first move) and captures diagonally.",
    chess.KNIGHT: "moves in an L-shape (2 + 1 squares) and can jump over pieces.",
    chess.BISHOP: "slides any distance diagonally.",
    chess.ROOK: "slides any distance along ranks and files.",
    chess.QUEEN: "slides any distance in any straight line - rook + bishop combined.",
    chess.KING: "moves 1 square in any direction. Keep him safe!",
}

FACTION_NAMES = {chess.WHITE: "Celestial Order", chess.BLACK: "Arcane Shadow"}
COLOR_NAMES = {chess.WHITE: "White", chess.BLACK: "Black"}


def piece_label(piece_type: int) -> str:
    return PIECE_NAMES[piece_type]


def value(piece_type: int | None) -> int:
    return PIECE_VALUES.get(piece_type, 0) if piece_type else 0


def material(board: chess.Board, color: bool) -> int:
    return sum(PIECE_VALUES[pt] * len(board.pieces(pt, color)) for pt in PIECE_VALUES)


def captured_piece_type(board: chess.Board, move: chess.Move) -> int | None:
    """Type of the piece captured by ``move`` (handles en passant)."""
    if board.is_en_passant(move):
        return chess.PAWN
    piece = board.piece_at(move.to_square)
    return piece.piece_type if piece else None


def captured_square(board: chess.Board, move: chess.Move) -> int | None:
    if board.is_en_passant(move):
        return chess.square(chess.square_file(move.to_square), chess.square_rank(move.from_square))
    if board.piece_at(move.to_square):
        return move.to_square
    return None


def castling_rook_squares(board: chess.Board, move: chess.Move) -> tuple[int, int] | None:
    """(rook_from, rook_to) for a castling move, else None."""
    if not board.is_castling(move):
        return None
    rank = chess.square_rank(move.from_square)
    if board.is_kingside_castling(move):
        return chess.square(7, rank), chess.square(5, rank)
    return chess.square(0, rank), chess.square(3, rank)


def is_hanging(board: chess.Board, square: int) -> bool:
    """A piece is 'hanging' if the enemy can win material by capturing it.

    Simple rule: attacked and either undefended, or attacked by a cheaper piece.
    """
    piece = board.piece_at(square)
    if piece is None or piece.piece_type == chess.KING:
        return False
    enemy = not piece.color
    attackers = board.attackers(enemy, square)
    if not attackers:
        return False
    defenders = board.attackers(piece.color, square)
    if not defenders:
        return True
    cheapest = min(value(board.piece_type_at(sq)) or 100 for sq in attackers)
    return cheapest < value(piece.piece_type)


def hanging_pieces(board: chess.Board, color: bool) -> list[int]:
    squares = []
    for sq, piece in board.piece_map().items():
        if piece.color == color and is_hanging(board, sq):
            squares.append(sq)
    return sorted(squares, key=lambda s: -value(board.piece_type_at(s)))


def find_mate(board: chess.Board, moves: int) -> chess.Move | None:
    """Return a move that forces checkmate in at most ``moves`` moves, else None."""
    if moves <= 0:
        return None
    # Try checks first: they find mates much faster.
    ordered = sorted(board.legal_moves, key=lambda m: not board.gives_check(m))
    for move in ordered:
        board.push(move)
        try:
            if board.is_checkmate():
                return move
            if moves > 1 and not board.is_game_over() and _all_replies_lose(board, moves - 1):
                return move
        finally:
            board.pop()
    return None


def _all_replies_lose(board: chess.Board, moves: int) -> bool:
    for reply in board.legal_moves:
        board.push(reply)
        try:
            if find_mate(board, moves) is None:
                return False
        finally:
            board.pop()
    return True


def has_forced_mate(board: chess.Board, moves: int) -> bool:
    return find_mate(board, moves) is not None


def best_defence(board: chess.Board, mate_moves: int) -> chess.Move | None:
    """For the side being mated: the reply that delays mate the longest."""
    replies = list(board.legal_moves)
    if not replies:
        return None
    best, best_len = replies[0], -1
    for reply in replies:
        board.push(reply)
        try:
            length = mate_moves + 1
            for n in range(1, mate_moves + 1):
                if find_mate(board, n):
                    length = n
                    break
        finally:
            board.pop()
        if length > best_len:
            best, best_len = reply, length
    return best


def mate_holds(board_after_move: chess.Board, moves: int) -> bool:
    """After the attacker's move: does every defence still lose to mate in ``moves``?"""
    if board_after_move.is_checkmate():
        return True
    if board_after_move.is_game_over() or moves <= 0:
        return False
    return _all_replies_lose(board_after_move, moves)
