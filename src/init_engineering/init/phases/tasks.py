"""Phase 4: tasks — Jinja2 沙箱环境 + 钩子执行 + 内置钩子."""

from __future__ import annotations

from pathlib import Path

from ..answers import AnswersMap
from ..config import TemplateConfig
from ..scaffold_tasks_runner import run_tasks_phase as _run_tasks_phase


def phase_tasks(
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
    """执行 template.tasks_before + run_builtin_hooks + template.tasks_after."""
    _run_tasks_phase(
        tmpdir=tmpdir,
        dst_path=dst_path,
        template=template,
        answers=answers,
        current_phase=current_phase,
        strict=strict,
        quiet=quiet,
        default_timeout=default_timeout,
        no_install=no_install,
    )
