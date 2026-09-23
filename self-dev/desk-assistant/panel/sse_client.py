"""panel/sse_client.py — 最小 SSE 长连接客户端。

发出信号：
  sse_event(name: str, data: dict)  — 收到一帧；name 缺省时为 "message"
  connected()
  disconnected()

5s 断线重连，按 \\n\\n 切帧 + 解析 event/data 字段。

注意信号名不能叫 event，会和 QObject.event(QEvent) 方法冲突
（Qt 内部派发事件时拿到信号对象，触发 "signal is not callable"）。
"""
import json
import logging

from PyQt5 import QtCore, QtNetwork

log = logging.getLogger("panel.sse")

# ---- server 配置 ----
SSE_URL = "http://127.0.0.1:18675/events"
SERVER_BASE = "http://127.0.0.1:18675"
SERVER_METRICS_URL = SERVER_BASE + "/api/metrics"
SERVER_EVENTS_URL = SERVER_BASE + "/api/events"
RECONNECT_DELAY_MS = 5000


class SSEClient(QtCore.QObject):
    sse_event = QtCore.pyqtSignal(str, dict)
    connected = QtCore.pyqtSignal()
    disconnected = QtCore.pyqtSignal()

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url
        self.nam = QtNetwork.QNetworkAccessManager(self)
        self.reply = None
        self.buffer = bytearray()
        self._frame_count = 0  # 当前连接已 dispatch 的帧数，start() 时清零
        self._reconnect_timer = QtCore.QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self.start)

    def start(self):
        req = QtNetwork.QNetworkRequest(QtCore.QUrl(self.url))
        req.setRawHeader(b"Accept", b"text/event-stream")
        req.setRawHeader(b"Cache-Control", b"no-cache")
        self.reply = self.nam.get(req)
        self.reply.readyRead.connect(self._on_ready_read)
        self.reply.finished.connect(self._on_finished)
        self._frame_count = 0
        log.info("SSE connect → %s", self.url)
        self.connected.emit()

    def _on_ready_read(self):
        if self.reply is None:
            return
        self.buffer.extend(bytes(self.reply.readAll()))
        while True:
            idx = self.buffer.find(b"\n\n")
            if idx < 0:
                break
            frame = bytes(self.buffer[:idx])
            del self.buffer[: idx + 2]
            self._dispatch(frame)

    def _dispatch(self, frame):
        event_name = "message"
        data_lines = []
        for raw in frame.split(b"\n"):
            if raw.startswith(b":"):
                continue  # 注释 / 心跳 ": keepalive"
            if raw.startswith(b"event:"):
                event_name = raw[6:].strip().decode("utf-8", errors="replace")
            elif raw.startswith(b"data:"):
                # 兼容 "data: xxx" 和 "data:xxx" 两种
                payload = raw[5:]
                if payload.startswith(b" "):
                    payload = payload[1:]
                data_lines.append(payload.decode("utf-8", errors="replace"))
        if not data_lines:
            return
        try:
            obj = json.loads("\n".join(data_lines))
        except json.JSONDecodeError as e:
            log.warning("[panel] bad SSE frame (json): %s frame=%r", e, frame[:80])
            return
        if not isinstance(obj, dict):
            log.warning("[panel] bad SSE frame (not dict): %r", frame[:80])
            return
        self._frame_count += 1
        # 前 3 帧打 INFO 让初次连接的事件类型一眼可见；之后静默避免刷屏
        if self._frame_count <= 3:
            log.info(
                "SSE frame #%d: event=%s keys=%s",
                self._frame_count, event_name, list(obj.keys())[:5],
            )
        self.sse_event.emit(event_name, obj)

    def _on_finished(self):
        if self.reply is not None:
            self.reply.deleteLater()
            self.reply = None
        self.buffer.clear()
        log.info("SSE disconnect: %d frames, reconnect in %dms",
                 self._frame_count, RECONNECT_DELAY_MS)
        self.disconnected.emit()
        self._reconnect_timer.start(RECONNECT_DELAY_MS)