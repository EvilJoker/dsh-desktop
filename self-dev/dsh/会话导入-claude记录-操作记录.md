# 从 Claude 导入会话到 DSH（操作记录）

> 任务：把本项目的 Claude Code 会话历史导入到 DeepSeek Harness（DSH），以便延续开发。
> 结论：**DSH 官方没有内置的命令**，通用做法是社区插件 `dsh-plugin-session-import`
> （官方仓库 Discussion #1087 推荐）。但该插件 0.1.1 与当前 DSH 0.1.5-rc.1 **存在版本不兼容**，
> 已就地打补丁修复并完成本项目会话导入。详见下文。

---

## 一、结论：官方有办法吗？

- **没有内置/官方命令**。`dsh` CLI 只提供通用的插件管理（`dsh plugin ... add`），没有把
  Claude/Codex 会话 JSONL 转成 DSH 会话的原生命令。
- **最接近"官方推荐"的是社区插件** `dsh-plugin-session-import`，在官方 `deepseek-ai/deepseek-harness`
  的 Discussions #1087 里有部署与推荐：
  https://github.com/deepseek-ai/deepseek-harness/discussions/1087
- 该插件支持：claude-code / codex / reasonix / zcode；扫描 `~/.claude/projects/**/*.jsonl`，
  提供侧边栏「⇩ 导入会话」按钮与 `/import <tool> <path>` 命令，导入后可直接续聊，并保留工具调用。

---

## 二、安装

已执行（装进 web profile，并自动 reconcile 到 `dsh.profile.bundles`）：

```bash
dsh plugin --profile web add dsh-plugin-session-import
```

验证装进配置树：

```bash
dsh --profile web --dump-config | grep -A2 "dsh-plugin-session-import"
# => - id: session-import / name: dsh-plugin-session-import
```

---

## 三、遇到的问题与补丁（重要）

插件 0.1.1 是针对更早的 DSH 写的，在当前 DSH 0.1.5-rc.1 上**所有导入都会失败**，
不是数据问题。用 3 条消息的小会话复测也报同样的错，确认是系统性版本不兼容。

安装位置：`~/.dsh/profiles/web/node_modules/dsh-plugin-session-import/lib/index.js`
（已就地打补丁，备份在 `index.js.bak`）。

### 补丁 A：assistant/message 缺 `stream` 字段

- 现象：`seed assistant/message at index N has invalid settlement fields`
- 原因：DSH 0.1.5-rc.1 的种子校验（`dsh-session/lib/index.js` 的
  `assertAssistantSettlementShape`）要求 `assistant/message` 事件的 `data.stream` 是数组；
  插件旧版只给 `data.message`，没给 `stream`。
- 修复：在 `flushPending()` 生成 `assistant/message` 时，按消息内容块补一个
  `block-start / block-end / usage / finish` 的 `stream` 数组（`data.message` 仍是展示内容的权威来源）。

### 补丁 B：cwd 解析失败 → 工作区被绑定到错误目录

- 现象：导入成功但 `cwd` 变成 `\home\...\.claude\projects\...` 这种错误路径，
  会话被绑到 `.claude/projects` 元数据目录而非真正的项目目录。
- 原因一：`loadCwdMap()` 用 `process.env.USERPROFILE`（Windows 变量）定位
  `~/.claude.json`，在 Linux 上为空 → 权威映射没加载。
- 原因二：没有按 Claude 的项目目录命名规则（把每个非 `[a-zA-Z0-9]` 字符替换为 `-`）
  建立反向索引，导致含中文/下划线等字符的真实路径（如 `P_20260422_桌面助手`）
  无法从目录名反查回真实路径。
- 修复：`loadCwdMap()` 改用 `USERPROFILE || HOME`，并为每个真实路径额外建立
  `realPath.replace(/[^a-zA-Z0-9]/g, "-")` 编码键；`decodeCwd()` 即可精确命中。

> 复现关系已验证：真实路径 `/home/.../P_20260422_桌面助手` 的编码
> `-home-10312862-zte-intra--pkm-20-Projects-P-20260422-----` 与 Claude 生成的
> 项目目录名完全一致。

**注意**：这是对已安装 npm 包的就地补丁。若以后 `npm install` / `dsh plugin` 重装或升级
该插件，补丁会丢失，需按本文件重新套用，或向插件作者反馈该版本兼容 bug。

---

## 四、本项目会话导入结果

- 源文件：`~/.claude/projects/-home-10312862-zte-intra--pkm-20-Projects-P-20260422-----/f20a4315-5a3d-4233-8532-80915e3509b6.jsonl`
- 导入会话 ID：`import-1789646437687-ubjmfp`
- 内容：266 条消息 / 693 个事件（95 条 assistant、94 次工具调用、92 次工具结果、26 条 user）
- 工作区：正确绑定到 `/home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手`，
  并已挂到该工作区（workspace `28eca57a-...` 的 sessionIds 里）。
- 说明：原会话约 616 条消息，为适配模型上下文预算（budget 117965）**截断了 350 条中间历史**，
  保留开头锚点 + 尾部，属插件设计的超长保护行为。

---

## 五、还需要你做的（一步）

当前正在运行的 Web GUI 是**插件安装前启动**的，因此还没加载插件、也没刷新会话列表。
> 为了让插件（侧边栏「⇩ 导入会话」按钮 + `/import` 命令）生效并看到导入的会话，**重启一次 `dsh web`** 即可。

```bash
dsh web   # 重启后：侧边栏底部「⇩ 导入会话」或输入 /import 命令
```

重启后如需手工再导入其它 Claude 对话：

```bash
/import claude-code ~/.claude/projects/<项目目录>
# 传目录=批量；也可以一次传单个 .jsonl 文件
```

---

## 六、参考链接

- 官方 Discussion（插件推荐）：https://github.com/deepseek-ai/deepseek-harness/discussions/1087
- 插件仓库：https://github.com/huguangyu666/dsh-plugin-session-import
- Claude Code 会话管理文档：https://code.claude.com/docs/en/sessions
