---
purpose: 项目 AI 记忆上下文
maintainer: AI assistant
last_updated: 2026-06-04 17:55:00
---

# Project: 桌面助手
- ID: 0284decf-138b-43a6-a569-c963f285de02
- 创建时间: 2026-04-22 14:07:06
- 当前版本: v2（数据库化架构，2026-06 切换）

## 项目描述
云桌面常驻看板：一个半透明、贴边、沉到桌面背景层的 PyQt5 浮窗，三张卡片展示系统指标 + 事件清单 + openclaw AI 对话流。后端 Flask + SQLite，前端 PyQt5，通过 SSE 推送瘦事件 + REST 拉取数据。

## 上下文
- **技术栈**: Python 3.6.8 / Flask / SQLite (WAL) / PyQt5 5.13.1 / PyInstaller
- **组件**: server (Flask REST+SSE) + panel (PyQt5 看板) + state.db (SQLite) + openclaw gateway
- **端口**: server 监听 127.0.0.1:18675；openclaw 默认 127.0.0.1:18789
- **数据源**: `~/.desk-assistant/state.db` 双表（metrics 最新值 + events 滚动 1w）
- **实时**: SSE 瘦事件（`metrics.changed` / `events.changed`）+ 客户端 REST 拉取 + 150ms debounce
- **部署**: PyInstaller `--onefile` 打 server(16M) + panel(71M) 二进制；launcher 在 `/usr/local/bin/`；autostart 桌面项

## 文件结构
```
desk-assistant/
├── server/
│   ├── app.py            Flask + REST + SSE 服务端
│   ├── db.py             SQLite 连接 + schema + 索引 + 触发器
│   ├── metrics_store.py  metrics 表 CRUD
│   ├── events_store.py   events 表 CRUD + 过滤查询
│   └── sse_hub.py        SSE 订阅者管理 + 瘦事件广播
├── panel/
│   ├── main.py           启动壳子（QApplication → WindowManager → exec_）
│   ├── window_manager.py 拼装 Strip + PanelWindow + 单例 SSEClient，5 种/7 receivers
│   ├── strip.py          右下角 37×75 窄条（默认可见，toggle 按钮）
│   ├── panel_window.py   完整面板容器，从右滑入；› 收起，✕ 退出
│   ├── sse_client.py     最小 SSE 长连接客户端（buffer/reconnect/5s 重试）
│   ├── config.py         加载 config.json + chat 协议常量 + load_openclaw_token
│   ├── metrics_card.py   指标横排小方块
│   ├── events_card.py    复选框+时间+name，可滚动
│   ├── chat_card.py      openclaw 流式回显 + 输入框
│   ├── base_chat_card.py  ChatCard 抽取的 base 类（4 个 tab 共用）
│   └── xiaoou_card.py    小欧对话 tab
├── assets/hamster.svg    应用图标
└── script/
    ├── build.sh          PyInstaller 编译
    ├── install.sh        build + 部署 + autostart + 桌面图标
    ├── uninstall.sh      反向清理
    └── desk-assistant_run.sh  start/stop/restart/status
```

## 关键决策
- **从 v1 升级到 v2（2026-06）**：放弃 state.json 全量快照，改 SQLite 双表 + SSE 瘦事件；解决 1w 事件全量推送导致的延迟
- **v3 Edge Dock（2026-06）**：把 Panel 从单窗口常驻拆成 Strip+PanelWindow 双窗口；Panel 默认隐藏，靠 QPropertyAnimation 从右滑入
- **v3.1（2026-06）**：去 Tool 标志（Wayland 失焦自隐）+ slide_out 改 pos+windowOpacity 并行动画（WA_TranslucentBackground 下 setMask 被 compositor 忽略）+ 移除 HotZoneWatcher（strip 改 toggle 按钮）+ EDGE_MARGIN=0 贴右 + 抽出 SSEClient/sse_client.py 和 config.py 解耦
- **PyQt5 源码编译（2026-06-18）**：放弃 wheel，源码编译 PyQt5 5.15.6 链接到系统 Qt 5.12.5（`/lib64/libQt5*.so.5.12.5`），彻底解决 wheel 自带 Qt 5.12.10 缺 `Qt_5.12.5_PRIVATE_API` 段导致 fcitx-qt5 input context plugin commit string 永远为 null 的问题。详见 [docs/pyqt5-abi-fix.md](../docs/pyqt5-abi-fix.md)
- **PyQt5 而非 Electron**：系统预装；二进制 71MB vs 200MB+
- **Flask + SSE 而非 WebSocket**：协议简单；curl 可调试；零额外依赖
- **PyInstaller `--onefile`**：单文件部署，无运行时依赖
- **数据放 `~/.desk-assistant/`**：用户级，跨进程共享，无需 root
- **`--paths panel --hidden-import *_card`**：panel/main.py 用 `sys.path.insert()` 动态注入，PyInstaller 静态分析跟不到
- **`clicked` 而非 `stateChanged`**：避免 SSE 重渲染 → setChecked → 信号 → POST 死循环
- **`_parse_iso()` 兼容 Python 3.6**：`datetime.fromisoformat()` 是 3.7+ API
- **测试/调试用 `state_test.db`**：通过 `DESK_ASSISTANT_DB=state_test.db` 切换，不污染生产数据

## 经验教训
- systemd timer 在 NewStartOS 上有 "Refuse to start, unit to trigger not loaded" 兼容性问题（v1 时代发现，已废弃）
- PyInstaller 打包时 PEP 604 语法（`str | None`）会嵌入运行时，Python 3.6.8 启动崩溃——必须避免
- SQLite WAL + 触发器滚动删除比应用层清理更稳
- SSE 心跳 15s 是客户端断线检测的甜点值
- PyQt5 wheel 在 Linux + 系统 Qt + 系统 fcitx-qt5/ibus-qt5 场景下几乎一定 ABI 不匹配（缺 `Qt_5.12.5_PRIVATE_API` 段）；验证方法 `readelf -V libQt5Gui.so | grep Qt_5`；修复只能用源码编译 + 链接系统 Qt，一次约 40+ 分钟
- 源码编译的 PyQt5 wheel 不带 platform plugins（libqxcb.so、libfcitxplatforminputcontextplugin.so），必须手动从 `/usr/lib64/qt5/plugins/{platforms,platforminputcontexts}` 拷贝，否则 QApplication() SIGABRT

## AI 使用指南
- 本文件是项目的 AI 记忆上下文，存储项目相关的背景、上下文
- AI 应阅读此文件理解项目背景后再开始相关工作
- 项目的关键决策、技术方案、经验教训应及时更新到此文件
- 保持简洁，聚焦对后续工作有价值的信息
