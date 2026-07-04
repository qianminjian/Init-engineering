"""CLI 子命令 — update / status Click 命令.

从 cli/commands.py 拆分 (code review 2026-07-04):
commands.py 330 行超 300 行约束, 拆出 update/status Click 命令.
"""

from __future__ import annotations

from pathlib import Path

import click


@click.command()
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
    from init_engineering.init.scaffold_update import run_update

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


@click.command()
def status():
    """查看当前项目环境配置."""
    from init_engineering.config.environment import ProjectEnvironment

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
