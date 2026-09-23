# 小欧对话 Tab 设计

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 panel 加第 4 个 tab「小欧」，对接团队 igptproxy 服务（iGPT 私有协议），与现有 OpenClaw「对话」tab 并列。

**Architecture:** 抽 `BaseChatCard` 基类承担 UI/生命周期/网络框架；`ChatCard`（OpenClaw 协议）和 `XiaoouCard`（小欧协议）继承基类，各实现 3 个虚方法（body 构造 / SSE 帧解析 / auth header）。配置全部走 `data/config.json`，env var `DESK_ASSISTANT_CONFIG` 可覆盖路径。

**Tech Stack:** Python 3.6 + PyQt5 5.13 + QtNetwork + stdlib `json`/`uuid`/`pathlib`。无新依赖。

---

## 1. 背景与目标

### 1.1 现状
- Panel 当前有 3 个 tab：指标 / 事件 / 对话。Ctrl+1/2/3 切换。
- 「对话」tab 调 OpenClaw Gateway `:18789/v1/chat/completions`，用 `Authorization: Bearer <token>` + `x-openclaw-session-key` 头部，按 OpenAI 协议跑 SSE 流。
- 团队有个公开的「小欧」chat 服务，部署在 `10.90.30.228:22004`（igptproxy），走 **iGPT 私有协议**（`POST /`，SSE 帧是 `{"chatUuid":..., "result":"<增量>"}`）。

### 1.2 目标
- 加第 4 个 tab「小欧」，与「对话」并列。
- 配置全部走 `data/config.json` 可改，**不需要碰代码**。
- 现有功能（指标 / 事件 / 对话）零行为变化。
- 覆盖率维持 **行 ≥ 85% / 分支 ≥ 70%**。

### 1.3 非目标
- 不做流式断点续传（断线重连 → 整流重发）
- 不做多会话切换（一个 tab 一个 session，UI 加"新对话"按钮重置）
- 不做安全策略 UI（被拦截时整段 label 替换为提示）
- 不做指数退避重试
- 不引入 yaml / pydantic / httpx

---

## 2. 架构

### 2.1 模块依赖图

```
panel/main.py
  ├─ MetricsCard        (不动)
  ├─ EventsCard         (不动)
  ├─ ChatCard           (BaseChatCard 子类，OpenClaw 协议)
  ├─ XiaoouCard         (BaseChatCard 子类，小欧协议)
  └─ config.load_config (新增)
            ↑
   panel/base_chat_card.py
            ↑
   panel/chat_card.py / panel/xiaoou_card.py

panel/data/config.json  ←→  配置文件
```

### 2.2 UI 布局

```
┌─ 桌面助手 · <timestamp> ─  ● connected ─┐
│                                         │
│   QStackedWidget（4 张卡片）            │
│     index 0: MetricsCard                │
│     index 1: EventsCard                 │
│     index 2: ChatCard (OpenClaw)        │
│     index 3: XiaoouCard (小欧)          │
│                                         │
├─────────────────────────────────────────┤
│  [ 指标 ][ 事件 ][ 对话 ][ 小欧 ]        │   Ctrl+1/2/3/4
└─────────────────────────────────────────┘
```

「对话」tab 默认选中（沿用现状）；「小欧」tab 可由用户 Ctrl+4 切过去。

---

## 3. 组件

### 3.1 `panel/base_chat_card.py`（新增，~180 行）

抽出现有 `chat_card.py` 里的 UI 装配 + 生命周期（输入 → POST → SSE 流 → 回显）。

**类签名**：

```python
class BaseChatCard(QtWidgets.QFrame):
    """chat 类卡片基类。
    
    子类必须实现：
      _build_request_body(text) -> dict
      _parse_sse_frame(data) -> str | None         # None = 跳过
      _auth_headers() -> [(bytes, bytes), ...]     # raw header 名值对列表
    
    子类可重写：
      _input_placeholder() -> str
      _format_error(err, status, body_bytes) -> str
      _build_button_row() -> QHBoxLayout           # 默认只放"新对话"按钮
      _reset_session()                              # "新对话"时子类 hook
    
    注意：避免使用 PEP 585 注解（list[T] / tuple[T]），生产 PyInstaller 打包用 Python 3.6。
    """
    
    REPLY_LINES_VIEW = 10
    REPLY_LINES_KEEP = 500
    LINE_PX = 18
```

**职责**：
- 装配 UI：title label + 滚动 QScrollArea 包 reply QLabel + 输入行（input + 子类的额外按钮）
- 持有 `QNetworkAccessManager` / `_reply` / `_sse_buf` / `_acc` 状态
- `_on_send()`：trim → abort 旧 reply → 清状态 → 调子类 `_build_request_body` / `_auth_headers` → 发 POST
- `_on_data()`：SSE 帧循环 → 调子类 `_parse_sse_frame` → 累加 / 截断 / setText / scroll
- `_on_done()`：错误 → log + 调子类 `_format_error` 显示 / 成功 → 静默
- `_on_new_conversation()`：abort → 清状态 → 调子类 `_reset_session()` → 清 UI

**关键不变量**：
- 基类不感知任何协议字段名（不出现 `choices` / `result` / `delta` / `Authorization` / `Bearer`）
- 不并发发送（`_on_send` 第一步 abort 旧 reply）
- SSE 帧循环逻辑（找 `\n\n`、split `\n`、`data:` 前缀、`[DONE]` 跳过、JSON 解析失败跳过）跟现 `chat_card.py` 一致

### 3.2 `panel/chat_card.py`（改写，~70 行）

`ChatCard` 继承 `BaseChatCard`，重写 3 个虚方法 + 1 个 button row + 1 个"打开 web UI"槽。

**构造参数**（从 config 传入，保留兼容）：
```python
ChatCard(openclaw_url, model, session_key, chat_url, parent=None)
```

**实现**：

```python
def _build_request_body(self, text):
    return {
        "model": self._model,
        "messages": [{"role": "user", "content": text}],
        "stream": True,
    }

def _parse_sse_frame(self, data):
    return data.get("choices", [{}])[0].get("delta", {}).get("content")

def _auth_headers(self):
    return [(b"Authorization", f"Bearer {self._token}".encode()),
            (b"x-openclaw-session-key", self._session_key.encode())]

def _build_button_row(self):  # 重写：加"↗ 打开 web UI"按钮
    # 跟现在 chat_card.py 一样
    ...
    
def _on_open_chat(self):
    QtGui.QDesktopServices.openUrl(QtCore.QUrl(self._chat_url))

def _reset_session(self):  # 不重写 = no-op，OpenClaw 不用 chatUuid
    pass
```

**保留行为**：
- `set_token(token=None)`：启用/禁用输入框，None 时 placeholder 切到"未找到 openclaw token…"
- 跟 `_open_chat_btn` 的样式 / 行为完全一致

### 3.3 `panel/xiaoou_card.py`（新增，~90 行）

`XiaoouCard` 继承 `BaseChatCard`，实现小欧协议。

**构造参数**：
```python
XiaoouCard(base_url, model, topic_id, source, auth_header, parent=None)
# auth_header: (bytes, bytes)  e.g. (b"X-Emp-No", b"10312862")
```

**实现**：

```python
def __init__(self, base_url, model, topic_id, source, auth_header, parent=None):
    self._url = base_url
    self._model = model
    self._topic_id = topic_id
    self._source = source
    self._auth_header = auth_header
    self._chat_uuid = str(uuid.uuid4())
    self._last_biz_error = None
    self._safety_blocked = False
    super().__init__(parent)

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
    code = data.get("code")
    if isinstance(code, dict) and code.get("code") and code.get("code") != "0000":
        self._last_biz_error = code.get("msg", "未知错误")
    result = data.get("result") or ""
    if "检测到高危指令" in result or "安全策略拦截" in result:
        self._safety_blocked = True
    return result if result else None

def _auth_headers(self):
    return [self._auth_header]

def _input_placeholder(self):
    return "发送给 小欧（Enter 发送）…"

def _format_error(self, err, status, body):
    body_str = body.decode("utf-8", errors="replace")[:200]
    if status:
        return f"✕ error: status={status} {body_str}".strip()
    return f"✕ error: {body_str}".strip()

def _on_done(self):  # 重写：业务错误 / 安全拦截 优先
    if self._safety_blocked:
        self._reply_label.setText("🛡 请求被安全策略拦截")
    elif self._last_biz_error:
        self._reply_label.setText(f"✕ {self._last_biz_error}")
    super()._on_done()

def _reset_session(self):
    self._chat_uuid = str(uuid.uuid4())
    self._last_biz_error = None
    self._safety_blocked = False
```

**关键不变量**：
- `_chat_uuid` 在 `__init__` 和 `_reset_session` 各生成一次（uuid4）
- 内存里，不写 SQLite，不持久化
- 业务错误 / 安全拦截 flag 在 `_on_send` 时清零（基类 hook 或子类重写 `_on_send` 第一步）

### 3.4 `panel/config.py`（新增，~50 行）

```python
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

# 用户配置路径（生产写 ~/.desk-assistant/，dev/测试用项目内 data/）
_USER_CONFIG = Path.home() / ".desk-assistant" / "config.json"
_DEV_CONFIG = Path(__file__).resolve().parent.parent / "data" / "config.json"

def _config_path():
    # 优先级：env > 用户 home > 项目 data/（dev/测试）
    env = os.environ.get("DESK_ASSISTANT_CONFIG")
    if env:
        return Path(env)
    if _USER_CONFIG.exists():
        return _USER_CONFIG
    return _DEV_CONFIG

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
    merged.update(user_cfg)  # 浅 merge：用户整个 xiaoou 块替换默认
    return merged
```

### 3.5 `panel/main.py`（改，~30 行新增）

**改 1**：`OPENCLAW_URL` 等顶层常量 → 从 config 读

```python
# 顶部删：
# OPENCLAW_URL = "http://127.0.0.1:18789/v1/chat/completions"
# OPENCLAW_MODEL = "openclaw"
# OPENCLAW_SESSION_KEY = "..."
# OPENCLAW_CHAT_URL = "..."

# 替换成：
from config import load_config
_CFG = load_config()
OPENCLAW_CFG = _CFG.get("openclaw", {})  # 兜底空 dict
XIAOOU_CFG = _CFG.get("xiaoou")          # None = 不显示小欧 tab
```

**改 2**：构造 4 张卡

```python
self.chat_card = ChatCard(
    openclaw_url=OPENCLAW_CFG["url"],
    model=OPENCLAW_CFG["model"],
    session_key=OPENCLAW_CFG["session_key"],
    chat_url=OPENCLAW_CFG["chat_url"],
)
self.chat_card.set_token(_load_openclaw_token())

self.xiaoou_card = None
if XIAOOU_CFG:  # 配置缺失就不显示
    self.xiaoou_card = XiaoouCard(
        base_url=XIAOOU_CFG["base_url"],
        model=XIAOOU_CFG["model"],
        topic_id=XIAOOU_CFG["topic_id"],
        source=XIAOOU_CFG["source"],
        auth_header=(XIAOOU_CFG["auth"]["header"].encode(),
                     XIAOOU_CFG["auth"]["value"].encode()),
    )
```

**改 3**：stack / tab 加第 4 项

```python
cards = [self.metrics_card, self.events_card, self.chat_card]
if self.xiaoou_card is not None:
    cards.append(self.xiaoou_card)
for card in cards:
    card.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                       QtWidgets.QSizePolicy.Expanding)

self._stack = QtWidgets.QStackedWidget()
for card in cards:
    self._stack.addWidget(card)
layout.addWidget(self._stack, 1)

labels = ["指标", "事件", "对话"]
if self.xiaoou_card is not None:
    labels.append("小欧")
# ... tab button loop 用 labels
```

**改 4**：`eventFilter` 加 Ctrl+4

```python
if key == QtCore.Qt.Key_4:
    self._set_tab(3)
    return True
```

**改 5**：默认 tab 仍为 2（对话），不动

---

## 4. 数据流

### 4.1 发送

```
[用户在 input 输入文字 + Enter]
    │
    ▼
BaseChatCard._on_send
    │ 1. text = self._input.text().strip()  ← 空 → return
    │ 2. if self._reply is not None: abort + deleteLater  ← 防叠加
    │ 3. 清 self._sse_buf / self._acc
    │ 4. self._reply_label.setText("…")
    │ 5. body = self._build_request_body(text)  ← 子类
    │ 6. headers = self._auth_headers()          ← 子类
    │
    ▼
QtNetwork.QNetworkRequest(QUrl(self._url))
    │ setHeader(ContentTypeHeader, "application/json")
    │ setRawHeader(Accept, "text/event-stream")
    │ for (k, v) in headers: setRawHeader(k, v)
    │
    ▼
self._nam.post(req, json.dumps(body).encode("utf-8"))
    │ reply.readyRead → _on_data
    │ reply.finished → _on_done
```

### 4.2 接收 SSE

```
[服务器] → data: {...}\n\n

BaseChatCard._on_data
    │ 1. self._sse_buf.extend(reply.readAll())
    │ 2. while find b"\n\n":
    │       frame = buf[:idx]; del buf[:idx+2]
    │       for raw in frame.split(b"\n"):
    │           if not raw.startswith(b"data:"): continue
    │           data = raw[5:].lstrip().decode(...)
    │           if not data or data == "[DONE]": continue
    │           obj = json.loads(data)
    │       delta = self._parse_sse_frame(obj)  ← 子类
    │       if delta:
    │           self._acc += delta
    │           truncate to REPLY_LINES_KEEP lines
    │           self._reply_label.setText(display)
    │           singleShot(0, _scroll_to_bottom)
```

子类 `_parse_sse_frame` 行为对比：

| 子类 | 输入 data | 返回 |
|------|-----------|------|
| ChatCard | `{"choices": [{"delta": {"content": "你"}}]}` | `"你"` |
| ChatCard | `{"choices": [{"delta": {}}]}` | `None` |
| XiaoouCard | `{"result": "你", "finishReason": ""}` | `"你"` |
| XiaoouCard | `{"result": "", "finishReason": "stop"}` | `None`（结束帧，跳过） |
| XiaoouCard | `{"result": "检测到高危指令..."}` | 文本 + 置 `_safety_blocked = True` |
| XiaoouCard | `{"result": "...", "code": {"code": "500", "msg": "..."}}` | 文本 + 置 `_last_biz_error` |

### 4.3 完成

```
BaseChatCard._on_done
    │ if reply.error() != NoError:
    │     log.warning(err=%s status=%s body=%r, ...)
    │     label.setText(self._format_error(err, status, body))  ← 子类
    │ reply.deleteLater(); self._reply = None
    │ self._sse_buf.clear()
```

XiaoouCard 重写 `_on_done`：业务错误 / 安全拦截 flag 优先显示，再调 super。

### 4.4 「新对话」

```
[用户点击"新对话"按钮]
    │
    ▼
BaseChatCard._on_new_conversation
    │ 1. if self._reply: abort + deleteLater
    │ 2. 清 _sse_buf / _acc
    │ 3. self._reset_session()  ← XiaoouCard 重写 = 新 uuid + 清 flag
    │                          ← ChatCard 不重写 = pass
    │ 4. _reply_label.setText(""); _input.setText(""); _input.setFocus()
```

---

## 5. 配置

### 5.1 文件位置

优先级（高 → 低）：
1. 环境变量 `DESK_ASSISTANT_CONFIG`（绝对路径）
2. `~/.desk-assistant/config.json`（生产；用户可手写覆盖）
3. `desk-assistant/data/config.json`（dev/测试；项目内可写）

### 5.2 完整默认配置

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

### 5.3 加载行为

- 文件不存在 → log info + 用默认（正常运行）
- 文件存在但 JSON 坏 → log warning + 用默认
- 文件顶层不是 dict → log warning + 用默认
- 文件合法 → 浅 merge：用户整个 `xiaoou` 块覆盖默认（不深 merge；用户要改 `auth.header` 必须把整个 `auth` 块都写）

### 5.4 可选块

如果用户 config.json 里没有 `xiaoou` 段：
- `cfg.get("xiaoou")` → `None`
- panel 不显示小欧 tab（tab 数量回到 3，Ctrl+4 仍是 noop）
- 旧配置文件 0 破坏

---

## 6. 错误处理

### 6.1 错误分类与显示

| 来源 | 触发 | ChatCard 显示 | XiaoouCard 显示 |
|------|------|---------------|-----------------|
| 网络不可达 | `:22004` 没监听 | `✕ error` | `✕ error <body前200字符>` |
| HTTP 4xx/5xx | 401/403/404/429/5xx | `✕ error: status=403` | `✕ error: status=403 <body>` |
| 业务错误 | SSE 帧含 `code.code != 0000` | (不会发生) | `✕ <msg>`（流结束后显示） |
| 安全拦截 | result 含 "检测到高危指令" | (不会发生) | `🛡 请求被安全策略拦截` |
| SSE JSON 坏 | `json.loads` 抛 | 跳过该帧 | 跳过该帧 |
| 超时 | 120s（OpenClaw 端限制） | `✕ error: status=0` | `✕ error: status=0` |

### 6.2 处理策略

- **基类统一处理网络/HTTP 错误**：log warning + 调子类 `_format_error` 显示
- **XiaoouCard 重写 `_format_error`**：status 后面接 body 前 200 字符（小欧错误消息常在 body）
- **业务错误 / 安全拦截**：不中断流，置 flag；`_on_done` 时根据 flag 替换 label
- **JSON 解析失败**：跳过该帧（沿用现有策略，log warning）
- **SSE 帧不闭合**：buffer 住，等下一帧到达

### 6.3 不做的事

- ❌ 指数退避重试
- ❌ 熔断
- ❌ 流式进度条
- ❌ 错误码 i18n
- ❌ 启动期预检：`:22004` 不通也不报错，等用户发送

---

## 7. 测试

### 7.1 目标

- 覆盖率：行 ≥ 85% / 分支 ≥ 70%（与现状持平）
- 增量 ~26 个测试

### 7.2 测试文件改动

| 文件 | 改动 | 测试数 |
|------|------|--------|
| `tests/test_chat_card.py` | 重写：只测 OpenClaw 协议解析（基类逻辑移到 base 测试） | 6 |
| `tests/test_base_chat_card.py` | 新增：基类 UI/生命周期/网络框架 | 12 |
| `tests/test_xiaoou_card.py` | 新增：小欧协议 body / auth / SSE 解析 | 7 |
| `tests/test_config.py` | 新增：config 加载语义 | 5 |
| `tests/test_main.py` | +2：4 个 tab + Ctrl+4 | +2 |
| `tests/test_events_card.py` | 不动 | 0 |
| `tests/test_metrics_card.py` | 不动 | 0 |

### 7.3 关键测试用例

**`test_base_chat_card.py`**（基类）：
- `test_init_assembles_widgets` —— title / input / reply_label / 新对话按钮都在
- `test_send_empty_returns`
- `test_send_aborts_previous_reply`
- `test_send_calls_subclass_build_request_body`
- `test_send_attaches_subclass_auth_headers`（用 monkeypatch 截 `_nam.post`，断言 request 里出现子类 header）
- `test_on_data_calls_subclass_parse_sse_frame`
- `test_on_data_subclass_returns_none_skips_frame`
- `test_on_data_accumulates_and_truncates`
- `test_on_done_no_error_clears_state`
- `test_on_done_error_uses_subclass_format_error`
- `test_on_new_conversation_resets_session_and_clears_ui`
- `test_new_conversation_aborts_in_flight_reply`

**`test_chat_card.py`**（OpenClaw 协议）：
- `test_build_request_body_has_openai_shape`
- `test_parse_sse_frame_extracts_delta_content`
- `test_parse_sse_frame_missing_delta_returns_none`
- `test_auth_headers_include_bearer_and_session_key`
- `test_set_token_enables_input`
- `test_set_token_empty_keeps_disabled`

**`test_xiaoou_card.py`**（小欧协议）：
- `test_init_uses_config`
- `test_build_request_body_has_required_fields`（chatUuid / topicId / source / keep / stream / text / model）
- `test_build_request_body_chatUuid_is_uuid_string`
- `test_auth_headers_returns_configured_header`（X-Emp-No）
- `test_parse_sse_frame_extracts_result`
- `test_parse_sse_frame_skips_stop_marker`
- `test_parse_sse_frame_marks_safety_block`

**`test_config.py`**：
- `test_load_default_when_file_missing`
- `test_load_default_when_file_bad_json`
- `test_load_default_when_file_not_dict`
- `test_user_config_overrides_defaults`
- `test_user_partial_xiaoou_block_fully_replaces_default`

**`test_main.py`** 增量：
- `test_panel_has_4_tabs`
- `test_ctrl_4_switches_to_xiaoou_tab`

### 7.4 测试基类用 mock 子类

```python
class _MockSubclass(BaseChatCard):
    def __init__(self, parent=None):
        self.build_calls = []
        self.parse_calls = []
        super().__init__(parent)
    
    def _build_request_body(self, text):
        self.build_calls.append(text)
        return {"text": text, "_marker": "mock"}
    
    def _parse_sse_frame(self, data):
        self.parse_calls.append(data)
        return data.get("delta")
    
    def _auth_headers(self):
        return [(b"X-Test", b"1")]
```

基类测试只断言：
- mock 方法被调过 / 调了几次 / 传了什么参数
- 用 monkeypatch 截 `_nam.post` 验 request body 实际 content

### 7.5 覆盖率预估

| 模块 | 行数 | 旧覆盖率 | 新增测试 | 新覆盖率 |
|------|------|----------|----------|----------|
| base_chat_card.py | 180 | n/a | 12 | ~92% |
| chat_card.py | 70 | 90% | 6 | ~88% |
| xiaoou_card.py | 90 | n/a | 7 | ~95% |
| config.py | 50 | n/a | 5 | ~85% |
| main.py (+30) | +30 | 92% | +2 | ~90% |

**总行/分支预估：90% / 88%**（基类逻辑集中测，覆盖率不降反升）。

### 7.6 不测的

- ❌ 真实 HTTP（igptproxy 启动与否依赖环境）
- ❌ Qt 事件循环手动 pump
- ❌ config.json 文件 IO 错误（OSError 被 except 兜住）
- ❌ 多线程
- ❌ Unicode 边界（沿用现有覆盖度）

---

## 8. 风险与回归

### 8.1 风险

| 风险 | 缓解 |
|------|------|
| `chat_card.py` 重写导致基类逻辑测试盲区 | `test_base_chat_card.py` 12 个测试覆盖基类每条路径 |
| 基类抽象过度，调试 stack 多一跳 | 虚方法就 3 个，命名直白 |
| `data/config.json` 路径硬编码 | 支持 `DESK_ASSISTANT_CONFIG` env var 覆盖 |
| 小欧 SSE 帧格式跟文档不一致 | 字段都 `data.get(...)` 缺省，容错好 |
| `_on_done` 重写时漏调 `super` | 写测试断言 reply 状态正确清理 |

### 8.2 回归点

- `test_events_card.py` / `test_metrics_card.py` / `test_sse_client.py` 0 改动 → 旧功能零回归
- `test_main.py` 旧 7 个 tab 测试不动 → 旧 tab 行为零变化
- `panel/main.py` 改 4 处（顶部常量 / 构造 4 卡 / tab+stack / eventFilter）→ 都有测试覆盖

---

## 9. 实施步骤（高层）

1. **Task 1**：`panel/base_chat_card.py` + `tests/test_base_chat_card.py`（基类 + 12 测试）
2. **Task 2**：`panel/chat_card.py` 重写为 BaseChatCard 子类 + 缩减 `tests/test_chat_card.py`
3. **Task 3**：`panel/xiaoou_card.py` + `tests/test_xiaoou_card.py`
4. **Task 4**：`panel/config.py` + `data/config.json` + `tests/test_config.py`
5. **Task 5**：`panel/main.py` 改：config 加载 + 4 张卡 + Ctrl+4
6. **Task 6**：`tests/test_main.py` +2 + 跑全量 + 覆盖率

---

## 10. 后续可能扩展（**不做**，仅留位）

- 多 session 切换：UI 加"会话列表"
- 配置多 auth 类型：`auth.type` 区分 `X-Emp-No` / `appCode+secretKey`
- 模型选择器：UI 加下拉
- 小欧 SSE 帧重排序 / 去重
- 集成 ASR 语音输入
