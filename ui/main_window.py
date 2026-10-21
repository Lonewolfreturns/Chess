"""Main window and game controller."""
from __future__ import annotations

import os
import random
import threading
import time

import chess
from PyQt6.QtCore import QSettings, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QGuiApplication, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                             QInputDialog, QLabel, QMainWindow, QMessageBox, QPushButton, QStackedWidget,
                             QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from audio.sounds import HAVE_QT_AUDIO, MusicPlayer, SoundBank, music_dirs
from game import coach, rules
from game.chess_ai import Engine, LEVELS, analyse, choose_move, level_by_number, stockfish
from game.game_state import GameState
from game.lessons import LESSONS, lesson_by_id
from game.openings import opening_name
from game.puzzles import PUZZLES, puzzle_by_id

from .menus import (TIME_CONTROLS, HelpDialog, HomeMenu, LessonBrowser, NewGameDialog, PromotionDialog,
                    PuzzleBrowser, SettingsDialog, rank_for)
from .piece_graphics import PieceRenderer
from .theme import APP_TITLE, ARMY_STYLES, GOLD, MUTED, TITLE_FONT
from .widgets import CoachLog, EvalBar, GameOverPanel, MoveList, PlayerPanel, avatar_pixmap

DEFAULTS = {
    "view_mode": "3d", "location": "volcano", "army3d": "light_shadow", "env2d": "castle",
    "style2d": "celestial_arcane", "anim_mode": "full", "camera_fx": True, "ambient": True, "bloom": True,
    "shadows": True, "msaa": True, "auto_camera": True, "show_legal": True, "show_last": True, "coach": True,
    "threats": True, "evalbar": True, "tooltips": True, "sfx": True, "volume": 70, "music": True,
    "music_volume": 35, "music_dir": "", "player_name": "Hero", "side": 0, "level": 2, "level2": 3, "tc": 0,
}

ARMY_NAMES_3D = {chess.WHITE: "Kingdom of Light", chess.BLACK: "Shadow Legion"}


class Job(QThread):
    done = pyqtSignal(int, str, object)

    def __init__(self, job_id: int, kind: str, fn, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.kind = kind
        self.fn = fn
        self.stop_event = threading.Event()

    def run(self):
        try:
            result = self.fn(self.stop_event)
        except Exception as exc:  # never crash the UI from a worker
            result = exc
        self.done.emit(self.job_id, self.kind, result)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.qs = QSettings("WizardWarChess", os.environ.get("WWC_PROFILE", "WizardWarChess"))
        self.cfg = {k: self.qs.value(f"settings/{k}", v, type=type(v)) for k, v in DEFAULTS.items()}
        self.setWindowTitle(APP_TITLE)
        self.resize(1480, 920)
        self.renderer = PieceRenderer()
        self.setWindowIcon(QIcon(avatar_pixmap(self.renderer, ARMY_STYLES["celestial_arcane"], chess.WHITE, 128)))

        self.sounds = SoundBank(self)
        self.music = None
        self.game = GameState()
        self.mode = "home"
        self.session = 0
        self.human_colors: set = set()
        self.ai_levels: dict = {}
        self.coach_on = True
        self.view_ply: int | None = None
        self.jobs: dict[int, Job] = {}
        self._job_seq = 0
        self._ai_job = None
        self._coach_pending = False
        self._ai_waiting = False
        self.analysis_cache: dict = {}
        self.wp_losses = {chess.WHITE: [], chess.BLACK: []}
        self.hints_used = 0
        self.clock = {chess.WHITE: 0, chess.BLACK: 0}
        self.clock_on = False
        self.increment = 0
        self._clock_last = time.perf_counter()
        self.player_names = {chess.WHITE: "White", chess.BLACK: "Black"}
        self.lesson = None
        self.step_index = 0
        self.puzzle = None
        self.engines = {}
        self._last_alerts: set = set()

        self.board3d = None
        self.board2d = None
        self.board = None
        self._build_ui()
        self._build_menus()
        self._build_shortcuts()
        self._init_board_view(self.cfg["view_mode"])
        self._setup_music()
        self._apply_settings()

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._clock_tick)
        self.clock_timer.start(100)
        QTimer.singleShot(50, lambda: self.mode == "home" and self.go_home())

    # ================================================================ UI
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(10)

        self.home_menu = HomeMenu()
        self.home_menu.action.connect(self._home_action)
        root.addWidget(self.home_menu)

        center = QVBoxLayout()
        center.setSpacing(6)
        self.top_panel = PlayerPanel()
        center.addWidget(self.top_panel)
        mid = QHBoxLayout()
        mid.setSpacing(6)
        self.eval_bar = EvalBar()
        mid.addWidget(self.eval_bar)
        self.stage = QStackedWidget()
        stage_box = QWidget()
        sg = QGridLayout(stage_box)
        sg.setContentsMargins(0, 0, 0, 14)
        sg.addWidget(self.stage, 0, 0)
        self.over_panel = GameOverPanel()
        self.over_panel.action.connect(self._game_over_action)
        sg.addWidget(self.over_panel, 0, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        mid.addWidget(stage_box, 1)
        center.addLayout(mid, 1)
        self.bottom_panel = PlayerPanel()
        center.addWidget(self.bottom_panel)
        self.cam_bar = QWidget()
        cb = QHBoxLayout(self.cam_bar)
        cb.setContentsMargins(0, 0, 0, 0)
        cb.setSpacing(6)
        for text, tip, fn in (("♔ Light side", "View from White's side", lambda: self.board.view_white()),
                              ("♚ Shadow side", "View from Black's side", lambda: self.board.view_black()),
                              ("⬒ Top", "Top-down view", lambda: self.board.view_top()),
                              ("◫ Side", "Side view", lambda: self.board.view_side()),
                              ("⟳ Orbit", "Slowly orbit the battlefield", lambda: self.board.toggle_orbit())):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            cb.addWidget(b)
        cb.addStretch(1)
        self.track_label = QLabel("")
        self.track_label.setStyleSheet(f"color:{MUTED}; font-style:italic; padding-right:8px;")
        self.track_label.setToolTip("Now playing - Sound > Next track (Ctrl+M)")
        cb.addWidget(self.track_label)
        self.loc_combo = QComboBox()
        self.loc_combo.setToolTip("Battlefield location")
        cb.addWidget(self.loc_combo)
        self.view_toggle = QPushButton("2D / 3D")
        self.view_toggle.setToolTip("Switch between the 3D battlefield and the classic 2D board")
        self.view_toggle.clicked.connect(self._toggle_view_mode)
        cb.addWidget(self.view_toggle)
        center.addWidget(self.cam_bar)
        root.addLayout(center, 1)

        # right side: battle tabs or mission panel
        self.side_stack = QStackedWidget()
        self.side_stack.setFixedWidth(370)
        self.tabs = QTabWidget()
        self.side_stack.addWidget(self.tabs)
        battle = QWidget()
        bl = QVBoxLayout(battle)
        bl.setContentsMargins(8, 10, 8, 8)
        self.mode_label = QLabel("")
        self.mode_label.setObjectName("panelTitle")
        bl.addWidget(self.mode_label)
        self.opening_label = QLabel("")
        self.opening_label.setStyleSheet(f"color:{MUTED}; font-style:italic;")
        self.opening_label.setWordWrap(True)
        bl.addWidget(self.opening_label)
        self.move_list = MoveList()
        self.move_list.ply_clicked.connect(self._browse_to)
        bl.addWidget(self.move_list, 1)
        nav = QHBoxLayout()
        for text, fn in (("⏮", lambda: self._browse_to(0)), ("◀", lambda: self._browse_step(-1)),
                         ("▶", lambda: self._browse_step(1)), ("⏭", lambda: self._browse_to(self.game.ply))):
            b = QPushButton(text)
            b.setObjectName("tool")
            b.clicked.connect(fn)
            nav.addWidget(b)
        bl.addLayout(nav)
        grid = QGridLayout()
        grid.setSpacing(6)
        self.btn_hint = QPushButton("💡 Hint")
        self.btn_hint.setObjectName("primary")
        self.btn_hint.clicked.connect(self.hint)
        self.btn_undo = QPushButton("↶ Undo")
        self.btn_undo.clicked.connect(self.undo)
        self.btn_redo = QPushButton("↷ Redo")
        self.btn_redo.clicked.connect(self.redo)
        self.btn_flip = QPushButton("⇅ Switch view")
        self.btn_flip.clicked.connect(self.flip)
        self.btn_new = QPushButton("⚔ New battle")
        self.btn_new.clicked.connect(lambda: self.new_game_dialog(self.mode if self.mode in ("ai", "pvp", "aivai") else "ai"))
        self.btn_draw = QPushButton("🤝 Offer draw")
        self.btn_draw.clicked.connect(self.offer_draw)
        self.btn_resign = QPushButton("🏳 Resign")
        self.btn_resign.setObjectName("danger")
        self.btn_resign.clicked.connect(self.resign)
        self.btn_home = QPushButton("🏰 Main menu")
        self.btn_home.clicked.connect(self.go_home)
        for i, b in enumerate((self.btn_hint, self.btn_undo, self.btn_redo, self.btn_flip, self.btn_new, self.btn_draw,
                               self.btn_resign, self.btn_home)):
            grid.addWidget(b, i // 2, i % 2)
        bl.addLayout(grid)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color:{GOLD}; font-weight:bold; padding:4px;")
        bl.addWidget(self.status)
        self.tabs.addTab(battle, "⚔ Battle")

        coach_tab = QWidget()
        cl = QVBoxLayout(coach_tab)
        cl.setContentsMargins(8, 10, 8, 8)
        t = QLabel("🧙 Merlin the Coach")
        t.setObjectName("panelTitle")
        cl.addWidget(t)
        self.coach_log = CoachLog()
        cl.addWidget(self.coach_log, 1)
        b = QPushButton("💡 Explain the best move")
        b.clicked.connect(self.hint)
        cl.addWidget(b)
        self.tabs.addTab(coach_tab, "🧙 Coach")

        # mission panel (lessons / puzzles)
        self.mission = QFrame()
        self.mission.setObjectName("panel")
        ml = QVBoxLayout(self.mission)
        ml.setContentsMargins(14, 14, 14, 14)
        self.mission_title = QLabel()
        self.mission_title.setObjectName("panelTitle")
        self.mission_title.setWordWrap(True)
        ml.addWidget(self.mission_title)
        self.mission_step = QLabel()
        self.mission_step.setStyleSheet(f"color:{MUTED};")
        ml.addWidget(self.mission_step)
        self.mission_text = QTextBrowser()
        self.mission_text.setStyleSheet("QTextBrowser { font-size: 14px; padding: 8px; }")
        ml.addWidget(self.mission_text, 1)
        self.mission_result = QLabel()
        self.mission_result.setWordWrap(True)
        self.mission_result.setStyleSheet("font-size:14px; font-weight:bold; padding:6px;")
        ml.addWidget(self.mission_result)
        row = QGridLayout()
        self.m_hint = QPushButton("💡 Hint")
        self.m_hint.clicked.connect(self.hint)
        self.m_retry = QPushButton("↺ Retry")
        self.m_retry.clicked.connect(self._mission_retry)
        self.m_next = QPushButton("▶ Next")
        self.m_next.setObjectName("primary")
        self.m_next.clicked.connect(self._mission_next)
        self.m_list = QPushButton("📜 All missions")
        self.m_list.clicked.connect(self._mission_list)
        self.m_home = QPushButton("🏰 Main menu")
        self.m_home.clicked.connect(self.go_home)
        row.addWidget(self.m_hint, 0, 0)
        row.addWidget(self.m_retry, 0, 1)
        row.addWidget(self.m_next, 1, 0, 1, 2)
        row.addWidget(self.m_list, 2, 0)
        row.addWidget(self.m_home, 2, 1)
        ml.addLayout(row)
        self.side_stack.addWidget(self.mission)
        root.addWidget(self.side_stack)

    def _build_menus(self):
        mb = self.menuBar()
        g = mb.addMenu("&Game")
        self._act(g, "New Battle…", "Ctrl+N", lambda: self.new_game_dialog("ai"))
        self._act(g, "Quick Battle vs AI", None, lambda: self.start_game({**self.cfg, "mode": "ai"}))
        self._act(g, "Two-Player Duel", None, lambda: self.start_game({**self.cfg, "mode": "pvp"}))
        self._act(g, "Watch AI vs AI", None, lambda: self.start_game({**self.cfg, "mode": "aivai"}))
        g.addSeparator()
        self._act(g, "Load PGN…", "Ctrl+O", self.load_pgn)
        self._act(g, "Save PGN…", "Ctrl+S", self.save_pgn)
        self._act(g, "Copy FEN", None, lambda: QGuiApplication.clipboard().setText(self.game.board.fen()))
        self._act(g, "Set up position from FEN…", None, self.load_fen)
        g.addSeparator()
        self._act(g, "Main Menu", "Esc", self.go_home)
        self._act(g, "Exit", "Alt+F4", self.close)

        le = mb.addMenu("&Learn")
        self._act(le, "Training Academy…", "Ctrl+L", self.lesson_browser)
        self._act(le, "Spell Puzzles…", "Ctrl+P", self.puzzle_browser)
        self._act(le, "Hint", "H", self.hint)
        le.addSeparator()
        self.act_coach = self._toggle(le, "Coach comments", "coach")
        self.act_threats = self._toggle(le, "Threat warnings", "threats")
        self.act_eval = self._toggle(le, "Evaluation bar", "evalbar")
        self.act_legal = self._toggle(le, "Highlight legal moves", "show_legal")

        v = mb.addMenu("&View")
        self.loc_menu = v.addMenu("3D Location")
        self.army_menu = v.addMenu("3D Armies")
        self.env_menu = v.addMenu("2D Environment")
        self.style_menu = v.addMenu("2D Armies")
        anim = v.addMenu("Animations")
        grp = QActionGroup(self)
        self.anim_actions = {}
        for key, name in (("full", "Cinematic battles"), ("quick", "Quick"), ("off", "Off")):
            a = QAction(name, self, checkable=True)
            a.triggered.connect(lambda _=False, k=key: self._set_cfg("anim_mode", k))
            grp.addAction(a)
            anim.addAction(a)
            self.anim_actions[key] = a
        v.addSeparator()
        self._act(v, "Switch 2D / 3D", "Ctrl+D", self._toggle_view_mode)
        self._act(v, "Switch side", "F", self.flip)
        self._act(v, "Fullscreen", "F11", self._toggle_fullscreen)
        self.act_ambient = self._toggle(v, "Ambient effects", "ambient")
        self.act_camfx = self._toggle(v, "Camera effects", "camera_fx")
        self._act(v, "Settings…", "Ctrl+,", self.settings_dialog)

        s = mb.addMenu("&Sound")
        self.act_sfx = self._toggle(s, "Sound effects", "sfx")
        self.act_music = self._toggle(s, "Music", "music")
        s.addSeparator()
        self._act(s, "Next track", "Ctrl+M", lambda: self.sounds.next_track())
        self._act(s, "Choose music folder…", None, self._choose_music_folder)
        self._act(s, "Open music folder", None, self._open_music_folder)

        h = mb.addMenu("&Help")
        self._act(h, "How to Play", "F1", lambda: HelpDialog(self).exec())
        self._act(h, "About", None, self._about)

    def _act(self, menu, text, shortcut, fn):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(fn)
        menu.addAction(a)
        return a

    def _toggle(self, menu, text, key):
        a = QAction(text, self, checkable=True)
        a.setChecked(bool(self.cfg[key]))
        a.toggled.connect(lambda on, k=key: self._set_cfg(k, on))
        menu.addAction(a)
        return a

    def _build_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self.redo)
        QShortcut(QKeySequence("Left"), self, lambda: self._browse_step(-1))
        QShortcut(QKeySequence("Right"), self, lambda: self._browse_step(1))

    def _fill_view_menus(self):
        from scene3d.locations import ARMIES_3D, LOCATIONS
        from .theme import ENVIRONMENTS
        for menu, items, key in ((self.loc_menu, {k: v.name for k, v in LOCATIONS.items()}, "location"),
                                 (self.army_menu, {k: v["name"] for k, v in ARMIES_3D.items()}, "army3d"),
                                 (self.env_menu, {k: v.name for k, v in ENVIRONMENTS.items()}, "env2d"),
                                 (self.style_menu, {k: v.name for k, v in ARMY_STYLES.items()}, "style2d")):
            menu.clear()
            grp = QActionGroup(menu)
            for k, name in items.items():
                a = QAction(name, menu, checkable=True)
                a.setChecked(self.cfg[key] == k)
                a.triggered.connect(lambda _=False, kk=key, vv=k: self._set_cfg(kk, vv))
                grp.addAction(a)
                menu.addAction(a)
        self.loc_combo.blockSignals(True)
        self.loc_combo.clear()
        for k, loc in LOCATIONS.items():
            self.loc_combo.addItem(loc.name, k)
        self.loc_combo.setCurrentIndex(max(0, self.loc_combo.findData(self.cfg["location"])))
        self.loc_combo.blockSignals(False)
        try:
            self.loc_combo.currentIndexChanged.disconnect()
        except TypeError:
            pass
        self.loc_combo.currentIndexChanged.connect(lambda _: self._set_cfg("location", self.loc_combo.currentData()))

    # ================================================================ board views
    def _init_board_view(self, mode: str):
        if mode == "3d" and self.board3d is None:
            try:
                from scene3d.view3d import Board3D
                self.board3d = Board3D()
                self.stage.addWidget(self.board3d.widget)
                self._wire(self.board3d)
            except Exception as exc:
                print("3D unavailable, using 2D:", exc)
                self.board3d = None
                mode = "2d"
                self.cfg["view_mode"] = "2d"
        if mode == "2d" and self.board2d is None:
            from .chess_scene import ChessScene
            self.board2d = ChessScene()
            self.stage.addWidget(self.board2d.widget)
            self._wire(self.board2d)
        old = self.board
        self.board = self.board3d if mode == "3d" and self.board3d else self.board2d
        if old is not None and old is not self.board:
            old.pause()
            old.reset_effects()
        self.board.resume()
        self.stage.setCurrentWidget(self.board.widget)
        is3d = self.board is self.board3d
        self.loc_combo.setVisible(is3d)
        for i in range(self.cam_bar.layout().count()):
            w = self.cam_bar.layout().itemAt(i).widget()
            if isinstance(w, QPushButton) and w is not self.view_toggle:
                w.setVisible(is3d)
        self._fill_view_menus()

    def _wire(self, view):
        view.move_requested.connect(self._on_move_requested)
        view.illegal_attempt.connect(lambda: self.sounds.play("illegal"))
        view.sound_cb = self.sounds.play
        view.promotion_handler = self._ask_promotion

    def _toggle_view_mode(self):
        self._set_cfg("view_mode", "2d" if self.board is self.board3d else "3d")

    def _sync_board(self):
        """Show the live (or browsed) position on the current view."""
        if self.view_ply is not None:
            b = self.game.board_at(self.view_ply)
            last = self.game.board.move_stack[self.view_ply - 1] if self.view_ply > 0 else None
        else:
            b = self.game.board
            last = self.game.board.peek() if self.game.board.move_stack else None
            if last == chess.Move.null():
                last = None
        self.board.set_position(b, last)

    def _ask_promotion(self, color):
        style = ARMY_STYLES[self.cfg["style2d"]]
        d = PromotionDialog(self.renderer, style, color, self)
        d.exec()
        return d.choice

    # ================================================================ settings
    def _set_cfg(self, key, value):
        self.cfg[key] = value
        self.qs.setValue(f"settings/{key}", value)
        if key == "view_mode":
            self._init_board_view(value)
            self._sync_board()
            self._refresh_panels()
            self._refresh_learning_marks()
            if self.mode == "home" and self.board is self.board3d:
                self.board3d.camera.auto_orbit = True
        self._apply_settings()

    def _apply_settings(self):
        c = self.cfg
        b = self.board
        if self.board3d:
            self.board3d.set_environment(c["location"])
            if self.board3d.army_key != c["army3d"]:
                self.board3d.set_style(c["army3d"])
            self.board3d.set_graphics(bloom=c["bloom"], shadows=c["shadows"], msaa=c["msaa"])
            self.board3d.set_ambient(c["ambient"])
            self.board3d.camera.enabled = c["camera_fx"]
        if self.board2d:
            self.board2d.set_environment(c["env2d"])
            if self.board2d.style.key != c["style2d"]:
                self.board2d.set_style(c["style2d"])
            self.board2d.set_ambient(c["ambient"])
            self.board2d.camera.enabled = c["camera_fx"]
            self.board2d.set_learning_tooltips(c["tooltips"])
        for v in (self.board2d, self.board3d):
            if v:
                v.anim_mode = c["anim_mode"]
                v.show_legal = c["show_legal"]
                v.show_last_move = c["show_last"]
        self.anim_actions[c["anim_mode"]].setChecked(True)
        for act, key in ((self.act_coach, "coach"), (self.act_threats, "threats"), (self.act_eval, "evalbar"),
                         (self.act_legal, "show_legal"), (self.act_ambient, "ambient"), (self.act_camfx, "camera_fx"),
                         (self.act_sfx, "sfx"), (self.act_music, "music")):
            act.blockSignals(True)
            act.setChecked(bool(c[key]))
            act.blockSignals(False)
        self.sounds.set_enabled(c["sfx"])
        self.sounds.set_volume(c["volume"] / 100)
        self.sounds.set_music(c["music"], c["music_volume"] / 100)
        self.eval_bar.setVisible(c["evalbar"] and self.mode != "home")
        self.coach_on = c["coach"]
        if self.board3d:
            from scene3d.locations import ARMIES_3D
            a = ARMIES_3D[c["army3d"]]
            ARMY_NAMES_3D[chess.WHITE] = a["white"]["army"]
            ARMY_NAMES_3D[chess.BLACK] = a["black"]["army"]
            self.eval_bar.white_rgb = tuple(int(a["white"]["glow"][i:i + 2], 16) for i in (1, 3, 5))
            self.eval_bar.black_rgb = (40, 20, 50)
        if b is not None and b is self.board3d and self.loc_combo.currentData() != c["location"]:
            self._fill_view_menus()
        self._refresh_panels()

    def settings_dialog(self):
        from scene3d.locations import ARMIES_3D, LOCATIONS
        d = SettingsDialog(self.cfg, LOCATIONS, ARMIES_3D, self._can_3d(), self)
        if d.exec():
            new = d.values()
            view_changed = new["view_mode"] != self.cfg["view_mode"]
            for k, v in new.items():
                self.cfg[k] = v
                self.qs.setValue(f"settings/{k}", v)
            if view_changed:
                self._set_cfg("view_mode", new["view_mode"])
            self._apply_settings()
            self._fill_view_menus()

    def _can_3d(self) -> bool:
        if self.board3d is not None:
            return True
        try:
            import PyQt6.QtQuick3D  # noqa: F401
            return True
        except Exception:
            return False

    # ================================================================ music
    def _setup_music(self):
        if not HAVE_QT_AUDIO:
            return
        try:
            dirs = music_dirs(self.cfg.get("music_dir") or None)
            if self.music is None:
                self.music = MusicPlayer(dirs, self)
                self.music.track_changed.connect(lambda name: self.track_label.setText(f"♪ {name}"))
            else:
                self.music.scan(dirs)
            self.sounds.use_soundtrack(self.music)
            if not self.music.has_tracks():
                self.track_label.setText("")
        except Exception as exc:  # music is optional
            print("music disabled:", exc)

    def _choose_music_folder(self):
        from PyQt6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder with your music",
                                                  self.cfg.get("music_dir") or "")
        if folder:
            self.cfg["music_dir"] = folder
            self.qs.setValue("settings/music_dir", folder)
            self._setup_music()
            n = len(self.music.all_tracks) if self.music else 0
            QMessageBox.information(self, "Music", f"Found {n} music file(s).")

    def _open_music_folder(self):
        import os
        dirs = music_dirs(self.cfg.get("music_dir") or None)
        if dirs:
            os.startfile(dirs[0])
        else:
            QMessageBox.information(self, "Music", "No music folder yet. Create a folder named 'music' next to "
                                                   "WizardWarChess.exe and put MP3 files in it, or use Sound > "
                                                   "Choose music folder.")

    # ================================================================ home
    def go_home(self):
        self._new_session()
        self.mode = "home"
        self.home_menu.setVisible(True)
        self.side_stack.setVisible(False)
        self.top_panel.setVisible(False)
        self.bottom_panel.setVisible(False)
        self.eval_bar.setVisible(False)
        self.home_menu.update_stats(self._stats())
        self.sounds.set_mood("menu")
        self.game = GameState()
        self.board.reset_effects()
        self.board.interactive = False
        self.board.human_colors = set()
        self.board.set_position(self.game.board)
        if self.board is self.board3d:
            self.board3d.camera.go(yaw=25, pitch=24, distance=17, target=(0, 0.3, 0), duration=1.2)
            self.board3d.camera.auto_orbit = True
        self.setWindowTitle(APP_TITLE)
        QTimer.singleShot(1500, lambda s=self.session: self._demo_step(s))

    def _demo_step(self, session):
        """Attract mode: an AI battle plays behind the main menu."""
        if session != self.session or self.mode != "home":
            return
        if self.game.is_over() or self.game.ply > 80:
            self.game = GameState()
            self.board.reset_effects()
            self.board.set_position(self.game.board)
            if self.board is self.board3d:
                self.board3d.camera.auto_orbit = True
            QTimer.singleShot(2000, lambda s=session: self._demo_step(s))
            return
        board = self.game.board.copy()
        level = LEVELS[1]

        def work(stop):
            return choose_move(board, level, self._engine("demo"), stop)
        self._run_job("demo", work)

    def _home_action(self, key):
        if key == "ai":
            self.new_game_dialog("ai")
        elif key == "pvp":
            self.new_game_dialog("pvp")
        elif key == "aivai":
            self.new_game_dialog("aivai")
        elif key == "lessons":
            self.lesson_browser()
        elif key == "puzzles":
            self.puzzle_browser()
        elif key == "settings":
            self.settings_dialog()
        elif key == "help":
            HelpDialog(self).exec()
        elif key == "exit":
            self.close()

    # ================================================================ jobs
    def _engine(self, name):
        if name not in self.engines:
            self.engines[name] = Engine()
        return self.engines[name]

    def _run_job(self, kind, fn) -> Job:
        self._job_seq += 1
        job = Job(self._job_seq, kind, fn, self)
        job.session = self.session
        job.done.connect(self._job_done)
        job.finished.connect(lambda j=job: self.jobs.pop(j.job_id, None))
        self.jobs[job.job_id] = job
        job.start()
        return job

    def _cancel_jobs(self):
        for job in list(self.jobs.values()):
            job.stop_event.set()
        self._coach_pending = False
        self._ai_waiting = False
        self._ai_job = None

    def _new_session(self):
        self._cancel_jobs()
        self.over_panel.hide()
        self.session += 1
        self.view_ply = None
        self.clock_on = False

    def _job_done(self, job_id, kind, result):
        job = self.jobs.get(job_id)
        session = getattr(job, "session", None) if job else None
        if job is None or session != self.session or job.stop_event.is_set():
            if kind == "coach":
                self._coach_pending = False
            return
        if isinstance(result, Exception):
            print("worker error:", kind, result)
            if kind == "coach":
                self._coach_pending = False
                if self._ai_waiting:
                    self._ai_waiting = False
                    self._start_ai()
            return
        if kind == "demo":
            if result.move and self.mode == "home":
                self._apply_move(result.move)
        elif kind == "ai":
            self._on_ai_result(job, result)
        elif kind == "coach":
            self._on_coach_result(job, result)
        elif kind == "analysis":
            fen, res = result
            self.analysis_cache[fen] = res
            if fen == self.game.board.fen():
                self._show_eval(res, self.game.board.turn)
        elif kind == "hint":
            fen, res = result
            self.analysis_cache[fen] = res
            if fen == self.game.board.fen():
                self._show_hint(res)

    # ================================================================ game start
    def new_game_dialog(self, mode="ai"):
        d = NewGameDialog(mode, self.cfg, self)
        if d.exec():
            r = d.result_settings()
            for k, v in r.items():
                if k in self.cfg:
                    self.cfg[k] = v
                    self.qs.setValue(f"settings/{k}", v)
            self.start_game(r)

    def _enter_game_layout(self, mission: bool):
        self.home_menu.setVisible(False)
        self.side_stack.setVisible(True)
        self.side_stack.setCurrentIndex(1 if mission else 0)
        self.top_panel.setVisible(True)
        self.bottom_panel.setVisible(True)
        self.eval_bar.setVisible(self.cfg["evalbar"] and not mission)
        if self.board is self.board3d:
            self.board3d.camera.auto_orbit = False

    def start_game(self, cfg: dict, fen: str | None = None, game: GameState | None = None):
        self._new_session()
        mode = cfg.get("mode", "ai")
        self.mode = mode
        self.last_cfg = dict(cfg)
        self._last_xp = 0
        self.game = game or GameState(fen)
        self.analysis_cache.clear()
        self.wp_losses = {chess.WHITE: [], chess.BLACK: []}
        self.hints_used = 0
        self.coach_on = bool(cfg.get("coach", self.cfg["coach"]))
        name = cfg.get("player_name", self.cfg["player_name"])
        lv1 = level_by_number(int(cfg.get("level", self.cfg["level"])))
        lv2 = level_by_number(int(cfg.get("level2", self.cfg["level2"])))
        if mode == "ai":
            side = int(cfg.get("side", 0))
            human = chess.WHITE if side == 0 else chess.BLACK if side == 1 else random.choice((chess.WHITE, chess.BLACK))
            self.human_colors = {human}
            self.ai_levels = {not human: lv1}
            self.player_names = {human: name, not human: f"{lv1.name} AI"}
        elif mode == "pvp":
            self.human_colors = {chess.WHITE, chess.BLACK}
            self.ai_levels = {}
            self.player_names = {chess.WHITE: f"{name} (Light)", chess.BLACK: "Player 2 (Shadow)"}
        else:
            self.human_colors = set()
            self.ai_levels = {chess.WHITE: lv1, chess.BLACK: lv2}
            self.player_names = {chess.WHITE: f"{lv1.name} AI", chess.BLACK: f"{lv2.name} AI"}
        _, base, inc = TIME_CONTROLS[int(cfg.get("tc", 0))]
        self.clock = {chess.WHITE: base * 1000, chess.BLACK: base * 1000}
        self.increment = inc * 1000
        self.clock_on = base > 0 and mode != "aivai"
        self._enter_game_layout(False)
        self.tabs.setCurrentIndex(0)
        self.board.reset_effects()
        self.board.human_colors = self.human_colors
        self._sync_board()
        flipped = self.human_colors == {chess.BLACK}
        self.board.set_flipped(flipped)
        self.coach_log.clear()
        self.coach_log.say("Greetings! I am <b>Merlin</b>, your battle coach. "
                           + ("I will grade your moves and warn you about danger. Press <b>💡 Hint</b> any time."
                              if self.coach_on else "Coach comments are off - turn them on in the Learn menu."))
        self.mode_label.setText({"ai": f"⚔ Battle vs {lv1.name}", "pvp": "👥 Two-Player Duel",
                                 "aivai": "🔮 AI vs AI"}[mode])
        self.board.show_banner("BATTLE BEGINS!", f"{ARMY_NAMES_3D[chess.WHITE] if self.board is self.board3d else 'Light'} "
                               f"vs {ARMY_NAMES_3D[chess.BLACK] if self.board is self.board3d else 'Shadow'}",
                               (255, 215, 120), 1.4, 72)
        self.sounds.play("start")
        self.sounds.set_mood("battle")
        self.eval_bar.reset()
        self._refresh_move_list()
        self._refresh_panels()
        QTimer.singleShot(900 if mode != "aivai" else 1500, lambda s=self.session: s == self.session and self._turn_start())

    # ================================================================ turn flow
    def _turn_start(self):
        if self.mode not in ("ai", "pvp", "aivai"):
            return
        self._refresh_panels()
        out = self.game.outcome()
        if out:
            self._game_over(out)
            return
        side = self.game.board.turn
        if side in self.ai_levels:
            self.board.interactive = False
            if self._coach_pending:
                self._ai_waiting = True
            else:
                delay = 600 if self.mode == "aivai" else 0
                QTimer.singleShot(delay, lambda s=self.session: s == self.session and self._start_ai())
        else:
            self.board.interactive = self.view_ply is None
            if self.mode == "pvp" and self.cfg["auto_camera"] and self.board is self.board3d:
                self.board.set_flipped(side == chess.BLACK)
            self._start_analysis()
            self._refresh_learning_marks()

    def _start_ai(self):
        if self.mode not in ("ai", "aivai", "pvp") or self.game.is_over():
            return
        side = self.game.board.turn
        level = self.ai_levels.get(side)
        if level is None:
            return
        board = self.game.board.copy()
        panel = self._panel_for(side)
        panel.set_thinking(True)
        engine = self._engine(f"ai{int(side)}")

        def work(stop):
            return choose_move(board, level, engine, stop)
        self._ai_job = self._run_job("ai", work)
        self._ai_job.fen = board.fen()

    def _on_ai_result(self, job, result):
        self.top_panel.set_thinking(False)
        self.bottom_panel.set_thinking(False)
        if getattr(job, "fen", None) != self.game.board.fen() or result.move is None:
            return
        if result.move not in self.game.board.legal_moves:
            return
        if not result.book and result.depth >= 2:
            self._show_eval(result, self.game.board.turn)
        self._apply_move(result.move)

    def _start_analysis(self):
        """Background evaluation of the position for the eval bar, coach and instant hints."""
        if not (self.cfg["evalbar"] or self.coach_on):
            return
        fen = self.game.board.fen()
        if fen in self.analysis_cache:
            self._show_eval(self.analysis_cache[fen], self.game.board.turn)
            return
        board = self.game.board.copy()
        engine = self._engine("analysis")
        self._run_job("analysis", lambda stop: (fen, analyse(board, 0.8, engine, stop)))

    def _show_eval(self, res, side_to_move):
        cp = res.score if side_to_move == chess.WHITE else -res.score
        mate = res.mate_in
        if mate is not None and side_to_move == chess.BLACK:
            mate = -mate
        self.eval_bar.set_score(cp, mate)
        self.eval_bar.flipped = self.board.flipped
        self.eval_bar.setToolTip(coach.eval_text(cp, mate))

    # ================================================================ moves
    def _on_move_requested(self, move: chess.Move):
        if self.view_ply is not None or move not in self.game.board.legal_moves:
            self._sync_board()
            return
        if self.mode == "lesson":
            self._lesson_move(move)
            return
        if self.mode == "puzzle":
            self._puzzle_move(move)
            return
        if self.mode not in ("ai", "pvp") or self.game.board.turn not in self.human_colors:
            self._sync_board()
            return
        if self.coach_on:
            self._start_coach(self.game.board.copy(), move)
        self._apply_move(move)

    def _apply_move(self, move: chess.Move, after=None):
        if self.view_ply is not None:
            self.view_ply = None
            self._sync_board()
        side = self.game.board.turn
        record = self.game.push(move)
        if self.clock_on and self.game.ply > 1:
            self.clock[side] += self.increment
        self.board.interactive = False
        self.board.set_threats({})
        self._refresh_move_list()
        callback = after or self._after_animation
        session = self.session
        self.board.play_move(record, self.game.board.copy(),
                             on_done=lambda: session == self.session and callback())

    def _after_animation(self):
        if self.mode == "home":
            QTimer.singleShot(900, lambda s=self.session: self._demo_step(s))
            return
        self._turn_start()

    # ================================================================ coach
    def _start_coach(self, before: chess.Board, move: chess.Move):
        self._coach_pending = True
        fen = before.fen()
        cached = self.analysis_cache.get(fen)
        engine = self._engine("coach")

        def work(stop):
            best = cached if cached is not None and cached.depth >= 3 else analyse(before, 0.7, engine, stop)
            after = before.copy()
            after.push(move)
            if after.is_game_over():
                from game.chess_ai import SearchResult, MATE
                score = -MATE if after.is_checkmate() else 0
                res_after = SearchResult(None, score)
            else:
                res_after = analyse(after, 0.7, engine, stop)
            return before, move, best, res_after
        job = self._run_job("coach", work)
        job.ply = self.game.ply

    def _on_coach_result(self, job, result):
        self._coach_pending = False
        before, move, best, after = result
        try:
            review = coach.review_move(before, move, best, after)
        except Exception as exc:
            print("coach error", exc)
            review = None
        if review is not None:
            ply = getattr(job, "ply", None)
            if ply is not None and ply < len(self.game.records):
                rec = self.game.records[ply]
                if rec.move == move:
                    rec.annotation = review.symbol
                    rec.quality = review.label
                    rec.comment = f"{review.label}: best was {review.best_san}"
                    self._refresh_move_list()
            self.wp_losses[before.turn].append(review.wp_loss)
            icon = {"Brilliant": "💎", "Best": "⭐", "Excellent": "✨", "Good": "👍", "Inaccuracy": "🤔",
                    "Mistake": "⚠", "Blunder": "💥"}.get(review.label, "🧙")
            self.coach_log.say(review.html, icon)
            if review.label in ("Mistake", "Blunder") and self.mode == "ai":
                self.status.setText(f"{icon} {review.label}! Check the Coach tab for advice.")
            after_fen = before.copy()
            after_fen.push(move)
            self.analysis_cache[after_fen.fen()] = after
        if self._ai_waiting:
            self._ai_waiting = False
            self._start_ai()

    def _refresh_learning_marks(self):
        if self.mode not in ("ai", "pvp") or not self.cfg["threats"] or self.view_ply is not None:
            self.board.set_threats({})
            return
        b = self.game.board
        if b.turn not in self.human_colors:
            self.board.set_threats({})
            return
        marks = {sq: (255, 70, 70) for sq in rules.hanging_pieces(b, b.turn)}
        for sq in rules.hanging_pieces(b, not b.turn):
            marks[sq] = (90, 230, 120)
        self.board.set_threats(marks)
        if self.coach_on:
            alerts = coach.threat_report(b)[:2]
            for alert in alerts:
                if alert not in self._last_alerts:
                    self.coach_log.say(alert, "")
            self._last_alerts = set(alerts)

    # ================================================================ hints
    def hint(self):
        if self.mode == "lesson":
            return self._lesson_hint()
        if self.mode == "puzzle":
            return self._puzzle_hint()
        if self.mode not in ("ai", "pvp") or self.game.is_over() or self.game.board.turn not in self.human_colors:
            return
        self.hints_used += 1
        fen = self.game.board.fen()
        res = self.analysis_cache.get(fen)
        if res is not None and res.depth >= 3 and res.move is not None:
            self._show_hint(res)
            return
        self.status.setText("🔮 Consulting the crystal ball…")
        board = self.game.board.copy()
        engine = self._engine("hint")
        self._run_job("hint", lambda stop: (fen, analyse(board, 1.2, engine, stop)))

    def _show_hint(self, res):
        if res.move is None:
            return
        self.board.show_hint(res.move)
        self.sounds.play("hint")
        text = coach.explain_hint(self.game.board, res)
        self.coach_log.say(text, "💡")
        self.status.setText("💡 " + coach.describe(self.game.board, res.move))

    # ================================================================ undo / redo / browse
    def undo(self):
        if self.mode not in ("ai", "pvp") or not self.game.records:
            return
        self._cancel_jobs()
        self.over_panel.hide()
        self.session += 1
        self.view_ply = None
        self.board.reset_effects()
        self.game.undo()
        while self.game.records and self.game.board.turn not in self.human_colors:
            self.game.undo()
        self._sync_board()
        self._refresh_move_list()
        self.board.show_hint(None)
        self.coach_log.say("↶ Move taken back. Think again, young wizard!", "")
        self._turn_start()

    def redo(self):
        if self.mode not in ("ai", "pvp") or not self.game.redo_stack:
            return
        self._cancel_jobs()
        self.session += 1
        self.game.redo()
        while self.game.redo_stack and self.game.board.turn not in self.human_colors:
            self.game.redo()
        self._sync_board()
        self._refresh_move_list()
        self._turn_start()

    def _browse_to(self, ply: int):
        if self.mode in ("home", "lesson", "puzzle"):
            return
        ply = max(0, min(self.game.ply, ply))
        self.view_ply = None if ply == self.game.ply else ply
        self._sync_board()
        self.board.interactive = self.view_ply is None and self.game.board.turn in self.human_colors \
            and not self.game.is_over()
        self.move_list.highlight_ply(ply)
        if self.view_ply is not None:
            self.status.setText(f"👁 Viewing move {(ply + 1) // 2}{'' if ply % 2 else '…'} - press ⏭ to return to the battle")
        else:
            self._refresh_panels()

    def _browse_step(self, d: int):
        cur = self.game.ply if self.view_ply is None else self.view_ply
        self._browse_to(cur + d)

    def flip(self):
        self.board.set_flipped(not self.board.flipped)
        self.eval_bar.flipped = self.board.flipped
        self.eval_bar.update()
        self._refresh_panels()

    # ================================================================ end of game
    def resign(self):
        if self.mode != "ai" and self.mode != "pvp" or self.game.is_over():
            return
        side = self.game.board.turn if self.mode == "pvp" else next(iter(self.human_colors))
        if QMessageBox.question(self, "Resign", "Lay down your arms and resign this battle?") != \
                QMessageBox.StandardButton.Yes:
            return
        winner = not side
        self.game.set_result("1-0" if winner == chess.WHITE else "0-1", "Resignation", winner)
        self._cancel_jobs()
        self._game_over(self.game.outcome())

    def offer_draw(self):
        if self.mode not in ("ai", "pvp") or self.game.is_over():
            return
        if self.mode == "pvp":
            if QMessageBox.question(self, "Draw", "Both players agree to a draw?") == QMessageBox.StandardButton.Yes:
                self.game.set_result("1/2-1/2", "Agreement", None)
                self._game_over(self.game.outcome())
            return
        res = self.analysis_cache.get(self.game.board.fen())
        human = next(iter(self.human_colors))
        ai_score = 0
        if res is not None:
            ai_score = -res.score if self.game.board.turn == human else res.score
        if self.game.ply >= 30 and ai_score <= 30:
            self.game.set_result("1/2-1/2", "Agreement", None)
            self.coach_log.say("The enemy commander accepts your offer of peace.", "🤝")
            self._cancel_jobs()
            self._game_over(self.game.outcome())
        else:
            self.coach_log.say("The enemy refuses your offer - they believe they can still win!", "🤝")
            self.status.setText("🤝 Draw offer declined.")

    def _game_over(self, out):
        self.clock_on = False
        self.board.interactive = False
        self.board.set_threats({})
        reason = out.reason
        is3d = self.board is self.board3d
        names = ARMY_NAMES_3D if is3d else {chess.WHITE: "Light", chess.BLACK: "Shadow"}
        if out.winner is None:
            self.sounds.set_mood("menu")
        elif self.mode == "ai" and out.winner not in self.human_colors:
            self.sounds.set_mood("defeat")
        else:
            self.sounds.set_mood("victory")
        if out.winner is None:
            title, sub, rgb = "DRAW", reason, (200, 215, 235)
            if self.mode == "ai":
                self._record_result("draw")
        else:
            win_name = names[out.winner]
            if self.mode == "ai":
                human_won = out.winner in self.human_colors
                title = "VICTORY" if human_won else "DEFEAT"
                rgb = (255, 215, 120) if human_won else (255, 90, 90)
                self._record_result("win" if human_won else "loss")
            else:
                title, rgb = ("CHECKMATE" if reason == "Checkmate" else "VICTORY"), (255, 215, 120)
            sub = f"{reason} - the {win_name} triumphs!"
        session = self.session

        def show_panel():
            if session == self.session:
                self._show_game_over(title, sub, rgb)
        if reason == "Checkmate":
            self.board.play_checkmate(not out.winner, title, sub, rgb,
                                      on_done=lambda: QTimer.singleShot(600, show_panel))
        elif out.winner is None:
            self.board.play_draw(title, sub, on_done=lambda: QTimer.singleShot(900, show_panel))
        else:
            self.board.show_banner(title, sub, rgb, None, 92)
            self.board.celebrate(out.winner)
            self.sounds.play("victory_horn" if (self.mode != "ai" or out.winner in self.human_colors) else "defeat")
            QTimer.singleShot(1800, show_panel)
        self.status.setText(f"🏁 {title}: {sub}")
        summary = [f"<b>Battle over:</b> {sub} ({out.result})"]
        for color in (chess.WHITE, chess.BLACK):
            losses = self.wp_losses[color]
            if losses:
                acc = coach.accuracy(losses)
                summary.append(f"{self.player_names[color]} accuracy: <b>{acc:.0f}%</b>")
        if self.hints_used:
            summary.append(f"Hints used: {self.hints_used}")
        self.coach_log.say("<br>".join(summary), "🏁")
        self._refresh_panels()

    def _show_game_over(self, title, sub, rgb):
        moves = (self.game.ply + 1) // 2
        parts = [f"Moves: <b>{moves}</b>"]
        for color in (chess.WHITE, chess.BLACK):
            if self.wp_losses[color] and (self.mode != "ai" or color in self.human_colors):
                acc = coach.accuracy(self.wp_losses[color])
                parts.append(f"{self.player_names[color]} accuracy: <b>{acc:.0f}%</b>")
        if self.hints_used:
            parts.append(f"Hints used: <b>{self.hints_used}</b>")
        if self.mode == "ai" and getattr(self, "_last_xp", 0):
            rank = rank_for(int(self.qs.value("stats/xp", 0)))[0]
            parts.append(f"<span style='color:#c4b5fd'>+{self._last_xp} XP  -  Rank: {rank}</span>")
        self.over_panel.buttons["review"].setVisible(self.game.ply > 0)
        self.over_panel.buttons["again"].setText("⚔  Rematch" if self.mode == "ai" else "⚔  Play again")
        self.board.hide_banner()
        self.over_panel.show_result(title, sub, rgb, "  •  ".join(parts))

    def _game_over_action(self, key):
        self.over_panel.hide()
        if key == "again":
            self.start_game(getattr(self, "last_cfg", {**self.cfg, "mode": "ai"}))
        elif key == "new":
            mode = self.mode if self.mode in ("ai", "pvp", "aivai") else "ai"
            self.new_game_dialog(mode)
            if self.game.is_over() and self.mode == mode:
                self.over_panel.show()
        elif key == "review":
            self.board.hide_banner()
            self.board.reset_effects()
            self.tabs.setCurrentIndex(0)
            self._browse_to(0)
            self.status.setText("👁 Review: click a move or use ◀ ▶ to replay the battle. Coach grades are "
                                "shown in the move list - hover a move for details.")
        elif key == "home":
            self.go_home()

    def _record_result(self, kind):
        lv = next(iter(self.ai_levels.values())).number if self.ai_levels else 1
        key = {"win": "wins", "loss": "losses", "draw": "draws"}[kind]
        self.qs.setValue(f"stats/{key}", int(self.qs.value(f"stats/{key}", 0)) + 1)
        xp = {"win": 20 * lv, "draw": 8 * lv, "loss": 3}[kind]
        self._last_xp = xp
        self._add_xp(xp)

    def _add_xp(self, xp):
        old = int(self.qs.value("stats/xp", 0))
        new = old + xp
        self.qs.setValue("stats/xp", new)
        if rank_for(new)[0] != rank_for(old)[0]:
            self.coach_log.say(f"🎖 <b>Rank up!</b> You are now a <b>{rank_for(new)[0]}</b>!", "")
            self.board.show_banner("RANK UP!", rank_for(new)[0], (190, 160, 255), 2.0, 70)

    def _stats(self) -> dict:
        solved = self._puzzles_solved()
        lessons = self._lesson_progress()
        return {"xp": int(self.qs.value("stats/xp", 0)), "wins": int(self.qs.value("stats/wins", 0)),
                "losses": int(self.qs.value("stats/losses", 0)), "draws": int(self.qs.value("stats/draws", 0)),
                "puzzles": len(solved), "lessons": len(lessons)}

    # ================================================================ clock
    def _clock_tick(self):
        now = time.perf_counter()
        dt = (now - self._clock_last) * 1000
        self._clock_last = now
        if not self.clock_on or self.mode not in ("ai", "pvp") or self.game.is_over():
            return
        if self.game.ply == 0:
            return
        side = self.game.board.turn
        self.clock[side] -= dt
        if self.clock[side] <= 0:
            self.clock[side] = 0
            winner = not side
            if not rules.material(self.game.board, winner) or self.game.board.has_insufficient_material(winner):
                self.game.set_result("1/2-1/2", "Timeout vs insufficient material", None)
            else:
                self.game.set_result("1-0" if winner == chess.WHITE else "0-1", "Time ran out", winner)
            self._cancel_jobs()
            self._game_over(self.game.outcome())
        self._refresh_clocks()

    def _refresh_clocks(self):
        for color in (chess.WHITE, chess.BLACK):
            panel = self._panel_for(color)
            if self.clock_on or (self.mode in ("ai", "pvp") and TIME_CONTROLS[int(self.cfg["tc"])][1] > 0
                                 and self.game.is_over()):
                ms = self.clock[color]
                panel.set_clock(int(ms), ms < 20000)
            else:
                panel.set_clock(None)

    # ================================================================ panels
    def _panel_for(self, color) -> PlayerPanel:
        bottom = chess.BLACK if self.board.flipped else chess.WHITE
        return self.bottom_panel if color == bottom else self.top_panel

    def _refresh_panels(self):
        if self.mode == "home" or self.board is None:
            return
        is3d = self.board is self.board3d
        style = ARMY_STYLES[self.cfg["style2d"]]
        balance = self.game.material_balance()
        for color in (chess.WHITE, chess.BLACK):
            panel = self._panel_for(color)
            panel.setup(self.player_names.get(color, "?"), color, style,
                        avatar_pixmap(self.renderer, style, color))
            if is3d:
                panel.army.setText(ARMY_NAMES_3D[color])
            adv = balance if color == chess.WHITE else -balance
            panel.set_captured(self.game.captured_by(color), not color, adv, self.renderer, style)
            panel.set_active(self.game.board.turn == color and not self.game.is_over())
            if color not in self.ai_levels:
                panel.set_thinking(False)
        self._refresh_clocks()
        self.btn_undo.setEnabled(self.mode in ("ai", "pvp") and bool(self.game.records))
        self.btn_redo.setEnabled(self.mode in ("ai", "pvp") and bool(self.game.redo_stack))
        self.btn_hint.setEnabled(self.mode in ("ai", "pvp") and not self.game.is_over())
        self.btn_resign.setEnabled(self.mode in ("ai", "pvp") and not self.game.is_over())
        self.btn_draw.setEnabled(self.mode in ("ai", "pvp") and not self.game.is_over())
        name = opening_name(self.game.moves_uci()) if self.game.start_fen == chess.STARTING_FEN else ""
        self.opening_label.setText(f"📖 {name}" if name else "")
        if self.mode in ("ai", "pvp", "aivai") and not self.game.is_over() and self.view_ply is None:
            side = self.game.board.turn
            who = self.player_names.get(side, "")
            txt = f"{'⚡ CHECK! ' if self.game.board.is_check() else ''}{who} to move"
            if side in self.ai_levels:
                txt = f"{who} is casting a spell…"
            self.status.setText(txt)
        if self.mode in ("ai", "pvp", "aivai"):
            self.setWindowTitle(f"{APP_TITLE} - {self.mode_label.text()}")

    def _refresh_move_list(self):
        self.move_list.set_records(self.game.records, chess.Board(self.game.start_fen).turn == chess.BLACK)

    # ================================================================ PGN / FEN
    def save_pgn(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save game", "battle.pgn", "PGN files (*.pgn)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.game.to_pgn(self.player_names.get(chess.WHITE, "White"),
                                         self.player_names.get(chess.BLACK, "Black")))
            self.status.setText(f"💾 Saved to {path}")

    def load_pgn(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load game", "", "PGN files (*.pgn);;All files (*)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                state, headers = GameState.from_pgn(f.read())
        except Exception as exc:
            QMessageBox.warning(self, "Load PGN", f"Could not read that game:\n{exc}")
            return
        self.start_game({**self.cfg, "mode": "pvp", "tc": 0}, game=state)
        self.player_names = {chess.WHITE: headers.get("White", "White"), chess.BLACK: headers.get("Black", "Black")}
        self._refresh_move_list()
        self._refresh_panels()

    def load_fen(self):
        fen, ok = QInputDialog.getText(self, "Set up position", "Paste a FEN:", text=self.game.board.fen())
        if not ok or not fen.strip():
            return
        try:
            b = chess.Board(fen.strip())
            if not b.is_valid():
                raise ValueError(str(b.status()))
        except Exception as exc:
            QMessageBox.warning(self, "FEN", f"That position is not valid:\n{exc}")
            return
        self.start_game({**self.cfg, "mode": "pvp", "tc": 0}, fen=fen.strip())

    # ================================================================ lessons
    def _lesson_progress(self) -> set:
        raw = self.qs.value("progress/lessons", "")
        return set(x for x in str(raw).split(",") if x)

    def _puzzles_solved(self) -> set:
        raw = self.qs.value("progress/puzzles", "")
        return set(x for x in str(raw).split(",") if x)

    def lesson_browser(self):
        prog = {k: True for k in self._lesson_progress()}
        d = LessonBrowser(prog, self)
        if d.exec() and d.selected:
            self.start_lesson(d.selected, 0)

    def start_lesson(self, lesson_id: str, step: int = 0):
        self._new_session()
        self.mode = "lesson"
        self.lesson = lesson_by_id(lesson_id)
        self.step_index = step
        self.sounds.set_mood("learn")
        self._enter_game_layout(True)
        self.player_names = {chess.WHITE: "You", chess.BLACK: "Training dummies"}
        self.ai_levels = {}
        self._lesson_load()

    def _lesson_load(self):
        self._new_session()
        self.mode = "lesson"
        step = self.lesson.steps[self.step_index]
        self.game = GameState(step.fen)
        self.board.reset_effects()
        self.board.set_position(self.game.board)
        self.human_colors = {self.game.board.turn}
        self.board.human_colors = self.human_colors
        self.board.interactive = step.goal != "info"
        self.board.set_flipped(self.game.board.turn == chess.BLACK)
        targets = [chess.parse_square(t) for t in step.targets]
        self.board.set_targets(targets)
        self.board.set_threats({})
        self.lesson_moves = 0
        self.sol_idx = 0
        self.lesson_done = step.goal == "info"
        self.mission_title.setText(f"{self.lesson.icon}  {self.lesson.title}")
        self.mission_step.setText(f"Step {self.step_index + 1} of {len(self.lesson.steps)}  •  {step.title}"
                                  + (f"  •  Par: {step.par} moves" if step.par else ""))
        self.mission_text.setHtml(step.text)
        self.mission_result.setText("" if step.goal != "info" else "📖 Read, then press Next.")
        self.mission_result.setStyleSheet("font-size:14px; font-weight:bold; padding:6px; color:#c4b5fd;")
        self.m_next.setEnabled(self.lesson_done)
        self.m_hint.setEnabled(step.goal != "info")
        self.m_list.setText("📜 All lessons")
        self._refresh_panels()

    def _lesson_move(self, move: chess.Move):
        step = self.lesson.steps[self.step_index]
        if self.lesson_done or step.goal == "info":
            self._sync_board()
            return
        g = step.goal
        if g == "solution":
            expected = step.solution[self.sol_idx]
            if move.uci() != expected and not (len(expected) == 4 and move.uci()[:4] == expected):
                self._lesson_wrong("Not quite - that's not the move we're practising. Try again!")
                return
            self.sol_idx += 1
            self._apply_move(move, after=self._lesson_after_solution)
        elif g in ("capture", "reach"):
            self.lesson_moves += 1
            self._apply_move(move, after=self._lesson_after_free)
        elif g == "mate":
            b = self.game.board.copy()
            b.push(move)
            if not b.is_checkmate():
                self._lesson_wrong("That move doesn't checkmate. Look for a check the King cannot escape!")
                return
            self._apply_move(move, after=lambda: self._lesson_success(move.to_square))
        elif g == "check":
            if not self.game.board.gives_check(move):
                self._lesson_wrong("That move doesn't attack the King. Try again!")
                return
            self._apply_move(move, after=lambda: self._lesson_success(move.to_square))
        elif g == "any":
            kind = "captured the attacker" if self.game.board.is_capture(move) else (
                "moved the King to safety" if self.game.board.piece_type_at(move.from_square) == chess.KING
                else "blocked the attack")
            self.lesson_note = f"You {kind}."
            self._apply_move(move, after=lambda: self._lesson_success(move.to_square))

    def _lesson_wrong(self, text):
        self.sounds.play("illegal")
        self.mission_result.setText("✖ " + text)
        self.mission_result.setStyleSheet("font-size:14px; font-weight:bold; padding:6px; color:#fca5a5;")
        self._sync_board()

    def _lesson_after_solution(self):
        step = self.lesson.steps[self.step_index]
        if self.sol_idx >= len(step.solution):
            self._lesson_success(self.game.board.peek().to_square)
            return
        reply = chess.Move.from_uci(step.solution[self.sol_idx])
        self.sol_idx += 1
        self.mission_result.setText("✔ Good! The enemy responds…")
        self.mission_result.setStyleSheet("font-size:14px; font-weight:bold; padding:6px; color:#86efac;")
        session = self.session

        def play_reply():
            if session != self.session:
                return
            self._apply_move(reply, after=self._lesson_continue)
        QTimer.singleShot(500, play_reply)

    def _lesson_continue(self):
        step = self.lesson.steps[self.step_index]
        if self.sol_idx >= len(step.solution):
            self._lesson_success(self.game.board.peek().to_square)
        else:
            self.board.interactive = True

    def _lesson_after_free(self):
        step = self.lesson.steps[self.step_index]
        b = self.game.board
        player = not b.turn
        done = False
        if step.goal == "capture":
            if step.targets:
                done = all(b.color_at(chess.parse_square(t)) != (not player) for t in step.targets)
            else:
                done = not b.occupied_co[not player]
        else:
            done = any(b.color_at(chess.parse_square(t)) == player for t in step.targets)
        if done:
            self._lesson_success(b.peek().to_square)
            return
        # the enemy stands still: give the turn back
        self.game.push_null()
        self.board.set_position(self.game.board, self.game.board.move_stack[-2], keep=True)
        self.board.interactive = True
        self.mission_result.setText(f"Moves used: {self.lesson_moves}" + (f" / par {step.par}" if step.par else ""))
        self.mission_result.setStyleSheet("font-size:14px; font-weight:bold; padding:6px; color:#c4b5fd;")

    def _lesson_success(self, sq):
        step = self.lesson.steps[self.step_index]
        self.lesson_done = True
        self.board.interactive = False
        self.board.lesson_success(sq)
        stars = 3
        if step.par:
            stars = 3 if self.lesson_moves <= step.par else 2 if self.lesson_moves <= step.par + 2 else 1
        note = getattr(self, "lesson_note", "") if step.goal == "any" else ""
        self.lesson_note = ""
        self.mission_result.setText(f"{'★' * stars}{'☆' * (3 - stars)}  Mission complete! {note}")
        self.mission_result.setStyleSheet("font-size:15px; font-weight:bold; padding:6px; color:#fde68a;")
        key = f"{self.lesson.id}:{self.step_index}"
        prog = self._lesson_progress()
        if key not in prog:
            prog.add(key)
            self.qs.setValue("progress/lessons", ",".join(sorted(prog)))
            self._add_xp(5)
        self.m_next.setEnabled(True)

    def _lesson_hint(self):
        step = self.lesson.steps[self.step_index]
        if step.hint:
            self.mission_result.setText("💡 " + step.hint)
            self.mission_result.setStyleSheet("font-size:14px; font-weight:bold; padding:6px; color:#7dd3fc;")
        if step.goal == "solution" and self.sol_idx < len(step.solution):
            self.board.show_hint(chess.Move.from_uci(step.solution[self.sol_idx]))
        elif step.goal == "mate":
            m = rules.find_mate(self.game.board, 1)
            if m:
                self.board.show_hint(m)
        self.sounds.play("hint")

    def _mission_retry(self):
        if self.mode == "lesson":
            self._lesson_load()
        elif self.mode == "puzzle":
            self._puzzle_load()

    def _mission_next(self):
        if self.mode == "lesson":
            if self.step_index + 1 < len(self.lesson.steps):
                self.step_index += 1
                self._lesson_load()
            else:
                idx = LESSONS.index(self.lesson)
                if idx + 1 < len(LESSONS):
                    self.start_lesson(LESSONS[idx + 1].id, 0)
                else:
                    self.board.show_banner("ACADEMY COMPLETE", "You are ready for real battles!", (255, 215, 120), 2.5)
        elif self.mode == "puzzle":
            idx = PUZZLES.index(self.puzzle)
            self.start_puzzle(PUZZLES[(idx + 1) % len(PUZZLES)].id)

    def _mission_list(self):
        if self.mode == "lesson":
            self.lesson_browser()
        else:
            self.puzzle_browser()

    # ================================================================ puzzles
    def puzzle_browser(self):
        d = PuzzleBrowser(self._puzzles_solved(), self)
        if d.exec() and d.selected:
            self.start_puzzle(d.selected)

    def start_puzzle(self, pid: str):
        self._new_session()
        self.mode = "puzzle"
        self.puzzle = puzzle_by_id(pid)
        self.sounds.set_mood("learn")
        self._enter_game_layout(True)
        self.ai_levels = {}
        self._puzzle_load()

    def _puzzle_load(self):
        self._new_session()
        self.mode = "puzzle"
        p = self.puzzle
        self.game = GameState(p.fen)
        side = self.game.board.turn
        self.human_colors = {side}
        self.player_names = {side: "You", not side: "The enemy"}
        self.board.reset_effects()
        self.board.set_position(self.game.board)
        self.board.human_colors = self.human_colors
        self.board.interactive = True
        self.board.set_targets([])
        self.board.set_threats({})
        self.board.set_flipped(side == chess.BLACK)
        self.puz_remaining = p.moves
        self.puz_idx = 0
        self.puz_hint_level = 0
        self.puz_mistakes = 0
        self.mission_title.setText(f"🧩  {p.title}")
        self.mission_step.setText(f"{p.theme}  •  Rating {p.rating}")
        self.mission_text.setHtml(f"<p><b>{p.goal_text}</b></p><p>Study the position. When you've found the spell, "
                                  f"make the move on the board. Stuck? Press <b>💡 Hint</b>.</p>")
        self.mission_result.setText("")
        self.m_next.setEnabled(True)
        self.m_hint.setEnabled(True)
        self.m_list.setText("🧩 All puzzles")
        self._refresh_panels()

    def _puzzle_move(self, move: chess.Move):
        p = self.puzzle
        b = self.game.board
        if b.turn not in self.human_colors:
            self._sync_board()
            return
        if p.kind == "mate":
            after = b.copy()
            after.push(move)
            if after.is_checkmate():
                self._apply_move(move, after=self._puzzle_solved)
            elif self.puz_remaining > 1 and rules.mate_holds(after, self.puz_remaining - 1):
                self._apply_move(move, after=self._puzzle_reply)
            else:
                self._puzzle_wrong()
        else:
            expected = p.solution[self.puz_idx]
            if move.uci() != expected:
                self._puzzle_wrong()
                return
            self.puz_idx += 1
            self._apply_move(move, after=self._puzzle_reply)

    def _puzzle_wrong(self):
        self.puz_mistakes += 1
        self.sounds.play("illegal")
        self.mission_result.setText("✖ That spell fizzles. Try another move!")
        self.mission_result.setStyleSheet("font-size:14px; font-weight:bold; padding:6px; color:#fca5a5;")
        self._sync_board()

    def _puzzle_reply(self):
        p = self.puzzle
        if p.kind == "mate":
            self.puz_remaining -= 1
            reply = rules.best_defence(self.game.board, self.puz_remaining)
        else:
            if self.puz_idx >= len(p.solution):
                self._puzzle_solved()
                return
            reply = chess.Move.from_uci(p.solution[self.puz_idx])
            self.puz_idx += 1
        if reply is None:
            self._puzzle_solved()
            return
        self.mission_result.setText("✔ Correct! The enemy responds…")
        self.mission_result.setStyleSheet("font-size:14px; font-weight:bold; padding:6px; color:#86efac;")
        session = self.session

        def go():
            if session == self.session:
                self._apply_move(reply, after=self._puzzle_continue)
        QTimer.singleShot(500, go)

    def _puzzle_continue(self):
        p = self.puzzle
        if p.kind == "win" and self.puz_idx >= len(p.solution):
            self._puzzle_solved()
            return
        self.board.interactive = True
        self.puz_hint_level = 0

    def _puzzle_solved(self):
        self.board.interactive = False
        self.board.lesson_success(self.game.board.peek().to_square)
        self.board.celebrate(next(iter(self.human_colors)))
        msg = "🏆 Puzzle solved!" + (" Flawless!" if self.puz_mistakes == 0 else f" ({self.puz_mistakes} misses)")
        self.mission_result.setText(msg)
        self.mission_result.setStyleSheet("font-size:15px; font-weight:bold; padding:6px; color:#fde68a;")
        solved = self._puzzles_solved()
        if self.puzzle.id not in solved:
            solved.add(self.puzzle.id)
            self.qs.setValue("progress/puzzles", ",".join(sorted(solved)))
            self._add_xp(10)
        self.board.show_banner("SOLVED!", self.puzzle.title, (255, 215, 120), 1.6, 80)

    def _puzzle_hint(self):
        p = self.puzzle
        b = self.game.board
        if p.kind == "mate":
            move = rules.find_mate(b, self.puz_remaining)
        else:
            move = chess.Move.from_uci(p.solution[self.puz_idx]) if self.puz_idx < len(p.solution) else None
        if move is None:
            return
        self.puz_hint_level += 1
        self.sounds.play("hint")
        if self.puz_hint_level == 1:
            self.board.set_square_marks({move.from_square: (90, 210, 255)})
            self.mission_result.setText(f"💡 {p.hint}  Look at your {rules.PIECE_NAMES[b.piece_type_at(move.from_square)]}.")
        else:
            self.board.set_square_marks({})
            self.board.show_hint(move)
            self.mission_result.setText(f"💡 Play {b.san(move)}.")
        self.mission_result.setStyleSheet("font-size:14px; font-weight:bold; padding:6px; color:#7dd3fc;")

    # ================================================================ misc
    def _toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def _about(self):
        QMessageBox.about(self, "About", f"<h2>{APP_TITLE}</h2><p>A medieval fantasy battle chess game built with "
                                         "Python, PyQt6 and Qt Quick 3D.</p><p>Rules by python-chess. Built-in AI, "
                                         "coach, lessons and puzzles. Optional Stockfish support: put "
                                         "<code>stockfish.exe</code> next to the game.</p>")

    def closeEvent(self, event):
        self._cancel_jobs()
        for job in list(self.jobs.values()):
            job.wait(1500)
        from game import chess_ai
        if chess_ai._stockfish is not None:
            chess_ai._stockfish.close()
        super().closeEvent(event)
