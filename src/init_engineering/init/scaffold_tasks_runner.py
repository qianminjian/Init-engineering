"""Tasks phase — Jinja2 沙箱环境 + 钩子执行 + 内置钩子。

从 scaffold_phases.py 拆分（v2.5：501→300 行）。

设计：
- 与 TemplateRenderer.render_to() 保持一致：使用 SandboxedEnvironment（防 Jinja2 沙箱穿透）
- 提供项目级 Jinja2 全局函数 git_status_clean / project_exists
- 串行执行 tasks_before → run_builtin_hooks → tasks_after
"""

from __future__ import annotations

__all__ = ["run_tasks_phase"]

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

if TYPE_CHECKING:
    from .config_types import TemplateConfig

from .answers import AnswersMap
from .hooks import TaskRunner
from .scaffold_hooks import subprocess_run, run_builtin_hooks

_logger = logging.getLogger(__name__)


def run_tasks_phase(
    tmpdir: Path,
    dst_path: Path,
    template: TemplateConfig,
    answers: AnswersMap,
    current_phase: str,
    strict: bool,
    quiet: bool,
    default_timeout: int | None = None,
    no_install: bool = False,
) -> None:
    """执行 template.tasks_before → run_builtin_hooks → template.tasks_after.

    SandboxedEnvironment 含项目级全局函数：
    - git_status_clean() : git 工作区是否干净
    - project_exists(path) : 项目目录下指定路径是否存在

    PE-P1-4: default_timeout 透传到 TaskRunner — 模板作者可对慢任务在
    Task.timeout 字段覆盖,也可通过 CLI --hook-timeout 全局覆盖

    PE-P0-1: no_install 透传到 run_builtin_hooks,跳过 package_manager install 阶段
    """
    jinja_env = _build_jinja_env(dst_path)
    context = answers.combined()

    runner = TaskRunner(
        tmpdir,
        current_phase=current_phase,
        default_timeout=default_timeout,
        strict=strict,
    )
    runner.run(template.tasks_before, context, jinja_env)
    run_builtin_hooks(
        answers, tmpdir,
        strict=strict, quiet=quiet, no_install=no_install,
        default_timeout=default_timeout,
    )
    runner.run(template.tasks_after, context, jinja_env)


def _build_jinja_env(dst_path: Path) -> SandboxedEnvironment:
    jinja_env = SandboxedEnvironment(undefined=StrictUndefined)

    def _git_status_clean() -> bool:
        try:
            result = subprocess_run(
                ["git", "status", "--porcelain"],
                cwd=dst_path,
                timeout=10,  # PE-AUDIT-P0-1: local read, clamp to 10s
            )
        except subprocess.TimeoutExpired:
            _logger.warning("git status --porcelain timed out after 10s, assuming dirty repo", exc_info=True)
            return False  # 安全选择: 超时视为非空,模板作者应排查仓库状态
        return result.stdout.strip() == ""

    def _project_exists(path: str) -> bool:
        p = (dst_path / path.strip()).resolve()
        return p.exists()

    jinja_env.globals["git_status_clean"] = _git_status_clean
    jinja_env.globals["project_exists"] = _project_exists
    return jinja_env
