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


def cmd_list_templates(templates_root: Path, *, filter_type: str | None = None) -> None:
    """--list-templates: 列出每个类型的模板文件。可选的 --type 过滤。"""
    types = sorted(
        d.name for d in templates_root.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    )
    if filter_type:
        if filter_type not in types:
            click.echo(f"✗ 未知项目类型: {filter_type}")
            click.echo(f"  可用类型: {', '.join(types)}")
            return
        types = [filter_type]
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
    *,
    include_hidden: bool = False,
) -> None:
    """存量项目分析 — 4 段分层输出。

    v5.6 重构：从 8 行平铺摘要 → 4 段分层输出：
      § 项目身份 — 名称/类型/描述
      § 技术栈     — 语言/框架/包管理器/测试/CI
      § 模块结构   — 多模块列表 + 关系
      § 初始化建议 — 推荐的 ae init 命令
    include_hidden 时追加 § 反向工程发现（qoder 数据）。
    """
    detector = detector_cls(dst_path, include_hidden=include_hidden)
    result = detector.analyze()

    # ═══ §1 项目身份 ═══
    click.echo("")
    click.echo("═══ § 项目身份 ═══")
    click.echo(f"  目录:       {dst_path}")
    click.echo(f"  项目名称:   {result.project_name or '(未检测到)'}")
    if result.candidates:
        click.echo(f"  类型候选:   {', '.join(result.candidates)}")
        if result.project_type:
            click.echo(f"  ✓ 自动检测: {result.project_type}")
        elif project_type:
            click.echo(f"  ✓ 手动指定: {project_type}")
        else:
            click.echo(f"  ⚠ 多个候选，无法自动确定。使用 --type 指定。")
    else:
        click.echo("  ⚠ 未检测到已知项目类型（空目录或未知类型）")
    if result.project_description:
        desc = result.project_description
        if len(desc) > 200:
            desc = desc[:197] + "..."
        click.echo(f"  项目描述:   {desc}")

    # ═══ §2 技术栈 ═══
    click.echo("")
    click.echo("═══ § 技术栈 ═══")
    if result.language:
        click.echo(f"  语言:       {result.language}")
    else:
        click.echo(f"  语言:       (未检测到)")
    if result.frameworks:
        click.echo(f"  框架:       {', '.join(result.frameworks)}")
    if result.package_manager:
        click.echo(f"  包管理器:   {result.package_manager}")
    if result.test_runner:
        click.echo(f"  测试框架:   {result.test_runner}")
    if result.ci_platform:
        click.echo(f"  CI 平台:    {result.ci_platform}")
    if result.has_lefthook:
        click.echo(f"  Git Hooks:  lefthook")
    if result.has_docker:
        click.echo(f"  容器化:     Docker")

    # Java 详细信息
    if result._java_info:
        ji = result._java_info
        extras = []
        if ji.get("group_id"):
            extras.append(f"GroupId: {ji['group_id']}")
        if ji.get("artifact_id"):
            extras.append(f"ArtifactId: {ji['artifact_id']}")
        if ji.get("java_version"):
            extras.append(f"Java {ji['java_version']}")
        if ji.get("spring_boot_version"):
            extras.append(f"Spring Boot {ji['spring_boot_version']}")
        if ji.get("build_tool"):
            extras.append(f"Build: {ji['build_tool']}")
        if extras:
            click.echo(f"  详细信息:   {' | '.join(extras)}")

    # ═══ §3 模块结构 ═══
    click.echo("")
    click.echo("═══ § 模块结构 ═══")
    java_mods = result._java_info.get("modules") if result._java_info else None
    if java_mods:
        click.echo(f"  多模块项目 ({len(java_mods)} 个子模块):")
        for mod in java_mods:
            click.echo(f"    • {mod}")
    else:
        qoder_mods = result._qoder_info.get("module_count") if result._qoder_info else 0
        if qoder_mods:
            click.echo(f"  Qoder 识别 {qoder_mods} 个模块")
            qmods = result._qoder_info.get("modules", [])
            for m in qmods:
                if m.get("key"):
                    click.echo(f"    • {m.get('key')}: {m.get('title', '')}")
        else:
            click.echo("  (单模块项目)")

    # 模块关系（qoder depends_on）
    if result._qoder_info and result._qoder_info.get("module_relations"):
        rels = result._qoder_info["module_relations"]
        has_deps = [r for r in rels if r.get("depends_on")]
        if has_deps:
            for r in has_deps:
                deps = ", ".join(r["depends_on"])
                click.echo(f"    {r['module']} → 依赖: {deps}")

    # ═══ §4 初始化建议 ═══
    click.echo("")
    click.echo("═══ § 初始化建议 ═══")
    _ptype = result.project_type or "app-service"
    _lang = result.language or ""
    lang_flag = f" --language {_lang}" if _lang else ""
    click.echo(f"  ae init . --type {_ptype}{lang_flag} --defaults")
    if include_hidden:
        click.echo(f"  ae init . --type {_ptype}{lang_flag} --defaults --include-hidden")
    click.echo(f"  ae init . --incremental     # 只补充缺失文件")
    click.echo("")
    click.echo("  详细选项: ae init --help")

    # ═══ §5 反向工程发现（--include-hidden） ═══
    if result._qoder_info:
        qi = result._qoder_info
        click.echo("")
        click.echo("═══ § 反向工程发现 (qoder) ═══")
        if qi.get("project_title"):
            click.echo(f"  Qoder 标题:   {qi['project_title']}")
        if qi.get("tech_stack_summary"):
            click.echo(f"  技术栈摘要:   {qi['tech_stack_summary']}")
        if qi.get("module_count"):
            click.echo(f"  识别模块数:   {qi['module_count']}")
        if qi.get("has_quickstart"):
            click.echo(f"  快速开始:     可用")
        if qi.get("repowiki_metadata"):
            rm = qi["repowiki_metadata"]
            click.echo(f"  Wiki 页面:    {rm.get('total_wiki_pages', 0)} 页, "
                        f"{rm.get('total_relations', 0)} 条关系")

    click.echo("")
