# 最终方向决策报告（v2 —— 一键唤醒 DSH 工作台）

> **决策日期**：2026-09-17
> **修订日期**：2026-09-21（v2：从"桌宠+工作台"收缩为"一键式唤醒 DSH"）
> **状态**：已确认，待执行

---

## 一句话定位

> 基于 **DSH（DeepSeek Harness）** 原生底座，构建一套 **petpal-suite** 插件集合，核心价值是**一键式唤醒 DSH 工作台**。不再实现独立桌宠。
>
> **核心目标不再是"再造一个工作台"，而是"让 DSH 更顺手地出现在你面前"。**

---

## 关键方向变更（v1 → v2）

| 维度 | v1（已废弃方向） | v2（当前方向） |
|---|---|---|
| **产品核心** | 桌宠（port-adapter 多终端桌宠）→ 工作台 | **一键式唤醒 DSH Web 工作台** |
| **桌宠** | 桌宠是产品主体（状态机/动画/多终端） | **不实现独立桌宠** |
| **工作台** | 自己搭工作台（workbench Tab） | **DSH 原生 Web 就是工作台**，我们只做入口 |
| **差异化** | port-adapter 架构 + 桌宠 | **全局唤起 + 零学习成本入口**（薄壳） |
| **Tauri 角色** | 桌宠壳 + 工作台壳 | **薄壳入口**：全局快捷键 → 拉起/聚焦 DSH Web |

**一句话**：v2 = "Cmd+快捷键 → 打开 DSH"，别人做桌宠、做工作台，我们做**那把最快的钥匙**。

---

## 为什么砍掉独立桌宠

1. **时间/收益比低**：多套终端适配器（Tauri/Web/Mobile）+ 状态机 + 动画 + 鼠标穿透，工程量巨大，而"桌宠"本身不解决你**快速使用 DSH** 的核心诉求。
2. **生态已被占**：dsh.so / GitHub 上已有 10+ 桌宠（sereinmono、FenyxHuang、xiaoshihou514…），纯桌宠打不过。
3. **真正的痛点是"唤起"**：DSH 默认要 `dsh web` 起服务 + 浏览器开标签页，路径太长。**一键唤起** 才是别人没做好的入口价值。
4. **架构更简单**：两层架构仍然成立，但核心层从"桌宠状态机"瘦身为"唤起/生命周期/事件订阅"，适配器层从"终端渲染"瘦身为"快捷键/打开方式"。

---

## 产品形态

```
┌──────────────────────────────────────────────────────┐
│  petpal-suite（DSH 插件集合 / monorepo）                │
│                                                      │
│  ├─ pet-core           核心逻辑（无终端 UI 依赖）      │
│  │   ├─ launcher.ts    唤起/生命周期状态机             │
│  │   ├─ dsh-bridge.ts  DSH 事件订阅（判断是否已起）    │
│  │   └─ ports/        LauncherPort 接口（核心定义）    │
│  │                                                    │
│  ├─ pet-adapter-tauri  Tauri 薄壳（v0.1 唯一）         │
│  │   ├─ 全局快捷键（Cmd+Space / 自定义）               │
│  │   ├─ 拉起 DSH Web（起服务 / 聚焦已有实例）          │
│  │   └─ 系统托盘（可选：最小化到托盘常驻）             │
│  │                                                    │
│  ├─ pet-adapter-web    Web 适配器（Phase 3，可选）     │
│  └─ pet-launcher       CLI / 入口包装                  │
│                                                      │
│  配套 DSH 插件：                                       │
│  └─ petpal-dsh-plugin   注册到 DSH，暴露唤起/状态事件   │
└──────────────────────────────────────────────────────┘
         ↓ 薄壳唤起 DSH
┌──────────────────────────────────────────────────────┐
│  DSH Harness（DeepSeek AI 原生底座）                  │
│  ├─ Cordis 元框架（一切皆插件）                       │
│  ├─ Agent Loop / Tools / Skills / MCP                 │
│  └─ Web UI（默认 127.0.0.1:3080）= 工作台本体         │
└──────────────────────────────────────────────────────┘
```

**核心交互**：

```text
按下全局快捷键（Cmd+Space 等）
    ↓
pet-core 检查 DSH 服务状态：
    ├─ 未启动 → 拉起 `dsh web`（后台）
    └─ 已启动 → 聚焦已有实例
    ↓
打开/聚焦 DSH Web 工作台（浏览器或内嵌 WebView）
    ↓
用户直接开始对话 / 使用 Agent —— 完
```

---

## 关键技术选型

| 维度 | 选择 | 理由 |
|---|---|---|
| 原生底座 | **DSH Harness** | 10 万+ stars、Cordis 插件生态、Agent 能力开箱即用 |
| 薄壳 | **Tauri 2 + Rust** | 体积小（5MB）、启动快、跨平台、原生全局快捷键 |
| 语言 | **TypeScript** | 与 DSH / Cordis 一致 |
| 状态同步 | **Cordis 插件 + HTTP/事件** | 判断 DSH 是否已运行、汇报唤起状态 |
| 核心/适配器通信 | **TypeScript 接口（port-adapter）** | 核心与终端解耦 |
| 分发 | **DSH 插件市场 + GitHub Releases** | 两条分发路径 |
| License | **MIT** | 与 DSH 一致 |

---

## 两层架构（核心关键：避免耦合过深）

### 核心原则：依赖方向永远单向

```
┌─────────────────────────────────────────────┐
│  核心层 pet-core（Domain / 业务 / 插件）      │
│  · 纯逻辑：唤起状态机、事件模型、端口契约     │
│  · 只依赖 DSH（Cordis），零终端依赖          │
└───────────────▲─────────────────────────────┘
                │ ① core 定义 Port（接口契约）
                │ ② adapter 实现 Port
                │ ③ 事件反向流（adapter→core）
┌───────────────┴─────────────────────────────┐
│  适配器层 pet-adapter-*（终端实现）           │
│  · Tauri / Web / CLI ...                    │
│  · 只做终端专有的事（快捷键/打开方式/托盘）    │
│  · 依赖 pet-core，但 pet-core 不认识它       │
└─────────────────────────────────────────────┘
```

### 层边界铁律

| 判据 | 核心层 pet-core | 适配器层 pet-adapter-* |
|---|---|---|
| 跟"终端长什么样"无关的纯逻辑 | ✅ 唤起状态机、事件模型 | ❌ |
| 跟 DSH 深度集成 | ✅ 订阅 Session/事件、检查服务状态 | ❌ |
| 跟"具体快捷键/打开方式/托盘"有关 | ❌ 只定义"要唤起" | ✅ Tauri 全局快捷键、起服务 |
| 跟"浏览器/WebView/窗口"有关 | ❌ | ✅ 打开/聚焦 DSH Web |
| 通知是终端能力 | ❌ 只定义"要通知什么" | ✅ 系统通知怎么弹 |

**铁律**：
- 核心层**绝不**出现 window / 快捷键注册 / Tauri IPC / DOM / 托盘
- 核心层**只**定义抽象信号（`onActivate` / `onServiceStateChange`）
- 适配器可自由用 Tauri/Web 技术，但**不写业务状态逻辑**

### 层间通信（两个单向契约）

**① 核心层定义 Port（适配器实现）—— 核心 → 适配器**

```ts
// pet-core/src/ports/launcher-port.ts
export interface LauncherPort {
  readonly capabilities: {
    globalHotkey: boolean      // 是否支持全局快捷键
    systemTray: boolean        // 是否支持托盘常驻
    embeddedWebview: boolean   // 是否内嵌 WebView
  }
  // 核心 → 适配器：让适配器去打开/聚焦 DSH Web
  openWorkbench(opts: OpenOptions): Promise<void>
  focusExisting(): Promise<boolean>
  notify(opts: NotifyOptions): Promise<void>
  quit(): Promise<void>
}
```

**② 事件反向流（适配器 → 核心）：统一 PetEvent 单向 emit**

```ts
// pet-core/src/events.ts
export type PetEvent =
  | { type: 'hotkey-pressed' }              // 用户按了快捷键
  | { type: 'service-state-change'; running: boolean }
  | { type: 'tray-clicked' }
  | { type: 'activate' }                    // 唤起请求
```

**依赖方向**：
```
core ──调用──> LauncherPort.openWorkbench(...)   // 核心主动推（单向）
core <──消费── PetEvent（来自适配器 emit）        // 适配器主动上报（单向）
```

两端都不需要知道对方内部实现，只遵守 `LauncherPort`（core→adapter）和 `PetEvent`（adapter→core）两个契约。

---

## 落地骨架（monorepo）

```
petpal-suite/
└── packages/
    ├── pet-core/                    # 纯 TS，零 UI 依赖
    │   └── src/
    │       ├── launcher.ts          # 唤起状态机（idle→activating→ready）
    │       ├── ports/
    │       │   └── launcher-port.ts # LauncherPort 契约
    │       ├── events.ts            # PetEvent 类型（反向流协议）
    │       └── dsh-bridge.ts        # 检查/启动 DSH 服务 + 订阅事件
    │
    ├── pet-adapter-tauri/           # v0.1 唯一：Tauri 薄壳
    │   ├── src/
    │   │   ├── index.ts             # new LauncherPortImpl(core)
    │   │   ├── hotkey.ts            # 全局快捷键注册
    │   │   └── launcher-port.ts     # implements LauncherPort
    │   └── src-tauri/
    │
    ├── pet-adapter-web/             # Phase 3：Web 适配器（验证架构）
    │   └── src/launcher-port.ts     # implements LauncherPort（几乎不改核心）
    │
    └── petpal-dsh-plugin/           # 注册到 DSH 的配套插件
        └── src/index.ts
```

**验证成功的信号**：新增 `pet-adapter-web` 时，`pet-core` **一行不改**——只新增一个 `LauncherPort` 实现 = 架构正确。

---

## 关键参考项目（按价值排序）

| 项目 | 借鉴什么 | URL |
|---|---|---|
| `anywhere-labs/deepseek-harness-desktop` | DSH 桌面壳成熟范式（无缝继承 .dsh 配置、系统托盘） | https://github.com/anywhere-labs/deepseek-harness-desktop |
| `dsh-desktop`（bruc3van） | 长任务常驻托盘 + 拉起 Web UI | https://github.com/bruc3van/dsh-desktop |
| `zebar` | Tauri webview + provider 模式 | https://github.com/glzr-io/zebar |
| `sereinmono/dsh-desktop-pet` | Cordis 插件唤起 DSH 的桥接思路（借鉴，非桌宠本体） | https://github.com/sereinmono/dsh-desktop-pet |
| `cc-haha` | 多会话工作台的多窗口/唤起交互 | https://github.com/NanmiCoder/cc-haha |

> v1 时期的桌宠参考（sereinmono / FenyxHuang / xiaoshihou514 等）已不适用为主体，仅保留"DSH 桥接 + 托盘"的工程思路。

---

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| DSH 还在快速迭代（developer preview） | 锁版本，定期升级，跟踪 release notes |
| 全局快捷键与系统冲突 | 可配置快捷键 + 托盘备选入口 |
| 起服务 vs 已有实例的判断 | pet-core 统一做服务健康检查（HTTP ping / 事件），适配器只管打开 |
| "一键唤起"太简单、价值感不足 | 差异化在**零摩擦**：快捷键即达，可叠加"快速指令直达"作为 v2 增量 |

---

## 与前一阶段调研的关系

- ❌ 废弃：**独立桌宠** + 多终端桌宠渲染 + workbench Tab 自建
- ✅ 继承：port-adapter 两层架构思想、DSH 底座、Tauri 薄壳、MIT
- ✅ 沿用：`02-deep-dive.md`（技术参考）、`03-trend-synthesis.md`（趋势背景）

> 调研阶段结论：**DSH 是当前个人 AI 工作台赛道最值得进入的生态。本项目正式从"独立桌宠+工作台"收缩为"一键式唤醒 DSH 工作台的薄壳入口"。**
