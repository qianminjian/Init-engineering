"""CLI 子命令 — init 命令实现 + 轻量子分支.

从 cli/__init__.py 拆分 (2026-07-03 深度审计 P2-A):
原 __init__.py 427 行超 300 行约束, 拆出:
- cmd_init (init 命令实现, 来自 P2-12)
- --list-types / --list-templates / --analyze 分支 (纯函数, init() 调用)
- update / status 命令拆分到 cli/subcommands.py (code review P2-12 follow-up)
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

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from init_engineering.init import InitResult
    from init_engineering.init.detector import ProjectDetector

# ============================================================
# init 命令的轻量子分支 (纯函数, init() 内部调用)
# ============================================================


def _cmd_list_types(templates_root: Path) -> None:
    """--list-types: 列出所有可用的项目类型."""
    types = sorted(
        d.name for d in templates_root.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    )
    click.echo("可用的项目类型:")
    for t in types:
        click.echo(f"  {t}")


def _cmd_list_templates(templates_root: Path) -> None:
    """--list-templates: 列出每个类型的模板文件."""
    types = sorted(
        d.name for d in templates_root.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    )
    for t in types:
        click.echo(f"\n[{t}]")
        type_dir = templates_root / t
        for f in sorted(type_dir.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                rel = f.relative_to(type_dir)
                click.echo(f"  {rel}")


def _cmd_analyze(
    dst_path: Path,
    detector_cls: type[ProjectDetector],
    project_type: str | None = None,
) -> None:
    """--analyze: 只运行代码分析, 不初始化.

    Args:
        dst_path: 目标目录
        detector_cls: ProjectDetector 类 (可替换用于测试注入)
        project_type: 用户通过 --type 指定的项目类型（消歧义时覆盖自动检测）
    """
    detector = detector_cls(dst_path)
    result = detector.analyze()
    click.echo(f"分析目录: {dst_path}")
    click.echo(f"项目名称: {result.project_name}")
    if result.candidates:
        click.echo(f"检测到的项目类型候选: {', '.join(result.candidates)}")
        if result.project_type:
            click.echo(f"✓ 自动检测结果: {result.project_type}")
        elif project_type:
            click.echo(f"✓ 使用 --type 指定类型: {project_type}")
        else:
            click.echo("⚠ 多个候选，无法自动确定类型")
    else:
        click.echo("⚠ 未检测到已知项目类型（空目录或未知类型）")
    if result.language:
        click.echo(f"语言: {result.language}")
    if result.package_manager:
        click.echo(f"包管理器: {result.package_manager}")
    if result.test_runner:
        click.echo(f"测试框架: {result.test_runner}")
    if result.ci_platform:
        click.echo(f"CI 平台: {result.ci_platform}")
    if result.frameworks:
        click.echo(f"框架: {', '.join(result.frameworks)}")


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
    analyze_only: bool,
    telemetry: bool,
    list_types: bool,
    list_templates: bool,
    templates_suffix: str | None,
    preserve_symlinks: bool | None,
    template_dir_override: str | None,
    hook_timeout: int | None,
    force_unsafe_template: bool,
) -> InitResult | None:
    """P2-12: init 命令实现 — 从 cli/__init__.py 拆分以满足 ≤ 300 行约束.

    纯函数,接收已 click-解析的所有参数,执行 init 主体逻辑.
    调用方 (init click 装饰函数) 只负责参数收集和转发.
    """
    from init_engineering.init import InitWorker
    from init_engineering.init.config_types import TEMPLATES_ROOT
    from init_engineering.init.detector import ProjectDetector
    from init_engineering.init.errors import InitError

    # --list-types / --list-templates / --analyze 早返回分支
    if list_types:
        _cmd_list_types(TEMPLATES_ROOT)
        return
    if list_templates:
        _cmd_list_templates(TEMPLATES_ROOT)
        return

    dst_path = (Path(project) if project else Path.cwd()).resolve()

    if analyze_only:
        _cmd_analyze(dst_path, ProjectDetector, project_type=project_type or None)
        return

    # --from-answers: 从 .ae-answers.yml 恢复 + 隐式非交互
    if answers_file:
        from init_engineering.init import AnswersMap

        answers = AnswersMap.from_answers_file(Path(answers_file))
        if not quiet:
            click.echo(f"从 {answers_file} 恢复答案")
        if not project_type:
            project_type = answers.get("project_type", default="") or ""
        defaults = True
    else:
        answers = None

    # PR#4 P1-4: --template-dir 白名单硬阻断 + --force-unsafe-template 显式绕过
    if template_dir_override:
        td = Path(template_dir_override).resolve()
        safe_roots = [Path.cwd(), Path.home() / ".ae-templates", Path("/tmp")]
        is_safe = any(
            str(td).startswith(str(r.resolve()) + "/") or td == r.resolve()
            for r in safe_roots if r.exists()
        )
        if not is_safe and not force_unsafe_template:
            raise click.UsageError(
                f"❌ --template-dir {td} 不在常用安全路径内 "
                f"({[str(r) for r in safe_roots if r.exists()]})。\n"
                f"使用不明来源的外部模板可能在您的机器上执行恶意代码。\n"
                f"如确认模板来源可信, 加 --force-unsafe-template 显式绕过。"
            )
        if not is_safe and verbose:
            click.echo(
                f"⚠ 已用 --force-unsafe-template 绕过白名单检查: {td}",
                err=True,
            )

    # --telemetry: 首次开启强制引导用户同意 (避免静默收集)
    if telemetry:
        from init_engineering.telemetry import has_consent, request_and_persist_consent
        if not has_consent() and not request_and_persist_consent():
            click.echo("已禁用 telemetry (本次 init 不发送数据)", err=False)
            telemetry = False

    _configure_logging(verbose=verbose)

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
        templates_suffix=templates_suffix,
        preserve_symlinks=preserve_symlinks, hook_timeout=hook_timeout,
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
        finally:
            elapsed_ms = int((_time.monotonic() - _start_ts) * 1000)
            _emit_telemetry(
                telemetry, project_type=project_type or "", language=language,
                success=_telemetry_error is None, elapsed_ms=elapsed_ms,
                error_type=_telemetry_error,
            )


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
    templates_suffix: str | None,
    preserve_symlinks: bool | None,
    hook_timeout: int | None,
) -> dict:
    """构建 InitWorker 构造参数 — 从 cmd_init 提取以减小函数体."""
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
        "templates_suffix": templates_suffix,
        "preserve_symlinks": preserve_symlinks,
        "hook_timeout": hook_timeout,
    }


def _emit_telemetry(
    enabled: bool,
    *,
    project_type: str,
    language: str | None,
    success: bool,
    elapsed_ms: int,
    error_type: str | None = None,
) -> None:
    """P2-12: 提取 init 成功/失败两条 telemetry send 分支 — 消除 11 行重复."""
    if not enabled:
        return
    from init_engineering.telemetry import TelemetryEvent
    from init_engineering.telemetry import send as _send_telemetry
    _send_telemetry(TelemetryEvent(
        ae_version=__version__,
        command="init",
        project_type=project_type,
        language=language or "",
        success=success,
        duration_ms=elapsed_ms,
        error_type=error_type,
    ))