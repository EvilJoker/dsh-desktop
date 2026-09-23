#!/bin/bash
# install.sh — 桌面助手安装脚本
#
# 流程：
#   1. 调用 build.sh 编译产物到 dist/
#   2. 复制二进制到 ~/.desk-assistant/bin/
#   3. sudo 复制 launcher (desk-assistant_run.sh) 到 /usr/local/bin/
#   4. 生成 ~/.config/autostart/*.desktop（开机自启）
#
# 用法：bash script/install.sh
#       PYTHON_BIN=/usr/bin/python3.6 bash script/install.sh   # 指定 python（精确路径，绕开 alternatives 软链）

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_DIR/dist"

DATA_DIR="$HOME/.desk-assistant"
BIN_DIR="$DATA_DIR/bin"
LOG_DIR="$DATA_DIR/logs"
ICON_SRC="$PROJECT_DIR/assets/hamster.svg"
ICON_DST="$DATA_DIR/icon.svg"
LAUNCHER_SRC="$SCRIPT_DIR/desk-assistant_run.sh"
LAUNCHER_DST="/usr/local/bin/desk-assistant_run.sh"
AUTOSTART_DIR="$HOME/.config/autostart"
APPS_DIR="$HOME/.local/share/applications"

SERVER_SRC="$DIST_DIR/desk-assistant-server"
PANEL_SRC="$DIST_DIR/desk-assistant-panel"
SERVER_DST="$BIN_DIR/desk-assistant-server"
PANEL_DST="$BIN_DIR/desk-assistant-panel"

echo "==> [1/5] 构建产物"
if [ ! -x "$SERVER_SRC" ] || [ ! -x "$PANEL_SRC" ]; then
    bash "$SCRIPT_DIR/build.sh"
else
    echo "    ✓ 已有产物，跳过构建（如需重建：rm -rf dist && bash script/build.sh）"
fi

echo "==> [2/5] 部署二进制 + 图标到 $DATA_DIR"
mkdir -p "$BIN_DIR" "$LOG_DIR"
install -m 0755 "$SERVER_SRC" "$SERVER_DST"
install -m 0755 "$PANEL_SRC"  "$PANEL_DST"
install -m 0644 "$ICON_SRC"   "$ICON_DST"
echo "    ✓ $SERVER_DST"
echo "    ✓ $PANEL_DST"
echo "    ✓ $ICON_DST"

echo "==> [3/5] 部署 launcher 到 $LAUNCHER_DST（需要 sudo）"
sudo install -m 0755 "$LAUNCHER_SRC" "$LAUNCHER_DST"
echo "    ✓ $LAUNCHER_DST"

echo "==> [4/5] 生成 autostart 桌面项"
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/desk-assistant-server.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Desk Assistant Server
Comment=Background HTTP/SSE service for desk assistant panel
Exec=$SERVER_DST
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF
cat > "$AUTOSTART_DIR/desk-assistant-panel.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Desk Assistant Panel
Comment=Translucent dashboard panel pinned to desktop
Exec=$PANEL_DST
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF
echo "    ✓ $AUTOSTART_DIR/desk-assistant-{server,panel}.desktop"

echo "==> [5/5] 生成应用菜单 + 桌面启动图标"
mkdir -p "$APPS_DIR"
cat > "$APPS_DIR/desk-assistant.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=桌面助手
GenericName=Desk Assistant
Comment=点击启动看板（如后台服务未运行会一并拉起）
Exec=$LAUNCHER_DST start
Icon=$ICON_DST
Terminal=false
Categories=Utility;System;
StartupNotify=false
EOF
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
echo "    ✓ $APPS_DIR/desk-assistant.desktop（应用菜单）"

# 桌面图标（部分桌面环境不索引 ~/.local/share/applications/，桌面图标作为兜底入口）
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$DESKTOP_DIR" ]; then
    install -m 0755 "$APPS_DIR/desk-assistant.desktop" "$DESKTOP_DIR/desk-assistant.desktop"
    # GNOME / 部分桌面需要标记为受信任才能直接点击
    command -v gio >/dev/null 2>&1 && \
        gio set "$DESKTOP_DIR/desk-assistant.desktop" metadata::trusted true 2>/dev/null || true
    echo "    ✓ $DESKTOP_DIR/desk-assistant.desktop（桌面快捷方式）"
fi

cat <<EOF

✓ 安装完成

立即启动:  desk-assistant_run.sh start
查看状态:  desk-assistant_run.sh status
停止:      desk-assistant_run.sh stop
重启:      desk-assistant_run.sh restart

下次注销重新登录或重启后会自动启动。
EOF
