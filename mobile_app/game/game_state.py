"""Game state: the live board plus move history, undo/redo, results and PGN."""
from __future__ import annotations

import datetime
import io
from dataclasses import dataclass

import chess
import chess.pgn

from . import rules

TERMINATION_TEXT = {
    chess.Termination.CHECKMATE: "Checkmate",
    chess.Termination.STALEMATE: "Stalemate",
    chess.Termination.INSUFFICIENT_MATERIAL: "Insufficient material",
    chess.Termination.SEVENTYFIVE_MOVES: "75-move rule",
    chess.Termination.FIVEFOLD_REPETITION: "Fivefold repetition",
    chess.Termination.FIFTY_MOVES: "50-move rule",
    chess.Termination.THREEFOLD_REPETITION: "Threefold repetition",
}


@dataclass
class MoveRecord:
    move: chess.Move
    san: str
    color: bool
    piece_type: int
    captured: int | None
    captured_sq: int | None
    castle_rook: tuple[int, int] | None
    promotion: int | None
    is_check: bool
    is_mate: bool
    annotation: str = ""     # coach symbol: !!, !, ?!, ?, ??
    quality: str = ""        # coach label: Best, Good, Mistake ...
    comment: str = ""


@dataclass
class GameResult:
    result: str              # "1-0", "0-1", "1/2-1/2"
    reason: str
    winner: bool | None      # chess.WHITE / chess.BLACK / None for draws


class GameState:
    def __init__(self, fen: str | None = None):
        self.board = chess.Board(fen) if fen else chess.Board()
        self.start_fen = self.board.fen()
        self.records: list[MoveRecord] = []
        self.redo_stack: list[chess.Move] = []
        self._forced_result: GameResult | None = None

    # ------------------------------------------------------------- moves
    def make_record(self, move: chess.Move) -> MoveRecord:
        b = self.board
        piece = b.piece_at(move.from_square)
        san = b.san(move)
        return MoveRecord(
            move=move,
            san=san,
            color=b.turn,
            piece_type=piece.piece_type if piece else chess.PAWN,
            captured=rules.captured_piece_type(b, move),
            captured_sq=rules.captured_square(b, move),
            castle_rook=rules.castling_rook_squares(b, move),
            promotion=move.promotion,
            is_check=san.endswith("+") or san.endswith("#"),
            is_mate=san.endswith("#"),
        )

    def push(self, move: chess.Move, keep_redo: bool = False) -> MoveRecord:
        record = self.make_record(move)
        self.board.push(move)
        self.records.append(record)
        if not keep_redo:
            self.redo_stack.clear()
        return record

    def push_null(self):
        """Pass the turn (used by lessons where the opponent stands still)."""
        self.board.push(chess.Move.null())

    def undo(self) -> MoveRecord | None:
        if not self.board.move_stack:
            return None
        move = self.board.pop()
        if move == chess.Move.null():
            return self.undo()
        self._forced_result = None
        record = self.records.pop() if self.records else None
        self.redo_stack.append(move)
        return record

    def redo(self) -> MoveRecord | None:
        if not self.redo_stack:
            return None
        move = self.redo_stack.pop()
        if move not in self.board.legal_moves:
            self.redo_stack.clear()
            return None
        return self.push(move, keep_redo=True)

    @property
    def ply(self) -> int:
        return len(self.records)

    def moves_uci(self) -> list[str]:
        return [m.uci() for m in self.board.move_stack]

    def board_at(self, ply: int) -> chess.Board:
        """Position after ``ply`` half-moves (0 = start position)."""
        b = chess.Board(self.start_fen)
        for move in self.board.move_stack[:ply]:
            b.push(move)
        return b

    def last_record(self) -> MoveRecord | None:
        return self.records[-1] if self.records else None

    def captured_by(self, color: bool) -> list[int]:
        """Piece types captured *by* ``color`` (i.e. lost by the other side)."""
        return sorted((r.captured for r in self.records if r.color == color and r.captured),
                      key=lambda pt: -rules.value(pt))

    def material_balance(self) -> int:
        return rules.material(self.board, chess.WHITE) - rules.material(self.board, chess.BLACK)

    # ------------------------------------------------------------- results
    def set_result(self, result: str, reason: str, winner: bool | None):
        self._forced_result = GameResult(result, reason, winner)

    def outcome(self) -> GameResult | None:
        if self._forced_result:
            return self._forced_result
        o = self.board.outcome(claim_draw=True)
        if o is None:
            return None
        reason = TERMINATION_TEXT.get(o.termination, "Game over")
        return GameResult(o.result(), reason, o.winner)

    def is_over(self) -> bool:
        return self.outcome() is not None

    # ------------------------------------------------------------- PGN
    def to_pgn(self, white: str = "White", black: str = "Black", event: str = "Wizard War Chess") -> str:
        game = chess.pgn.Game.from_board(self.board)
        game.headers["Event"] = event
        game.headers["Site"] = "Wizard War Chess"
        game.headers["Date"] = datetime.date.today().strftime("%Y.%m.%d")
        game.headers["White"] = white
        game.headers["Black"] = black
        out = self.outcome()
        game.headers["Result"] = out.result if out else "*"
        node = game
        for record in self.records:
            node = node.variations[0] if node.variations else node
            if record.comment:
                node.comment = record.comment
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True)
        return game.accept(exporter)

    @classmethod
    def from_pgn(cls, text: str) -> tuple["GameState", dict]:
        game = chess.pgn.read_game(io.StringIO(text))
        if game is None:
            raise ValueError("No game found in PGN")
        state = cls(game.board().fen())
        for move in game.mainline_moves():
            state.push(move)
        return state, dict(game.headers)
