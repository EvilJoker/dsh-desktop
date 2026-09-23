# Panel Tab 化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把桌面助手 panel 从「三卡垂直堆叠」改为「tab 栏 + QStackedWidget」布局，三张 card 收进 stack，添加 Ctrl+1/2/3 快捷键。

**Architecture:** 在 `Panel.__init__` 中把 3 个 card 的 `addWidget` 替换为 `QStackedWidget`，新增 `QButtonGroup` 互斥的 3 个 `QPushButton` 作为 tab，用 `installEventFilter` 拦截 Ctrl+1/2/3 切 tab。SSE 派发、debounce、3 张 card 内部实现、信号连接全部保持原样。

**Tech Stack:** Python 3.6.8 + PyQt5 5.13.1 + pytest 7.0.1 + coverage 4.5.1

---

## 文件结构

| 路径 | 角色 | 操作 |
|---|---|---|
| `desk-assistant/panel/main.py` | Panel 类，承载 tab 栏 + QStackedWidget + eventFilter | 修改 |
| `desk-assistant/tests/test_main.py` | Panel/SSEClient 单元测试，追加 6 个 tab 用例 | 修改 |

不创建新文件；不修改 `panel/metrics_card.py`、`panel/events_card.py`、`panel/chat_card.py`、其他 `tests/test_*.py`。

---

## Task 1: QStackedWidget + tab 栏 + 默认选中 chat

**Files:**
- Modify: `desk-assistant/tests/test_main.py:append` —— 追加 `test_panel_tab_default_is_chat`
- Modify: `desk-assistant/panel/main.py:198-212` —— 把 3 个 `addWidget` 替换为 `QStackedWidget` + tab 栏初始化

- [ ] **Step 1.1: 写失败测试**

追加到 `desk-assistant/tests/test_main.py` 末尾：

```python
# ---- Panel tab 切换 ----


def test_panel_tab_default_is_chat(qapp):
    """__init__ 后默认选中「对话」tab（index 2）。"""
    p = Panel()
    # 数据态
    assert p._current_tab_index == 2
    # 视觉态：QStackedWidget 显示 chat card
    assert p._stack.currentIndex() == 2
    # 视觉态：chat tab button checked
    assert p._tabs[2].isChecked()
    # 其他 tab button 未选中
    assert not p._tabs[0].isChecked()
    assert not p._tabs[1].isChecked()
```

- [ ] **Step 1.2: 跑测试确认失败**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_main.py::test_panel_tab_default_is_chat -v
```

Expected: FAIL，错误是 `AttributeError: 'Panel' object has no attribute '_stack'`（或 `_tabs` / `_current_tab_index`）。

- [ ] **Step 1.3: 修改 `Panel.__init__`，把 3 个 card 收进 QStackedWidget 并加 tab 栏**

定位到 `desk-assistant/panel/main.py` 第 197-212 行（"三张卡片（指标 / 事件 / 对话）"注释开始到 `layout.addWidget(self.chat_card)`），**整段替换**为：

```python
        # 三张卡片（指标 / 事件 / 对话）收进 QStackedWidget，
        # 通过 tab 栏切换；SSE 派发 / debounce / 卡片内部实现全部不动。
        # events_card.toggle_requested 信号仍在原位置连接（见下方 _on_event_toggle）。
        self._stack = QtWidgets.QStackedWidget()
        self._stack.addWidget(self.metrics_card)  # index 0
        self._stack.addWidget(self.events_card)   # index 1
        self._stack.addWidget(self.chat_card)     # index 2
        layout.addWidget(self._stack, 1)

        # tab 栏：3 个 QPushButton（checkable + 互斥）+ 透明背景
        self._tab_group = QtWidgets.QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self._tab_group.buttonClicked[int].connect(self._set_tab)
        self._tabs = []
        tab_bar = QtWidgets.QHBoxLayout()
        tab_bar.setContentsMargins(0, 0, 0, 0)
        tab_bar.setSpacing(0)
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

**重要**：以上替换是「新增」QStackedWidget + tab 栏。events_card 的 `toggle_requested.connect` 仍在替换前的那段（`self.events_card.toggle_requested.connect(self._on_event_toggle)`）— 保持不动，**不要删**。

- [ ] **Step 1.4: 在 `__init__` 末尾追加初始状态设置**

定位到 `desk-assistant/panel/main.py` 现有 `__init__` 末尾（最后一个 `self._refresh_events_timer = QtCore.QTimer(self)` 块结束后，方法最后一个语句之后）。在 `def __init__(self):` 方法的最后（`self._refresh_events_timer.timeout.connect(self._refresh_events)` 之后）追加：

```python

        # 初始状态：chat 选中（必须在 tab_bar 创建后、eventFilter 安装前）
        self._tabs[2].setChecked(True)
        self._stack.setCurrentIndex(2)
        self._current_tab_index = 2
```

- [ ] **Step 1.5: 跑测试确认通过**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_main.py::test_panel_tab_default_is_chat -v
```

Expected: PASS。

- [ ] **Step 1.6: 跑回归测试，确保现有 30+ 个 case 不挂**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/ -q --tb=short
```

Expected: 全部通过（之前 commit `5f47927` 已建立 30 个 case，应全绿）。

- [ ] **Step 1.7: 跑覆盖率，确认未掉**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
bash test.sh
```

Expected: 行覆盖率 ≥ 90%，分支覆盖率 ≥ 90%（略低于 85% / 70% 阈值，安全余量）。如果因 `Panel._set_tab` 尚未实现导致某个分支未覆盖，**记下具体行号**，Task 2 完成后会消除。

- [ ] **Step 1.8: Commit**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/panel/main.py desk-assistant/tests/test_main.py
git commit -m "feat(panel): 加 tab 栏 + QStackedWidget，默认选中对话 tab"
```

---

## Task 2: 实现 `_set_tab`（含越界和同 index 防御）

**Files:**
- Modify: `desk-assistant/tests/test_main.py:append` —— 追加 3 个用例
- Modify: `desk-assistant/panel/main.py:append method` —— 在 Panel 类里加 `_set_tab` 方法

- [ ] **Step 2.1: 写失败测试**

追加到 `desk-assistant/tests/test_main.py` 末尾：

```python
def test_panel_click_tab_switches(qapp):
    """模拟点击 events tab（index 1）→ stack + _current_tab_index 同步。"""
    p = Panel()
    # 触发 buttonClicked[0]（模拟点击「指标」tab）
    p._tab_group.buttonClicked[int].emit(0)
    assert p._current_tab_index == 0
    assert p._stack.currentIndex() == 0
    assert p._tabs[0].isChecked()
    assert not p._tabs[2].isChecked()


def test_panel_set_tab_same_index_noop(qapp):
    """同 index 重复 _set_tab 不抛、不改状态。"""
    p = Panel()
    before_idx = p._current_tab_index
    p._set_tab(before_idx)
    assert p._current_tab_index == before_idx


def test_panel_set_tab_out_of_range_noop(qapp):
    """越界 index 不抛、不改状态。"""
    p = Panel()
    before_idx = p._current_tab_index
    p._set_tab(99)
    p._set_tab(-1)
    assert p._current_tab_index == before_idx
```

- [ ] **Step 2.2: 跑测试确认失败**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest \
  tests/test_main.py::test_panel_click_tab_switches \
  tests/test_main.py::test_panel_set_tab_same_index_noop \
  tests/test_main.py::test_panel_set_tab_out_of_range_noop -v
```

Expected: 全部 FAIL，错误是 `AttributeError: 'Panel' object has no attribute '_set_tab'`。

- [ ] **Step 2.3: 在 Panel 类加 `_set_tab` 方法**

定位到 `desk-assistant/panel/main.py` 中 `on_sse_event` 方法前面（"SSE 事件分发"注释下）。在该注释行下方、`def on_sse_event(self, name, data):` 之前，插入：

```python
    def _set_tab(self, i: int):
        """切换 tab：bounds + 同 index 防御性 no-op。

        入口有两处：
        - 鼠标点击 tab button：QButtonGroup.buttonClicked → 此方法
        - Ctrl+1/2/3 快捷键：eventFilter → _set_tab_if_not_input → 此方法
        """
        if not 0 <= i < self._stack.count():
            return
        if i == self._current_tab_index:
            return
        self._current_tab_index = i
        self._stack.setCurrentIndex(i)
        self._tabs[i].setChecked(True)
```

- [ ] **Step 2.4: 跑测试确认通过**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest \
  tests/test_main.py::test_panel_click_tab_switches \
  tests/test_main.py::test_panel_set_tab_same_index_noop \
  tests/test_main.py::test_panel_set_tab_out_of_range_noop -v
```

Expected: 3 个全 PASS。

- [ ] **Step 2.5: 跑回归**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/ -q --tb=short
```

Expected: 全部通过。

- [ ] **Step 2.6: Commit**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/panel/main.py desk-assistant/tests/test_main.py
git commit -m "feat(panel): _set_tab 切换逻辑（越界 + 同 index 防御）"
```

---

## Task 3: Ctrl+1/2/3 快捷键（QApplication eventFilter）

**Files:**
- Modify: `desk-assistant/tests/test_main.py:append` —— 追加 2 个用例
- Modify: `desk-assistant/panel/main.py:append method + append init line` —— 加 `_set_tab_if_not_input` + `eventFilter`，在 `__init__` 末尾装 filter

- [ ] **Step 3.1: 写失败测试**

追加到 `desk-assistant/tests/test_main.py` 末尾：

```python
def test_panel_ctrl_shortcut_switches_when_no_input_focus(qapp):
    """焦点在非输入控件（close_btn）时调 _set_tab_if_not_input → 切 tab。"""
    p = Panel()
    p.close_btn.setFocus()
    assert p._current_tab_index == 2
    p._set_tab_if_not_input(0)  # 模拟 Ctrl+1
    assert p._current_tab_index == 0


def test_panel_ctrl_shortcut_noop_when_input_focused(qapp):
    """焦点在 chat_card._input 时 _set_tab_if_not_input → 不切 tab。"""
    p = Panel()
    p.chat_card._input.setFocus()
    assert p._current_tab_index == 2
    p._set_tab_if_not_input(0)  # 模拟 Ctrl+1
    assert p._current_tab_index == 2  # 没切走
```

- [ ] **Step 3.2: 跑测试确认失败**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest \
  tests/test_main.py::test_panel_ctrl_shortcut_switches_when_no_input_focus \
  tests/test_main.py::test_panel_ctrl_shortcut_noop_when_input_focused -v
```

Expected: 全部 FAIL，错误是 `AttributeError: 'Panel' object has no attribute '_set_tab_if_not_input'`。

- [ ] **Step 3.3: 在 Panel 类加 `_set_tab_if_not_input` 和 `eventFilter` 方法**

定位到 `desk-assistant/panel/main.py` 中 Task 2 加的 `_set_tab` 方法紧后面（紧跟其末尾空行后），插入：

```python
    def _set_tab_if_not_input(self, i: int):
        """eventFilter 调用：焦点在 QLineEdit 时让位，不切 tab。"""
        focus = QtWidgets.QApplication.focusWidget()
        if isinstance(focus, QtWidgets.QLineEdit):
            return
        self._set_tab(i)

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

- [ ] **Step 3.4: 在 `__init__` 末尾安装 eventFilter**

定位到 `desk-assistant/panel/main.py` 中 Task 1.4 加的初始状态块（`self._current_tab_index = 2` 那一行）**之后**追加：

```python

        # 快捷键：在 QApplication 装 filter，截 Ctrl+1/2/3 切 tab
        # 必须在所有 widget / _tabs / _stack 构造完成后安装，
        # 否则 init 期间收到的 KeyPress 会触发未就绪的 _set_tab。
        QtWidgets.QApplication.instance().installEventFilter(self)
```

- [ ] **Step 3.5: 跑测试确认通过**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest \
  tests/test_main.py::test_panel_ctrl_shortcut_switches_when_no_input_focus \
  tests/test_main.py::test_panel_ctrl_shortcut_noop_when_input_focused -v
```

Expected: 2 个全 PASS。

- [ ] **Step 3.6: 跑全套测试，确认零回归**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/ -q --tb=short
```

Expected: 全部通过（原 30+ 个 + 新增 6 个 = 36+ 个）。

- [ ] **Step 3.7: Commit**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/panel/main.py desk-assistant/tests/test_main.py
git commit -m "feat(panel): Ctrl+1/2/3 快捷键切 tab（焦点在 QLineEdit 时让位）"
```

---

## Task 4: 全量覆盖率验证 + 人工冒烟

**Files:**
- 不改代码，只跑测试和启动 panel 验证视觉

- [ ] **Step 4.1: 跑 `test.sh`，确认覆盖率门禁未掉**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
bash test.sh
```

Expected:
- `[1/4]` 全部测试通过
- `[2/4]` 行覆盖率 ≥ 85%（实际预期 90%+）
- `[3/4]` 分支覆盖率 ≥ 70%（实际预期 90%+）
- `[4/4]` 总结显示 `✓ OK 通过`

如果失败：找到未覆盖的具体行号，按需追加 case。

- [ ] **Step 4.2: 启动 panel 人工验证视觉**

```bash
# 1. 启 server
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state.db /usr/bin/python3 server/app.py &

# 2. 等 1s 让 server ready
sleep 1

# 3. 启 panel
DISPLAY=:0 /usr/bin/python3 panel/main.py &
```

观察：
- 面板显示在屏幕右侧
- 顶部标题行下方是 3 个 tab（指标 / 事件 / 对话），「对话」tab 有蓝色下划线
- 切到「指标」tab：显示横排小方块
- 切到「事件」tab：显示滚动列表
- 切回「对话」tab：显示流式回显区 + 输入框
- 在对话 tab 焦点下按 Ctrl+1/2/3：应正常输入 "1"/"2"/"3" 到输入框，**不切 tab**
- 在事件 tab 焦点下按 Ctrl+1：应切到指标 tab

- [ ] **Step 4.3: 停止 panel 和 server**

```bash
pkill -f "panel/main.py" || true
pkill -f "server/app.py" || true
```

- [ ] **Step 4.4: 验收清单**

确认以下项：
- [ ] 切 tab 不闪屏、不卡顿
- [ ] 切到 events tab 时列表已最新（不需等 SSE 触发）
- [ ] 切到 chat tab 时上一次 reply_label 完整保留
- [ ] 启动 30s 内状态条 / tab 渲染正常
- [ ] 焦点在 chat 输入框时 Ctrl+1/2/3 输入数字、不切 tab
- [ ] 焦点在其他位置时 Ctrl+1/2/3 切 tab

- [ ] **Step 4.5: 如有需要，最后整理 + 不再 commit（按用户习惯，commit 由用户决定）**

无需新 commit。如果 4.1 失败、调整了代码，参考前面 3 个 task 的 commit 模板单独 commit；如果只是验证观察，**不发 commit**。

---

## 自审

- **Spec 覆盖**：
  - 目标 1（QStackedWidget 包 3 卡 + tab 栏切换）→ Task 1 ✓
  - 目标 2（默认 chat）→ Task 1.4 ✓
  - 目标 3（不抖/不丢/不打断）→ Task 1.3 + 现有 SSE 不动 ✓
  - 目标 4（Ctrl+1/2/3 + 输入框让位）→ Task 3 ✓
  - 6 个新测试 → Task 1.1 + 2.1 + 3.1 ✓
  - 覆盖率门禁 → Task 4.1 ✓
  - 人工验证 → Task 4.2-4.4 ✓
  - 关键不变量（零回归）→ Task 1.6 + 2.5 + 3.6 反复验证 ✓

- **占位扫描**：无 TODO / TBD / 模糊描述；每步有具体代码 + 命令 + 预期输出。

- **类型一致性**：
  - `_current_tab_index` 在 Task 1.4 初始化为 `int`，Task 2 始终 `< self._stack.count()` ✓
  - `_tabs` 在 Task 1.3 构造为 `List[QPushButton]`，Task 1.4 / 2.3 都按此用 ✓
  - `_stack` 在 Task 1.3 构造为 `QStackedWidget`，Task 2.3 用 `.count()` / `.setCurrentIndex()` ✓
  - `_set_tab_if_not_input` 签名 `(self, i: int)` 在 Task 3.1 / 3.3 一致 ✓
  - `eventFilter` 签名 `(self, watched, event)` 符合 Qt 约定 ✓

- **方法名拼写**：`_set_tab` / `_set_tab_if_not_input` / `eventFilter` 全部一致；未出现 Task 3 写 `clearLayers` 之类命名漂移。
