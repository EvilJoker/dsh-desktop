# Panel Tab 化设计

- 日期：2026-06-09
- 状态：待用户复核
- 范围：仅 `panel/main.py`（Panel 类）；三张 `*_card.py` 不动

## 背景

桌面助手当前 `Panel` 用 `QVBoxLayout` 把三张卡（MetricsCard / EventsCard / ChatCard）垂直堆叠，窗口固定 960×800。用户反馈：chat 对话是最常用的入口，每次要点不到（不在堆叠顶部）；且三卡同时占着空间，事件列表和对话历史都嫌挤。

诉求：把面板改成 tab 页设计，最上方三个 tab 切换：指标 / 事件 / 对话。

## 目标

1. 把三张卡收进 `QStackedWidget`，通过顶部 tab 栏切换
2. 启动默认停在「对话」tab（用户最常用）
3. 切换 tab 不抖尺寸、不丢状态、不打断 SSE/chat 流
4. 增加键盘快捷键 `Ctrl+1/2/3` 直达三个 tab（焦点在 chat 输入框时让位）

## 非目标

- 不重做三张卡内部的视觉
- 不加 tab 角标/红点
- 不改面板整体几何（仍 960×800，位置不变）
- 不动 SSEClient、`on_sse_event`、debounce、REST 拉取、EventsCard.PATCH 链路
- 不拆 panel 子模块为多个文件

## 设计

### 架构

```
Panel (QWidget, 960×800)
├── header (QHBoxLayout)  ← 标题 + 状态（保留原样）
│
├── tab_bar (QWidget + QHBoxLayout)  ← 新增
│   ├── QPushButton "指标"  (checkable, group id=0)
│   ├── QPushButton "事件"  (checkable, group id=1)
│   ├── QPushButton "对话"  (checkable, group id=2, 默认选中)
│   └── addStretch(1)
│
└── QStackedWidget  ← 新增，包住 3 张 card
    ├── [0] MetricsCard
    ├── [1] EventsCard  (toggle_requested 仍连 Panel._on_event_toggle)
    └── [2] ChatCard    (set_token 仍调 _load_openclaw_token)
```

### 关键不变量（零回归约束）

- `SSEClient` 类、`sse_event`/`connected`/`disconnected` 信号 — 不动
- `Panel.on_sse_event` / `_refresh_metrics` / `_refresh_events` / debounce timer — 不动
- `Panel._on_metrics_reply` / `_on_events_reply` / `_on_event_toggle` / `_on_patch_reply` — 不动
- `MetricsCard` / `EventsCard` / `ChatCard` 的类实现 — 不动
- 关闭按钮、右键退出、左键拖动、`_reposition_to_right_edge` — 不动

### 新增代码（全部在 `Panel.__init__` 末尾 + 几个小方法）

```python
# 在 __init__ 中，原 self.metrics_card.addWidget(...) 替换为：
self._stack = QtWidgets.QStackedWidget()
self._stack.addWidget(self.metrics_card)  # 0
self._stack.addWidget(self.events_card)   # 1
self._stack.addWidget(self.chat_card)     # 2
layout.addWidget(self._stack, 1)

# tab 栏（与现有 header 一致：QHBoxLayout 直接 addLayout 到主 layout）
self._tab_group = QtWidgets.QButtonGroup(self)
self._tab_group.setExclusive(True)
self._tab_group.buttonClicked[int].connect(self._set_tab)
self._current_tab_index = 2  # 默认 chat
self._tabs = []
tab_bar = QtWidgets.QHBoxLayout()
tab_bar.setContentsMargins(0, 0, 0, 0)
tab_bar.setSpacing(0)
for i, label in enumerate(["指标", "事件", "对话"]):
    btn = QtWidgets.QPushButton(label)
    btn.setCheckable(True)
    btn.setFixedHeight(28)
    btn.setCursor(QtCore.Qt.PointingHandCursor)
    btn.setStyleSheet(...)  # 详见下文
    self._tab_group.addButton(btn, i)
    self._tabs.append(btn)
    tab_bar.addWidget(btn)
tab_bar.addStretch(1)
layout.addLayout(tab_bar)

# 快捷键（用 QApplication 级 eventFilter，而非 QShortcut；
#   这样焦点在 QLineEdit 时 Ctrl+1 不会被截获，能正常进入输入框）
QtWidgets.QApplication.instance().installEventFilter(self)

# 默认选中
self._tabs[2].setChecked(True)
```

```python
def _set_tab(self, i: int):
    if not 0 <= i < self._stack.count():
        return
    if i == self._current_tab_index:
        return
    self._current_tab_index = i
    self._stack.setCurrentIndex(i)
    self._tabs[i].setChecked(True)

def _set_tab_if_not_input(self, i: int):
    focus = QtWidgets.QApplication.focusWidget()
    if isinstance(focus, QtWidgets.QLineEdit):
        return  # 让 Ctrl+1 在输入框里走默认行为
    self._set_tab(i)

def eventFilter(self, watched, event):
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

### Tab 视觉

- 选中：白字 + 加粗 + 底部 2px 蓝线 `#6bb6ff`
- 未选：灰字 `rgba(255,255,255,160)`，hover 变 `rgba(255,255,255,220)`
- 背景透明，跟随面板半透明黑底
- 按钮高度 28px，左右 padding 14px

### 几何

总高 800 不变；分配：
- 标题行：~30px（不变）
- tab 栏：~30px（28 按钮 + 2 边距）
- 内容区（QStackedWidget）：~740px

每张 tab 拿到的内容高度都比现状对应卡的可用高度大（或持平），无挤压。

### 行为约定

| 场景 | 行为 |
|---|---|
| 启动 | 选中「对话」tab（`_current_tab_index = 2`） |
| 鼠标点击 tab | `buttonClicked[i]` → `_set_tab(i)` |
| Ctrl+1/2/3（焦点不在 QLineEdit） | `eventFilter` 截到 → `_set_tab(i)` |
| Ctrl+1/2/3（焦点在 QLineEdit） | eventFilter 不截，QLineEdit 收到 Ctrl+1（QKeyEvent 不被消费） |
| 切到 tab i，已是当前 i | no-op（不重渲染） |
| 切到非法 index | 防御性 no-op（不抛） |
| SSE 推送到达 | 数据进入对应的 card（即使 card 不可见），下次切到时已就绪 |
| ChatCard 正在流式回显 | 切走 tab 期间流继续、_acc 继续累加、_reply_label 继续更新；切回时完整呈现，无丢字 |
| EventsCard 用户勾选 | 走原 toggle_requested 链路 PATCH /api/events/<id>，不变 |
| openclaw token 缺失 | ChatCard 输入框禁用 + placeholder "未找到 openclaw token"，不变 |

### 错误处理

| 错误 | 处理 |
|---|---|
| `_set_tab` 越界 | if 防御 + return |
| `_set_tab_if_not_input` 焦点类型扩展 | 当前用 `isinstance(QLineEdit)`；未来添加新输入控件时需扩展白名单 |
| `eventFilter` 误吞其他 Ctrl+组合 | 仅在 key 是 Key_1/2/3 时返回 True 消费，其他 key 透传 |
| 切换 tab 过程中触发 SSE reply | 走原 `_on_metrics_reply`/`_on_events_reply`，对隐藏 card 调 `update_indicators`/`update_events` 是安全的（widget hide 也能更新内部数据） |
| Qt layout 异常 | 依赖 Qt 自身兜底 |

所有原有错误处理（SSE 断线、REST 失败、PATCH 失败、SSE 帧解析失败）保持不变。

## 测试

### 现有测试（回归保护，不动）

- `tests/test_main.py` —— SSEClient、Panel 事件派发、metrics/events reply
- `tests/test_chat_card.py` —— token 启用、SSE 解析、done 处理
- `tests/test_metrics_card.py` / `tests/test_events_card.py` —— 各 card 渲染

### 新增测试（追加到 `tests/test_main.py`，6 个）

| 用例 | 断言 |
|---|---|
| `test_panel_tab_default_is_chat` | `__init__` 后 `_current_tab_index == 2`，对应 button checked |
| `test_panel_click_tab_switches` | 模拟 `buttonClicked[0]` → `_current_tab_index == 0` + stack index 切到 0 |
| `test_panel_set_tab_same_index_noop` | 同 index 重复设不抛、不改状态 |
| `test_panel_set_tab_out_of_range_noop` | 99 / -1 不抛、不改状态 |
| `test_panel_ctrl_shortcut_switches_when_no_input_focus` | 焦点在 `close_btn` 时调 `_set_tab_if_not_input(0)` → 切到 0 |
| `test_panel_ctrl_shortcut_noop_when_input_focused` | 焦点在 `chat_card._input` 时调 → 不切 |

### 覆盖率预期

- 新加 tab 代码约 30 行
- 6 个新 case 覆盖：默认/点击/同 index/越界/快捷键非焦点/快捷键焦点
- 新代码行覆盖 ≥ 90%，分支覆盖 ≥ 75%
- 整体覆盖率（行 / 分支）不应下降
- `test.sh` 阈值保持 85% / 70%

### 人工验证（PR 描述 TODO）

- 切 tab 不闪屏、不卡顿
- 切到 events tab 时列表已最新（不需等 SSE 触发）
- 切到 chat tab 时上一次 reply_label 完整保留
- 启动 30s 内观察状态条 / tab 渲染是否正常
