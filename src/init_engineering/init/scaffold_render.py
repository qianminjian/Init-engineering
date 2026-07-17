"""scaffold 阶段辅助函数 — 模板目录选择 + 阶段渲染。

从 scaffold_phases.py 提取（v2.2 Phase I），让 InitWorker 主类保持简短。

模块内容：
- build_template_dirs() : feature → path 映射
- render_to()           : InitWorker._phase_render() 提取的渲染函数
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .config_types import TEMPLATES_ROOT, TemplateConfig, coerce_bool
from .errors import ConfigFileError

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .answers import AnswersMap

# language → 模板 feature 子目录映射（来源: Copier _template.py 风格）
_LANG_FEATURE_MAP = {
    "typescript": "typescript",
    "javascript": "typescript",  # JS 项目复用 TS 模板（含 package.json/eslint/prettier）
    "python": "python",
    "go": "go",
    "rust": "rust",
    "bash": "bash",
    "java": "java",
}

# ci_platform → 模板 feature 子目录映射
_CI_FEATURE_MAP = {
    "github": "github-actions",
    "gitlab": "gitlab-ci",
}

# 渲染阶段需要回填默认空值的 str 变量
_RENDER_STR_VARS = [
    "project_description",
    "language",
    "package_manager",
    "test_runner",
    "ci_platform",
    "project_type",
    "qoder_project_title",
    "qoder_project_description",
    "qoder_tech_stack_summary",
    "qoder_quickstart",
]


def build_template_dirs(
    context: dict,
    type_dir: Path,
    subdirectory: str = "",
    external_template_dir: Path | None = None,
) -> list[Path]:
    """根据 context 决定要加载的模板目录列表（按优先级排列）。

    Args:
        context: AnswersMap.combined() 的渲染上下文
        type_dir: 项目类型对应的模板根目录 (e.g. templates/app-service/)
        subdirectory: 可选子目录（TemplateConfig.subdirectory）
        external_template_dir: 外部模板目录（--template-dir CLI），优先级最高

    Returns:
        模板目录列表，按查找顺序排列（外部 → _shared → features → type_dir）
    """
    default_root = external_template_dir if external_template_dir else TEMPLATES_ROOT
    template_dirs: list[Path] = []

    # 0. external template dir _shared (最高优先级)
    if external_template_dir:
        ext_shared = external_template_dir / "_shared"
        if ext_shared.exists():
            template_dirs.append(ext_shared)

    # 1. built-in _shared
    template_dirs.append(default_root / "_shared")

    # 2. language → _features/<lang>
    # spec-doc 项目跳过语言 feature（只生成文档，不需要源码模板）
    language = context.get("language", "typescript")
    project_type = context.get("project_type", "")
    if project_type != "spec-doc" and (lang_feat := _LANG_FEATURE_MAP.get(language)):
        # external feature first
        if external_template_dir:
            ext_feat = external_template_dir / "_features" / lang_feat
            if ext_feat.exists():
                template_dirs.append(ext_feat)
        feat_dir = default_root / "_features" / lang_feat
        if feat_dir.exists():
            template_dirs.append(feat_dir)

    # 3. feature 映射：lefthook / ci_platform / docker — 条件化选择
    feature_map: list[tuple[str, str]] = []
    if coerce_bool(context.get("use_lefthook")):
        feature_map.append(("use_lefthook", "lefthook"))

    ci_platform = context.get("ci_platform")
    if ci_platform:
        feat_name = _CI_FEATURE_MAP.get(ci_platform, "")
        if feat_name:
            feature_map.append(("ci_platform", feat_name))

    if coerce_bool(context.get("use_docker")):
        feature_map.append(("use_docker", "docker"))

    for answer_key, feature_name in feature_map:
        if not feature_name:
            continue
        if external_template_dir:
            ext_dir = external_template_dir / "_features" / feature_name
            if ext_dir.exists():
                template_dirs.append(ext_dir)
        feat_dir = default_root / "_features" / feature_name
        if feat_dir.exists():
            template_dirs.append(feat_dir)
        else:
            _logger.warning(
                "feature directory not found for '%s' (%s): %s",
                answer_key, feature_name, feat_dir,
            )

    # 4. type_dir（项目类型主模板，最后追加以获得最高优先级）
    # 外部 type dir 优先覆盖内置
    if external_template_dir:
        ext_type_dir = external_template_dir / type_dir.name
        if subdirectory:
            ext_type_dir = ext_type_dir / subdirectory
        if ext_type_dir.exists():
            template_dirs.append(ext_type_dir)
    final_type_dir = type_dir / subdirectory if subdirectory else type_dir
    template_dirs.append(final_type_dir)

    return template_dirs


def render_to(
    answers: AnswersMap,
    folder_name: str,
    template_dir: Path,
    subdirectory: str,
    exclude: list[str],
    skip_if_exists: list[str],
    no_render: list[str],
    envops: dict,
    overwrite: bool,
    tmpdir: Path,
    exclude_callback_spec: str | None = None,
    templates_suffix: str = ".jinja",
    preserve_symlinks: bool = True,
    external_template_dir: Path | None = None,
    mode: str = "fresh",
) -> list[Path]:
    """Phase 渲染 — 委托给 TemplateRenderer，渲染到 tmpdir。

    拆分自 InitWorker._phase_render()，让 InitWorker 主类保持简短。

    Args:
        answers: InitWorker._answers（duck-typed，需要 .builtins + .combined()）
        folder_name: 目标目录名 (dst_path.name)
        template_dir: 模板根目录
        subdirectory: 可选子目录
        exclude_callback_spec: P1.2 — "module:function" 格式字符串, 渲染阶段动态排除
            来源: Copier _main.py:753 match_exclude
        mode: "fresh" | "incremental" — 增量模式跳过示例源码模板
        其他: TemplateRenderer 参数

    Returns:
        生成的文件相对路径列表
    """
    # 准备 context 默认值（不修改传入的 AnswersMap，避免隐式副作用）
    builtin_overrides: dict = {"_folder_name": folder_name, "_mode": mode}
    for var in _RENDER_STR_VARS:
        if var not in answers:
            builtin_overrides[var] = ""
    if "project_name" not in answers:
        builtin_overrides["project_name"] = folder_name
    for k in ("use_typescript", "use_lefthook", "use_docker"):
        if k not in answers:
            builtin_overrides[k] = False

    context = {**answers.combined(), **builtin_overrides}
    template_dirs = build_template_dirs(
        context=context,
        type_dir=template_dir,
        subdirectory=subdirectory,
        external_template_dir=external_template_dir,
    )

    # v5.3: 多模块项目 — 不生成根级 src/（各子模块有自己的源码）
    # v5.6: 增量模式 — 存量 monorepo 项目已有模块结构，
    #        跳过 packages/**/src/main/**（不覆盖已有源码），保留 test + pom.xml 等配置
    if context.get("is_multi_module"):
        exclude = list(exclude) + ["src/**"]
    if mode == "incremental" and context.get("project_type") == "monorepo":
        exclude = list(exclude) + ["packages/**/src/main/**"]
        # v5.6 Phase I: aggregator 不在根目录 → 项目是「独立项目容器」而非「统一 reactor」。
        # 所有依赖根 reactor POM 的模板都应跳过（tests/ 的 pom.xml 有 <parent> 引用根 POM）。
        # 此列表为命名常量而非 ad-hoc 字符串追加，确保同类模板一次性全审计。
        # v5.6 Phase J: 容器项目无根 POM → 排除 tests/ 整个目录（含 pom.xml + Java 文件）。
        # tests/ Maven 模块仅适用于拓扑 B（reactor），拓扑 C 各模块用 src/test/java/。
        _REACTOR_ONLY_TEMPLATES = ["/pom.xml", "packages/", "tests/"]
        if context.get("aggregator_path", ""):
            exclude = list(exclude) + _REACTOR_ONLY_TEMPLATES

    # P1.2: 解析 exclude_callback_spec → 可调用对象
    # ImportError: 模板模块不存在 → 回退(非阻断)
    # ValueError: spec 格式错误 → 抛错(阻断)
    # AttributeError: 函数不存在 → 抛错(阻断)
    from ._shared.exclude import default_match_exclude, parse_exclude_callback

    if exclude_callback_spec is None:
        exclude_callback_spec = TemplateConfig._EXCLUDE_CALLBACK_SPEC

    try:
        match_exclude = parse_exclude_callback(exclude_callback_spec)
    except ImportError:
        _logger.warning(
            "exclude callback module not found, falling back to default: %s",
            exclude_callback_spec,
        )
        match_exclude = default_match_exclude
    except (ValueError, AttributeError) as e:
        raise ConfigFileError(
            f"exclude_callback_spec 配置错误: {e}",
            config_path=exclude_callback_spec,
        ) from e

    from .renderer import TemplateRenderer

    renderer = TemplateRenderer(
        template_dirs=template_dirs,
        context=context,
        exclude=exclude,
        skip_if_exists=skip_if_exists,
        no_render=no_render,
        envops=envops,
        overwrite=overwrite,
        match_exclude=match_exclude,
        templates_suffix=templates_suffix,
        preserve_symlinks=preserve_symlinks,
    )
    return renderer.render_to(tmpdir)
