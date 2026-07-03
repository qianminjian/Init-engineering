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

from auto_engineering import __version__


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
):
    """项目环境初始化."""
    from auto_engineering.init import InitWorker
    from auto_engineering.init.config import TEMPLATES_ROOT
    from auto_engineering.init.detector import ProjectDetector

    # --list-types: 列出可用项目类型
    if list_types:
        types = sorted(
            d.name for d in TEMPLATES_ROOT.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        )
        click.echo("可用的项目类型:")
        for t in types:
            click.echo(f"  {t}")
        return

    # --list-templates: 列出每个类型的模板文件
    if list_templates:
        types = sorted(
            d.name for d in TEMPLATES_ROOT.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        )
        for t in types:
            click.echo(f"\n[{t}]")
            type_dir = TEMPLATES_ROOT / t
            for f in sorted(type_dir.rglob("*")):
                if f.is_file() and not f.name.startswith("."):
                    rel = f.relative_to(type_dir)
                    click.echo(f"  {rel}")
        return

    dst_path = Path(project) if project else Path.cwd()

    # --analyze 模式：只运行代码分析，不初始化
    if analyze_only:
        detector = ProjectDetector(dst_path)
        result = detector.analyze()
        click.echo(f"分析目录: {dst_path}")
        click.echo(f"项目名称: {result.project_name}")
        if result.candidates:
            click.echo(f"检测到的项目类型候选: {', '.join(result.candidates)}")
            if result.project_type:
                click.echo(f"✓ 自动检测结果: {result.project_type}")
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
        return

    if answers_file:
        from auto_engineering.init import AnswersMap

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

    # P2-10: template-dir 白名单软警告 — 不阻断, 仅在 verbose 模式显示
    # 防止用户从 internet/不明来源拖入恶意模板 (可能含 [AE-P0-1] Jinja 沙箱穿透)
    if template_dir_override and verbose:
        from pathlib import Path as _P
        td = _P(template_dir_override).resolve()
        safe_roots = [_P.cwd(), _P.home() / ".ae-templates", _P("/tmp")]
        is_safe = any(
            str(td).startswith(str(r.resolve()) + "/") or td == r.resolve()
            for r in safe_roots if r.exists()
        )
        if not is_safe:
            click.echo(
                f"⚠ 警告: --template-dir {td} 不在常用安全路径内 "
                f"({[str(r) for r in safe_roots]})。"
                f"使用不明来源模板可能有 RCE 风险 (Jinja 沙箱穿透攻击).",
                err=True,
            )

    if telemetry:
        import os as _os
        # B6: 首次开启强制引导用户同意 (避免静默收集)
        from auto_engineering.telemetry import has_consent, request_consent
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
        cleanup_on_error=cleanup_on_error,
        quiet=quiet,
        verbose=verbose,
        incremental=incremental,
        strict=strict,
        template_dir_override=Path(template_dir_override) if template_dir_override else None,
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
                from auto_engineering.telemetry import TelemetryEvent, send as _send_telemetry
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
                from auto_engineering.telemetry import TelemetryEvent, send as _send_telemetry
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


def _sanitize_error(msg: str) -> str:
    """P2-13: 错误消息脱敏 — 替换常见 secret 模式为 [REDACTED]."""
    import re as _re

    patterns = [
        # 长 token / api key (>=20 字符的 base64/hex)
        (r"(?i)(token|api[_-]?key|secret|password|access[_-]?key)\s*[=:]\s*['\"]?[\w\-]{16,}['\"]?",
         r"\1=[REDACTED]"),
        # Bearer token
        (r"(?i)Bearer\s+[\w\-\.]{16,}", "Bearer [REDACTED]"),
        # JWT 风格 (xxx.yyy.zzz)
        (r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", "[REDACTED-JWT]"),
    ]
    for pat, repl in patterns:
        msg = _re.sub(pat, repl, msg)
    return msg


def _configure_logging(verbose: bool) -> None:
    """配置 logging — B7: 结构化 + session_id；B9: dictConfig 强制覆盖。

    设计：
    - 默认 INFO 级别（plain text）
    - --verbose 升级到 DEBUG
    - 全局注入 ae_session_id (uuid4 前 8 位) 用于日志关联
    - 使用 dictConfig 而非 basicConfig — 避免用户/agent 已有 logger 配置失效
    """
    import logging.config
    import uuid

    session_id = uuid.uuid4().hex[:8]
    level = "DEBUG" if verbose else "INFO"

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "format": f"%(asctime)s [%(levelname)s] [ae:{session_id}] [%(name)s] %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            },
        },
        "handlers": {
            "stderr": {
                "class": "logging.StreamHandler",
                "formatter": "structured",
                "stream": "ext://sys.stderr",
            },
        },
        "root": {
            "level": level,
            "handlers": ["stderr"],
        },
    })


@main.command()
@click.argument("project", required=False)
@click.option(
    "--conflict",
    "conflict_strategy",
    type=click.Choice(["skip", "overwrite", "prompt"]),
    default="skip",
    help="文件冲突处理策略 (默认 skip — 保护用户修改)",
)
@click.option("--dry-run", is_flag=True, help="只计算 diff 不写入")
@click.option("--force", is_flag=True, help="无 .ae-answers.yml 时强制升级（自动推断 project_type）")
@click.option("--quiet", is_flag=True, help="静默模式")
def update(
    project: str | None,
    conflict_strategy: str,
    dry_run: bool,
    force: bool,
    quiet: bool,
):
    """升级已存在的项目 — 重新渲染模板 + 合并到目标目录.

    默认策略: skip (保护用户手动修改).  可选: overwrite / prompt.
    """
    from auto_engineering.init.scaffold_update import run_update

    dst_path = Path(project) if project else Path.cwd()
    result = run_update(
        dst_path=dst_path,
        force=force,
        dry_run=dry_run,
        conflict_strategy=conflict_strategy,
    )
    if not quiet:
        click.echo(result.summary())
        for f in result.files_added:
            click.echo(f"  + {f.relative_to(dst_path)}")
        for f in result.files_updated:
            click.echo(f"  ~ {f.relative_to(dst_path)}")
        for f in result.files_skipped:
            click.echo(f"  - {f.relative_to(dst_path)}  (skipped)")


@main.command()
def status():
    """查看当前项目环境配置."""
    from auto_engineering.config.environment import ProjectEnvironment

    cwd = Path.cwd()
    click.echo(f"当前目录: {cwd}")

    try:
        env = ProjectEnvironment.resolve(cwd)
        click.echo(f"  项目名称: {env.project_name}")
        click.echo(f"  项目类型: {env.project_type or '未知'}")
        click.echo(f"  包管理器: {env.package_manager or '未知'}")
        click.echo(f"  测试框架: {env.test_runner or '未知'}")
        click.echo(f"  TypeScript: {'是' if env.use_typescript else '否'}")
        click.echo(f"  Lefthook: {'是' if env.use_lefthook else '否'}")
        click.echo(f"  CI: {env.ci_platform or '无'}")
        click.echo(f"  Git: {'是' if env.has_git else '否'}")
        undetectable = env._warn_undetectable(cwd)
        if undetectable:
            click.echo(f"  ⚠ 不可自动判定: {', '.join(undetectable)}", err=True)
    except Exception as e:
        click.echo(f"  读取项目环境失败: {e}")


if __name__ == "__main__":
    main()
