# Desk Assistant 云桌面助手

## 背景与目标

Desk Assistant 是云桌面管理工具，提供系统监控告警功能。首个功能：CPU 监控告警。当 CPU 使用率超过 90% 时，通过系统通知栏气泡提醒用户，防止因 CPU 过载导致系统卡死。

## 需求确认

| 项目 | 值 |
|------|-----|
| 操作系统 | Linux (NewStartOS V4.4.2) |
| 告警方式 | 系统通知栏气泡 (notify-send) |
| 历史记录 | 无 |
| 运行方式 | 长期后台运行，开机自启 |
| 定时器 | cron |
| 检测频率 | 每 10 分钟 |
| 告警阈值 | CPU > 90% |
| 技术栈 | Python + cron + notify-send |
| 命令名 | `desk-assistant` |
| 安装路径 | `/usr/local/bin/desk-assistant` |

**说明**: 初始设计使用 systemd timer，但部分环境存在兼容性问题，改用 cron 实现更稳定。

## 整体架构

```
┌─────────────────────────────────────────────┐
│              cron 定时任务                   │
│                                             │
│  ┌───────────────┐    ┌──────────────────┐ │
│  │  CPU 检测进程  │───▶│  notify-send     │ │
│  │  (psutil)     │    │  系统通知栏气泡    │ │
│  └───────────────┘    └──────────────────┘ │
│         ▲                                    │
│         │ 每 10 分钟执行                     │
└─────────┼────────────────────────────────────┘
          │
    cron 调度
    (*/10 * * * *)
```

## 工作模式

采用 **cron 调度** 的短时任务模式：

1. cron 每 10 分钟触发一次
2. 进程读取 CPU 使用率
3. 若超阈值则发送通知
4. 进程执行完毕立即退出（非持续驻留）

**优势**：兼容性好，稳定可靠，开机自启

## 文件结构

```
desk-assistant/
├── desk_assistant.py       # 主程序（检测 + 告警）
├── install.sh              # 安装脚本
└── README.md              # 使用说明
```

（systemd 单元文件已创建但未使用，保留供参考）

## 核心实现

### desk_assistant.py

使用 `psutil.cpu_percent()` 获取 CPU 使用率，通过 `notify-send` 发送系统通知。

### desk_assistant.service

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

### desk_assistant.timer

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

## 告警效果

```
┌──────────────────────────────────┐
│ ⚠️ CPU 使用率过高                │
│                                  │
│ 当前: 92.5%                      │
│ 时间: 2026-04-22 10:50:30       │
└──────────────────────────────────┘
        (持续显示，不自动消失)
```

## 使用指令

```bash
# 安装（复制文件 + systemd + 开机自启）
desk-assistant install

# 查看状态
desk-assistant status

# 启动
desk-assistant start

# 停止
desk-assistant stop

# 卸载
desk-assistant uninstall
```

## cron 原始指令（参考）

```bash
# 安装
cp desk_assistant.py /usr/local/bin/desk-assistant
chmod +x /usr/local/bin/desk-assistant
(crontab -l 2>/dev/null | grep -v "desk-assistant run"; echo "*/10 * * * * /usr/local/bin/desk-assistant run") | crontab -

# 状态
crontab -l | grep desk

# 启动（重新添加 cron 任务）
desk-assistant install

# 停止（移除 cron 任务）
desk-assistant stop

# 卸载
desk-assistant uninstall
```

## 后续扩展方向（本次不实现）

- 内存使用率监控
- 磁盘空间监控
- 网络流量监控
- 告警历史记录
