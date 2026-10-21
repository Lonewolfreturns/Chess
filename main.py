"""Wizard War Chess - entry point.

Run:  python main.py
Build the .exe:  python build_exe.py
"""
import multiprocessing
import os
import sys


def _log_exception(exc_type, exc, tb):
    """Log unexpected errors instead of letting Qt abort the game."""
    import traceback
    traceback.print_exception(exc_type, exc, tb)
    try:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        os.makedirs(os.path.join(base, "WizardWarChess"), exist_ok=True)
        with open(os.path.join(base, "WizardWarChess", "error.log"), "a", encoding="utf-8") as f:
            traceback.print_exception(exc_type, exc, tb, file=f)
    except OSError:
        pass


def main():
    sys.excepthook = _log_exception
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Wizard War Chess")
    app.setOrganizationName("WizardWarChess")
    app.setFont(QFont("Segoe UI", 10))

    from ui.main_window import MainWindow
    from ui.theme import stylesheet

    app.setStyleSheet(stylesheet())
    window = MainWindow()
    if "--selftest" in sys.argv:
        _selftest(app, window)
    else:
        window.showMaximized()
    sys.exit(app.exec())


def _selftest(app, window):
    """Hidden check used after building: play an AI battle off-screen and write a report."""
    from PyQt6.QtCore import Qt, QTimer

    out = sys.argv[sys.argv.index("--selftest") + 1] if len(sys.argv) > sys.argv.index("--selftest") + 1 \
        else "selftest.txt"
    errors = []
    old_hook = sys.excepthook

    def hook(t, e, tb):
        errors.append(f"{t.__name__}: {e}")
        old_hook(t, e, tb)
    sys.excepthook = hook
    window.resize(1400, 860)
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.show()
    window.sounds.set_enabled(False)
    window.sounds.set_music(False)
    QTimer.singleShot(1500, lambda: window.start_game({**window.cfg, "mode": "aivai", "level": 1, "level2": 1}))

    def finish():
        window.grab().save(os.path.splitext(out)[0] + ".png")
        with open(out, "w", encoding="utf-8") as f:
            tracks = len(window.music.all_tracks) if window.music else 0
            f.write(f"3d={window.board is window.board3d}\nplies={window.game.ply}\n"
                    f"sounds_ready={window.sounds._ready}\nmusic_tracks={tracks}\n"
                    f"errors={len(errors)}\n" + "\n".join(errors))
        app.quit()
    QTimer.singleShot(16000, finish)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
