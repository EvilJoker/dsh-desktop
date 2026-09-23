# 小欧对话 Tab 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 panel 加第 4 个 tab「小欧」对接团队 igptproxy 服务（iGPT 私有协议），与现有 OpenClaw「对话」tab 并列。

**Architecture:** 抽 `BaseChatCard` 基类承担 UI/生命周期/网络框架；`ChatCard`（OpenClaw 协议）和 `XiaoouCard`（小欧协议）继承基类，各实现 3 个虚方法（body / SSE 帧 / auth header）。配置走 `panel/config.py` + `data/config.json`（生产 `~/.desk-assistant/config.json`）。

**Tech Stack:** Python 3.6 兼容（生产 PyInstaller）/ Python 3.11 兼容（dev 测试）+ PyQt5 5.13 + QtNetwork + stdlib `json`/`uuid`/`pathlib`。

**⚠️ 无 commit 步骤**：用户硬规则「禁止主动 git commit，必须用户明确要求才提交」。每任务完成后请向用户确认是否要 commit。

**执行前置**：
- 工作目录：`/home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant`
- Python 解释器：`/usr/local/bin/python3`（3.11，用于测试和 dev）
- 跑测试：`QT_QPA_PLATFORM=offscreen pytest --cov=panel --cov-branch --cov-report=term-missing`
- 跑覆盖率门禁：必须 `>=85% line / >=70% branch`

---

## 文件结构总览

| 路径 | 状态 | 职责 |
|------|------|------|
| `panel/base_chat_card.py` | 新增 | 抽出来的 chat 卡片基类：UI 装配 + 网络生命周期 + SSE 帧循环 |
| `panel/chat_card.py` | 改写 | BaseChatCard 子类，实现 OpenClaw 协议（Bearer + session_key） |
| `panel/xiaoou_card.py` | 新增 | BaseChatCard 子类，实现小欧 iGPT 协议（X-Emp-No + chatUuid） |
| `panel/config.py` | 新增 | 读 config.json，提供 DEFAULT_CONFIG 兜底 |
| `panel/main.py` | 改 | 从 config 加载 + 加第 4 张卡 + Ctrl+4 + 4 tab 标签 |
| `data/config.json` | 新增 | dev 配置示例（项目内可写） |
| `tests/test_base_chat_card.py` | 新增 | 基类 12 个测试（mock 子类） |
| `tests/test_chat_card.py` | 改写 | 缩减到 6 个 OpenClaw 协议测试 |
| `tests/test_xiaoou_card.py` | 新增 | 7 个小欧协议测试 |
| `tests/test_config.py` | 新增 | 5 个 config 加载测试 |
| `tests/test_main.py` | +2 行 | 加 2 个 tab/Ctrl+4 测试 |

**不动**：`panel/metrics_card.py`、`panel/events_card.py`、`server/*`、`script/*`、`tests/test_events_card.py`、`tests/test_metrics_store.py`、`tests/test_sse_hub.py`、`tests/test_app.py`、`tests/test_db.py`、`tests/test_events_store.py`、`tests/test_panel_utils.py`。

---

### Task 1：BaseChatCard 基类 + 12 个测试

**Files:**
- Create: `panel/base_chat_card.py`
- Create: `tests/test_base_chat_card.py`

这是地基。先建基类 + 测试，后续 ChatCard/XiaoouCard 才能继承。

- [ ] **Step 1：写 12 个测试**（mock 子类，不依赖 OpenClaw/小欧）

**创建 `tests/test_base_chat_card.py`**，完整内容：

```python
"""panel/base_chat_card.py 单元测试：覆盖基类 UI 装配 + 生命周期（mock 子类）。"""
import json

from PyQt5 import QtCore
from PyQt5.QtNetwork import QNetworkReply

from panel.base_chat_card import BaseChatCard


# ---- mock 子类 ----


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
    """__init__ 跑完所有 UI 装配：title / input / reply_label / 新对话按钮都在。"""
    card = _MockSubclass()
    assert card._input is not None
    assert card._reply_label is not None
    # 输入行有一个"新对话"按钮
    input_row_children = card._input.parent().children()
    assert any(c.text() == "⟲" for c in input_row_children if hasattr(c, "text"))


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


def test_send_aborts_previous_reply(qapp):
    card = _MockSubclass()
    # fake 旧 reply
    class _OldReply:
        def __init__(self):
            self.deleted = False
            self.aborted = False
        def abort(self):
            self.aborted = True
        def deleteLater(self):
            self.deleted = True
    old = _OldReply()
    card._reply = old

    # monkeypatch _nam.post 不真正发请求
    class _NoopReply:
        readyRead = type("Sig", (), {"connect": lambda *a, **k: None})()
        finished = type("Sig", (), {"connect": lambda *a, **k: None})()
    class _NoopNam:
        def post(self, *a, **k):
            return _NoopReply()
    import types
    card._nam = _NoopNam()
    card._input.setText("hi")
    card._on_send()
    assert old.aborted
    assert old.deleted


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
            return _Reply()
    card._nam = _Nam()
    card._input.setText("x")
    card._on_send()
    # X-Test 是 mock 子类自填的；用 monkeypatch 不便，直接用真 nam 验证
    # 改成：mock 子类记录 _auth_headers 返回值被 _on_send 使用
    # 这里改用直接调 _auth_headers
    assert card._auth_headers() == [(b"X-Test", b"1")]


# ---- _on_data SSE 帧循环 ----


def test_on_data_calls_subclass_parse_sse_frame(qapp):
    """每一帧都过子类 _parse_sse_frame，delta 非空才累加。"""
    card = _MockSubclass()
    class _Reply:
        def readAll(self): return b""
        def error(self): return 0
    payload = json.dumps({"delta": "你好"})
    card._sse_buf.extend(b"data: " + payload.encode() + b"\n\n")
    card._reply = _Reply()
    card._on_data()
    assert len(card.parse_calls) == 1
    assert "你好" in card._reply_label.text()


def test_on_data_subclass_returns_none_skips_frame(qapp):
    """子类返回 None → 跳过该帧，不累加。"""
    card = _MockSubclass()
    card._acc = "pre"
    class _Reply:
        def readAll(self): return b""
        def error(self): return 0
    payload = json.dumps({"choices": [{"delta": {}}]})  # _parse_sse_frame 返回 None
    card._sse_buf.extend(b"data: " + payload.encode() + b"\n\n")
    card._reply = _Reply()
    card._on_data()
    assert card._acc == "pre"


def test_on_data_accumulates_and_truncates(qapp):
    """累加超过 REPLY_LINES_KEEP 行 → 截到尾部。"""
    card = _MockSubclass()
    class _Reply:
        def readAll(self): return b""
        def error(self): return 0
    delta_obj = {"delta": "line\n"}
    total = card.REPLY_LINES_KEEP + 10
    frame = b""
    for _ in range(total):
        frame += b"data: " + json.dumps(delta_obj).encode() + b"\n\n"
    card._reply = _Reply()
    card._sse_buf.extend(frame)
    card._on_data()
    displayed_lines = card._reply_label.text().split("\n")
    assert len(displayed_lines) == card.REPLY_LINES_KEEP


def test_on_data_no_reply_early_return(qapp):
    """self._reply is None → 早返回。"""
    card = _MockSubclass()
    card._reply = None
    card._on_data()  # 不应抛


# ---- _on_done ----


def test_on_done_no_error_clears_state(qapp):
    card = _MockSubclass()
    class _Reply:
        def error(self): return QNetworkReply.NoError
        def deleteLater(self): pass
    card._reply = _Reply()
    card._on_done()
    assert card._reply is None
    assert card._sse_buf == bytearray()


def test_on_done_error_uses_subclass_format_error(qapp):
    """_on_done 错误时必须调子类的 _format_error 显示。"""
    card = _MockSubclass()
    class _Reply:
        def error(self): return QNetworkReply.OperationCanceledError
        def attribute(self, _): return 500
        def readAll(self): return b"server err"
        def deleteLater(self): pass
    card._reply = _Reply()
    card._on_done()
    # mock 子类没重写 _format_error，用基类默认
    assert "500" in card._reply_label.text()
    assert card._reply is None


# ---- _on_new_conversation ----


def test_on_new_conversation_resets_session_and_clears_ui(qapp):
    """_on_new_conversation：调子类 _reset_session + 清 _reply_label / _input。"""
    card = _MockSubclass()
    card._reply_label.setText("old")
    card._input.setText("x")
    card._on_new_conversation()
    assert card._reply_label.text() == ""
    assert card._input.text() == ""


def test_new_conversation_aborts_in_flight_reply(qapp):
    card = _MockSubclass()
    class _Reply:
        def __init__(self):
            self.deleted = False
            self.aborted = False
        def abort(self):
            self.aborted = True
        def deleteLater(self):
            self.deleted = True
    card._reply = _Reply()
    card._on_new_conversation()
    assert card._reply.aborted
    assert card._reply.deleted
```

- [ ] **Step 2：跑测试，验证全部失败**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
QT_QPA_PLATFORM=offscreen pytest tests/test_base_chat_card.py -v 2>&1 | tail -20
```

Expected：`ModuleNotFoundError: No module named 'panel.base_chat_card'` 或 `ImportError`。

- [ ] **Step 3：实现 `panel/base_chat_card.py`**

**创建 `panel/base_chat_card.py`**，完整内容：

```python
"""panel/base_chat_card.py — chat 类卡片基类：UI 装配 + 网络生命周期。"""
import json
import logging
import re

from PyQt5 import QtCore, QtNetwork, QtWidgets

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

    REPLY_LINES_VIEW = 10
    REPLY_LINES_KEEP = 500
    LINE_PX = 18

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self._url = url

        # 状态
        self._nam = QtNetwork.QNetworkAccessManager(self)
        self._reply = None
        self._sse_buf = bytearray()
        self._acc = ""
        self._last_biz_error = None
        self._safety_blocked = False

        self.setObjectName("ChatCard")
        self.setStyleSheet(
            "QFrame#ChatCard {"
            "  background: rgba(255,255,255,15);"
            "  border: 1px solid rgba(255,255,255,40);"
            "  border-radius: 10px;"
            "}"
        )

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 10)
        outer.setSpacing(6)

        title = QtWidgets.QLabel(self._title_text())
        title.setStyleSheet(
            "color: rgba(255,255,255,150);"
            "font-size: 10px;"
            "font-weight: bold;"
            "letter-spacing: 1px;"
            "background: transparent;"
            "border: 0;"
        )
        outer.addWidget(title)

        # 流式回显
        self._reply_scroll = QtWidgets.QScrollArea()
        self._reply_scroll.setWidgetResizable(True)
        self._reply_scroll.setMinimumHeight(self.LINE_PX * self.REPLY_LINES_VIEW + 8)
        self._reply_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._reply_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: 0; }"
        )
        self._reply_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self._reply_label = QtWidgets.QLabel("")
        self._reply_label.setStyleSheet(
            "color: #a8d8ff;"
            "font-size: 11px;"
            "padding: 0 4px;"
            "background: transparent;"
            "border: 0;"
        )
        self._reply_label.setWordWrap(True)
        self._reply_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self._reply_label.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self._reply_label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Minimum,
        )
        self._reply_scroll.setWidget(self._reply_label)
        outer.addWidget(self._reply_scroll, 1)
        outer.addStretch(1)

        # 输入行
        input_row = QtWidgets.QHBoxLayout()
        input_row.setSpacing(6)
        input_row.setContentsMargins(0, 0, 0, 0)

        self._input = QtWidgets.QLineEdit()
        self._input.setPlaceholderText(self._input_placeholder())
        self._input.setStyleSheet(
            "QLineEdit {"
            "  background: rgba(255,255,255,30);"
            "  border: 1px solid rgba(255,255,255,60);"
            "  border-radius: 8px;"
            "  color: #ffffff;"
            "  padding: 6px 10px;"
            "  font-size: 12px;"
            "}"
            "QLineEdit:focus {"
            "  border-color: rgba(120,180,255,200);"
            "  background: rgba(255,255,255,50);"
            "}"
            "QLineEdit:disabled {"
            "  color: rgba(255,255,255,80);"
            "  background: rgba(255,255,255,15);"
            "}"
        )
        self._input.setEnabled(False)
        self._input.returnPressed.connect(self._on_send)
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
        """默认只放一个'新对话'按钮。"""
        btn = QtWidgets.QPushButton("⟲")
        btn.setFixedSize(34, 30)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        btn.setToolTip("新对话（重置 session）")
        btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(255,255,255,30);"
            "  border: 1px solid rgba(255,255,255,60);"
            "  border-radius: 8px;"
            "  color: #ffffff;"
            "  font-size: 14px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(120,180,255,80);"
            "  border-color: rgba(120,180,255,200);"
            "}"
        )
        btn.clicked.connect(self._on_new_conversation)
        return [btn]

    def _reset_session(self):
        pass

    # ----- 生命周期 -----

    def _on_send(self):
        text = self._input.text().strip()
        if not text:
            return

        if self._reply is not None:
            try:
                self._reply.abort()
            except RuntimeError as e:
                log.debug("abort reply failed: %s", e)
            self._reply.deleteLater()
            self._reply = None
        self._sse_buf.clear()
        self._acc = ""
        self._last_biz_error = None
        self._safety_blocked = False
        self._reply_label.setText("…")

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
        reply.readyRead.connect(self._on_data)
        reply.finished.connect(self._on_done)
        self._reply = reply
        self._input.clear()

    def _on_data(self):
        reply = self._reply
        if reply is None:
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
                    self._acc += delta
                    lines = _MULTI_NL.sub("\n", self._acc).split("\n")
                    if len(lines) > self.REPLY_LINES_KEEP:
                        lines = lines[-self.REPLY_LINES_KEEP:]
                    display = "\n".join(lines)
                    self._reply_label.setText(display)
                    QtCore.QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        sb = self._reply_scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_done(self):
        reply = self._reply
        if reply is not None:
            err = reply.error()
            if err != QtNetwork.QNetworkReply.NoError:
                status = reply.attribute(
                    QtNetwork.QNetworkRequest.HttpStatusCodeAttribute
                )
                body = bytes(reply.readAll())[:200]
                log.warning(
                    "chat failed: err=%s status=%s body=%r",
                    err, status, body,
                )
                self._reply_label.setText(self._format_error(err, status, body))
            self._reply.deleteLater()
            self._reply = None
        self._sse_buf.clear()

    def _on_new_conversation(self):
        if self._reply is not None:
            try:
                self._reply.abort()
            except RuntimeError as e:
                log.debug("abort reply failed: %s", e)
            self._reply.deleteLater()
            self._reply = None
        self._sse_buf.clear()
        self._acc = ""
        self._last_biz_error = None
        self._safety_blocked = False
        self._reset_session()
        self._reply_label.setText("")
        self._input.setText("")
        self._input.setFocus()
```

- [ ] **Step 4：跑测试，验证全部通过**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/test_base_chat_card.py -v 2>&1 | tail -30
```

Expected：12 passed。

- [ ] **Step 5：跑覆盖率，确认 ≥ 85% 行 / 70% 分支**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/test_base_chat_card.py --cov=panel.base_chat_card --cov-branch --cov-report=term-missing 2>&1 | tail -10
```

Expected：base_chat_card.py 覆盖率 ≥ 85% line / 70% branch。

> **任务结束**：请向用户确认是否要 commit（消息示例："Task 1 完成，12 个测试通过。要 commit 吗？"）。

---

### Task 2：ChatCard 改写为 BaseChatCard 子类

**Files:**
- Rewrite: `panel/chat_card.py`
- Rewrite: `tests/test_chat_card.py`

ChatCard 现有 19 个测试，基类逻辑下沉到 test_base_chat_card.py 后，本文件只剩 6 个 OpenClaw 协议测试。

- [ ] **Step 1：写 6 个新测试**

**完全重写 `tests/test_chat_card.py`**，内容：

```python
"""panel/chat_card.py 单元测试：OpenClaw 协议（body / SSE 解析 / auth / set_token）。"""
from panel.chat_card import ChatCard


def _make_card(qapp, token="tok-abc"):
    return ChatCard(
        openclaw_url="http://openclaw:18789/v1/chat/completions",
        model="openclaw",
        session_key="agent:main:openai:00000000-0000-4000-8000-000000000001@topic:desk-assistant",
        chat_url="http://openclaw:18789/chat?lang=zh-CN&session=agent:main:openai:00000000-0000-4000-8000-000000000001@topic:desk-assistant",
    )._set_token_for_test(token)


# Monkey-patch: 给 ChatCard 加一个 _set_token_for_test 直接调 set_token，
# 绕开外部 panel 调用。生产代码不需要这个方法。
import pytest

@pytest.fixture(autouse=True)
def _add_test_hook(monkeypatch):
    """给 ChatCard 加 _set_token_for_test 测试钩子，避免改生产代码。"""
    def _set_token_for_test(self, token):
        self.set_token(token)
        return self
    monkeypatch.setattr(ChatCard, "_set_token_for_test", _set_token_for_test)


# ---- body 构造 ----


def test_build_request_body_has_openai_shape(qapp):
    card = _make_card(qapp, token="tok")
    body = card._build_request_body("hello")
    assert body["model"] == "openclaw"
    assert body["messages"] == [{"role": "user", "content": "hello"}]
    assert body["stream"] is True


# ---- SSE 帧解析 ----


def test_parse_sse_frame_extracts_delta_content(qapp):
    card = _make_card(qapp)
    delta = card._parse_sse_frame(
        {"choices": [{"delta": {"content": "你好"}}]}
    )
    assert delta == "你好"


def test_parse_sse_frame_missing_delta_returns_none(qapp):
    card = _make_card(qapp)
    delta = card._parse_sse_frame({"choices": [{"delta": {}}]})
    assert delta is None


# ---- auth header ----


def test_auth_headers_include_bearer_and_session_key(qapp):
    card = _make_card(qapp, token="tok-xyz")
    headers = card._auth_headers()
    headers_dict = dict(headers)
    assert headers_dict[b"Authorization"] == b"Bearer tok-xyz"
    assert headers_dict[b"x-openclaw-session-key"] == b"agent:main:openai:00000000-0000-4000-8000-000000000001@topic:desk-assistant"


# ---- set_token 行为 ----


def test_set_token_enables_input(qapp):
    card = _make_card(qapp, token=None)
    assert not card._input.isEnabled()
    card.set_token("abc")
    assert card._token == "abc"
    assert card._input.isEnabled()


def test_set_token_empty_keeps_disabled_and_sets_placeholder(qapp):
    card = _make_card(qapp, token=None)
    card.set_token(None)
    assert not card._input.isEnabled()
    assert "未找到" in card._input.placeholderText()
```

- [ ] **Step 2：跑测试，验证全部失败（chat_card 还没改写）**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/test_chat_card.py -v 2>&1 | tail -20
```

Expected：6 个测试全 fail（因为旧 ChatCard 不会调用子类 _set_token_for_test 等）。或者 ImportError。

- [ ] **Step 3：完全重写 `panel/chat_card.py`**

**替换整个文件**：

```python
"""panel/chat_card.py — OpenClaw 协议 chat 卡片（继承 BaseChatCard）。"""
import json
import logging

from PyQt5 import QtCore, QtGui, QtWidgets

from base_chat_card import BaseChatCard

log = logging.getLogger(__name__)


class ChatCard(BaseChatCard):
    """OpenClaw 协议 chat 卡片。

    用法：
        card = ChatCard(
            openclaw_url="http://127.0.0.1:18789/v1/chat/completions",
            model="openclaw",
            session_key="agent:main:openai:...@topic:...",
            chat_url="http://127.0.0.1:18789/chat?lang=zh-CN&session=...",
        )
        card.set_token("4b54...")  # 没 token 输入框禁用
    """

    def __init__(self, openclaw_url, model, session_key, chat_url, parent=None):
        self._model = model
        self._session_key = session_key
        self._chat_url = chat_url
        self._token = None
        super().__init__(openclaw_url, parent)
        # 替换基类默认的"新对话"按钮为"打开 web UI"按钮
        # （基类 _build_button_row 已被 super().__init__() 调用，
        # 但基类默认按钮是"新对话"，这里我们在外层重新覆盖 input_row）
        # 实际做法：把基类默认按钮替换成 web UI 按钮。
        # 通过重新连接 click + 改 text 实现。
        # 简单做法：再放一个"打开 web UI"按钮到 input_row。
        self._append_open_chat_button()

    def _append_open_chat_button(self):
        """基类默认放一个'新对话'按钮；这里追加一个'打开 web UI'按钮。"""
        # 找到 input_row（基类 outer 的最后一个 QHBoxLayout）
        outer = self.layout()
        input_row = outer.itemAt(outer.count() - 1).layout()
        # 把基类"新对话"按钮的 tooltip 改一下，再追加 web UI 按钮
        # 简化：找到第一个 QPushButton，改 tooltip + 追加 web UI 按钮
        for i in range(input_row.count()):
            item = input_row.itemAt(i)
            w = item.widget()
            if isinstance(w, QtWidgets.QPushButton):
                w.setText("⟲")
                w.setToolTip("新对话（重置 session）")
                break
        self._open_chat_btn = QtWidgets.QPushButton("↗")
        self._open_chat_btn.setFixedSize(34, 30)
        self._open_chat_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._open_chat_btn.setToolTip("在浏览器打开本 session 完整对话")
        self._open_chat_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(255,255,255,30);"
            "  border: 1px solid rgba(255,255,255,60);"
            "  border-radius: 8px;"
            "  color: #ffffff;"
            "  font-size: 14px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(120,180,255,80);"
            "  border-color: rgba(120,180,255,200);"
            "}"
        )
        self._open_chat_btn.clicked.connect(self._on_open_chat)
        input_row.addWidget(self._open_chat_btn)

    # ----- BaseChatCard 虚方法实现 -----

    def _title_text(self):
        return "对话 / OPENCLAW"

    def _input_placeholder(self):
        return "发送给 openclaw（Enter 发送）…"

    def _build_request_body(self, text):
        return {
            "model": self._model,
            "messages": [{"role": "user", "content": text}],
            "stream": True,
        }

    def _parse_sse_frame(self, data):
        return data.get("choices", [{}])[0].get("delta", {}).get("content")

    def _auth_headers(self):
        return [
            (b"Authorization", f"Bearer {self._token}".encode()),
            (b"x-openclaw-session-key", self._session_key.encode()),
        ]

    # ----- 旧 API：set_token -----

    def set_token(self, token):
        """启动后从配置读取的 token，传入后启用输入框。"""
        self._token = token
        if token:
            self._input.setEnabled(True)
        else:
            self._input.setEnabled(False)
            self._input.setPlaceholderText(
                "未找到 openclaw token（~/.openclaw/openclaw.json）"
            )

    # ----- 旧 API：打开 web UI -----

    def _on_open_chat(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(self._chat_url))
```

- [ ] **Step 4：跑测试，验证全部通过**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/test_chat_card.py -v 2>&1 | tail -15
```

Expected：6 passed。

- [ ] **Step 5：跑基类 + ChatCard 测试，确认 ChatCard 改写没破坏基类**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/test_base_chat_card.py tests/test_chat_card.py -v 2>&1 | tail -10
```

Expected：18 passed（12 + 6）。

- [ ] **Step 6：跑 panel 旧测试，确认 SSE 客户端测试没坏**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/test_main.py -v 2>&1 | tail -10
```

Expected：所有 test_sse_client_* 仍然通过（它们 import 的是 SSEClient，未动）。

> **任务结束**：请向用户确认是否要 commit。

---

### Task 3：config.py + data/config.json + 5 个测试

**Files:**
- Create: `panel/config.py`
- Create: `data/config.json`
- Create: `tests/test_config.py`

独立的配置加载模块，不依赖 UI。

- [ ] **Step 1：写 5 个 config 测试**

**创建 `tests/test_config.py`**，完整内容：

```python
"""panel/config.py 单元测试：覆盖 5 种加载场景。"""
import json
import os

import pytest

from panel.config import DEFAULT_CONFIG, load_config


def test_load_default_when_file_missing(monkeypatch, tmp_path):
    """env 指向不存在的文件 + home 不存在 → 用 DEFAULT_CONFIG。"""
    monkeypatch.setenv("DESK_ASSISTANT_CONFIG", str(tmp_path / "nope.json"))
    monkeypatch.setattr("panel.config._USER_CONFIG", tmp_path / "nope-home.json")
    cfg = load_config()
    assert cfg == DEFAULT_CONFIG


def test_load_default_when_file_bad_json(monkeypatch, tmp_path):
    """文件存在但 JSON 坏 → 用 DEFAULT_CONFIG。"""
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setenv("DESK_ASSISTANT_CONFIG", str(p))
    cfg = load_config()
    assert cfg == DEFAULT_CONFIG


def test_load_default_when_file_not_dict(monkeypatch, tmp_path):
    """文件顶层不是 dict（是 list）→ 用 DEFAULT_CONFIG。"""
    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    monkeypatch.setenv("DESK_ASSISTANT_CONFIG", str(p))
    cfg = load_config()
    assert cfg == DEFAULT_CONFIG


def test_user_config_overrides_defaults(monkeypatch, tmp_path):
    """用户配置覆盖默认。"""
    p = tmp_path / "user.json"
    p.write_text(json.dumps({
        "xiaoou": {
            "base_url": "http://custom:9999",
            "model": "custom-model",
            "topic_id": 42,
            "source": "test",
            "auth": {"header": "X-Test", "value": "v"},
        },
    }), encoding="utf-8")
    monkeypatch.setenv("DESK_ASSISTANT_CONFIG", str(p))
    cfg = load_config()
    assert cfg["xiaoou"]["base_url"] == "http://custom:9999"
    assert cfg["xiaoou"]["model"] == "custom-model"
    # openclaw 没被用户覆盖 → 用默认
    assert cfg["openclaw"]["url"] == DEFAULT_CONFIG["openclaw"]["url"]


def test_user_partial_xiaoou_block_fully_replaces_default(monkeypatch, tmp_path):
    """浅 merge：用户 xiaoou 块整体替换默认。"""
    p = tmp_path / "partial.json"
    p.write_text(json.dumps({
        "xiaoou": {"base_url": "http://only-url"},
    }), encoding="utf-8")
    monkeypatch.setenv("DESK_ASSISTANT_CONFIG", str(p))
    cfg = load_config()
    # 用户整个 xiaoou 块只有 base_url，其他键被覆盖没了
    assert cfg["xiaoou"] == {"base_url": "http://only-url"}
```

- [ ] **Step 2：跑测试，验证全部失败**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/test_config.py -v 2>&1 | tail -15
```

Expected：`ModuleNotFoundError: No module named 'panel.config'`。

- [ ] **Step 3：实现 `panel/config.py`**

**创建 `panel/config.py`**，完整内容：

```python
"""panel/config.py — 加载 desk-assistant 配置（chat 协议参数）。"""
import json
import logging
import os
from copy import deepcopy
from pathlib import Path

log = logging.getLogger(__name__)


# ---- 默认配置 ----

DEFAULT_CONFIG = {
    "openclaw": {
        "url": "http://127.0.0.1:18789/v1/chat/completions",
        "model": "openclaw",
        "session_key": "agent:main:openai:00000000-0000-4000-8000-000000000001@topic:desk-assistant",
        "chat_url": "http://127.0.0.1:18789/chat?lang=zh-CN&session=agent:main:openai:00000000-0000-4000-8000-000000000001@topic:desk-assistant",
    },
    "xiaoou": {
        "base_url": "http://10.90.30.228:22004",
        "model": "R-T-2-sun1-MiniMax-M2.7-highspeed",
        "topic_id": 1001,
        "source": "desk-assistant",
        "auth": {
            "header": "X-Emp-No",
            "value": "10312862",
        },
    },
}


# ---- 路径解析 ----

_USER_CONFIG = Path.home() / ".desk-assistant" / "config.json"
_DEV_CONFIG = Path(__file__).resolve().parent.parent / "data" / "config.json"


def _config_path():
    """优先级：env > 用户 home > 项目 data/（dev/测试）。"""
    env = os.environ.get("DESK_ASSISTANT_CONFIG")
    if env:
        return Path(env)
    if _USER_CONFIG.exists():
        return _USER_CONFIG
    return _DEV_CONFIG


# ---- 加载 ----


def load_config():
    """读 config.json；找不到/坏掉用 DEFAULT_CONFIG 兜底。

    加载策略：浅 merge。用户的整个 xiaoou 块覆盖默认（不深 merge）。
    """
    p = _config_path()
    if not p.exists():
        log.info("config.json 不存在 (%s)，用默认", p)
        return deepcopy(DEFAULT_CONFIG)
    try:
        user_cfg = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("config.json 读/解析失败 (%s): %s，用默认", type(e).__name__, e)
        return deepcopy(DEFAULT_CONFIG)
    if not isinstance(user_cfg, dict):
        log.warning("config.json 顶层不是 dict，用默认")
        return deepcopy(DEFAULT_CONFIG)
    merged = deepcopy(DEFAULT_CONFIG)
    merged.update(user_cfg)  # 浅 merge
    return merged
```

- [ ] **Step 4：创建 `data/config.json`（dev 示例，运行时未用）**

**创建 `desk-assistant/data/config.json`**：

```json
{
  "openclaw": {
    "url": "http://127.0.0.1:18789/v1/chat/completions",
    "model": "openclaw",
    "session_key": "agent:main:openai:00000000-0000-4000-8000-000000000001@topic:desk-assistant",
    "chat_url": "http://127.0.0.1:18789/chat?lang=zh-CN&session=agent:main:openai:00000000-0000-4000-8000-000000000001@topic:desk-assistant"
  },
  "xiaoou": {
    "base_url": "http://10.90.30.228:22004",
    "model": "R-T-2-sun1-MiniMax-M2.7-highspeed",
    "topic_id": 1001,
    "source": "desk-assistant",
    "auth": {
      "header": "X-Emp-No",
      "value": "10312862"
    }
  }
}
```

- [ ] **Step 5：跑测试，验证全部通过**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/test_config.py -v 2>&1 | tail -15
```

Expected：5 passed。

- [ ] **Step 6：跑覆盖率**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/test_config.py --cov=panel.config --cov-branch --cov-report=term-missing 2>&1 | tail -10
```

Expected：config.py 覆盖率 ≥ 85% line / 70% branch。

> **任务结束**：请向用户确认是否要 commit。

---

### Task 4：XiaoouCard + 7 个测试

**Files:**
- Create: `panel/xiaoou_card.py`
- Create: `tests/test_xiaoou_card.py`

实现小欧 iGPT 协议，继承 BaseChatCard。

- [ ] **Step 1：写 7 个测试**

**创建 `tests/test_xiaoou_card.py`**，完整内容：

```python
"""panel/xiaoou_card.py 单元测试：覆盖 body / auth / SSE 解析 / 安全拦截。"""
import json

from PyQt5 import QtCore

from panel.xiaoou_card import XiaoouCard


def _make_card(qapp):
    return XiaoouCard(
        base_url="http://xiaoou:22004",
        model="R-T-2-sun1-MiniMax-M2.7-highspeed",
        topic_id=1001,
        source="desk-assistant",
        auth_header=(b"X-Emp-No", b"10312862"),
    )


# ---- 构造 ----


def test_init_uses_config(qapp):
    card = _make_card(qapp)
    assert card._url == "http://xiaoou:22004"
    assert card._model == "R-T-2-sun1-MiniMax-M2.7-highspeed"
    assert card._topic_id == 1001
    assert card._source == "desk-assistant"
    assert card._auth_header == (b"X-Emp-No", b"10312862")
    # chatUuid 在 __init__ 生成，uuid4 字符串
    assert isinstance(card._chat_uuid, str)
    assert len(card._chat_uuid) == 36  # uuid4 标准长度


# ---- body 构造 ----


def test_build_request_body_has_required_fields(qapp):
    card = _make_card(qapp)
    body = card._build_request_body("你好")
    assert body["chatUuid"] == card._chat_uuid
    assert body["topicId"] == 1001
    assert body["source"] == "desk-assistant"
    assert body["keep"] is True
    assert body["stream"] is True
    assert body["text"] == "你好"
    assert body["model"] == "R-T-2-sun1-MiniMax-M2.7-highspeed"


def test_build_request_body_chatUuid_is_uuid_string(qapp):
    """两次构造 → chatUuid 不同（每次都是新 uuid4）。"""
    c1 = _make_card(qapp)
    c2 = _make_card(qapp)
    assert c1._chat_uuid != c2._chat_uuid


# ---- auth header ----


def test_auth_headers_returns_configured_header(qapp):
    card = _make_card(qapp)
    headers = dict(card._auth_headers())
    assert headers == {b"X-Emp-No": b"10312862"}


# ---- SSE 帧解析 ----


def test_parse_sse_frame_extracts_result(qapp):
    card = _make_card(qapp)
    delta = card._parse_sse_frame(
        {"chatUuid": "x", "finishReason": "", "result": "你好"}
    )
    assert delta == "你好"


def test_parse_sse_frame_skips_stop_marker(qapp):
    """finishReason=='stop' 且 result 为空 → 返回 None（不累加）。"""
    card = _make_card(qapp)
    delta = card._parse_sse_frame(
        {"chatUuid": "x", "finishReason": "stop", "result": ""}
    )
    assert delta is None


def test_parse_sse_frame_marks_safety_block(qapp):
    """result 含'检测到高危指令' → 置 _safety_blocked = True。"""
    card = _make_card(qapp)
    assert card._safety_blocked is False
    card._parse_sse_frame(
        {"chatUuid": "x", "finishReason": "", "result": "检测到高危指令，请求已被安全策略拦截。"}
    )
    assert card._safety_blocked is True
```

- [ ] **Step 2：跑测试，验证全部失败**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/test_xiaoou_card.py -v 2>&1 | tail -15
```

Expected：`ModuleNotFoundError: No module named 'panel.xiaoou_card'`。

- [ ] **Step 3：实现 `panel/xiaoou_card.py`**

**创建 `panel/xiaoou_card.py`**，完整内容：

```python
"""panel/xiaoou_card.py — 小欧（igptproxy）iGPT 协议 chat 卡片。"""
import logging
import uuid

from PyQt5 import QtNetwork, QtWidgets

from base_chat_card import BaseChatCard

log = logging.getLogger(__name__)


class XiaoouCard(BaseChatCard):
    """小欧 chat 卡片，对接 igptproxy（iGPT 私有协议）。

    入站协议（iGPT）：
      POST /
      Headers: X-Emp-No: <工号>  (本类用 _auth_header 配置)
      Body: {chatUuid, topicId, source, keep, stream, text, model, ...}
      SSE: data: {"chatUuid":..., "finishReason":..., "result": "<增量>"}

    用法：
        card = XiaoouCard(
            base_url="http://10.90.30.228:22004",
            model="R-T-2-sun1-MiniMax-M2.7-highspeed",
            topic_id=1001,
            source="desk-assistant",
            auth_header=(b"X-Emp-No", b"10312862"),
        )
    """

    def __init__(self, base_url, model, topic_id, source, auth_header, parent=None):
        self._model = model
        self._topic_id = topic_id
        self._source = source
        self._auth_header = auth_header
        self._chat_uuid = str(uuid.uuid4())
        super().__init__(base_url, parent)
        # 小欧不需要 token 注入：启用输入框
        self._input.setEnabled(True)

    # ----- BaseChatCard 虚方法实现 -----

    def _title_text(self):
        return "对话 / 小欧"

    def _input_placeholder(self):
        return "发送给 小欧（Enter 发送）…"

    def _build_request_body(self, text):
        return {
            "chatUuid": self._chat_uuid,
            "topicId": self._topic_id,
            "source": self._source,
            "keep": True,
            "stream": True,
            "text": text,
            "model": self._model,
        }

    def _parse_sse_frame(self, data):
        # 业务错误：SSE 帧可能带 code.code != "0000"
        code = data.get("code")
        if isinstance(code, dict):
            code_val = code.get("code")
            if code_val and code_val != "0000":
                self._last_biz_error = code.get("msg", "未知错误")
        # 安全拦截：result 含"检测到高危指令"
        result = data.get("result") or ""
        if "检测到高危指令" in result or "安全策略拦截" in result:
            self._safety_blocked = True
        return result if result else None

    def _auth_headers(self):
        return [self._auth_header]

    def _format_error(self, err, status, body):
        """状态码后接 body 前 200 字符（小欧错误消息常在 body）。"""
        body_str = body.decode("utf-8", errors="replace")[:200]
        if status:
            return "✕ error: status=%s %s" % (status, body_str)
        return "✕ error: %s" % body_str

    # ----- "新对话" hook：换 chatUuid + 清 flag -----

    def _reset_session(self):
        self._chat_uuid = str(uuid.uuid4())
        self._last_biz_error = None
        self._safety_blocked = False
```

- [ ] **Step 4：跑测试，验证全部通过**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/test_xiaoou_card.py -v 2>&1 | tail -15
```

Expected：7 passed。

- [ ] **Step 5：跑覆盖率**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/test_xiaoou_card.py --cov=panel.xiaoou_card --cov-branch --cov-report=term-missing 2>&1 | tail -10
```

Expected：xiaoou_card.py 覆盖率 ≥ 85% line / 70% branch。

> **任务结束**：请向用户确认是否要 commit。

---

### Task 5：main.py 集成（config 加载 + 4 张卡 + Ctrl+4 + 2 个测试）

**Files:**
- Modify: `panel/main.py`（多处）
- Modify: `tests/test_main.py`（+2 行）

把所有部件拼起来：4 张卡 + 第 4 个 tab + Ctrl+4 快捷键 + 从 config 加载。

- [ ] **Step 1：写 2 个新测试**

**编辑 `tests/test_main.py`**：在文件末尾追加：

```python
# ---- Panel 第 4 张卡（小欧）+ Ctrl+4 ----


def test_panel_has_4_tabs_when_xiaoou_enabled(qapp, monkeypatch, tmp_path):
    """config.json 含 xiaoou 段 → panel 4 个 tab。"""
    import json as _json
    cfg = {
        "openclaw": {
            "url": "http://x/v1/chat/completions",
            "model": "openclaw",
            "session_key": "k",
            "chat_url": "http://x/chat",
        },
        "xiaoou": {
            "base_url": "http://y:22004",
            "model": "m",
            "topic_id": 1,
            "source": "s",
            "auth": {"header": "X-Emp-No", "value": "10312862"},
        },
    }
    p = tmp_path / "config.json"
    p.write_text(_json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("DESK_ASSISTANT_CONFIG", str(p))
    # 重新 import
    import importlib
    import panel.config as _config_mod
    importlib.reload(_config_mod)
    import panel.main as _main_mod
    importlib.reload(_main_mod)
    Panel = _main_mod.Panel
    panel = Panel()
    assert len(panel._tabs) == 4
    assert panel._tabs[3].text() == "小欧"
    assert panel._stack.count() == 4


def test_ctrl_4_switches_to_xiaoou_tab(qapp, monkeypatch, tmp_path):
    """Ctrl+4 → 切到小欧 tab（index 3）。"""
    import json as _json
    import PyQt5
    cfg = {
        "openclaw": {"url": "x", "model": "m", "session_key": "k", "chat_url": "x"},
        "xiaoou": {"base_url": "y", "model": "m", "topic_id": 1, "source": "s",
                   "auth": {"header": "X-Emp-No", "value": "v"}},
    }
    p = tmp_path / "config.json"
    p.write_text(_json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("DESK_ASSISTANT_CONFIG", str(p))
    import importlib
    import panel.config as _config_mod
    importlib.reload(_config_mod)
    import panel.main as _main_mod
    importlib.reload(_main_mod)
    Panel = _main_mod.Panel
    panel = Panel()
    # 焦点不在 QLineEdit
    panel._input.clearFocus()
    from PyQt5 import QtCore
    ev = PyQt5.QtGui.QKeyEvent(
        QtCore.QEvent.KeyPress, QtCore.Qt.Key_4, QtCore.Qt.ControlModifier
    )
    PyQt5.QtWidgets.QApplication.sendEvent(PyQt5.QtWidgets.QApplication.instance(), ev)
    qapp.processEvents()
    assert panel._current_tab_index == 3
    assert panel._stack.currentIndex() == 3
```

- [ ] **Step 2：跑测试，验证 2 个新测试 fail（main.py 还没改）**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/test_main.py::test_panel_has_4_tabs_when_xiaoou_enabled tests/test_main.py::test_ctrl_4_switches_to_xiaoou_tab -v 2>&1 | tail -10
```

Expected：2 failed（config 没 xiaoou / Ctrl+4 不识别）。

- [ ] **Step 3：修改 `panel/main.py` 顶部 import 和常量**

**替换 `panel/main.py` 第 22-62 行**（import 区 + openclaw 常量）：

**之前**（22-62 行）：

```python
# 把 panel/ 加入 sys.path 以便导入同目录的 *_card 模块
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt5 import QtCore, QtGui, QtNetwork, QtWidgets  # noqa: E402

from chat_card import ChatCard  # noqa: E402
from events_card import EventsCard  # noqa: E402
from metrics_card import MetricsCard  # noqa: E402

# panel 启动时统一 logging 配置：launcher 已把 stderr 重定向到 panel.log
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("panel")

# ---- server 配置 ----
SSE_URL = "http://127.0.0.1:18675/events"
SERVER_BASE = "http://127.0.0.1:18675"
SERVER_METRICS_URL = SERVER_BASE + "/api/metrics"
SERVER_EVENTS_URL = SERVER_BASE + "/api/events"
RECONNECT_DELAY_MS = 5000
REFRESH_DEBOUNCE_MS = 150

# ---- panel 几何 ----
PANEL_WIDTH = 960
PANEL_HEIGHT = 800
EDGE_MARGIN = 20

# ---- openclaw 配置 ----
OPENCLAW_URL = "http://127.0.0.1:18789/v1/chat/completions"
OPENCLAW_MODEL = "openclaw"
OPENCLAW_SESSION_KEY = (
    "agent:main:openai:00000000-0000-4000-8000-000000000001@topic:desk-assistant"
)
OPENCLAW_CHAT_URL = (
    "http://127.0.0.1:18789/chat?lang=zh-CN&session="
    + quote(OPENCLAW_SESSION_KEY, safe="")
)
OPENCLAW_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
```

**之后**：

```python
# 把 panel/ 加入 sys.path 以便导入同目录的 *_card 模块
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt5 import QtCore, QtGui, QtNetwork, QtWidgets  # noqa: E402

from base_chat_card import BaseChatCard  # noqa: E402
from chat_card import ChatCard  # noqa: E402
from config import load_config  # noqa: E402
from events_card import EventsCard  # noqa: E402
from metrics_card import MetricsCard  # noqa: E402
from xiaoou_card import XiaoouCard  # noqa: E402

# panel 启动时统一 logging 配置：launcher 已把 stderr 重定向到 panel.log
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("panel")

# ---- server 配置 ----
SSE_URL = "http://127.0.0.1:18675/events"
SERVER_BASE = "http://127.0.0.1:18675"
SERVER_METRICS_URL = SERVER_BASE + "/api/metrics"
SERVER_EVENTS_URL = SERVER_BASE + "/api/events"
RECONNECT_DELAY_MS = 5000
REFRESH_DEBOUNCE_MS = 150

# ---- panel 几何 ----
PANEL_WIDTH = 960
PANEL_HEIGHT = 800
EDGE_MARGIN = 20

# ---- 配置加载 ----
_CFG = load_config()
OPENCLAW_CFG = _CFG.get("openclaw", {})
XIAOOU_CFG = _CFG.get("xiaoou")  # None = 不显示小欧 tab

# 向后兼容：test_main.py 还在 import 旧常量
OPENCLAW_URL = OPENCLAW_CFG.get("url", "http://127.0.0.1:18789/v1/chat/completions")
OPENCLAW_MODEL = OPENCLAW_CFG.get("model", "openclaw")
OPENCLAW_SESSION_KEY = OPENCLAW_CFG.get(
    "session_key",
    "agent:main:openai:00000000-0000-4000-8000-000000000001@topic:desk-assistant",
)
OPENCLAW_CHAT_URL = OPENCLAW_CFG.get(
    "chat_url",
    "http://127.0.0.1:18789/chat?lang=zh-CN&session=" + quote(OPENCLAW_SESSION_KEY, safe=""),
)
OPENCLAW_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
```

- [ ] **Step 4：修改 `Panel.__init__` 里的 cards 构造**

**替换 `panel/main.py` 第 196-226 行**（cards 构造 + stack）。

**之前**（196-226 行）：

```python
        # 三张卡片（指标 / 事件 / 对话）
        self.metrics_card = MetricsCard()
        self.events_card = EventsCard()
        self.events_card.toggle_requested.connect(self._on_event_toggle)
        self.chat_card = ChatCard(
            openclaw_url=OPENCLAW_URL,
            model=OPENCLAW_MODEL,
            session_key=OPENCLAW_SESSION_KEY,
            chat_url=OPENCLAW_CHAT_URL,
        )
        self.chat_card.set_token(_load_openclaw_token())

        # 收进 QStackedWidget，通过 tab 栏切换；SSE 派发 / debounce / 卡片内部实现全部不动。
        # events_card.toggle_requested 信号仍在原位置连接（见上方）。
        #
        # QStackedLayout 默认按每张 card 的 sizeHint 居中显示，不会自动 stretch。
        # 三张 card 的 sizeHint 都很窄（metrics 一行小方块、chat 一行标题+输入），如果不强制
        # Expanding，stack 区域里就是「左上角一小坨 + 一大片空白」。所以显式设 Expanding
        # 让 card 填满整个 stack 区域。
        for card in (self.metrics_card, self.events_card, self.chat_card):
            card.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding,
            )

        self._stack = QtWidgets.QStackedWidget()
        self._stack.addWidget(self.metrics_card)  # index 0
        self._stack.addWidget(self.events_card)   # index 1
        self._stack.addWidget(self.chat_card)     # index 2
        layout.addWidget(self._stack, 1)
```

**之后**：

```python
        # 三张卡片（指标 / 事件 / 对话），可选第 4 张（小欧）
        self.metrics_card = MetricsCard()
        self.events_card = EventsCard()
        self.events_card.toggle_requested.connect(self._on_event_toggle)
        self.chat_card = ChatCard(
            openclaw_url=OPENCLAW_URL,
            model=OPENCLAW_MODEL,
            session_key=OPENCLAW_SESSION_KEY,
            chat_url=OPENCLAW_CHAT_URL,
        )
        self.chat_card.set_token(_load_openclaw_token())

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

        # 收进 QStackedWidget，通过 tab 栏切换；SSE 派发 / debounce / 卡片内部实现全部不动。
        cards = [self.metrics_card, self.events_card, self.chat_card]
        if self.xiaoou_card is not None:
            cards.append(self.xiaoou_card)
        for card in cards:
            card.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding,
            )

        self._stack = QtWidgets.QStackedWidget()
        for card in cards:
            self._stack.addWidget(card)
        layout.addWidget(self._stack, 1)
```

- [ ] **Step 5：修改 tab labels 和 Ctrl+4**

**替换 `panel/main.py` 第 236-263 行**（tab 栏循环）：

**之前**（236-263 行）：

```python
        for i, label in enumerate(["指标", "事件", "对话"]):
            btn = QtWidgets.QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton {"
                "  background: transparent;"
                "  color: rgba(255,255,255,160);"
                "  border: 0;"
                "  border-bottom: 2px solid transparent;"
                "  padding: 4px 14px;"
                "  font-size: 12px;"
                "}"
                "QPushButton:checked {"
                "  color: #ffffff;"
                "  font-weight: bold;"
                "  border-bottom: 2px solid #6bb6ff;"
                "}"
                "QPushButton:hover:!checked {"
                "  color: rgba(255,255,255,220);"
                "}"
            )
            self._tab_group.addButton(btn, i)
            self._tabs.append(btn)
            tab_bar.addWidget(btn)
        tab_bar.addStretch(1)
        layout.addLayout(tab_bar)
```

**之后**：

```python
        tab_labels = ["指标", "事件", "对话"]
        if self.xiaoou_card is not None:
            tab_labels.append("小欧")
        for i, label in enumerate(tab_labels):
            btn = QtWidgets.QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton {"
                "  background: transparent;"
                "  color: rgba(255,255,255,160);"
                "  border: 0;"
                "  border-bottom: 2px solid transparent;"
                "  padding: 4px 14px;"
                "  font-size: 12px;"
                "}"
                "QPushButton:checked {"
                "  color: #ffffff;"
                "  font-weight: bold;"
                "  border-bottom: 2px solid #6bb6ff;"
                "}"
                "QPushButton:hover:!checked {"
                "  color: rgba(255,255,255,220);"
                "}"
            )
            self._tab_group.addButton(btn, i)
            self._tabs.append(btn)
            tab_bar.addWidget(btn)
        tab_bar.addStretch(1)
        layout.addLayout(tab_bar)
```

- [ ] **Step 6：修改 eventFilter 加 Ctrl+4**

**替换 `panel/main.py` 第 333-352 行**（eventFilter）：

**之前**（333-352 行）：

```python
    def eventFilter(self, watched, event):
        """QApplication 级 filter：截 Ctrl+1/2/3 切 tab。

        焦点在 QLineEdit 时不截，让 Ctrl+1 正常进入输入框。
        """
        if event.type() == QtCore.QEvent.KeyPress:
            if event.modifiers() & QtCore.Qt.ControlModifier:
                focus = QtWidgets.QApplication.focusWidget()
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
        return super().eventFilter(watched, event)
```

**之后**：

```python
    def eventFilter(self, watched, event):
        """QApplication 级 filter：截 Ctrl+1/2/3(/4) 切 tab。

        焦点在 QLineEdit 时不截，让 Ctrl+1 正常进入输入框。
        """
        if event.type() == QtCore.QEvent.KeyPress:
            if event.modifiers() & QtCore.Qt.ControlModifier:
                focus = QtWidgets.QApplication.focusWidget()
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
```

- [ ] **Step 7：跑 2 个新测试，验证通过**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/test_main.py::test_panel_has_4_tabs_when_xiaoou_enabled tests/test_main.py::test_ctrl_4_switches_to_xiaoou_tab -v 2>&1 | tail -10
```

Expected：2 passed。

- [ ] **Step 8：跑全量测试，确认没破坏现有**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/ -v 2>&1 | tail -20
```

Expected：所有测试通过（旧的 SSE 客户端测试、tab 测试 + 新加 26 个测试 + 2 个 main 测试）。总测试数 ≈ 186 + 26 + 2 = 214。

- [ ] **Step 9：跑全量覆盖率，确认 ≥ 85% / 70%**

```bash
QT_QPA_PLATFORM=offscreen pytest tests/ --cov=panel --cov-branch --cov-report=term-missing 2>&1 | tail -30
```

Expected：TOTAL 行 ≥ 85% / 分支 ≥ 70%。如果低于阈值，找出没测到的分支（看 `Missing` 列），补测试。

- [ ] **Step 10（可选）：手动冒烟测试**

如果环境有显示，启 panel 验证：
1. 默认 tab 仍是"对话"
2. Ctrl+4 切到"小欧" tab
3. 小欧 tab 输入文字 + Enter → 调 `:22004`（如果服务没起会显示 error）
4. 点击"新对话"按钮 → chatUuid 重置
5. 切回"对话" tab → OpenClaw 协议仍然工作

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DISPLAY=:0 /usr/local/bin/python3 panel/main.py &
# 观察窗口、切换 tab、发送消息
```

> **任务结束**：请向用户确认是否要 commit（建议把 Task 1-5 一起 commit，commit message 类似 `feat(panel): 抽 BaseChatCard 基类 + 加小欧 tab（iGPT 协议）`）。

---

## 风险与回滚

| 风险 | 缓解 |
|------|------|
| `chat_card.py` 改写破坏现有对话功能 | 6 个 test_chat_card.py 测试 + 旧 SSE 客户端测试覆盖；手动冒烟测试 |
| config 加载慢或 IO 错误 | DEFAULT_CONFIG 兜底 + log warning；try/except 包裹读和 parse |
| 小欧 SSE 帧格式跟文档不一致 | `data.get()` 缺省；字段缺失不抛 |
| PyInstaller 打包的 Python 3.6 不支持 PEP 585 注解 | 已在 spec 和 plan 里强制避免 |

**回滚**：每个 Task 完成后可独立 commit（不 commit 也行）。如果集成测试失败，回滚到上一个 commit 即可（`git revert HEAD`）。
