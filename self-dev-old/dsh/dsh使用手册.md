# DSH（DeepSeek Harness）使用手册

> 基于公开信息整理（2026-09-17）。
> 文档目的：作为本项目（petpal-suite）开发前的入门参考。

---

## 1. DSH 是什么

- **DSH** = **DeepSeek Harness**，DeepSeek AI 开源的 Agent Harness / 智能体框架
- 仓库：https://github.com/deepseek-ai/deepseek-harness
- License：MIT
- 状态：developer preview（会有兼容性破坏的变更）
- 核心理念：**Everything is a Plugin**，由 Cordis 元框架驱动
- 10 万+ GitHub stars

四层结构：

1. **内核（harness）**：Cordis 插件树，包含模型适配器、Agent Loop、工具注册表、会话日志、沙箱、调度、UI
2. **运行模式**：标准 / PTC（程序化工具调用）/ 极简 / 创造模式
3. **Web UI**：默认 `npx @deepseek-ai/dsh web` 起在 `127.0.0.1:3080`
4. **桌面端**：社区在它之上的 Electron/Tauri 封装

---

## 2. 安装

### 2.1 前置条件

| 依赖 | 版本要求 | 检查命令 |
| --- | --- | --- |
| Node.js | ^22.19 或 >=24 | `node -v` |
| pnpm | 最新版（推荐） | `npm install -g pnpm` |
| Git | 任意版本 | `git --version` |

### 2.2 安装方式 A：直接从 npm（推荐）

```bash
# 全局安装 DSH CLI
npm install -g @deepseek-ai/dsh

# 验证安装
dsh --version
```

### 2.3 安装方式 B：从源码（需要二次开发时）

```bash
git clone https://github.com/deepseek-ai/deepseek-harness.git
cd deepseek-harness
pnpm install
pnpm run build
pnpm dsh web   # 启动 Web UI
```

---

## 3. 启动与使用

### 3.1 启动 Web UI

```bash
# 启动 Web 界面
npx @deepseek-ai/dsh web

# 默认地址：http://127.0.0.1:3080
# 如不想自动打开浏览器：加 --no-open
npx @deepseek-ai/dsh web --no-open
```

首次启动会自动打开浏览器进入 `http://127.0.0.1:3080`。

### 3.2 配置模型

进入 Web UI 后，需要配置至少一个模型 API Key：

- DeepSeek / OpenAI / Anthropic / Gemini / OpenRouter / xAI / Moonshot / MiniMax / 智谱 GLM / Mistral / Groq / Together 等 40+ 厂商开箱即用

推荐先在 **Settings → Models** 配置 DeepSeek API Key（国内访问稳定）。

### 3.3 运行模式

| 模式 | 描述 | 默认加载插件 |
| --- | --- | --- |
| **标准模式** | 完整工具组合 | 全部 |
| **PTC 模式** | 程序化工具调用 | 精简 |
| **极简模式** | 仅 shell + 文件编辑 | 最小（基准测试用） |
| **创造模式** | 在内存中试验插件、创作新模式 | 创造相关 |

### 3.4 四种模式详解

四种模式**不是四套不同的 Agent，也不是同一套 Agent 的性能档位**，而是"同一套 Harness 宿主 + 不同插件组合"的运行时形态。每个 Preset 是一份 `agent.cordis.yml` 组装文件，决定当前会话装入哪些工具、提示词段落、Skill 与 Agent 循环方式。Preset 在**会话启动时锁定**——发出第一条消息后就不能再切换。

#### 3.4.1 标准模式（standard）—— 日常开发默认

| 项 | 说明 |
| --- | --- |
| **预设 ID** | `standard`（默认） |
| **能力范围** | 文件读写 / Shell / 文件搜索 / 网页检索 / Skill / 计划（plan）/ 目标（goal）/ 子 Agent / 工作流 / 上下文压缩 / 审批弹窗 |
| **典型场景** | 写代码、改 Bug、做文档、重构项目、跑测试、看日志 |
| **适用人群** | 所有人，新手首选 |
| **Token 消耗** | 中（每一步单独调一次工具） |

**一句话定位**：开箱即用的完整编码 Agent。

#### 3.4.2 PTC 模式（ptc / code）—— 省 Token 的进阶模式

| 项 | 说明 |
| --- | --- |
| **预设 ID** | `ptc`（内部 `code`） |
| **核心机制** | 在标准模式之上把工具呈现方式换成 **Code Mode SDK**：模型生成一段 TypeScript 程序，在一次 `run_code` 调用里编排多步工具 |
| **典型场景** | 批量处理（重命名、统计、聚合）、多分支条件任务、连续查询类任务、固定流程自动化 |
| **适用人群** | 在意 Token 成本、能看懂代码规划过程的重度用户 |
| **Token 消耗** | 低（中间结果留在程序执行环境，不进模型上下文） |

**与标准模式的本质区别**：

```text
标准模式：调 A → 等结果 → 调 B → 等结果 → 调 C ...   （5 次往返）
PTC 模式：生成一段 TS 程序，一次 run_code 里调 A/B/C ...   （1 次往返）
```

**代价**：

- 调试更难——失败要看程序日志
- 要求模型有较强的代码规划能力
- 涉及删除/覆盖的批量操作，必须开审批沙箱

**典型场景举例**：统计仓库内所有包的 TODO 数量并按文件数排序——标准模式要几十次工具往返，PTC 模式一段程序一次跑完。

#### 3.4.3 极简模式（minimal）—— 基准测试专用

| 项 | 说明 |
| --- | --- |
| **预设 ID** | `minimal` |
| **能力范围** | 只有**持久 Bash + str_replace_editor** 两个工具 |
| **典型场景** | 模型基准测试（DSBench、LM-Eval、SWE-bench 等）、最小复现 Bug、教学演示 |
| **适用人群** | 研究人员、模型评测工程师 |
| **Token 消耗** | 极低（系统提示只有一句话） |

**与标准模式的区别**：极简模式不是"低配版"——它**故意剥离所有花哨工具**，用来测"模型裸能力"。DeepSeek V4 Pro 在 DSBench 上 62.7 分就是极简模式下测得的。

**普通用户不建议日常用**——缺工具会让你怀疑人生。

#### 3.4.4 创造模式（create / cordis）—— 插件开发者专用

| 项 | 说明 |
| --- | --- |
| **预设 ID** | `create`（内部 `cordis`） |
| **能力范围** | 标准模式全部能力 + 一组 `cordis_*` 运行时自检工具集 |
| **典型场景** | 创建自定义 Preset、调试 Cordis 插件、试验新插件组合、让 Agent 自我改造 |
| **适用人群** | 框架二次开发者、插件作者 |
| **安全等级** | **高信任**（等同于 shell 访问权限） |

**与标准模式的区别**：创造模式**多了一组自指工具**——Agent 可以：

- 检查当前 Cordis 运行时的插件树
- 在内存里挂载/卸载插件测试
- 把新组合保存成新的 Preset
- 通过自然语言让它"现场造一个扳手装到自己手上"

**典型例子**：在创造模式下让 DeepSeek V4 Pro DSH 创建了一个"三栏模式"（Web UI 默认没有），约 11 分钟完成；另一个例子是创建"统计汉字个数"工具，约 3 分钟当场可用。

**安全警告**：

> 创造模式能执行模型编写的插件代码、修改自身运行时，权限等同 shell。**不要在公网服务器、未受信任环境或生产业务里开创造模式**。

#### 3.4.5 模式对比表

| 维度 | 标准模式 | PTC 模式 | 极简模式 | 创造模式 |
| --- | --- | --- | --- | --- |
| **预设 ID** | `standard` | `ptc` | `minimal` | `create` |
| **工具数量** | 全套（~50） | 全套 + run_code | 2 个（bash + edit） | 全套 + cordis_* |
| **系统提示词** | 完整 | 完整 | 一句话 | 完整 + 创作指导 |
| **子 Agent** | ✅ | ✅ | ❌ | ✅ |
| **Skill** | ✅ | ✅ | ❌ | ✅ |
| **Token 消耗** | 中 | 低 | 极低 | 高 |
| **审批沙箱** | ✅ | ✅ | ⚠️ 仅 bash | ❌ 高信任 |
| **调试难度** | 低 | 中（要看代码） | 低 | 高 |
| **新手推荐** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ |
| **典型用例** | 日常开发 | 批量自动化 | 模型评测 | 插件开发 |

#### 3.4.6 切换模式的注意事项

- **会话锁定**：发出第一条消息后，Preset 就锁定了。想换模式需要**开新会话**。
- **预设文件可复制修改**：四个内置预设是只读的，但你可以复制一份改成自定义预设，存为 `~/.dsh/agents/<name>.cordis.yml`。
- **CLI 启动方式**：

  ```bash
  npx @deepseek-ai/dsh --mode standard  # 默认
  npx @deepseek-ai/dsh --mode ptc
  npx @deepseek-ai/dsh --mode minimal
  npx @deepseek-ai/dsh --mode create
  ```

- **Web UI 切换**：新建会话时顶部下拉框选——一旦发出首条消息，下拉框被禁用。

#### 3.4.7 选择建议（实战经验）

| 场景 | 推荐模式 |
| --- | --- |
| 第一次用 / 日常开发 / 改 Bug / 写文档 | **标准模式**（默认） |
| 批量处理大量文件 / 想省 Token | **PTC 模式** |
| 跑模型 benchmark / 教学演示 / 最小复现 | **极简模式** |
| 写自定义 Preset / 调试 Cordis 插件 | **创造模式** |
| 跑 petpal-suite 插件的 E2E 调试 | **标准模式** |

### 3.5 运行 Headless（无 UI）

```bash
# 无界面运行，适合服务器
npx @deepseek-ai/dsh --profile headless
```

---

## 4. 插件管理

### 4.1 安装插件

```bash
# 从 GitHub 仓库
dsh plugin --profile web add github:owner/repo

# 从本地目录（开发调试）
dsh plugin --profile web add /path/to/plugin-dir

# 从 npm 包
dsh plugin --profile web add package-name

# 从打包好的 tarball
dsh plugin --profile web add ./plugin-0.1.0.tgz
```

安装到 `--profile web` 后，**重启 dsh web** 插件才会生效（bundle 在启动时合并）。

### 4.2 验证插件

```bash
# 列出已安装插件
dsh plugin list

# 移除插件
dsh plugin remove plugin-name
```

### 4.3 推荐体验插件

安装一个现成桌宠体验 DSH 插件生态：

```bash
# sereinmono 的 dsh-desktop-pet（Codex pet 格式兼容）
dsh plugin --profile web add github:sereinmono/dsh-desktop-pet

# 鲸鱼娘（xiaoshihou514，Tauri 打包）
dsh plugin --profile web add "github:vlln/whale-girl#main"

# 状态可视化（FenyxHuang，余额 + 任务状态）
dsh plugin --profile web add github:FenyxHuang/dsh-desktop-pet

# DIY 素材链（PC2005-cloud，AI 视频→透明动画）
dsh plugin --profile web add dsh-pet
```

安装后重启 `dsh web`，桌宠会出现在 Web UI 右下角。

---

## 5. 桌面壳（社区版）

如果你不想用浏览器访问 Web UI，可以装一个社区桌面壳：

### 5.1 主流选择

| 项目 | 形态 | License | 特点 |
| --- | --- | --- | --- |
| `dataelement/dsh-desktop` | Electron | MIT | 内置多模型服务商目录 |
| `anywhere-labs/deepseek-harness-desktop` | Electron | MIT | 无缝继承 .dsh 配置 |
| `ningbainb/deepseek-harness-desktop` | Electron | BSD-3-Clause | Windows + 11 套皮肤 + 移动远程 |
| `xiaoshihou514/dsh-desktop-pet` | Tauri | MIT | Tauri 打包的桌宠 |

### 5.2 推荐起点

先用 `anywhere-labs/deepseek-harness-desktop`：

```bash
# 1. 从 https://github.com/anywhere-labs/deepseek-harness-desktop/releases 下载安装包
# 2. 安装后双击启动
# 3. 自动拉起 dsh web 并嵌入原生窗口
```

或者纯命令行调试就 `npx @deepseek-ai/dsh web`，最轻量。

---

## 6. 核心概念速查

### 6.1 Cordis

DSH 底层的元框架，把所有能力（模型、工具、会话、Agent Loop、UI）都做成插件。插件通过 service + event 协作，开发者无需改源码就能替换任一能力。

### 6.2 Profile / Bundle / Patch

- **Profile**：DSH 的一种运行配置（如 `web` / `headless`）
- **Bundle**：一个完整的 DSH 插件包
- **Patch**：在已加载插件之上的覆盖/补充

桌面宠物的典型做法：在 `cordis.patch.yml` 加一行客户端插件，桌宠就是纯浏览器 UI，落在 profile 补丁层。

### 6.3 会话日志

只追加（append-only）的会话事件日志，包括：

- 系统提示词
- 思维链
- 工具调用与结果
- 子 Agent 调度
- 每次上下文注入

在 Web UI 的 **Trajectory** 视图可按来源查看、恢复、分叉、检索、回放。

---

## 7. 常见问题

### Q1: DSH 是 DeepSeek 官方产品吗？

**是**。deepseek-harness 由 DeepSeek AI 官方开发和维护。

但**桌面壳（dsh-desktop）是社区项目**，与官方无直接关系。命名容易混淆。

### Q2: 国内能用吗？

- DSH 本体（`npx @deepseek-ai/dsh web`）：国内可直连
- 模型 API Key：取决于你接入的模型服务商在国内是否可达

### Q3: 需要付费吗？

DSH 本身**完全免费**（MIT 协议），成本来自你接入的模型 API。

### Q4: 与 OpenAI Codex Desktop / Cursor 的区别？

| 维度 | DSH Desktop | Codex Desktop | Cursor |
| --- | --- | --- | --- |
| 协议 | MIT 开源 | 闭源 | 闭源 |
| 成本 | 仅模型 API | $20~200/月 | 免费+Pro 订阅 |
| 模型 | 40+ 厂商 | 仅 OpenAI | 多模型 |
| 插件生态 | "万物皆插件" | 有限 | VS Code 扩展 |
| 移动远程 | 支持 | 不支持 | 不支持 |

### Q5: 数据隐私？

- DSH 默认只监听 127.0.0.1 loopback，不暴露公网
- 默认关闭遥测
- 对话记录、配置档案默认存储本机

---

## 8. 本项目（petpal-suite）的使用方式

按调研决策 [05-final-direction.md](../docs/调研/05-final-direction.md)，petpal-suite 是 DSH 之上的一套插件集合。

### 8.1 用户视角

```bash
# 1. 装 DSH（一次）
npm install -g @deepseek-ai/dsh

# 2. 起 Web UI
npx @deepseek-ai/dsh web

# 3. 装 petpal 插件集合
dsh plugin --profile web add github:your-org/petpal-suite

# 4. 重启 dsh web，桌宠出现
```

### 8.2 开发者视角

```bash
# 1. clone petpal-suite monorepo
git clone https://github.com/your-org/petpal-suite.git
cd petpal-suite

# 2. 装依赖
pnpm install

# 3. 本地 link 到 dsh profile
cd packages/pet-core && pnpm run build && pnpm link --global
cd ../pet-adapter-tauri && pnpm run build
dsh plugin --profile web add link:./packages/dsh-plugin

# 4. 启动 dsh web 调试
npx @deepseek-ai/dsh web
```

---

## 9. 参考链接

- 官方仓库：https://github.com/deepseek-ai/deepseek-harness
- 官方文档：https://deepseekharness.online/
- 插件市场：https://www.dsh.so/
- 插件索引：https://dshhub.org/
- 桌面壳评测：https://orkas.ai/compare/orkas-vs-deepseek-harness
- 国内综述：https://www.toutiao.com/article/7674826168790090292

---

## 10. 进阶阅读

DSH 的工作原理、Cordis / Bundle / Profile 三大核心概念、数据流与配置体系，已单独整理到：

**[dsh原理介绍说明.md](./dsh原理介绍说明.md)**

包含：

- DSH 启动流程、单实例架构、端口与多 profile 隔离
- `~/.dsh` 目录、配置层叠顺序、Session / Workspace / Credentials / Storage
- Cordis 插件容器、Bundle 打包、Profile 运行模式（含生活化比喻 + 代码示例）
- 第一个 DSH plugin 实践模板
