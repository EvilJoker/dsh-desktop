# 桌面助手演进方向 · GitHub & 网络调研报告

> 调研目标：评估"桌面宠物"和"个人工作台"两条演进方向，盘点当前 GitHub 与网络上热度高、维护活跃的开源参考实现，提炼对本项目（基于 PyQt5 的桌面助手）有借鉴价值的设计点。
> 调研日期：2026-09-15
> 调研方式：`gh search repos` 多维度广度搜索 + WebFetch 深度抓取热门项目 README + web_search 行业趋势综述
> 数据时效：stars/forks/commits 数据基于 2026-09 当周抓取

---

## ⚡ 最终决策（2026-09-17 更新）

**已确认方向**：基于 **DSH（DeepSeek Harness）** 原生底座，构建 **petpal-suite** DSH 插件集合。核心是 **pet 组件**（port-adapter 架构，可对接多终端，目前只实现 Tauri 桌面端）。

详见 [05-final-direction.md](./05-final-direction.md)。

**PyQt 面板项目**：封存为设计参考，不再演进。设计理念（玻璃拟态、strip "鼠标穿透 + 不抢焦点"、状态机驱动）保留并翻译到新项目。

---

## 目录

1. [05-final-direction.md](./05-final-direction.md) — **最终方向决策报告（请先看）**
2. [01-candidates-overview.md](./01-candidates-overview.md) — 候选项目速览表（28+ 项目）
3. [02-deep-dive.md](./02-deep-dive.md) — Top 12 项目深度分析（架构 / 技术栈 / 借鉴点）
4. [03-trend-synthesis.md](./03-trend-synthesis.md) — 行业趋势综合（国内 + 海外）
5. [04-references-for-evolution.md](./04-references-for-evolution.md) — 演进方向参考资料（已废弃，仅作历史记录）

---

## 核心结论（先看这一页）

### 行业大势（2026-Q3）

1. **AI Agent 桌宠爆发**：从"装饰"转向"状态代理"——Clawd on Desk (6.2k★)、MiniCPM-Desk-Pet (484★)、Agentic-Desktop-Pet (338★) 都把桌宠定位成"AI Coding Agent 的可视化外设"，解决长任务下的"进度模糊"问题。
2. **个人工作台赛道**：cc-haha (14.4k★) 一枝独秀，整合会话管理 / Worktree / 多模型 / 桌宠 / IM 接入 / 技能市场，是当前国内最完整的"个人 AI 工作台"开源实现。
3. **跨平台 Widget 框架**：zebar (3.1k★, Rust) 与 fabric (1.4k★, Python) 为 DIY 桌面 widget 提供成熟底座；本项目已有的"侧边栏 strip + 主面板"形态可以借鉴 zebar 的 provider 模式。
4. **Token 监控成刚需**：token-monitor (2.1k★) 跨 36+ AI 工具监控用量，是 Claude Code 用户的高频需求。
5. **国产本地执行型 Agent 崛起**：AiPy / LobsterAI / CoPaw / OpenOcta 强调"数据不出本机"，与本项目"本机 PyQt 面板 + pydbus"的定位高度契合。

### 本项目的演进路径建议（轻量优先、低 token 投入）

| 演进方向 | 推荐优先级 | 推荐参考资料 | 实施成本 |
| ------ | ------ | ------ | ------ |
| **A. 工作台增强**（保留 PyQt 面板） | ★★★★★ | zebar、token-monitor、cc-haha | 中 |
| **B. 桌宠化（追加 layer）** | ★★★★ | Clawd on Desk、MiniCPM-Desk-Pet、OpenPets | 低 |
| **C. Token / 任务状态监控**（接 Claude Code） | ★★★★ | token-monitor、Clawd on Desk、AgentPet | 低 |
| **D. 长期记忆 / 个人知识库** | ★★★ | MemTensor (1.9k★)、Kimi-core、Open-LLM-VTuber | 中 |
| **E. 跨平台 Widget 框架** | ★★ | zebar、fabric | 高（需重写） |

### 三条不动手也能立刻借鉴的设计点

1. **任务感知动画状态机**（来自 Clawd on Desk）：thinking / working / waiting / finished / idle 五态，不打断用户、不滥用动画。
2. **Provider 解耦**（来自 zebar）：把系统信息源（CPU/电池/网络/Claude Code 状态）做成 provider，主面板只消费。
3. **侧栏 dock 条 + 主面板 + 透明气泡**（来自 OpenPets / cc-haha）：分层 UI，dock 条常驻不打扰，主面板按需展开，气泡用于主动提示。

---

## 详细报告

- 候选项目速览：[01-candidates-overview.md](./01-candidates-overview.md)
- Top 12 深度分析：[02-deep-dive.md](./02-deep-dive.md)
- 行业趋势综合：[03-trend-synthesis.md](./03-trend-synthesis.md)
- 按演进方向的参考资料：[04-references-for-evolution.md](./04-references-for-evolution.md)
