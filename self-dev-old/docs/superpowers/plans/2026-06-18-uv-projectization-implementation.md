# 桌面助手 uv 项目化实施计划 v2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 desk-assistant 从"裸 Python 项目"项目化成 uv 项目——`pyproject.toml` + `uv.lock` + `.venv` + `.python-version`，用 uv 创 `.venv/` 隔离 build-time 依赖（pyinstaller 4.10、pyinstaller-hooks-contrib 2022.0），运行时不归 uv 管。

**Architecture:** v1 设计用 `[tool.uv.scripts]` 包装 bash 脚本作为 `uv run <name>` 入口，实施时发现 uv 0.11.6 不支持此字段。v2 改为：uv **只做依赖管理**（锁版本 + 创 venv + 生成 uv.lock），bash script/*.sh /usr/local/bin/desk-assistant_run.sh / autostart .desktop **完全不动**。运行时依赖（PyQt5/flask/requests）继续走 user site（`~/.local/lib/python3.6/site-packages/`），pyproject.toml `dependencies = []` 避免 uv 试图重装覆盖源码编译的 PyQt5。

**Tech Stack:** uv 0.11.6、PEP 621 pyproject.toml、Python 3.6.8（系统 `/usr/bin/python3.6`）。

## Global Constraints

- **Python 版本固定 3.6.8**：`.python-version` 内容 `3.6`，`requires-python = ">=3.6.8,<3.7"`。
- **bash 脚本零修改**：所有 `script/*.sh`（build.sh / install.sh / uninstall.sh / desk-assistant_run.sh）一行不改。
- **运行时依赖不动**：PyQt5 5.15.6（源码编译 ABI 对齐系统 Qt 5.12.5）、PyQt5-sip 12.9.1、sip 6.5.1、flask 2.0.3、requests 2.27.1、pyinstaller 4.10、pyinstaller-hooks-contrib 2022.0 继续装在 user site，**不归 uv 管**。
- **pyproject.toml dependencies 留空**：`dependencies = []`，uv sync 不重装 user site 包。
- **venv 只装 build-time 包**：`uv sync --extra build` 在 `.venv/` 内只装 `[project.optional-dependencies] build` 指定的 pyinstaller 4.10 + pyinstaller-hooks-contrib 2022.0（但因 user site 已装，uv 会**复用**而非重装）。
- **不引入 `[tool.uv.scripts]`**：uv 0.11.6 不支持此字段（不在 `[tool.uv.*]` 合法字段列表中）。
- **不引入 `[project.scripts]` / `[build-system]` / `[tool.setuptools]` / `[tool.uv.dependency-groups]`**：项目不是 wheel 分发。
- **uv.lock 必须提交**：保证重装/跨机器 100% 一致。
- **不主动 commit**（用户偏好）：每 Task 完成后报告，等用户明确说"commit"才 `git commit`。
- **不改动任何运行时版本**：用户实际版本（PyQt5 5.15.6、pyinstaller 4.10 等）原样记录到 pyproject.toml，uv 不会"升级或改动"。

---

## 文件结构

实施后最终布局：

```text
desk-assistant/
├── pyproject.toml                       # 新增（spec §4 内容）
├── .python-version                      # 新增（"3.6"）
├── uv.lock                              # uv sync 自动生成（提交）
├── .venv/                               # uv sync 自动生成（gitignore）
├── .gitignore                           # 改：加 .venv
├── README.md                            # 改：新增 "uv 依赖管理" 章节
├── pyproject.toml.old.bak               # Task 1 备份（最后删）
├── panel/                               # 不动
├── server/                              # 不动
├── tests/                               # 不动
├── assets/                              # 不动
└── script/                              # ✓ 全部保留（内容一行不改）
    ├── build.sh
    ├── install.sh
    ├── uninstall.sh
    └── desk-assistant_run.sh

❌ 删 desk-assistant/tools/           # Task 2
```

---

## Task 1: 改写 pyproject.toml + uv sync 创 venv

**Files:**
- Modify: `desk-assistant/pyproject.toml`（完整替换为 spec §4 内容）
- Create: `desk-assistant/.python-version`（如不存在；内容 `3.6`）
- Create: `desk-assistant/uv.lock`（uv sync 生成）
- Create: `desk-assistant/.venv/`（uv sync 生成，gitignored）
- Modify: `desk-assistant/.gitignore`（加 `.venv`）
- Backup: `desk-assistant/pyproject.toml.old.bak`（最后删）

**Interfaces:**
- Consumes: 当前 pyproject.toml（旧设计，含 Python CLI 残留 + `[project.scripts]`）
- Produces: 新 pyproject.toml（spec §4 内容），被 Task 2 验证、被 Task 4 引用

- [ ] **Step 1：备份当前 pyproject.toml**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
cp pyproject.toml pyproject.toml.old.bak
ls -la pyproject.toml.old.bak
```

预期：`pyproject.toml.old.bak` 存在。

- [ ] **Step 2：完整替换 pyproject.toml 内容**

用 Write 工具把 pyproject.toml 替换为 spec §4 内容（**逐字节**）：

```toml
[project]
name = "desk-assistant"
version = "3.1.0"
description = "云桌面常驻看板：半透明贴边 PyQt5 浮窗（server + panel + openclaw chat）"
readme = "README.md"
requires-python = ">=3.6.8,<3.7"
license = { text = "Internal" }
authors = [{ name = "Sun Qiyuan", email = "10312862@zte.intra" }]

# 运行时依赖故意不列——PyQt5/flask/requests 装在 user site（/usr/bin/python3.6 能看到）
# uv 不管理这些包，避免 uv sync 试图重装 PyQt5 wheel 覆盖源码编译产物（ABI 会坏）
dependencies = []

[project.optional-dependencies]
# build-time 依赖：uv sync --extra build 装到 .venv/
# pyinstaller 4.10 是最后一个支持 Python 3.6 的稳定版本（5.0+ 要 Py 3.7+）
build = [
    "pyinstaller==4.10",
    "pyinstaller-hooks-contrib==2022.0",
]

[tool.uv]
# 项目不是 wheel 分发（panel/ server/ 是裸脚本）
package = false

# 不引入 [tool.uv.scripts]：uv 0.11.6 不支持此字段（不在 [tool.uv.*] 合法字段列表中）
# bash 脚本直接用 `bash script/*.sh` 调用
```

- [ ] **Step 3：确保 .python-version 存在且内容是 "3.6"**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
if [ ! -f .python-version ]; then
    echo "3.6" > .python-version
fi
cat .python-version
```

预期：输出 `3.6`。

- [ ] **Step 4：把 .venv 加到 .gitignore（如果还没加）**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
grep -qF ".venv" .gitignore || echo ".venv" >> .gitignore
grep -F ".venv" .gitignore
```

预期：`.gitignore` 包含 `.venv`。

- [ ] **Step 5：先记录 user site 包列表（验收基线）**

```bash
/usr/bin/python3.6 -m pip list > /tmp/user-site-baseline.txt
wc -l /tmp/user-site-baseline.txt
head -5 /tmp/user-site-baseline.txt
```

预期：基线文件保存了 user site 现有包列表。**这是验收清单第 5 项的对照基线。**

- [ ] **Step 6：跑 uv sync --extra build**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
uv sync --extra build 2>&1 | tail -20
```

预期：
- 输出含 `Using CPython 3.6.8 interpreter at: /usr/bin/python3.6`
- 输出含 `Creating virtual environment at: .venv`（如 .venv 不存在）
- 输出含 `Resolved N packages` + `Installed N packages` 或 `Audited N packages`（如 .venv 已部分存在）
- 退出码 0

- [ ] **Step 7：验证 .venv/ 装了什么**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
ls -la .venv/bin/ 2>&1 | head -20
echo "---"
.venv/bin/python3.6 -m pip list 2>&1 | head -20
```

预期：
- `.venv/bin/` 含 `python3.6` `pip` 等
- `.venv/bin/python3.6 -m pip list` 输出**含** `pyinstaller==4.10` + `pyinstaller-hooks-contrib==2022.0`
- **不**含 PyQt5 / flask / requests（这些是 user site 的，不归 venv 管）

- [ ] **Step 8：验证 user site 包未被动过（关键安全检查）**

```bash
/usr/bin/python3.6 -m pip list > /tmp/user-site-after.txt
diff /tmp/user-site-baseline.txt /tmp/user-site-after.txt && echo "USER SITE UNCHANGED" || echo "USER SITE CHANGED!"
```

预期：输出 `USER SITE UNCHANGED`（无差异）。如果输出 `USER SITE CHANGED!`，**停下来告诉用户**——uv 动了不该动的东西。

- [ ] **Step 9：确认 uv.lock 已生成**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
ls -la uv.lock
head -10 uv.lock
```

预期：uv.lock 存在（≥ 1KB），首行 `version = 1`。

- [ ] **Step 10：报告完成，等用户确认 commit**

报告内容：
- 改写后 pyproject.toml 行数 / 字节数
- uv sync 安装了多少包
- uv.lock 文件大小
- .venv/ 装了什么（用 `pip list` 输出）
- user site 是否 unchanged

**不主动 git commit**。等用户回复"commit"或类似明确指令再进入 Step 11。

- [ ] **Step 11（仅用户授权后）：commit Task 1 改动**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/pyproject.toml desk-assistant/uv.lock desk-assistant/.python-version desk-assistant/.gitignore
git status
git commit -m "feat: uv 项目化（pyproject.toml + uv.lock + venv 装 build-time 依赖）"
```

预期：commit 成功，git status 干净。

---

## Task 2: 删除 tools/ 目录（弃用的 Python CLI 方案）

**Files:**
- Delete: `desk-assistant/tools/`（整个目录）

**Interfaces:**
- Consumes: Task 1 已改写 pyproject.toml（已不含 `tools.cli:main` 引用）
- Produces: 干净的工作树（spec §3"删除的产物"全部清掉）

- [ ] **Step 1：检查 tools/ 当前内容（删除前最后确认）**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
find tools -type f
```

预期输出（与 spec §3"删除的产物"清单对应）：
```
tools/lib/__init__.py
tools/lib/log.py
tools/lib/paths.py
tools/lib/process.py
tools/lib/run.py
tools/commands/__init__.py
```

如果还看到 `tools/cli.py`（spec 也提到要删），一并删即可。如果看到**其他**文件，**停下来告诉用户**，不要乱删。

- [ ] **Step 2：确认 pyproject.toml 不再引用 tools/**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
grep -rn "tools" pyproject.toml || echo "no references"
```

预期：输出 `no references`（pyproject.toml 已干净）。

- [ ] **Step 3：删除 tools/ 目录**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
rm -rf tools
ls -la | grep -E "^d.*tools$" || echo "tools/ deleted"
```

预期：输出 `tools/ deleted`（目录已不存在）。

- [ ] **Step 4：重跑 uv sync 确认无副作用**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
uv sync --extra build 2>&1 | tail -5
```

预期：输出 `Audited N packages`（已装包无变化）或类似成功行。无 `error` / `Failed to` 行。

- [ ] **Step 5：git status 检查**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git status -s desk-assistant/tools/
```

预期：输出形如 `D desk-assistant/tools/lib/log.py` 等多行 `D`（删除标记）。

- [ ] **Step 6：报告完成，等用户确认 commit**

报告内容：
- 删除了几个文件
- uv sync 是否无副作用

**不主动 git commit**。等用户回复"commit"再进入 Step 7。

- [ ] **Step 7（仅用户授权后）：commit Task 2 改动**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add -u desk-assistant/tools/
git status
git commit -m "chore: 删除弃用的 tools/ Python CLI 目录（uv 替代方案）"
```

预期：commit 成功，仅含 tools/ 删除的文件。

---

## Task 3: 更新 README.md 加 uv 依赖管理章节

**Files:**
- Modify: `desk-assistant/README.md`（新增 "uv 依赖管理" 章节 + 简提"开发"步骤）

**Interfaces:**
- Consumes: Task 1 已改写 pyproject.toml（确定 `uv sync --extra build` 是开发入口）
- Produces: README.md 含新章节，下个开发者 clone 后能照着跑

- [ ] **Step 1：定位 README 章节插入点**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
grep -n "^## " README.md
```

预期输出示例（按现有 README 结构）：
```
## 概览
## Edge Dock（v3）
## 组件构成
## 项目结构
## 系统要求
## 快速开始
## launcher 命令
## HTTP API
...
```

**插入点**：在 "## 快速开始" 之后、"## launcher 命令" 之前。

- [ ] **Step 2：在 "## 快速开始" 后插入 "## uv 依赖管理" 章节**

用 Edit 工具，匹配字符串 `"## launcher 命令"` 之前的内容。具体操作：
1. 用 Read 工具读 README.md 定位"## 快速开始"末尾
2. 在 "## 快速开始" 章节的最后一个内容行之后（`## launcher 命令` 之前）插入新章节：

```markdown
## uv 依赖管理

项目用 uv 项目化（`pyproject.toml` + `uv.lock` + `.venv` + `.python-version`），用于**开发时**隔离 build-time 依赖。运行时仍走 `/usr/bin/python3.6` + user site，**与 uv 无关**。

### 两层环境

| 环境 | 谁用 | 装的包 | 谁装 |
| --- | --- | --- | --- |
| `~/.local/lib/python3.6/site-packages/`（user site） | 运行时 `/usr/bin/python3.6` | PyQt5 5.15.6、PyQt5-sip、sip、flask、requests、pyinstaller 4.10、pyinstaller-hooks-contrib 2022.0 | `/usr/bin/python3.6 -m pip install --user`（历史手动装） |
| `.venv/` | 开发（uv sync 创出） | （同上，uv 复用 user site 已装的包，不重装） | `uv sync --extra build` |

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

```

- [ ] **Step 3：README.md 章节顺序验证**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
grep -n "^## " README.md
```

预期输出（新章节位置）：
```
## 快速开始
## uv 依赖管理
## launcher 命令
## HTTP API
...
```

`uv 依赖管理` 必须在 `launcher 命令` 之前。

- [ ] **Step 4：行数 / 字数检查**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
wc -l README.md
```

预期：README.md 增加约 50 行。

- [ ] **Step 5：报告完成，等用户确认 commit**

报告内容：
- README.md 增加行数
- 新章节位置

**不主动 git commit**。等用户回复"commit"再进入 Step 6。

- [ ] **Step 6（仅用户授权后）：commit Task 3 改动**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/README.md
git status
git commit -m "docs(readme): 加 uv 依赖管理章节（两层环境 + uv sync 用法）"
```

预期：commit 成功，仅含 README.md 修改。

---

## Task 4: 验证 + 验收清单 + 清理备份

**Files:**
- None（验证任务，不改代码文件）
- Delete: `desk-assistant/pyproject.toml.old.bak`（最后清理）

**Interfaces:**
- Consumes: Task 1+2+3 全部完成
- Produces: 验收通过证明（user site 未动 + bash 脚本跑通 + 13 项验收清单）

- [ ] **Step 1：验收 1-2：pyproject.toml + .python-version**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
cat .python-version
echo "---"
python3 -c "import tomllib; d = tomllib.load(open('pyproject.toml','rb')); print('project name:', d['project']['name']); print('requires-python:', d['project']['requires-python']); print('dependencies:', d['project']['dependencies']); print('build extras:', d['project']['optional-dependencies']['build']); print('package:', d['tool']['uv']['package']); print('has scripts:', 'scripts' in d.get('tool', {}).get('uv', {}))"
```

预期：
- `.python-version` 输出 `3.6`
- `project name: desk-assistant`
- `requires-python: >=3.6.8,<3.7`
- `dependencies: []`
- `build extras: ['pyinstaller==4.10', 'pyinstaller-hooks-contrib==2022.0']`
- `package: False`
- `has scripts: False`（确认 [tool.uv.scripts] 不存在）

- [ ] **Step 2：验收 3-4：uv.lock + .venv/**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
ls -la uv.lock .venv/bin/python3.6
echo "---"
.venv/bin/python3.6 -m pip list 2>&1 | grep -E "pyinstaller|hooks-contrib"
```

预期：
- `uv.lock` 存在
- `.venv/bin/python3.6` 存在
- `.venv/bin/python3.6 -m pip list` 输出 `pyinstaller==4.10` + `pyinstaller-hooks-contrib==2022.0`

- [ ] **Step 3：验收 5：user site 未被 uv 触碰（关键安全检查）**

```bash
diff /tmp/user-site-baseline.txt <(/usr/bin/python3.6 -m pip list) && echo "USER SITE UNCHANGED" || echo "USER SITE CHANGED!"
```

预期：输出 `USER SITE UNCHANGED`。如果 changed，**停下找原因**。

- [ ] **Step 4：验收 6：tools/ 不存在**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
[ ! -d tools ] && echo "tools/ absent" || echo "tools/ STILL EXISTS"
```

预期：`tools/ absent`。

- [ ] **Step 5：验收 7：bash 脚本未修改**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git log --oneline -1 -- desk-assistant/script/build.sh
git log --oneline -1 -- desk-assistant/script/install.sh
git log --oneline -1 -- desk-assistant/script/uninstall.sh
git log --oneline -1 -- desk-assistant/script/desk-assistant_run.sh
```

预期：4 个脚本的最后 commit 都不是本 plan 的 commit（应该是某个旧 commit，如 `3782758 docs(panel)` 或更早）。

- [ ] **Step 6：验收 8-9：uv sync 退出码 0**

```bash
cd /home/10312862@zte.intra/.pkm/20_20260422_桌面助手/desk-assistant
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
uv sync --extra build 2>&1 | tail -3
echo "exit: $?"
echo "---"
uv sync 2>&1 | tail -3
echo "exit: $?"
```

预期：两个 `uv sync` 都成功（exit 0）。

- [ ] **Step 7：验收 10：bash script/build.sh 跑通（PyInstaller，约 1-2 分钟）**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
rm -rf dist/ build/  # 清干净
bash script/build.sh 2>&1 | tail -15
ls -la dist/ 2>&1
```

预期：
- 输出"==> [1/3] 检查依赖" / "[2/3] 打包 server" / "[3/3] 打包 panel" 三阶段
- `dist/desk-assistant-server` 存在（可执行）
- `dist/desk-assistant-panel` 存在（可执行）
- 退出码 0

> 该任务可能耗时 1-3 分钟（PyInstaller --onefile 慢）。如果失败，记录错误并停下。

- [ ] **Step 8：验收 11：README.md 含 "uv 依赖管理" 章节**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
grep -c "^## uv 依赖管理" README.md
```

预期：输出 `1`（章节存在）。

- [ ] **Step 9：验收 12-13：.gitignore 包含 .venv，不包含 uv.lock**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
grep -F ".venv" .gitignore && echo "OK: .venv ignored"
[ "$(grep -F "uv.lock" .gitignore)" = "" ] && echo "OK: uv.lock not ignored"
```

预期：两个 `OK:` 都打印。

- [ ] **Step 10：清理备份**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
rm -f pyproject.toml.old.bak
ls pyproject.toml.old.bak 2>&1 || echo "backup cleaned"
```

预期：输出 `backup cleaned`。

- [ ] **Step 11：跑完整 spec §11 验收清单 13 项**

逐条核对（手填 ✅/❌）：

```markdown
- [ ] pyproject.toml 存在且内容符合 §4
- [ ] .python-version 存在且内容 3.6
- [ ] uv.lock 存在
- [ ] .venv/ 存在且含 pyinstaller==4.10 + pyinstaller-hooks-contrib==2022.0
- [ ] user site 的 PyQt5 + flask + requests 未被 uv 触碰
- [ ] tools/ 目录不存在
- [ ] script/build.sh 等 4 个脚本内容未修改
- [ ] uv sync --extra build 退出码 0
- [ ] uv sync（不传 --extra build）退出码 0
- [ ] bash script/build.sh 跑通
- [ ] README.md 加了 "uv 依赖管理" 章节
- [ ] .venv/ 在 .gitignore 中
- [ ] uv.lock 不在 .gitignore 中
```

- [ ] **Step 12：报告验收结果**

报告内容：
- 13 条验收清单逐条 ✅/❌
- dist/ 二进制大小
- 任何 ❌ 必须明确说

**不主动 git commit**。整个 plan 完成后等用户统一 ack 是否要 commit。

---

## Self-Review

**1. Spec 覆盖**（spec §11 验收清单 13 项 → 计划任务映射）：

| 验收项 | Task |
| --- | --- |
| pyproject.toml 符合 §4 | Task 1 Step 1-2 + Task 4 Step 1 |
| .python-version 内容 3.6 | Task 1 Step 3 + Task 4 Step 1 |
| uv.lock 存在 | Task 1 Step 9 + Task 4 Step 2 |
| .venv/ 装对包 | Task 1 Step 7 + Task 4 Step 2 |
| user site 未动 | Task 1 Step 8 + Task 4 Step 3 |
| tools/ 不存在 | Task 2 + Task 4 Step 4 |
| bash 脚本未修改 | Task 4 Step 5 |
| uv sync --extra build 退出码 0 | Task 1 Step 6 + Task 4 Step 6 |
| uv sync 退出码 0 | Task 4 Step 6 |
| bash script/build.sh 跑通 | Task 4 Step 7 |
| README.md 含新章节 | Task 3 + Task 4 Step 8 |
| .venv/ 在 .gitignore | Task 1 Step 4 + Task 4 Step 9 |
| uv.lock 不在 .gitignore | Task 4 Step 9 |

**2. 占位符扫描**：无 TBD / TODO / "类似 Task X"。

**3. 类型一致性**：本计划无函数签名；文件名路径用绝对路径全程一致。

**4. 范围检查**：4 个 Task，每 Task 独立可验收，符合"single implementation plan"。

**5. 风险**：
- Task 1 Step 6 `uv sync --extra build` 首次会下载（PyInstaller 4.10 + hooks-contrib 2022.0 都是 wheel），需 1-2 分钟
- Task 4 Step 7 `bash script/build.sh` PyInstaller 编译 1-3 分钟
- 两次"长时间操作"已加注释

**无 inline fix 需要。**

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-18-uv-projectization-implementation.md` (v2). Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

**Per memory rule: 不主动 commit**——每 Task 完成后报告，等用户明确说"commit"才 `git commit`。
