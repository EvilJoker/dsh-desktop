#!/bin/bash
# build.sh — 用 PyInstaller 把 server / panel 打包成单文件可执行
#
# 产物：
#   dist/desk-assistant-server
#   dist/desk-assistant-panel
#
# 用法：bash script/build.sh
#       PYTHON_BIN=/some/other/python3.6 bash script/build.sh   # 覆盖解释器
#
# 默认用 /usr/bin/python3.6（精确路径，不走 /usr/bin/python3 软链）
# 原因：/usr/bin/python3 受 update-alternatives 控制，可能被切到 3.10/3.11/3.13 等；
# python3.6 指向 /usr/libexec/platform-python3.6（受 RPM 包管理，不会因 alternatives 切换而变）
# 进一步精确可写 /usr/libexec/platform-python3.6，但本系统之外不一定有

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_DIR/dist"
BUILD_DIR="$PROJECT_DIR/build"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3.6}"

cd "$PROJECT_DIR"

echo "==> [1/3] 检查依赖"
$PYTHON_BIN -c "import PyInstaller, PyQt5, flask" 2>/dev/null \
    && echo "    ✓ pyinstaller / PyQt5 / flask OK" \
    || { echo "    ✗ 缺少依赖（pyinstaller / PyQt5 / flask）"; exit 1; }

mkdir -p "$BUILD_DIR"

echo "==> [2/3] 打包 server（约 1 分钟）"
$PYTHON_BIN -m PyInstaller --onefile --clean --noconfirm \
    --name desk-assistant-server \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR" \
    --specpath "$BUILD_DIR" \
    --paths server \
    --hidden-import db \
    --hidden-import metrics_store \
    --hidden-import events_store \
    --hidden-import sse_hub \
    server/app.py > "$BUILD_DIR/server-build.log" 2>&1 \
    || { echo "    ✗ server 打包失败 — 查看 $BUILD_DIR/server-build.log"; exit 1; }
echo "    ✓ $DIST_DIR/desk-assistant-server"

echo "==> [3/3] 打包 panel（约 2 分钟，PyQt5 体积大）"
$PYTHON_BIN -m PyInstaller --onefile --clean --noconfirm \
    --name desk-assistant-panel \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR" \
    --specpath "$BUILD_DIR" \
    --paths panel \
    --hidden-import base_chat_card \
    --hidden-import chat_card \
    --hidden-import xiaoou_card \
    --hidden-import events_card \
    --hidden-import metrics_card \
    --hidden-import config \
    --hidden-import theme \
    --hidden-import PyQt5.QtNetwork \
    --hidden-import PyQt5.QtGui \
    --hidden-import PyQt5.QtWidgets \
    panel/main.py > "$BUILD_DIR/panel-build.log" 2>&1 \
    || { echo "    ✗ panel 打包失败 — 查看 $BUILD_DIR/panel-build.log"; exit 1; }
echo "    ✓ $DIST_DIR/desk-assistant-panel"

echo ""
echo "✓ 构建完成"
ls -lh "$DIST_DIR/"
