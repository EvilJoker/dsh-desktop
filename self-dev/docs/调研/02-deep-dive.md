# Top 12 项目深度分析

> 每个项目按"定位 / 技术栈 / 核心特性 / 借鉴点 / 风险"展开。
> 数据采集于 2026-09-15。

---

## 1. cc-haha（NanmiCoder/cc-haha）⭐ 14.4k / Forks 8.5k

**定位**：本地优先、跨平台的 Claude Code / AI Agent 桌面工作台。对标对象：Claude Code CLI + IDE 插件 + 桌宠 + IM 接入 + 技能市场的"全家桶"。

**技术栈**：TypeScript + Electron + React + Vite + Bun + Ink（终端 UI）+ Anthropic SDK + MCP + LSP。

**核心特性**：

- 多会话标签 + 项目切换 + 可拖拽侧边栏
- **会话活动面板**集中查看任务进度与后台任务
- **AI 桌宠**：搭搭、弧弧、补补、回回，随任务状态切换动作（默认关闭，可自定义）
- 多模型选择：Claude / ChatGPT / Grok / DeepSeek / Kimi / GLM / Ollama / LM Studio
- Computer Use（Agent 控制桌面应用）
- MCP 可视化管理、SubAgent / Agent Teams 协作、动态 Workflow 编排
- IM 接入：Telegram / 飞书 / 微信 / 钉钉 / WhatsApp / 企业微信 / QQ / Slack
- 内置浏览器预览、五档权限模式、技能市场、六套主题

**维护**：✅ 活跃，2,011 commits，main 分支持续提交，有企业赞助（Atlas Cloud、ApiSmart）。

**License**：MIT

**借鉴点**：

1. **会话活动面板**结构：本项目当前的 panel 可以扩展一个"会话列表 + 状态"视图，参考其 layout。
2. **桌宠默认关闭 + 可启用**：避免桌宠成为噪音，让用户自己选择是否开启。
3. **IM 接入 + H5 远程**：从手机推送任务到本机面板——这是高价值但高成本的方向，先记下。
4. **权限模式（5 档）**：本项目目前是单档"全自动"，可参考其分级。

**风险**：体积庞大（Electron 全家桶），不适合做"轻量桌面助手"的全部借鉴对象；建议只取其 UI 范式。

---

## 2. clawd-on-desk（rullerzhou-afk/clawd-on-desk）⭐ 6.2k / Forks 646

**定位**：像素桌面宠物，监控 Claude Code / Codex / Cursor 等 AI 编程代理——核心解决"长任务下用户不需要盯终端"。

**技术栈**：Electron（Node.js）+ 资产格式 SVG/GIF/APNG/WebP/PNG/JPG。

**核心特性**：

- **12 种动画状态**：idle / thinking / typing / building / juggling 等
- 内置 3 个主题（Clawd 螃蟹 / Calico 猫 / Cloudling 云宝），支持自定义
- **权限气泡**：浮动卡片处理 Allow/Deny，支持 Telegram/Feishu 远程审批
- 多会话跟踪、子代理感知、终端聚焦
- 开机自启、单实例锁、自动更新、DND 模式
- 支持 **20+ AI 代理**：Claude Code / Codex CLI / Copilot CLI / Gemini CLI / Cursor Agent / Qwen Code / opencode / Kimi Code CLI / CodeBuddy / Kiro CLI 等

**维护**：✅ 活跃，2,348 commits，Issues 66 / PR 21 开放。

**License**：AGPL-3.0（资产单独授权，Clawd 角色是 Anthropic 财产）

**借鉴点（最高优先级）**：

1. **状态机驱动动画**：本项目 panel 当前是"输入 + 显示"，可以加一个状态字段（idle / thinking / typing / waiting），按状态切换表情/动画/缩略文字。
2. **权限气泡 UX**：本项目当前全在面板内处理，确认/取消按钮可以做成浮动气泡，减少面板交互开销。
3. **20+ Agent 适配的扩展模型**：用 hooks / 状态文件读取 / transcript tailing 三种方式接入新 Agent，新增 agent 不需要大改核心。

**风险**：AGPL-3.0——如果直接 fork，必须开源衍生作品。建议只读代码借鉴，UI 自写。

---

## 3. token-monitor（Javis603/token-monitor）⭐ 2.1k / Forks 205

**定位**：本地优先桌面小部件，跨 36+ AI 编程工具追踪 token 用量、成本与限额，支持多设备同步。

**技术栈**：Electron + Node.js CLI + Cloudflare Worker（sync hub）+ SSE。

**核心特性**：

- 实时追踪 Claude Code / Codex / Cursor / Copilot / Antigravity / OpenCode / OpenClaw 等 36+ 工具
- 缓存命中统计、每会话明细、成本（USD/TWD/HKD/CNY）
- AI 工具限额检测、Codex 账号一键切换
- **三种 hub 后端**：widget 内置 / Node CLI / Cloudflare Worker
- macOS 菜单栏 / Windows 系统托盘 / 浮动 Bubble 三种 UI 形态
- iOS Widget（Widgy / Scriptable）
- 跨平台：macOS（ARM + Intel）、Windows 10/11、Linux x64

**维护**：✅ 活跃，742 commits，Issues 49 / PRs 43 开放。

**License**：MIT

**借鉴点**：

1. **本机日志解析的多种格式适配**——本项目如果要做 token 监控，可以直接参考 tokscale 的解析逻辑。
2. **菜单栏 / 系统托盘 / 浮动气泡**三种 UI 形态——本项目已有侧边栏 strip，可以参考其"按窗口类型选 UI"的策略。
3. **隐私优先：prompts/responses/源码均留在本地**——与本项目的本机面板定位一致。

**风险**：项目核心在解析，需要写大量 AI 工具日志适配器，工作量大。建议列为"方向 C"的参考而不是直接 fork。

---

## 4. MiniCPM-Desk-Pet（OpenBMB/MiniCPM-Desk-Pet）⭐ 484 / Forks 61

**定位**：本地优先桌面宠物，集成 MiniCPM5-1B 本地推理 + Coding Agent 状态感知。

**技术栈**：Electron + 内嵌 llama.cpp sidecar + HF/ModelScope 模型下载。

**核心特性**：

- **零手动设置**：首次启动引导环境检查 → 模型下载 → 预热 → 就绪
- **悬浮聊天气泡**：Cmd/Ctrl+Shift+M 唤起，Cmd/Ctrl+Shift+T 切换思考模式，Esc 关闭
- **Agent-aware 联动**：自动扫描 Cursor / Claude Code / Codex 等 agent，感知 thinking / working / finished / idle
- **任务叙事**：agent session 结束时用气泡总结 AI 刚做的事
- **Idle 提醒**：agent 等待输入时播放铃铛动画 + 音效
- **Persona 切换**：Settings → MiniCPM 切换或导入角色 adapter（neko LoRA）

**维护**：✅ 活跃，92 commits，Releases 持续发布。

**License**：AGPL-3.0-only（模型权重另行遵循 OpenBMB MiniCPM License）

**借鉴点**：

1. **首次启动引导流程**：环境检查 → 模型下载 → 预热 → 就绪，是"本地 LLM 桌宠"的标准 onboarding 范式。
2. **任务叙事气泡**：agent 结束时总结"AI 刚做了什么"，是非常实用的功能。本项目如未来接入 Claude Code 任务状态，可参考。
3. **Cmd/Ctrl+Shift+M 全局快捷键 + 浮动气泡**——本项目已有 Alt+M（nde-globalkeysd），气泡形态可以借鉴。
4. **Persona adapter 的拆分**：UI 资源与角色分开，便于用户自定义。

**风险**：Apple Silicon 主测，Windows 兼容性未完全验证；AGPL-3.0 与 clawd-on-desk 相同问题。

---

## 5. Agentic-Desktop-Pet（jihe520/Agentic-Desktop-Pet）⭐ 338 / Forks 45

**定位**：下一代 Agentic 桌宠 = LLM + 记忆 + 情感 + RPG + Claude Code。

**技术栈**：Godot 4.3+（前端 GDScript）+ Python 3.13+ / FastAPI（后端）+ Cognee（知识图谱）+ 自研 emotion_engine。

**核心特性**：

- **记忆**：知识图谱 + 长期持久化 + 语义检索 + 自动实体/关系抽取
- **Agent**：文件读写、代码执行、待办、系统命令（Claude Code 风格）
- **Mod**：可切换的 `.pck` 主题，方便换皮
- **情感**：基础情绪 + 时间衰减 + 交互增强 + 影响回复风格
- **RPG**：智力/魅力/敏捷/体力、经验升级、技能解锁、亲密度

**维护**：⚠️ 个人业余，29 commits，"development is still in progress, there are many bugs"

**License**：⚠️ **非标**——代码可片段复用，禁止整体商用打包。

**借鉴点**：

1. **情感引擎 + RPG 养成**：如果要走"长期陪伴"方向，是少数提供完整情感建模的参考。
2. **Cognee 知识图谱**：长期记忆的现代方案，比纯向量 RAG 多一层关系。
3. **Mod 主题包**（`.pck`）：把"换皮肤"做成一等公民。

**风险**：Godot 技术栈本项目无法直接复用；license 限制商用打包，只能借鉴设计思路。

---

## 6. OpenPetsHQ/openpets ⭐ 1.2k+（最近 30 天 +329★，增速惊人）

**定位**：本地优先桌面伴侣平台，桌宠 + 插件 SDK v3 + 可选 Coding Agent MCP 接入。

**技术栈**：TypeScript + Electron + pnpm workspace + 沙箱化 BrowserWindow。

**核心特性**：

- **官方插件目录**：focus timers、reminders、mood check-ins、mini games、launcher、hydration nudges、virtual pet stats
- **插件 SDK v3**：沙箱化 JS/TS 运行时，权限 + 配额 + 存储 + 计划 + 命令 + 面板 + 事件 + 音频 + 通知
- **可选 MCP 接入**：Claude Code、OpenCode、Cursor、Pi 都能驱动本地宠物反应，不暴露 prompt / code / 路径 / 日志 / secret
- **敏感功能默认关闭**：剪贴板、麦克风、AI 语音都要显式 opt-in
- 跨平台：macOS（ARM + Intel）、Windows、Linux

**维护**：✅ 活跃，最近 30 天 +329 stars，在 trending 出现 34 天，峰值 #106。

**License**：MIT

**借鉴点（最高优先级）**：

1. **插件 SDK v3 设计**：沙箱 + 权限清单 + 配额 + 计划任务，是"插件化"的标准答案。本项目未来如果要开放插件机制，直接参考其 SDK 模型。
2. **安全默认**：剪贴板、麦克风、AI 语音默认关闭——这是隐私优先的硬规则。
3. **MCP stdio 桥接**：用 `npx -y @open-pets/mcp@latest` 把 MCP 客户端（如 Claude Code）连到桌宠，是当前最干净的 Agent ↔ 桌宠集成模式。

**风险**：插件 SDK 的设计是大型工程，本项目短期内不需要。

---

## 7. zebar（glzr-io/zebar）⭐ 3.1k / Forks 132

**定位**：跨平台桌面 widget / taskbar / popup 创建工具，原生 webview（比 Electron 轻量）。

**技术栈**：Rust + 原生 webview + NPM 包（zebar 提供 provider API）。

**核心特性**：

- **Provider 模型**：`audio / battery / cpu / date / disk / glazewm / host / ip / keyboard / komorebi / media / memory / network / systray / weather` 全部抽象成响应式 provider
- 内置 GUI / 系统托盘 / 市场（marketplace）
- 模板选项：React buildless（无需 Node）
- 配置文件：`zpack.json` 描述 widget 包
- 安装目录：`~/.glzr/zebar/`

**维护**：✅ 活跃，504 commits，Issues 61 / PR 10 开放。

**License**：GPL-3.0

**借鉴点（最高优先级）**：

1. **Provider 解耦**：本项目的 panel 当前是"输入 → OpenClaw → 显示"的直接流程，可以把"OpenClaw 状态 / 系统信息 / Claude Code 日志"分别抽象成 provider，panel 只消费。
2. **Webview 而非 Electron**：本项目是 PyQt5，可以参考其"原生窗口 + 内部渲染"的取舍逻辑。
3. **市场（marketplace）**：如果未来要让用户分享 widget / 主题，可以参考其包格式。

**风险**：GPL-3.0 与本项目商用打包不冲突（不 fork，只借鉴架构），但 Rust 技术栈本身门槛高。

---

## 8. Fabric-Development/fabric ⭐ 1.4k / Forks 47

**定位**：下一代 Python 桌面 widget 框架。

**技术栈**：Python + GTK3 + X11/Wayland 兼容。

**核心特性**：

- 简单但强大，API 高层抽象
- 基于 signal 的工作流，无需轮询或 shell 脚本
- 支持所有 Python 模块
- 出色的开发者体验与类型支持
- 低资源占用
- 跨显示协议兼容（X11/Wayland）

**维护**：✅ 活跃，246 commits，有 Nix flake 和 Arch Linux PKGBUILD。

**License**：AGPL-3.0

**借鉴点**：

1. **Signal-based 工作流**：本项目 pydbus / Qt signal 用得不少，可以参考其"无轮询"理念。
2. **跨显示协议兼容**：本项目当前是 Deepin (X11)，未来如果兼容 Wayland 需要这种解耦设计。

**风险**：GTK3 与本项目 Qt5 技术栈不同，无法直接复用。

---

## 9. rainmeter / rainmeter ⭐ 6.0k / Forks 641

**定位**：Windows 桌面定制工具（widget / 皮肤引擎），是 widget 类应用的"祖师爷"。

**技术栈**：C++ 解决方案（`Rainmeter.sln`），含 Application / Library / PluginAPI / RainLexer / SkinInstaller 模块。

**核心特性**：

- 桌面 widget / 皮肤引擎，支持用户自定义界面元素
- 插件架构（PluginAPI）
- 内置语法解析器（RainLexer）
- 皮肤打包工具（`.rmskin`）
- 多语言本地化（Weblate）
- 默认不联网，皮肤可按需拉取 RSS / 天气等数据

**维护**：✅ 活跃，5,151 commits，issues / PR 通道畅通，SignPath 代码签名 + Weblate 本地化。

**License**：GNU GPL v2

**借鉴点（架构层面）**：

1. **Plugin API + 自定义脚本解析器（Lexer）**的组合是 widget 引擎的经典骨架。
2. **`.rmskin` 打包格式**：解决了 widget 类产品的最大分发难题——"用户怎么装一个 widget"。本项目未来如果要分发改皮 / 插件，需要类似的打包方案。
3. **开源 + 基金会赞助签名 + Weblate 社区翻译 + 独立官网分发**的"四位一体"治理模式。

**风险**：仅 Windows（Win32 API），跨平台改造需评估 GDI / Direct2D 剥离成本——这正是本项目 PyQt5 已经跨过的坎。

---

## 10. Open-LLM-VTuber ⭐ 13.8k / Forks 1.6k

**定位**：开源语音交互 AI 伴侣，复刻开源版 neuro-sama。

**技术栈**：Python + Ollama / OpenAI 兼容 API + sherpa-onnx / Faster-Whisper + Live2D + Docker。

**核心特性**：

- **实时语音**：无需耳机即可打断（AI 不听到自己的声音）
- **视觉感知**：摄像头/录屏/截图
- **Live2D 表情映射**：后端控制情绪
- **触摸反馈**：点击/拖拽交互
- **桌面宠物模式**：透明背景 + 全局置顶 + 鼠标穿透
- 灵活 Agent 接口：可继承实现 HumeAI EVI / OpenAI Her / Mem0 等

**维护**：✅ 活跃，913 commits，v2.0 重写中。社区迁移到 Zulip。

**License**：MIT（Live2D 示例模型单独授权）

**借鉴点**：

1. **桌面宠物模式**：透明背景 + 全局置顶 + 鼠标穿透——本项目 panel 当前是"全屏面板 + 失焦自隐"，可以参考其"不抢占焦点"的桌宠模式。
2. **打断机制**：用户说话时 AI 自动停——对话类桌宠的关键体验。
3. **Agent 接口继承化**：让用户自己接入 Mem0 / HumeAI / OpenAI Her，是插件化的轻量版本。

**风险**：VTuber 路线比桌宠路线重（涉及语音 + Live2D），本项目短期内不建议走这条路。

---

## 11. moeru-ai/airi ⭐ 49.1k / Forks 4.9k

**定位**：开源 AI 数字人 / 虚拟伴侣，对标 Neuro-sama。

**技术栈**：Vue + TypeScript + WebGPU + WebAudio + WebAssembly + WebSocket + Electron + Live2D/VRM/Three.js + PostgreSQL + Redis。

**核心特性**：

- **Brain**：Minecraft / Factorio / Helldivers 2 协同、Kerbal Space Program（即将）、Telegram/Discord 聊天
- **Ears**：浏览器/Discord 音频采集、客户端语音识别、说话检测
- **Mouth**：ElevenLabs / Azure / OpenAI 兼容 / Kokoro 本地 TTS
- **Body**：VRM + Live2D 模型控制、自动眨眼/注视/闲置眼动

**维护**：✅ 极度活跃，4,407 commits，DevLog 持续更新（移动端性能与游戏引擎探索）。

**License**：MIT

**借鉴点**：

1. **项目品牌 + 社区运营**：49k stars 来自持续 DevLog + 多语言 README + Discord 社区，是开源 AI 桌宠的天花板。本项目如要开源，"讲好故事 + 持续更新"是关键。
2. **Live2D + VRM 双格式支持**：未来如果要可视化桌宠，可以参考其"模型即插件"的做法。

**风险**：体量过大，技术栈与本项目不重合，借鉴价值主要在"社区运营方法论"。

---

## 12. awesome-ai-companion ⭐ 682 / Forks 66

**定位**：人机恋开源项目大全，让"家机"脱离官端、拥有记忆与主动性。

**分类**：

1. Companion Clients & Workspaces：RikkaHub / Aura / Operit / Scowld / yoji / Claude Code CLI
2. Virtual Phones & Companion Spaces：KI-CO / AI Virtual Phone / Hamster Nest / dwell-on-something
3. Memory, Identity & Emotion State：Ombre-Brain / kimi-core / Paramecium / Memory Constellations / Aelios / imprint-memory / Drivesoid / Eventide
4. Background Heartbeats & Proactive Messaging：Headlong / AstrBot / Claude Imprint / jiwen / revive-companion
5. Voice, Visual Presence & Embodiment：GPT-SoVITS / AIRI / Open-LLM-VTuber / Soul-of-Waifu / super-agent-party / LingChat
6. **Desktop Pet**：clawd-on-desk / Miru
7. Continuity & Data Ownership：forge-reload / context-slim / immortal-skill / character-card-spec-v2

**借鉴点**：

- **这是生态地图**，远比单项目参考价值高。本项目演进时按上面 7 个分类对号入座。
- **"Continuity & Data Ownership"**（数据所有权）这一类对本项目价值最高——本项目本身是"本机 PyQt 面板"，正好踩在这个赛道上。

---

## 速查对照表（按本项目最相关的设计点）

| 设计点 | 最佳参考 |
| ------ | ------ |
| **状态机驱动动画** | clawd-on-desk |
| **Agent ↔ 桌宠桥接（MCP）** | openpets、clawd-on-desk |
| **Provider 解耦** | zebar |
| **插件 SDK 设计** | openpets、rainmeter |
| **隐私优先默认** | openpets、token-monitor |
| **首次启动引导** | MiniCPM-Desk-Pet |
| **权限气泡 UX** | clawd-on-desk |
| **桌宠模式（透明 + 不抢焦）** | Open-LLM-VTuber |
| **同技术栈参考** | WolfChen1996/DesktopPet（PyQt5） |
| **生态全景图** | awesome-ai-companion |
| **长期记忆** | Agentic-Desktop-Pet（Cognee） |
| **社区运营方法论** | airi |
