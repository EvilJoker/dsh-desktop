"""panel/window_manager.py — 桌面助手两部件拼装器。

架构（v3 Edge Dock，简化版）：
  - 持有 SSEClient（单例）
  - 创建 Strip + PanelWindow
  - 连接 5 种信号 / 7 个 receivers：
      strip.show_requested    → self._toggle_panel    (1)
      panel.collapse_requested → panel._slide_out     (1)
      sse.connected            → strip + panel        (2)
      sse.disconnected         → strip + panel        (2)
      sse.sse_event            → panel                (1)
  - 监听 QScreen.geometryChanged → strip + panel 重新定位
  - SSEClient.start() 由 WindowManager 触发（所有者）

v3.1：去掉 HotZoneWatcher。展开/折叠完全靠 strip 按钮（toggle）+ panel
› 按钮触发，不再有"鼠标贴右"自动展开。

v3.2：真全局快捷键 Alt+M（通过 Nde addMethodAction，nde-globalkeysd 派发）。
       焦点在浏览器/IDE/编辑器都能触发，等价于点击 strip 图标。
       非 Nde 桌面（如 KDE/GNOME）下 nde-globalkeysd 不存在，
       NdeGlobalShortcut 静默跳过——只能靠 strip 点击。
"""
import logging

from PyQt5 import QtCore, QtWidgets

from panel.global_shortcut import NdeGlobalShortcut
from panel.panel_window import PanelWindow
from panel.sse_client import SSEClient, SSE_URL
from panel.strip import Strip

log = logging.getLogger("panel.manager")


class WindowManager(QtCore.QObject):
    """两部件 + SSEClient 拼装器。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 单例 SSEClient
        self._sse = SSEClient(SSE_URL)
        self._sse_reference = self._sse  # 仅供 test 断言引用相等

        # 两部件
        self.strip = Strip()
        self.panel = PanelWindow()

        # Strip 永远显示；Panel 默认隐藏
        self.strip.show()
        # 注意：不要在这里 processEvents()。Qt 5.12 + xcb + fcitx/搜狗 XIM 下，
        # strip.show() 立即 processEvents 会让 XIM 提前 attach 到不稳定的窗口，
        # 后续用户点 chat 输入框时 XIM 上下文错乱 → 搜狗切英文、中文进不来。
        # 历史上 v3 Edge Dock 上线时 (63e689d) 没有这个 processEvents，IME 正常。

        # 监听屏分辨率变化（用 hasattr 防御 FakeScreen 替身）
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None and hasattr(screen, "geometryChanged"):
            screen.geometryChanged.connect(self._on_screen_changed)

        # 信号连接（5 种 / 7 receivers）
        self.strip.show_requested.connect(self._toggle_panel)
        self.panel.collapse_requested.connect(self.panel._slide_out)
        self._sse.connected.connect(self.strip.on_connected)
        self._sse.connected.connect(self.panel.on_connected)
        self._sse.disconnected.connect(self.strip.on_disconnected)
        self._sse.disconnected.connect(self.panel.on_disconnected)
        self._sse.sse_event.connect(self.panel.on_sse_event)
        log.info("manager: 7 receivers connected, SSE start")

        # 真全局快捷键 Alt+M：nde-globalkeysd 派发到本进程，焦点在哪都能触发
        # 等价于点击 strip 上的图标（_toggle_panel 复用既有逻辑）
        # 非 Nde 桌面 nde 不存在时内部 log warning 跳过，is_registered()=False
        self._global_shortcut = NdeGlobalShortcut(
            shortcut_str="Alt+M",
            bus_name="org.deskassistant.panel",
            object_path="/deskassistant/shortcut",
            description="Toggle desk-assistant panel",
            parent=self,
        )
        if self._global_shortcut.is_registered():
            self._global_shortcut.activated.connect(self._toggle_panel)
            log.info("global shortcut wired: Alt+M → _toggle_panel")
        else:
            log.info("global shortcut unavailable, strip click only")

        # SSE 启动（所有者）
        self._sse.start()

    def _toggle_panel(self):
        """strip 按钮 toggle：panel 隐藏则展开，显示则折叠。
        展开后 raise strip，让它浮在 panel 之上保持可点。"""
        was_visible = self.panel.isVisible()
        log.info("toggle_panel: was_visible=%s", was_visible)
        if was_visible:
            self.panel._slide_out()
        else:
            self.panel.show_animated()
            self.strip.raise_()

    def _on_screen_changed(self, _geo):
        log.info("screen geometry changed: repositioning strip%s",
                 " + panel" if self.panel.isVisible() else "")
        self.strip._reposition_to_right_edge()
        if self.panel.isVisible():
            self.panel._reposition_to_right_edge()