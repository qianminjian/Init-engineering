"""--list-types / --list-templates / --analyze 早返回函数.

从 cli/commands.py 拆分 (2026-07-13 深度审计 P0-1):
commands.py 376 行超 300 行约束, 提取 3 个 _cmd_* 分支函数.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from init_engineering.init.detector import ProjectDetector


def cmd_list_types(templates_root: Path) -> None:
    """--list-types: 列出所有可用的项目类型."""
    types = sorted(
        d.name for d in templates_root.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    )
    click.echo("可用的项目类型:")
    for t in types:
        click.echo(f"  {t}")


def cmd_list_templates(templates_root: Path) -> None:
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


def cmd_analyze(
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
