"""panel/sse_client.py 单元测试：SSEClient 的 buffer/reconnect/start 路径。

Panel 相关测试已迁到 tests/test_panel_window.py（v3 拆分）。
"""
import pytest
from PyQt5 import QtCore, QtGui, QtNetwork

from panel.config import (
    OPENCLAW_CHAT_URL,
    OPENCLAW_MODEL,
    OPENCLAW_SESSION_KEY,
    OPENCLAW_URL,
)
from panel.sse_client import SSEClient


# ---- SSEClient ----


def _make_sse_client(url="http://test/events"):
    """跳过 QNetworkAccessManager 构造，但调 QObject.__init__ 让 pyqtSignal 工作。"""
    c = SSEClient.__new__(SSEClient)
    QtCore.QObject.__init__(c)
    c.url = url
    c.buffer = bytearray()
    c.nam = _FakeNam()
    c.reply = None
    c._frame_count = 0
    c._reconnect_timer = QtCore.QTimer()
    c._reconnect_timer.setSingleShot(True)
    return c


class _FakeSignal:
    """模拟 pyqtSignal 的 connect/emit 接口。"""
    def __init__(self):
        self._callbacks = []

    def connect(self, cb):
        self._callbacks.append(cb)

    def emit(self, *args, **kwargs):
        for cb in self._callbacks:
            cb(*args, **kwargs)


class _FakeReply:
    def __init__(self, data=b"", error=0, status=None, body=b""):
        self._data = data
        self._error = error
        self._status = status
        self._body = body
        self.deleted = False
        self.readyRead = _FakeSignal()
        self.finished = _FakeSignal()

    def readAll(self):
        return self._data

    def error(self):
        return self._error

    def attribute(self, _attr):
        return self._status

    def deleteLater(self):
        self.deleted = True


class _FakeRequest:
    """记录 setHeader / setRawHeader 调用的 QNetworkRequest 替身。"""
    class ContentTypeHeader:
        pass

    def __init__(self, url=None):
        self._headers = {}
        self._raw_headers = {}
        self._url = url

    def url(self):
        from PyQt5.QtCore import QUrl
        return self._url or QUrl()

    def setHeader(self, key, value):
        self._headers[key] = value

    def header(self, key):
        return self._headers.get(key, "")

    def setRawHeader(self, key, value):
        self._raw_headers[key] = value

    def rawHeader(self, key):
        return self._raw_headers.get(key, b"")


class _FakeNam:
    """替身 QNetworkAccessManager.get，返一个 _FakeReply。"""
    def __init__(self, reply=None):
        self._reply = reply or _FakeReply()
        self.last_req = None
        # 预构造一个 _FakeRequest 让 nam.get 可以用
        self._stub_req = _FakeRequest()

    def get(self, req):
        # req 是真的 QNetworkRequest，只读其 rawHeader
        self.last_req = req
        return self._reply


def test_sse_client_on_ready_read_no_reply(qapp):
    """reply is None → 早返回。"""
    c = _make_sse_client()
    c.reply = None
    # 不应抛
    c._on_ready_read()
    assert c.buffer == bytearray()


def test_sse_client_on_ready_read_dispatches_full_frames(qapp):
    """完整帧被切出 dispatch，残留不完整数据留在 buffer。"""
    c = _make_sse_client()
    emitted = []
    c.sse_event.connect(lambda n, d: emitted.append((n, d)))
    full = b"event: hello\ndata: {\"k\":1}\n\n"
    half = full[: len(full) // 2]
    c.reply = _FakeReply(data=half)
    c._on_ready_read()
    # 还没 \n\n，buffer 有内容但没 emit
    assert emitted == []
    assert len(c.buffer) > 0

    c.reply = _FakeReply(data=full[len(full) // 2 :])
    c._on_ready_read()
    assert emitted == [("hello", {"k": 1})]
    assert c.buffer == bytearray()


def test_sse_client_on_ready_read_multiple_frames_in_one_chunk(qapp):
    """一次 readAll 拿到多帧都被处理。"""
    c = _make_sse_client()
    emitted = []
    c.sse_event.connect(lambda n, d: emitted.append((n, d)))
    f1 = b"data: {\"a\":1}\n\n"
    f2 = b"event: bye\ndata: {\"b\":2}\n\n"
    c.reply = _FakeReply(data=f1 + f2)
    c._on_ready_read()
    assert ("message", {"a": 1}) in emitted
    assert ("bye", {"b": 2}) in emitted


def test_sse_client_on_finished_clears_and_schedules_reconnect(qapp):
    """finish 时 deleteLater reply + 清 buffer + 启动 reconnect timer。"""
    c = _make_sse_client()
    reply = _FakeReply()
    c.reply = reply
    c.buffer.extend(b"residue")
    disconnected = []
    c.disconnected.connect(lambda: disconnected.append(True))
    c._on_finished()
    assert reply.deleted
    assert c.reply is None
    assert c.buffer == bytearray()
    assert disconnected == [True]
    # reconnect timer 启动
    assert c._reconnect_timer.isActive()


def test_sse_client_on_finished_no_reply(qapp):
    """reply 已为 None（重复 finish）也安全。"""
    c = _make_sse_client()
    c.reply = None
    c._on_finished()
    assert c.reply is None


def test_sse_client_start_emits_connected_and_uses_nam(qapp):
    """start 创建请求、发 connected。"""
    c = _make_sse_client()
    nam = _FakeNam()
    c.nam = nam
    connected = []
    c.connected.connect(lambda: connected.append(True))
    c.start()
    assert connected == [True]
    # nam.get 被调用，request 有 Accept / Cache-Control 头
    assert nam.last_req is not None
    assert b"text/event-stream" in nam.last_req.rawHeader(b"Accept")
    assert b"no-cache" in nam.last_req.rawHeader(b"Cache-Control")
    # reply 信号已连接
    assert c.reply is nam._reply
