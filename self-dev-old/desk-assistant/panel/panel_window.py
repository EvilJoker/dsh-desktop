"""panel/panel_window.py — 桌面助手主面板（960×800）。

架构（v3.1，Edge Dock 简化版）：
  - 构造后默认隐藏，由 WindowManager 在收到 Strip.show_requested 时
    调 show_animated() 唤起（去掉 HotZoneWatcher，不再有"贴右自动展开"）
  - 窗口标志：FramelessWindowHint | WindowStaysOnTopHint（不挂 Tool：
    dde-kwin / KWin 会把 Tool 窗口当 dock/utility 在失焦时自隐，
    导致点外部空白就消失。IME 已被 PyQt5 ABI 重建独立解决）
  - 左侧 › collapse_btn 发 collapse_requested 信号（指向右侧 strip）
  - 右上 ✕ close_btn 仍调 QApplication.quit（保留现状）
  - slide_in：pos 动画 200ms 从右滑入
  - slide_out：pos + windowOpacity 并行动画 200ms（panel 边滑边淡）
  - SSEClient 由 WindowManager 持有并传入，PanelWindow 不持有所有权
"""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt5 import QtCore, QtGui, QtNetwork, QtWidgets  # noqa: E402

from chat_card import ChatCard  # noqa: E402
from config import (  # noqa: E402
    OPENCLAW_CHAT_URL,
    OPENCLAW_MODEL,
    OPENCLAW_SESSION_KEY,
    OPENCLAW_URL,
    load_config,
    load_openclaw_token,
)
from events_card import EventsCard  # noqa: E402
from metrics_card import MetricsCard  # noqa: E402
from sse_client import SERVER_EVENTS_URL, SERVER_METRICS_URL  # noqa: E402
from xiaoou_card import XiaoouCard  # noqa: E402

log = logging.getLogger("panel.window")

# ---- panel 几何 ----
PANEL_WIDTH = 960
PANEL_HEIGHT = 800
EDGE_MARGIN = 0  # 贴右：panel 右边缘对齐到主屏右边界，无缝隙
SLIDE_DURATION_MS = 200
SLIDE_EASING = QtCore.QEasingCurve.OutCubic
REFRESH_DEBOUNCE_MS = 150

# ---- 背景图（用户配置；不存在则保持 v3.2 半透现状）----
BG_PATH = Path.home() / ".desk-assistant" / "bg.png"

# ---- chat 协议配置（从 panel.config 派生）----
XIAOOU_CFG = load_config().get("xiaoou")


class PanelWindow(QtWidgets.QWidget):
    """主面板：壳子 + 4 张卡片 + 关闭按钮 + 收起按钮 + 滑入/滑出动画。"""

    # WindowManager 连这个信号：Panel.collapse → WindowManager.hide panel
    collapse_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DeskAssistantPanel")
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            # 不要 Qt.Tool：dde-kwin / KWin 会把 Tool 窗口当 dock/utility
            # 在失焦时主动 unmap（自隐），点 panel 外空白就消失。
            # IME 问题已通过 PyQt5 ABI 重建（3782758）独立解决，
            # 不需要 Tool 走内部 focus 代理路径。
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.resize(PANEL_WIDTH, PANEL_HEIGHT)
        self._positioned = False
        self._drag_offset = None
        self._anim = None
        self._http_nam = QtNetwork.QNetworkAccessManager(self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # 标题行（标题 + 快捷键提示 + SSE 连接状态）。右侧留 30px 给浮动关闭按钮。
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)
        header.setContentsMargins(0, 0, 30, 0)
        self.title = QtWidgets.QLabel("桌面助手 · 等待连接…")
        self.title.setObjectName("HeaderTitle")
        header.addWidget(self.title, 1)
        # 快捷键提示徽章：暗示用户有 Alt+M 可用
        self.shortcut_hint = QtWidgets.QLabel("⌥ M")
        self.shortcut_hint.setObjectName("ShortcutHint")
        self.shortcut_hint.setToolTip("全局快捷键（焦点在哪都能触发）")
        header.addWidget(self.shortcut_hint)
        self.status = QtWidgets.QLabel("● disconnected")
        self.status.setObjectName("StatusLabel")
        self.status.setProperty("connected", "false")
        header.addWidget(self.status)
        layout.addLayout(header)

        # 4 张卡片
        self.metrics_card = MetricsCard()
        self.events_card = EventsCard()
        self.events_card.toggle_requested.connect(self._on_event_toggle)
        self.chat_card = ChatCard(
            openclaw_url=OPENCLAW_URL,
            model=OPENCLAW_MODEL,
            session_key=OPENCLAW_SESSION_KEY,
            chat_url=OPENCLAW_CHAT_URL,
        )
        self.chat_card.set_token(None)
        # openclaw token 异步加载：构造时同步读 ~/.openclaw/openclaw.json 会
        # 卡 UI 启动；丢到下一轮事件循环让首帧先出来
        QtCore.QTimer.singleShot(0, self._load_openclaw_token_async)

        self.xiaoou_card = None
        if XIAOOU_CFG:
            self.xiaoou_card = XiaoouCard(
                base_url=XIAOOU_CFG["base_url"],
                model=XIAOOU_CFG["model"],
                topic_id=XIAOOU_CFG["topic_id"],
                source=XIAOOU_CFG["source"],
                auth_header=(
                    XIAOOU_CFG["auth"]["header"].encode("utf-8"),
                    XIAOOU_CFG["auth"]["value"].encode("utf-8"),
                ),
            )

        # cards 顺序与 tab 顺序保持一致（v3.2）：
        #   无小欧：[chat, metrics, events] → tab 0=对话 / 1=指标 / 2=事件
        #   有小欧：[chat, xiaoou, metrics, events] → tab 0=对话 / 1=小欧 / 2=指标 / 3=事件
        # 这样 tab i 与 stack i 一一对应，_set_tab 不用做映射
        if self.xiaoou_card is not None:
            cards = [self.chat_card, self.xiaoou_card, self.metrics_card, self.events_card]
        else:
            cards = [self.chat_card, self.metrics_card, self.events_card]
        for card in cards:
            card.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding,
            )

        self._stack = QtWidgets.QStackedWidget()
        for card in cards:
            self._stack.addWidget(card)
        layout.addWidget(self._stack, 1)

        # tab 栏（底部，玻璃药丸风）
        # 顺序：对话 / 小欧 / 指标 / 事件（核心功能前置，2026-07-23 样式改造定稿）
        self._tab_group = QtWidgets.QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self._tab_group.buttonClicked[int].connect(self._set_tab)
        self._tabs = []
        tab_bar = QtWidgets.QHBoxLayout()
        tab_bar.setContentsMargins(0, 0, 0, 0)
        tab_bar.setSpacing(6)
        # v3.2：标签顺序改为"对话/小欧/指标/事件"，去掉"资讯"
        tab_labels = ["对话", "小欧", "指标", "事件"]
        # 兼容旧配置：如果 xiaoou 未启用，剔除"小欧"
        if self.xiaoou_card is None:
            tab_labels = [l for l in tab_labels if l != "小欧"]
        for i, label in enumerate(tab_labels):
            btn = QtWidgets.QPushButton(label)
            btn.setObjectName("TabBtn")
            btn.setCheckable(True)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            self._tab_group.addButton(btn, i)
            self._tabs.append(btn)
            tab_bar.addWidget(btn, 1)
        layout.addLayout(tab_bar)

        # 右上角关闭按钮（✕ 退出整个 app，v3.2 幽灵按钮 + hover 显红）
        self.close_btn = QtWidgets.QPushButton("✕", self)
        self.close_btn.setObjectName("CloseBtn")
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_btn.setToolTip("关闭看板（后台服务继续运行）")
        self.close_btn.clicked.connect(QtWidgets.QApplication.quit)
        self.close_btn.raise_()

        # 左侧 › 收起按钮（v3.2 幽灵按钮）
        self.collapse_btn = QtWidgets.QPushButton("›", self)
        self.collapse_btn.setObjectName("CollapseBtn")
        self.collapse_btn.setFixedSize(24, 32)
        self.collapse_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.collapse_btn.setToolTip("收起面板（保留后台）")
        self.collapse_btn.clicked.connect(self._on_collapse_clicked)
        self.collapse_btn.raise_()

        # SSE → REST debounce timers
        self._refresh_metrics_timer = QtCore.QTimer(self)
        self._refresh_metrics_timer.setSingleShot(True)
        self._refresh_metrics_timer.setInterval(REFRESH_DEBOUNCE_MS)
        self._refresh_metrics_timer.timeout.connect(self._refresh_metrics)
        self._refresh_events_timer = QtCore.QTimer(self)
        self._refresh_events_timer.setSingleShot(True)
        self._refresh_events_timer.setInterval(REFRESH_DEBOUNCE_MS)
        self._refresh_events_timer.timeout.connect(self._refresh_events)

        # v3.2：默认显示 tab 0 = 对话（取代 v3.1 的默认事件）
        self._current_tab_index = 0
        self._tabs[0].setChecked(True)
        self._stack.setCurrentIndex(0)

        QtWidgets.QApplication.instance().installEventFilter(self)

        # v3.3 背景图：读 ~/.desk-assistant/bg.png，找不到保持半透现状
        self._bg_pixmap = self._load_bg_pixmap()
        # v3.3 背景图热重载：QFileSystemWatcher 监听 bg.png 变更（覆盖/删除/重建）
        # 注意：文件被替换（inode 变化）或删除时 watcher 会失效，slot 里要重新 addPath
        self._bg_watcher = QtCore.QFileSystemWatcher(self)
        if BG_PATH.exists():
            self._bg_watcher.addPath(str(BG_PATH))
        self._bg_watcher.fileChanged.connect(self._on_bg_changed)

        # v3：默认隐藏，等 WindowManager 调 show_animated()
        self.hide()
        log.info("panel constructed: %dx%d, hidden by default", PANEL_WIDTH, PANEL_HEIGHT)

    # ----- tab 切换（从 main.py 搬过来，零改动）-----

    def _set_tab(self, i):
        if not 0 <= i < self._stack.count():
            return
        if i == self._current_tab_index:
            return
        self._current_tab_index = i
        self._stack.setCurrentIndex(i)
        self._tabs[i].setChecked(True)

    def _set_tab_if_not_input(self, i):
        focus = QtWidgets.QApplication.focusWidget()
        if isinstance(focus, QtWidgets.QLineEdit):
            return
        self._set_tab(i)

    def eventFilter(self, watched, event):
        # 诊断：把截到的所有事件打日志，看输入框 key 事件有没有被 panel 吞掉
        if event.type() == QtCore.QEvent.KeyPress:
            focus = QtWidgets.QApplication.focusWidget()
            log.info(
                "eventFilter: KeyPress watched=%s type=%s text=%r key=0x%x "
                "modifiers=0x%x focusWidget=%s",
                type(watched).__name__, int(event.type()),
                event.text(), int(event.key()),
                int(event.modifiers()),
                type(focus).__name__ if focus else None,
            )
            if event.modifiers() & QtCore.Qt.ControlModifier:
                if not isinstance(focus, QtWidgets.QLineEdit):
                    key = event.key()
                    if key == QtCore.Qt.Key_1:
                        self._set_tab(0)
                        return True
                    if key == QtCore.Qt.Key_2:
                        self._set_tab(1)
                        return True
                    if key == QtCore.Qt.Key_3:
                        self._set_tab(2)
                        return True
                    if key == QtCore.Qt.Key_4:
                        self._set_tab(3)
                        return True
        return super().eventFilter(watched, event)

    # ----- collapse -----

    def _on_collapse_clicked(self):
        self.collapse_requested.emit()

    # ----- openclaw token 异步加载 -----

    def _load_openclaw_token_async(self):
        """下一轮事件循环再读 ~/.openclaw/openclaw.json，避免卡 UI 启动。"""
        token = load_openclaw_token()
        if token is not None:
            self.chat_card.set_token(token)

    # ----- 滑入/滑出动画 -----

    def _cancel_anim_if_running(self):
        if self._anim is not None and self._anim.state() == QtCore.QAbstractAnimation.Running:
            self._anim.stop()
            try:
                self._anim.finished.disconnect(self._on_slide_out_finished)
            except (TypeError, RuntimeError):
                pass
            # slide_out 中途被取消时，opacity 可能停在中间值，恢复到 1.0
            # 避免下次 slide_in 一开始就半透明
            self.setWindowOpacity(1.0)

    def _slide_in(self):
        self._cancel_anim_if_running()
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        if screen.width() <= 0 or screen.height() <= 0:
            log.warning("primary screen invalid, skip slide in")
            return
        final_x = screen.x() + screen.width() - self.width() - EDGE_MARGIN
        final_y = screen.y() + (screen.height() - self.height()) // 2
        off_screen_x = screen.x() + screen.width() + 1

        self.move(off_screen_x, final_y)
        self.show()
        self.raise_()
        self.activateWindow()

        log.info("slide_in start: final_pos=(%d,%d) duration=%dms",
                 final_x, final_y, SLIDE_DURATION_MS)

        self._anim = QtCore.QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(SLIDE_DURATION_MS)
        self._anim.setEasingCurve(SLIDE_EASING)
        self._anim.setStartValue(QtCore.QPoint(off_screen_x, final_y))
        self._anim.setEndValue(QtCore.QPoint(final_x, final_y))
        self._anim.start()

    def _on_slide_out_finished(self):
        # 恢复 opacity 防止下次 slide_in 时还残留 0
        self.setWindowOpacity(1.0)
        self.hide()
        log.info("slide_out finished: panel hidden")

    def _slide_out(self):
        self._cancel_anim_if_running()
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        if screen.width() <= 0 or screen.height() <= 0:
            log.warning("primary screen invalid, skip slide out")
            self.setWindowOpacity(1.0)
            self.hide()
            return
        current = self.pos()
        off_screen_x = screen.x() + screen.width() + 1
        log.info("slide_out start: from=(%d,%d) to=(%d,%d) duration=%dms",
                 current.x(), current.y(), off_screen_x, current.y(), SLIDE_DURATION_MS)

        # 位置动画：panel 向右滑出主屏（和 slide_in 对称）
        pos_anim = QtCore.QPropertyAnimation(self, b"pos", self)
        pos_anim.setDuration(SLIDE_DURATION_MS)
        pos_anim.setEasingCurve(SLIDE_EASING)
        pos_anim.setStartValue(current)
        pos_anim.setEndValue(QtCore.QPoint(off_screen_x, current.y()))

        # 透明度动画：1.0 → 0.0 线性淡出
        # 上一次用 setMask 裁到主屏但被 compositor 忽略（WA_TranslucentBackground 下
        # mask 失效），所以这里改用并行淡出：等 panel 越过主屏右边界进入第二屏时，
        # 它已经基本不可见，残影轻微。
        opacity_anim = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        opacity_anim.setDuration(SLIDE_DURATION_MS)
        opacity_anim.setEasingCurve(QtCore.QEasingCurve.Linear)
        opacity_anim.setStartValue(1.0)
        opacity_anim.setEndValue(0.0)

        self._anim = QtCore.QParallelAnimationGroup(self)
        self._anim.addAnimation(pos_anim)
        self._anim.addAnimation(opacity_anim)
        self._anim.finished.connect(self._on_slide_out_finished)
        self._anim.start()

    def show_animated(self):
        """WindowManager 调用：强制刷新一次 + 滑入。"""
        log.info("show_animated: force refresh metrics+events + slide_in")
        self._refresh_metrics()
        self._refresh_events()
        self._slide_in()

    # ----- SSE 事件派发 -----

    def on_sse_event(self, name, data):
        if name == "hello":
            self._refresh_metrics_timer.stop()
            self._refresh_events_timer.stop()
            self._refresh_metrics()
            self._refresh_events()
        elif name == "metrics.changed":
            self._refresh_metrics_timer.start()
        elif name == "events.changed":
            self._refresh_events_timer.start()

    def _refresh_metrics(self):
        req = QtNetwork.QNetworkRequest(QtCore.QUrl(SERVER_METRICS_URL))
        reply = self._http_nam.get(req)
        reply.finished.connect(lambda r=reply: self._on_metrics_reply(r))

    def _on_metrics_reply(self, reply):
        try:
            if reply.error() == QtNetwork.QNetworkReply.NoError:
                body = bytes(reply.readAll()).decode("utf-8", errors="replace")
                data = json.loads(body) if body else []
                if isinstance(data, list):
                    self.metrics_card.update_indicators(data)
                    # v3.2：时间戳改成 HH:MM 紧凑格式（之前 ISO 太长，标题挤）
                    now = datetime.now().strftime("%H:%M")
                    self.title.setText("桌面助手 · " + now)
                log.info("GET /api/metrics ok: items=%d", len(data) if isinstance(data, list) else -1)
            else:
                log.warning("GET /api/metrics failed: err=%s", reply.error())
                self.status.setText("✕ metrics error")
                self.status.setProperty("connected", "false")
        finally:
            reply.deleteLater()

    def _refresh_events(self):
        req = QtNetwork.QNetworkRequest(QtCore.QUrl(SERVER_EVENTS_URL))
        reply = self._http_nam.get(req)
        reply.finished.connect(lambda r=reply: self._on_events_reply(r))

    def _on_events_reply(self, reply):
        try:
            if reply.error() == QtNetwork.QNetworkReply.NoError:
                body = bytes(reply.readAll()).decode("utf-8", errors="replace")
                data = json.loads(body) if body else []
                if isinstance(data, list):
                    self.events_card.update_events(data)
                log.info("GET /api/events ok: items=%d", len(data) if isinstance(data, list) else -1)
            else:
                log.warning("GET /api/events failed: err=%s", reply.error())
                self.status.setText("✕ events error")
                self.status.setProperty("connected", "false")
        finally:
            reply.deleteLater()

    def on_connected(self):
        self.status.setText("● connected")
        self.status.setProperty("connected", "true")
        log.info("SSE connected: status text updated to '● connected'")

    def on_disconnected(self):
        self.status.setText("○ reconnecting in 5s…")
        self.status.setProperty("connected", "false")
        log.info("SSE disconnected: status text updated to '○ reconnecting in 5s…'")

    # ----- 事件勾选回写 -----

    def _on_event_toggle(self, event_id, checked):
        url = "%s/%d" % (SERVER_EVENTS_URL, int(event_id))
        body = json.dumps({"done": bool(checked)}).encode("utf-8")
        req = QtNetwork.QNetworkRequest(QtCore.QUrl(url))
        req.setHeader(
            QtNetwork.QNetworkRequest.ContentTypeHeader,
            "application/json",
        )
        reply = self._http_nam.sendCustomRequest(req, b"PATCH", body)
        reply.finished.connect(lambda r=reply, eid=event_id: self._on_patch_reply(r, eid))
        log.info("PATCH /api/events/%d done=%s sent", int(event_id), bool(checked))

    def _on_patch_reply(self, reply, event_id):
        try:
            err = reply.error()
            if err != QtNetwork.QNetworkReply.NoError:
                status = reply.attribute(
                    QtNetwork.QNetworkRequest.HttpStatusCodeAttribute
                )
                body = bytes(reply.readAll())[:200]
                log.warning(
                    "PATCH /api/events/%s failed: err=%s status=%s body=%r",
                    event_id, err, status, body,
                )
        finally:
            reply.deleteLater()

    # ----- 绘制 / 位置 / 交互 -----

    def paintEvent(self, _event):
        # v3.3 背景图：用户配置 ~/.desk-assistant/bg.png 存在时画图（中心对齐 + 暗色蒙层）；
        # 不存在时保持 v3.2 半透（深灰底，圆角矩形）。
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        if self._bg_pixmap is None:
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(QtGui.QColor(20, 20, 28, 160))
            p.drawRoundedRect(self.rect(), 12, 12)
            return
        # 有背景图：缩放（KeepAspectRatioByExpanding）+ 中心对齐 + 暗色蒙层
        pix = self._bg_pixmap
        pw, ph = self.width(), self.height()
        iw, ih = pix.width(), pix.height()
        # 按 panel 比例等比缩放（短边对齐 → 长边超出）
        if iw * ph > ih * pw:
            # 图更宽：以 panel 高度为基准，宽度超出
            scaled_h = ph
            scaled_w = int(iw * (ph / ih))
        else:
            # 图更窄：以 panel 宽度为基准
            scaled_w = pw
            scaled_h = int(ih * (pw / iw))
        scaled = pix.scaled(
            scaled_w, scaled_h,
            QtCore.Qt.KeepAspectRatioByExpanding,
            QtCore.Qt.SmoothTransformation,
        )
        # 中心对齐
        x = (pw - scaled.width()) // 2
        y = (ph - scaled.height()) // 2
        p.drawPixmap(x, y, scaled)
        # 暗色蒙层（v 形渐变：上下深，中间稍浅，让中部控件更清晰）
        grad = QtGui.QLinearGradient(0, 0, 0, ph)
        grad.setColorAt(0.0, QtGui.QColor(0, 0, 0, 180))
        grad.setColorAt(0.5, QtGui.QColor(0, 0, 0, 140))
        grad.setColorAt(1.0, QtGui.QColor(0, 0, 0, 180))
        p.fillRect(self.rect(), QtGui.QBrush(grad))

    def _load_bg_pixmap(self):
        """读 ~/.desk-assistant/bg.png，找不到/读不到返回 None（保持 v3.2 半透）。"""
        try:
            if not BG_PATH.exists():
                log.info("bg: no user image at %s, keep v3.2 transparent", BG_PATH)
                return None
            pix = QtGui.QPixmap(str(BG_PATH))
            if pix.isNull():
                log.warning("bg: invalid image at %s, keep v3.2 transparent", BG_PATH)
                return None
            log.info("bg: loaded %s (%dx%d)", BG_PATH, pix.width(), pix.height())
            return pix
        except Exception as e:
            log.warning("bg: load failed: %s, keep v3.2 transparent", e)
            return None

    def _on_bg_changed(self, path):
        """bg.png 变更（覆盖/删除/重建）→ 重载 + 触发重绘。
        关键：文件被替换时 inode 变化，QFileSystemWatcher 会丢监听，必须重新 addPath；
        文件被删时同理。先 reload，再判断要不要重新 watch。
        """
        log.info("bg: fileChanged: %s", path)
        self._bg_pixmap = self._load_bg_pixmap()
        # watcher 可能因 inode 变化失效，重新 add（仅当文件还存在时）
        if path not in self._bg_watcher.files() and BG_PATH.exists():
            self._bg_watcher.addPath(path)
            log.info("bg: watcher re-armed on %s", path)
        self.update()  # 触发 paintEvent 重绘

    def _reposition_to_right_edge(self):
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        if screen.width() <= 0 or screen.height() <= 0:
            return
        self.move(
            screen.x() + screen.width() - self.width() - EDGE_MARGIN,
            screen.y() + (screen.height() - self.height()) // 2,
        )
        self._positioned = True
        log.info("panel reposition to right edge: pos=(%d,%d) %dx%d",
                 self.x(), self.y(), self.width(), self.height())

    def showEvent(self, event):
        super().showEvent(event)
        if not self._positioned:
            QtCore.QTimer.singleShot(0, self._reposition_to_right_edge)
            QtCore.QTimer.singleShot(100, self._reposition_to_right_edge)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.close_btn.move(self.width() - self.close_btn.width() - 8, 8)
        # collapse_btn 垂直居中
        self.collapse_btn.move(
            8,
            (self.height() - self.collapse_btn.height()) // 2,
        )

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
        elif event.button() == QtCore.Qt.RightButton:
            QtWidgets.QApplication.quit()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)

    def mouseReleaseEvent(self, _event):
        self._drag_offset = None
