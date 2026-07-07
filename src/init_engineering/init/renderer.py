"""TemplateRenderer — Jinja2 双层渲染引擎.

来源：
- copier/_main.py:815-1025 — _render_file() + _render_folder() + 冲突处理
- cookiecutter/generate.py:175-260 — generate_file() 带二进制检测、换行符保持、权限保持
- cookiecutter/generate.py:327-466 — generate_files() 遍历目录树 + is_copy_only_path

接口：
  TemplateRenderer(template_dirs, context) -> .render_to(dst_dir) -> list[Path]

设计决策：
- template_dirs 是列表，支持 _shared/ + _features/ + 类型模板 多层源目录
- 文件名中的 Jinja2 条件：渲染结果为空字符串 → 跳过不生成
- 模板后缀约定：文件名以 .jinja 结尾 → 渲染文件名，内容也渲染
- 非 .jinja 文件 → 原样复制（二进制自动检测）
- no_render 列表中的文件始终原样复制
- 文件冲突：调用 conflict_handler 回调决定覆盖/跳过/询问
- Jinja2 环境使用 SandboxedEnvironment

PR#3 P1-2: 拆分 — atomic_write + is_binary 迁至 _shared/io.py。
symlink 处理并入本文件 (P2: renderer_symlinks.py 已折叠)。
"""

from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Callable
from pathlib import Path

import jinja2
import pathspec
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from ._shared.io import atomic_write_binary, atomic_write_text, detect_newline, is_binary
from ._shared.path_utils import is_path_under_any_root
from .config_types import DEFAULT_TEMPLATES_SUFFIX
from .errors import TemplateRenderError

_logger = logging.getLogger(__name__)


def resolve_symlink(
    src_file: Path,
    dst_file: Path,
    *,
    preserve_symlinks: bool,
) -> tuple[bool, str | None]:
    """处理模板中的 symlink 文件 (从 renderer_symlinks.py 折叠)。

    返回 (handled, skip_reason): handled=True 已写入, handled=False+reason 已跳过。
    """
    if not src_file.is_symlink():
        return False, None
    target = src_file.resolve()
    if preserve_symlinks:
        if not target.exists():
            return True, "dangling"
        try:
            raw_target = os.readlink(src_file)
        except OSError:
            return True, "unreadable"
        if ".." in raw_target:
            raise TemplateRenderError(
                str(src_file),
                ValueError(f"symlink target '{raw_target}' contains '..', refusing to copy"),
            )
        try:
            dst_file.symlink_to(target)
        except OSError:
            return True, "symlink_failed"
        return True, None
    if not target.exists():
        return True, "dangling"
    if is_binary(str(target)):
        atomic_write_binary(dst_file, target)
    else:
        newline = detect_newline(target)
        atomic_write_text(dst_file, target.read_text(), newline=newline)
    try:
        shutil.copymode(src_file, dst_file)
    except OSError:
        _logger.debug("copymode failed for %s", dst_file, exc_info=True)
    return True, None


class TemplateRenderer:
    """遍历多层模板目录，双层渲染文件名和内容。

    template_dirs 按优先级排列：后面的目录覆盖前面的同名文件。
    """

    TEMPLATE_SUFFIX = DEFAULT_TEMPLATES_SUFFIX

    def __init__(
        self,
        template_dirs: list[Path],
        context: dict,
        exclude: list[str] | None = None,
        skip_if_exists: list[str] | None = None,
        no_render: list[str] | None = None,
        envops: dict | None = None,
        overwrite: bool = False,
        conflict_handler: Callable[[str], bool] | None = None,
        match_exclude: Callable[[Path], bool] | None = None,
        templates_suffix: str | None = None,
        preserve_symlinks: bool = True,
        on_exists: Callable[[str], None] | None = None,
    ):
        self.template_dirs = template_dirs
        self.context = context
        self.exclude = exclude or []
        self.skip_if_exists = skip_if_exists or []
        self.no_render = no_render or []
        self.overwrite = overwrite
        self.conflict_handler = conflict_handler
        # P1.2: Copier match_exclude 回调 — 动态排除路径 (Callable[[Path], bool])
        # 来源: copier/_main.py:753 match_exclude(self) -> Callable[[Path], bool]
        self.match_exclude = match_exclude
        self.templates_suffix = (
            templates_suffix if templates_suffix is not None else self.TEMPLATE_SUFFIX
        )
        # T2-2: preserve_symlinks 可配置 — True 保留 symlink, False 跳过 dangling 或解析内容
        self.preserve_symlinks = preserve_symlinks
        self.on_exists = on_exists
        self.env = SandboxedEnvironment(
            undefined=StrictUndefined,
            **(envops or {"keep_trailing_newline": True}),
        )
        # PR#5 P1-8: 预算 PathSpec 实例, render_to 循环内复用
        # 之前每个文件都重新 pathspec.PathSpec.from_lines(...)
        # 100 文件 × 3 matcher = 300 次 re.compile, 30k+ glob 编译开销
        self._exclude_matcher = self._path_matcher(self.exclude)
        self._no_render_matcher = self._path_matcher(self.no_render)
        self._skip_if_exists_matcher = self._path_matcher(self.skip_if_exists)

    def render_to(self, dst_dir: Path) -> list[Path]:
        """遍历所有模板目录，渲染到目标目录。返回生成的文件列表。"""
        generated: dict[str, Path] = {}

        for src_dir in self.template_dirs:
            if not src_dir.exists():
                continue
            for src_file in src_dir.rglob("*"):
                if src_file.is_dir():
                    continue
                if self._is_excluded(src_file, src_dir):
                    continue

                rel_path = src_file.relative_to(src_dir)
                rendered_rel = self._render_path(str(rel_path))

                if not rendered_rel or rendered_rel.strip() == "":
                    continue

                is_template = rendered_rel.endswith(self.templates_suffix)
                if is_template:
                    rendered_rel = rendered_rel[: -len(self.templates_suffix)]

                dst_file = dst_dir / rendered_rel

                if not is_path_under_any_root(dst_file, [dst_dir]):
                    raise TemplateRenderError(str(rel_path), ValueError("路径穿越"))

                if (
                    dst_file.exists()
                    and generated.get(rendered_rel) is None
                    and not self._should_overwrite(rendered_rel)
                ):
                    if self.on_exists is not None:
                        self.on_exists(rendered_rel)
                    continue

                dst_file.parent.mkdir(parents=True, exist_ok=True)

                if self._is_no_render(str(rel_path)):
                    self._write_copy(src_file, dst_file)
                    generated[rendered_rel] = dst_file
                    continue

                # symlink 处理委托 resolve_symlink (本模块内)
                handled, skip_reason = resolve_symlink(
                    src_file, dst_file, preserve_symlinks=self.preserve_symlinks,
                )
                if handled:
                    # skip_reason 非空表示 dangling/symlink_failed 等跳过场景,
                    # 不应记录到 generated (测试要求 dangling 不在 generated 中)
                    if skip_reason is None:
                        generated[rendered_rel] = dst_file
                    continue

                self._write_rendered(src_file, dst_file, src_dir, is_template=is_template)

                try:
                    shutil.copymode(src_file, dst_file)
                except OSError:
                    _logger.info(
                        "copymode failed for %s — file permissions may be incorrect",
                        dst_file,
                    )
                generated[rendered_rel] = dst_file

        return list(generated.values())

    def _write_copy(self, src_file: Path, dst_file: Path) -> None:
        """F1: no_render 文件原子复制 — 二进制/文本都走流式原子写。"""
        if is_binary(str(src_file)):
            atomic_write_binary(dst_file, src_file)
        else:
            newline = detect_newline(src_file)
            atomic_write_text(dst_file, src_file.read_text(), newline=newline)

    def _write_rendered(
        self, src_file: Path, dst_file: Path, src_dir: Path, *, is_template: bool
    ) -> None:
        """核心渲染分支:template 走 jinja,其他按二进制/文本复制。"""
        if is_template:
            try:
                content = self._render(src_file.read_text())
            except jinja2.TemplateError as e:
                raise TemplateRenderError(str(src_file.relative_to(src_dir)), e) from e
            newline = detect_newline(src_file)
            atomic_write_text(dst_file, content, newline=newline)
        elif is_binary(str(src_file)):
            atomic_write_binary(dst_file, src_file)
        else:
            newline = detect_newline(src_file)
            atomic_write_text(dst_file, src_file.read_text(), newline=newline)

    def _render_path(self, path_str: str) -> str:
        """渲染路径模板。"""
        try:
            tpl = self.env.from_string(path_str)
            return tpl.render(**self.context)
        except jinja2.TemplateError as e:
            raise TemplateRenderError(path_str, e) from e

    def _render(self, content: str) -> str:
        """渲染文件内容。"""
        tpl = self.env.from_string(content)
        return tpl.render(**self.context)

    def _path_matcher(self, patterns: list[str]) -> Callable[[str], bool]:
        """Produce a function that matches against .gitignore-style patterns.

        参考 Copier _main.py:467-471 _path_matcher + pathspec。

        P2-18: 改用 GitIgnoreSpecPattern (官方推荐) — GitWildMatchPattern 已 deprecated,
        新代码会触发 deprecation warning 噪音。GitIgnoreSpecPattern 行为与原相同。
        """
        # pathspec >=1.1.1 使用字符串 API, 'gitignore' 替代已弃用的 GitWildMatchPattern
        spec = pathspec.PathSpec.from_lines("gitignore", patterns)
        return spec.match_file

    def _is_excluded(self, file_path: Path, src_dir: Path) -> bool:
        """检查文件是否被排除。

        两层排除（与 Copier match_exclude + 路径模式一致）:
        1. self.exclude 路径模式 (gitignore-style) — 来自 _exclude YAML
        2. self.match_exclude 回调 (Callable[[Path], bool]) — P1.2 动态排除
           默认指向 _shared.exclude.default_match_exclude, 排除 .git/ 等

        PR#5 P1-8: 使用预算的 _exclude_matcher, 不再每次重新构造 PathSpec
        """
        rel = str(file_path.relative_to(src_dir))
        if self._exclude_matcher(rel):
            return True
        return self.match_exclude is not None and self.match_exclude(file_path)

    def _is_no_render(self, rel_path: str) -> bool:
        """检查文件是否应原样复制不渲染。"""
        return self._no_render_matcher(rel_path)

    def _should_overwrite(self, rel_path: str) -> bool:
        """判断是否覆盖已存在的文件。"""
        if self.overwrite:
            return True
        if self._skip_if_exists_matcher(rel_path):
            return False
        if self.conflict_handler:
            return self.conflict_handler(rel_path)
        return False

    # _detect_newline 已迁至 _shared.io.detect_newline (PR#3 P1-2), 薄壳已移除.