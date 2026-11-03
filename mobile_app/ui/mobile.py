"""Touch-screen helpers: slide-out menu drawer, finger scrolling and phone-sized dialogs."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import (QAbstractScrollArea, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QScroller, QScrollerProperties, QVBoxLayout, QWidget)

from platform_info import IS_MOBILE, IS_PHONE_OS


# ------------------------------------------------------------------ scrolling
def enable_touch_scroll(root: QWidget):
    """Let lists, text and scroll areas scroll by dragging a finger (kinetic, like a phone)."""
    if not IS_MOBILE or root is None:
        return
    gesture = (QScroller.ScrollerGestureType.TouchGesture if IS_PHONE_OS
               else QScroller.ScrollerGestureType.LeftMouseButtonGesture)
    areas = list(root.findChildren(QAbstractScrollArea))
    if isinstance(root, QAbstractScrollArea):
        areas.append(root)
    for area in areas:
        vp = area.viewport()
        if vp.property("wwcTouchScroll"):
            continue
        vp.setProperty("wwcTouchScroll", True)
        QScroller.grabGesture(vp, gesture)
        scroller = QScroller.scroller(vp)
        props = scroller.scrollerProperties()
        off = QScrollerProperties.OvershootPolicy.OvershootAlwaysOff
        props.setScrollMetric(QScrollerProperties.ScrollMetric.VerticalOvershootPolicy, off)
        props.setScrollMetric(QScrollerProperties.ScrollMetric.HorizontalOvershootPolicy, off)
        props.setScrollMetric(QScrollerProperties.ScrollMetric.DragStartDistance, 0.004)
        scroller.setScrollerProperties(props)


# ------------------------------------------------------------------ dialogs
def fit_dialog(dlg: QDialog, full: bool = True):
    """On phones, show a dialog filling the screen (or at least never wider than it)."""
    if not IS_MOBILE:
        return
    dlg.setMinimumSize(0, 0)
    enable_touch_scroll(dlg)
    host = dlg.parentWidget().window() if dlg.parentWidget() else None
    if IS_PHONE_OS:
        if full:
            dlg.setWindowState(dlg.windowState() | Qt.WindowState.WindowMaximized)
        else:
            scr = dlg.screen().availableGeometry() if dlg.screen() else None
            if scr is not None:
                dlg.setMaximumWidth(scr.width())
        return
    if host is not None:                       # phone preview on a PC
        g = host.geometry()
        if full:
            dlg.setGeometry(g)
        else:
            dlg.setMaximumWidth(g.width())
            dlg.adjustSize()
            dlg.move(g.center() - QPoint(dlg.width() // 2, dlg.height() // 2))


def scroll_wrap(inner: QWidget) -> QScrollArea:
    """Put a dialog page inside a scroll area so it fits small screens."""
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.Shape.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sa.setWidget(inner)
    return sa


# ------------------------------------------------------------------ drawer
class Drawer(QWidget):
    """The phone menu: a panel that slides in from the left over a dimmed screen.

    Items are given as a list of tuples:
        ("section", "TITLE")
        ("item", "Text", callback, {"checked": fn, "enabled": fn, "page": fn})
    A "page" option opens a sub-list (fn returns (title, items)) with a back button.
    Toggles ("checked") stay open after a tap; other items close the drawer first.
    """

    def __init__(self, host: QWidget):
        super().__init__(host)
        self.host = host
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("Drawer { background: rgba(4, 2, 10, 150); }")
        self.panel = QFrame(self)
        self.panel.setObjectName("drawer")
        pl = QVBoxLayout(self.panel)
        pl.setContentsMargins(6, 8, 6, 8)
        pl.setSpacing(2)
        head = QHBoxLayout()
        self.back_btn = QPushButton("‹")
        self.back_btn.setObjectName("burger")
        self.back_btn.clicked.connect(self._back)
        head.addWidget(self.back_btn)
        self.title = QLabel("")
        self.title.setObjectName("mobileTitle")
        head.addWidget(self.title, 1)
        close = QPushButton("✕")
        close.setObjectName("burger")
        close.clicked.connect(self.close_drawer)
        head.addWidget(close)
        pl.addLayout(head)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pl.addWidget(self.scroll, 1)
        self._root_title = ""
        self._root_items_fn = None
        self._stack: list = []
        self._anim = QPropertyAnimation(self.panel, b"pos", self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        host.installEventFilter(self)
        self.hide()

    # -------------------------------------------------------------- api
    def set_root(self, title: str, items_fn):
        """items_fn() builds the main list each time the drawer opens (so states are fresh)."""
        self._root_title = title
        self._root_items_fn = items_fn

    def open_drawer(self):
        self._stack = [(self._root_title, self._root_items_fn)]
        self._render()
        self._fit()
        self.show()
        self.raise_()
        w = self.panel.width()
        self._anim.stop()
        self._anim.setStartValue(QPoint(-w, 0))
        self._anim.setEndValue(QPoint(0, 0))
        self._anim.start()

    def close_drawer(self):
        self.hide()

    def is_open(self) -> bool:
        return self.isVisible()

    def back_or_close(self):
        if len(self._stack) > 1:
            self._back()
        else:
            self.close_drawer()

    # -------------------------------------------------------------- internals
    def _fit(self):
        r = self.host.rect()
        self.setGeometry(r)
        w = min(340, max(240, int(r.width() * 0.86)))
        self.panel.setGeometry(0, 0, w, r.height())

    def eventFilter(self, obj, event):
        if obj is self.host and event.type() == QEvent.Type.Resize and self.isVisible():
            self._fit()
        return False

    def mousePressEvent(self, event):
        if not self.panel.geometry().contains(event.position().toPoint()):
            self.close_drawer()
        event.accept()

    def _back(self):
        if len(self._stack) > 1:
            self._stack.pop()
            self._render()

    def _render(self):
        title, items_fn = self._stack[-1]
        items = items_fn() if callable(items_fn) else items_fn
        self.title.setText(title)
        self.back_btn.setVisible(len(self._stack) > 1)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        for entry in items:
            if entry[0] == "section":
                lab = QLabel(entry[1].upper())
                lab.setObjectName("drawerSection")
                lay.addWidget(lab)
                continue
            _, text, fn, *rest = entry
            opts = rest[0] if rest else {}
            checked = opts.get("checked")
            enabled = opts.get("enabled")
            page = opts.get("page")
            label = text
            if checked is not None:
                label = ("☑  " if checked() else "☐  ") + text
            if page is not None:
                label = f"{text}  ›"
            b = QPushButton(label)
            b.setObjectName("drawerItem")
            if enabled is not None and not enabled():
                b.setEnabled(False)
            b.clicked.connect(lambda _=False, f=fn, c=checked, p=page: self._activate(f, c, p))
            lay.addWidget(b)
        lay.addStretch(1)
        self.scroll.setWidget(content)
        enable_touch_scroll(self.scroll)

    def _activate(self, fn, checked, page):
        if page is not None:
            self._stack.append(page())
            self._render()
            return
        if checked is not None:
            fn()
            self._render()
            return
        self.close_drawer()
        QTimer.singleShot(0, fn)
