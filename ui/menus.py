"""Home menu, dialogs and browsers."""
from __future__ import annotations

import chess
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                             QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QProgressBar, QPushButton, QRadioButton, QScrollArea, QSlider,
                             QTabWidget, QTextBrowser, QToolButton, QVBoxLayout, QWidget)

from game.chess_ai import available_levels
from game.lessons import LESSONS
from game.puzzles import PUZZLES

from .theme import ARMY_STYLES, ENVIRONMENTS, GOLD, MUTED, TITLE_FONT, VIOLET

TIME_CONTROLS = [("Unlimited", 0, 0), ("Bullet 1+0", 60, 0), ("Blitz 3+2", 180, 2), ("Blitz 5+0", 300, 0),
                 ("Rapid 10+0", 600, 0), ("Rapid 15+10", 900, 10)]

RANKS = [(0, "Squire"), (100, "Knight Initiate"), (250, "Adept"), (500, "Battle Mage"), (900, "Sorcerer"),
         (1500, "Archmage"), (2500, "Grand Wizard"), (4000, "Legend of the Realm")]


def rank_for(xp: int) -> tuple[str, int, int]:
    """(rank name, xp at this rank, xp for next rank)."""
    name, lo, hi = RANKS[0][1], 0, RANKS[1][0]
    for i, (need, title) in enumerate(RANKS):
        if xp >= need:
            name, lo = title, need
            hi = RANKS[i + 1][0] if i + 1 < len(RANKS) else need
    return name, lo, hi


# ===================================================================== home
class HomeMenu(QFrame):
    action = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setFixedWidth(330)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 26, 22, 20)
        lay.setSpacing(9)
        title = QLabel("WIZARD\nWAR CHESS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-family:'{TITLE_FONT}'; font-size:34px; font-weight:bold; color:{GOLD};"
                            "letter-spacing:3px;")
        lay.addWidget(title)
        sub = QLabel("Command your medieval army.\nCast spells. Conquer the realm.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color:{MUTED}; font-size:12px; margin-bottom:10px;")
        lay.addWidget(sub)
        for key, text, primary in (("ai", "⚔   Battle the AI", True), ("pvp", "👥   Two-Player Duel", False),
                                   ("aivai", "🔮   Watch AI vs AI", False), ("lessons", "📜   Training Academy", False),
                                   ("puzzles", "🧩   Spell Puzzles", False), ("settings", "⚙   Settings", False),
                                   ("help", "❓   How to Play", False), ("exit", "✖   Exit", False)):
            b = QPushButton(text)
            b.setMinimumHeight(44)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("text-align:left; padding-left:18px; font-size:15px;")
            if primary:
                b.setObjectName("primary")
            b.clicked.connect(lambda _=False, k=key: self.action.emit(k))
            lay.addWidget(b)
        lay.addStretch(1)
        self.rank_card = QFrame()
        self.rank_card.setObjectName("card")
        rc = QVBoxLayout(self.rank_card)
        self.rank_label = QLabel()
        self.rank_label.setStyleSheet(f"font-family:'{TITLE_FONT}'; font-size:16px; font-weight:bold; color:{GOLD};")
        self.xp_bar = QProgressBar()
        self.xp_bar.setTextVisible(False)
        self.xp_bar.setFixedHeight(8)
        self.xp_bar.setStyleSheet(f"QProgressBar {{ background:#2a2140; border:none; border-radius:4px; }}"
                                  f"QProgressBar::chunk {{ background:{VIOLET}; border-radius:4px; }}")
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet(f"color:{MUTED}; font-size:12px;")
        self.stats_label.setWordWrap(True)
        rc.addWidget(self.rank_label)
        rc.addWidget(self.xp_bar)
        rc.addWidget(self.stats_label)
        lay.addWidget(self.rank_card)

    def update_stats(self, stats: dict):
        xp = stats.get("xp", 0)
        name, lo, hi = rank_for(xp)
        self.rank_label.setText(f"🛡 Rank: {name}")
        self.xp_bar.setRange(0, max(1, hi - lo))
        self.xp_bar.setValue(min(hi - lo, xp - lo) if hi > lo else 1)
        self.stats_label.setText(
            f"XP {xp}  •  Wins {stats.get('wins', 0)}  •  Losses {stats.get('losses', 0)}  •  Draws {stats.get('draws', 0)}\n"
            f"Puzzles solved {stats.get('puzzles', 0)}/{len(PUZZLES)}  •  Lessons {stats.get('lessons', 0)}/"
            f"{sum(len(l.steps) for l in LESSONS)}")


# ================================================================ new game
class NewGameDialog(QDialog):
    def __init__(self, mode: str = "ai", settings: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Battle")
        self.setMinimumWidth(460)
        s = settings or {}
        lay = QVBoxLayout(self)
        head = QLabel("⚔  Prepare for Battle")
        head.setObjectName("title")
        lay.addWidget(head)

        mode_box = QGroupBox("Battle mode")
        ml = QVBoxLayout(mode_box)
        self.mode_group = QButtonGroup(self)
        self.mode_buttons = {}
        for key, text in (("ai", "Battle the AI"), ("pvp", "Two players on this PC"), ("aivai", "Watch AI vs AI")):
            rb = QRadioButton(text)
            self.mode_group.addButton(rb)
            self.mode_buttons[key] = rb
            ml.addWidget(rb)
        self.mode_buttons.get(mode, self.mode_buttons["ai"]).setChecked(True)
        lay.addWidget(mode_box)

        form = QFormLayout()
        self.name = QLineEdit(s.get("player_name", "Hero"))
        form.addRow("Your name:", self.name)
        self.side = QComboBox()
        self.side.addItems(["Light (White - moves first)", "Shadow (Black)", "Random"])
        self.side.setCurrentIndex(int(s.get("side", 0)))
        form.addRow("Your army:", self.side)
        self.level = QComboBox()
        self.levels = available_levels()
        for lv in self.levels:
            self.level.addItem(f"{lv.number}. {lv.name}", lv.number)
        idx = max(0, self.level.findData(int(s.get("level", 2))))
        self.level.setCurrentIndex(idx)
        form.addRow("AI strength:", self.level)
        self.level_desc = QLabel()
        self.level_desc.setStyleSheet(f"color:{MUTED};")
        self.level_desc.setWordWrap(True)
        form.addRow("", self.level_desc)
        self.level2 = QComboBox()
        for lv in self.levels:
            self.level2.addItem(f"{lv.number}. {lv.name}", lv.number)
        self.level2.setCurrentIndex(max(0, self.level2.findData(int(s.get("level2", 3)))))
        form.addRow("Second AI:", self.level2)
        self.tc = QComboBox()
        for name, _, _ in TIME_CONTROLS:
            self.tc.addItem(name)
        self.tc.setCurrentIndex(int(s.get("tc", 0)))
        form.addRow("Time control:", self.tc)
        self.coach = QCheckBox("Learning mode: coach comments, threat warnings & hints")
        self.coach.setChecked(bool(s.get("coach", True)))
        form.addRow("", self.coach)
        lay.addLayout(form)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("To Battle!")
        bb.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.level.currentIndexChanged.connect(self._sync)
        self.mode_group.buttonToggled.connect(lambda *_: self._sync())
        self._sync()

    def _sync(self):
        lv = self.levels[self.level.currentIndex()]
        self.level_desc.setText(lv.description)
        mode = self.mode()
        self.level.setEnabled(mode != "pvp")
        self.side.setEnabled(mode == "ai")
        self.level2.setEnabled(mode == "aivai")

    def mode(self) -> str:
        for k, b in self.mode_buttons.items():
            if b.isChecked():
                return k
        return "ai"

    def result_settings(self) -> dict:
        return {"mode": self.mode(), "player_name": self.name.text().strip() or "Hero",
                "side": self.side.currentIndex(), "level": self.level.currentData(),
                "level2": self.level2.currentData(), "tc": self.tc.currentIndex(), "coach": self.coach.isChecked()}


# ================================================================ promotion
class PromotionDialog(QDialog):
    def __init__(self, renderer, style, color: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Promotion")
        self.choice = None
        lay = QVBoxLayout(self)
        t = QLabel("✨ Your Pawn reached the far rank! Choose its new form:")
        t.setStyleSheet(f"color:{GOLD}; font-weight:bold;")
        lay.addWidget(t)
        row = QHBoxLayout()
        for pt, name in ((chess.QUEEN, "Queen"), (chess.ROOK, "Rook\n(Elephant)"), (chess.BISHOP, "Bishop"),
                         (chess.KNIGHT, "Knight\n(Horse)")):
            b = QToolButton()
            b.setIcon(QIcon(renderer.pixmap(pt, color, style)))
            b.setIconSize(QSize(72, 72))
            b.setText(name)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setMinimumSize(100, 120)
            b.setStyleSheet("QToolButton { background:#1f1930; border:1px solid #3b2f55; border-radius:10px; }"
                            f"QToolButton:hover {{ border-color:{GOLD}; }}")
            b.clicked.connect(lambda _=False, p=pt: self._pick(p))
            row.addWidget(b)
        lay.addLayout(row)

    def _pick(self, pt):
        self.choice = pt
        self.accept()


# ================================================================ lessons
class LessonBrowser(QDialog):
    def __init__(self, progress: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Training Academy")
        self.setMinimumSize(560, 520)
        self.selected = None
        lay = QVBoxLayout(self)
        head = QLabel("📜  Training Academy")
        head.setObjectName("title")
        lay.addWidget(head)
        sub = QLabel("Learn chess step by step - from how the pieces move to winning tactics.")
        sub.setObjectName("subtitle")
        lay.addWidget(sub)
        self.list = QListWidget()
        self.list.setIconSize(QSize(28, 28))
        for les in LESSONS:
            done = sum(1 for i in range(len(les.steps)) if progress.get(f"{les.id}:{i}"))
            stars = "★" * done + "☆" * (len(les.steps) - done)
            item = QListWidgetItem(f"{les.icon}  {les.title}\n      {les.summary}   {stars}")
            item.setData(Qt.ItemDataRole.UserRole, les.id)
            if done == len(les.steps):
                item.setForeground(QColor("#bef264"))
            self.list.addItem(item)
        self.list.setStyleSheet("QListWidget::item { padding: 8px; }")
        self.list.itemDoubleClicked.connect(lambda it: self._choose(it))
        lay.addWidget(self.list, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Start Lesson")
        bb.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        bb.accepted.connect(lambda: self._choose(self.list.currentItem()))
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.list.setCurrentRow(next((i for i, les in enumerate(LESSONS)
                                      if not all(progress.get(f"{les.id}:{k}") for k in range(len(les.steps)))), 0))

    def _choose(self, item):
        if item is None:
            return
        self.selected = item.data(Qt.ItemDataRole.UserRole)
        self.accept()


class PuzzleBrowser(QDialog):
    def __init__(self, solved: set, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spell Puzzles")
        self.setMinimumSize(560, 520)
        self.selected = None
        lay = QVBoxLayout(self)
        head = QLabel("🧩  Spell Puzzles")
        head.setObjectName("title")
        lay.addWidget(head)
        sub = QLabel(f"Solved {len(solved)} of {len(PUZZLES)}. Find the winning spell!")
        sub.setObjectName("subtitle")
        lay.addWidget(sub)
        self.list = QListWidget()
        for p in PUZZLES:
            mark = "✅" if p.id in solved else "🔮"
            item = QListWidgetItem(f"{mark}  {p.title}   ·   {p.goal_text}   ·   {p.theme}   ·   ⭐ {p.rating}")
            item.setData(Qt.ItemDataRole.UserRole, p.id)
            self.list.addItem(item)
        self.list.setStyleSheet("QListWidget::item { padding: 7px; }")
        self.list.itemDoubleClicked.connect(self._choose)
        lay.addWidget(self.list, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Solve")
        bb.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        bb.accepted.connect(lambda: self._choose(self.list.currentItem()))
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.list.setCurrentRow(next((i for i, p in enumerate(PUZZLES) if p.id not in solved), 0))

    def _choose(self, item):
        if item is None:
            return
        self.selected = item.data(Qt.ItemDataRole.UserRole)
        self.accept()


# ================================================================ settings
class SettingsDialog(QDialog):
    def __init__(self, values: dict, locations: dict, armies3d: dict, has3d: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        v = values
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        lay.addWidget(tabs)

        # graphics
        g = QWidget()
        gf = QFormLayout(g)
        self.view_mode = QComboBox()
        self.view_mode.addItem("3D Battlefield", "3d")
        self.view_mode.addItem("Classic 2D Board", "2d")
        self.view_mode.setCurrentIndex(0 if v.get("view_mode", "3d") == "3d" and has3d else 1)
        if not has3d:
            self.view_mode.model().item(0).setEnabled(False)
        gf.addRow("Board view:", self.view_mode)
        self.location = QComboBox()
        for key, loc in locations.items():
            self.location.addItem(loc.name, key)
        self.location.setCurrentIndex(max(0, self.location.findData(v.get("location"))))
        gf.addRow("3D location:", self.location)
        self.army3d = QComboBox()
        for key, a in armies3d.items():
            self.army3d.addItem(a["name"], key)
        self.army3d.setCurrentIndex(max(0, self.army3d.findData(v.get("army3d"))))
        gf.addRow("3D armies:", self.army3d)
        self.env2d = QComboBox()
        for key, e in ENVIRONMENTS.items():
            self.env2d.addItem(e.name, key)
        self.env2d.setCurrentIndex(max(0, self.env2d.findData(v.get("env2d"))))
        gf.addRow("2D environment:", self.env2d)
        self.style2d = QComboBox()
        for key, st in ARMY_STYLES.items():
            self.style2d.addItem(st.name, key)
        self.style2d.setCurrentIndex(max(0, self.style2d.findData(v.get("style2d"))))
        gf.addRow("2D armies:", self.style2d)
        self.anim = QComboBox()
        for key, name in (("full", "Cinematic battles"), ("quick", "Quick"), ("off", "Off")):
            self.anim.addItem(name, key)
        self.anim.setCurrentIndex(max(0, self.anim.findData(v.get("anim_mode", "full"))))
        gf.addRow("Animations:", self.anim)
        self.camera_fx = QCheckBox("Camera shake & cinematic camera")
        self.camera_fx.setChecked(v.get("camera_fx", True))
        gf.addRow("", self.camera_fx)
        self.ambient = QCheckBox("Ambient effects (fire, fog, particles)")
        self.ambient.setChecked(v.get("ambient", True))
        gf.addRow("", self.ambient)
        self.bloom = QCheckBox("Bloom glow (3D)")
        self.bloom.setChecked(v.get("bloom", True))
        gf.addRow("", self.bloom)
        self.shadows = QCheckBox("Shadows (3D)")
        self.shadows.setChecked(v.get("shadows", True))
        gf.addRow("", self.shadows)
        self.msaa = QCheckBox("Anti-aliasing (3D)")
        self.msaa.setChecked(v.get("msaa", True))
        gf.addRow("", self.msaa)
        self.auto_cam = QCheckBox("Two-player: turn the camera to the side to move")
        self.auto_cam.setChecked(v.get("auto_camera", True))
        gf.addRow("", self.auto_cam)
        tabs.addTab(g, "🎨 Graphics")

        # gameplay / learning
        p = QWidget()
        pf = QFormLayout(p)
        self.legal = QCheckBox("Highlight legal moves")
        self.legal.setChecked(v.get("show_legal", True))
        self.last = QCheckBox("Highlight the last move")
        self.last.setChecked(v.get("show_last", True))
        self.coach = QCheckBox("Coach comments on every move")
        self.coach.setChecked(v.get("coach", True))
        self.threats = QCheckBox("Warn about threats and hanging pieces")
        self.threats.setChecked(v.get("threats", True))
        self.evalbar = QCheckBox("Show the evaluation bar")
        self.evalbar.setChecked(v.get("evalbar", True))
        self.tooltips = QCheckBox("Piece info tooltips (2D)")
        self.tooltips.setChecked(v.get("tooltips", True))
        for w in (self.legal, self.last, self.coach, self.threats, self.evalbar, self.tooltips):
            pf.addRow("", w)
        tabs.addTab(p, "🧙 Learning")

        # audio
        a = QWidget()
        af = QFormLayout(a)
        self.sfx = QCheckBox("Sound effects")
        self.sfx.setChecked(v.get("sfx", True))
        af.addRow("", self.sfx)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(v.get("volume", 70)))
        af.addRow("Effects volume:", self.volume)
        self.music = QCheckBox("Ambient music")
        self.music.setChecked(v.get("music", True))
        af.addRow("", self.music)
        self.music_volume = QSlider(Qt.Orientation.Horizontal)
        self.music_volume.setRange(0, 100)
        self.music_volume.setValue(int(v.get("music_volume", 35)))
        af.addRow("Music volume:", self.music_volume)
        tabs.addTab(a, "🔊 Sound")

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def values(self) -> dict:
        return {"view_mode": self.view_mode.currentData(), "location": self.location.currentData(),
                "army3d": self.army3d.currentData(), "env2d": self.env2d.currentData(),
                "style2d": self.style2d.currentData(), "anim_mode": self.anim.currentData(),
                "camera_fx": self.camera_fx.isChecked(), "ambient": self.ambient.isChecked(),
                "bloom": self.bloom.isChecked(), "shadows": self.shadows.isChecked(), "msaa": self.msaa.isChecked(),
                "auto_camera": self.auto_cam.isChecked(), "show_legal": self.legal.isChecked(),
                "show_last": self.last.isChecked(), "coach": self.coach.isChecked(),
                "threats": self.threats.isChecked(), "evalbar": self.evalbar.isChecked(),
                "tooltips": self.tooltips.isChecked(), "sfx": self.sfx.isChecked(), "volume": self.volume.value(),
                "music": self.music.isChecked(), "music_volume": self.music_volume.value()}


HELP_HTML = f"""
<h2 style='color:{GOLD}'>How to play Wizard War Chess</h2>
<p><b>Goal:</b> checkmate the enemy King - attack him so he cannot escape.</p>
<h3 style='color:{GOLD}'>Your army</h3>
<ul>
<li><b>Pawn - Foot Knight</b>: moves 1 square forward (2 on its first move), captures diagonally.</li>
<li><b>Knight - War Horse</b>: jumps in an L-shape, over other pieces.</li>
<li><b>Bishop - Battle Mage</b>: slides diagonally.</li>
<li><b>Rook - War Elephant</b>: slides along ranks and files.</li>
<li><b>Queen</b>: slides in any direction - the strongest piece.</li>
<li><b>King</b>: one square in any direction. Protect him!</li>
</ul>
<h3 style='color:{GOLD}'>Controls</h3>
<ul>
<li><b>Click</b> a piece, then click a glowing square - or <b>drag</b> the piece.</li>
<li>3D: <b>drag on empty space</b> (or right-drag) to orbit the camera, <b>mouse wheel</b> to zoom,
use the camera buttons for White / Black / top views.</li>
<li><b>Right-click</b> a square to mark it, <b>right-drag</b> on the 2D board to draw arrows.</li>
<li><b>H</b> = hint, <b>Ctrl+Z</b> = undo, <b>Ctrl+Y</b> = redo, <b>F</b> = flip / switch side,
<b>← →</b> = browse moves, <b>F11</b> = fullscreen.</li>
</ul>
<h3 style='color:{GOLD}'>Learning features</h3>
<ul>
<li><b>Coach</b>: grades every move (Best, Good, Inaccuracy, Mistake, Blunder) and explains why.</li>
<li><b>Hints</b>: shows the best move with a glowing path and explains the idea.</li>
<li><b>Threat warnings</b>: red rings mark your pieces in danger, green rings mark enemy pieces you can win.</li>
<li><b>Evaluation bar</b>: who is winning and by how much.</li>
<li><b>Training Academy</b>: interactive lessons. <b>Spell Puzzles</b>: tactics to solve.</li>
</ul>
<h3 style='color:{GOLD}'>Special moves</h3>
<p><b>Castling</b> (King two squares toward a Rook), <b>en passant</b> and <b>promotion</b> are all supported,
as are draws by stalemate, repetition, the 50-move rule and insufficient material.</p>
"""


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("How to Play")
        self.resize(640, 640)
        lay = QVBoxLayout(self)
        tb = QTextBrowser()
        tb.setHtml(HELP_HTML)
        lay.addWidget(tb)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
