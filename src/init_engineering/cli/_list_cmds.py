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


def _detect_missing_infrastructure(
    dst_path: Path,
    result: "DetectionResult",
) -> list[str]:
    """检测缺失的工程基础设施文件。

    返回人类可读的缺失项列表，用于 ae analyze 输出。
    """
    missing: list[str] = []

    # 根目录工程文件
    for fname, label in [
        (".editorconfig", ".editorconfig — 编辑器配置"),
        (".gitignore", ".gitignore — Git 忽略规则"),
        ("CLAUDE.md", "CLAUDE.md — AI Agent 项目文档"),
        ("README.md", "README.md — 项目说明"),
        ("LICENSE", "LICENSE — 开源许可证"),
    ]:
        if not (dst_path / fname).exists():
            missing.append(label)

    # 设计基线
    if not (dst_path / "design" / "BEACON.md").exists():
        missing.append("design/BEACON.md — 设计基线")

    # CI 配置
    has_ci = (
        (dst_path / ".github" / "workflows").exists()
        or (dst_path / ".gitlab-ci.yml").exists()
        or (dst_path / "Jenkinsfile").exists()
    )
    if not has_ci:
        missing.append(".github/workflows/ 或 .gitlab-ci.yml — CI 流水线")

    # Git hooks
    has_hooks = (
        (dst_path / ".pre-commit-config.yaml").exists()
        or (dst_path / "lefthook.yml").exists()
    )
    if not has_hooks:
        missing.append(".pre-commit-config.yaml 或 lefthook.yml — Git hooks")

    # 测试目录
    test_dirs = _find_test_dirs(dst_path, result)
    if test_dirs is not None and not test_dirs:
        missing.append("src/test/ — 测试目录（全项目未发现）")

    return missing


def _find_test_dirs(
    dst_path: Path,
    result: "DetectionResult",
) -> list[Path] | None:
    """查找项目中的测试目录。返回 None 表示无法判断（无源码语言）。

    在项目根目录下递归搜索 src/test/ 目录（最多 3 层）。
    """
    found: list[Path] = []
    try:
        for p in dst_path.rglob("src/test"):
            if p.is_dir():
                found.append(p)
                if len(found) >= 10:
                    break
    except OSError:
        return None
    return found


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
        # v5.6: 模块-磁盘校验 — 标记 pom.xml <modules> 与磁盘目录不一致
        missing = result._java_info.get("module_missing", []) if result._java_info else []
        extra = result._java_info.get("module_extra_dirs", []) if result._java_info else []
        if missing:
            click.echo(f"  ⚠ pom.xml 声明但磁盘不存在的模块: {', '.join(missing)}")
        if extra:
            click.echo(f"  ⚠ 磁盘存在但未在 pom.xml 声明的模块: {', '.join(extra)}")
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

    # ═══ §4 缺失的工程文件 ═══
    click.echo("")
    click.echo("═══ § 缺失的工程文件 ═══")
    missing = _detect_missing_infrastructure(dst_path, result)
    if missing:
        for item in missing:
            click.echo(f"  ✗ {item}")
    else:
        click.echo("  ✓ 工程基础设施完整")

    # ═══ §5 初始化建议 ═══
    click.echo("")
    click.echo("═══ § 初始化建议 ═══")
    _ptype = result.project_type or "app-service"
    _lang = result.language or ""
    lang_flag = f" --language {_lang}" if _lang else ""

    # v5.6: 根据项目状态推荐正确的初始化模式
    has_answers_yml = (dst_path / ".ae-answers.yml").exists()
    is_empty = not any(dst_path.iterdir()) if dst_path.exists() else True

    if is_empty:
        click.echo(f"  新项目（空目录）:")
        click.echo(f"    ae init . --type {_ptype}{lang_flag} --defaults")
    elif has_answers_yml:
        click.echo(f"  存量项目（有基线文件）:")
        click.echo(f"    ae init . --incremental     # 基于基线补充缺失文件")
        click.echo(f"    ae update                    # 版本升级增量更新")
    else:
        click.echo(f"  存量项目（首次初始化）:")
        click.echo(f"    ae init . --incremental     # 自动检测 + 只补缺失文件")
        if missing:
            click.echo(f"    将补充以上 {len(missing)} 个缺失的工程文件")
    if include_hidden:
        click.echo(f"    --include-hidden 已启用")
    click.echo("")
    click.echo("  详细选项: ae init --help")

    # ═══ §6 反向工程发现（--include-hidden） ═══
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
