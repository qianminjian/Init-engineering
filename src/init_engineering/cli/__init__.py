"""CLI 入口 — Click 命令注册.

命令:
    ae init <project>         项目环境初始化
    ae init --analyze <path> 存量项目：代码分析 + 自动初始化
    ae init-config            查看/编辑初始化配置
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import click

from init_engineering import __version__
from init_engineering.cli._helpers import configure_logging as _configure_logging
from init_engineering.cli._helpers import sanitize_error as _sanitize_error


@click.group()
@click.version_option(version=__version__, prog_name="ae")
def main():
    """Init-Engineering — Agent Skill 模式项目环境初始化工具."""
    pass


@main.command()
@click.argument("project", required=False)
@click.option(
    "--type",
    "project_type",
    help="项目类型 (app-service/library/cli-tool/skill/hook/mcp-server/spec-doc/monorepo)",
)
@click.option("--defaults", is_flag=True, help="非交互模式，全部使用默认值")
@click.option("--force", is_flag=True, help="允许覆盖非空目录")
@click.option(
    "--from-answers", "answers_file", type=click.Path(exists=True), help="从 .ae-answers.yml 重放"
)
@click.option("--language", help="主要语言 (typescript/python/go/rust)")
@click.option("--package-manager", help="包管理器 (npm/pnpm/yarn/bun/uv/poetry)")
@click.option("--ci", "ci_platform", help="CI 平台 (github/gitlab/none)")
@click.option("--test-runner", help="测试框架")
@click.option(
    "--use-typescript/--no-typescript",
    "use_typescript",
    default=None,
    help="是否启用 TypeScript",
)
@click.option(
    "--use-lefthook/--no-lefthook",
    "use_lefthook",
    default=None,
    help="是否安装 Lefthook",
)
@click.option(
    "--use-docker/--no-docker", "use_docker", default=None, help="添加 Docker 支持"
)
@click.option("--pretend", is_flag=True, help="模拟执行，不产生文件")
@click.option("--skip-tasks", is_flag=True, help="跳过钩子任务执行")
# PE-P0-1: --no-install 跳过 package_manager install 阶段 (CI/离线场景)
@click.option(
    "--no-install", "no_install", is_flag=True, help="跳过依赖安装 (uv sync/npm install)"
)
@click.option(
    "--no-cleanup", "cleanup_on_error", flag_value=False, default=True, help="出错时不清理目标目录"
)
@click.option("--template-dir", "template_dir_override", type=click.Path(exists=True, file_okay=False), help="外部模板目录路径")
@click.option("--strict", is_flag=True, help="严格模式：钩子失败时抛出异常而非警告")
@click.option("--quiet", is_flag=True, help="静默模式")
@click.option("--verbose", "-v", is_flag=True, help="详细输出（DEBUG 级别日志）")
@click.option("--telemetry", is_flag=True, help="启用匿名使用数据收集")
@click.option("--incremental", is_flag=True, help="增量模式：只补充缺失文件，不覆盖已有文件")
@click.option(
    "--analyze", "analyze_only", is_flag=True, help="存量项目：只分析项目类型，不初始化"
)
@click.option(
    "--list-types", "list_types", is_flag=True, help="列出所有可用的项目类型"
)
@click.option(
    "--list-templates", "list_templates", is_flag=True, help="列出所有可用模板文件"
)
# P1-1: templates_suffix + preserve_symlinks CLI 透传
@click.option(
    "--templates-suffix",
    "templates_suffix",
    help="模板文件后缀 (默认: .jinja)",
)
@click.option(
    "--preserve-symlinks/--no-preserve-symlinks",
    "preserve_symlinks",
    default=None,
    help="是否保留 symlink (默认: True)",
)
# PE-P1-4: 全局钩子超时(秒) — 对慢任务 (cargo build/large npm install) 显式调大
@click.option(
    "--hook-timeout",
    "hook_timeout",
    type=int,
    default=None,
    help="钩子命令默认超时秒数 (默认 300, 模板 Task.timeout 可逐任务覆盖)",
)
# PR#4 P1-4: --template-dir 安全绕过 — 显式 flag 才允许非白名单路径
@click.option(
    "--force-unsafe-template",
    "force_unsafe_template",
    is_flag=True,
    default=False,
    help="强制使用非白名单 --template-dir (PR#4 P1-4: 默认会被拒绝, 仅此 flag 可绕过)",
)
def init(
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
):
    """项目环境初始化."""
    from init_engineering.init import InitWorker
    from init_engineering.init.config import TEMPLATES_ROOT
    from init_engineering.init.detector import ProjectDetector

    # P2-A: --list-types / --list-templates / --analyze 分支提到独立函数,
    # 避免 init() 函数体超长 (target: cli/__init__.py ≤ 300 行)
    if list_types:
        _cmd_list_types(TEMPLATES_ROOT)
        return
    if list_templates:
        _cmd_list_templates(TEMPLATES_ROOT)
        return

    dst_path = Path(project) if project else Path.cwd()

    if analyze_only:
        _cmd_analyze(dst_path, ProjectDetector)
        return

    if answers_file:
        from init_engineering.init import AnswersMap

        answers = AnswersMap.from_answers_file(Path(answers_file))
        if not quiet:
            click.echo(f"从 {answers_file} 恢复答案")
        if not project_type:
            with contextlib.suppress(KeyError):
                project_type = answers.get("project_type") or ""
        # --from-answers 隐含非交互模式，避免 InteractivePrompt 无 stdin 崩溃
        defaults = True
    else:
        answers = None

    # PR#4 P1-4: template-dir 白名单由软警告升级为硬阻断
    # 防止用户从 internet/不明来源拖入恶意模板 (Jinja 沙箱穿透 + AE-P0-1 历史 CVEs)
    if template_dir_override:
        from pathlib import Path as _P
        td = _P(template_dir_override).resolve()
        safe_roots = [_P.cwd(), _P.home() / ".ae-templates", _P("/tmp")]
        is_safe = any(
            str(td).startswith(str(r.resolve()) + "/") or td == r.resolve()
            for r in safe_roots if r.exists()
        )
        if not is_safe and not force_unsafe_template:
            raise click.UsageError(
                f"❌ --template-dir {td} 不在常用安全路径内 "
                f"({[str(r) for r in safe_roots if r.exists()]})。"
                f"使用不明来源模板可能含 RCE 风险 (Jinja 沙箱穿透攻击)。"
                f"如确认模板来源可信, 加 --force-unsafe-template 显式绕过。"
            )
        if not is_safe and verbose:
            click.echo(
                f"⚠ 已用 --force-unsafe-template 绕过白名单检查: {td}",
                err=True,
            )

    if telemetry:
        import os as _os

        # B6: 首次开启强制引导用户同意 (避免静默收集)
        from init_engineering.telemetry import has_consent, request_consent
        if not has_consent():
            if not request_consent():
                click.echo("已禁用 telemetry (本次 init 不发送数据)", err=False)
                telemetry = False
            else:
                _os.environ["AE_TELEMETRY"] = "1"
        else:
            _os.environ["AE_TELEMETRY"] = "1"

    if verbose:
        _configure_logging(verbose=True)
    else:
        _configure_logging(verbose=False)

    # B1: 必须用 with 块 — __exit__ → _cleanup() 释放 InitLock,否则 .ae-init.lock
    # 残留,导致后续 --incremental 看到陈旧锁文件 / 第二个 init 误判有进程持锁
    with InitWorker(
        dst_path=dst_path,
        project_type=project_type,
        language=language,
        package_manager=package_manager,
        ci_platform=ci_platform,
        test_runner=test_runner,
        use_typescript=use_typescript,
        use_lefthook=use_lefthook,
        use_docker=use_docker,
        defaults=defaults,
        force=force,
        pretend=pretend,
        skip_tasks=skip_tasks,
        # PE-P0-1: --no-install 透传
        no_install=no_install,
        cleanup_on_error=cleanup_on_error,
        quiet=quiet,
        verbose=verbose,
        incremental=incremental,
        strict=strict,
        template_dir_override=Path(template_dir_override) if template_dir_override else None,
        # PR#4 P1-4: 透传 force_unsafe_template (CLI 已在上面硬阻断, 此处再传以供 InitWorker 记录日志)
        force_unsafe_template=force_unsafe_template,
        # P1-1: templates_suffix + preserve_symlinks CLI 透传
        templates_suffix=templates_suffix,
        preserve_symlinks=preserve_symlinks,
        # PE-P1-4: --hook-timeout 透传
        hook_timeout=hook_timeout,
    ) as worker:
        if answers:
            worker._previous_answers = answers

        import time as _time
        _start_ts = _time.monotonic()

        try:
            result = worker.execute()
            elapsed_ms = int((_time.monotonic() - _start_ts) * 1000)
            # Success output is handled by InitWorker._phase_finalize()
            if telemetry:
                from init_engineering.telemetry import TelemetryEvent
                from init_engineering.telemetry import send as _send_telemetry
                _send_telemetry(TelemetryEvent(
                    ae_version=__version__,
                    command="init",
                    project_type=result.project_type,
                    language=language or "",
                    success=True,
                    duration_ms=elapsed_ms,
                ))
        except Exception as e:
            elapsed_ms = int((_time.monotonic() - _start_ts) * 1000)
            if telemetry:
                from init_engineering.telemetry import TelemetryEvent
                from init_engineering.telemetry import send as _send_telemetry
                _send_telemetry(TelemetryEvent(
                    ae_version=__version__,
                    command="init",
                    project_type=project_type or "",
                    language=language or "",
                    success=False,
                    duration_ms=elapsed_ms,
                    error_type=type(e).__name__,
                ))
            # P2-13: 错误消息脱敏 — 替换 token/api_key/password 等敏感字段为 [REDACTED]
            # 防止 init 失败时把含 secret 的 stderr/traceback 打印到屏幕 + 写入日志
            safe_msg = _sanitize_error(str(e))
            click.echo(f"✗ 初始化失败: {safe_msg}", err=True)
            raise SystemExit(1) from e


# P2-A: update / status 命令 + init 子分支拆到 cli/commands.py — cli/__init__.py 拆分后 ≤ 300 行
from init_engineering.cli.commands import (  # noqa: E402
    _cmd_analyze,
    _cmd_list_templates,
    _cmd_list_types,
    status,
    update,
)

main.add_command(update)
main.add_command(status)


if __name__ == "__main__":
    main()
