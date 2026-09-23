"""panel/strip.py 单元测试：尺寸、位置、窗口标志、自绘。"""
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

from panel.strip import Strip, STRIP_WIDTH, STRIP_HEIGHT, EDGE_MARGIN, BOTTOM_MARGIN


def test_strip_size_constants():
    """Strip 尺寸常量与电脑管家参考一致：37×75。"""
    assert STRIP_WIDTH == 37
    assert STRIP_HEIGHT == 75


def test_strip_window_flags_have_stays_on_top_and_tool(qapp):
    """Strip 必须 WindowStaysOnTopHint（永远在最前）+ Tool（不进任务栏）。"""
    s = Strip()
    flags = s.windowFlags()
    assert flags & QtCore.Qt.WindowStaysOnTopHint
    assert flags & QtCore.Qt.Tool
    assert flags & QtCore.Qt.FramelessWindowHint


def test_strip_default_size_37x75(qapp):
    """构造后 size = (37, 75)。"""
    s = Strip()
    assert s.width() == 37
    assert s.height() == 75


def test_strip_reposition_to_right_edge(qapp, monkeypatch):
    """_reposition_to_right_edge 把窗口贴到屏幕右边、距底 BOTTOM_MARGIN。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(
        QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen()
    )
    s = Strip()
    s._reposition_to_right_edge()
    assert s.x() == 1920 - 37 - EDGE_MARGIN
    assert s.y() == 1080 - 75 - BOTTOM_MARGIN


def test_strip_reposition_skips_when_screen_invalid(qapp, monkeypatch):
    """primaryScreen 返 0×0 → 跳过（log warning + 不动位置）。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 0, 0)
    monkeypatch.setattr(
        QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen()
    )
    s = Strip()
    before = s.pos()
    s._reposition_to_right_edge()
    assert s.pos() == before


def test_strip_paint_event_does_not_crash(qapp):
    """paintEvent 不抛异常（自绘半透明圆角矩形）。"""
    s = Strip()
    s.resize(37, 75)
    s.show()
    QtCore.QCoreApplication.processEvents()
    s.repaint()
    assert True


def test_strip_status_dot_green_on_connected(qapp):
    """on_connected() → 状态点 connected property 为 true（颜色由 QSS 决定）。"""
    s = Strip()
    s.on_connected()
    # v3.2 样式大改：颜色走 QSS，用 property 驱动（不再 setStyleSheet）
    assert s._status_dot.property("connected") == "true"


def test_strip_status_dot_red_on_disconnected(qapp):
    """on_disconnected() → 状态点 connected property 为 false（颜色由 QSS 决定）。"""
    s = Strip()
    s.on_disconnected()
    # v3.2 样式大改：颜色走 QSS，用 property 驱动（不再 setStyleSheet）
    assert s._status_dot.property("connected") == "false"


def test_strip_left_click_emits_show_requested(qapp):
    """左键 mousePressEvent → emit show_requested。"""
    from PyQt5 import QtCore, QtGui
    s = Strip()
    received = []
    s.show_requested.connect(lambda: received.append(True))
    ev = QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonPress,
        QtCore.QPoint(10, 10),
        QtCore.QPoint(10, 10),
        QtCore.Qt.LeftButton,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier,
    )
    s.mousePressEvent(ev)
    assert received == [True]


def test_strip_right_click_no_emit(qapp):
    """右键 mousePressEvent 不 emit show_requested。"""
    from PyQt5 import QtCore, QtGui
    s = Strip()
    received = []
    s.show_requested.connect(lambda: received.append(True))
    ev = QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonPress,
        QtCore.QPoint(10, 10),
        QtCore.QPoint(10, 10),
        QtCore.Qt.RightButton,
        QtCore.Qt.RightButton,
        QtCore.Qt.NoModifier,
    )
    s.mousePressEvent(ev)
    assert received == []


def test_strip_mouse_move_with_drag_reposition(qapp):
    """drag_offset 非空 + 左键 → 移到新位置。"""
    from PyQt5 import QtCore, QtGui
    s = Strip()
    s._drag_offset = QtCore.QPoint(0, 0)
    s.move(50, 50)
    ev = QtGui.QMouseEvent(
        QtCore.QEvent.MouseMove,
        QtCore.QPoint(200, 200),
        QtCore.QPoint(200, 200),
        QtCore.Qt.NoButton,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier,
    )
    s.mouseMoveEvent(ev)
    assert abs(s.x() - 200) < 5
    assert abs(s.y() - 200) < 5


def test_strip_release_offscreen_snaps_back(qapp, monkeypatch):
    """拖到屏外（screenAt 返 None）→ release 后回到右边缘。"""
    from PyQt5 import QtCore, QtGui
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(
        QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen()
    )
    monkeypatch.setattr(
        QtWidgets.QApplication, "screenAt", lambda *args, **kwargs: None
    )
    s = Strip()
    s._drag_offset = QtCore.QPoint(0, 0)
    # 假装被拖到屏外 (-9999, -9999)
    s.move(-9999, -9999)
    s.mouseReleaseEvent(QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonRelease,
        QtCore.QPoint(-9999, -9999),
        QtCore.QPoint(-9999, -9999),
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoButton,
        QtCore.Qt.NoModifier,
    ))
    # 应被吸回右边缘
    assert s.x() == 1920 - 37 - EDGE_MARGIN
    assert s.y() == 1080 - 75 - BOTTOM_MARGIN
    assert s._drag_offset is None