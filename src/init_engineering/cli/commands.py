"""CLI 子命令 — update / status + init 命令的轻量子分支.

从 cli/__init__.py 拆分 (2026-07-03 深度审计 P2-A):
原 __init__.py 427 行超 300 行约束, 拆出:
- update / status 命令 (本文件 Click 装饰器)
- --list-types / --list-templates / --analyze 分支 (纯函数, init() 调用)

注册方式: update/status 通过 main.add_command() 注册到 group;
init 的子分支作为模块函数, 由 init() 内部直接调用.
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


def _cmd_analyze(dst_path: Path, project_detector_cls) -> None:
    """--analyze: 只运行代码分析, 不初始化."""
    detector = project_detector_cls(dst_path)
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