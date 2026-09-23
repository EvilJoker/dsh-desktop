"""scripts/smoke_test_edge_dock.py — 桌面助手 Edge Dock 启动 smoke 测试。

Task 14（真机手动验收）无法在 offscreen 环境完成，但能用此脚本验证：
  - panel.main 可正常 import
  - main() 函数是 launch shell（QApplication → 关系统代理 → WindowManager → exec_）
  - WindowManager() 可构造：strip 可见、panel 隐藏、SSE 实例存在
  - 5 种信号 / 7 receivers 全部就位（QObject.receivers() 计数）

v3.1：去掉 HotZoneWatcher（已删除）。现在 strip 是 toggle 按钮（点
击展开或折叠），面板上仍保留 › 按钮作为折叠入口。

用法（在 desk-assistant/ 目录下）：
  DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \\
    /usr/bin/python3.6 scripts/smoke_test_edge_dock.py

退出码：0 = 全过；非 0 = 任一断言失败。

真机验收清单（不在此脚本范围内，需 DISPLAY=:0 手工测）：
  [ ] 启动只看到右下角窄条（没有完整面板）
  [ ] 点窄条 → 面板从右滑入
  [ ] 再点窄条 → 面板滑出（toggle）
  [ ] 面板左侧 › → 面板滑出
  [ ] 面板右上 ✕ → app 退出
  [ ] 鼠标贴右不再自动展开（v3.1 移除）
  [ ] SSE 断 → 状态点变红（停 server 验证）
  [ ] SSE 重连 → 状态点变绿（重启 server 验证）
  [ ] 拖窄条到副屏 → 跟着过去
"""
import os
import sys
import inspect

# 确保能 import panel
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DESK_ASSISTANT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, DESK_ASSISTANT)

from PyQt5 import QtWidgets  # noqa: E402

# 1. QApplication
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
print("[0/4] QApplication created: OK")

# 2. import panel.main
print("[1/4] import panel.main: OK")
import panel.main  # noqa: E402

# 3. main() 必须是 launch shell
src = inspect.getsource(panel.main.main)
assert "QApplication" in src, "main() must create QApplication"
assert "WindowManager" in src, "main() must construct WindowManager"
assert "exec_" in src, "main() must call exec_()"
assert "Panel" not in src.replace("PanelWindow", ""), \
    "main() must not construct Panel directly"
assert "SSEClient" not in src, "main() must not construct SSEClient directly"
print("[2/4] main() is launch shell: OK")

# 4. 关键 export
import panel.sse_client
assert panel.sse_client.SSE_URL == "http://127.0.0.1:18675/events"
assert panel.main.WindowManager is not None
print("[3/4] key exports (SSE_URL, WindowManager): OK")

# 5. WindowManager 可构造
wm = panel.main.WindowManager()
assert wm.strip.isVisible(), "Strip must be visible after WindowManager()"
assert wm.panel.isHidden(), "Panel must be hidden after WindowManager()"
assert wm._sse is not None
print("[4/4] WindowManager constructed: OK")
print("     strip:    visible =", wm.strip.isVisible())
print("     panel:    hidden  =", wm.panel.isHidden())
print("     _sse:     exists")

# 6. 5 种信号 / 7 receivers（v3.1：去掉 hotzone，strip.show_requested 改为 toggle）
print()
print("[bonus] signal connection counts:")
checks = [
    ("strip.show_requested",     wm.strip,    wm.strip.show_requested,     1),
    ("panel.collapse_requested", wm.panel,    wm.panel.collapse_requested, 1),
    ("sse.connected",            wm._sse,     wm._sse.connected,           2),
    ("sse.disconnected",         wm._sse,     wm._sse.disconnected,        2),
    ("sse.sse_event",            wm._sse,     wm._sse.sse_event,           1),
]
all_ok = True
for name, recv, sig, expected in checks:
    actual = recv.receivers(sig)
    status = "OK" if actual == expected else "FAIL"
    if actual != expected:
        all_ok = False
    print(f"  [{status}] {name:30s} = {actual} (expected {expected})")

if not all_ok:
    print("\n✗ Some signal connections missing — review WindowManager wiring")
    sys.exit(1)

print("\n✓ All smoke checks passed. Run real-machine manual checklist on DISPLAY=:0.")
