#!/bin/bash
# test.sh — 桌面助手测试一键执行
#
# 行为：
#   1. 检查 pytest / coverage 依赖
#   2. 强制使用 DESK_ASSISTANT_DB=state_test.db（防污染生产）
#   3. offscreen 模式跑 panel 测试（无需 DISPLAY）
#   4. 失败条件（任一满足即非零退出）：
#        - 任何 pytest 用例失败 / 错误
#        - 行覆盖率 < LINE_THRESHOLD  (默认 85)
#        - 分支覆盖率 < BRANCH_THRESHOLD (默认 70)
#
# 输出格式：4 段（运行 / 行覆盖 / 分支覆盖 / 总结），最终 OK / FAIL 一目了然。
#
# 用法：bash test.sh
#       bash test.sh -v
#       bash test.sh tests/test_db.py
#       LINE_THRESHOLD=90 BRANCH_THRESHOLD=80 bash test.sh

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
DESK_DIR="$PROJECT_DIR/desk-assistant"

# ---- 1. 前置检查 ----

PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "✗ python3 not found (set PYTHON_BIN=/path/to/python3)"
    exit 1
fi

for mod in pytest coverage; do
    if ! "$PYTHON_BIN" -c "import $mod" >/dev/null 2>&1; then
        echo "✗ missing module: $mod (pip install pytest coverage)"
        exit 1
    fi
done

if ! "$PYTHON_BIN" -c "import PyQt5" >/dev/null 2>&1; then
    echo "✗ missing module: PyQt5"
    exit 1
fi

# ---- 2. 隔离配置 ----

export DESK_ASSISTANT_DB="${DESK_ASSISTANT_DB:-state_test.db}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"

LINE_THRESHOLD="${LINE_THRESHOLD:-85}"
BRANCH_THRESHOLD="${BRANCH_THRESHOLD:-70}"

cd "$DESK_DIR"

# ---- 3. 跑测试 + 收集覆盖率 ----

rm -f .coverage .coverage.*
COVERAGE_TARGETS="--source=server,panel"

echo "==> [1/4] 运行测试 + 收集行/分支覆盖率"
echo "    DESK_ASSISTANT_DB=$DESK_ASSISTANT_DB"
echo "    QT_QPA_PLATFORM=$QT_QPA_PLATFORM"
echo "    阈值：行 ≥ ${LINE_THRESHOLD}%  分支 ≥ ${BRANCH_THRESHOLD}%"
echo ""

set +e
"$PYTHON_BIN" -m coverage run $COVERAGE_TARGETS --branch -m pytest "$@" -q --tb=short
TEST_EXIT=$?
set -e

# ---- 4. 生成 report（仅一次，下面两段都从这里解析）----

echo ""
echo "==> [2/4] 行覆盖率（阈值 ${LINE_THRESHOLD}%）"
set +e
REPORT_TEXT="$("$PYTHON_BIN" -m coverage report)"
REPORT_EXIT=$?
set -e

if [ $REPORT_EXIT -ne 0 ]; then
    echo "✗ coverage report 执行失败（exit=$REPORT_EXIT）"
    echo "    测试是否运行了？.coverage 数据是否被外部清理？"
    exit 2
fi

# 打印原 report（顺手给用户看每个文件的覆盖率）
echo "$REPORT_TEXT"

# 解析 TOTAL 行：Stmts Miss Branch BrPart Cover
COVERAGE_INFO="$("$PYTHON_BIN" -c "
import re, sys
m = re.search(r'^TOTAL\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+\d+%\s*$',
              '''$REPORT_TEXT''', re.MULTILINE)
if not m:
    print('PARSE_ERROR'); sys.exit(0)
stmts, miss, branch, brpart = (int(x) for x in m.groups())
line_pct = (stmts - miss) * 100.0 / stmts
branch_pct = (branch - brpart) * 100.0 / branch
print(f'{line_pct:.1f} {branch_pct:.1f} {stmts} {miss} {branch} {brpart}')
")"

if [ "$COVERAGE_INFO" = "PARSE_ERROR" ] || [ -z "$COVERAGE_INFO" ]; then
    echo ""
    echo "✗ 无法解析 coverage report 的 TOTAL 行"
    exit 2
fi

LINE_PCT=$(echo "$COVERAGE_INFO" | awk '{print $1}')
BRANCH_PCT=$(echo "$COVERAGE_INFO" | awk '{print $2}')
STMTS=$(echo "$COVERAGE_INFO" | awk '{print $3}')
MISS=$(echo "$COVERAGE_INFO" | awk '{print $4}')
BRANCH=$(echo "$COVERAGE_INFO" | awk '{print $5}')
BRPART=$(echo "$COVERAGE_INFO" | awk '{print $6}')

# ---- 5. 判定行覆盖率 ----

LINE_EXIT=0
if awk "BEGIN{exit !($LINE_PCT < $LINE_THRESHOLD)}"; then
    echo ""
    echo "✗ 行覆盖率 ${LINE_PCT}% < 阈值 ${LINE_THRESHOLD}%"
    echo "    未覆盖行：${MISS} / ${STMTS}"
    LINE_EXIT=1
else
    echo ""
    echo "✓ 行覆盖率 ${LINE_PCT}% ≥ ${LINE_THRESHOLD}%  (${STMTS} 行，${MISS} 未覆盖)"
fi

# ---- 6. 判定分支覆盖率 ----

echo ""
echo "==> [3/4] 分支覆盖率（阈值 ${BRANCH_THRESHOLD}%）"
echo "    覆盖：$((BRANCH - BRPART)) / ${BRANCH}（partial = ${BRPART}）"
BRANCH_EXIT=0
if awk "BEGIN{exit !($BRANCH_PCT < $BRANCH_THRESHOLD)}"; then
    echo "✗ 分支覆盖率 ${BRANCH_PCT}% < 阈值 ${BRANCH_THRESHOLD}%"
    BRANCH_EXIT=1
else
    echo "✓ 分支覆盖率 ${BRANCH_PCT}% ≥ ${BRANCH_THRESHOLD}%"
fi

# ---- 7. 总结 ----

echo ""
echo "==> [4/4] 结果"

OVERALL_EXIT=0
[ $TEST_EXIT -ne 0 ] && OVERALL_EXIT=1
[ $LINE_EXIT -ne 0 ] && OVERALL_EXIT=1
[ $BRANCH_EXIT -ne 0 ] && OVERALL_EXIT=1

if [ $OVERALL_EXIT -eq 0 ]; then
    echo "✓ OK  通过"
    printf "    测试:    全部通过\n"
    printf "    行覆盖:  %s%% ≥ %s%%\n" "$LINE_PCT" "$LINE_THRESHOLD"
    printf "    分支覆盖:%s%% ≥ %s%%\n" "$BRANCH_PCT" "$BRANCH_THRESHOLD"
    exit 0
else
    echo "✗ FAIL  失败"
    if [ $TEST_EXIT -ne 0 ]; then
        printf "    [✗] 测试:    有失败/错误 (exit=%d)\n" "$TEST_EXIT"
    else
        printf "    [✓] 测试:    全部通过\n"
    fi
    if [ $LINE_EXIT -ne 0 ]; then
        printf "    [✗] 行覆盖:  %s%% < %s%%  (未覆盖 %d / %d 行)\n" \
               "$LINE_PCT" "$LINE_THRESHOLD" "$MISS" "$STMTS"
    else
        printf "    [✓] 行覆盖:  %s%% ≥ %s%%\n" "$LINE_PCT" "$LINE_THRESHOLD"
    fi
    if [ $BRANCH_EXIT -ne 0 ]; then
        printf "    [✗] 分支覆盖:%s%% < %s%%  (未覆盖 %d / %d 分支)\n" \
               "$BRANCH_PCT" "$BRANCH_THRESHOLD" "$BRPART" "$BRANCH"
    else
        printf "    [✓] 分支覆盖:%s%% ≥ %s%%\n" "$BRANCH_PCT" "$BRANCH_THRESHOLD"
    fi
    exit 1
fi
