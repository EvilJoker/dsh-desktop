"""panel/window_manager.py 单元测试：拼装三部件 + SSEClient 单例。"""
import pytest
from PyQt5 import QtCore, QtTest, QtWidgets

from panel.window_manager import WindowManager
from panel.panel_window import PanelWindow, SLIDE_DURATION_MS
from panel.strip import Strip


def test_window_manager_creates_strip_and_panel(qapp):
    """WindowManager 持有 strip + panel 实例。"""
    wm = WindowManager()
    assert isinstance(wm.strip, Strip)
    assert isinstance(wm.panel, PanelWindow)


def test_window_manager_panel_starts_hidden(qapp):
    """PanelWindow 构造后 isHidden（不在 WindowManager 里临时 show）。"""
    wm = WindowManager()
    assert wm.panel.isHidden()


def test_window_manager_strip_is_visible(qapp, monkeypatch):
    """Strip 在 WindowManager 里被 show。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    wm = WindowManager()
    assert wm.strip.isVisible()


def test_window_manager_sse_client_singleton(qapp, monkeypatch):
    """SSEClient 只 new 一次（被 strip + panel 共享引用）。"""
    from panel import window_manager as wm_mod
    constructed = {"count": 0}
    real_sse = wm_mod.SSEClient

    class CountingSSE(real_sse):
        def __init__(self, *a, **kw):
            constructed["count"] += 1
            super().__init__(*a, **kw)

    monkeypatch.setattr(wm_mod, "SSEClient", CountingSSE)
    wm = WindowManager()
    # strip 和 panel 拿到的是同一个 sse 实例引用
    assert wm._sse is wm._sse_reference  # 见实现
    assert constructed["count"] == 1


def test_window_manager_strip_click_expands_when_panel_hidden(qapp, monkeypatch):
    """strip 按钮 toggle：panel 隐藏时点击 → 展开。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    wm = WindowManager()
    assert wm.panel.isHidden()
    show_called = {"c": 0}
    slide_called = {"c": 0}
    wm.panel.show_animated = lambda: show_called.__setitem__("c", show_called["c"] + 1)
    wm.panel._slide_out = lambda: slide_called.__setitem__("c", slide_called["c"] + 1)
    wm.strip.show_requested.emit()
    assert show_called["c"] == 1
    assert slide_called["c"] == 0


def test_window_manager_strip_click_collapses_when_panel_visible(qapp, monkeypatch):
    """strip 按钮 toggle：panel 显示时点击 → 折叠。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    wm = WindowManager()
    wm.panel.show_animated()
    QtTest.QTest.qWait(SLIDE_DURATION_MS + 100)
    QtCore.QCoreApplication.processEvents()
    assert wm.panel.isVisible()
    show_called = {"c": 0}
    slide_called = {"c": 0}
    wm.panel.show_animated = lambda: show_called.__setitem__("c", show_called["c"] + 1)
    wm.panel._slide_out = lambda: slide_called.__setitem__("c", slide_called["c"] + 1)
    wm.strip.show_requested.emit()
    assert slide_called["c"] == 1
    assert show_called["c"] == 0


def test_window_manager_panel_collapse_triggers_slide_out(qapp, monkeypatch):
    """panel.collapse_requested → panel._slide_out 被调。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    wm = WindowManager()
    called = {"slide": 0}
    wm.panel.collapse_requested.disconnect(wm.panel._slide_out)
    wm.panel.collapse_requested.connect(lambda: called.__setitem__("slide", called["slide"] + 1))
    wm.panel.collapse_requested.emit()
    assert called["slide"] == 1


def test_window_manager_sse_connected_propagates_to_strip_and_panel(qapp):
    """sse.connected → strip.on_connected + panel.on_connected 都被调。"""
    wm = WindowManager()
    strip_called = {"c": 0}
    panel_called = {"c": 0}
    # 同样：原连接在 __init__ 期间已建立，断开后接 spy 验证连线存在。
    wm._sse.connected.disconnect(wm.strip.on_connected)
    wm._sse.connected.disconnect(wm.panel.on_connected)
    wm._sse.connected.connect(lambda: strip_called.__setitem__("c", strip_called["c"] + 1))
    wm._sse.connected.connect(lambda: panel_called.__setitem__("c", panel_called["c"] + 1))
    wm._sse.connected.emit()
    assert strip_called["c"] == 1
    assert panel_called["c"] == 1


def test_window_manager_screen_change_repositions_strip(qapp, monkeypatch):
    """geometryChanged → strip 重新定位（Panel 隐藏时不调）。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    wm = WindowManager()
    # 把 _reposition 替成计数
    strip_called = {"c": 0}
    panel_called = {"c": 0}
    wm.strip._reposition_to_right_edge = lambda: strip_called.__setitem__("c", strip_called["c"] + 1)
    wm.panel._reposition_to_right_edge = lambda: panel_called.__setitem__("c", panel_called["c"] + 1)
    wm._on_screen_changed(None)
    assert strip_called["c"] == 1
    assert panel_called["c"] == 0  # panel 隐藏时不调


def test_window_manager_full_flow_collapse_after_show(qapp, monkeypatch):
    """完整流程：show_animated → panel 可见 → collapse_requested → panel 隐藏。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    wm = WindowManager()
    # 模拟 Strip 点击 → panel.show_animated
    wm.panel.show_animated()
    QtTest.QTest.qWait(SLIDE_DURATION_MS + 100)
    QtCore.QCoreApplication.processEvents()
    assert wm.panel.isVisible()
    # 模拟 › 点击 → panel._slide_out
    wm.panel.collapse_requested.emit()
    QtTest.QTest.qWait(SLIDE_DURATION_MS + 100)
    QtCore.QCoreApplication.processEvents()
    assert wm.panel.isHidden()


def test_window_manager_global_shortcut_activates_toggle(qapp, monkeypatch):
    """NdeGlobalShortcut.activated 触发时 → _toggle_panel 被调（等效 strip 点击）。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    wm = WindowManager()
    # 替换 _toggle_panel 为 spy
    toggle_called = {"c": 0}
    wm._toggle_panel = lambda: toggle_called.__setitem__("c", toggle_called["c"] + 1)
    # 重新连信号（构造时连的是原方法）
    if wm._global_shortcut.is_registered():
        wm._global_shortcut.activated.disconnect()
        wm._global_shortcut.activated.connect(wm._toggle_panel)
        wm._global_shortcut.activated.emit()
        assert toggle_called["c"] == 1


def test_window_manager_global_shortcut_client_trigger_calls_panel(qapp, monkeypatch):
    """Nde-globalkeysd 模拟：调 client.Trigger() → _toggle_panel 被调。
    这是 nde 派发的真实入口链路。用 unique bus name 隔离避免上一个
    测试的 Publication 还在 GIO 注册表里导致 'already exported'。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    # 用 unique bus name + path，避免和前一个测试的 Publication 撞
    from panel import global_shortcut as gs_mod
    orig_init = gs_mod.NdeGlobalShortcut.__init__

    def patched_init(self, shortcut_str, bus_name, object_path, description, parent=None):
        return orig_init(
            self, shortcut_str,
            "org.deskassistant.panel.test_trigger",
            "/deskassistant/shortcut_test_trigger",
            description, parent,
        )
    monkeypatch.setattr(gs_mod.NdeGlobalShortcut, "__init__", patched_init)

    wm = WindowManager()
    if not wm._global_shortcut.is_registered():
        pytest.skip("nde-globalkeysd unavailable in this env")
    # 拿到 nde 实际会 call 的 client object
    client = wm._global_shortcut._client
    toggle_called = {"c": 0}
    wm._toggle_panel = lambda: toggle_called.__setitem__("c", toggle_called["c"] + 1)
    wm._global_shortcut.activated.disconnect()
    wm._global_shortcut.activated.connect(wm._toggle_panel)
    # 模拟 nde call
    client.Trigger()
    assert toggle_called["c"] == 1
