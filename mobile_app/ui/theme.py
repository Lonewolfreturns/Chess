"""Visual themes: environments, army styles, fonts and the Qt stylesheet."""
from __future__ import annotations

from dataclasses import dataclass

import chess

from effects.magic import ARCANE, CELESTIAL, FIRE, ICE, NATURE, Palette

APP_TITLE = "Wizard War Chess"

TITLE_FONT = "Palatino Linotype"
BODY_FONT = "Segoe UI"

GOLD = "#e8c372"
VIOLET = "#a879ff"
TEXT = "#ece6f5"
MUTED = "#a89fbd"
PANEL = "#1a1626"
BG = "#0e0c15"


@dataclass(frozen=True)
class Environment:
    key: str
    name: str
    light: str             # light square
    dark: str              # dark square
    frame: str             # frame stone colour
    frame_edge: str        # frame bevel highlight
    rune: tuple            # glowing rune colour
    coord: str             # coordinate label colour
    bg_top: str
    bg_bottom: str
    fog: tuple             # fog colour
    fog_alpha: float
    ambient: str           # embers | fireflies | runes | stars | ash
    torch: Palette
    texture: str           # stone | moss | marble | crystal | basalt
    description: str = ""


ENVIRONMENTS: dict[str, Environment] = {e.key: e for e in [
    Environment("castle", "Castle Keep", "#c9bfa9", "#6b6157", "#4a4038", "#8c7a63", (255, 190, 90),
                "#f3d9a4", "#2a1f1a", "#0b0807", (255, 200, 150), 0.10, "embers", FIRE, "stone",
                "Torch-lit stone hall of an ancient fortress."),
    Environment("forest", "Dark Forest", "#a9b38c", "#435036", "#2f3a26", "#6f7f52", (150, 255, 170),
                "#d8f0b8", "#0f2016", "#030806", (190, 230, 200), 0.18, "fireflies", NATURE, "moss",
                "A misty glade deep in the enchanted woods."),
    Environment("ruins", "Enchanted Ruins", "#d3cadc", "#5d4f72", "#3a3150", "#7d6c9c", (200, 140, 255),
                "#e9dcff", "#1d1233", "#06030c", (190, 160, 255), 0.14, "runes", ARCANE, "marble",
                "Crumbling temple where old magic still hums."),
    Environment("celestial", "Celestial Sanctum", "#ebe6d6", "#4f6f9a", "#2b3d5c", "#7d98c4", (150, 210, 255),
                "#e0efff", "#0b1430", "#02040c", (180, 210, 255), 0.10, "stars", ICE, "crystal",
                "A floating board among the stars."),
    Environment("volcano", "Volcanic Forge", "#9c8775", "#3f2c26", "#2a1c18", "#7a4a32", (255, 120, 40),
                "#ffc58a", "#2b0d05", "#080201", (255, 140, 90), 0.12, "ash", FIRE, "basalt",
                "A war-forge carved into a living volcano."),
]}


@dataclass(frozen=True)
class Material:
    fill: tuple            # gradient stops top -> bottom (hex strings)
    line: str              # detail line colour
    glow: tuple            # rgb aura colour
    rim: str               # rim light colour
    gem: tuple             # rgb gem/orb colour
    glowing_lines: bool = False


@dataclass(frozen=True)
class ArmyStyle:
    key: str
    name: str
    white_army: str
    black_army: str
    white: Material
    black: Material
    white_palette: Palette
    black_palette: Palette

    def material(self, color: bool) -> Material:
        return self.white if color == chess.WHITE else self.black

    def palette(self, color: bool) -> Palette:
        return self.white_palette if color == chess.WHITE else self.black_palette

    def army(self, color: bool) -> str:
        return self.white_army if color == chess.WHITE else self.black_army


ARMY_STYLES: dict[str, ArmyStyle] = {s.key: s for s in [
    ArmyStyle(
        "celestial_arcane", "Celestial vs Arcane", "Celestial Order", "Arcane Shadow",
        Material(("#fffdf5", "#f4e7c8", "#d9bf8a", "#a8864e"), "#6b4b16", (255, 215, 120), "#fff6d8",
                 (110, 190, 255)),
        Material(("#6a4f8f", "#3a2758", "#22143a", "#120a20"), "#d1a6ff", (176, 92, 255), "#c08cff",
                 (255, 72, 196), glowing_lines=True),
        CELESTIAL, ARCANE),
    ArmyStyle(
        "ice_fire", "Frost vs Flame", "Frost Legion", "Ember Horde",
        Material(("#ffffff", "#dff4ff", "#a8d8f5", "#5f9dcc"), "#1d5c8f", (150, 215, 255), "#ffffff",
                 (120, 230, 255)),
        Material(("#6b2216", "#3d120b", "#250805", "#140302"), "#ffae5c", (255, 120, 40), "#ff9a55",
                 (255, 210, 80), glowing_lines=True),
        ICE, FIRE),
    ArmyStyle(
        "classic", "Ivory vs Ebony", "Ivory Kingdom", "Ebony Dominion",
        Material(("#fffaf0", "#f0e2c8", "#d5bf98", "#a58a62"), "#4a3519", (255, 230, 170), "#ffffff",
                 (220, 60, 60)),
        Material(("#5a4a3e", "#33271f", "#1d1612", "#0e0a08"), "#c9a46a", (210, 170, 110), "#a07c50",
                 (90, 200, 120)),
        CELESTIAL, Palette((255, 236, 200), (205, 160, 90), (240, 120, 60), (90, 50, 20), (60, 45, 35))),
]}

DEFAULT_ENV = "castle"
DEFAULT_STYLE = "celestial_arcane"


def stylesheet(mobile: bool = False) -> str:
    return _BASE_CSS() + (_MOBILE_CSS() if mobile else "")


def _BASE_CSS() -> str:
    return f"""
    QWidget {{
        background: {BG};
        color: {TEXT};
        font-family: "{BODY_FONT}";
        font-size: 13px;
    }}
    QMainWindow, QDialog {{ background: {BG}; }}
    QMenuBar {{ background: #120f1c; color: {TEXT}; border-bottom: 1px solid #2c2440; }}
    QMenuBar::item {{ padding: 5px 12px; background: transparent; }}
    QMenuBar::item:selected {{ background: #2a2140; border-radius: 4px; }}
    QMenu {{ background: #1a1528; border: 1px solid #3b2f55; padding: 4px; }}
    QMenu::item {{ padding: 6px 26px 6px 18px; border-radius: 4px; }}
    QMenu::item:selected {{ background: #3a2a5c; }}
    QMenu::item:checked {{ color: {GOLD}; }}
    QMenu::separator {{ height: 1px; background: #3b2f55; margin: 4px 8px; }}

    QPushButton {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2f2547, stop:1 #1d1630);
        border: 1px solid #4b3b6e;
        border-radius: 7px;
        padding: 7px 14px;
        color: {TEXT};
        font-weight: 600;
    }}
    QPushButton:hover {{ border-color: {GOLD}; color: #fff3d6;
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3d2f5e, stop:1 #241b3c); }}
    QPushButton:pressed {{ background: #160f26; }}
    QPushButton:disabled {{ color: #6b6380; border-color: #2c2440; background: #17121f; }}
    QPushButton#primary {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f3d48a, stop:1 #b88a35);
        color: #24170a; border: 1px solid #ffe7a8;
    }}
    QPushButton#primary:hover {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffe4a3, stop:1 #c99a42); }}
    QPushButton#primary:disabled {{ background: #2a2236; color: #7d7390; border: 1px solid #3b2f55; }}
    QPushButton#danger {{ border-color: #7a2e3e; }}
    QPushButton#danger:hover {{ border-color: #ff6b81; color: #ffd6dc; }}
    QPushButton#tool {{ padding: 6px 8px; min-width: 34px; font-size: 15px; }}

    QLabel {{ background: transparent; }}
    QLabel#title {{ font-family: "{TITLE_FONT}"; font-size: 20px; font-weight: bold; color: {GOLD}; }}
    QLabel#subtitle {{ color: {MUTED}; }}
    QLabel#panelTitle {{ font-family: "{TITLE_FONT}"; font-size: 15px; font-weight: bold; color: {GOLD}; }}

    QFrame#panel {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1c172b, stop:1 #141020);
        border: 1px solid #33294b; border-radius: 10px;
    }}
    QFrame#card {{ background: #1f1930; border: 1px solid #3b2f55; border-radius: 10px; }}
    QFrame#card:hover {{ border-color: {GOLD}; }}

    QListWidget, QTextBrowser, QTableWidget, QPlainTextEdit, QLineEdit {{
        background: #120f1b; border: 1px solid #2f2645; border-radius: 8px;
        selection-background-color: #3a2a5c; selection-color: #fff;
    }}
    QListWidget::item {{ padding: 4px; border-radius: 4px; }}
    QListWidget::item:hover {{ background: #221b33; }}
    QTableWidget {{ gridline-color: transparent; }}
    QHeaderView::section {{ background: #1a1528; color: {MUTED}; border: none; padding: 4px; }}
    QTableCornerButton::section {{ background: #1a1528; border: none; }}

    QComboBox, QSpinBox {{
        background: #1d1730; border: 1px solid #3b2f55; border-radius: 6px; padding: 5px 8px; min-height: 20px;
    }}
    QComboBox:hover, QSpinBox:hover {{ border-color: {GOLD}; }}
    QComboBox QAbstractItemView {{ background: #1a1528; border: 1px solid #3b2f55; selection-background-color: #3a2a5c; }}
    QCheckBox {{ spacing: 8px; background: transparent; }}
    QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; }}
    QRadioButton {{ background: transparent; spacing: 8px; }}
    QSlider::groove:horizontal {{ height: 6px; background: #2a2140; border-radius: 3px; }}
    QSlider::handle:horizontal {{ background: {GOLD}; width: 16px; margin: -6px 0; border-radius: 8px; }}
    QSlider::sub-page:horizontal {{ background: {VIOLET}; border-radius: 3px; }}

    QTabWidget::pane {{ border: 1px solid #33294b; border-radius: 8px; top: -1px; background: #141020; }}
    QTabBar::tab {{ background: #1a1528; color: {MUTED}; padding: 7px 14px; border-top-left-radius: 7px;
        border-top-right-radius: 7px; margin-right: 2px; }}
    QTabBar::tab:selected {{ background: #2a2140; color: {GOLD}; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: #3b2f55; border-radius: 4px; min-height: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar:horizontal {{ height: 0; }}
    QToolTip {{ background: #1f1930; color: {TEXT}; border: 1px solid {GOLD}; padding: 6px; border-radius: 4px; }}
    QGroupBox {{ border: 1px solid #33294b; border-radius: 8px; margin-top: 14px; padding: 10px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 12px; color: {GOLD}; }}
    QSplitter::handle {{ background: transparent; }}
    """


def _MOBILE_CSS() -> str:
    """Bigger touch targets, thin scroll bars and a lighter palette for phones and tablets."""
    return f"""
    QWidget {{ font-size: 14px; background: #1c1536; color: #f4efff; }}
    QLabel, QCheckBox, QRadioButton {{ background: transparent; }}
    QMainWindow, QDialog {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2d2160, stop:0.6 #1f1840, stop:1 #2a1838); }}
    QFrame#panel {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #34286a, stop:1 #241c4a);
        border: 1px solid #6d58b0; border-radius: 12px; }}
    QFrame#card {{ background: #2e2460; border: 1px solid #7a64c4; }}
    QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5a46a0, stop:1 #3a2d72);
        border: 1px solid #8c74d8; color: #ffffff; }}
    QPushButton:pressed {{ background: #2a2058; border-color: {GOLD}; }}
    QPushButton:disabled {{ color: #9a90b8; border-color: #4a3d78; background: #2a2250; }}
    QPushButton#primary {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffe39a, stop:1 #e0a83e);
        color: #2a1606; border: 1px solid #fff0c4; }}
    QPushButton#primary:disabled {{ background: #3a3060; color: #9a90b8; border: 1px solid #4a3d78; }}
    QListWidget, QTextBrowser, QTableWidget, QPlainTextEdit, QLineEdit {{ background: #241c48;
        border: 1px solid #5a4896; selection-background-color: #6a52b8; }}
    QHeaderView::section {{ background: #2e2460; color: #d8ccf4; }}
    QComboBox, QSpinBox {{ background: #2e2460; border: 1px solid #6d58b0; }}
    QTabWidget::pane {{ background: #241c4a; border: 1px solid #5a4896; }}
    QTabBar::tab {{ background: #2e2460; color: #d0c4ee; }}
    QTabBar::tab:selected {{ background: #4a3a8a; color: {GOLD}; }}
    QLabel#subtitle {{ color: #d0c4ee; }}
    QPushButton {{ min-height: 30px; padding: 8px 10px; border-radius: 9px; }}
    QPushButton#tool {{ min-height: 30px; font-size: 17px; }}
    QPushButton#bar {{ padding: 6px 4px; font-size: 13px; min-width: 0px; }}
    QPushButton#burger {{ font-size: 20px; padding: 4px 10px; min-width: 34px; }}
    QComboBox, QSpinBox, QLineEdit {{ min-height: 34px; font-size: 15px; }}
    QCheckBox, QRadioButton {{ min-height: 34px; font-size: 15px; }}
    QCheckBox::indicator, QRadioButton::indicator {{ width: 22px; height: 22px; }}
    QTabBar::tab {{ padding: 9px 14px; font-size: 14px; }}
    QListWidget::item {{ padding: 10px 6px; }}
    QListWidget::item:hover {{ background: transparent; }}
    QSlider::groove:horizontal {{ height: 8px; }}
    QSlider::handle:horizontal {{ width: 26px; margin: -9px 0; border-radius: 13px; }}
    QScrollBar:vertical {{ width: 4px; margin: 0px; }}
    QScrollBar::handle:vertical {{ background: #4b3b6e; border-radius: 2px; min-height: 30px; }}
    QMenu::item {{ padding: 12px 30px 12px 20px; font-size: 15px; }}
    QFrame#drawer {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2d2160, stop:1 #1c1536);
        border-right: 1px solid #6d58b0; }}
    QPushButton#drawerItem {{ text-align: left; padding: 12px 16px; font-size: 15px; font-weight: 500;
        background: transparent; border: none; border-radius: 8px; }}
    QPushButton#drawerItem:pressed {{ background: #4a3a8a; }}
    QPushButton#drawerItem:disabled {{ color: #5a5370; background: transparent; }}
    QLabel#drawerSection {{ color: {MUTED}; font-size: 12px; font-weight: bold; padding: 12px 16px 2px 16px;
        letter-spacing: 1px; }}
    QLabel#mobileTitle {{ font-family: "{TITLE_FONT}"; font-size: 16px; font-weight: bold; color: {GOLD}; }}
    """
