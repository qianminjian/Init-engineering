#!/usr/bin/env bash
# scripts/setup.sh — Init-Engineering 一键安装脚本
# 团队成员 git clone 后执行: ./scripts/setup.sh
# 功能:
#   1. uv sync --dev 装 Python 依赖
#   2. 验证 ae CLI 可用
#   3. 输出验证结果
# 参考: lark-workflow-weekly-report/scripts/setup.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# 1. 检查 uv 是否安装
if ! command -v uv >/dev/null 2>&1; then
    echo "[ERROR] uv 未安装。请先运行:" >&2
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

# 2. uv sync (装 dev extras: pytest/ruff 等)
echo "[setup] uv sync --dev --extra dev ..."
uv sync --dev --extra dev

# 3. 验证 ae CLI
echo "[setup] 验证 ae CLI ..."
if uv run ae --version >/dev/null 2>&1; then
    VERSION=$(uv run ae --version)
    echo "[setup] ✓ $VERSION"
else
    echo "[ERROR] ae CLI 不可用,请检查依赖安装。" >&2
    exit 1
fi

# 4. 提示下一步
echo ""
echo "[setup] ✓ 安装完成。下一步:"
echo "  ae init --help                    # 查看命令"
echo "  ae init my-app --type app-service # 创建新项目"
echo "  ae init --analyze .               # 分析当前目录"
