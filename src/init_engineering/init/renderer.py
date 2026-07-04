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

PR#3 P1-2: 拆分 — atomic_write + is_binary 迁至 _shared/io.py,
symlink 处理迁至 renderer_symlinks.py。本文件瘦身到 <300 行。
"""

import shutil
from collections.abc import Callable
from pathlib import Path

import jinja2
import pathspec
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from ._shared.io import _atomic_write_binary, _atomic_write_text, detect_newline, is_binary
from .errors import TemplateRenderError
from .renderer_symlinks import resolve_symlink


class TemplateRenderer:
    """遍历多层模板目录，双层渲染文件名和内容。

    template_dirs 按优先级排列：后面的目录覆盖前面的同名文件。
    """

    TEMPLATE_SUFFIX = ".jinja"

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
        templates_suffix: str = ".jinja",
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
        # T2-1: templates_suffix 参数化 — 支持自定义模板后缀,替代类属性 TEMPLATE_SUFFIX
        self.templates_suffix = templates_suffix
        # T2-2: preserve_symlinks 可配置 — True 保留 symlink, False 跳过 dangling 或解析内容
        self.preserve_symlinks = preserve_symlinks
        # P0-2: on_exists 回调 — 目标文件已存在时调用 HookRunner.on_exists_hook
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

                # P2-12: 路径穿越 guard — 改用 _shared.path_utils.is_path_under_any_root
                # (与 answers.py / config_loader.py 同一 util, 避免散落实现)
                from ._shared.path_utils import is_path_under_any_root
                if not is_path_under_any_root(dst_file, [dst_dir]):
                    raise TemplateRenderError(str(rel_path), ValueError("路径穿越"))

                if (
                    dst_file.exists()
                    and generated.get(rendered_rel) is None
                    and not self._should_overwrite(rendered_rel)
                ):
                    # P0-2: 调用 on_exists 钩子 (HookRunner.on_exists_hook)
                    if self.on_exists is not None:
                        self.on_exists(rendered_rel)
                    continue

                dst_file.parent.mkdir(parents=True, exist_ok=True)

                if self._is_no_render(str(rel_path)):
                    self._write_copy(src_file, dst_file)
                    generated[rendered_rel] = dst_file
                    continue

                # PR#3 P1-2: symlink 处理委托 renderer_symlinks.resolve_symlink
                handled, skip_reason = resolve_symlink(
                    src_file, dst_file, preserve_symlinks=self.preserve_symlinks,
                )
                if handled:
                    # skip_reason 非空表示 dangling/symlink_failed 等跳过场景,
                    # 不应记录到 generated (测试要求 dangling 不在 generated 中)
                    if skip_reason is None:
                        generated[rendered_rel] = dst_file
                    continue

                self._write_rendered(src_file, dst_file, is_template=is_template)

                try:
                    shutil.copymode(src_file, dst_file)
                except OSError:
                    pass  # Windows 不支持 chmod, symlink 权限保留可能失败
                generated[rendered_rel] = dst_file

        return list(generated.values())

    def _write_copy(self, src_file: Path, dst_file: Path) -> None:
        """F1: no_render 文件原子复制 — 二进制/文本都走流式原子写。"""
        if is_binary(str(src_file)):
            _atomic_write_binary(dst_file, src_file)
        else:
            newline = detect_newline(src_file)
            _atomic_write_text(dst_file, src_file.read_text(), newline=newline)

    def _write_rendered(self, src_file: Path, dst_file: Path, *, is_template: bool) -> None:
        """核心渲染分支:template 走 jinja,其他按二进制/文本复制。"""
        if is_template:
            try:
                content = self._render(src_file.read_text())
            except jinja2.TemplateError as e:
                raise TemplateRenderError(str(src_file.relative_to(src_file.parents[-2])), e) from e
            newline = detect_newline(src_file)
            _atomic_write_text(dst_file, content, newline=newline)
        elif is_binary(str(src_file)):
            _atomic_write_binary(dst_file, src_file)
        else:
            newline = detect_newline(src_file)
            _atomic_write_text(dst_file, src_file.read_text(), newline=newline)

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
        # pathspec 0.12+ 推荐 GitIgnoreSpecPattern, 旧版 fallback 到 GitWildMatchPattern
        if hasattr(pathspec.patterns, "GitIgnoreSpecPattern"):
            pattern_cls = pathspec.patterns.GitIgnoreSpecPattern
        else:
            pattern_cls = pathspec.patterns.GitWildMatchPattern
        spec = pathspec.PathSpec.from_lines(pattern_cls, patterns)
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

    # PR#3 P1-2: _detect_newline 已迁至 _shared.io.detect_newline
    # 保留 staticmethod 薄壳供旧调用方 (例如子类的扩展) 兼容
    @staticmethod
    def _detect_newline(file_path: Path) -> str | None:
        """检测文件的换行符风格 — PR#3 P1-2 后薄壳,实际调用 _shared.io.detect_newline."""
        return detect_newline(file_path)