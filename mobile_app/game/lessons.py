"""Training Academy: interactive lessons that teach chess from zero.

Step goals:
  info      - read the text, look at the board, press Continue
  capture   - capture the target pieces (all enemy pieces if no targets); enemy stands still
  reach     - move a piece onto one of the glowing target squares; enemy stands still
  solution  - play the exact moves; the enemy replies are scripted
  mate      - deliver checkmate in one move (any mating move counts)
  check     - give check (any checking move counts)
  any       - any legal move (used for 'escape from check')
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    title: str
    text: str
    fen: str
    goal: str = "info"
    targets: tuple[str, ...] = ()
    solution: tuple[str, ...] = ()
    par: int = 0
    hint: str = ""


@dataclass
class Lesson:
    id: str
    title: str
    icon: str
    summary: str
    steps: list[Step] = field(default_factory=list)


START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

LESSONS: list[Lesson] = [
    Lesson("board", "The Battlefield", "🗺", "How the board works and how to win.", [
        Step("Welcome, young wizard!",
             "Chess is a battle between two armies: the <b>Celestial Order</b> (White) and the "
             "<b>Arcane Shadow</b> (Black). White always moves first, then the armies take turns.<br><br>"
             "The board has 8 <b>files</b> (columns a-h) and 8 <b>ranks</b> (rows 1-8). Every square has a "
             "name like <b>e4</b>.<br><br>Your goal is to <b>checkmate</b> the enemy King: attack him so that "
             "he cannot escape. Press <b>Continue</b>.",
             START),
        Step("Your army",
             "Each side has 16 warriors: 8 Pawns, 2 Rooks, 2 Knights, 2 Bishops, a Queen and a King.<br><br>"
             "<b>Values</b> (how much each piece is worth in a trade):<br>"
             "Pawn = 1 &nbsp; Knight = 3 &nbsp; Bishop = 3 &nbsp; Rook = 5 &nbsp; Queen = 9 &nbsp; "
             "King = priceless!<br><br>Tip: hover over pieces in Learning Mode to see what they do.",
             START),
    ]),
    Lesson("rook", "The Rook - Golem Tower", "🏰", "Straight lines, any distance.", [
        Step("Rook moves",
             "The <b>Rook</b> moves any number of squares in a straight line - up, down, left or right. "
             "It cannot jump over pieces.<br><br><b>Mission:</b> capture all three enemy Pawns.",
             "8/p4p2/8/8/8/8/5p2/R7 w - - 0 1", "capture", par=3,
             hint="Go up the a-file first: Ra7 captures."),
    ]),
    Lesson("bishop", "The Bishop - Sorcerer", "🔮", "Diagonals, any distance.", [
        Step("Bishop moves",
             "The <b>Bishop</b> slides diagonally any distance. A Bishop always stays on squares of the "
             "same colour.<br><br><b>Mission:</b> capture all three enemy Pawns.",
             "8/8/3p4/8/5p2/p7/8/2B5 w - - 0 1", "capture", par=3,
             hint="Start with Bf4."),
    ]),
    Lesson("queen", "The Queen - Archmage", "👑", "The most powerful piece.", [
        Step("Queen moves",
             "The <b>Queen</b> combines the Rook and the Bishop: she moves any distance in any straight "
             "line. She is your strongest warrior - don't lose her!<br><br>"
             "<b>Mission:</b> capture all three enemy Pawns.",
             "8/3p4/8/8/p6p/8/8/3Q4 w - - 0 1", "capture", par=3,
             hint="Qxd7 first, then go diagonally to a4."),
    ]),
    Lesson("knight", "The Knight - Spell-Knight", "🐴", "The L-shaped jumper.", [
        Step("Knight moves",
             "The <b>Knight</b> moves in an <b>L-shape</b>: two squares in one direction and then one "
             "square sideways. It is the only piece that can <b>jump over</b> other pieces.<br><br>"
             "<b>Mission:</b> capture all three enemy Pawns.",
             "8/8/8/6p1/4p3/2p5/8/1N6 w - - 0 1", "capture", par=3,
             hint="b1 → c3 → e4 → g5."),
    ]),
    Lesson("king", "The King - High King", "🤴", "Slow but vital.", [
        Step("King moves",
             "The <b>King</b> moves one square in any direction. He may never move into a square that is "
             "attacked by the enemy.<br><br><b>Mission:</b> capture both enemy Pawns with your King.",
             "8/8/8/4p3/8/3p4/8/4K3 w - - 0 1", "capture", par=4,
             hint="Walk via d2, capture on d3, then go to e4 and capture on e5."),
    ]),
    Lesson("pawn", "The Pawn - Acolyte", "⚔", "Small, brave and full of surprises.", [
        Step("Pawn moves",
             "<b>Pawns</b> move straight forward one square. On their very first move they may move "
             "<b>two</b> squares. Pawns can never move backwards.<br><br>"
             "<b>Mission:</b> march the Pawn to the glowing square on the 8th rank.",
             "8/8/8/8/8/8/4P3/8 w - - 0 1", "reach", targets=("e8",), par=5,
             hint="Start with the double step e2-e4."),
        Step("Pawns capture diagonally",
             "Pawns <b>capture diagonally</b> forward - one square. A Pawn is blocked by any piece "
             "directly in front of it.<br><br><b>Mission:</b> capture the Pawn on e5.",
             "8/8/8/3pp3/3P4/8/8/8 w - - 0 1", "capture", targets=("e5",), par=1,
             hint="The d4 Pawn takes on e5."),
    ]),
    Lesson("castle", "Special Move: Castling", "🛡", "Hide your King, wake your Rook.", [
        Step("Kingside castling",
             "<b>Castling</b> moves the King two squares towards a Rook, and the Rook jumps to the other "
             "side of the King. It is the only move where two pieces move at once.<br><br>"
             "Rules: neither piece has moved yet, the squares between them are empty, and the King is not "
             "in check and does not pass through an attacked square.<br><br>"
             "<b>Mission:</b> castle kingside - move your King two squares to the right (to g1).",
             "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1", "solution", solution=("e1g1",),
             hint="Drag the King from e1 to g1."),
        Step("Queenside castling",
             "Castling can also be done on the <b>queenside</b>: the King moves two squares to the left "
             "and the Rook from a1 jumps to d1.<br><br><b>Mission:</b> castle queenside.",
             "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1", "solution", solution=("e1c1",),
             hint="Drag the King from e1 to c1."),
    ]),
    Lesson("enpassant", "Special Move: En Passant", "👻", "The ghostly pawn capture.", [
        Step("En passant",
             "When an enemy Pawn moves two squares and lands <b>right next to</b> your Pawn, you may "
             "capture it as if it had only moved one square. This is <b>en passant</b> ('in passing'). "
             "It must be done immediately or the chance is gone.<br><br>"
             "Black just played d7-d5. <b>Mission:</b> capture it en passant.",
             "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2", "solution", solution=("e5d6",),
             hint="Move your e5 Pawn diagonally to d6."),
    ]),
    Lesson("promotion", "Special Move: Promotion", "✨", "A Pawn becomes a hero.", [
        Step("Promotion",
             "When a Pawn reaches the last rank it <b>promotes</b> - it transforms into a Queen, Rook, "
             "Bishop or Knight. Almost always you choose a <b>Queen</b>.<br><br>"
             "<b>Mission:</b> promote your Pawn to a Queen.",
             "8/4P3/8/8/8/8/k7/4K3 w - - 0 1", "solution", solution=("e7e8q",),
             hint="Push the Pawn to e8 and pick the Queen."),
    ]),
    Lesson("check", "Check and Escape", "⚡", "Attacking the King.", [
        Step("Give check",
             "When a King is attacked, he is in <b>check</b>. The player in check must deal with it "
             "immediately.<br><br><b>Mission:</b> give check to the enemy King.",
             "4k3/8/8/8/8/8/8/R3K3 w - - 0 1", "check",
             hint="Your Rook can attack along the 8th rank."),
        Step("Escape from check",
             "There are three ways to escape check:<br>1. <b>Move</b> the King to a safe square.<br>"
             "2. <b>Block</b> the attack with another piece.<br>3. <b>Capture</b> the attacker.<br><br>"
             "Your King is in check from the Rook on e8. <b>Mission:</b> escape the check. "
             "(Capturing the attacker is the strongest here!)",
             "R3r1k1/8/8/8/8/8/3B4/4K3 w - - 0 1", "any",
             hint="Your Rook on a8 can capture the attacker."),
    ]),
    Lesson("mate", "Checkmate Patterns", "☠", "How battles are won.", [
        Step("Back-rank mate",
             "<b>Checkmate</b> means the King is in check and has no escape. The game ends immediately.<br>"
             "<br>A King trapped behind his own Pawns is weak on the back rank.<br><br>"
             "<b>Mission:</b> checkmate in one move.",
             "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", "mate",
             hint="Your Rook goes to the 8th rank."),
        Step("Queen and King",
             "The Queen, supported by her King, can force checkmate against a lone King.<br><br>"
             "<b>Mission:</b> checkmate in one move.",
             "k7/8/1K6/8/8/8/7Q/8 w - - 0 1", "mate",
             hint="Attack the whole 8th rank."),
        Step("Smothered mate",
             "A King surrounded by his own pieces can be <b>smothered</b> by a Knight, which jumps over "
             "the wall.<br><br><b>Mission:</b> checkmate in one move.",
             "6rk/6pp/8/6N1/8/8/8/6K1 w - - 0 1", "mate",
             hint="The Knight jumps to f7."),
        Step("Beware of stalemate!",
             "If the side to move is <b>not in check</b> but has <b>no legal moves</b>, the game is a "
             "<b>draw</b> by <b>stalemate</b>.<br><br>Here Black's King on a8 cannot move anywhere, yet he "
             "is not in check - a draw! When you are winning, always leave the enemy King a square until "
             "you can deliver mate.",
             "k7/2Q5/1K6/8/8/8/8/8 b - - 0 1"),
    ]),
    Lesson("tactics", "Battle Tactics", "🗡", "Forks, pins and skewers.", [
        Step("The fork",
             "A <b>fork</b> is one piece attacking two enemy pieces at once. Knights are fork masters!"
             "<br><br><b>Mission:</b> fork the King and Queen, then capture the Queen.",
             "3q3k/6pp/8/4N3/8/8/8/6K1 w - - 0 1", "solution", solution=("e5f7", "h8g8", "f7d8"),
             hint="Nf7+ attacks both h8 and d8."),
        Step("The pin",
             "A <b>pin</b> holds an enemy piece in place because moving it would expose something more "
             "valuable behind it. Here the Knight on c6 cannot move: it would expose its King.<br><br>"
             "<b>Mission:</b> attack the pinned Knight with a Pawn and win it.",
             "4k3/8/2n5/1B6/3P4/8/8/4K3 w - - 0 1", "solution", solution=("d4d5", "e8e7", "d5c6"),
             hint="Push d4-d5."),
        Step("The skewer",
             "A <b>skewer</b> attacks a valuable piece that must move away, exposing the piece behind it."
             "<br><br><b>Mission:</b> check the King on the e-file, then win the Queen behind him.",
             "4q3/8/4k3/8/8/8/6K1/R7 w - - 0 1", "solution", solution=("a1e1", "e6d6", "e1e8"),
             hint="Re1+ first."),
    ]),
    Lesson("opening", "Opening Wisdom", "📜", "How to start a battle.", [
        Step("Golden rules of the opening",
             "1. <b>Control the centre</b> with Pawns (e4, d4).<br>"
             "2. <b>Develop</b> Knights and Bishops early.<br>"
             "3. <b>Castle</b> to protect your King.<br>"
             "4. Don't move the same piece twice without reason.<br>"
             "5. Don't bring the Queen out too early.<br>"
             "6. <b>Connect your Rooks</b> on the back rank.<br><br>"
             "<b>Mission:</b> make a strong first move - push a centre Pawn two squares.",
             START, "solution", solution=("e2e4",),
             hint="e2-e4 is the most popular first move in history."),
        Step("Develop a Knight",
             "Black answered e7-e5. Now bring a Knight out towards the centre and attack the e5 Pawn."
             "<br><br><b>Mission:</b> play Knight to f3.",
             "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2", "solution",
             solution=("g1f3",), hint="The g1 Knight jumps to f3."),
    ]),
]


def lesson_by_id(lesson_id: str) -> Lesson | None:
    return next((les for les in LESSONS if les.id == lesson_id), None)
