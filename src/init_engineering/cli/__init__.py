"""CLI 入口 — Click 命令注册.

命令:
    ae init <project>         项目环境初始化
    ae init --analyze <path> 存量项目：代码分析 + 自动初始化
    ae init-config            查看/编辑初始化配置
"""

from __future__ import annotations

import click

from init_engineering import __version__


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
    help="项目类型 (app-service/cli-tool/library/skill/hook/mcp-server/spec-doc/monorepo/plugin)",
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
@click.option(
    "--template-dir",
    "template_dir_override",
    type=click.Path(exists=True, file_okay=False),
    help="外部模板目录路径",
)
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
    help="强制使用非白名单 --template-dir (默认会被拒绝, 仅此 flag 可绕过)",
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
    # P2-12: 函数体拆到 cli/commands.py::cmd_init —
    # cli/__init__.py 只保留 click 选项装饰器 + 调度, 控制在 300 行内.
    from init_engineering.cli.commands import cmd_init

    cmd_init(
        project=project,
        project_type=project_type,
        defaults=defaults,
        force=force,
        answers_file=answers_file,
        language=language,
        package_manager=package_manager,
        ci_platform=ci_platform,
        test_runner=test_runner,
        use_typescript=use_typescript,
        use_lefthook=use_lefthook,
        use_docker=use_docker,
        pretend=pretend,
        skip_tasks=skip_tasks,
        no_install=no_install,
        cleanup_on_error=cleanup_on_error,
        quiet=quiet,
        verbose=verbose,
        incremental=incremental,
        strict=strict,
        analyze_only=analyze_only,
        telemetry=telemetry,
        list_types=list_types,
        list_templates=list_templates,
        templates_suffix=templates_suffix,
        preserve_symlinks=preserve_symlinks,
        template_dir_override=template_dir_override,
        hook_timeout=hook_timeout,
        force_unsafe_template=force_unsafe_template,
    )


# P2-A: update / status 命令拆到 cli/subcommands.py (code review follow-up)
from init_engineering.cli.subcommands import status, update  # noqa: E402

main.add_command(update)
main.add_command(status)


if __name__ == "__main__":
    main()
