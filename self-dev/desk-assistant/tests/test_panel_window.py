"""panel/panel_window.py 单元测试：构造、窗口标志、隐藏态、collapse 按钮、slide 动画。"""
import pytest
from PyQt5 import QtCore, QtGui, QtTest, QtWidgets

from panel.panel_window import (
    PanelWindow,
    PANEL_WIDTH,
    PANEL_HEIGHT,
    EDGE_MARGIN,
    SLIDE_DURATION_MS,
)


def test_panel_size_constants():
    """PanelWindow 尺寸保持现状 960×800。"""
    assert PANEL_WIDTH == 960
    assert PANEL_HEIGHT == 800


def test_panel_starts_hidden_after_init(qapp):
    """PanelWindow.__init__ 不调 show()，构造后 isHidden() == True。"""
    p = PanelWindow()
    assert p.isHidden()


def test_panel_no_window_stays_on_bottom_hint(qapp):
    """PanelWindow 不再用 WindowStaysOnBottomHint（按需弹出而非常驻沉底）。"""
    p = PanelWindow()
    flags = p.windowFlags()
    assert not (flags & QtCore.Qt.WindowStaysOnBottomHint)


def test_panel_has_close_btn_on_top_right(qapp):
    """close_btn 仍在右上角（✕ 退出 app）。"""
    p = PanelWindow()
    p.resize(PANEL_WIDTH, PANEL_HEIGHT)
    p.show()
    QtCore.QCoreApplication.processEvents()
    expected_x = p.width() - p.close_btn.width() - 8
    assert p.close_btn.x() == expected_x
    assert p.close_btn.y() == 8


def test_panel_collapse_btn_exists_on_left(qapp):
    """collapse_btn（›）位于面板左侧 8px 处。"""
    p = PanelWindow()
    p.resize(PANEL_WIDTH, PANEL_HEIGHT)
    p.show()
    QtCore.QCoreApplication.processEvents()
    assert p.collapse_btn.x() == 8
    assert p.collapse_btn.y() > 0
    # › 字符（指向右侧 strip）
    assert "›" in p.collapse_btn.text()


def test_panel_has_window_stays_on_top_hint(qapp):
    """PanelWindow 必须 WindowStaysOnTopHint（展开时不被其他 app 遮）。"""
    p = PanelWindow()
    flags = p.windowFlags()
    assert flags & QtCore.Qt.WindowStaysOnTopHint


# ---- 原 test_main.py 中的 Panel 测试（搬过来）----


@pytest.fixture
def panel(qapp):
    """构造 PanelWindow 并用调用计数替身替换 _refresh_* 方法。"""
    p = PanelWindow()
    calls = {"metrics": 0, "events": 0}
    p._refresh_metrics = lambda: calls.__setitem__("metrics", calls["metrics"] + 1)
    p._refresh_events = lambda: calls.__setitem__("events", calls["events"] + 1)
    p._test_calls = calls
    return p


def test_panel_sse_hello_dispatches_immediate_refresh(panel):
    panel.on_sse_event("hello", {"protocol": 1})
    assert panel._test_calls["metrics"] == 1
    assert panel._test_calls["events"] == 1
    assert not panel._refresh_metrics_timer.isActive()
    assert not panel._refresh_events_timer.isActive()


def test_panel_sse_metrics_changed_starts_metrics_timer(panel):
    panel.on_sse_event("metrics.changed", {"id": "cpu"})
    assert panel._refresh_metrics_timer.isActive()
    assert panel._test_calls["metrics"] == 0


def test_panel_sse_events_changed_starts_events_timer(panel):
    panel.on_sse_event("events.changed", {"reason": "insert", "id": 1})
    assert panel._refresh_events_timer.isActive()
    assert panel._test_calls["events"] == 0


def test_panel_sse_unknown_event_ignored(panel):
    panel.on_sse_event("something.else", {})
    assert not panel._refresh_metrics_timer.isActive()
    assert not panel._refresh_events_timer.isActive()
    assert panel._test_calls == {"metrics": 0, "events": 0}


def test_panel_on_connected_sets_status_green(panel):
    panel.on_connected()
    assert "connected" in panel.status.text()
    # v3.2 样式大改：状态颜色走 QSS，用 property 驱动
    assert panel.status.property("connected") == "true"


def test_panel_on_disconnected_sets_status_red(panel):
    panel.on_disconnected()
    assert "reconnecting" in panel.status.text()
    # v3.2 样式大改：状态颜色走 QSS，用 property 驱动
    assert panel.status.property("connected") == "false"


def test_panel_tab_default_is_chat(qapp):
    p = PanelWindow()
    # v3.2 样式大改：tab 顺序调整为 对话/小欧/指标/事件，默认改为 index 0 = 对话
    assert p._current_tab_index == 0
    assert p._stack.currentIndex() == 0
    assert p._tabs[0].isChecked()  # 对话默认选中
    for i in range(1, len(p._tabs)):
        assert not p._tabs[i].isChecked()


def test_panel_show_animated_triggers_refresh(qapp, monkeypatch):
    """show_animated 触发一次 _refresh_metrics + _refresh_events（不等 debounce）。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    p = PanelWindow()
    calls = {"metrics": 0, "events": 0}
    p._refresh_metrics = lambda: calls.__setitem__("metrics", calls["metrics"] + 1)
    p._refresh_events = lambda: calls.__setitem__("events", calls["events"] + 1)
    p.show_animated()
    # 立即调用一次（不等 debounce timer）
    assert calls["metrics"] == 1
    assert calls["events"] == 1


def test_panel_show_animated_results_in_visible_and_on_screen(qapp, monkeypatch):
    """show_animated 完成后 panel 可见，pos 在屏幕内。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    p = PanelWindow()
    p.show_animated()
    # 等动画结束（200ms + buffer）
    QtCore.QCoreApplication.processEvents()
    QtTest.QTest.qWait(SLIDE_DURATION_MS + 100)
    QtCore.QCoreApplication.processEvents()
    assert p.isVisible()
    # x 应小于 1920（在屏内）
    assert p.x() < 1920


def test_panel_slide_out_then_hide(qapp, monkeypatch):
    """_slide_out 完成后（动画 200ms）panel 自动 hide()。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    p = PanelWindow()
    p.show()  # 先 show 才能 slide_out
    p._slide_out()
    # 等动画结束
    QtTest.QTest.qWait(SLIDE_DURATION_MS + 100)
    QtCore.QCoreApplication.processEvents()
    assert p.isHidden()


def test_panel_slide_in_then_slide_out_overlap_ends_hidden(qapp, monkeypatch):
    """slide_in 中调 slide_out 不会动画叠加，最终状态是隐藏。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    p = PanelWindow()
    p.show_animated()
    # 立刻调 slide_out（动画进行中）
    p._slide_out()
    QtTest.QTest.qWait(SLIDE_DURATION_MS + 100)
    QtCore.QCoreApplication.processEvents()
    assert p.isHidden()


def test_panel_slide_out_fades_window_opacity(qapp, monkeypatch):
    """slide_out 期间 windowOpacity 线性 1.0→0.0，结束恢复 1.0 + hide。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    p = PanelWindow()
    p.resize(PANEL_WIDTH, PANEL_HEIGHT)
    p.move(940, 140)
    p.show()
    QtCore.QCoreApplication.processEvents()
    # 初始 opacity 应为 1.0
    assert p.windowOpacity() == 1.0
    p._slide_out()
    # 等动画到一半：opacity 应介于 0 和 1 之间
    QtTest.QTest.qWait(SLIDE_DURATION_MS // 2)
    QtCore.QCoreApplication.processEvents()
    mid_opacity = p.windowOpacity()
    assert 0.0 < mid_opacity < 1.0, "slide_out 中段 opacity 应在 (0,1) 之间，实际 %s" % mid_opacity
    # 等动画结束：opacity 恢复 1.0，panel hide
    QtTest.QTest.qWait(SLIDE_DURATION_MS + 100)
    QtCore.QCoreApplication.processEvents()
    assert p.windowOpacity() == 1.0
    assert p.isHidden()


def test_panel_no_tool_window_flag(qapp):
    """PanelWindow 不能是 Qt.Tool 窗口（Wayland 上 Tool 失焦会自隐）。

    Qt.Tool = Qt.Window | 0xa；只检查 0xa 这位（Tool 特有位），
    否则会和 Qt.Window 共用 bit 误判。
    """
    p = PanelWindow()
    flags_int = int(p.windowFlags())
    tool_specific = int(QtCore.Qt.Tool) & ~int(QtCore.Qt.Window)
    assert not (flags_int & tool_specific), \
        "PanelWindow 不应有 Qt.Tool 标志 (flags=%d)" % flags_int
