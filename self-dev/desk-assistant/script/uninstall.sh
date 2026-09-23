#!/bin/bash
# uninstall.sh — 桌面助手卸载脚本
#
# 流程：
#   1. 停止运行中的进程（通过 launcher）
#   2. sudo 删除 /usr/local/bin/desk-assistant_run.sh
#   3. 删除 ~/.desk-assistant/bin/ 下的二进制
#   4. 删除 ~/.config/autostart/ 中的桌面项
#   5. 默认保留数据目录 ~/.desk-assistant/；--purge 时一并删除
#
# 用法：bash script/uninstall.sh
#       bash script/uninstall.sh --purge   # 连数据/日志一起删

set -eu

DATA_DIR="$HOME/.desk-assistant"
BIN_DIR="$DATA_DIR/bin"
LAUNCHER_DST="/usr/local/bin/desk-assistant_run.sh"
AUTOSTART_DIR="$HOME/.config/autostart"
APPS_DIR="$HOME/.local/share/applications"

PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

echo "==> [1/4] 停止运行中的进程"
if [ -x "$LAUNCHER_DST" ]; then
    "$LAUNCHER_DST" stop || true
else
    pgrep -f "^$BIN_DIR/desk-assistant-panel\$"  | xargs -r kill 2>/dev/null || true
    pgrep -f "^$BIN_DIR/desk-assistant-server\$" | xargs -r kill 2>/dev/null || true
    echo "    (launcher 未安装，已尝试直接 kill 进程)"
fi

echo "==> [2/4] 删除 launcher"
if [ -e "$LAUNCHER_DST" ]; then
    sudo rm -f "$LAUNCHER_DST"
    echo "    ✓ removed $LAUNCHER_DST"
else
    echo "    (不存在，跳过)"
fi

echo "==> [3/4] 删除二进制"
removed=0
for f in "$BIN_DIR/desk-assistant-server" "$BIN_DIR/desk-assistant-panel"; do
    if [ -e "$f" ]; then
        rm -f "$f"
        echo "    ✓ removed $f"
        removed=1
    fi
done
[ $removed -eq 0 ] && echo "    (无二进制需要删除)"
rmdir "$BIN_DIR" 2>/dev/null || true

echo "==> [4/4] 删除 autostart / 应用菜单 / 桌面项"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
removed=0
for f in \
    "$AUTOSTART_DIR/desk-assistant-server.desktop" \
    "$AUTOSTART_DIR/desk-assistant-panel.desktop" \
    "$APPS_DIR/desk-assistant.desktop" \
    "$DESKTOP_DIR/desk-assistant.desktop"; do
    if [ -e "$f" ]; then
        rm -f "$f"
        echo "    ✓ removed $f"
        removed=1
    fi
done
[ $removed -eq 0 ] && echo "    (无桌面项需要删除)"
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$APPS_DIR" 2>/dev/null || true

echo ""
if [ -d "$DATA_DIR" ]; then
    if [ $PURGE -eq 1 ]; then
        rm -rf "$DATA_DIR"
        echo "✓ 已删除数据目录 $DATA_DIR (--purge)"
    else
        echo "数据目录保留: $DATA_DIR"
        echo "  如需一并删除，重跑：bash script/uninstall.sh --purge"
    fi
fi

echo ""
echo "✓ 卸载完成"
