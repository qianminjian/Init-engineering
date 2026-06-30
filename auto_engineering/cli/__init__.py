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
@click.option("--package-manager", help="包管理器 (npm/pnpm/yarn/bun/uv/poetry)")
@click.option("--ci", "ci_platform", help="CI 平台 (github/gitlab/none)")
@click.option("--test-runner", help="测试框架")
@click.option(
    "--no-typescript", "use_typescript", flag_value=False, default=None, help="不使用 TypeScript"
)
@click.option(
    "--no-lefthook", "use_lefthook", flag_value=False, default=None, help="不安装 Lefthook"
)
@click.option("--pretend", is_flag=True, help="模拟执行，不产生文件")
@click.option("--skip-tasks", is_flag=True, help="跳过钩子任务执行")
@click.option(
    "--no-cleanup", "cleanup_on_error", flag_value=False, default=True, help="出错时不清理目标目录"
)
@click.option("--quiet", is_flag=True, help="静默模式")
@click.option("--incremental", is_flag=True, help="增量模式：只补充缺失文件，不覆盖已有文件")
@click.option(
    "--analyze", "analyze_only", is_flag=True, help="存量项目：只分析项目类型，不初始化"
)
def init(
    project: str | None,
    project_type: str | None,
    defaults: bool,
    force: bool,
    answers_file: str | None,
    package_manager: str | None,
    ci_platform: str | None,
    test_runner: str | None,
    use_typescript: bool | None,
    use_lefthook: bool | None,
    pretend: bool,
    skip_tasks: bool,
    cleanup_on_error: bool,
    quiet: bool,
    incremental: bool,
    analyze_only: bool,
):
    """项目环境初始化."""
    from auto_engineering.init import InitWorker
    from auto_engineering.init.detector import ProjectDetector

    dst_path = Path(project) if project else Path.cwd()

    # --analyze 模式：只运行代码分析，不初始化
    if analyze_only:
        detector = ProjectDetector(dst_path)
        candidates = detector.list_candidates()
        detected = detector.detect()
        click.echo(f"分析目录: {dst_path}")
        if candidates:
            click.echo(f"检测到的项目类型候选: {', '.join(candidates)}")
            if detected:
                click.echo(f"✓ 自动检测结果: {detected}")
            else:
                click.echo("⚠ 多个候选，无法自动确定类型")
        else:
            click.echo("⚠ 未检测到已知项目类型（空目录或未知类型）")
        return

    if answers_file:
        from auto_engineering.init import AnswersMap

        answers = AnswersMap.from_answers_file(Path(answers_file))
        click.echo(f"从 {answers_file} 恢复答案")
        if not project_type:
            with contextlib.suppress(KeyError):
                project_type = answers.get("project_type") or ""
    else:
        answers = None

    worker = InitWorker(
        dst_path=dst_path,
        project_type=project_type,
        package_manager=package_manager,
        ci_platform=ci_platform,
        test_runner=test_runner,
        use_typescript=use_typescript,
        use_lefthook=use_lefthook,
        defaults=defaults,
        force=force,
        pretend=pretend,
        skip_tasks=skip_tasks,
        cleanup_on_error=cleanup_on_error,
        quiet=quiet,
        incremental=incremental,
    )
    if answers:
        worker._previous_answers = answers

    try:
        result = worker.execute()
        if pretend:
            click.echo(f"[DRY RUN] 将生成到: {result.dst_path}")
        else:
            click.echo(f"✓ 项目已生成: {result.dst_path}")
    except Exception as e:
        click.echo(f"✗ 初始化失败: {e}", err=True)
        raise SystemExit(1) from e


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
