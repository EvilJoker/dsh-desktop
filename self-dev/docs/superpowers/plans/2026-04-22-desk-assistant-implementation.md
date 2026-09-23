# Desk Assistant 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 desk-assistant 云桌面助手，首个功能为 CPU 监控告警（CPU > 90% 时弹出系统通知栏气泡）

**Architecture:** 使用 cron 定时任务每 10 分钟触发一次检测，超阈值则调用 notify-send 发送持久气泡通知

**Tech Stack:** Python 3 + psutil + cron + notify-send

**说明:** 初始设计使用 systemd timer，但部分环境存在兼容性问题（"Refusing to start, unit to trigger not loaded"），改用 cron 实现更稳定。

---

## 文件结构

```
desk-assistant/
├── desk_assistant.py       # 主程序（CLI + CPU 检测 + 告警）
├── install.sh              # 安装脚本
└── README.md              # 使用说明
```

（注：systemd 单元文件已创建但未使用，保留供参考）

---

## Task 1: 创建项目目录和 CLI 入口

**Files:**
- Create: `desk-assistant/desk_assistant.py`

- [ ] **Step 1: 创建 desk_assistant.py CLI 框架**

```python
#!/usr/bin/env python3
"""Desk Assistant - 云桌面助手"""

import sys
import argparse


def main():
    parser = argparse.ArgumentParser(prog='desk-assistant', description='云桌面助手')
    subparsers = parser.add_subparsers(dest='command', help='子命令')

    # install 子命令
    install_parser = subparsers.add_parser('install', help='安装到系统')

    # status 子命令
    status_parser = subparsers.add_parser('status', help='查看状态')

    # start 子命令
    start_parser = subparsers.add_parser('start', help='启动监控')

    # stop 子命令
    stop_parser = subparsers.add_parser('stop', help='停止监控')

    # uninstall 子命令
    uninstall_parser = subparsers.add_parser('uninstall', help='卸载')

    # run 子命令（内部使用）
    run_parser = subparsers.add_parser('run', help='执行一次 CPU 检测')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    print(f"desk-assistant {args.command}")


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 设置可执行权限并测试**

Run: `chmod +x desk-assistant/desk_assistant.py`
Run: `desk-assistant/desk_assistant.py`
Expected: 显示帮助信息

- [ ] **Step 3: 添加 shebang 并确认入口正确**

Run: `head -1 desk-assistant/desk_assistant.py`
Expected: `#!/usr/bin/env python3`

- [ ] **Step 4: 提交**

```bash
git add desk-assistant/desk_assistant.py
git commit -m "feat: 创建 desk-assistant CLI 框架"
```

---

## Task 2: 实现 CPU 检测和告警核心逻辑

**Files:**
- Modify: `desk-assistant/desk_assistant.py`

- [ ] **Step 1: 添加 CPU 检测函数**

```python
import psutil
import subprocess
from datetime import datetime

THRESHOLD = 90  # CPU 阈值 %


def get_cpu_percent() -> float:
    """获取 CPU 使用率（interval=1 秒）"""
    return psutil.cpu_percent(interval=1)


def send_notification(cpu_percent: float):
    """发送系统通知"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = f"当前: {cpu_percent:.1f}%\n时间: {timestamp}"

    subprocess.run([
        'notify-send',
        '-u', 'critical',
        '-a', 'Desk Assistant',
        '-t', '0',  # 不过期
        '⚠️ CPU 使用率过高',
        message
    ])


def check_and_alert():
    """检测 CPU 并在超阈值时告警"""
    cpu = get_cpu_percent()
    if cpu > THRESHOLD:
        send_notification(cpu)
```

- [ ] **Step 2: 在 run 子命令中调用检测逻辑**

```python
# run 子命令处理
if args.command == 'run':
    check_and_alert()
```

- [ ] **Step 3: 测试 CPU 检测**

Run: `python3 desk-assistant/desk_assistant.py run`
Expected: 无输出（CPU 未超阈值）或弹出通知（CPU 超阈值）

- [ ] **Step 4: 提交**

```bash
git add desk-assistant/desk_assistant.py
git commit -m "feat: 实现 CPU 检测和告警逻辑"
```

---

## Task 3: 实现 systemd 服务和定时器单元

**Files:**
- Create: `desk-assistant/desk_assistant.service`
- Create: `desk-assistant/desk_assistant.timer`

- [ ] **Step 1: 创建 desk_assistant.service**

```ini
[Unit]
Description=Desk Assistant Service
After=graphical.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/desk-assistant run
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: 创建 desk_assistant.timer**

```ini
[Unit]
Description=Desk Assistant Timer (every 10s)

[Timer]
OnBootSec=10s
OnUnitActiveSec=10s
Unit=desk-assistant.service

[Install]
WantedBy=timers.target
```

- [ ] **Step 3: 提交**

```bash
git add desk-assistant/desk_assistant.service desk-assistant/desk_assistant.timer
git commit -m "feat: 添加 systemd 服务和定时器单元"
```

---

## Task 4: 实现 install/start/stop/status/uninstall 子命令

**Files:**
- Modify: `desk-assistant/desk_assistant.py`

- [ ] **Step 1: 实现 install/start/stop/uninstall 子命令（使用 cron）**

```python
import subprocess

BIN_PATH = '/usr/local/bin/desk-assistant'
CRON_ENTRY = "*/10 * * * * /usr/local/bin/desk-assistant run"
SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))


def cmd_install(args):
    """安装到系统"""
    # 复制主程序
    subprocess.run(['sudo', 'cp', os.path.join(SOURCE_DIR, 'desk_assistant.py'), BIN_PATH])
    subprocess.run(['sudo', 'chmod', '+x', BIN_PATH])

    # 添加 crontab 任务
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    current_crontab = result.stdout if result.returncode == 0 else ""
    lines = [line for line in current_crontab.split('\n') if 'desk-assistant' not in line]
    lines.append(CRON_ENTRY)
    new_crontab = '\n'.join(lines).strip() + '\n'
    subprocess.run(['crontab', '-'], input=new_crontab, text=True)
    print('安装完成，开机自启已启用')


def cmd_status(args):
    """查看状态"""
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    if 'desk-assistant' in result.stdout:
        print('✓ 监控已启用（Cron 任务运行中）')
    else:
        print('✗ 监控未启用')


def cmd_start(args):
    """启动监控"""
    cmd_install(args)


def cmd_stop(args):
    """停止监控"""
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    if result.returncode == 0:
        lines = [line for line in result.stdout.split('\n') if 'desk-assistant' not in line]
        new_crontab = '\n'.join(lines).strip() + '\n'
        subprocess.run(['crontab', '-'], input=new_crontab, text=True)
    print('监控已停止')


def cmd_uninstall(args):
    """卸载"""
    cmd_stop(args)
    if os.path.exists(BIN_PATH):
        subprocess.run(['sudo', 'rm', BIN_PATH])
    print('卸载完成')
```

- [ ] **Step 2: 在 main() 中注册子命令处理函数**

```python
if args.command == 'run':
    check_and_alert()
elif args.command == 'install':
    cmd_install(args)
elif args.command == 'status':
    cmd_status(args)
elif args.command == 'start':
    cmd_start(args)
elif args.command == 'stop':
    cmd_stop(args)
elif args.command == 'uninstall':
    cmd_uninstall(args)
```

- [ ] **Step 3: 测试 install 命令（dry-run 模式）**

Run: `python3 desk-assistant/desk_assistant.py install --help`
Expected: 显示 install 帮助信息

- [ ] **Step 4: 提交**

```bash
git add desk-assistant/desk_assistant.py
git commit -m "feat: 实现 install/start/stop/status/uninstall 子命令"
```

---

## Task 5: 创建安装脚本

**Files:**
- Create: `desk-assistant/install.sh`

- [ ] **Step 1: 创建 install.sh**

```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "安装 Desk Assistant..."

# 复制主程序
sudo cp desk_assistant.py /usr/local/bin/desk-assistant
sudo chmod +x /usr/local/bin/desk-assistant

# 添加 crontab 任务（每 10 分钟检测一次）
(crontab -l 2>/dev/null | grep -v "desk-assistant run"; echo "*/10 * * * * /usr/local/bin/desk-assistant run") | crontab -

echo "安装完成！"
echo ""
echo "使用指令:"
echo "  desk-assistant status   - 查看状态"
echo "  desk-assistant start   - 启动（重启 cron）"
echo "  desk-assistant stop    - 停止（移除 cron）"
echo "  desk-assistant uninstall - 卸载"
```

- [ ] **Step 2: 设置执行权限**

Run: `chmod +x desk-assistant/install.sh`

- [ ] **Step 3: 提交**

```bash
git add desk-assistant/install.sh
git commit -m "feat: 添加 install.sh 安装脚本"
```

---

## Task 6: 创建 README

**Files:**
- Create: `desk-assistant/README.md`

- [ ] **Step 1: 编写 README**

```markdown
# Desk Assistant 云桌面助手

云桌面管理工具，提供系统监控告警功能。

## 首个功能

CPU 监控告警：当 CPU 使用率超过 90% 时，弹出系统通知栏气泡提醒。

## 系统要求

- Linux (NewStartOS 或其他 Linux 系统)
- Python 3.6+
- psutil

## 安装

```bash
./install.sh
```

## 使用指令

```bash
desk-assistant install    # 安装（添加 cron 任务，开机自启）
desk-assistant status     # 查看状态
desk-assistant start      # 启动
desk-assistant stop       # 停止
desk-assistant uninstall  # 卸载
desk-assistant run        # 手动触发一次检测
```

## 工作原理

- cron 任务每 10 分钟触发一次检测
- 检测 CPU 使用率（psutil）
- 若超 90% 阈值，发送持久系统通知
- 通知持续显示，直到用户手动关闭

## 验证

```bash
# 查看 cron 任务
crontab -l | grep desk

# 手动触发一次检测
desk-assistant run
```

## 卸载

```bash
desk-assistant uninstall
```
```

- [ ] **Step 2: 提交**

```bash
git add desk-assistant/README.md
git commit -m "docs: 添加 README"
```

---

## Task 7: 手动安装测试

- [ ] **Step 1: 执行安装脚本**

Run: `cd desk-assistant && ./install.sh`

- [ ] **Step 2: 验证 cron 任务已添加**

Run: `crontab -l | grep desk`
Expected: `*/10 * * * * /usr/local/bin/desk-assistant run`

- [ ] **Step 3: 手动触发一次测试**

Run: `desk-assistant run`
Expected: 无输出（CPU 未超阈值）或弹出通知（CPU 超阈值）

- [ ] **Step 4: 测试 stop 命令**

Run: `desk-assistant stop`
Run: `crontab -l | grep desk`
Expected: 无输出（cron 条目已移除）

- [ ] **Step 5: 测试 uninstall**

Run: `desk-assistant uninstall`
Run: `which desk-assistant`
Expected: 无输出（命令已删除）

---

## Task 8: 最终提交和检查

- [ ] **Step 1: 确认所有文件就位**

```
desk-assistant/
├── desk_assistant.py       # 主程序
├── desk_assistant.service  # systemd 服务（保留未使用）
├── desk_assistant.timer    # systemd 定时器（保留未使用）
├── install.sh              # 安装脚本
└── README.md              # 文档
```

- [ ] **Step 2: 检查代码质量**

Run: `python3 -m py_compile desk-assistant/desk_assistant.py`
Expected: 无错误

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "feat: 完成 desk-assistant CPU 监控告警功能"
```
