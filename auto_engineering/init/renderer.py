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
"""

import shutil
from collections.abc import Callable
from pathlib import Path

import pathspec

import jinja2
from jinja2.sandbox import SandboxedEnvironment
from jinja2 import StrictUndefined

from .errors import TemplateRenderError

try:
    from binaryornot.check import is_binary
except ImportError:
    def is_binary(path):
        with open(path, 'rb') as f:
            return b'\x00' in f.read(1024)


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
    ):
        self.template_dirs = template_dirs
        self.context = context
        self.exclude = exclude or []
        self.skip_if_exists = skip_if_exists or []
        self.no_render = no_render or []
        self.overwrite = overwrite
        self.conflict_handler = conflict_handler
        self.env = SandboxedEnvironment(
            undefined=StrictUndefined,
            **(envops or {"keep_trailing_newline": True}),
        )

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

                is_template = rendered_rel.endswith(self.TEMPLATE_SUFFIX)
                if is_template:
                    rendered_rel = rendered_rel[:-len(self.TEMPLATE_SUFFIX)]

                dst_file = dst_dir / rendered_rel

                # Path traversal guard (参考 Copier _main.py:800-805)
                dst_dir_real = dst_dir.resolve()
                if not dst_file.resolve().is_relative_to(dst_dir_real):
                    raise TemplateRenderError(str(src_file), ValueError("路径穿越"))

                if dst_file.exists() and generated.get(rendered_rel) is None:
                    if not self._should_overwrite(rendered_rel):
                        continue

                dst_file.parent.mkdir(parents=True, exist_ok=True)

                if self._is_no_render(str(rel_path)):
                    shutil.copy2(src_file, dst_file)
                    generated[rendered_rel] = dst_file
                    continue

                if is_template:
                    try:
                        content = self._render(src_file.read_text())
                    except jinja2.TemplateError as e:
                        raise TemplateRenderError(str(src_file), e)
                    newline = self._detect_newline(src_file)
                    dst_file.write_text(content, newline=newline)
                elif is_binary(str(src_file)):
                    shutil.copy2(src_file, dst_file)
                else:
                    newline = self._detect_newline(src_file)
                    dst_file.write_text(src_file.read_text(), newline=newline)

                shutil.copymode(src_file, dst_file)
                generated[rendered_rel] = dst_file

        return list(generated.values())

    def _render_path(self, path_str: str) -> str:
        """渲染路径模板。"""
        try:
            tpl = self.env.from_string(path_str)
            return tpl.render(**self.context)
        except jinja2.TemplateError as e:
            raise TemplateRenderError(path_str, e)

    def _render(self, content: str) -> str:
        """渲染文件内容。"""
        tpl = self.env.from_string(content)
        return tpl.render(**self.context)

    def _path_matcher(self, patterns: list[str]) -> Callable[[str], bool]:
        """Produce a function that matches against .gitignore-style patterns.

        参考 Copier _main.py:467-471 _path_matcher + pathspec。
        """
        spec = pathspec.PathSpec.from_lines(
            pathspec.patterns.GitWildMatchPattern, patterns
        )
        return spec.match_file

    def _is_excluded(self, file_path: Path, src_dir: Path) -> bool:
        """检查文件是否被排除。"""
        matcher = self._path_matcher(self.exclude)
        rel = str(file_path.relative_to(src_dir))
        return matcher(rel)

    def _is_no_render(self, rel_path: str) -> bool:
        """检查文件是否应原样复制不渲染。"""
        matcher = self._path_matcher(self.no_render)
        return matcher(rel_path)

    def _should_overwrite(self, rel_path: str) -> bool:
        """判断是否覆盖已存在的文件。"""
        if self.overwrite:
            return True
        matcher = self._path_matcher(self.skip_if_exists)
        if matcher(rel_path):
            return False
        if self.conflict_handler:
            return self.conflict_handler(rel_path)
        return False

    @staticmethod
    def _detect_newline(file_path: Path) -> str | None:
        """检测文件的换行符风格。"""
        try:
            with open(file_path, encoding='utf-8') as f:
                f.readline()
                newline = getattr(f, 'newlines', None)
                if isinstance(newline, tuple):
                    newline = newline[0]
                return newline
        except Exception:
            return None
