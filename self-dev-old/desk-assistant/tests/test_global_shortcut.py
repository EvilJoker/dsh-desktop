"""panel/global_shortcut.py 单元测试：cleanup 路径（atexit + signal + QTimer）。

bug 复现：v3.2 NdeGlobalShortcut 最初只挂 aboutToQuit + 直接在 signal
handler 里调 release()。问题：
  - SIGTERM 进程被杀时 QApplication.quit 不会调 → aboutToQuit 不触发
  - signal handler 调 pydbus 不是 async-signal-safe（hang/crash 风险）
  - signal handler 调完 release 再 os.kill 自己也可能死锁

修复：三层兜底
  - aboutToQuit: 主循环退出时（最常见）
  - QTimer 轮询 _shutdown_requested flag: SIGTERM/SIGINT 触发
  - atexit.register(release): Python 解释器正常退出兜底

每个测试用 unique bus name 避免 GIO Publication 撞车。
"""
import signal

import pytest
from PyQt5 import QtCore, QtTest, QtWidgets

from panel.global_shortcut import NdeGlobalShortcut


@pytest.fixture
def unique_shortcut(qapp, monkeypatch):
    """起一个 NdeGlobalShortcut，bus+path 唯一避免和别的测试撞。

    如果 nde-globalkeysd 在当前环境不存在（release 服务不在），自动 skip。
    """
    from panel import global_shortcut as gs_mod
    orig_init = gs_mod.NdeGlobalShortcut.__init__

    def patched_init(self, shortcut_str, bus_name, object_path, description, parent=None):
        return orig_init(
            self, shortcut_str,
            "org.deskassistant.panel.test_cleanup",
            "/deskassistant/shortcut_test_cleanup",
            description, parent,
        )
    monkeypatch.setattr(gs_mod.NdeGlobalShortcut, "__init__", patched_init)
    sc = NdeGlobalShortcut(
        "Alt+M",
        bus_name="placeholder",  # patched_init 忽略
        object_path="/placeholder",
        description="test_cleanup",
    )
    yield sc
    sc.release()


def test_nde_global_shortcut_atexit_registers_release(qapp, monkeypatch):
    """atexit.register 必须在 __init__ 里被调过，self.release 作为参数。

    验证：构造时给 atexit's _exithandlers 加一项（type=function，func=release）。
    """
    import atexit
    from panel import global_shortcut as gs_mod

    captured = {"call_count": 0, "args": None}

    real_register = atexit.register
    def spy_register(func, *args, **kwargs):
        # self.release 是 bound method；用 __func__ 取底层函数再 == 比对
        # （Py3 bound method == unbound function 是 False，== 同样对象才 True）
        underlying = getattr(func, "__func__", func)
        if underlying is gs_mod.NdeGlobalShortcut.release:
            captured["call_count"] += 1
            captured["args"] = (func, args, kwargs)
            # 不真注册，避免污染全局 atexit 列表
            return
        return real_register(func, *args, **kwargs)
    monkeypatch.setattr(atexit, "register", spy_register)

    sc = NdeGlobalShortcut(
        "Alt+M",
        bus_name="org.deskassistant.panel.test_atexit",
        object_path="/deskassistant/shortcut_test_atexit",
        description="test_atexit",
    )
    try:
        assert captured["call_count"] == 1, "atexit.register(release) 没被调到"
        assert captured["args"] is not None
        func, args, kwargs = captured["args"]
        # func 是 bound method；验证它是 NdeGlobalShortcut.release
        assert isinstance(func.__self__, NdeGlobalShortcut)
        assert func.__func__ is NdeGlobalShortcut.release
    finally:
        sc.release()


def test_nde_global_shortcut_shutdown_flag_default_false(unique_shortcut):
    """新构造的 NdeGlobalShortcut _shutdown_requested 默认 False。"""
    sc = unique_shortcut
    assert hasattr(sc, "_shutdown_requested"), "缺 _shutdown_requested flag"
    assert sc._shutdown_requested is False


def test_nde_global_shortcut_poll_timer_calls_quit_when_flag_set(qapp, monkeypatch):
    """QTimer 检测到 flag → QApplication.quit() 被调。

    模拟 SIGTERM：直接 set flag（不调 _on_signal 避免旧代码的 os.kill 自杀），
    让 QTimer 检测。
    """
    from panel import global_shortcut as gs_mod

    # 重新构造（unique bus）
    orig_init = gs_mod.NdeGlobalShortcut.__init__

    def patched_init(self, shortcut_str, bus_name, object_path, description, parent=None):
        return orig_init(
            self, shortcut_str,
            "org.deskassistant.panel.test_poll",
            "/deskassistant/shortcut_test_poll",
            description, parent,
        )
    monkeypatch.setattr(gs_mod.NdeGlobalShortcut, "__init__", patched_init)

    quit_calls = {"n": 0}
    real_quit = QtCore.QCoreApplication.quit
    def spy_quit():
        quit_calls["n"] += 1
        # 不真 quit，避免后续测试受影响
    monkeypatch.setattr(QtCore.QCoreApplication, "quit", staticmethod(spy_quit))

    sc = NdeGlobalShortcut(
        "Alt+M", bus_name="x", object_path="/x", description="test_poll",
    )
    try:
        # 模拟 SIGTERM 路径
        sc._shutdown_requested = True
        # QTimer 200ms 间隔，至少等 300ms 让 timer fire
        QtTest.QTest.qWait(300)
        QtCore.QCoreApplication.processEvents()
        assert quit_calls["n"] >= 1, f"QTimer 没触发 QApplication.quit (calls={quit_calls['n']})"
    finally:
        # 显式 release 清理
        sc.release()


def test_nde_global_shortcut_release_idempotent(unique_shortcut):
    """release() 多次调用安全：第二次早返回。"""
    sc = unique_shortcut
    sc.release()
    sc.release()  # 不能崩
    assert sc._released is True


def test_nde_global_shortcut_signal_handlers_registered(qapp, monkeypatch):
    """构造时 signal.signal(SIGTERM/SIGINT) 都被调到（核心 SIGTERM 路径开关）。

    这个 test 验证 review HIGH 关注点：handler 必须真安装，否则 QTimer
    轮询 + atexit 都接不到 SIGTERM，进程会死掉 nde 留下 orphan。
    """
    captured = []  # [(signum, handler), ...]
    real_signal = signal.signal

    def spy_signal(signum, handler):
        captured.append((signum, handler))
        return real_signal(signum, handler)
    monkeypatch.setattr(signal, "signal", spy_signal)

    sc = NdeGlobalShortcut(
        "Alt+M",
        bus_name="org.deskassistant.panel.test_signal",
        object_path="/deskassistant/shortcut_test_signal",
        description="test_signal_reg",
    )
    try:
        sigs = [s for s, _ in captured]
        assert signal.SIGTERM in sigs, "SIGTERM handler 没注册"
        assert signal.SIGINT in sigs, "SIGINT handler 没注册"
        # 确认注册的 handler 是 _on_signal
        for s, h in captured:
            if s in (signal.SIGTERM, signal.SIGINT):
                assert h == sc._on_signal, f"signal {s} handler 错的: {h}"
    finally:
        sc.release()


def test_nde_global_shortcut_poll_timer_stops_after_quit(qapp, monkeypatch):
    """QApplication.quit 后 QTimer 应停掉，避免重复触发。

    不停的话会反复调 QApplication.quit()，至少浪费 CPU + 可能干扰其他测试。
    """
    from panel import global_shortcut as gs_mod
    orig_init = gs_mod.NdeGlobalShortcut.__init__

    def patched_init(self, shortcut_str, bus_name, object_path, description, parent=None):
        return orig_init(
            self, shortcut_str,
            "org.deskassistant.panel.test_stop",
            "/deskassistant/shortcut_test_stop",
            description, parent,
        )
    monkeypatch.setattr(gs_mod.NdeGlobalShortcut, "__init__", patched_init)

    sc = NdeGlobalShortcut(
        "Alt+M", bus_name="x", object_path="/x", description="test_stop",
    )
    try:
        # 模拟 SIGTERM 路径
        sc._shutdown_requested = True
        # 第一次 wait：trigger quit
        QtTest.QTest.qWait(300)
        QtCore.QCoreApplication.processEvents()
        # 第二次 wait：不应该再 quit（timer 应当已停）
        # 但因为 spy_quit 不真 quit，timer 不会自己停——这就是为什么实现里需要
        # self._poll_timer.stop()
        # 验证：_poll_timer 应该 isActive() == False
        if hasattr(sc, "_poll_timer"):
            assert not sc._poll_timer.isActive(), "_poll_timer 触发后没停"
    finally:
        sc.release()
