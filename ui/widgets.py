"""Side widgets: evaluation bar, player panels, move list, coach log."""
from __future__ import annotations

import math

import chess
from PyQt6.QtCore import QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (QAbstractItemView, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QHeaderView,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout,
                             QWidget)

from game import rules
from game.coach import win_prob

from .theme import GOLD, MUTED, TITLE_FONT, ArmyStyle


class EvalBar(QWidget):
    """Vertical bar showing who is winning (learning aid)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(26)
        self.target = 0.5
        self.value = 0.5
        self.text = "0.0"
        self.flipped = False
        self.white_rgb = (245, 230, 190)
        self.black_rgb = (70, 40, 110)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(30)
        self.setToolTip("Evaluation bar: how much the balance favours each army")

    def set_style(self, style: ArmyStyle):
        self.white_rgb = style.white_palette.main
        self.black_rgb = style.black_palette.deep
        self.update()

    def set_score(self, cp_white: int, mate_white: int | None = None):
        if mate_white is not None:
            self.target = 1.0 if mate_white > 0 else 0.0
            self.text = f"M{abs(mate_white)}"
        else:
            self.target = win_prob(cp_white)
            self.text = f"{abs(cp_white) / 100:.1f}"
        self.update()

    def reset(self):
        self.target = 0.5
        self.text = "0.0"

    def _step(self):
        if abs(self.value - self.target) > 0.001:
            self.value += (self.target - self.value) * 0.12
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(3, 2, -3, -2)
        p.setPen(QPen(QColor("#3b2f55"), 1))
        p.setBrush(QColor(*self.black_rgb))
        p.drawRoundedRect(r, 6, 6)
        frac = self.value
        h = r.height() * frac
        wr = QRectF(r.left(), r.bottom() - h, r.width(), h) if not self.flipped else QRectF(r.left(), r.top(), r.width(), h)
        g = QLinearGradient(wr.left(), 0, wr.right(), 0)
        c = QColor(*self.white_rgb)
        g.setColorAt(0, c.lighter(130))
        g.setColorAt(1, c.darker(115))
        p.setBrush(QBrush(g))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(wr, 6, 6)
        p.setPen(QPen(QColor(255, 255, 255, 90), 1, Qt.PenStyle.DashLine))
        p.drawLine(int(r.left()), int(r.center().y()), int(r.right()), int(r.center().y()))
        f = QFont()
        f.setPixelSize(10)
        f.setBold(True)
        p.setFont(f)
        white_ahead = frac >= 0.5
        at_bottom = white_ahead != self.flipped
        p.setPen(QColor(30, 20, 10) if white_ahead else QColor(240, 230, 255))
        tr = QRectF(r.left(), r.bottom() - 18, r.width(), 16) if at_bottom else QRectF(r.left(), r.top() + 2, r.width(), 16)
        p.drawText(tr, Qt.AlignmentFlag.AlignCenter, self.text)


class PlayerPanel(QFrame):
    """Name, army, captured pieces, material balance, clock and 'thinking' state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setFixedHeight(58)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 12, 4)
        lay.setSpacing(10)
        self.avatar = QLabel()
        self.avatar.setFixedSize(46, 46)
        lay.addWidget(self.avatar)
        col = QVBoxLayout()
        col.setSpacing(0)
        self.name = QLabel("Player")
        self.name.setStyleSheet(f"font-family:'{TITLE_FONT}'; font-size:15px; font-weight:bold; color:{GOLD};")
        self.army = QLabel("")
        self.army.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        col.addWidget(self.name)
        col.addWidget(self.army)
        lay.addLayout(col)
        self.captured = QLabel()
        self.captured.setMinimumHeight(26)
        lay.addWidget(self.captured, 1)
        self.status = QLabel("")
        self.status.setStyleSheet("color:#c4b5fd; font-style:italic;")
        lay.addWidget(self.status)
        self.clock = QLabel("")
        self.clock.setMinimumWidth(84)
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.clock)
        self._active = False
        self._dots = 0
        self._thinking = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._anim)
        self._timer.start(400)
        self._set_clock_style(False, False)

    def setup(self, name: str, color: bool, style: ArmyStyle, avatar: QPixmap):
        self.name.setText(name)
        self.army.setText(style.army(color))
        self.avatar.setPixmap(avatar.scaled(46, 46, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))

    def set_captured(self, pieces: list[int], color_of_pieces: bool, advantage: int, renderer, style):
        if not pieces and advantage <= 0:
            self.captured.clear()
            return
        size = 22
        w = max(1, len(pieces)) * (size - 8) + 50
        pix = QPixmap(w, size + 4)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        x = 0
        for pt in pieces:
            pm = renderer.pixmap(pt, color_of_pieces, style)
            p.drawPixmap(QRectF(x, 2, size, size), pm, QRectF(pm.rect()))
            x += size - 8
        if advantage > 0:
            f = QFont()
            f.setPixelSize(13)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(GOLD))
            p.drawText(QRectF(x + 12, 0, 40, size + 4), Qt.AlignmentFlag.AlignVCenter, f"+{advantage}")
        p.end()
        self.captured.setPixmap(pix)

    def set_active(self, active: bool):
        self._active = active
        self.setStyleSheet("QFrame#panel { border: 1px solid %s; }" % (GOLD if active else "#33294b"))
        self._set_clock_style(active, False)

    def set_thinking(self, on: bool):
        self._thinking = on
        if not on:
            self.status.setText("")

    def set_clock(self, ms: int | None, low: bool = False):
        if ms is None:
            self.clock.setText("")
            self.clock.setVisible(False)
            return
        self.clock.setVisible(True)
        s = max(0, ms) / 1000
        if s >= 60:
            text = f"{int(s // 60)}:{int(s % 60):02d}"
        else:
            text = f"{s:0.1f}"
        self.clock.setText(text)
        self._set_clock_style(self._active, low)

    def _set_clock_style(self, active, low):
        bg = "#3a1420" if low else ("#2c2245" if active else "#15111f")
        fg = "#ff9aa8" if low else (GOLD if active else MUTED)
        self.clock.setStyleSheet(f"background:{bg}; color:{fg}; border:1px solid #3b2f55; border-radius:6px;"
                                 f"font-family:'Consolas'; font-size:20px; font-weight:bold; padding:2px 8px;")

    def _anim(self):
        if self._thinking:
            self._dots = (self._dots + 1) % 4
            self.status.setText("casting" + "." * self._dots)


class MoveList(QTableWidget):
    ply_clicked = pyqtSignal(int)   # ply after the clicked move

    def __init__(self, parent=None):
        super().__init__(0, 3, parent)
        self.setHorizontalHeaderLabels(["#", "White", "Black"])
        self.verticalHeader().setVisible(False)
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.setColumnWidth(0, 36)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cellClicked.connect(self._clicked)
        self._start_black = False

    def set_records(self, records, start_turn_black: bool, current_ply: int | None = None):
        self._start_black = start_turn_black
        self.setRowCount(0)
        offset = 1 if start_turn_black else 0
        n = len(records) + offset
        rows = (n + 1) // 2
        self.setRowCount(rows)
        for row in range(rows):
            num = QTableWidgetItem(f"{row + 1}.")
            num.setForeground(QColor(MUTED))
            num.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.setItem(row, 0, num)
        for i, rec in enumerate(records):
            idx = i + offset
            row, col = idx // 2, 1 + idx % 2
            text = rec.san + (rec.annotation or "")
            item = QTableWidgetItem(text)
            if rec.annotation and rec.annotation in ("??", "?"):
                item.setForeground(QColor("#f87171"))
            elif rec.annotation == "?!":
                item.setForeground(QColor("#facc15"))
            elif rec.annotation in ("!", "!!"):
                item.setForeground(QColor("#5eead4"))
            if rec.comment:
                item.setToolTip(rec.comment)
            item.setData(Qt.ItemDataRole.UserRole, i + 1)
            self.setItem(row, col, item)
        if current_ply is not None and current_ply > 0:
            idx = current_ply - 1 + offset
            self.setCurrentCell(idx // 2, 1 + idx % 2)
        self.scrollToBottom() if current_ply is None else None

    def highlight_ply(self, ply: int):
        offset = 1 if self._start_black else 0
        if ply <= 0:
            self.clearSelection()
            return
        idx = ply - 1 + offset
        self.setCurrentCell(idx // 2, 1 + idx % 2)

    def _clicked(self, row, col):
        item = self.item(row, col)
        if item is None or col == 0:
            return
        ply = item.data(Qt.ItemDataRole.UserRole)
        if ply:
            self.ply_clicked.emit(int(ply))


class CoachLog(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenExternalLinks(False)
        self.setStyleSheet("QTextBrowser { font-size: 13px; padding: 6px; }")
        self.document().setDefaultStyleSheet("p { margin: 0 0 8px 0; }")

    def say(self, html: str, icon: str = "🧙"):
        self.append(f"<p>{icon} {html}</p>")
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


def avatar_pixmap(renderer, style, color: bool, size: int = 92) -> QPixmap:
    """King portrait in a glowing medallion."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    pal = style.palette(color)
    g = QLinearGradient(0, 0, 0, size)
    g.setColorAt(0, QColor(*pal.deep).lighter(140))
    g.setColorAt(1, QColor(10, 6, 18))
    p.setBrush(QBrush(g))
    p.setPen(QPen(QColor(*pal.main), 3))
    p.drawEllipse(QRectF(2, 2, size - 4, size - 4))
    km = renderer.pixmap(chess.KING, color, style)
    p.drawPixmap(QRectF(size * 0.1, size * 0.04, size * 0.8, size * 0.8), km, QRectF(km.rect()))
    p.end()
    return pix


class GameOverPanel(QFrame):
    """Shown over the board when a battle ends: play again, new battle, review or main menu."""
    action = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gameOver")
        self.setMaximumWidth(680)
        self.setStyleSheet(f"QFrame#gameOver {{ background: rgba(16, 11, 28, 238); border: 2px solid {GOLD}; "
                           "border-radius: 16px; }")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 18, 26, 20)
        lay.setSpacing(8)
        self.title = QLabel()
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.title)
        self.subtitle = QLabel()
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet("color:#ece6f5; font-size:14px;")
        lay.addWidget(self.subtitle)
        self.stats = QLabel()
        self.stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats.setWordWrap(True)
        self.stats.setStyleSheet(f"color:{MUTED}; font-size:13px; padding:4px;")
        lay.addWidget(self.stats)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.buttons = {}
        for key, text in (("again", "⚔  Play again"), ("new", "⚙  New battle…"), ("review", "👁  Review game"),
                          ("home", "🏰  Main menu")):
            b = QPushButton(text)
            b.setMinimumHeight(40)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            if key == "again":
                b.setObjectName("primary")
            b.clicked.connect(lambda _=False, k=key: self.action.emit(k))
            row.addWidget(b)
            self.buttons[key] = b
        lay.addLayout(row)
        self.hide()

    def show_result(self, title: str, subtitle: str, rgb, stats_html: str):
        r, g, b = rgb
        self.title.setText(title)
        self.title.setStyleSheet(f"font-family:'{TITLE_FONT}'; font-size:34px; font-weight:bold; "
                                 f"color: rgb({r},{g},{b}); letter-spacing:4px;")
        self.subtitle.setText(subtitle)
        self.stats.setText(stats_html)
        self.show()
        self.raise_()
