# 桌面助手贴边悬浮（Edge Dock）设计

- 日期：2026-06-13
- 状态：✅ 已交付（v3 Edge Dock 落地，commit `4379164`）
- 范围：`panel/` 目录全模块拆分 + 双窗口改造；`server/`、`*_card.py`、构建脚本不动

> **v3.1 变更（2026-06-15）**：UI 反馈后去掉了 HotZoneWatcher。展开/折叠完全靠 strip 按钮（toggle）+ panel › 按钮触发，不再有"鼠标贴右自动展开"。本 spec 中所有 HotZoneWatcher / 热区 / `hover_right_edge` 信号相关章节已被实际实现超越，仅作设计过程参考。`panel/hotzone.py` 和 `tests/test_hotzone.py` 在实施时已被删除。

## 背景

桌面助手目前是 `panel/main.py` 启动的一个 960×800 透明浮窗，常驻在桌面背景层（`WindowStaysOnBottomHint`），需要用户主动回到桌面才能看到、用到。

用户反馈：背景上用起来不方便，「必须回到桌面」是核心痛点。诉求：
1. 平时只露出一个窄条贴在屏幕右边，存在感低
2. 鼠标贴近屏幕右边缘自动展开完整面板
3. 或点击窄条展开
4. 面板上能手动收起回到窄条

参考：电脑管家的双窗口结构（`SMBMainWidget 37×75` 贴边条 + `SysMonitorBall/主面板` 完整看板）。

## 目标

1. 启动后只看到窄条（37×75，贴右居中），完整面板默认隐藏
2. 鼠标进入屏幕右边缘 6-8px 隐形热区 → 面板从右滑入（200ms）
3. 点击窄条本身 → 面板从右滑入（200ms）
4. 点面板左侧 ◀ 按钮 → 面板滑出收回（200ms），回到窄条状态
5. 点面板右上 ✕（保留现状）→ 退出整个 app
6. 共享同一 SSEClient，窄条状态点实时反映 SSE 连接态（绿/红）

## 非目标

- 不实现多屏独立贴条（每屏一条），v1 默认主屏，但允许窄条拖到副屏
- 不实现「自动记忆展开/收起状态」——启动总是收起状态
- 不改 960×800 面板尺寸
- 不改 SSE / REST / debounce 任何链路
- 不改 `MetricsCard` / `EventsCard` / `ChatCard` / `XiaoouCard` 任何实现
- 不动 server / 构建脚本 / autostart

## 设计

### 架构

```
panel/main.py（缩成启动壳子，约 30 行）
  └── WindowManager（panel/window_manager.py，新文件）
       ├── Strip（panel/strip.py，新文件，37×75，WindowStaysOnTopHint）
       ├── PanelWindow（panel/panel_window.py，从 main.py 拆出，960×800）
       ├── HotZoneWatcher（panel/hotzone.py，新文件，50ms 轮询 QCursor.pos）
       └── SSEClient（panel/main.py 现有，单例）
            ├── sse_event → PanelWindow.on_sse_event（保持现有派发逻辑）
            ├── connected → Strip.on_connected + PanelWindow.on_connected
            └── disconnected → Strip.on_disconnected + PanelWindow.on_disconnected
```

### 拆分原则

- `strip.py`：窄条 UI + 鼠标事件，**不持有业务数据**
- `hotzone.py`：只判断鼠标是否在热区内，emit 信号，**不关心谁响应**
- `window_manager.py`：连接器，把三个独立部件拼起来
- `panel_window.py`：面板 UI + SSE 派发 + tab + 卡片（从 main.py 拆出）
- `main.py`：只剩 `QApplication` 启动 + 创建 `WindowManager`

### 文件改动表

| 文件 | 改动 |
|------|------|
| `panel/main.py` | 缩成 ~30 行启动壳子，构造 `WindowManager` 后 `app.exec_()` |
| `panel/panel_window.py`（新） | 从 main.py 拆出 `Panel` 类，重命名为 `PanelWindow`；新增 `collapse_btn`（◀ 左侧）、`_slide_in()`、`_slide_out()`、`_cancel_anim_if_running()`、`show_animated()`；构造时 **不调用** `self.show()` |
| `panel/strip.py`（新） | `Strip` 类，37×75，`WindowStaysOnTopHint` + `Tool` + `FramelessWindowHint` + `WA_TranslucentBackground`；自绘圆角矩形 + 图标 + 状态点；emit `show_requested`；鼠标拖动 + 屏外吸附 |
| `panel/hotzone.py`（新） | `HotZoneWatcher(QObject)`，50ms `QTimer` 轮询 `QCursor.pos()`；emit `hover_right_edge`；parent 销毁时 timer 自动停 |
| `panel/window_manager.py`（新） | `WindowManager(QObject)`，构造三个部件 + 单例 `SSEClient` + 连信号 |

### 窗口标志与 Z-Order

**Strip**：
```python
self.setWindowFlags(
    QtCore.Qt.FramelessWindowHint
    | QtCore.Qt.WindowStaysOnTopHint   # 永远在最前
    | QtCore.Qt.Tool                    # 不进任务栏
)
self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
```

**PanelWindow**（相对现有改动）：
```python
self.setWindowFlags(
    QtCore.Qt.FramelessWindowHint
    | QtCore.Qt.Tool                # 不进任务栏
    # 删除 WindowStaysOnBottomHint
)
self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
self.hide()                        # 启动默认隐藏
```

**Z-Order 行为表**：

| 时刻 | Strip | Panel |
|------|-------|-------|
| 启动后 | 显示在最右、垂直居中 | 隐藏 |
| 鼠标进入右 6-8px 热区 | 保持显示 | 滑入（raise_ + activateWindow + slide_in） |
| 点 Strip | 保持显示 | 滑入 |
| 鼠标点浏览器等外部窗口 | 保持显示（on top） | 被外部窗口盖住（正常 z-order） |
| 鼠标再回到 Strip | 保持显示 | 滑入 |
| 点 Panel 左侧 ◀ | 保持显示 | hide()（slide_out 动画完成后） |
| 点 Panel 右上 ✕ | 退出整个 app | 退出整个 app |

### 数据流（SSE / REST 共享）

```
SSEClient（单例，由 WindowManager 创建）
   │
   ├─► Strip.on_connected / on_disconnected  ─► 状态点颜色（绿/红）
   │
   └─► PanelWindow.on_sse_event（保留现有逻辑）
          ├─ hello           ─► 强制刷新 metrics + events
          ├─ metrics.changed ─► 150ms debounce → REST
          └─ events.changed  ─► 150ms debounce → REST
```

**SSEClient 单例化**：`WindowManager.__init__` 里只 new 一次，引用传给 Strip 和 Panel。Strip/Panel **不持有所有权**，避免重复 `start()`。

**Strip 状态点**：
```python
def on_connected(self):
    self._status_dot.setStyleSheet("background: #77ff77;")  # 绿
def on_disconnected(self):
    self._status_dot.setStyleSheet("background: #ff7777;")  # 红
```

**Panel hide/show 时的数据策略**：
- Panel hide 时 SSE 长连接保持，cards 内存数据继续更新（不渲染）
- Panel show 时 `show_animated()` 内部强制 `_refresh_metrics()` + `_refresh_events()`，不等 debounce，保证打开就是最新

### 交互时序

**启动**：
```
main() → QApplication 启动 → WindowManager 构造
  → Strip 创建并 show（37×75，贴右居中）
  → PanelWindow 创建（构造时不 show）
  → HotZoneWatcher 创建（启动 50ms 轮询）
  → SSEClient 创建 + start()
→ app.exec_()
```

**悬停热区**：
```
HotZoneWatcher 50ms 轮询发现 QCursor.pos().x() > screen.right() - 8
  → emit hover_right_edge
  → WindowManager 接收 → PanelWindow.show_animated()
     → _refresh_metrics() / _refresh_events() 强制刷一次
     → _slide_in() 200ms QPropertyAnimation 从右滑入
  → panel.show() / raise_() / activateWindow()
```

**点 Strip**：emit `show_requested` → WindowManager → PanelWindow.show_animated()（同上）

**点 ◀ 收起**：
```
PanelWindow._on_collapse_clicked
  → emit collapse_requested
  → WindowManager 接收 → panel._slide_out()
     → QPropertyAnimation 200ms 反向滑出
     → animation.finished → panel.hide()
  → SSE 不停，cards 内存数据继续更新
```

**点 ✕ 退出**：`QtWidgets.QApplication.quit()` → app 退出，Strip 跟随消失；server 进程独立运行不退出

**拖 Strip 到副屏**：
```
mousePressEvent 记录 _drag_offset
mouseMoveEvent 移动窗口（Qt 自动跨屏调整）
mouseReleaseEvent
  → QApplication.screenAt(self.pos()) 检测
  → 若为 None（屏外）→ _reposition_to_right_edge() 吸附回主屏右边缘
```

**屏分辨率变化**：
```
QScreen.geometryChanged
  → WindowManager._on_screen_changed
     → Strip._reposition_to_right_edge
     → PanelWindow.isVisible() 时 _reposition_to_right_edge
```

### 动画实现

```python
# panel_window.py
SLIDE_DURATION_MS = 200
SLIDE_EASING = QtCore.QEasingCurve.OutCubic
EDGE_MARGIN = 20
```

**Slide In**：
```python
def _slide_in(self):
    self._cancel_anim_if_running()
    screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
    final_x = screen.x() + screen.width() - self.width() - EDGE_MARGIN
    final_y = screen.y() + (screen.height() - self.height()) // 2
    off_screen_x = screen.x() + screen.width() + 1

    self.move(off_screen_x, final_y)
    self.show()
    self.raise_()
    self.activateWindow()

    self._anim = QtCore.QPropertyAnimation(self, b"pos", self)
    self._anim.setDuration(SLIDE_DURATION_MS)
    self._anim.setEasingCurve(SLIDE_EASING)
    self._anim.setStartValue(QtCore.QPoint(off_screen_x, final_y))
    self._anim.setEndValue(QtCore.QPoint(final_x, final_y))
    self._anim.start()
```

**Slide Out**：
```python
def _slide_out(self):
    self._cancel_anim_if_running()
    screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
    current = self.pos()
    off_screen_x = screen.x() + screen.width() + 1

    self._anim = QtCore.QPropertyAnimation(self, b"pos", self)
    self._anim.setDuration(SLIDE_DURATION_MS)
    self._anim.setEasingCurve(SLIDE_EASING)
    self._anim.setStartValue(current)
    self._anim.setEndValue(QtCore.QPoint(off_screen_x, current.y()))
    self._anim.finished.connect(self.hide)
    self._anim.start()
```

**动画衔接**：每次入口先 `_cancel_anim_if_running()`，避免动画叠加。

**关键约束**：
- 不使用 `QGraphicsBlurEffect` 等特效，PyQt5 5.13.1 + 部分 X11 驱动上性能差且偶发崩溃
- 窗口保持 `FramelessWindowHint`，动画期间无标题栏闪烁

### 错误处理

| 场景 | 行为 |
|------|------|
| SSE 断开 | 5s 重连；Strip 红点；Panel 状态栏「○ reconnecting…」 |
| REST 失败 | 已有 warning 日志 + 状态栏「✕ xxx error」（保留现状） |
| 屏分辨率变化 | Strip + Panel 重新定位；动画中遇到变化则 stop + 重定位 |
| 鼠标在副屏右边缘 | **不支持**（v1 写在 Future Work） |
| 拖 Strip 到屏外 | 释放时 `screenAt(pos) is None` → 吸附回主屏右边缘 |
| Panel 构造失败 | `WindowManager.__init__` try/except → `QMessageBox.critical` + `app.exit(1)` |
| 动画中途被打断 | `_cancel_anim_if_running()` 衔接 |
| ✕ 在动画中按 | 立即退出，动画/计时器随进程回收 |
| 启动时屏分辨率无效 | `_reposition_to_right_edge` 检查 `screen.width() <= 0` → log warning + 跳过 |

统一用现有 `log = logging.getLogger("panel")`，不引入新 logger。

### 测试策略

**现有测试基建（不动）**：
- `test.sh` 一键：`QT_QPA_PLATFORM=offscreen` + 行覆盖 ≥85% / 分支 ≥70%
- pytest + coverage，覆盖目标 `server,panel`
- `DESK_ASSISTANT_DB=state_test.db` 隔离

**新增测试文件**：
| 文件 | 覆盖范围 |
|------|---------|
| `tests/test_strip.py` | strip.py：渲染、状态点、鼠标事件、拖动、屏外吸附 |
| `tests/test_hotzone.py` | hotzone.py：50ms 轮询、热区内/外 emit、不在 screen 内不 emit |
| `tests/test_panel_window.py` | panel_window.py：hide/show、slide_in/out、collapse、动画衔接、屏变化重定位、SSE 派发零回归 |
| `tests/test_window_manager.py` | window_manager.py：三部件创建顺序、SSEClient 单例化、信号连接 |

**动画测试原则**：
- 不测帧（offscreen 帧时长不稳，强测会 flaky）
- 测终点：`qtbot.wait(SLIDE_DURATION_MS + 50)` 等结束后断言最终位置/hidden
- 测衔接：连发 show_animated → collapse，断言最后一次 pos 是收起状态
- 测 cancel：slide_in 期间手动 `anim.stop()` → 立即 _slide_out，断言衔接

**覆盖率目标**：保持现有 **行 ≥85% / 分支 ≥70%** 门禁。新增 4 文件，净增 ~400 行代码 + ~800 行测试。

**验收门槛**（提 PR 前）：
```bash
bash test.sh                                  # 默认阈值
DISPLAY=:0 /usr/bin/python3 panel/main.py     # 真机手动跑一遍
```

人工真机验收清单：
- [ ] 启动只看到窄条
- [ ] 鼠标贴右 6-8px → 面板滑入
- [ ] 点窄条 → 面板滑入
- [ ] 面板左侧 ◀ → 面板滑出
- [ ] 面板右上 ✕ → app 退出
- [ ] SSE 断 → 状态点变红
- [ ] SSE 重连 → 状态点变绿
- [ ] 拖窄条到副屏 → 跟着过去

### 风险与决策记录

| 决策 | 原因 |
|------|------|
| 单进程双窗口（方案 A），不做双进程 | 跟电脑管家参考一致；改动局部；复用现有 SSE 客户端和 debounce |
| Panel 去掉 `WindowStaysOnBottomHint` | 它现在是按需弹出而不是常驻沉底；`raise_()` + `activateWindow()` 解决置顶 |
| Panel hide 时 SSE 不停 | 保持数据最新，show 时强制 refresh 一次 |
| 不记忆展开/收起状态 | 用户偏好：启动总是收起 |
| 隐形热区用 QTimer 轮询而非 EventFilter | 简单稳；PyQt5 5.13.1 + X11 全局鼠标 hook 兼容性差 |
| 多屏先只支持主屏 + 窄条可拖跨屏 | v1 简化范围；每屏一条放 Future Work |

## Future Work（明确不做）

- 多屏独立贴条（每屏右边各一条）
- 展开/收起状态持久化
- 拖动时实时显示窗口阴影
- 智能延迟收起（hover out 后等 1s 再收）
- 通知角标（窄条上有数字徽标）
- 圆形悬浮球变体（替代窄条）

## 实施顺序（指导 writing-plans）

1. `panel/strip.py` + `tests/test_strip.py`（最独立）
2. `panel/hotzone.py` + `tests/test_hotzone.py`
3. `panel/panel_window.py` 从 main.py 拆出 + `tests/test_panel_window.py`
4. `panel/window_manager.py` + `tests/test_window_manager.py`
5. `panel/main.py` 缩成启动壳子
6. 整体真机验收清单走一遍
7. `bash test.sh` 通过 + 提 PR