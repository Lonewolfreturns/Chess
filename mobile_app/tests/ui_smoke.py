"""Drive every screen of the game automatically and save screenshots.

    python tests/ui_smoke.py OUTDIR                 (desktop layout)
    python tests/ui_smoke.py OUTDIR --mobile        (phone layout, portrait)
    python tests/ui_smoke.py OUTDIR --mobile --phone 844x390   (phone, landscape)

Writes OUTDIR/report.txt (errors found) and OUTDIR/*.png.
"""
from __future__ import annotations

import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "smoke_out")
os.makedirs(OUT, exist_ok=True)

import chess  # noqa: E402
from PySide6.QtCore import QEvent, Qt, QTimer, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from platform_info import IS_MOBILE, phone_window_size  # noqa: E402

errors: list[str] = []
log: list[str] = []


def hook(t, e, tb):
    errors.append("".join(traceback.format_exception(t, e, tb)))
    traceback.print_exception(t, e, tb)


sys.excepthook = hook


def qt_messages(mode, ctx, msg):
    low = msg.lower()
    if any(k in low for k in ("error", "typeerror", "referenceerror", "cannot", "failed", "unable")) \
            and "disconnect" not in low and "pw.conf" not in low:
        errors.append(f"Qt: {msg}")
    log.append(msg)


qInstallMessageHandler(qt_messages)

app = QApplication(sys.argv)
from ui import main_window  # noqa: E402
from ui.menus import LessonBrowser, NewGameDialog, PromotionDialog, PuzzleBrowser  # noqa: E402
from ui.theme import stylesheet  # noqa: E402

app.setStyleSheet(stylesheet(IS_MOBILE))


class AutoBox:
    """Stands in for QMessageBox: always answers Yes."""
    StandardButton = QMessageBox.StandardButton

    @staticmethod
    def question(*a, **k):
        return QMessageBox.StandardButton.Yes

    @staticmethod
    def information(*a, **k):
        return QMessageBox.StandardButton.Ok

    warning = information
    about = information


main_window.QMessageBox = AutoBox
shots: list[str] = []


def shot(name: str, widget=None):
    w = widget or win
    QApplication.processEvents()
    path = os.path.join(OUT, f"{len(shots):02d}_{name}.png")
    w.grab().save(path)
    shots.append(path)


def fake_exec(self):
    self.show()
    t0 = time.time()
    while time.time() - t0 < 0.4:
        QApplication.processEvents()
    shot("dialog_" + type(self).__name__, self)
    if isinstance(self, NewGameDialog):
        self.level.setCurrentIndex(0)
        self.tc.setCurrentIndex(0)
        self.side.setCurrentIndex(0)
    if isinstance(self, LessonBrowser):
        self.selected = main_window.LESSONS[0].id
    if isinstance(self, PuzzleBrowser):
        self.selected = main_window.PUZZLES[0].id
    if isinstance(self, PromotionDialog):
        self.choice = chess.QUEEN
    self.hide()
    return 1


QDialog.exec = fake_exec

win = main_window.MainWindow()
win.resize(*(phone_window_size() if IS_MOBILE else (1400, 860)))
win.show()
win.sounds.set_enabled(False)
win.sounds.set_music(False)
win.cfg["anim_mode"] = "quick"
win._apply_settings()


def wait_until(cond, timeout=25.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        QApplication.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def pause(sec):
    wait_until(lambda: False, sec)


def human_move(uci):
    win._on_move_requested(chess.Move.from_uci(uci))


def back_key():
    for et in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QApplication.sendEvent(win, QKeyEvent(et, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))


def step(name, fn):
    try:
        fn()
        log.append(f"ok   {name}")
    except Exception:
        errors.append(f"step {name}:\n{traceback.format_exc()}")
        log.append(f"FAIL {name}")


def run():
    pause(2.5)
    step("home", lambda: shot("home"))
    if IS_MOBILE:
        def drawer():
            win.open_drawer()
            pause(0.4)
            shot("drawer")
            win.drawer._activate(None, None, win._drawer_items()[[e[1] for e in win._drawer_items()].index(
                "🏔  3D location")][3]["page"])
            pause(0.2)
            shot("drawer_location_page")
            win.drawer.back_or_close()
            win.drawer.back_or_close()
        step("drawer", drawer)
    step("new game dialog", lambda: win.new_game_dialog("ai"))
    pause(1.5)

    def play_vs_ai():
        assert win.mode == "ai", win.mode
        wait_until(lambda: win.board.interactive, 10)
        human_move("e2e4")
        assert wait_until(lambda: win.game.ply >= 2 and win.board.interactive, 40), "AI did not reply"
        human_move("g1f3")
        assert wait_until(lambda: win.game.ply >= 4 and win.board.interactive, 40), "AI did not reply (2)"
    step("play vs AI", play_vs_ai)

    def hint():
        win.hint()
        wait_until(lambda: "💡" in win.status.text(), 20)
        pause(0.8)
        shot("game_hint")
    step("hint", hint)
    step("undo", lambda: (win.undo(), pause(0.5)))
    step("redo", lambda: (win.redo(), pause(0.5)))
    step("browse", lambda: (win._browse_to(1), pause(0.3), shot("browse"), win._browse_to(win.game.ply)))
    step("flip", lambda: (win.flip(), pause(1.0), win.flip()))
    step("coach tab", lambda: (win.tabs.setCurrentIndex(1), pause(0.3), shot("coach_tab"), win.tabs.setCurrentIndex(0)))
    step("camera views", lambda: (win.board3d.view_top(), pause(1.2), shot("view_top"), win.board3d.view_white()))
    if IS_MOBILE:
        def pinch_like():
            r = win.board3d.root
            d0 = float(r.property("distance"))
            r.setProperty("distance", d0 * 0.7)
            pause(0.5)
            shot("zoomed")
            r.setProperty("distance", d0)
        step("zoom", pinch_like)

    def to_2d():
        win._toggle_view_mode()
        pause(1.5)
        shot("board_2d")
        wait_until(lambda: win.board.interactive, 10)
        human_move("d2d4")
        assert wait_until(lambda: win.game.ply >= 6 and win.board.interactive, 40), "AI did not reply in 2D"
        win._toggle_view_mode()
        pause(1.0)
    step("2D board", to_2d)
    step("settings dialog", win.settings_dialog)
    step("help dialog", win.show_help)
    step("promotion dialog", lambda: win._ask_promotion(chess.WHITE))
    step("copy/paste PGN", lambda: (win.copy_pgn() if IS_MOBILE else None))

    def resign():
        win.resign()
        assert wait_until(lambda: win.over_panel.isVisible(), 15), "game over panel not shown"
        pause(0.3)
        shot("game_over_resign")
    step("resign", resign)
    step("paste PGN", lambda: (win.paste_pgn() if IS_MOBILE else None, pause(1.0)))

    def fools_mate():
        win.start_game({**win.cfg, "mode": "pvp", "tc": 0})
        win.cfg["anim_mode"] = "full"
        win._apply_settings()
        for uci in ("f2f3", "e7e5", "g2g4", "d8h4"):
            assert wait_until(lambda: win.board.interactive, 25), f"board not ready before {uci}"
            human_move(uci)
        assert wait_until(lambda: win.over_panel.isVisible(), 60), "checkmate panel not shown"
        pause(0.3)
        shot("checkmate")
        win.cfg["anim_mode"] = "quick"
        win._apply_settings()
    step("checkmate", fools_mate)

    def lesson():
        win.lesson_browser()
        pause(1.5)
        shot("lesson")
        win.hint()
        pause(0.5)
        win._mission_retry()
        pause(0.5)
    step("lesson", lesson)

    def puzzle():
        win.puzzle_browser()
        pause(1.5)
        shot("puzzle")
        win.hint()
        win.hint()
        pause(0.5)
        p = win.puzzle
        from game import rules
        mv = rules.find_mate(win.game.board, win.puz_remaining) if p.kind == "mate" else \
            chess.Move.from_uci(p.solution[0])
        human_move(mv.uci())
        wait_until(lambda: "solved" in win.mission_result.text().lower() or "correct" in win.mission_result.text().lower(), 30)
        pause(1.0)
        shot("puzzle_after_move")
    step("puzzle", puzzle)

    def back_button():
        win.start_game({**win.cfg, "mode": "ai"})
        pause(1.0)
        if IS_MOBILE:
            back_key()
            pause(0.5)
            assert win.mode == "home", f"Back did not return home (mode={win.mode})"
    step("back button", back_button)

    if IS_MOBILE:
        def rotate():
            w, h = win.width(), win.height()
            win.resize(h, w)
            pause(1.5)
            shot("rotated_home")
            win.start_game({**win.cfg, "mode": "ai"})
            pause(2.0)
            shot("rotated_game")
            win.resize(w, h)
            pause(1.0)
            shot("rotated_back")
        step("rotate", rotate)

    with open(os.path.join(OUT, "report.txt"), "w", encoding="utf-8") as f:
        f.write(f"mobile={IS_MOBILE} size={win.width()}x{win.height()}\n")
        f.write("\n".join(x for x in log if x.startswith(("ok", "FAIL"))) + "\n")
        f.write(f"errors={len(errors)}\n" + "\n---\n".join(errors))
    app.quit()


QTimer.singleShot(200, run)
app.exec()
