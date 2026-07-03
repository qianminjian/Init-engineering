"""Phase 3: render — 渲染模板到 tmpdir (含 before/after 钩子).

来源: scaffold_phase_funcs.py phase_render (2026-07-03 拆分).

注意 _render_to 调用方式:
- 直接 `from ..scaffold_render import render_to as _render_to` 会破坏测试
  patch("init_engineering.init.scaffold_phase_funcs._render_to") 的拦截
- 通过 `scaffold_phase_funcs` 模块间接调用, 让测试 patch 的 mock 生效
- scaffold_phase_funcs._render_to 用 PEP 562 __getattr__ 懒加载 (避免循环 import)
"""

from __future__ import annotations

from pathlib import Path

from .. import scaffold_phase_funcs
from ..answers import AnswersMap
from ..config import TemplateConfig
from ..hooks import HookRunner


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
    strict: bool,
) -> list[Path]:
    """渲染到 tmpdir（含 before/after 钩子）."""
    templates_suffix = (
        templates_suffix
        if templates_suffix is not None
        else template.templates_suffix
    )
    preserve_symlinks = (
        preserve_symlinks
        if preserve_symlinks is not None
        else template.preserve_symlinks
    )

    hook_runner = HookRunner(dst_path, strict=strict)
    context = answers.combined()
    hook_runner.before_renderer_hook(context)

    # 通过 scaffold_phase_funcs 模块间接调用 _render_to, 让测试
    # patch("init_engineering.init.scaffold_phase_funcs._render_to") 生效.
    # 直接 import scaffold_render.render_to 会绕过 patch 拦截.
    generated = scaffold_phase_funcs._render_to(
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
        exclude_callback=template.exclude_callback,
        templates_suffix=templates_suffix,
        preserve_symlinks=preserve_symlinks,
        on_exists=hook_runner.on_exists_hook,
    )

    hook_runner.after_renderer_hook(context, generated)
    return generated