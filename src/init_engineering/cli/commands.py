"""CLI 子命令 — init 命令实现.

从 cli/__init__.py 拆分 (2026-07-03 深度审计 P2-A):
原 __init__.py 427 行超 300 行约束, 拆出:
- cmd_init (init 命令实现)
- --list-types / --list-templates / --analyze 已提升为独立命令 (2026-07-15 v5.5)
- update / status 命令拆到 cli/subcommands.py
"""

from __future__ import annotations

import logging
import time as _time
from pathlib import Path
from typing import TYPE_CHECKING

import click

from init_engineering import __version__
from init_engineering.cli._helpers import (
    configure_logging as _configure_logging,
)
from init_engineering.cli._helpers import (
    sanitize_error as _sanitize_error,
)
from init_engineering.init import InitResult

if TYPE_CHECKING:
    from typing import Any

    from init_engineering.init._shared.prompt_backend import PromptBackend

_logger = logging.getLogger(__name__)


def cmd_init(
    *,
    project: str | None,
    project_type: str | None,
    defaults: bool,
    force: bool,
    answers_file: str | None,
    language: str | None,
    package_manager: str | None,
    ci_platform: str | None,
    test_runner: str | None,
    use_typescript: bool | None,
    use_lefthook: bool | None,
    use_docker: bool | None,
    pretend: bool,
    skip_tasks: bool,
    no_install: bool,
    cleanup_on_error: bool,
    quiet: bool,
    verbose: bool,
    incremental: bool,
    strict: bool,
    template_dir_override: str | None,
    include_hidden: bool = False,
    prompt_backend: PromptBackend | None = None,
) -> InitResult | None:
    """init 命令实现 — 纯函数,接收已 click-解析的所有参数.

    v5.5: 移除 templates_suffix / preserve_symlinks / hook_timeout /
    force_unsafe_template / telemetry CLI 选项（内部 API 仍保留默认值）。
    --list-types / --list-templates / --analyze 已提升为独立命令。

    Returns:
        InitResult: 正常 init 流程完成时返回。
    """
    from init_engineering.init import InitWorker
    from init_engineering.init.errors import InitError

    dst_path = (Path(project) if project else Path.cwd()).resolve()

    # --from-answers: 从 .ae-answers.yml 恢复 + 隐式非交互
    if answers_file:
        from init_engineering.init import AnswersMap

        answers = AnswersMap.from_answers_file(Path(answers_file))
        if not quiet:
            click.echo(f"从 {answers_file} 恢复答案")
        if not project_type:
            project_type = answers.get("project_type", default="") or ""
        if not language:
            language = answers.get("language", default="") or "" or None
        defaults = True
    else:
        answers = None

    # --template-dir 白名单检查
    if template_dir_override:
        td = Path(template_dir_override).resolve()
        safe_roots = [Path.cwd(), Path.home() / ".ae-templates", Path("/tmp")]
        is_safe = any(
            str(td).startswith(str(r.resolve()) + "/") or td == r.resolve()
            for r in safe_roots if r.exists()
        )
        if not is_safe:
            raise click.UsageError(
                f"❌ --template-dir {td} 不在安全路径内 "
                f"({[str(r) for r in safe_roots if r.exists()]})。\n"
                f"请将模板放入 ~/.ae-templates/ 或当前项目目录下。"
            )

    _configure_logging(verbose=verbose)

    # 非 TTY 环境自动启用非交互模式。
    # --incremental 自身已隐含非交互（存量项目不弹问答），不需要 --defaults 的语义覆盖。
    # --defaults 意味着"全部使用模板默认值"；--incremental 意味着"使用检测值驱动渲染"。
    # 两者语义不同——incremental 走自己的 non_interactive 路径。
    import sys as _sys
    if (not _sys.stdin.isatty()) and not defaults and not incremental:
        if not quiet:
            click.echo("非 TTY 环境，自动启用 --defaults 模式", err=True)
        defaults = True

    _worker_kwargs = _build_init_worker_kwargs(
        dst_path=dst_path, project_type=project_type, language=language,
        package_manager=package_manager, ci_platform=ci_platform,
        test_runner=test_runner, use_typescript=use_typescript,
        use_lefthook=use_lefthook, use_docker=use_docker,
        defaults=defaults, force=force, pretend=pretend,
        skip_tasks=skip_tasks, no_install=no_install,
        cleanup_on_error=cleanup_on_error, quiet=quiet,
        verbose=verbose, incremental=incremental, strict=strict,
        template_dir_override=template_dir_override,
        prompt_backend=prompt_backend,
        include_hidden=include_hidden,
    )

    # B1: 必须用 with 块 — __exit__ → _cleanup() 释放 InitLock,
    # 否则 .ae-init.lock 残留,导致后续 --incremental 看到陈旧锁 / 第二个 init 误判
    with InitWorker(**_worker_kwargs) as worker:
        if answers:
            worker._previous_answers = answers

        _start_ts = _time.monotonic()
        _telemetry_error: str | None = None
        try:
            result = worker.execute()
            if not quiet and not pretend:
                _print_completion_report(result)
            return result
        except InitError as e:
            _telemetry_error = type(e).__name__
            _logger.error(
                "init failed for %s: %s (recovery: %s)",
                dst_path, e, e.recovery_hint or "无",
            )
            safe_msg = _sanitize_error(str(e))
            click.echo(f"✗ 初始化失败: {safe_msg}", err=True)
            raise SystemExit(e.exit_code) from e
        except Exception as e:
            _telemetry_error = type(e).__name__
            _logger.exception("init failed unexpectedly for %s", dst_path)
            safe_msg = _sanitize_error(str(e))
            click.echo(f"✗ 初始化失败: {safe_msg}", err=True)
            raise SystemExit(1) from e


def _build_init_worker_kwargs(
    *,
    dst_path: Path,
    project_type: str | None,
    language: str | None,
    package_manager: str | None,
    ci_platform: str | None,
    test_runner: str | None,
    use_typescript: bool | None,
    use_lefthook: bool | None,
    use_docker: bool | None,
    defaults: bool,
    force: bool,
    pretend: bool,
    skip_tasks: bool,
    no_install: bool,
    cleanup_on_error: bool,
    quiet: bool,
    verbose: bool,
    incremental: bool,
    strict: bool,
    template_dir_override: str | None,
    prompt_backend: PromptBackend | None = None,
    include_hidden: bool = False,
) -> dict[str, Any]:
    """构建 InitWorker 构造参数."""
    return {
        "dst_path": dst_path,
        "project_type": project_type,
        "language": language,
        "package_manager": package_manager,
        "ci_platform": ci_platform,
        "test_runner": test_runner,
        "use_typescript": use_typescript,
        "use_lefthook": use_lefthook,
        "use_docker": use_docker,
        "defaults": defaults,
        "force": force,
        "pretend": pretend,
        "skip_tasks": skip_tasks,
        "no_install": no_install,
        "cleanup_on_error": cleanup_on_error,
        "quiet": quiet,
        "verbose": verbose,
        "incremental": incremental,
        "strict": strict,
        "template_dir_override": Path(template_dir_override) if template_dir_override else None,
        "prompt_backend": prompt_backend,
        "include_hidden": include_hidden,
    }


def _print_completion_report(result: InitResult) -> None:
    """Print structured init completion report with stage boundary declaration.

    Design: ae-init-process-analysis.md §4.3 — every successful init must
    output a completion report that declares the stage boundary, so the agent
    (and user) know init is done and design phase comes next.
    """
    file_count = len(result.files)
    mode_label = "增量补充" if result.mode == "incremental" else "全新初始化"

    lines = [
        "",
        "╔══════════════════════════════════════════╗",
        "║         Init 完成报告                    ║",
        "╚══════════════════════════════════════════╝",
        "",
        f"  项目类型:   {result.project_type}",
        f"  初始化模式: {mode_label}",
        f"  生成文件:   {file_count} 个",
    ]

    if result.mode == "incremental" and result.skipped_files > 0:
        lines.append(f"  跳过文件:   {result.skipped_files} 个（已有）")

    lines += [
        f"  目标目录:   {result.dst_path}",
        "",
        "──────────────── 阶段边界 ────────────────",
        "  ✅ init 阶段完成",
        "  ⏭  下一步: 设计阶段",
        "      - 确认技术选型（框架/库/工具）",
        "      - 填充 BEACON.md 业务目标与范围",
        "      - 产出架构方案",
        "",
        "  ❌ 不要直接安装业务依赖或编写业务代码",
        "  ❌ 不要填充 BEACON.md 业务内容",
        "  ⏸  等待用户确认后进入设计阶段",
        "──────────────────────────────────────────",
    ]

    for line in lines:
        click.echo(line)
