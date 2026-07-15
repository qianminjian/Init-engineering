"""CLI 入口 — Click 命令注册.

命令:
    ae init <project>       项目环境初始化
    ae analyze <path>        存量项目分析（只分析不初始化）
    ae update <project>      增量更新已有项目
    ae status                查看项目环境状态
    ae list-types            列出可用项目类型
    ae list-templates        列出模板文件
"""

from __future__ import annotations

import click

from init_engineering import __version__

# ── Epilogs (usage examples) ──────────────────────────────────────────

_EXAMPLES_INIT = """\
使用示例:
  ae init my-app --type app-service          新项目向导初始化
  ae init my-app --type library --defaults   非交互初始化（跳过问答）
  ae init . --defaults                       存量项目自动分析 + 初始化
  ae init . --incremental                    增量模式：只补充缺失文件
  ae init my-app --type app-service --pretend 模拟执行，查看会生成什么
  ae init . --defaults --skip-tasks --no-install  CI 流水线模式"""

_EXAMPLES_ANALYZE = """\
使用示例:
  ae analyze .                       分析当前目录
  ae analyze /path/to/project        分析指定目录
  ae analyze . --include-hidden      包含隐藏目录（.qoder/.claude/ 等）"""

_EXAMPLES_UPDATE = """\
使用示例:
  ae update                        升级当前目录项目
  ae update --conflict overwrite   强制覆盖用户修改
  ae update --dry-run              只看差异，不实际写入"""


# ── Group ─────────────────────────────────────────────────────────────

@click.group()
@click.version_option(version=__version__, prog_name="ae")
def main():
    """Init-Engineering — 项目环境初始化工具.

    为 Claude Code Agent 工作流提供项目脚手架能力。

    \b
    两种核心模式：
      新项目向导：  ae init <project> --type <type>
      存量项目分析：ae analyze <path> && ae init . --defaults

    \b
    常用命令：
      ae init        项目初始化
      ae analyze     存量项目分析
      ae update      增量更新已有项目
      ae status      查看项目环境状态
    """


# ── ae init ───────────────────────────────────────────────────────────

@main.command(epilog=_EXAMPLES_INIT)
@click.argument("project", required=False)
# ── 项目配置 ──
@click.option(
    "--type", "project_type",
    help="项目类型：app-service / cli-tool / library / skill / hook / mcp-server / spec-doc / monorepo / plugin",
)
@click.option("--language", help="主要语言：typescript / python / go / rust / java")
# ── 模式控制 ──
@click.option("--defaults", is_flag=True, help="非交互模式，全部使用默认值")
@click.option("--force", is_flag=True, help="允许覆盖非空目录")
@click.option("--incremental", is_flag=True, help="增量模式：只补充缺失文件，不覆盖已有")
@click.option("--pretend", is_flag=True, help="模拟执行，不产生文件（调试用）")
# ── 配置覆盖 ──
@click.option("--package-manager", help="包管理器：npm / pnpm / yarn / bun / uv / poetry / pip")
@click.option("--ci", "ci_platform", help="CI 平台：github / gitlab / none")
@click.option("--test-runner", help="测试框架：pytest / jest / vitest / go test / mvn test")
@click.option(
    "--use-typescript/--no-typescript", "use_typescript", default=None,
    help="启用/禁用 TypeScript（默认对 Node 项目自动开启）",
)
@click.option(
    "--use-lefthook/--no-lefthook", "use_lefthook", default=None,
    help="启用/禁用 Lefthook git hooks",
)
@click.option(
    "--use-docker/--no-docker", "use_docker", default=None,
    help="启用/禁用 Docker 支持",
)
@click.option("--no-install", "no_install", is_flag=True, help="跳过依赖安装（CI/离线场景）")
# ── 流程控制 ──
@click.option("--skip-tasks", is_flag=True, help="跳过钩子任务（git init / package install 等）")
@click.option("--quiet", is_flag=True, help="静默模式，减少输出")
@click.option("--verbose", "-v", is_flag=True, help="详细输出（DEBUG 级别日志）")
@click.option("--strict", is_flag=True, help="严格模式：钩子失败时报错退出而非警告")
# ── 高级（--help 不显示，--help-advanced 或源码查阅） ──
@click.option(
    "--from-answers", "answers_file", type=click.Path(exists=True), hidden=True,
    help="从 .ae-answers.yml 恢复（CI 场景）",
)
@click.option(
    "--template-dir", "template_dir_override", type=click.Path(exists=True, file_okay=False),
    hidden=True, help="外部模板目录（默认仅允许 ~/.ae-templates/）",
)
@click.option(
    "--include-hidden", "include_hidden", is_flag=True, default=False, hidden=True,
    help="检测阶段扫描隐藏目录（.qoder/.claude/ 等）",
)
@click.option(
    "--no-cleanup", "cleanup_on_error", flag_value=False, default=True, hidden=True,
    help="错误时保留临时文件用于调试",
)
# ── 已废弃（hidden，仅向后兼容） ──
@click.option("--list-types", "list_types_legacy", is_flag=True, hidden=True)
@click.option("--list-templates", "list_templates_legacy", is_flag=True, hidden=True)
@click.option("--analyze", "analyze_legacy", is_flag=True, hidden=True)
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
    list_types_legacy: bool,
    list_templates_legacy: bool,
    analyze_legacy: bool,
    template_dir_override: str | None,
    include_hidden: bool,
):
    """项目环境初始化 — 新项目向导或存量项目自动分析.

    不指定 --type 时自动检测存量项目类型与配置。
    使用 --defaults 跳过所有交互式问答（CI/Agent 模式）。
    """
    from init_engineering.cli._click_backend import ClickPromptBackend
    from init_engineering.cli.commands import cmd_init

    # Backward compat: --list-types / --list-templates / --analyze as init flags
    if list_types_legacy:
        click.echo("⚠  --list-types 已废弃，请使用 ae list-types", err=True)
        from init_engineering.cli._list_cmds import cmd_list_types
        from init_engineering.init.config_types import TEMPLATES_ROOT
        cmd_list_types(TEMPLATES_ROOT)
        return
    if list_templates_legacy:
        click.echo("⚠  --list-templates 已废弃，请使用 ae list-templates", err=True)
        from init_engineering.cli._list_cmds import cmd_list_templates
        from init_engineering.init.config_types import TEMPLATES_ROOT
        cmd_list_templates(TEMPLATES_ROOT)
        return
    if analyze_legacy:
        click.echo("⚠  --analyze 已废弃，请使用 ae analyze <path>", err=True)
        from pathlib import Path as _Path
        from init_engineering.cli._list_cmds import cmd_analyze
        from init_engineering.init.detector import ProjectDetector
        dst_path = (_Path(project) if project else _Path.cwd()).resolve()
        cmd_analyze(dst_path, ProjectDetector, project_type=project_type, include_hidden=include_hidden)
        return

    cmd_init(
        prompt_backend=ClickPromptBackend(),
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
        template_dir_override=template_dir_override,
        include_hidden=include_hidden,
    )


# ── ae analyze ────────────────────────────────────────────────────────

@main.command(epilog=_EXAMPLES_ANALYZE)
@click.argument("path", required=False, default=".")
@click.option(
    "--include-hidden", "include_hidden", is_flag=True, default=False,
    help="扫描隐藏目录（.qoder/.claude/ 等反向工程资产）",
)
def analyze(path: str, include_hidden: bool):
    """分析存量项目 — 检测项目类型、语言、框架、配置.

    只分析不初始化，输出检测结果供后续 ae init 使用。
    """
    from pathlib import Path as _Path

    from init_engineering.cli._list_cmds import cmd_analyze
    from init_engineering.init.detector import ProjectDetector

    dst_path = _Path(path).resolve()
    if not dst_path.exists():
        click.echo(f"✗ 目录不存在: {dst_path}", err=True)
        raise SystemExit(1)
    cmd_analyze(dst_path, ProjectDetector, include_hidden=include_hidden)


# ── ae list-types ─────────────────────────────────────────────────────

@main.command(name="list-types")
def list_types_cmd():
    """列出所有可用的项目类型."""
    from init_engineering.cli._list_cmds import cmd_list_types
    from init_engineering.init.config_types import TEMPLATES_ROOT
    cmd_list_types(TEMPLATES_ROOT)


# ── ae list-templates ─────────────────────────────────────────────────

@main.command(name="list-templates")
@click.option("--type", "filter_type", help="仅列出指定类型的模板")
def list_templates_cmd(filter_type: str | None):
    """列出模板文件 — 查看每个项目类型会生成哪些文件."""
    from init_engineering.cli._list_cmds import cmd_list_templates
    from init_engineering.init.config_types import TEMPLATES_ROOT
    cmd_list_templates(TEMPLATES_ROOT, filter_type=filter_type)


# ── ae update / ae status (imported from subcommands) ─────────────────

from init_engineering.cli.subcommands import status, update  # noqa: E402

main.add_command(update)
main.add_command(status)


if __name__ == "__main__":
    main()
