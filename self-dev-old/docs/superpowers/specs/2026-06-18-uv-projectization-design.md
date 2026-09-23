---
date: 2026-06-18
status: draft
revision: 2
topic: uv 项目化（依赖锁定 + venv 隔离 build-time 包）
target: desk-assistant v3.1
---

# 桌面助手 uv 项目化设计 v2

> **v2 变更**：v1 设计用 `[tool.uv.scripts]` 包装 bash 脚本作为 `uv run <name>` 入口，
> 实施时发现 uv 0.11.6 不支持 `[tool.uv.scripts]` 字段（不在 `[tool.uv.*]` 合法字段列表中，
> 也不在 uv 官方文档中）。v2 改为：**uv 只做依赖管理**（锁版本 + 创 venv + 生成 uv.lock），
> bash 脚本和 launcher 保持现状。

## 1. 背景与目标

桌面助手当前是"裸 Python 项目"——没有 `pyproject.toml`、没有 lockfile、没有 venv。
build/install/uninstall/service 全靠 `script/*.sh` 直接调 `/usr/bin/python3.6`，
依赖（`PyQt5==5.15.6`、`pyinstaller==4.10`、`flask==2.0.3` 等）零散装在
`~/.local/lib/python3.6/site-packages/`。

后果：
- 重装系统后要手动按记忆敲 `/usr/bin/python3.6 -m pip install --user` 一堆命令
- pyinstaller 装在 user site 容易被误删/被其他工具覆盖
- 跨机器/换同事开发时环境无法保证一致

**本文档目标**：
- 把桌面助手项目化（`pyproject.toml` + `uv.lock` + `.venv` + `.python-version`）
- 用 uv 创 **`.venv/`** 隔离**开发时**需要的 build-time 依赖（pyinstaller 4.10、pyinstaller-hooks-contrib 2022.0）
- **运行时依赖不动**：PyQt5 5.15.6（源码编译产物，ABI 对齐系统 Qt 5.12.5）、PyQt5-sip、sip、flask、requests 仍装在 user site，由 `script/build.sh` 调 `/usr/bin/python3.6` 使用
- `script/*.sh` 一行不改，`/usr/local/bin/desk-assistant_run.sh` 一行不改，autostart .desktop 一行不改

## 2. 入口（双层）

### 运行时入口（不变）

| 入口 | 用途 |
|------|------|
| `bash script/build.sh` | PyInstaller 打包 server + panel → `dist/` |
| `bash script/install.sh` | 编译 + 部署 + 配开机自启（sudo） |
| `bash script/uninstall.sh` | 反向清理（`--purge` 删数据） |
| `bash script/desk-assistant_run.sh {start\|stop\|restart\|status}` | 启停 + 状态 |
| `/usr/local/bin/desk-assistant_run.sh` | install 后装到 PATH 的 launcher（autostart .desktop 指向它） |

### 开发时入口（uv）

| 命令 | 作用 |
|------|------|
| `uv sync --extra build` | 创 `.venv/` + 装 pyinstaller 4.10 + pyinstaller-hooks-contrib 2022.0 + 生成 `uv.lock` |
| `uv sync` | 只装空 `dependencies`（实际啥也不装） |
| `uv lock` | 重生成 `uv.lock`（不安装） |

**不引入 `uv run` 入口**——bash 脚本已存在且工作正常，uv run 多此一举且 uv 0.11.6 无 `[tool.uv.scripts]` 支持。

## 3. 文件结构

```text
desk-assistant/
├── pyproject.toml                       # 新增（PEP 621 + [tool.uv] package=false）
├── .python-version                      # 新增（"3.6"）
├── uv.lock                              # uv sync 自动生成（提交到 git）
├── .venv/                               # uv sync 创出（gitignore）
├── README.md                            # 改：新增 "uv 依赖管理" 章节
├── docs/
│   ├── pyqt5-abi-fix.md                 # 不动
│   └── superpowers/specs/...            # 历史 spec
├── panel/                               # 不动
├── server/                              # 不动
├── tests/                               # 不动
├── assets/                              # 不动
└── script/                              # ✓ 全部保留（内容一行不改）
    ├── build.sh
    ├── install.sh
    ├── uninstall.sh
    └── desk-assistant_run.sh
```

**删除的产物**：
- `desk-assistant/tools/` 整个目录——之前头脑风暴初期按 Python CLI 方案写的：
  - `tools/lib/__init__.py` `tools/lib/paths.py` `tools/lib/log.py` `tools/lib/run.py` `tools/lib/process.py`
  - `tools/commands/__init__.py`
  - （`tools/cli.py` 在本 spec v1 写过但实际未创建，无需删除）

## 4. pyproject.toml 完整内容

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

### .python-version

```text
3.6
```

uv 找不到 3.6 时自动 fallback 到系统 `/usr/bin/python3.6`。

## 5. 关键决策

| 决策点 | 方案 | 理由 |
|--------|------|------|
| 用 uv 而不是 poetry/pdm | **uv**（用户指定） | Rust 写、流程化、速度快、社区主流 |
| 用 uv 干什么 | **依赖管理 + venv 隔离** | 用户明确"用 uv 是因为他有比较健全的版本管理机制" |
| venv 装什么 | **只装 build-time 包**（pyinstaller 4.10 + hooks-contrib 2022.0） | user site 已有 PyQt5 等运行时包，venv 不重复装；uv 不重装 user site 包（会覆盖源码编译的 PyQt5 ABI） |
| 运行时依赖在哪 | **user site**（`~/.local/lib/python3.6/site-packages/`） | 现状如此；`/usr/bin/python3.6` 默认能 `import`；源码编译 PyQt5 ABI 已对齐系统 Qt 5.12.5 |
| bash 脚本处理 | **保留 + 不动** | 现状可用；uv 不增加新入口 |
| `uv run <name>` 入口 | **不做** | uv 0.11.6 无 `[tool.uv.scripts]`，且 `bash script/*.sh` 已够用 |
| `[project.scripts]` | **不引入** | 需要 wheel 分发或 `uv tool install`，与"项目不打包"冲突 |
| PyInstaller 版本 | **4.10 固定** | 4.10 是最后支持 Py 3.6 的版本；5.0+ 不兼容当前 Python 3.6.8 |
| pyinstaller-hooks-contrib 版本 | **2022.0 固定** | 兼容 PyInstaller 4.x 系列 |
| `package = false` | **开启** | 项目不打包成 wheel，panel/ server/ 仍是裸脚本 |
| `uv.lock` 提交 | **是** | 保证重装环境 100% 一致 |

## 6. 工作流

### 首次 clone + 准备开发

```bash
git clone <repo>
cd desk-assistant
uv sync --extra build       # 创 .venv/ 装 pyinstaller 4.10 + hooks-contrib 2022.0
```

### 日常开发（修改 panel / server 后打包）

```bash
# 直接用 bash 脚本（v3.1 不变）
bash script/build.sh        # PyInstaller 打包 → dist/
bash script/desk-assistant_run.sh start
```

### 部署到本机

```bash
bash script/install.sh      # 调用 build.sh + sudo 装 launcher + 配 autostart
```

### 跨机器复现环境

```bash
git clone <repo>
cd desk-assistant
uv sync --frozen --extra build      # 严格按 uv.lock 还原（CI / 重装环境用）
```

### 改依赖

```bash
vim pyproject.toml          # 改 build = [...] 里的版本
uv lock                     # 更新 uv.lock
uv sync --extra build       # 同步 .venv/
```

## 7. 范围

### 在范围（in scope）

| 任务 | 备注 |
|------|------|
| 创建 `pyproject.toml` | 完整内容见 §4 |
| 创建 `.python-version` | 内容 `3.6` |
| 生成 `uv.lock` | `uv sync --extra build` 自动生成 |
| 删除 `tools/` 目录 | 之前头脑风暴初期写的，全删 |
| 验证 `uv sync --extra build` 装 pyinstaller 4.10 到 .venv/ | 必须通过 |
| 验证 `uv sync` 不重装 user site 的 PyQt5/flask/requests | 必须通过（关键安全保证） |
| `bash script/build.sh` 跑通 | 验证运行时链路未受 venv 干扰 |
| `README.md` 加 "uv 依赖管理" 章节 | 简述 venv 用途 + uv sync 命令 |

### 不在范围（out of scope）

| 任务 | 备注 |
|------|------|
| 改 `script/*.sh` 内容 | 一行不改 |
| 改 `/usr/local/bin/desk-assistant_run.sh` | 仍是 bash 转发到 script/desk-assistant_run.sh |
| 改 `~/.config/autostart/*.desktop` | 仍指向 launcher |
| 改 `docs/pyqt5-abi-fix.md` | ABI 修复文档独立维护 |
| 改 user site 的 PyQt5/flask/requests | 这些是运行时依赖，不归 venv 管 |
| `uv run` 命令入口 | uv 0.11.6 不支持 `[tool.uv.scripts]`，且不需要 |
| 新增测试（bats / pytest） | 本次只项目化，不动测试 |
| 打包成 wheel / uv tool install | 弃用 Python CLI 方案 |
| Python 入口脚本（`[project.scripts]`） | 弃用 |
| 升级 pyinstaller 到 5.x | 用户机器 Py 3.6.8 不兼容 5.x；保持 4.10 |

## 8. 错误处理

- bash 脚本已有 `set -eu`，失败立即退出
- `uv sync` 失败立即退出（非零 exit code 透传给调用方）
- 不在本次 spec 范围新增错误处理逻辑

## 9. 测试

- 不在本次 spec 范围
- 现有 `tests/` 目录、`test.sh` 不动
- 验收：手工 `uv sync --extra build` 跑通 + `bash script/build.sh` 跑通

## 10. 风险与回滚

| 风险 | 影响 | 回滚 |
|------|------|------|
| `pyproject.toml` 写错导致 `uv sync` 失败 | 开发者环境无法创建 | 直接删 `pyproject.toml` + `uv.lock` + `.python-version`，回到裸 bash |
| `uv sync` 试图重装 PyQt5 覆盖源码编译产物 | 中文 IME 坏、ABI 不匹配系统 Qt | 已被 `dependencies = []` 规避；user site 的 PyQt5 不归 uv 管 |
| `uv` 在用户机器上未装 | 新入口不可用 | 旧入口 `bash script/*.sh` 仍可用，与 uv 无关 |
| pyinstaller 4.10 与 Python 3.6 实际不兼容 | build.sh 失败 | 退回到 pip 手动装：`/usr/bin/python3.6 -m pip install --user pyinstaller==4.10` |
| 删 `tools/` 误删其他文件 | 数据丢失 | `tools/` 内容是本次新增（v2 之前 brainstorm 写的），git status 可查；commit 前 review |

## 11. 验收清单

- [ ] `pyproject.toml` 存在且内容符合 §4
- [ ] `.python-version` 存在且内容 `3.6`
- [ ] `uv.lock` 存在（`uv sync` 生成）
- [ ] `.venv/` 存在且含 `pyinstaller==4.10` + `pyinstaller-hooks-contrib==2022.0`
- [ ] user site 的 PyQt5 5.15.6（源码编译）+ flask 2.0.3 + requests 2.27.1 **未被 uv 触碰**（`/usr/bin/python3.6 -m pip list` 输出不变）
- [ ] `tools/` 目录不存在
- [ ] `script/build.sh` `script/install.sh` `script/uninstall.sh` `script/desk-assistant_run.sh` 内容**未修改**（用 `git diff` 验证）
- [ ] `uv sync --extra build` 退出码 0
- [ ] `uv sync`（不传 `--extra build`）退出码 0
- [ ] `bash script/build.sh` 跑通（产出 `dist/desk-assistant-{server,panel}`）
- [ ] `README.md` 加了 "uv 依赖管理" 章节
- [ ] `.venv/` 在 `.gitignore` 中
- [ ] `uv.lock` **不在** `.gitignore`（要提交到 git）

