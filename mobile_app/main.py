"""Wizard War Chess - entry point (desktop, Android and iOS).

Run:  python main.py              (desktop)
      python main.py --mobile     (try the phone layout on a PC)
Build the Windows .exe:  python build_exe.py
Build the Android app:   see MOBILE.md
"""
import multiprocessing
import os
import sys

from platform_info import IS_ANDROID, IS_IOS, IS_MOBILE, IS_PHONE_OS, data_dir, phone_window_size


def _log_exception(exc_type, exc, tb):
    """Log unexpected errors instead of letting Qt abort the game."""
    import traceback
    traceback.print_exception(exc_type, exc, tb)
    try:
        with open(os.path.join(data_dir(), "error.log"), "a", encoding="utf-8") as f:
            traceback.print_exception(exc_type, exc, tb, file=f)
    except OSError:
        pass


def _setup_fonts(app):
    """Map the Windows fonts the game asks for onto fonts phones actually have."""
    from PySide6.QtGui import QFont
    if IS_ANDROID:
        QFont.insertSubstitutions("Palatino Linotype", ["Noto Serif", "serif"])
        QFont.insertSubstitutions("Consolas", ["Droid Sans Mono", "monospace"])
        QFont.insertSubstitutions("Segoe UI", ["Roboto", "sans-serif"])
    elif IS_IOS:
        QFont.insertSubstitutions("Palatino Linotype", ["Palatino", "Georgia"])
        QFont.insertSubstitutions("Consolas", ["Menlo", "Courier"])
        QFont.insertSubstitutions("Segoe UI", [".AppleSystemUIFont", "Helvetica Neue"])
    if not IS_PHONE_OS:
        app.setFont(QFont("Segoe UI", 10))


def main():
    sys.excepthook = _log_exception
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    if IS_ANDROID:
        # sound/music through Android's own media player (the app ships without FFmpeg)
        os.environ.setdefault("QT_MEDIA_BACKEND", "android")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Wizard War Chess")
    app.setOrganizationName("WizardWarChess")
    _setup_fonts(app)

    from ui.theme import stylesheet

    app.setStyleSheet(stylesheet(IS_MOBILE))
    splash = None
    if "--selftest" not in sys.argv and "--no-splash" not in sys.argv:
        from ui.splash import Splash
        splash = Splash()
        splash.present()
        splash.step(0.08, "Opening the spellbook…")

    import ui.main_window as main_window
    if splash is not None:
        splash.step(0.2, "Forging the battlefield…")
        main_window.progress_hook = splash.step
    import time
    t_start = time.perf_counter()
    window = main_window.MainWindow()
    main_window.progress_hook = None
    if IS_PHONE_OS:
        print(f"[wwc] main window built in {time.perf_counter() - t_start:.2f}s", flush=True)
    app.applicationStateChanged.connect(window.on_app_state)
    if "--selftest" in sys.argv:
        _selftest(app, window)
    elif IS_PHONE_OS:
        window.showMaximized()
    elif IS_MOBILE:
        window.resize(*phone_window_size())     # phone layout preview on a PC
        window.show()
    else:
        window.showMaximized()
    if splash is not None:
        splash.finish(window)
    sys.exit(app.exec())


def _selftest(app, window):
    """Hidden check used after building: play an AI battle off-screen and write a report."""
    from PySide6.QtCore import Qt, QTimer

    out = sys.argv[sys.argv.index("--selftest") + 1] if len(sys.argv) > sys.argv.index("--selftest") + 1 \
        else "selftest.txt"
    errors = []
    old_hook = sys.excepthook

    def hook(t, e, tb):
        errors.append(f"{t.__name__}: {e}")
        old_hook(t, e, tb)
    sys.excepthook = hook
    window.resize(*(phone_window_size() if IS_MOBILE else (1400, 860)))
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
                    f"mobile={IS_MOBILE}\nerrors={len(errors)}\n" + "\n".join(errors))
        app.quit()
    QTimer.singleShot(16000, finish)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
