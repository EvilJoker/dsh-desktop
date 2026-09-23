"""panel/base_chat_card.py — chat 类卡片基类：UI 装配 + 网络生命周期。"""
import json
import logging
import re

from PyQt5 import QtCore, QtGui, QtNetwork, QtWidgets

log = logging.getLogger(__name__)

# 多个连续换行合并成单个，避免段间空行让面板看着很疏
_MULTI_NL = re.compile(r"\n{2,}")


class BaseChatCard(QtWidgets.QFrame):
    """chat 类卡片基类。

    子类必须实现：
      _build_request_body(text) -> dict
      _parse_sse_frame(data) -> str | None         # None = 跳过
      _auth_headers() -> [(bytes, bytes), ...]     # raw header 名值对列表

    子类可重写：
      _title_text() -> str
      _input_placeholder() -> str
      _format_error(err, status, body_bytes) -> str
      _build_button_row() -> [QPushButton, ...]    # 默认只放"新对话"按钮
      _reset_session()                              # "新对话"时子类 hook

    注意：避免使用 PEP 585 注解（list[T] / tuple[T]），
    生产 PyInstaller 打包用 Python 3.6。
    """

    LINE_PX = 18

    # 消息气泡样式（v3.2 改为走全局 QSS，QLabel objectName 区分）
    # 留常量是为了子类在 add_message / error 路径上还能用 setObjectName 引用
    BUBBLE_USER = "BubbleUser"
    BUBBLE_ASSISTANT = "BubbleAssistant"
    BUBBLE_ERROR = "BubbleError"

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self._url = url

        # 状态
        self._nam = QtNetwork.QNetworkAccessManager(self)
        self._reply = None
        self._sse_buf = bytearray()
        self._frame_count = 0  # 当前会话已收到的 SSE 帧数，_on_send 时清零
        self._last_biz_error = None
        self._safety_blocked = False
        # 流式追加目标
        self._current_label = None
        self._current_text = ""

        self.setObjectName("ChatCard")
        # 样式走 theme.GLOBAL_QSS（#ChatCard 选择器），不再 setStyleSheet

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 10)
        outer.setSpacing(6)

        title = QtWidgets.QLabel(self._title_text())
        title.setObjectName("CardTitle")
        outer.addWidget(title)

        # 对话历史（每条消息一个 QLabel，垂直堆叠在 scroll area 内）
        self._reply_scroll = QtWidgets.QScrollArea()
        self._reply_scroll.setObjectName("ChatScroll")
        self._reply_scroll.setWidgetResizable(True)
        self._reply_scroll.setMinimumHeight(self.LINE_PX * 10 + 8)
        self._reply_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._reply_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        # viewport 同样不画自己的背景（理由同 _history_container）。
        self._reply_scroll.viewport().setAutoFillBackground(False)

        self._history_container = QtWidgets.QWidget()
        self._history_layout = QtWidgets.QVBoxLayout(self._history_container)
        self._history_layout.setContentsMargins(4, 4, 4, 4)
        self._history_layout.setSpacing(6)
        self._history_layout.setAlignment(QtCore.Qt.AlignTop)
        self._reply_scroll.setWidget(self._history_container)
        # 不画自己的背景——让 card 的 rgba(255,255,255,15) 半透 + panel 的深色
        # 半透背景都透出来。注意：QScrollArea.setWidget() 内部会强制把子 widget
        # 的 autoFillBackground 改成 True（Qt 默认行为，确保 scroll 内容能填背景），
        # 所以必须在 setWidget 之后调一次，否则就是白底。
        self._history_container.setAutoFillBackground(False)
        outer.addWidget(self._reply_scroll, 1)

        # 输入行
        input_row = QtWidgets.QHBoxLayout()
        input_row.setSpacing(6)
        input_row.setContentsMargins(0, 0, 0, 0)

        self._input = QtWidgets.QLineEdit()
        self._input.setObjectName("ChatInput")
        self._input.setPlaceholderText(self._input_placeholder())
        self._input.setEnabled(False)
        self._input.returnPressed.connect(self._on_send)
        self._input.installEventFilter(self)
        input_row.addWidget(self._input, 1)

        for btn in self._build_button_row():
            input_row.addWidget(btn)

        outer.addLayout(input_row)

    # ----- 子类必须实现的虚方法 -----

    def _build_request_body(self, text):
        raise NotImplementedError

    def _parse_sse_frame(self, data):
        raise NotImplementedError

    def _auth_headers(self):
        raise NotImplementedError

    # ----- 子类可重写的 hook -----

    def _title_text(self):
        return "对话 / CHAT"

    def _input_placeholder(self):
        return "发送消息（Enter 发送）…"

    def _format_error(self, err, status, body):
        if status:
            return "✕ error: status=%s" % status
        return "✕ error"

    def _build_button_row(self):
        """默认只放一个'新会话'按钮（v3.2 走全局 QSS，objectName=GlassBtn）。"""
        btn = QtWidgets.QPushButton("➕")
        btn.setObjectName("GlassBtn")
        btn.setFixedSize(34, 30)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        btn.setToolTip("新会话（重置 session）")
        btn.clicked.connect(self._on_new_conversation)
        return [btn]

    def _reset_session(self):
        pass

    # ----- IME 诊断：focus / key 时打印 XIM 状态 -----

    def eventFilter(self, watched, event):
        if watched is not self._input:
            return super().eventFilter(watched, event)
        et = event.type()
        if et == QtCore.QEvent.FocusIn:
            im = QtGui.QGuiApplication.inputMethod()
            log.info(
                "IME diag: _input FocusIn im.visible=%s imEnabled=%s focusWidget=%s",
                im.isVisible(),
                self._input.inputMethodQuery(QtCore.Qt.ImEnabled),
                type(QtWidgets.QApplication.focusWidget()).__name__,
            )
        elif et == QtCore.QEvent.FocusOut:
            im = QtGui.QGuiApplication.inputMethod()
            log.info(
                "IME diag: _input FocusOut im.visible=%s",
                im.isVisible(),
            )
        elif et == QtCore.QEvent.KeyPress:
            k = event.key()
            txt = event.text()
            log.info(
                "IME diag: _input KeyPress key=0x%x text=%r modifiers=0x%x "
                "im.cursorVisible=%s",
                int(k), txt, int(event.modifiers()),
                int(self._input.inputMethodQuery(QtCore.Qt.ImCursorPosition)),
            )
        elif et == QtCore.QEvent.InputMethod:
            commit = getattr(event, "commitString", lambda: None)()
            preedit = getattr(event, "preeditString", lambda: None)()
            log.info(
                "IME diag: _input InputMethod commit=%r preedit=%r",
                commit, preedit,
            )
        return super().eventFilter(watched, event)

    # ----- 生命周期 -----

    def _on_send(self):
        text = self._input.text().strip()
        if not text:
            return

        # 流式回答期间 Enter 不触发任何操作（不 abort、不创建新请求、不清输入框）。
        # 原因：abort 旧 reply + self._nam.post() 之间存在 Qt 5 race
        # （manager 可能同步 delete 旧 reply C++ 对象 → _on_done 闭包 handler
        # 在已 free 对象上调 deleteLater → segfault）。保守起见直接禁用。
        if self._reply is not None:
            return

        self._sse_buf.clear()
        self._current_label = None
        self._current_text = ""
        self._frame_count = 0
        self._last_biz_error = None
        self._safety_blocked = False
        # 立即显示用户消息 + 助手占位
        self._add_message("user", text)
        self._current_label = self._add_message("assistant", "…")

        body = self._build_request_body(text)
        if body is None:
            return

        req = QtNetwork.QNetworkRequest(QtCore.QUrl(self._url))
        req.setHeader(
            QtNetwork.QNetworkRequest.ContentTypeHeader,
            "application/json",
        )
        req.setRawHeader(b"Accept", b"text/event-stream")
        for name, value in self._auth_headers():
            req.setRawHeader(name, value)

        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        reply = self._nam.post(req, encoded)
        # 用闭包绑定 reply 实例：旧的 finished/readyRead 信号到达时（如 abort 后），
        # handler 能识别这是过期信号并直接 return，不会误删新 reply。
        reply.readyRead.connect(self._make_on_data(reply))
        reply.finished.connect(self._make_on_done(reply))
        self._reply = reply
        self._input.clear()
        log.info("chat send: text_len=%d url=%s", len(text), self._url)

    def _make_on_data(self, reply):
        def handler():
            self._on_data(reply)
        return handler

    def _make_on_done(self, reply):
        def handler():
            self._on_done(reply)
        return handler

    def _on_data(self, reply):
        if reply is None or reply is not self._reply:
            return
        self._sse_buf.extend(bytes(reply.readAll()))
        while True:
            idx = self._sse_buf.find(b"\n\n")
            if idx < 0:
                break
            frame = bytes(self._sse_buf[:idx])
            del self._sse_buf[: idx + 2]
            for raw in frame.split(b"\n"):
                if not raw.startswith(b"data:"):
                    continue
                data = raw[5:].lstrip().decode("utf-8", errors="replace")
                if not data or data == "[DONE]":
                    continue
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                delta = self._parse_sse_frame(obj)
                if delta:
                    self._current_text += delta
                    if self._current_label is not None:
                        self._current_label.setText(self._current_text)
                    QtCore.QTimer.singleShot(0, self._scroll_to_bottom)
                self._frame_count += 1

    def _scroll_to_bottom(self):
        sb = self._reply_scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ----- 对话列表 -----

    def _add_message(self, role, text):
        """加一条消息到 history：user 右对齐，assistant 左对齐。v3.2 样式走全局 QSS。"""
        label = QtWidgets.QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        # 让 label 撑满 scroll area 宽度，避免消息靠左上角显示
        label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        label.setMinimumWidth(0)
        if role == "user":
            label.setObjectName(self.BUBBLE_USER)
            label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
        else:  # assistant
            label.setObjectName(self.BUBBLE_ASSISTANT)
            label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self._history_layout.addWidget(label)
        QtCore.QTimer.singleShot(0, self._scroll_to_bottom)
        return label

    def _clear_history(self):
        """清空所有消息（'新会话'用）。"""
        while self._history_layout.count():
            item = self._history_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _on_done(self, reply):
        # 过期信号（旧 reply 被 abort 后，Qt 仍会 emit finished）：忽略
        if reply is None or reply is not self._reply:
            try:
                reply.deleteLater()
            except RuntimeError:
                pass
            return
        err = reply.error()
        if err != QtNetwork.QNetworkReply.NoError:
            status = reply.attribute(
                QtNetwork.QNetworkRequest.HttpStatusCodeAttribute
            )
            body = bytes(reply.readAll())[:200]
            log.warning(
                "chat failed: err=%s status=%s body=%r frames=%d",
                err, status, body, self._frame_count,
            )
            # 错误显示在当前 assistant label 里（替换占位）。v3.2 改 objectName。
            if self._current_label is not None:
                self._current_label.setObjectName(self.BUBBLE_ERROR)
                # 触发 QSS 重新解析（Qt 不会在 objectName 改变时自动重算）
                # 用 unpolish+polish 走 stylesheet 重应用
                self._current_label.style().unpolish(self._current_label)
                self._current_label.style().polish(self._current_label)
                self._current_label.setText(self._format_error(err, status, body))
        else:
            log.info(
                "chat done: frames=%d text_len=%d",
                self._frame_count, len(self._current_text),
            )
        reply.deleteLater()
        self._reply = None
        self._current_label = None
        self._current_text = ""
        self._sse_buf.clear()

    def _on_new_conversation(self):
        # 流式回答期间"新会话"按钮也不触发任何操作（不 abort、不清 history、不重置 session），
        # 同 _on_send 的 race 保护。等流式结束（self._reply 被 _on_done 置 None）后用户再点。
        if self._reply is not None:
            return
        log.info("chat new session: previous frames=%d text_len=%d",
                 self._frame_count, len(self._current_text))
        self._sse_buf.clear()
        self._current_label = None
        self._current_text = ""
        self._frame_count = 0
        self._last_biz_error = None
        self._safety_blocked = False
        self._reset_session()
        self._clear_history()
        self._input.setText("")
        self._input.setFocus()
