# self-dev

> 基于上游 `anywhere-labs/dsh-desktop` 的二开目录。所有 self-dev 代码放在上游项目内，作为 `dsh-desktop/self-dev/` 子树。

## 目录结构

```text
P_20260422_桌面助手/                      ← git 仓库根（仅含 dsh-desktop/ + 隐藏文件）
└── dsh-desktop/                          ← 上游 anywhere-labs/dsh-desktop（drop-history 引入）
    ├── AGENTS.md / README.md / package.json ...    ← 上游根
    ├── dsh-plugin-desktop/                          ← 上游 Stable 桌面壳
    ├── dsh-plugin-desktop-beta/                     ← 上游 Beta 桌面壳
    ├── dsh-desktop-next/                            ← 上游实验 Next 壳
    ├── deepseek-harness/                            ← pinned DSH 上游（git submodule，不在此仓库编辑）
    ├── vendor/ patches/ assets/ ...                 ← 上游构建产物与补丁
    │
    └── self-dev/                         ← 我们的二开代码（不与上游冲突）
        ├── desk-assistant/               PyQt5 旧项目（封存为设计参考）
        ├── petpal/                       Electron 一键唤起 DSH 工作台
        ├── dsh/                          DSH 原理与使用文档
        ├── docs/                         项目调研、方向决策文档
        ├── project.md                    项目 AI 记忆上下文
        ├── panel.log                     PyQt 面板运行日志（项目历史快照）
        ├── test.sh                       旧测试脚本
```

## 与上游的关系

| 项 | 值 |
|---|---|
| **上游仓库** | <https://github.com/anywhere-labs/dsh-desktop> |
| **本地 remote** | `upstream`（已添加） |
| **首次引入** | `chore: import upstream anywhere-labs/dsh-desktop into dsh-desktop/ (drop-history)`（1 个 init commit，245909 行） |
| **合并策略** | `git merge -X subtree=dsh-desktop` |
| **本地 origin** | 待定（本次未推送） |

## 上游工作约定（必须遵守）

`dsh-desktop/AGENTS.md` 是上游项目工作约定，本仓库作为 fork 同样遵守：

- **不要编辑 `deepseek-harness/` 子模块**（pinned upstream）
- **使用 Node.js `^22.19.0` 或 `>=24.0.0`** + 根目录 Yarn 4.18.0（通过 corepack）
- **日常开发命令**：`corepack yarn dev` / `corepack yarn build` / `corepack yarn test` / `corepack yarn typecheck` / `corepack yarn check`
- **Stable/Beta 双变体开发**：`dsh-plugin-desktop-beta/` 先开发 → `corepack yarn check:desktop-variants` → 同步到 `dsh-plugin-desktop/`（保留声明的变体差异）
- **不要 fork 上游官方 Web 前端**（`dsh-desktop-next/` 独立 Next 壳，按 upstream:build 同步）
- **Graphical 应用启动要显式**（构建/类型检查/单元测试必须保持 headless-safe）
- **子模块更新与桌面行为改动分开提交**

## self-dev 开发流程

### 日常开发（在 self-dev/）

```bash
# 在 self-dev/ 下创建特性分支
git checkout -b feat/petpal-xxx

# 在 dsh-desktop/self-dev/petpal 等下进行改动
git commit -am "feat(petpal): ..."

# 验证（按上游约定）
cd dsh-desktop
corepack yarn typecheck
corepack yarn test
```

### 反合上游 master

当上游 `anywhere-labs/dsh-desktop` 更新时：

```bash
# 1. 拉取最新上游
git fetch upstream master

# 2. 把 upstream/master 合入 dsh-desktop/（subtree 合并策略）
git merge upstream/master -X subtree=dsh-desktop \
  -m "chore: rebase upstream master into dsh-desktop/"

# 3. 解决冲突（通常在 dsh-desktop/ 下，self-dev/ 几乎不会冲突）
# 4. 推送到 origin
git push origin master
```

### 冲突处理

- **`dsh-desktop/` 冲突**：跟上游同步，按上游优先
- **`dsh-desktop/self-dev/` 冲突**：我们的代码，几乎不会冲突
- **罕见重叠**：手动评估保留哪边

## 快捷别名（推荐）

```ini
# ~/.gitconfig
[alias]
    upstream-fetch = fetch upstream
    upstream-merge = "!f() { git fetch upstream && git merge upstream/master -X subtree=dsh-desktop \"$@\"; }; f"
```

之后 `git upstream-merge` 一条命令完成。

## 项目背景

本仓库原为独立的 PyQt5 桌面助手项目（`desk-assistant/`），2026-09 完成 DSH 桌面壳生态调研后，转型为基于 `anywhere-labs/dsh-desktop` 的二次开发 fork，专注于在 `petpal`（Electron 一键唤起 DSH 工作台）等自研能力。

详细决策见：
- `dsh-desktop/self-dev/docs/调研/05-final-direction.md` — 最终方向决策
- `dsh-desktop/self-dev/dsh/` — DSH 原理与使用文档
- `dsh-desktop/README.md` — 上游原始 README
- `dsh-desktop/AGENTS.md` — 上游工作约定（本 fork 遵守）