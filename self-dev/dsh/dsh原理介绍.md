# DSH 原理介绍说明

> 本文档讲解 DSH（DeepSeek Harness）的核心原理：
> - **第 1 部分：DSH 工作原理** —— `dsh web` 怎么跑起来、数据怎么存
> - **第 2 部分：三大核心概念** —— Cordis / Bundle / Profile 是什么
>
> 适用读者：DSH 用户 / 插件开发者。

---

## 第 1 部分：DSH 工作原理

## 1.1 `dsh web` 启动流程

CLI 入口 → 选定 profile → 按层应用配置 → 加载 `dsh-base` + `dsh-web-app` bundle → Cordis 上下文创建 → Agent runtime 初始化 → 浏览器应用启动。

启动顺序：

1. **CLI 入口**：`dsh web` 等价于 `dsh --profile web`
2. **Profile 选择**：从 `dsh.profile` 字段读取 bundle 列表
3. **Layer 应用**：profile bundle → profile 的 `cordis.patch.yml` → home 层 → `--patch` overlay
4. **Bundle 加载**：`dsh-base` 提供 model adapter / tools / persistence / sandbox / settings / telemetry / credentials；`dsh-web-app` 添加浏览器应用
5. **Cordis 上下文**：所有 plugin 挂载到共享 context，提供 typed services 与 reversible effects
6. **验证**：`verify-application-entrypoints` 确保 Node 路径都经过 `dsh`

可用命令查看树：`dsh --profile web --dump-config`

## 1.2 Cordis 容器：进程内单例

**每个 `dsh` 进程就是一个 Cordis context**：

- 一个进程 = 一个 plugin tree
- registrations 作为 effects 在 plugin unload 时 unwind
- 服务通过 `ctx.xxx` key 直接访问（同进程）

## 1.3 端口分配机制

- **Web profile**：默认监听 `127.0.0.1:3080`（HTTP + WebSocket）
- **Desktop 桌面应用**：明确**不开端口**，使用 Electron 风格的 IPC 通道
- **端口冲突时**：boot 库会按配置决定 "Warn; continue without that endpoint" 或 "Stop startup"

可用 `--port` 参数指定其他端口。

## 1.4 多 `dsh web` 实例并行启动的行为

**结论：第二个 `dsh web` 会因端口冲突报错**。

原因：

1. DSH 是"单实例单 profile"架构——一个进程只跑一个 profile
2. 没有单实例锁 / 端口复用机制（util 包只有写入锁，没有"实例级"互斥）
3. 默认端口 3080 被第一个进程占用，第二个进程无法绑定

**多实例适用场景**：

| 场景 | 是否支持 | 方案 |
|---|---|---|
| 同机器多终端（桌面+浏览器+手机） | ❌ 单 DSH | 各终端作为 DSH 客户端连接 localhost:3080 |
| 多机器（Mac + 服务器） | ✅ | DSH 桌面壳自带的远程连接，或自建反向代理 |
| 同机器多 DSH 隔离 | ⚠️ 不推荐 | 必须用 `--port` 改端口，且数据目录 ~/.dsh 会共享 |

## 1.5 `~/.dsh` 目录结构

DSH 的所有用户数据存储在 `~/.dsh/`（可通过 `$DSH_HOME` 环境变量覆盖）：

```text
~/.dsh/
├── cordis.yml                    # 用户根配置
├── cordis.patch.yml              # 全局 tweak（覆盖所有 profile）
├── .env                          # 环境变量层（DSH_HOME 等）
├── profiles/                     # 各 profile 独立目录
│   ├── web/                      # dsh web 专用
│   │   └── cordis.patch.yml
│   ├── headless/                 # dsh headless 专用
│   └── desktop/                  # Electron 桌面壳专用
│       └── pnpm-store/
├── credentials.yaml              # 凭证存储（同 OS 用户可读，权限 600）
├── sessions/                     # 会话数据（JSONL，可选 Zstd 压缩）
└── workspaces/                   # 工作空间索引
```

## 1.6 多 Profile 隔离机制

**机制：独立进程 + 不同 bundle 组合 + 配置层叠**。

隔离方式：

1. **进程隔离**：每个 profile 一个 `dsh` 进程实例
2. **Bundle 差异**：
   - `web`：浏览器应用
   - `headless`：一次性 runner，无 server
   - `sdk` / `sdk-minimal`：JSON-RPC SDK 服务
   - `acp`：自动化 ACP server
3. **Patch reload 策略**：
   - `web` / 自定义 profile：热重载
   - `headless` / `sdk` / `sdk-minimal` / `acp`：启动时一次性应用
4. **用户级覆盖**：home 的 `cordis.patch.yml` 可修改任何 profile 的行

**示例**：`dsh --profile web --dump-config` 输出当前 profile 树；任何行可被自定义 patch 替换。

## 1.7 Web UI ↔ Agent Runtime 通信

DSH Web UI 与 Agent runtime 的通信采用版本化的 framed byte pipes：

- **Unary RPC + Remote streams**：走版本化字节管道
- **Node IPC**：仅用于 lifecycle control
- **`dsh-app://` protocol**：renderer 通过 secure protocol 访问资源
- **Loopback port**：桌面不开 Web server 或回环端口

**Web Session-follow adapter** 是 agent live event 的唯一远程消费者：

- `session/event` 广播用于实时 UI 增量更新
- `agent/assistant-stream` 发布 process-local start/chunk/end 帧

## 1.8 配置层叠顺序

DSH 使用 Cordis 配置层叠机制，按以下顺序应用（后层覆盖前层）：

```text
CLI flag (--patch)                   ← 临时覆盖，最高优先级
    ↓
profile bundle 内的 cordis.yml       ← profile 自带配置
    ↓
profile 的 cordis.patch.yml          ← profile 局部补丁
    ↓
~/.dsh/cordis.yml                    ← 用户级根配置
    ↓
~/.dsh/cordis.patch.yml              ← 用户级覆盖所有 profile 的 tweak
```

**查看当前生效配置**：

```bash
dsh --profile web --dump-config
```

## 1.9 核心数据存储

### 1.9.1 Session（会话记忆）

**session = 一次对话的完整生命周期记录**，是 DSH 的核心持久化层。

- **格式**：JSONL（每行一个事件），可选 Zstandard 压缩
- **位置**：`~/.dsh/sessions/`（按代际文件名规范）
- **特性**：只追加（append-only）—— 永不改写历史，便于回放和分叉

**记录内容**：

| 内容 | 说明 |
|---|---|
| 系统提示词 | 每轮的系统 prompt 快照 |
| 思维链 | 模型的推理过程 |
| 工具调用与结果 | function call 完整记录 |
| 子 Agent 调度 | Subagent 委派链 |
| 上下文注入 | 每次 LLM 调用前的内容快照 |
| 用户消息与助手回复 | 对话主体 |

**用途**：

- Trajectory 回放：Web UI 的 Trajectory 视图可按来源查看、恢复、分叉、检索
- 断点续传：进程崩溃后下次启动能从 checkpoint 继续
- 统计分析：`session-stats` 提供对话计数和墙钟时间
- 会话标题生成：可基于首条消息自动生成标题
- 遥测上报：可选通过 OpenTelemetry 上报（默认关闭）

### 1.9.2 Workspace（工作空间）

**workspace = 持久化的项目层**——把一堆相关会话按项目组织起来。

| 维度 | Workspace | Session |
|---|---|---|
| 定位 | 项目（长期） | 单次对话（短期） |
| 模型可见 | ❌ 不暴露给模型 | ✅ 注入到 LLM 上下文 |
| 存储 | 域名 KV（SQLite / JSON） | JSONL 文件 |
| 组织方式 | 按项目分组的 session 列表 | 独立单元 |
| 删除行为 | 软删除（保留目录和历史） | 硬删除 |

**典型场景**：你有项目 A、项目 B、项目 C；每个项目下有 N 个 session（"实现登录功能"、"修 bug #123" 等）。

### 1.9.3 Credentials（凭证）

**设计原则：配置只存名称，不存值。**

```yaml
# ~/.dsh/cordis.yml（正确做法：只引用）
provider:
  api_key_ref: "deepseek-prod"   # 引用 credentials.yaml 里的条目
```

```yaml
# ~/.dsh/credentials.yaml（同 OS 用户可读，权限 600）
deepseek-prod:
  value: "sk-xxxx"
  # 旋转后下次 LLM 调用生效
```

**优先级**：

```text
环境变量 DEEPSEEK_API_KEY=xxx   ← 单次运行最高优先级
    ↓
~/.dsh/credentials.yaml          ← 本地持久存储
```

### 1.9.4 Storage（非会话应用数据）

跨进程持久化的非会话应用数据。**不暴露给模型**。

| 后端 | 用途 |
|---|---|
| `storage-json` | 每个单元一个 JSON 文件（人类可读） |
| `storage-sqlite` | 单 SQLite 库 + JSON 文档（点更新） |
| `storage-domain` | 带 schema 验证 + 变更通知的 KV 域 |

**典型用途**：应用配置、缓存、用户偏好、插件状态等。

## 1.10 整体数据流图

```text
┌─────────────────────────────────────────────┐
│  DSH Process (单实例)                         │
│                                              │
│  ┌──────────────┐    ┌──────────────────┐   │
│  │ LLM Adapter  │    │ Tool Registry    │   │
│  └──────┬───────┘    └────────┬─────────┘   │
│         │                     │             │
│         ▼                     ▼             │
│  ┌──────────────────────────────────────┐   │
│  │   Agent Loop (core package)          │   │
│  │   - 接收 user input                   │   │
│  │   - 注入 session + context            │   │
│  │   - 调用 LLM，调度 tools              │   │
│  └──────────┬───────────────────────────┘   │
│             │                               │
│             ▼                               │
│  ┌──────────────────────────────────────┐   │
│  │   Session Persistence (JSONL)         │   │
│  │   → ~/.dsh/sessions/<id>.jsonl       │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │   Storage (workspace / settings)      │   │
│  │   → ~/.dsh/workspaces/ + sqlite       │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │   Credentials (local file, mode 600)  │   │
│  │   → ~/.dsh/credentials.yaml          │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

---

## 第 2 部分：三大核心概念 —— Cordis / Bundle / Profile

## 2.1 Cordis 是什么

**一句话：Cordis 是一个"插件容器"，把一堆小功能（插件）装进同一个盒子里，让它们能互相调用。**

### 生活比喻

想象一个 **公司**：

- 公司 = Cordis context（容器）
- 每个员工 = 一个 plugin（插件）
- 员工入职时分配工位 → `ctx.plugin()`
- 员工之间发消息协作 → `ctx.emit('event')` / `ctx.on('event')`
- 员工离职时清空工位 → plugin unload 时 unwind 所有 effect

### 代码示例

```typescript
import { Context } from 'cordis'

// 创建一个 Cordis 容器（一家公司）
const ctx = new Context()

// 员工 A：负责"发送邮件"
ctx.plugin(function sendEmail(ctx) {
  // 注册一个 service（岗位）
  ctx.service('email', {
    send(to: string, body: string) {
      console.log(`发送邮件给 ${to}: ${body}`)
    }
  })
})

// 员工 B：负责"用户注册"
ctx.plugin(function register(ctx) {
  // B 需要发邮件，直接找 A 的 service
  ctx.inject(['email'], (ctx) => {
    const result = ctx.email.send('alice@example.com', '欢迎注册！')
    // 同一个 ctx 内部直接调用，不需要传 HTTP / 消息队列
  })
})

// 启动公司（按依赖顺序激活所有员工）
ctx.start()
```

### 关键特性

| 特性 | 作用 |
|---|---|
| **plugin** | 一个独立的功能模块，通过 `ctx.plugin()` 注册 |
| **service** | 一个具名的服务（员工岗位），通过 `ctx.service('name', obj)` 注册 |
| **inject** | 声明依赖其他 service（"我需要 email 部门的支持"） |
| **event** | 异步消息（"老板来了！" / `ctx.emit` + `ctx.on`） |
| **effect** | 可逆操作（注册了就要能卸载，比如开了文件就要能关闭） |
| **fork** | 复制一个 ctx，给不同请求用（互不影响） |

### Cordis 与普通 import 的区别

```typescript
// ❌ 普通 import：写死的依赖
import { sendEmail } from './email'
sendEmail('alice@example.com', 'hi')
// 问题：想换邮件服务商？得改源码

// ✅ Cordis 服务：运行时注入的依赖
ctx.inject(['email'], (ctx) => {
  ctx.email.send('alice@example.com', 'hi')
})
// 想换邮件服务商？改 cordis.yml 配置就行，不用动代码
```

**DSH 里一切都是 plugin**——LLM、Tool、Agent Loop、UI、Session 全部通过 Cordis 组合，想替换任意一个不用改源码，改配置就行。

---

## 2.2 Bundle 是什么

**一句话：Bundle = 多个 Cordis plugin 的"打包集合"，可以一次性装到 ctx 里。**

### 生活比喻

继续用公司比喻：

- **单个员工** = 一个 plugin
- **一个部门**（如"前端部"包含 Vue 工程师、CSS 工程师、UI 设计师） = **bundle**

你可以一次招聘"整个前端部"（装一个 bundle），而不是一个一个员工地招。

### DSH 里的实际 bundle

```yaml
# dsh-web-app 这个 bundle 包含：
- dsh-base       # 基础能力（model adapter, tools, persistence...）
- dsh-agent-loop # Agent 主循环
- dsh-web-host   # Web 服务器
- dsh-web-client # Web 浏览器端
- dsh-session-*  # 会话持久化
- dsh-mcp-*      # MCP 集成
- dsh-credentials # 凭证管理
... 共 47 个 plugin
```

### Bundle 与 plugin 的关系

```yaml
# cordis.yml 中：
bundles:
  web:
    - "@deepseek-ai/dsh-base"
    - "@deepseek-ai/dsh-agent-loop"
    - "@deepseek-ai/dsh-web-app"   # 这个 bundle 内部又引用其他 bundle
```

### 与 npm 包的对比

| 维度 | npm 包 | DSH Bundle |
|---|---|---|
| 形态 | JavaScript 模块 | Cordis plugin 列表 + 配置 |
| 加载 | `import` | `ctx.plugin(...)` 自动 |
| 依赖 | build-time 静态 | runtime 动态注入 |
| 可替换 | 需要改源码 | 改配置即可 |

---

## 2.3 Profile 是什么

**一句话：Profile = "DSH 的一种运行模式"，决定装哪些 bundle、怎么启动。**

### 生活比喻

一家公司（DSH）有 **不同的工作场景**：

- **web 模式**：开门营业，前台 + 销售 + 客服 + 后厨全开（`dsh web`）
- **headless 模式**：只开后厨做菜，不开门（`dsh headless`）
- **acp 模式**：只开自动化测试部门（`dsh --profile acp`）

每个 profile 就是一份"今天要开哪些部门"的清单。

### DSH 内置 profile

| Profile | 命令 | 包含的 bundle | 用途 |
|---|---|---|---|
| **web** | `dsh web` | dsh-base + dsh-agent-* + dsh-web-* | 完整 Web UI（浏览器访问） |
| **headless** | `dsh --profile headless` | dsh-base + dsh-headless | 一次性任务，无 UI |
| **sdk** | `dsh --profile sdk` | dsh-sdk-* | 给外部程序用的 JSON-RPC 服务 |
| **sdk-minimal** | `dsh --profile sdk-minimal` | 精简 SDK tree | 最小化嵌入 |
| **acp** | `dsh --profile acp` | dsh-acp-* | Agent Client Protocol server |
| **desktop** | (Electron 自动) | dsh-base + dsh-desktop-* | 桌面壳 |

### Profile 与 Bundle 的关系

```text
DSH CLI
  └─ dsh web
       └─ profile = "web"
            └─ bundles = [dsh-base, dsh-agent-*, dsh-web-*]
                 └─ plugin = dsh-llm, dsh-tool-shell, dsh-session-*, ...
```

**配置文件** `cordis.yml` 的 `dsh.profile` 字段定义当前 profile 用哪些 bundle：

```yaml
# ~/.dsh/cordis.yml
dsh:
  profile: web
  bundles:
    web:
      - "@deepseek-ai/dsh-base"
      - "@deepseek-ai/dsh-agent-loop"
      - "@deepseek-ai/dsh-web-app"
```

### 自定义 profile

可以自己定义一个 profile，把多个 plugin 装在一起：

```yaml
# ~/.dsh/cordis.yml
dsh:
  profiles:
    my-coding-setup:
      bundles:
        - "@deepseek-ai/dsh-base"
        - "@deepseek-ai/dsh-agent-loop"
        - "github:my-org/my-tools"   # 自己的 bundle
        - "github:petpal-suite/pet-core"  # 我们要做的 petpal
```

```bash
# 启动自定义 profile
dsh --profile my-coding-setup
```

---

## 三者关系图

```text
┌──────────────────────────────────────────────┐
│  DSH CLI (dsh web / dsh --profile X)         │
│                                              │
│  选定 Profile ───────────┐                   │
│                          ▼                   │
│  ┌────────────────────────────────────┐      │
│  │  Profile: web                       │      │
│  │  - bundle 列表                      │      │
│  │  - 启动参数                         │      │
│  └─────────────┬──────────────────────┘      │
│                │                             │
│                ▼                             │
│  ┌────────────────────────────────────┐      │
│  │  Bundle A: dsh-base                 │      │
│  │  ┌──────────┐ ┌──────────┐          │      │
│  │  │ plugin 1 │ │ plugin 2 │ ...      │      │
│  │  └──────────┘ └──────────┘          │      │
│  └────────────────────────────────────┘      │
│  ┌────────────────────────────────────┐      │
│  │  Bundle B: dsh-agent-loop          │      │
│  │  ┌──────────┐ ┌──────────┐          │      │
│  │  │ plugin 3 │ │ plugin 4 │ ...      │      │
│  │  └──────────┘ └──────────┘          │      │
│  └────────────────────────────────────┘      │
│                                              │
│                │                             │
│                ▼                             │
│  ┌────────────────────────────────────┐      │
│  │  Cordis Context (单个容器)          │      │
│  │  - 所有 plugin 装在这里             │      │
│  │  - 通过 ctx.xxx 互相调用            │      │
│  │  - 单进程单实例                     │      │
│  └────────────────────────────────────┘      │
└──────────────────────────────────────────────┘
```

---

## 一句话总结

| 概念 | 一句话 | 对应生活 |
|---|---|---|
| **Cordis** | 插件容器 | 一家公司 |
| **plugin** | 容器里的一个功能模块 | 一个员工 |
| **service** | 一个具名能力，别的 plugin 可以 inject 它 | 一个岗位（如"客服"） |
| **bundle** | 一组 plugin 的打包清单 | 一个部门 |
| **profile** | 一种运行模式，决定装哪些 bundle | 公司的一个业务场景 |

---

## 实践：在 DSH 中写第一个 plugin

```typescript
// my-plugin/src/index.ts
import { Schema } from 'cordis'

export const name = 'my-plugin'

export interface Config {
  greeting: string
}

export const Config = Schema.object({
  greeting: Schema.string().default('Hello'),
})

export function apply(ctx) {
  // 注册一个 service
  ctx.service('myService', {
    greet(name: string) {
      return `${ctx.config.greeting}, ${name}!`
    }
  })

  // 订阅其他 service 的事件
  ctx.inject(['agent'], (ctx) => {
    ctx.on('agent/message', (msg) => {
      console.log(ctx.myService.greet(msg.user))
    })
  })
}
```

```yaml
# ~/.dsh/cordis.yml - 加载这个 plugin
dsh:
  profile: web
  bundles:
    web:
      - "@deepseek-ai/dsh-base"
      - "@deepseek-ai/dsh-agent-loop"
      - "@deepseek-ai/dsh-web-app"
      - "github:your-name/my-plugin"
```

```bash
# 启动
dsh web

# 查看当前加载的 plugin 树
dsh --profile web --dump-config
```

---

## 第 3 部分：Bundle 之间怎么协作

## 3.1 关键结论

**bundle 之间不直接"对话"，bundle 里的 plugin 通过 Cordis context 互相调用。bundle 只是 plugin 的"打包清单"。**

## 3.2 真实场景走一遍

**场景**：你让 Agent 写一个 `hello.py` 文件。

### 步骤 1：请求怎么进 DSH

```text
你（浏览器）输入"创建一个 hello.py"
    ↓
Web UI (React 应用)
    ↓ HTTP POST /api/agent/message
Web Host (Node.js 进程内的 HTTP server)
    ↓ 收到消息，调用 ctx.agent.handleMessage(...)
Agent Loop plugin (核心插件)
    ↓
```

### 步骤 2：Agent Loop 需要 LLM 来生成代码

Agent Loop plugin 不直接 import LLM，而是这样写：

```typescript
// Agent Loop plugin 的 apply 函数
export function apply(ctx) {
  ctx.service('agent', {
    async handleMessage(userInput: string) {
      // 调用 LLM
      const llmResponse = await ctx.llm.chat({
        model: 'deepseek-chat',
        messages: [{ role: 'user', content: userInput }]
      })

      // LLM 说"我要调用 fs_write 工具"
      // 调用工具
      for (const toolCall of llmResponse.toolCalls) {
        const result = await ctx.tools.invoke(toolCall.name, toolCall.args)
      }
    }
  })

  // 声明：我需要 llm 和 tools 才能工作
  ctx.inject(['llm', 'tools'], (ctx) => {
    // 这段代码在 llm 和 tools 都加载完后才执行
    console.log('Agent Loop 准备就绪')
  })
}
```

### 步骤 3：LLM 和 Tools 是哪来的？

它们是**不同 bundle 里的 plugin**，但都注册到**同一个 ctx**：

```typescript
// bundle: @deepseek-ai/dsh-llm (其他团队开发的 npm 包)
export function apply(ctx) {
  ctx.service('llm', {
    async chat(opts) {
      // 调用 DeepSeek/OpenAI API
      const resp = await fetch('https://api.deepseek.com/v1/chat', {
        method: 'POST',
        headers: { Authorization: `Bearer ${ctx.credentials.get('deepseek-prod')}` },
        body: JSON.stringify(opts)
      })
      return resp.json()
    }
  })
}

// bundle: @deepseek-ai/dsh-fs (又另一个团队开发的)
export function apply(ctx) {
  ctx.service('tools', {
    async invoke(name: string, args: any) {
      if (name === 'fs_write') {
        const fs = await import('fs/promises')
        await fs.writeFile(args.path, args.content)
        return { success: true }
      }
    }
  })
}
```

### 步骤 4：这些 plugin 怎么装到一起？

在 `cordis.yml` 的 profile 配置里列出来：

```yaml
dsh:
  profile: web
  bundles:
    web:
      - "@deepseek-ai/dsh-base"      # bundle A：包含 dsh-llm, dsh-credentials, dsh-settings
      - "@deepseek-ai/dsh-fs-local"  # bundle B：包含 dsh-tools, dsh-fs
      - "@deepseek-ai/dsh-agent"     # bundle C：包含 dsh-agent-loop
      - "@deepseek-ai/dsh-web-app"   # bundle D：包含 dsh-web-host, dsh-web-client
```

**DSH 启动时**：

```text
1. 解析 cordis.yml → 拿到 4 个 bundle
2. 把每个 bundle 展开成 plugin 列表（共 47 个）
3. 按依赖顺序，逐个调用 ctx.plugin(pluginA), ctx.plugin(pluginB)...
4. 每个 plugin 的 apply(ctx) 跑起来 → 注册 service / 声明 inject
5. 当一个 plugin 声明 inject ['llm', 'tools']，Cordis 等到 llm 和 tools 都注册完才执行它的回调
```

## 3.3 协作的完整图景

```text
┌─────────────────────────────────────────────────────┐
│  DSH Process                                          │
│                                                      │
│  Bundle A: dsh-base                                   │
│  ├─ plugin: dsh-llm                                  │
│  │   └─ ctx.service('llm', { chat() {} })           │
│  │                                                   │
│  ├─ plugin: dsh-credentials                          │
│  │   └─ ctx.service('credentials', { get() {} })    │
│  │                                                   │
│  Bundle B: dsh-fs-local                               │
│  └─ plugin: dsh-tools                                 │
│      └─ ctx.service('tools', { invoke() {} })        │
│                                                      │
│  Bundle C: dsh-agent                                  │
│  └─ plugin: dsh-agent-loop                            │
│      └─ ctx.inject(['llm', 'tools'], (ctx) => {       │
│           ctx.llm.chat(...)                           │
│           ctx.tools.invoke(...)                       │
│         })                                           │
│                                                      │
│  Bundle D: dsh-web-app                                │
│  └─ plugin: dsh-web-host                              │
│      └─ ctx.service('webServer', { listen() {} })    │
│                                                      │
│  ────── 全部 plugin 注册到同一个 ctx ──────           │
│                                                      │
│  ctx.llm       ←─── 来自 Bundle A                    │
│  ctx.tools     ←─── 来自 Bundle B                    │
│  ctx.agent     ←─── 来自 Bundle C                    │
│  ctx.webServer ←─── 来自 Bundle D                    │
│                                                      │
│  C 的 plugin 通过 ctx.llm 调用 A 的能力               │
│  B 不需要知道 C 的存在                                │
│  A 不需要知道 C 的存在                                │
└─────────────────────────────────────────────────────┘
```

**bundle 是打包单位，plugin 才是协作单位**。A bundle 里的 plugin 通过 ctx service 给所有其他 bundle 用，反过来也通过 ctx inject 声明自己的依赖。

## 3.4 三种协作模式

### 模式 1：同步调用（最常见）

```typescript
// plugin A 注册 service
ctx.service('llm', { chat() {} })

// plugin C 通过 ctx 调用
const result = await ctx.llm.chat(...)
```

### 模式 2：事件订阅（异步广播）

```typescript
// plugin A 广播事件
ctx.emit('session/message', { role: 'user', content: '...' })

// plugin D 订阅事件
ctx.on('session/message', (msg) => {
  console.log('收到消息', msg)
})
```

### 模式 3：依赖注入（延迟初始化）

```typescript
// plugin C 声明：我需要 llm 和 tools 才能工作
ctx.inject(['llm', 'tools'], (ctx) => {
  // 这段代码在 llm 和 tools 都就绪后才执行
  // 适合做"系统启动完成"后的初始化
})
```

## 3.5 对照表

| 比喻 | DSH | 说明 |
|---|---|---|
| **公司** | Cordis context | 整体容器 |
| **员工** | plugin | 协作单位 |
| **岗位说明书** | service | 别人能调用的能力 |
| **部门** | bundle | 一组员工的打包清单 |
| **部门预算表** | cordis.yml | 决定开哪些部门、装哪些 bundle |
| **业务场景** | profile | "今天开门营业 / 后厨备菜" |

**bundle 之间不直接"对话"，是 bundle 里的 plugin 通过 ctx 互相协作。** bundle 只是把相关 plugin 打成一包方便分发。

### 类比真实场景

```text
npm 生态：
  react + react-dom + redux + axios 各自是包
  它们通过 import 互相调用

DSH 生态：
  dsh-llm + dsh-tools + dsh-agent-loop 各自是 plugin
  它们通过 ctx 互相调用

npm 包是"代码模块"
DSH plugin 是"运行时服务"
```

---

## 第 4 部分：Agent Loop 详解

## 4.1 本质

**一句话：Agent Loop 是个"循环调度器"——它不只是把请求转给 LLM，而是 LLM 调工具 → 拿到工具结果 → 再调 LLM → 再调工具，直到 LLM 说"我搞定了"。**

### 你最初的理解（部分对）

```text
用户输入 → Agent Loop → LLM → 返回
```

### 实际是这样（更准确）

```text
用户输入
   ↓
Agent Loop：调用 LLM
   ↓
LLM 返回："我要调 fs_write 写 hello.py"
   ↓
Agent Loop：调用 tools.fs_write(...)
   ↓
工具返回："写好了"
   ↓
Agent Loop：把工具结果再喂给 LLM
   ↓
LLM 返回："我已经写好了，要继续吗？"
   ↓
Agent Loop：判断结束，把最终回复返回给用户
```

**关键：LLM 不只生成文字，还能"调用工具"。Agent Loop 是这个循环的调度者。**

## 4.2 Agent Loop 依赖的所有 service

Agent Loop 不是孤立组件，它需要 ctx 里这些 service 才能工作：

```text
Agent Loop 需要：
├─ ctx.llm          ← 调模型
├─ ctx.tools        ← 工具注册表（fs_write, shell, web_search...）
├─ ctx.session      ← 读写会话历史
├─ ctx.context      ← 注入额外上下文
├─ ctx.credentials  ← 拿 API Key
└─ ctx.presets      ← 当前 agent 的能力组合
```

**LLM 不知道有"工具"，只知道"我应该输出什么格式"。Agent Loop 解析 LLM 的输出，看到"调用工具"的指令就执行，再把结果喂回去。**

## 4.3 Agent Loop 在 DSH 里的位置

```text
dsh-agent bundle（核心 bundle）
├─ dsh-agent-loop        ← 主循环（这节的主角）
├─ dsh-agent-instructions ← 系统提示词生成
├─ dsh-agent-tool-presentation ← 工具描述格式化
├─ dsh-goal              ← 任务目标管理
├─ dsh-subagent          ← 子 Agent 调度
├─ dsh-compaction        ← 上下文压缩
└─ dsh-guard             ← 循环保护（防止死循环）
```

**`dsh-agent` 是一个 bundle，里面有 7 个 plugin 协同工作，agent-loop 只是其中之一。**

## 4.4 伪代码

```typescript
ctx.inject(['agent', 'llm', 'tools', 'session'], (ctx) => {
  ctx.agent.handleMessage = async (userInput) => {
    // 1. 把用户输入追加到 session
    await ctx.session.append({ role: 'user', content: userInput })

    // 2. 组装 prompt：system + 历史 + user
    const messages = await ctx.context.assemble()

    // 3. 调 LLM
    let response = await ctx.llm.chat({
      messages,
      tools: ctx.tools.list()
    })

    // 4. 处理 LLM 返回（可能包含工具调用）
    while (response.hasToolCalls) {
      // 执行每个工具调用
      const results = await Promise.all(
        response.toolCalls.map(call => ctx.tools.invoke(call.name, call.args))
      )
      // 把工具结果喂给 LLM 再调
      response = await ctx.llm.chat({ messages: [...messages, ...results] })

      // 防止死循环
      ctx.guard.checkIteration()
    }

    // 5. 把最终回复返回
    return response.content
  }
})
```

## 4.5 一句话更正

| 简化理解 | 准确版 |
|---|---|
| Agent Loop 接受请求，给 LLM 发请求，返回结果 | **Agent Loop 是循环调度器：循环"调 LLM → 执行工具 → 再调 LLM"，直到 LLM 不再要求调工具为止** |

**更深一层**：Agent Loop 不是 DSH 的"业务核心"，它是 DSH 把"用户输入 + LLM + 工具 + 会话"四个东西粘合起来的"胶水代码"。真正的"业务"是这些 service 各自实现的，Agent Loop 只是编排它们。

---

## 第 5 部分：Profile 详解

## 5.1 一句话区分

**Profile 决定了"DSH 这家公司的业务模式"——开门营业 / 后厨备菜 / 接外部订单 / 派员工驻场 / 接 Agent 同行的单。**

## 5.2 6 种 Profile 总览

| Profile | 谁在用 DSH？ | DSH 在哪跑？ | 主要场景 | 典型用户 |
|---|---|---|---|---|
| **web** | 人（通过浏览器） | 本地服务器 | 你想用 Web UI 操作 Agent | 开发者、终端用户 |
| **headless** | 脚本 / 定时任务 / CI | 本地进程 | 跑一次性任务，不开 UI | 自动化脚本、批处理 |
| **sdk** | 外部程序 | 本地服务（监听端口） | 别的程序想调 DSH 能力 | IDE 插件、外部 App |
| **sdk-minimal** | 外部程序（嵌入式） | 同进程 | 把 DSH 嵌进自己 App | 第三方工具嵌入 |
| **acp** | 别的 Agent | 本地服务（ACP 协议） | 别的 Agent 想控制 DSH | Agent-to-Agent 协作 |
| **desktop** | 人（通过原生窗口） | Electron 桌面壳 | 不想开浏览器 | 普通用户 |

## 5.3 三个维度理解区别

### 维度 1：UI 给不给？

```text
有 UI → web（浏览器）/ desktop（原生窗口）
无 UI → headless / sdk / sdk-minimal / acp
```

### 维度 2：调用方向

```text
人 → DSH：web / desktop（用户操作 Agent）
程序 → DSH：sdk / sdk-minimal / acp（其他程序调 Agent）
DSH → 任务：headless（DSH 自己跑任务）
```

### 维度 3：进程边界

```text
跨进程（HTTP / 端口 / IPC）：
  - web（HTTP 3080）
  - sdk（JSON-RPC over port）
  - acp（Agent Client Protocol）
  - desktop（Electron IPC）

同进程嵌入：
  - sdk-minimal（不挂 dsh-base，自带精简 SDK tree）
  - headless（一次性 runner，跑完即退出）
```

## 5.4 用大白话解释每个

### web — "开浏览器用 DSH"

```bash
dsh web
# 浏览器打开 http://127.0.0.1:3080
```

- 启动一个本地 HTTP 服务器
- 你用浏览器访问，点点鼠标跟 Agent 对话
- 适合：日常开发、调试、跟 Agent 协作

### headless — "让 DSH 跑个任务就退出"

```bash
dsh --profile headless "帮我把 /tmp/test.go 跑一遍测试"
```

- 不开 UI，不监听端口
- 跑完任务进程直接退出
- 适合：CI、定时任务、脚本里调 DSH

### sdk — "让别的程序用 DSH 的能力"

```bash
dsh --profile sdk --port 9000
# 别的程序通过 JSON-RPC 连 localhost:9000 调用 DSH
```

- 监听一个端口
- 提供 JSON-RPC API
- 适合：自己写 IDE 插件、App 想调 DSH

### sdk-minimal — "把 DSH 嵌进我的 App"

```typescript
// 在你的 Node App 里直接 import
import { DSH } from '@deepseek-ai/dsh-sdk-minimal'
const dsh = new DSH()
const result = await dsh.run('写个 hello world')
```

- **不挂 dsh-base**（web 那一套都不要）
- 自带精简 SDK tree
- 同进程嵌入，包体积小
- 适合：第三方工具想用 DSH 又不想带全套依赖

### acp — "让别的 Agent 控制 DSH"

```bash
dsh --profile acp --port 9100
# 别的 Agent 通过 Agent Client Protocol 连接
```

- 专门给 Agent-to-Agent 通信用
- 协议是 ACP（Agent Client Protocol），不是 JSON-RPC
- 适合：多 Agent 协作场景、Agent 编排平台

### desktop — "不开浏览器，用桌面 App"

```bash
# 不是命令启动，是 Electron 应用启动时自动加载
# 用户双击桌面图标
```

- 桌面壳（Electron / Tauri）
- **不开 HTTP 端口**（避免冲突），用 IPC
- Web UI 嵌进原生窗口
- 适合：不想开浏览器的普通用户

## 5.5 实际选哪个？

| 你的情况 | 推荐 Profile |
|---|---|
| 我想跟 Agent 聊天、调试 | `web` |
| 我想跑个 CI / 写个脚本 | `headless` |
| 我想做个 IDE 插件调 DSH | `sdk` |
| 我想把 DSH 嵌进我的 App | `sdk-minimal` |
| 我想让别的 Agent 控制 DSH | `acp` |
| 我想给普通用户做个客户端 | `desktop` |

---

## 第 6 部分：Multi-Agent 机制

## 6.1 一句话

**DSH 的多 Agent 是"父子任务树"——主 Agent 决定"这个事太复杂，我要派个子 Agent 去干"，子 Agent 完成后回来汇报。**

## 6.2 三种调度模式

| 模式 | 含义 | 典型场景 |
|---|---|---|
| **单 Agent 串行** | 一个 Agent 循环到结束 | 简单任务 |
| **多 Agent 串行** | 第一个 Agent 完成后，结果传给第二个 | 流水线（写代码 → 跑测试 → 修 bug） |
| **多 Agent 并行 / 嵌套** | 主 Agent 同时派多个子 Agent | 调研（同时搜 3 个资料源） |

## 6.3 在 DSH 里的实现

```text
dsh-agent bundle 里专门有：
├─ dsh-subagent         ← 子 Agent provider + delegation tools
├─ dsh-goal            ← 任务目标生命周期
└─ dsh-goal-round-driver ← 多轮驱动
```

**核心机制**：

```typescript
// dsh-subagent plugin 注入两个工具到 ctx.tools
ctx.service('tools', {
  // 主 Agent 看到的工具
  invoke(name, args) {
    if (name === 'delegate_task') {
      // 1. fork 一个新的 Cordis ctx（隔离）
      const subCtx = ctx.fork()
      // 2. 启动子 Agent
      const subAgent = new AgentLoop(subCtx)
      // 3. 派任务
      return subAgent.run(args.task)
    }
    if (name === 'spawn_parallel') {
      // 并行启动多个子 Agent
      return Promise.all(args.tasks.map(t => delegateTask(t)))
    }
  }
})
```

**关键点**：子 Agent 是**独立 Cordis ctx（fork 出来的）**，有自己的 session、自己的工具集、自己的状态。完成后把结果返回给父 Agent。

## 6.4 父子 Agent 协作流程

```text
用户输入："帮我调研 3 个竞品"
    ↓
主 Agent 看到任务复杂，决定拆分
    ↓
ctx.tools.invoke('spawn_parallel', {
  tasks: [
    '调研 A 竞品的优势',
    '调研 B 竞品的定价',
    '调研 C 竞品的技术栈'
  ]
})
    ↓
DSH fork 3 个子 ctx，并行启动 3 个子 Agent
    ↓
子 Agent A / B / C 各自独立工作（独立 session、独立工具）
    ↓
3 个子 Agent 完成后，结果合并回主 Agent 上下文
    ↓
主 Agent 拿到三份结果，综合输出给用户
```

## 6.5 与单 Agent 的区别

| 维度 | 单 Agent | 多 Agent |
|---|---|---|
| Cordis ctx 数 | 1 个 | 主 + N 个 fork 出来的子 |
| Session | 一个共享 | 每个 Agent 独立 |
| 工具集 | 一致 | 每个 Agent 可不同（按 preset） |
| 上下文 | 串行累积 | 主 Agent 上下文 + 子 Agent 结果 |
| 适用 | 简单任务 | 复杂任务、需要隔离或并行 |

---

## 第 7 部分：Skill / MCP / Tool 三者关系

## 7.1 核心结论（一句话）

**Tool（工具）是 DSH 里的"一等公民"，所有东西——内置工具、Skill、MCP——最终都注册到同一个 `ctx.tools` 上。Skill 和 MCP 不是和 tool 平级的概念，是 tool 的不同"来源"。**

## 7.2 三个的真实层级关系

```text
ctx.tools（统一的工具注册表，Agent Loop 唯一看的）
│
├─ 内置工具（dsh-fs-local / dsh-shell 等 bundle 提供）
│   ├─ fs_read / fs_write / shell ...
│
├─ Skill（dsh-skill bundle 提供）
│   ├─ 注册一个特殊的"元工具"叫 skill
│   │   作用：让 Agent 加载技能包
│   └─ 技能包本身 = 一组"提示词模板 + 可选工具集"
│
└─ MCP（dsh-mcp bundle 提供）
    └─ 把外部 MCP server 的工具桥接过来，名字加 mcp:server: 前缀
```

**关键点**：从 Agent Loop 视角看，它只调 `ctx.tools.invoke(name, args)`，不在乎这个工具来自哪里。

## 7.3 Skill 真实实现

### 包结构

```text
packages/skill/                      ← 独立 bundle，不是 dsh-agent 的一部分
├── skill/                           ← 技能 registry（注册中心）
├── skill-filesystem/                ← 从文件系统发现技能
├── skill-badge/                     ← UI 徽章（默认关闭）
└── tool-skill/                      ← 注册"加载技能"这个工具到 ctx.tools
```

### 关键：Skill 注册的是"一个元工具"

```typescript
// tool-skill plugin 的核心
ctx.service('tools', {
  // 注册一个名为 'skill' 的工具到 ctx.tools
  register({
    name: 'skill',
    description: '加载一个技能包（按名称 /name 调用）',
    parameters: {
      name: 'string'
    },
    invoke: async (args) => {
      // 1. 从 ctx.skills registry 找技能
      const skill = await ctx.skills.load(args.name)
      // 2. 把技能的 instructions 拼到 system prompt
      ctx.context.injectInstructions(skill.instructions)
      // 3. 把技能的工具集临时加到 ctx.tools
      ctx.tools.registerNamespace(skill.tools)
      return { success: true, loaded: skill.name }
    }
  })
})
```

### Skill 技能包的内容

```typescript
// 一个 skill 包 = 4 个东西
{
  name: 'frontend-react',
  description: '前端 React 开发专家',
  instructions: '你是 React 专家，用 TypeScript + 函数组件 + hooks...',
  tools: [fs_read, fs_write, search_code],   // 可选：技能专有工具
  examples: [{ input: '...', output: '...' }]  // 可选：few-shot
}
```

## 7.4 Skill 存放目录（5 个扫描根）

DSH 启动时会扫描 5 类目录，按 rank 合并（rank 越大优先级越高，后扫的覆盖同名 skill）：

| 优先级 (rank) | 来源 | 默认路径 |
|---|---|---|
| 100 | project-dsh | `<项目根>/.dsh/skills/` |
| 200 | project-agents | `<项目根>/.agents/skills/` |
| 300 | custom | 配置里的 `customSkillDirs` |
| 400 | user-dsh | `~/.dsh/skills/` |
| 500 | user-agents | `~/.agents/skills/` |
| 600 | bundled | 编译时内嵌（可选） |

**关键路径变量**：

- `projectRoot` = 当前目录往上找最近的 `.git` 父目录；找不到就用 cwd
- `dshHome` = `$DSH_HOME` 环境变量 或 `~/.dsh`（**跳过 `.system` 子目录**）
- `agentsHome` = `$DSH_AGENTS_HOME` 环境变量 或 `~/.agents`

## 7.5 用户怎么安装一个 Skill

**没有 install 命令**！直接文件系统操作：

```bash
# 方式 A：用户级（最常见）
mkdir -p ~/.dsh/skills/my-skill
cat > ~/.dsh/skills/my-skill/SKILL.md <<'EOF'
---
name: my-skill
description: 我自己写的 skill
whenToUse: 当用户问前端问题时
---

# My Skill

你是前端开发专家...
EOF

# 方式 B：项目级（跟着项目走）
mkdir -p .dsh/skills/my-skill
# 写 SKILL.md

# 方式 C：放在 agents 通用目录
mkdir -p ~/.agents/skills/my-skill
```

**DSH 通过 chokidar 自动监听**（depth=1），文件一写好就生效，不需要重启。

## 7.6 SKILL.md 两种形态

```text
# 形态 1：目录包（推荐）
~/.dsh/skills/my-skill/
└── SKILL.md          ← 唯一入口

# 形态 2：平铺文件
~/.dsh/skills/my-skill.md

# 注意：不扫描嵌套子目录
# ❌ 不会识别：~/.dsh/skills/my-skill/sub/SKILL.md
```

## 7.7 SKILL.md 格式

```markdown
---
name: my-skill                # 必填，kebab-case
description: 一句话描述       # 必填
whenToUse: 何时使用           # 可选
metadata:                    # 可选
  author: your-name
disable-model-invocation: false  # 可选：是否禁止模型自动调
user-invocable: true            # 可选：用户能否 /name 直接调
---

# 这里是 skill 的正文

你是 React 专家，遵循以下原则：
- 用 TypeScript
- 用函数组件 + hooks
- ...
```

**布尔字段**：`true/false`、`yes/no`、`on/off`、`1/0` 都接受（大小写不敏感）。拼错就 warn + 整个 skill 丢弃，**不静默**。

## 7.8 加载时机（两层分离）

| 层 | 何时 | 干什么 |
|---|---|---|
| **Catalog（目录摘要）** | 启动 / 文件变更 | 解析 frontmatter，缓存到 KV（轻量） |
| **Body（正文）** | 每次 Agent 调用 skill 工具 | 重新读完整文件 |

**优势**：frontmatter 改了立即生效；正文改了不影响已缓存的 catalog 摘要。

## 7.9 调用方式

```text
# 方式 1：模型自动调用（默认）
Agent 看到 description 匹配用户需求 → 自动调 ctx.tools.invoke('skill', { name: 'my-skill' })

# 方式 2：用户在 Web UI 里 /skill-name 直接调（user-invocable: true 时）
用户在聊天框输入 /my-skill 写代码
```

## 7.10 Skill 已知限制

- ❌ **不支持版本管理**——没有 `version` 字段、没有 hash、没有 revision 协议
- ❌ **不扫描嵌套目录**——一个 skill 就是一个 SKILL.md
- ❌ **项目级按最近 `.git` 父目录**——monorepo 子项目识别不了
- ❌ **格式错误 warn 跳过**——模型看不到逐条诊断
- ❌ **缺失根目录需轮询探测**——延迟和可靠性有 trade-off

## 7.11 MCP 真实实现

### 包结构

```text
packages/mcp/                     ← 独立 bundle
├── mcp-client/                   ← 连接一个 MCP server，桥接它的工具
└── mcp-resources/                ← 跨 MCP server 的共享资源工具
```

### 关键：MCP 工具注册到 ctx.tools 时加 server 前缀

```typescript
// mcp-client plugin 的核心
ctx.service('mcp', {
  async connect(serverConfig) {
    // 1. 启动 MCP 协议连接（stdio / HTTP）
    const client = new McpClient(serverConfig)
    await client.connect()

    // 2. 列出外部工具
    const remoteTools = await client.listTools()

    // 3. 把每个外部工具"包装"后注册到 ctx.tools
    for (const tool of remoteTools) {
      ctx.tools.register({
        name: `mcp:${serverConfig.name}:${tool.name}`,  // ← 加前缀
        description: tool.description,
        parameters: tool.inputSchema,
        invoke: async (args) => {
          // 转发调用到外部 MCP server
          return await client.callTool(tool.name, args)
        }
      })
    }
  }
})
```

## 7.12 用户配置 MCP

在 `cordis.yml` 配 `mcp-client` 条目：

```yaml
mcp:
  clients:
    github:
      transport: stdio
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_TOKEN: "${credentials:github}"
    filesystem:
      transport: stdio
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
```

## 7.13 Agent 看到的工具列表

```text
# Agent 视角：所有工具在一个平面上
ctx.tools.list() →
  - fs_read              ← 内置
  - fs_write             ← 内置
  - shell                ← 内置
  - skill                ← tool-skill 注册的元工具
  - mcp:github:create_issue    ← MCP
  - mcp:github:list_repos      ← MCP
  - mcp:filesystem:read_file   ← MCP
```

## 7.14 Agent Loop 视角的真相

Agent Loop **不知道**有 skill 和 mcp 的存在。它只看到：

```typescript
ctx.tools.list()  // 给我所有工具的描述
ctx.tools.invoke(name, args)  // 调一个工具
```

**Agent Loop 不区分**：

```typescript
// 内置工具
await ctx.tools.invoke('fs_write', { path: '/tmp/a.txt', content: 'hi' })

// Skill 元工具
await ctx.tools.invoke('skill', { name: 'frontend-react' })

// MCP 工具
await ctx.tools.invoke('mcp:github:create_issue', { title: 'bug', body: '...' })
```

三者对 Agent Loop 完全透明。

## 7.15 三者关键边界规则

| 维度 | Skill | MCP |
|---|---|---|
| **是不是独立的"类别"** | ❌ 是 ctx.tools 里的一个元工具（叫 `skill`） | ❌ 是 ctx.tools 里的命名空间（`mcp:server:tool`） |
| **是不是内置插件** | 是独立 bundle（dsh-skill），但只注册一个元工具到 ctx.tools | 是独立 bundle（dsh-mcp），把外部工具注册到 ctx.tools |
| **加载时机** | 运行时按需（Agent 调用 skill 工具时加载） | 启动时连接（DSH 启动时桥接所有配置的 MCP server） |
| **作用域** | 调用 skill 工具后，该 session 内技能可用 | 只对配置了对应 server 的用户可见（per-server scope） |
| **内容** | instructions + 可选 tools + examples | 纯工具（外部进程提供） |
| **配置位置** | 目录（~/.dsh/skills/） | cordis.yml 的 mcp.clients 字段 |

## 7.16 Tool / Skill / MCP 一图终结

```
ctx.tools（Agent Loop 唯一看的统一工具表）
│
├─ 内置（dsh-base 等 bundle 直接注册）
│   ├─ fs_read / fs_write / shell ...
│
├─ Skill 注册的工具（dsh-skill bundle 注册 1 个元工具）
│   └─ skill   ← 调它会加载 skill 包，临时注入 instructions + 工具
│
└─ MCP 桥接的工具（dsh-mcp bundle 启动时连接外部 server）
    └─ mcp:github:create_issue / mcp:filesystem:read_file ...
```

| 维度 | Tool（内置） | Skill | MCP |
|---|---|---|---|
| **是不是独立 bundle** | 在 dsh-base / dsh-fs-local 等 | dsh-skill | dsh-mcp |
| **注册到 ctx.tools 几个** | 多个（每个工具一个） | 1 个（元工具 `skill`） | N 个（每个外部工具一个） |
| **配置位置** | 写在 bundle 代码里 | 文件系统目录（SKILL.md） | cordis.yml |
| **加载时机** | 启动 | 运行时按需 | 启动时连接 |
| **核心作用** | 直接能力 | 加载专家知识 | 桥接外部进程 |

## 7.17 一句话总结

> **Tool 是 DSH Agent 的"肌肉"（做什么）。Skill 是"临时专家大脑"（怎么想）。MCP 是"外部肌肉接入"（借别人的手）。三者最终都长在同一个 ctx.tools 表上。**

---

## 第 8 部分：Instructions / AGENTS.md 加载机制

## 8.1 一句话

**DSH 把 AGENTS.md / CLAUDE.md 等指令文件当成 user-role 消息注入会话历史，按 broad-to-specific 顺序合并，touch 触发刷新，digest 比对避免重复注入——比 OpenClaw / Claude Code 更精细（双文件名兼容 + .local 覆盖 + 持久化到会话）。**

## 8.2 加载的文件名

### 基础候选（默认）

DSH **同时加载**两个文件名（基于源码 `instructionFileCandidates` 默认值）：

```yaml
instructionFileCandidates: ['AGENTS.md', 'CLAUDE.md']
```

这是 DSH 与 OpenClaw（只用 AGENTS.md）、Claude Code（只用 CLAUDE.md）的关键区别——**DSH 有意兼容两个生态**。

### 本地覆盖（仅项目级）

```yaml
localInstructionFileCandidates: ['AGENTS.local.md', 'CLAUDE.local.md']
```

注意：**中间只有一个点** `AGENTS.local.md`，不是 `AGENTS..md` 或 `AGENTS_local.md`。

### 用户级只认 AGENTS.md

```yaml
# ~/.dsh/AGENTS.md    ← 用户级（被加载）
# ~/.dsh/CLAUDE.md    ← 用户级（不加载）
```

**用户级只认 AGENTS.md**，不认 CLAUDE.md——推测是避免 OpenClaw 和 Claude Code 在用户全局互相干扰。

### 不支持的文件名

- ❌ `.claude/rules/` 目录（Claude Code 的另一种约定）
- ❌ `@path` 导入

## 8.3 扫描目录

```
用户级（$DSH_HOME 或 ~/.dsh/）
    ↓
项目根（向上找最近的 .git 父目录；找不到用 cwd）
    ↓
项目根 → cwd 中间整条目录路径链
```

**关键：每个目录都查一遍**，从用户级一路到 cwd 当前目录。

## 8.4 优先级与合并规则

### 顺序：broad-to-specific（宽到窄）

```text
1. 用户级 ~/.dsh/AGENTS.md
    ↓
2. 项目根 AGENTS.md / CLAUDE.md
    ↓
3. 项目根/src AGENTS.md / CLAUDE.md
    ↓
4. 项目根/src/components AGENTS.md / CLAUDE.md
    ↓
5. 当前 cwd AGENTS.md / CLAUDE.md
```

### 合并规则

| 规则 | 说明 |
|---|---|
| **更具体覆盖更宽泛** | 深目录的 AGENTS.md 优先于浅目录 |
| **同级去重** | trim 后字节相同的兄弟文件只渲染一次 |
| **空链贡献 0 token** | 链上没文件就跳过 |
| **超 `maxBytes`** | 先丢宽泛文件，再截断具体文件 |
| **超 `maxSourceBytes`** | 单文件渲染前字节上限 |

### Local overlay 优先级

```text
项目根/AGENTS.md          ← 项目级 base
项目根/AGENTS.local.md    ← 项目级 override（覆盖 base）
项目根/src/AGENTS.md      ← 子目录 base
项目根/src/AGENTS.local.md ← 子目录 override（覆盖）
```

## 8.5 注入位置和格式

### 注入到 user-role（不是 system prompt）

```text
首个请求：
┌──────────────────────────────────┐
│ claimed messages（用户上下文）    │
├──────────────────────────────────┤
│ <插件自有 wrapper>                │  ← AGENTS.md / CLAUDE.md 在这里注入
│   Instructions from: /path/...   │
│   ...指令内容...                 │
│ </插件自有 wrapper>               │
├──────────────────────────────────┤
│ 真正的 user message              │
└──────────────────────────────────┘
```

### 为什么是 user-role 不是 system-role？

| 维度 | system-role | user-role（DSH 选择） |
|---|---|---|
| 持久化 | 易丢失 | 进会话历史，可重放 |
| 压缩 | 不参与 | 可压缩、可截断 |
| Resume | 不恢复 | 自动恢复 |
| 修改文件后 | 不会刷新 | digest 比对自动刷新 |

**核心**：user-role 让指令文件"像对话一样"参与生命周期管理。

## 8.6 刷新触发条件

DSH **不持续监听** AGENTS.md 改动。只在三种时机刷新：

| 触发时机 | 行为 |
|---|---|
| **首次请求** | 注入完整 baseline（持久化 user message） |
| **`read` / `write` / `edit` 工具到达更深目录** | touch 冒泡，触发重新发现 |
| **Session resume** | 调和可见 baseline |
| **进入 pre-step** | 恢复被遮蔽的 baseline |

### 已知坑

- ❌ `bash cd 切目录` 不触发发现
- ❌ 没装 chokidar，依赖 touch 驱动
- ❌ Symlink 跨信任边界会被跟随（可能泄漏仓库外内容）

## 8.7 与其他上下文的拼装顺序

DSH 把所有上下文注入按以下顺序组装（用户视角）：

```text
System Prompt（dsh-base 默认）
    ↓
Tools 描述（ctx.tools.list() → 转 OpenAI/Anthropic 格式）
    ↓
Skill Instructions（加载的 skill 包正文）
    ↓
Subagent 注入（ctx.subagent 配置）
    ↓
其他 opt-in 上下文：
  - time-context（当前时间）
  - tmux-context（agent tmux 位置）
  - file-reference（@file mention 解析）
  - session-reference（其他会话快照）
    ↓
AGENTS.md / CLAUDE.md 注入（user-role）
    ↓
真实 user message
```

**特别注意**：`agent-instructions` 是 **`dsh-base` 默认包含**的，其他上下文插件都是 opt-in。profile patch 可以禁用。

## 8.8 与 OpenClaw / Claude Code 对比

| 维度 | Claude Code | OpenClaw | DSH |
|---|---|---|---|
| **文件名** | `CLAUDE.md` | `AGENTS.md` | `AGENTS.md` + `CLAUDE.md`（双兼容） |
| **位置** | 项目根 + 子目录 + 用户级 | 项目根 + 子目录 | 项目根 + 子目录 + 用户级 |
| **注入位置** | system prompt | system prompt | **user-role message** |
| **刷新机制** | 每次请求重读 | 每次请求重读 | **touch 触发 + digest 比对** |
| **作用域** | per-cwd | per-cwd | per-cwd + per-session 持久化 |
| **local 覆盖** | ❌ | ❌ | ✅ `AGENTS.local.md` / `CLAUDE.local.md` |
| **用户级文件名** | `CLAUDE.md` | `AGENTS.md` | 只认 `AGENTS.md`（避免冲突） |

## 8.9 完整示例

假设项目结构：

```text
~/projects/my-app/
├── .git/
├── AGENTS.md                    # 项目级 base：项目约定
├── AGENTS.local.md              # 项目级 override：个人偏好
├── src/
│   ├── AGENTS.md                # src 级：前端规范
│   └── components/
│       └── AGENTS.md            # 最深：组件开发规范
```

你在 `src/components/` 跑 `dsh web` 并问"写个按钮"：

```text
注入顺序（user-role）：
1. ~/.dsh/AGENTS.md                                    [全局偏好]
2. ~/projects/my-app/AGENTS.md                         [项目约定]
3. ~/projects/my-app/AGENTS.local.md                   [个人偏好，覆盖 2]
4. ~/projects/my-app/src/AGENTS.md                     [前端规范]
5. ~/projects/my-app/src/components/AGENTS.md          [组件规范，最具体]
```

**最终 LLM 看到**：5 段指令按顺序拼接，深层覆盖浅层同名条目。

## 8.10 关键配置

```yaml
# 在 cordis.yml 的 agent-instructions 配置里
instructions:
  maxBytes: 65536              # 完整 baseline 字节上限（dsh-base 默认）
  maxSourceBytes: 1048576      # 单文件上限
  projectRootMarkers: [".git"] # 项目根标记
  instructionFileCandidates: ["AGENTS.md", "CLAUDE.md"]
  localInstructionFileCandidates: ["AGENTS.local.md", "CLAUDE.local.md"]
  dshHome: "~/.dsh"            # 用户级目录
```

## 8.11 一句话总结

> **DSH 把 AGENTS.md / CLAUDE.md 当成 user-role 消息注入会话，按 broad-to-specific 顺序合并，touch 触发刷新，digest 比对避免重复注入——比 OpenClaw / Claude Code 更精细（双文件名兼容 + .local 覆盖 + 持久化到会话）。**

---

## 第 9 部分：Skill 加载顺序（简洁版）

## 9.1 一句话

**全局目录扫一遍 → 项目目录从根到 cwd 扫一遍 → 同名按"近的覆盖远的"合并 → 全部按名字字母序排序后给模型。**

## 9.2 加载顺序（broad → specific）

```text
1. 全局目录（~/.dsh/skills/ 和 ~/.agents/skills/）
   ↓
2. 项目根（向上找最近的 .git 目录）
   ↓
3. 项目根下的子目录
   ↓
4. ... 一路到当前工作目录 cwd
```

**越具体的目录（越深）覆盖越宽泛的目录（越浅）**。

## 9.3 加载位置

模型看到的是这个结构（注入在 user-role message 里）：

```xml
<available_skills>
  <skill>
    <name>code-review</name>
    <description>对代码进行审查...</description>
  </skill>
  <skill>
    <name>frontend-react</name>
    <description>前端 React 开发专家...</description>
  </skill>
</available_skills>
```

**注意**：这只是"目录"，只有 name + 简介。**模型需要主动调 `skill` 工具（或用户输入 `/skill-name`）才能看到完整内容**。

## 9.4 项目是不是 workspace？

**是的**，DSH 用"最近的 .git 父目录"作为 workspace 边界。

```bash
你在 /home/user/projects/my-app/src/components 跑 dsh
    ↓
向上找 .git：/home/user/projects/my-app/.git ✓
    ↓
DSH 认这个 my-app 目录是你的 workspace
```

**已知坑**：

- ❌ 没有 `.git` 时回退到当前 cwd
- ❌ monorepo 子项目识别不了（只看最近的一个 `.git`）
- ❌ 项目级 skill 没有独立配置文件，纯靠目录约定

## 9.5 全局 vs 项目的关系

| 层级 | 路径 | 隔离 |
|---|---|---|
| **全局** | `~/.dsh/skills/` | 跨项目共享 |
| **项目** | `<workspace>/.dsh/skills/` | 只在当前项目有效 |
| **当前目录** | `<workspace>/<cwd>/.dsh/skills/` | 跟着 cwd 走 |

**同名冲突**：项目里的 skill **覆盖**全局 skill（因为更具体）。

## 9.6 一句话总结

> **Skill 加载 = 全局扫 + 项目从根到 cwd 扫 + 近覆盖远 + 按名字排序输出 catalog。Catalog 只是目录，正文要主动加载才生效。**
https://deepseek-harness.github.io/deepseek-harness/reference/subsystems/skills#%E6%9C%AC%E5%9C%B0%E5%8F%91%E7%8E%B0%E4%BC%98%E5%85%88%E7%BA%A7
---

## 参考链接

- 官方仓库：https://github.com/deepseek-ai/deepseek-harness
- 官方文档：https://deepseekharness.online/
- Cordis 元框架：https://github.com/deepseek-ai/cordis
- 插件市场：https://www.dsh.so/
