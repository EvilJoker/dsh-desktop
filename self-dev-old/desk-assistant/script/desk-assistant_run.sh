#!/bin/bash
# desk-assistant_run.sh — 桌面助手启停脚本
# 安装位置：/usr/local/bin/desk-assistant_run.sh
# 二进制位置：~/.desk-assistant/bin/

set -eu

DATA_DIR="$HOME/.desk-assistant"
BIN_DIR="$DATA_DIR/bin"
LOG_DIR="$DATA_DIR/logs"
SERVER_BIN="$BIN_DIR/desk-assistant-server"
PANEL_BIN="$BIN_DIR/desk-assistant-panel"
SERVER_LOG="$LOG_DIR/server.log"
PANEL_LOG="$LOG_DIR/panel.log"
SERVER_PORT=18675

# 按 binary 全路径精确匹配进程 cmdline（PyInstaller --onefile boot loader + Python
# 子进程的 cmdline 都包含 binary 路径，用 pgrep -f 固定字符串一并杀掉）。
#
# 不能用 pgrep -x：Linux comm 字段只有 15 字符，desk-assistant-server/panel
# 都被截断为 "desk-assistant-"，区分不开。
_kill_by_name() {
    local bin_path=$1
    local pids
    # pgrep -f 默认走正则；用 -x 匹配整个 cmdline（精确字符串而非子串）
    pids=$(pgrep -f -x "$bin_path" 2>/dev/null | tr '\n' ' ' | sed 's/ *$//' || true)
    if [ -z "$pids" ]; then
        return 0
    fi
    # 先 SIGTERM 让进程优雅退出（PyInstaller 启动慢，给 0.5s）
    kill $pids 2>/dev/null || true
    sleep 0.5
    pids=$(pgrep -f -x "$bin_path" 2>/dev/null | tr '\n' ' ' | sed 's/ *$//' || true)
    if [ -n "$pids" ]; then
        kill -9 $pids 2>/dev/null || true
        sleep 0.2
    fi
}

# 仅用于 status 报告当前 PID，不参与启停决策
_pid_of() {
    pgrep -f -x "$1" 2>/dev/null | head -1 || true
}

start_one() {
    local name=$1 bin=$2 log=$3 prefix=${4:-}

    # 启动前先按 binary 全路径清理残留（防 setsid 孤儿、调试启动、手动跑的同名进程）
    _kill_by_name "$bin"

    if [ ! -x "$bin" ]; then
        echo "[$name] ✗ binary not found or not executable: $bin"
        return 1
    fi
    mkdir -p "$LOG_DIR"
    if [ -n "$prefix" ]; then
        env $prefix setsid "$bin" >> "$log" 2>&1 < /dev/null &
    else
        setsid "$bin" >> "$log" 2>&1 < /dev/null &
    fi
    # 给 boot loader 启动 + 解压 + python 初始化留时间
    sleep 0.8
    local pid
    pid=$(_pid_of "$bin")
    if [ -n "$pid" ]; then
        echo "[$name] ✓ started (PID $pid)"
    else
        echo "[$name] ✗ failed to start; check $log"
        return 1
    fi
}

stop_one() {
    local name=$1 bin=$2
    local pid
    pid=$(_pid_of "$bin")
    if [ -z "$pid" ]; then
        echo "[$name] not running"
        return 0
    fi
    _kill_by_name "$bin"
    echo "[$name] ✓ stopped (was PID $pid)"
}

cmd_start() {
    start_one server "$SERVER_BIN" "$SERVER_LOG" || return 1
    sleep 1
    # 必须传 XAUTHORITY：桌面图标点击 → .desktop → launcher 时没继承当前会话的
    # X cookie，会 fallback 到 ~/.Xauthority（老 MIT-MAGIC-COOKIE-1），跟 nde-panel
    # 当前会话的 /tmp/xauth_* 新 cookie 不同，panel 创建的窗口在 X server 上对
    # 用户会话的 xdotool/wmctrl 不可见。
    start_one panel "$PANEL_BIN" "$PANEL_LOG" "DISPLAY=${DISPLAY:-:0} XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}"
}

cmd_stop() {
    stop_one panel "$PANEL_BIN"
    stop_one server "$SERVER_BIN"
}

cmd_restart() {
    cmd_stop
    sleep 0.5
    cmd_start
}

cmd_status() {
    local s p port_info win_info
    s=$(_pid_of "$SERVER_BIN")
    p=$(_pid_of "$PANEL_BIN")
    if [ -n "$s" ]; then
        echo "server:  ✓ running (PID $s)"
        port_info=$(ss -tlnp 2>/dev/null | grep ":$SERVER_PORT " | head -1 | awk '{print $4}')
        [ -n "$port_info" ] && echo "         listening on $port_info"
    else
        echo "server:  ✗ stopped"
    fi
    if [ -n "$p" ]; then
        echo "panel:   ✓ running (PID $p)"
        win_info=$(DISPLAY=${DISPLAY:-:0} xwininfo -tree -root 2>/dev/null | grep DeskAssistantPanel | head -1)
        [ -n "$win_info" ] && echo "         window: $win_info"
    else
        echo "panel:   ✗ stopped"
    fi
}

usage() {
    cat <<EOF
Usage: $(basename "$0") {start|stop|restart|status}

桌面助手启停脚本
  start    启动 server + panel（后台运行）
  stop     停止 server + panel
  restart  重启
  status   查看运行状态、端口、窗口

二进制位置: $BIN_DIR/
数据/日志: $DATA_DIR/
EOF
}

case "${1:-help}" in
    start)    cmd_start ;;
    stop)     cmd_stop ;;
    restart)  cmd_restart ;;
    status)   cmd_status ;;
    -h|--help|help) usage ;;
    *)        usage; exit 1 ;;
esac