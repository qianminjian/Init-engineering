"""Agent Skill 入口 — ae init 作为 Claude Code Skill 运行.

用法:
    from init_engineering.skill import skill
    result = skill("init my-project --type app-service")
    result = skill("analyze /path/to/existing/project")

作为 Claude Code Skill 调用时, skill() 接收结构化命令字符串,
解析后调用 InitWorker 或 ProjectDetector, 返回结构化结果.

Skill 描述 (用于 Claude Code skill 注册):
    "初始化项目环境: ae init <project> --type <type>
     分析存量项目: ae init --analyze <path>"

P1-3: 拆为 skill/ 子包 — SkillResult + skill() 在 __init__.py,
_parse_prompt → _parse.py, _run_* → _runner.py.
"""

from __future__ import annotations

import logging
from pathlib import Path

import click

from ._parse import _parse_prompt
from ._runner import _run_analyze, _run_detect, _run_init
from ._types import SkillResult

_logger = logging.getLogger(__name__)


def skill(command_str: str, cwd: Path | None = None) -> SkillResult:
    """解析结构化指令并执行对应的 init 操作。

    ⚠ 隐式副作用: 未传 cwd 时默认绑定进程当前工作目录 (Path.cwd())，
    调用方应始终显式传入 cwd 以避免非确定性行为。

    Args:
        command_str: 结构化命令字符串，如 "init my-project --type app-service"
        cwd: 当前工作目录。传入 None 时回退到 Path.cwd()

    Returns:
        SkillResult: 执行结果
    """
    if cwd is None:
        cwd = Path.cwd()

    # 解析指令
    action, project_path, options = _parse_prompt(command_str)

    if action == "analyze":
        return _run_analyze(project_path, cwd)
    elif action == "init":
        return _run_init(project_path, options, cwd)
    elif action == "detect":
        return _run_detect(project_path, cwd)
    else:
        return SkillResult(
            success=False,
            message=(
                f"未知指令动词 '{action}'。"
                f"支持: init <project> [--type <type>] [options], "
                f"analyze <path>, detect <path>"
            ),
            action="parse",
        )


# Claude Code Skill 入口点
# 当作为 Skill 调用时, Claude Code 会调用 skill() 函数
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        result = skill(" ".join(sys.argv[1:]))
        click.echo(result.message)
        sys.exit(0 if result.success else 1)
    else:
        click.echo("Usage: python -m init_engineering.skill <command>")
        click.echo("  analyze <path>  - 分析存量项目")
        click.echo("  detect <path>  - 检测项目类型")
        click.echo("  init <project> [--type <type>] - 初始化新项目")
