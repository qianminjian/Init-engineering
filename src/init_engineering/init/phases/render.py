"""Phase 3: render — 渲染模板到 tmpdir (含 before/after 钩子).

来源: init/scaffold_phases.py → phases/render.py (2026-07-03 拆分).
"""

from __future__ import annotations

from pathlib import Path

from ..answers import AnswersMap
from ..config_types import TemplateConfig
from ..scaffold_render import render_to


def phase_render(
    answers: AnswersMap,
    template: TemplateConfig,
    dst_path: Path,
    tmpdir: Path,
    *,
    overwrite: bool,
    templates_suffix: str | None,
    preserve_symlinks: bool | None,
    template_dir_override: Path | None,
) -> list[Path]:
    """渲染到 tmpdir。

    ⚠ 副作用:
    - 遍历模板目录树，写入渲染后文件到 tmpdir
    - 生成的路径列表供后续 phase_finalize 使用
    """
    templates_suffix, preserve_symlinks = template.resolve_render_opts(
        templates_suffix, preserve_symlinks
    )

    generated = render_to(
        answers=answers,
        folder_name=dst_path.name,
        template_dir=template.template_dir,
        subdirectory=template.subdirectory,
        external_template_dir=template_dir_override,
        exclude=template.exclude,
        skip_if_exists=template.skip_if_exists,
        no_render=template.no_render,
        envops=template.envops,
        overwrite=overwrite,
        tmpdir=tmpdir,
        exclude_callback_spec=template.exclude_callback,
        templates_suffix=templates_suffix,
        preserve_symlinks=preserve_symlinks,
    )

    return generated
