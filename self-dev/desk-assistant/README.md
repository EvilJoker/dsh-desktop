# 桌面助手 (Desk Assistant)

云桌面常驻看板：一个半透明、贴边、沉到桌面背景层的 PyQt5 浮窗，实时展示指标 + 事件 + AI 对话。

```text
┌── 桌面助手 · 2026-06-04T10:00:00 ──── ● connected   ✕ ──┐
│                                                          │
│  ┌─ 指标 / METRICS ──────────────────────────────────┐  │
│  │  [77%]  [62%]  [12]                                │  │
│  │   CPU   内存   待办                                 │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ 事件 / EVENTS ───────────────────────────────────┐  │
│  │  ☐ 14:30  回复邮件                                  ▲ │
│  │  ☐ 14:45  提交 PR                                   ║ │
│  │  ☑ 12:15  ̶提̶交̶ ̶R̶F̶C̶ ̶                                 ▼ │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ 对话 / CHAT ─────────────────────────────────────┐  │
│  │  AI 流式回显（10 行视口 + 滚动）                    ▲ │
│  │                                                    ║ │
│  │                                                    ▼ │
│  │  [发送给 openclaw（Enter 发送）……]          [ ↗ ]  │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Edge Dock（v3）

启动后只看到右边缘一个 37×75 的窄条；鼠标贴右 6-8px 热区或点窄条可唤起完整面板；
面板左侧 ◀ 收起，右侧 ✕ 退出 app。三部件（Strip / PanelWindow / HotZoneWatcher）由
`window_manager.py` 拼装，共享同一个 SSEClient。

## 组件构成

| 组件 | 角色 | 协议 |
| ------ | ------ | ------ |
| **server** (Flask) | REST + SSE，SQLite 持久化 | HTTP CRUD + SSE 瘦事件推送 |
| **panel** (PyQt5) | 看板 UI，订阅 SSE + 调 REST 拉取 | SSE 客户端 + REST 拉取 + PATCH 回写 |
| **state.db** (SQLite) | 单一数据源（metrics + events 双表） | `~/.desk-assistant/state.db` |
| **openclaw gateway** | AI 后端（公司魔改） | OpenAI 兼容 `/v1/chat/completions` |

## 项目结构

```text
desk-assistant/
├── server/
│   ├── app.py            Flask + REST + SSE 服务端 (端口 18675)
│   ├── db.py             SQLite 连接 + schema + 索引 + 触发器
│   ├── metrics_store.py  metrics 表 CRUD
│   ├── events_store.py   events 表 CRUD + 过滤查询
│   └── sse_hub.py        SSE 订阅者管理 + 瘦事件广播
├── panel/
│   ├── main.py           启动壳子
│   ├── window_manager.py 拼装 Strip + PanelWindow + HotZoneWatcher，共享 SSEClient
│   ├── strip.py          右边缘 37×75 窄条（默认可见，可点击展开）
│   ├── panel_window.py   完整面板容器，从右滑入；◀ 收起，✕ 退出
│   ├── hotzone.py        6-8px 贴右热区，50ms 轮询鼠标
│   ├── metrics_card.py   指标横排小方块
│   ├── events_card.py    复选框+时间+name，可滚动，最多显示 100 条
│   ├── chat_card.py      openclaw 流式回显 + 输入框 + 打开 web UI
│   ├── base_chat_card.py  ChatCard 抽取的 base 类（4 个 tab 共用）
│   └── xiaoou_card.py    小欧对话 tab
├── assets/
│   └── hamster.svg       应用图标（仓鼠）
└── script/
    ├── build.sh          PyInstaller 编译 → dist/
    ├── install.sh        build + 部署 + autostart + 桌面图标
    ├── uninstall.sh      反向清理（--purge 删数据）
    └── desk-assistant_run.sh  start/stop/restart/status
```

## 系统要求

- Linux X11（已验证：NewStartOS V4.4.2-ZTE / Nde 桌面）
- Python 3.6.8+（系统自带）
- 系统包：`PyQt5` 5.13.1+、`flask`、`pyinstaller`
- 可选：openclaw gateway 监听 `127.0.0.1:18789`（用于对话）

## 快速开始

### 部署（生产）

```bash
cd desk-assistant
bash script/install.sh             # 编译 + 部署 + 配开机自启
desk-assistant_run.sh start        # 立即启动
desk-assistant_run.sh status       # 查看状态
```

部署后产物：

```text
~/.desk-assistant/
├── bin/{desk-assistant-server, desk-assistant-panel}   # 单文件可执行
├── logs/{server.log, panel.log}                         # 运行日志
├── icon.svg                                             # 应用图标
└── state.db                                             # SQLite 数据（首次启动自动建表）

/usr/local/bin/desk-assistant_run.sh                     # launcher（需 sudo）
~/.config/autostart/desk-assistant-{server,panel}.desktop # 开机自启
~/.local/share/applications/desk-assistant.desktop        # 应用菜单
~/Desktop/desk-assistant.desktop                          # 桌面快捷方式
```

### 调试（开发）

直接跑 Python 源码，跳过 2 分钟的 PyInstaller 编译：

```bash
# 终端 1：起 server（用 python3.6 绝对路径，绕开 alternatives 软链）
/usr/bin/python3.6 server/app.py

# 终端 2：起 panel
DISPLAY=:0 /usr/bin/python3.6 panel/main.py
```

## uv 依赖管理

项目用 uv 项目化（`pyproject.toml` + `uv.lock` + `.venv` + `.python-version`），用于**开发时**隔离 build-time 依赖。运行时仍走 `/usr/bin/python3.6` + user site，**与 uv 无关**。

**Python 版本精确锁**：`pyproject.toml` 里 `requires-python = "==3.6.8"`（不写范围），`uv.lock` 同步锁定。升级到 3.6.9/3.7+ 会让 `uv lock` 立即失败，避免误用未调过的版本。

### 两层环境

| 环境 | 谁用 | 装的包 | 谁装 |
| --- | --- | --- | --- |
| `~/.local/lib/python3.6/site-packages/`（user site） | 运行时 `/usr/bin/python3.6`（精确路径，绕开 alternatives 软链） | PyQt5 5.15.6、PyQt5-sip、sip、flask、requests、pyinstaller 4.10、pyinstaller-hooks-contrib 2022.0 | 历史手动装（`/usr/bin/python3.6 -m pip install --user`） |
| `.venv/` | `pyproject.toml` + `uv.lock` 声明的 build-time 隔离环境 | pyinstaller 4.10 + hooks-contrib 2022.0 + 5 个传递依赖 | `uv sync --extra build` |

### 首次 clone

```bash
cd desk-assistant
uv sync --extra build       # 创 .venv/ + 生成 uv.lock（不重装 user site 包）
```

### 跨机器复现

```bash
git clone <repo>
cd desk-assistant
uv sync --frozen --extra build      # 严格按 uv.lock 还原
```

### 改依赖

```bash
vim pyproject.toml          # 改 [project.optional-dependencies] build = [...] 里的版本
uv lock                     # 更新 uv.lock
uv sync --extra build       # 同步 .venv/
```

### PyQt5 ABI 修复

PyQt5==5.15.6 源码编译产物（链接系统 Qt 5.12.5）装到 user site，不进 venv。
`uv sync` **不会**重装 PyQt5（`dependencies = []` 显式不管理），ABI 不会破坏。
一次性环境准备，详见 `docs/pyqt5-abi-fix.md`。

## launcher 命令

```bash
desk-assistant_run.sh start      # 启动（已运行则跳过）
desk-assistant_run.sh stop       # 停止
desk-assistant_run.sh restart    # 重启
desk-assistant_run.sh status     # 状态 + 端口 + 窗口
```

启动幂等：多次 start 不会重复启动进程。

## HTTP API

详见 [docs/api.md](../docs/api.md)（完整规范）。简要：

### Metrics（只存最新值）

```bash
GET    /api/metrics              # 所有指标（按 position,id 排序）
PUT    /api/metrics/<id>         # 创建或覆盖；body {label,value,unit?,type?,position?}
DELETE /api/metrics/<id>         # 删除（不存在返 404）
```

### Events（积累式，1w 上限自动滚动）

```bash
GET    /api/events                                   # 默认过滤：未处理 OR 已完成未过期，最多 200 条
GET    /api/events?all=true&limit=N&offset=M         # 全量分页
POST   /api/events                                   # 创建；body {name, type?, description?, content?, source?, external_id?, expire_seconds?}
PATCH  /api/events/<id>                              # {done: bool}；done=true 自动补 completed_at
DELETE /api/events/<id>                              # 删除
```

`external_id` 幂等：相同值已存在则返回现有，不重复插入。错误响应统一 `{"error": "..."}` 配 400/404/500。

### SSE（瘦事件）

```bash
GET /events
# event: hello              data: {"protocol":1}
# event: metrics.changed    data: {"id":"cpu"}
# event: events.changed     data: {"reason":"insert|update|delete","id":123}
# 心跳：每 15s 一行 ": keepalive\n\n"
```

客户端收到通知后**自己调 REST 拉数据**，避免在 SSE 通道里塞完整列表撑爆推送。

### 示例：cron 写入

```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "name": "回邮件",
  "type": "todo",
  "description": "周报相关",
  "source": "cron",
  "external_id": "task-001"
}' http://127.0.0.1:18675/api/events
```

## 数据 Schema

详见 [docs/metrics_events_数据库设计.md](../docs/metrics_events_数据库设计.md) 第 2 节。

`events` 表关键字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER PK | 数据库主键 |
| `external_id` | TEXT UNIQUE | 写入方幂等键，可选 |
| `type` | TEXT | "todo" / "alert" / "reminder" / ... |
| `name` | TEXT NOT NULL | 主标题（列表显示） |
| `description` | TEXT | 一句话补充（可选） |
| `content` | TEXT | 详细内容（可长） |
| `done` | 0/1 | 完成状态 |
| `completed_at` | ISO8601 | done=1 时自动写入 |
| `expire_seconds` | INTEGER | 完成后保留秒数，默认 6h |

### 进度条颜色

`type: "progress"` 的指标按值上色：< 70 绿 / 70–90 黄 / ≥ 90 红。

### 事件保留策略

- 未完成：永久显示
- 已完成（`done && completed_at`）：完成时间起 6 小时内显示（灰色 + 删除线），6 小时后自动隐藏
- 取消勾选会清除 `completed_at`，回到未完成

## openclaw 集成

panel 底部输入框走 openclaw gateway 的 OpenAI 兼容接口（`POST /v1/chat/completions` + `x-openclaw-session-key`）。所有消息固定进入 session `desk-assistant`。

点击右侧 `↗` 按钮在浏览器打开同一 session 的完整对话页。

**前置条件**：`~/.openclaw/openclaw.json` 的 `gateway` 段含：

```jsonc
{
  "gateway": {
    "port": 18789,
    "auth": { "mode": "token", "token": "..." },
    "http": { "endpoints": { "chatCompletions": { "enabled": true } } }
  }
}
```

启动 panel 时自动读取 token；缺失时输入框禁用。

## 卸载

```bash
bash script/uninstall.sh           # 保留 ~/.desk-assistant/ 数据
bash script/uninstall.sh --purge   # 连数据一起删
```

## 关键技术决策

| 决策 | 理由 |
| ------ | ------ |
| PyQt5 而非 Electron | NewStartOS 系统已预装；二进制小（71MB vs 200MB+） |
| Flask + SSE 而非 WebSocket | 协议简单；curl 可调试；零额外依赖 |
| PyInstaller `--onefile` | 单文件部署，无运行时依赖 |
| 数据放 `~/.desk-assistant/` | 用户级，跨进程共享，无需 root |
| launcher 在 `/usr/local/bin/` | 全局可用，但二进制留在用户目录 |
| `--paths panel --hidden-import *_card` | panel/main.py 用 `sys.path.insert()` 动态注入，PyInstaller 静态分析跟不到 |
| `clicked` 而非 `stateChanged` | 避免 SSE 重渲染 → setChecked → 信号 → POST 死循环 |
| `_parse_iso()` 兼容 Python 3.6 | `datetime.fromisoformat()` 是 3.7+ API |

## 详细文档

- [透明面板实现方案](../docs/透明面板实现方案.md) — 调研「云电脑管家」+ 选型 + 关键技术点
