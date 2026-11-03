"""Simulated fingers on the 3D board: pinch zoom, two-finger orbit, swipe, tap-to-move.

    python tests/touch_check.py      (prints TOUCH TEST PASSED / FAILED)
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("WWC_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_touch_cache"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
app = QApplication(sys.argv[:1])
from scene3d.view3d import Board3D
import chess
b = Board3D()
w = b.widget
w.resize(400, 420); w.show()
def spin(sec):
    t=time.time()
    while time.time()-t < sec:
        app.processEvents(); time.sleep(0.01)
spin(2.0)
r = b.root
b.camera.auto_orbit = False
dev = QTest.createTouchDevice()
def props(): return {k: round(float(r.property(k)), 2) for k in ("distance", "yaw", "pitch")}
print("start", props())
c = QPoint(200, 210)
# pinch out: fingers move apart -> zoom in (distance smaller)
QTest.touchEvent(w, dev).press(0, c + QPoint(-30, 0)).press(1, c + QPoint(30, 0)).commit()
spin(0.05)
for i in range(1, 11):
    QTest.touchEvent(w, dev).move(0, c + QPoint(-30 - 8*i, 0)).move(1, c + QPoint(30 + 8*i, 0)).commit()
    spin(0.03)
QTest.touchEvent(w, dev).release(0, c + QPoint(-110, 0)).release(1, c + QPoint(110, 0)).commit()
spin(0.3)
p1 = props(); print("after pinch-out", p1)
# two-finger drag sideways -> orbit (yaw changes)
QTest.touchEvent(w, dev).press(0, c + QPoint(-40, 0)).press(1, c + QPoint(40, 0)).commit(); spin(0.05)
for i in range(1, 11):
    QTest.touchEvent(w, dev).move(0, c + QPoint(-40 + 10*i, 0)).move(1, c + QPoint(40 + 10*i, 0)).commit(); spin(0.03)
QTest.touchEvent(w, dev).release(0, c + QPoint(60, 0)).release(1, c + QPoint(140, 0)).commit(); spin(0.3)
p2 = props(); print("after two-finger drag", p2)
# one finger drag on empty space (top of view = sky) -> orbit
top = QPoint(200, 30)
QTest.touchEvent(w, dev).press(0, top).commit(); spin(0.05)
for i in range(1, 11):
    QTest.touchEvent(w, dev).move(0, top + QPoint(8*i, 0)).commit(); spin(0.03)
QTest.touchEvent(w, dev).release(0, top + QPoint(80, 0)).commit(); spin(0.3)
p3 = props(); print("after one-finger drag on sky", p3)
# tap a white pawn: find e2 on screen via projecting? use the QML boardHit search over a grid
b.set_flipped(False, duration=0.01); b.camera.go(yaw=0, pitch=60, distance=15, duration=0.01); spin(0.6)
found = None
for y in range(40, 410, 6):
    for x in range(20, 390, 6):
        h = b.call("boardHit", x, y); h = h.toVariant() if hasattr(h, "toVariant") else h
        if h and h.get("ok") and h.get("sq", -1) == chess.E2:
            found = QPoint(x, y); break
    if found: break
print("e2 on screen at", found)
moves = []
b.move_requested.connect(lambda m: moves.append(m.uci()))
b.interactive = True; b.human_colors = {chess.WHITE}
QTest.touchEvent(w, dev).press(0, found).commit(); spin(0.05)
QTest.touchEvent(w, dev).release(0, found).commit(); spin(0.3)
print("selected after tap:", b.selected, "(e2 =", chess.E2, ")")
# tap e4
target = None
for y in range(40, 410, 6):
    for x in range(20, 390, 6):
        h = b.call("boardHit", x, y); h = h.toVariant() if hasattr(h, "toVariant") else h
        if h and h.get("ok") and chess.square(int((h["x"]+4)//1), int((4-h["z"])//1)) == chess.E4 and h.get("sq",-1) < 0:
            target = QPoint(x, y); break
    if target: break
QTest.touchEvent(w, dev).press(0, target).commit(); spin(0.05)
QTest.touchEvent(w, dev).release(0, target).commit(); spin(0.3)
print("move requested:", moves)
ok = p1["distance"] < 15.0 and abs(p2["yaw"] - p1["yaw"]) > 5 and abs(p3["yaw"] - p2["yaw"]) > 5 and b.selected in (chess.E2, None) and moves == ["e2e4"]
print("TOUCH TEST", "PASSED" if ok else "FAILED")
