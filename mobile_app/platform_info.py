"""Where the game is running (desktop, Android, iOS) and where it may write files.

Phones get a touch layout. To try the phone layout on a PC, run:
    python main.py --mobile                 (phone-sized window, portrait)
    python main.py --mobile --phone 844x390 (landscape)
or set the environment variable WWC_MOBILE=1.
"""
from __future__ import annotations

import os
import sys

IS_ANDROID = (sys.platform == "android" or hasattr(sys, "getandroidapilevel")
              or "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ)
IS_IOS = sys.platform == "ios" or (sys.platform == "darwin" and os.uname().machine.startswith("iP"))
IS_PHONE_OS = IS_ANDROID or IS_IOS

# Touch layout: real phones/tablets, or forced for testing on a PC.
IS_MOBILE = IS_PHONE_OS or "--mobile" in sys.argv or os.environ.get("WWC_MOBILE", "") not in ("", "0")
IS_WINDOWS = sys.platform.startswith("win")

APP_DIR_NAME = "WizardWarChess"


def phone_window_size() -> tuple[int, int]:
    """Window size used when testing the phone layout on a PC (``--phone WxH``)."""
    if "--phone" in sys.argv:
        try:
            w, h = sys.argv[sys.argv.index("--phone") + 1].lower().split("x")
            return int(w), int(h)
        except (IndexError, ValueError):
            pass
    return 390, 844


def data_dir() -> str:
    """A writable folder for caches, logs and the user's own music."""
    base = os.environ.get("WWC_DATA_DIR")
    if not base and IS_PHONE_OS:
        try:
            from PySide6.QtCore import QStandardPaths
            base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        except Exception:
            base = ""
        base = base or os.environ.get("ANDROID_PRIVATE") or os.environ.get("HOME") or os.getcwd()
    elif not base:
        root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        base = os.path.join(root, APP_DIR_NAME)
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        pass
    return base


def app_dir() -> str:
    """Folder that holds the game's own files (scene3d/qml, assets, ...)."""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
