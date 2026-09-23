# 按本项目两条演进方向的参考资料

> 本项目当前状态（参考 `~/pkm/30_Notes/` 中的项目笔记）：
> - **技术栈**：Python 3 + PyQt5（panel_window.py + strip.py）+ pydbus + Nde global shortcut（Alt+M）
> - **形态**：右侧 37×75 天蓝色侧栏 strip + 主面板（玻璃拟态 QSS，Alt+M 唤起，失焦自隐）
> - **背景图**：v3.3 用户配置背景图系统（带热重载）
> - **集成**：OpenClaw / Gateway（猜测，待确认）
> - **部署**：PyInstaller 打包到 `~/.desk-assistant`，开机自启
> - **测试**：233 个测试用例通过（v3.4 时统计）

---

## 演进方向 A：保留 PyQt 面板，强化"个人工作台"

### 核心定位

> 一个轻量、本机优先、与 Deepin/UOS 等国产桌面集成良好的个人 AI 工作台面板。

### 借鉴项目（按价值排序）

#### ★★★★★ cc-haha（14.4k★）

- **借鉴点**：
  - **会话活动面板**结构：把"当前会话 + 后台任务 + 子任务"做成三层视图
  - **权限分级模式**：本项目当前是"全自动"，可参考其 5 档设计
  - **H5 远程访问**：从手机浏览器远程看本机面板（高价值、高成本）
- **实现路径**：在 panel_window.py 加一个 Tab，参考其 layout 设计
- **成本评估**：低~中，主要是 UI 工作

#### ★★★★★ clawd-on-desk（6.2k★）的状态机设计

- **借鉴点**：
  - **12 种动画状态**：idle / thinking / typing / building / juggling / waiting / error / sleep / ...
  - 状态不是装饰，而是**低认知负荷的状态反馈**
- **实现路径**：
  - 在 panel_window.py 中加一个 `_status` 字段（`thinking` / `working` / `idle` / `waiting` / `error`）
  - 给 strip.py 加 4 个状态色（蓝 / 黄 / 绿 / 橙 / 红）
  - 主面板顶部加状态指示器
- **成本评估**：极低（半天工作量）

#### ★★★★ token-monitor（2.1k★）的本地日志解析

- **借鉴点**：
  - 解析 `~/.claude/`、`~/.codex/` 等日志的 token 用量
  - 缓存命中统计、每会话明细
- **实现路径**：
  - 新增 `token_monitor.py` 模块
  - 主面板新增"用量 Tab"
  - 参考 tokscale（其解析核心）的 JSONL 解析逻辑
- **成本评估**：中（适配各 AI 工具的日志格式是体力活）

#### ★★★★ zebar（3.1k★）的 Provider 模型

- **借鉴点**：
  - 把"OpenClaw 状态 / 系统信息 / Claude Code 日志"分别抽象成 provider
  - 面板只消费 provider 输出，不直接读数据源
- **实现路径**：
  - 定义 `Provider` 协议（async def get_state() -> dict）
  - 各 provider 独立实现
  - panel_window.py 用 QTimer / QThread 轮询
- **成本评估**：中（需要重构一些现有代码）

#### ★★★★ OpenPets 的 MCP 桥接设计

- **借鉴点**：
  - 通过 MCP stdio 接入 Claude Code / OpenCode / Cursor / Pi
  - 不暴露 prompt / code / 路径 / 日志 / secret
- **实现路径**：
  - 新增 `mcp_bridge.py` 模块
  - 通过 `npx -y @modelcontextprotocol/...` 或 `uvx` 调用 MCP server
  - 面板显示 MCP 返回的状态事件
- **成本评估**：中（MCP 协议学习成本）

---

## 演进方向 B：保留 PyQt 面板，追加"桌宠"层

### 核心定位

> 在现有面板基础上，叠加一个低噪音的桌宠 / 状态代理，让长任务不再"无感"。

### 借鉴项目（按价值排序）

#### ★★★★★ clawd-on-desk（6.2k★）

- **借鉴点**：
  - 整个项目就是"桌宠 + Agent 状态可视化"
  - 12 种动画状态、20+ Agent 适配
- **实现路径**：
  - **不直接 fork**（AGPL-3.0）
  - **借鉴其状态机 + 颜色 / 表情映射**到本项目 strip
  - strip 当前是单一蓝色，可以加 4~5 个状态色
- **成本评估**：极低（半天到一天）

#### ★★★★ MiniCPM-Desk-Pet（484★）的首次启动引导

- **借鉴点**：
  - 环境检查 → 模型下载 → 预热 → 就绪的 onboarding 流程
- **实现路径**：
  - 如果未来要加本地 LLM，参考此流程
  - 否则跳过
- **成本评估**：仅当用户选择本地 LLM 路线时适用

#### ★★★★ Open-LLM-VTuber（13.8k★）的桌宠模式

- **借鉴点**：
  - 透明背景 + 全局置顶 + 鼠标穿透——本项目 panel 当前是"失焦自隐"，可以参考其"不抢占焦点"
- **实现路径**：
  - strip 默认鼠标穿透（用户点击穿透到桌面）
  - 点击 strip 才唤起主面板
- **成本评估**：低

#### ★★★ AgentPet（350★，30 天 +85★）

- **借鉴点**：
  - 多 Agent 实时监控菜单栏 + 桌宠
  - 等级养成 / leaderboard（可选）
- **实现路径**：
  - 可选功能——"本项目使用的 token 越多，宠物等级越高"
  - 增加粘性但非核心
- **成本评估**：低（可选）

---

## 演进方向 C：Token / 用量监控（独立模块）

> 与 A、B 不冲突，可独立实施。

### 借鉴项目

#### ★★★★ token-monitor（2.1k★）

- **借鉴点**：
  - 解析 36+ AI 工具的本地日志
  - 多设备同步（用 Cloudflare Worker / 自托管 SSE）
- **实现路径**：
  - 新增 `token_monitor.py` 模块
  - 解析 `~/.claude/settings.json` + `~/.claude/projects/**/*.jsonl`
  - 主面板新增"用量"视图（折线图 + 明细表）
- **成本评估**：中

---

## 不建议的方向

### ❌ Live2D / VTuber 路线

- 代表：`airi`、`Open-LLM-VTuber`、`Miru`、`Petto`
- 原因：需要 Live2D 模型 + 语音 + 长期记忆三件套，技术栈与本项目不兼容
- 除非用户明确要走这条线，否则不建议

### ❌ 长期记忆 / 情感建模

- 代表：`Agentic-Desktop-Pet`、`awesome-ai-companion` 中的 Memory 类项目
- 原因：本项目当前是工具型，"情感引擎 + RPG 养成"是另一类产品

### ❌ 国产本地执行型 Agent 路线

- 代表：`AiPy`、`LobsterAI`、`CoPaw`、`OpenOcta`
- 原因：这些是"通过 AI 控制电脑执行任务"的 Agent，与本项目"AI 助手面板"形态不同
- 但可以借鉴其"本地优先 + 数据不出本机"的对外宣传

### ❌ 重写为 Electron / Tauri

- 成本太高，本项目 PyQt5 跨平台已经 OK
- 仅当需要"Web 生态 + npm 包 + 跨端"时才考虑

---

## 实施路线图建议（低 token 投入，渐进）

### 阶段 1：低成本立刻可做（半天 ~ 一天）

- [ ] strip 加 4~5 个状态色（借鉴 clawd-on-desk）
- [ ] panel 顶部加状态指示器
- [ ] 写一个 `task_state.py` 模块，统一状态字段

### 阶段 2：增强交互（一周）

- [ ] 把"权限确认"做成浮动气泡（替代面板内的全屏对话框）
- [ ] 全局快捷键增加：Cmd/Ctrl+Shift+T 切换思考模式显示
- [ ] 增加用量 Tab（解析 `~/.claude/` 日志）

### 阶段 3：可选 - Claude Code / Coding Agent 集成（两周）

- [ ] 抽象 Provider 协议（zebar 模式）
- [ ] 增加 MCP bridge（OpenPets 模式）
- [ ] 多 Agent 状态展示（Claude Code / Codex / Cursor）

### 阶段 4：可选 - 长期方向（一月+）

- [ ] 插件 SDK（参考 OpenPets / Rainmeter）
- [ ] H5 远程访问（参考 cc-haha）
- [ ] 多设备同步（参考 token-monitor）

### 阶段 5：开源准备（如要开源）

- [ ] LICENSE 选择（建议 MIT 或 Apache-2.0，参考本项目同类）
- [ ] README + 多语言（参考 airi）
- [ ] Weblate 翻译（参考 Rainmeter）
- [ ] 持续 DevLog（参考 airi）

---

## 核心引用（按价值排序）

1. **clawd-on-desk** — 状态机设计 + Agent 适配
2. **cc-haha** — 工作台整体形态
3. **token-monitor** — Token 监控实现
4. **OpenPets** — 插件 SDK + MCP 桥接 + 隐私默认
5. **zebar** — Provider 解耦
6. **awesome-ai-companion** — 生态地图
7. **WolfChen1996/DesktopPet** — 同技术栈参考（PyQt5）
8. **fabric** — Python widget 框架
9. **Open-LLM-VTuber** — 桌宠模式（透明 + 不抢焦）
10. **MiniCPM-Desk-Pet** — 首次启动引导
