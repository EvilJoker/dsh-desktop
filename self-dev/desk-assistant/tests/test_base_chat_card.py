"""panel/base_chat_card.py 单元测试：覆盖基类 UI 装配 + 生命周期（mock 子类）。"""
import json

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtNetwork import QNetworkReply

from panel.base_chat_card import BaseChatCard


# ---- mock 子类 ----


class _SignalStub:
    """mock 给 QNetworkReply.signal 用的桩：connect 不报错就行。"""
    def connect(self, *_args, **_kwargs):
        pass


class _MockSubclass(BaseChatCard):
    """把 3 个虚方法都暴露成可观测字段，基类测试只测基类逻辑。"""
    def __init__(self, url="http://test/v1/chat", parent=None):
        self.build_calls = []
        self.parse_calls = []
        super().__init__(url, parent)

    def _build_request_body(self, text):
        self.build_calls.append(text)
        return {"text": text, "_marker": "mock"}

    def _parse_sse_frame(self, data):
        self.parse_calls.append(data)
        return data.get("delta")

    def _auth_headers(self):
        return [(b"X-Test", b"1")]


# ---- UI 装配 ----


def test_init_assembles_widgets(qapp):
    """__init__ 跑完所有 UI 装配：title / input / history_container / 新会话按钮都在。"""
    card = _MockSubclass()
    assert card._input is not None
    assert card._history_container is not None
    assert card._history_layout is not None
    assert card._history_layout.count() == 0
    # 输入行有一个"新会话"按钮
    input_row_children = card._input.parent().children()
    assert any(c.text() == "➕" for c in input_row_children if hasattr(c, "text"))


def test_history_area_is_transparent(qapp):
    """消息历史区必须透明：history_container + scroll viewport 都不能自动填背景。

    否则 card 的 rgba(255,255,255,15) 半透 + panel 的深色背景都看不到，
    视觉上变成一块纯白方框（用户报的"面板颜色不对"就是这个）。
    """
    card = _MockSubclass()
    assert card._history_container.autoFillBackground() is False, (
        "history_container 不应自动填充背景（默认 QWidget 调色板是白色，"
        "会挡住 card 和 panel 的半透背景）"
    )
    assert card._reply_scroll.viewport().autoFillBackground() is False, (
        "QScrollArea.viewport 不应自动填充背景（同上）"
    )


# ---- _on_send 早返回 + 调子类 ----


def test_send_empty_returns(qapp, monkeypatch):
    card = _MockSubclass()
    card._input.setText("   ")
    class _BoomNam:
        def post(self, *a, **k):
            raise AssertionError("should not post")
    monkeypatch.setattr(card, "_nam", _BoomNam())
    card._on_send()
    assert card.build_calls == []


def test_send_during_streaming_is_noop(qapp, monkeypatch):
    """流式回答期间按 Enter：早返回，**不**触发 abort、**不**创建新请求、**不**清输入框。

    关键：避免 abort 旧 reply + post 新 reply 之间的 Qt 5 race
    （manager 可能同步 delete 旧 reply C++ 对象 → _on_done 闭包 handler
    在已 free 对象上调 deleteLater → segfault）。

    见 base_chat_card._on_send 顶部的 `if self._reply is not None: return`。
    """
    card = _MockSubclass()
    in_flight = object()  # 占位，只要 self._reply 非 None
    card._reply = in_flight
    card._input.setText("用户已输入但还没发出去")
    # mock _nam.post 不应被调
    class _BoomNam:
        def post(self, *a, **k):
            raise AssertionError("流式期间不应创建新请求")
    monkeypatch.setattr(card, "_nam", _BoomNam())
    card._on_send()
    assert card.build_calls == [], "_build_request_body 不应被调"
    assert card._input.text() == "用户已输入但还没发出去", "输入框文字应保留"
    assert card._reply is in_flight, "self._reply 仍指向旧 reply（不应被清）"


def test_send_calls_subclass_build_request_body(qapp):
    """_on_send 必须把 text 传给子类的 _build_request_body，body 进 HTTP request。"""
    card = _MockSubclass()
    captured = {}

    class _FakeReq:
        def setHeader(self, *a): pass
        def setRawHeader(self, k, v): captured[k] = v
    class _Reply:
        readyRead = type("Sig", (), {"connect": lambda *a, **k: None})()
        finished = type("Sig", (), {"connect": lambda *a, **k: None})()
    class _Nam:
        def post(self, req, body):
            captured["body"] = body
            return _Reply()
    card._nam = _Nam()
    card._input.setText("hello")
    card._on_send()
    assert card.build_calls == ["hello"]
    assert json.loads(captured["body"].decode()) == {"text": "hello", "_marker": "mock"}


def test_send_attaches_subclass_auth_headers(qapp):
    """_on_send 必须把子类的 _auth_headers() 加到 request 上。"""
    card = _MockSubclass()
    captured = {}
    class _Reply:
        readyRead = type("Sig", (), {"connect": lambda *a, **k: None})()
        finished = type("Sig", (), {"connect": lambda *a, **k: None})()
    class _Nam:
        def post(self, req, body):
            captured["req"] = req
            return _Reply()
    card._nam = _Nam()
    card._input.setText("x")
    card._on_send()
    assert captured["req"].rawHeader(b"X-Test") == b"1"


# ---- _on_data SSE 帧循环 ----


def test_on_data_calls_subclass_parse_sse_frame(qapp):
    """每一帧都过子类 _parse_sse_frame，delta 非空才累加到 _current_text。"""
    card = _MockSubclass()
    class _Reply:
        def readAll(self): return b""
        def error(self): return 0
    payload = json.dumps({"delta": "你好"})
    card._sse_buf.extend(b"data: " + payload.encode() + b"\n\n")
    card._reply = _Reply()
    # 模拟 _on_send 之后创建的占位 label
    card._current_label = card._add_message("assistant", "")
    card._on_data(card._reply)
    assert len(card.parse_calls) == 1
    assert "你好" in card._current_text
    assert "你好" in card._current_label.text()


def test_on_data_subclass_returns_none_skips_frame(qapp):
    """子类返回 None → 跳过该帧，不累加。"""
    card = _MockSubclass()
    card._current_text = "pre"
    class _Reply:
        def readAll(self): return b""
        def error(self): return 0
    payload = json.dumps({"choices": [{"delta": {}}]})  # _parse_sse_frame 返回 None
    card._sse_buf.extend(b"data: " + payload.encode() + b"\n\n")
    card._reply = _Reply()
    card._on_data(card._reply)
    assert card._current_text == "pre"


def test_on_data_accumulates_concatenates(qapp):
    """多帧连续累加：delta 串成完整文本。"""
    card = _MockSubclass()
    class _Reply:
        def readAll(self): return b""
        def error(self): return 0
    card._reply = _Reply()
    card._current_label = card._add_message("assistant", "")
    frame = b""
    for word in ["你", "好", "，", "世界", "！"]:
        frame += b"data: " + json.dumps({"delta": word}).encode() + b"\n\n"
    card._sse_buf.extend(frame)
    card._on_data(card._reply)
    assert card._current_text == "你好，世界！"
    assert card._current_label.text() == "你好，世界！"


def test_on_data_no_reply_early_return(qapp):
    """self._reply is None → 早返回。"""
    card = _MockSubclass()
    card._reply = None
    card._on_data(card._reply)  # 不应抛


# ---- _on_done ----


def test_on_done_no_error_clears_state(qapp):
    card = _MockSubclass()
    class _Reply:
        def error(self): return QNetworkReply.NoError
        def deleteLater(self): pass
    card._reply = _Reply()
    card._on_done(card._reply)
    assert card._reply is None
    assert card._sse_buf == bytearray()


def test_on_done_error_uses_subclass_format_error(qapp):
    """_on_done 错误时必须调子类的 _format_error 显示在当前 assistant label。"""
    card = _MockSubclass()
    class _Reply:
        def error(self): return QNetworkReply.OperationCanceledError
        def attribute(self, _): return 500
        def readAll(self): return b"server err"
        def deleteLater(self): pass
    card._reply = _Reply()
    label = card._add_message("assistant", "…")
    card._current_label = label
    card._on_done(card._reply)
    # 错误显示在占位 label 里（用保留的引用，因为 _on_done 会清掉 _current_label）
    assert "500" in label.text()
    assert card._reply is None
    assert card._current_label is None  # 流式指针清掉


# ---- _on_new_conversation ----


def test_on_new_conversation_resets_session_and_clears_history(qapp):
    """_on_new_conversation：调子类 _reset_session + 清整个 history / _input。"""
    card = _MockSubclass()
    card._add_message("user", "old user msg")
    card._add_message("assistant", "old assistant msg")
    assert card._history_layout.count() == 2
    card._input.setText("x")
    card._on_new_conversation()
    assert card._history_layout.count() == 0
    assert card._current_label is None
    assert card._current_text == ""
    assert card._input.text() == ""


def test_new_conversation_during_streaming_is_noop(qapp):
    """流式回答期间点'新会话'：早返回，**不**触发 abort、**不**清 history、**不**重置 session。

    同 _on_send 的 race 保护——避免在流式期间调用 abort。
    """
    card = _MockSubclass()
    in_flight = object()
    card._reply = in_flight
    # 已积累一些历史
    card._add_message("user", "old question")
    card._add_message("assistant", "old reply")
    # mock _reset_session 不应被调
    reset_calls = []
    card._reset_session = lambda: reset_calls.append(True)
    # 输入框已有文字（用户正在打字时点的新会话）
    card._input.setText("打到一半")

    card._on_new_conversation()

    assert card._reply is in_flight, "self._reply 仍指向旧 reply"
    assert card._history_layout.count() == 2, "history 不应被清"
    assert reset_calls == [], "_reset_session 不应被调"
    assert card._input.text() == "打到一半", "输入框文字应保留"


# ---- race：abort 后旧 reply 的 finished 信号到达，不能误删新 reply ----


def test_stale_finished_signal_does_not_touch_new_reply(qapp):
    """abort 旧 reply 后，旧 reply 的 finished 信号到达，handler 必须能识别并跳过。

    复现的闪退场景：
      1. 用户发消息 → 创建 reply A（self._reply = A）
      2. 用户再发消息 → A.abort() + deleteLater + self._reply = B
      3. Qt 事件循环里 A 的 finished 信号仍然 emit → _on_done 被调用
      4. 老代码读 self._reply（已是 B），把 B.deleteLater() + self._reply = None
         → B 还在用就被标记删除，下次 B.readyRead 时崩 RuntimeError
    """
    card = _MockSubclass()
    class _Reply:
        def __init__(self, label):
            self.label = label
            self.deleted = False
            # Qt 信号是 class-level attribute；mock 用实例属性实现
            self.readyRead = _SignalStub()
            self.finished = _SignalStub()
        def abort(self): pass
        def deleteLater(self):
            self.deleted = True
        def error(self): return 0
        def readAll(self): return b""
        def attribute(self, _key): return None

    # 用 send() 真触发 reply 创建
    def _fake_post(_req, _body):
        return _Reply("A")
    card._nam.post = _fake_post
    card._input.setText("first")
    card._on_send()
    assert card._reply is not None
    first_reply = card._reply

    # 模拟"用户再发消息"：创建新 reply，旧的 abort
    new_reply = _Reply("B")
    new_reply.deleted = False
    card._reply = new_reply

    # 现在旧 reply A 的 finished 信号到达（Qt 异步事件）
    first_reply.deleteLater()  # 模拟 A 已经被标记延迟删除
    card._on_done(first_reply)  # 模拟 A 的 finished 触发 handler

    # 关键断言：新 reply 必须没被误删
    assert not new_reply.deleted, "stale finished 信号误删了新 reply"
    assert card._reply is new_reply, "新 reply 指针被错误清掉"


def test_stale_readyRead_signal_does_not_pollute_buffer(qapp):
    """旧 reply 的 readyRead 信号到达，handler 必须丢弃其数据。"""
    card = _MockSubclass()
    class _Reply:
        def __init__(self, label):
            self.label = label
            self.read_calls = 0
            self.payload = b""
        def readAll(self):
            self.read_calls += 1
            return self.payload
        def error(self): return 0
        def attribute(self, _key): return None
        def abort(self): pass
        def deleteLater(self): pass

    current = _Reply("current")
    current.payload = b'ignored frame\n\n'
    card._reply = current
    card._sse_buf = bytearray()

    # 旧 reply 触发 readyRead
    stale = _Reply("stale")
    stale.payload = b'stale frame should not enter buffer\n\n'
    card._on_data(stale)

    # buffer 应该是空的——stale 信号被丢弃
    assert len(card._sse_buf) == 0, f"stale 数据污染 buffer: {card._sse_buf!r}"
    assert stale.read_calls == 0, "stale reply 的 readAll 没被调用"


def test_on_done_clears_reply_only_for_current(qapp):
    """_on_done 只在 reply == self._reply 时才清 self._reply。"""
    card = _MockSubclass()
    class _Reply:
        def __init__(self):
            self.deleted = False
        def abort(self): pass
        def deleteLater(self): self.deleted = True
        def error(self): return 0
        def readAll(self): return b""
        def attribute(self, _key): return None

    current = _Reply()
    card._reply = current
    card._on_done(current)
    assert current.deleted  # 正常流程：current 被删
    assert card._reply is None

    # 再次发送，创建新 reply
    new = _Reply()
    card._reply = new
    card._on_done(new)
    assert new.deleted
    assert card._reply is None


# ---- 对话列表（user/assistant 样式 + 累积）----


def test_add_message_user_uses_user_style_and_right_align(qapp):
    card = _MockSubclass()
    label = card._add_message("user", "hi")
    # v3.2 样式大改：user 气泡走全局 QSS，通过 objectName 区分
    assert label.objectName() == card.BUBBLE_USER
    assert label.alignment() & QtCore.Qt.AlignRight
    assert label.wordWrap() is True
    assert label.textInteractionFlags() & QtCore.Qt.TextSelectableByMouse


def test_add_message_assistant_uses_assistant_style_and_left_align(qapp):
    card = _MockSubclass()
    label = card._add_message("assistant", "reply")
    # v3.2 样式大改：assistant 气泡走全局 QSS，通过 objectName 区分
    assert label.objectName() == card.BUBBLE_ASSISTANT
    assert label.alignment() & QtCore.Qt.AlignLeft
    assert label.wordWrap() is True


def test_add_message_label_fills_scroll_area_width(qapp):
    """消息 label 必须撑满 scroll area 宽度（避免靠左上角显示）。"""
    card = _MockSubclass()
    label = card._add_message("user", "x")
    policy = label.sizePolicy()
    assert policy.horizontalPolicy() == QtWidgets.QSizePolicy.Expanding
    assert policy.verticalPolicy() in (
        QtWidgets.QSizePolicy.Preferred,
        QtWidgets.QSizePolicy.Minimum,
    )


def test_send_appends_user_then_assistant_placeholder(qapp):
    """_on_send 必须把用户消息和 assistant 占位都加进 history。"""
    card = _MockSubclass()
    class _Reply:
        readyRead = _SignalStub()
        finished = _SignalStub()
    class _Nam:
        def post(self, *a, **k): return _Reply()
    card._nam = _Nam()
    card._input.setText("hello")
    card._on_send()
    # history 应该 2 条：user + assistant 占位
    assert card._history_layout.count() == 2
    user_label = card._history_layout.itemAt(0).widget()
    asst_label = card._history_layout.itemAt(1).widget()
    assert user_label.text() == "hello"
    assert asst_label.text() == "…"
    # _current_label 指向 assistant 占位
    assert card._current_label is asst_label
    assert card._current_text == ""


def test_streaming_updates_only_current_assistant_label(qapp):
    """流式 delta 只更新 _current_label，不动之前的消息。"""
    card = _MockSubclass()
    # 先放一条历史 user 消息
    old_user = card._add_message("user", "old")
    class _Reply:
        def readAll(self): return b""
        def error(self): return 0
    card._reply = _Reply()
    card._current_label = card._add_message("assistant", "")
    card._sse_buf.extend(b'data: {"delta": "new reply"}\n\n')
    card._on_data(card._reply)
    # 旧的 user 不动，新的 assistant 更新
    assert old_user.text() == "old"
    assert card._current_label.text() == "new reply"


def test_history_after_multiple_sends(qapp):
    """多次发送后 history 累积：u1 a1 u2 a2 ...。

    注意：流式期间 _on_send 早返回（见 race 保护），所以两次发送之间必须
    模拟流式完成（_on_done → self._reply = None）才能发下一条。
    """
    card = _MockSubclass()
    class _Reply:
        readyRead = _SignalStub()
        finished = _SignalStub()
        def error(self): return 0  # NoError
        def readAll(self): return b""
        def deleteLater(self): pass
    class _Nam:
        def post(self, *a, **k): return _Reply()
    card._nam = _Nam()

    def _send(text):
        # _on_send 从 self._input.text() 读输入
        card._input.setText(text)
        card._on_send()
        # 模拟流完成：把 assistant 占位替换为 AI 回复
        card._current_label.setText("AI: " + text)
        # 调基类 _on_done 把 self._reply / _current_label / _sse_buf 清干净
        card._on_done(card._reply)

    _send("Q1")
    _send("Q2")
    assert card._history_layout.count() == 4
    assert card._history_layout.itemAt(0).widget().text() == "Q1"
    assert card._history_layout.itemAt(1).widget().text() == "AI: Q1"
    assert card._history_layout.itemAt(2).widget().text() == "Q2"
    assert card._history_layout.itemAt(3).widget().text() == "AI: Q2"
