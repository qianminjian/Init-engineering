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

import os
import shutil
from collections.abc import Callable
from pathlib import Path

import jinja2
import pathspec
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from .errors import TemplateRenderError


# PE-P1-5: 流式原子写 — 大文件 (大 README / 嵌入式 binary) 写到 dst.tmp-<pid>,
# write 完成后 rename 替换 dst。SIGKILL 落入写过程 → dst.tmp-<pid> 残留,
# dst 保持上次成功状态 (或不存在),不出现半文件。
# 流式 (chunks) 避免 read_text() 一次性加载整文件到内存。
_CHUNK_SIZE = 64 * 1024  # 64KB


def _atomic_write_text(dst: Path, content: str, newline: str | None = None) -> None:
    """流式原子写文本文件。

    Args:
        dst: 目标路径
        content: 完整内容 (jinja 渲染后)
        newline: 换行符策略 (None/''/'\n')，透传给 Path.write_text
    """
    import time as _time

    partial = dst.with_name(f"{dst.name}.tmp-{_time.monotonic_ns()}")
    try:
        with open(partial, "w", encoding="utf-8", newline=newline) as f:
            f.write(content)
        partial.replace(dst)
    except Exception:
        try:
            partial.unlink()
        except OSError:
            pass
        raise


def _atomic_write_binary(dst: Path, src: Path) -> None:
    """流式原子写二进制文件 — 分块 64KB read+write。

    shutil.copy2 不分块(直接 syscall 走 sendfile/copyfile_range 已是零拷贝),
    但仍是直接写到 final path。改为分块 read+write 到 .tmp 再 rename。
    """
    import time as _time

    partial = dst.with_name(f"{dst.name}.tmp-{_time.monotonic_ns()}")
    try:
        with open(src, "rb") as f_in, open(partial, "wb") as f_out:
            while True:
                chunk = f_in.read(_CHUNK_SIZE)
                if not chunk:
                    break
                f_out.write(chunk)
        # 复制权限位
        shutil.copymode(src, partial)
        partial.replace(dst)
    except Exception:
        try:
            partial.unlink()
        except OSError:
            pass
        raise


def is_binary(path: str) -> bool:
    """检测文件是否为二进制（无外部依赖，纯字节启发式）。

    算法：
    1. 读首 8KB 字节
    2. 含 NUL 字节（\\x00）→ 二进制
    3. 全部 UTF-8 可解码 → 文本
    4. 否则 → 二进制

    替代 binaryornot（最后发布 2020，无 3.13 兼容性保证）。
    """
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
    except OSError:
        return False
    if not chunk:
        return False
    if b"\x00" in chunk:
        return True
    try:
        chunk.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


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
                    shutil.copy2(src_file, dst_file)
                    generated[rendered_rel] = dst_file
                    continue

                # A4: symlink 处理 — preserve_symlinks=True 保留为 symlink; False 解析为内容
                if src_file.is_symlink():
                    target = src_file.resolve()
                    if self.preserve_symlinks:
                        if target.exists():
                            # 安全: 只拒绝含 .. 的相对 symlink（可穿越到 dst_dir 外）
                            # 绝对路径 symlink 可保留（目标位置在渲染后不变）
                            try:
                                raw_target = os.readlink(src_file)
                            except OSError:
                                continue
                            if ".." in raw_target:
                                raise TemplateRenderError(
                                    str(rel_path),
                                    ValueError(
                                        f"symlink target '{raw_target}' contains '..', refusing to copy"
                                    ),
                                )
                            # 复制 symlink 本身 (保留为指向 target 的链接)
                            try:
                                dst_file.symlink_to(target)
                            except OSError:
                                continue
                            generated[rendered_rel] = dst_file
                            continue
                        # dangling symlink → 跳过 (目标不存在,无法保留)
                        continue
                    else:
                        # preserve_symlinks=False: 跳过 dangling; 有效 symlink 解析为内容复制
                        if not target.exists():
                            continue  # dangling symlink → 跳过
                        # 解析 symlink 为内容,复制到目标
                        if is_binary(str(target)):
                            shutil.copy2(target, dst_file)
                        else:
                            newline = self._detect_newline(target)
                            dst_file.write_text(target.read_text(), newline=newline)
                        try:
                            shutil.copymode(src_file, dst_file)
                        except OSError:
                            pass
                        generated[rendered_rel] = dst_file
                        continue

                if is_template:
                    try:
                        content = self._render(src_file.read_text())
                    except jinja2.TemplateError as e:
                        raise TemplateRenderError(str(rel_path), e) from e
                    newline = self._detect_newline(src_file)
                    # PE-P1-5: 流式原子写 — 大文件 (大 README/Dockerfile) 不一次性 read+write
                    # 分块 read(64KB) 写入 .partial 后 rename 原子替换。
                    # SIGKILL 落入写过程 → .partial 残留, dst_file 保持上次成功状态
                    _atomic_write_text(dst_file, content, newline=newline)
                elif is_binary(str(src_file)):
                    # 二进制文件流式复制 (shutil.copyfile 内部用 sendfile/copyfile_range,
                    # 已是流式; 但仍是 write-to-final-path,加 .partial 阶段防 SIGKILL 留半文件)
                    _atomic_write_binary(dst_file, src_file)
                else:
                    newline = self._detect_newline(src_file)
                    _atomic_write_text(dst_file, src_file.read_text(), newline=newline)

                try:
                    shutil.copymode(src_file, dst_file)
                except OSError:
                    pass  # Windows 不支持 chmod, symlink 权限保留可能失败
                generated[rendered_rel] = dst_file

        return list(generated.values())

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
        """
        matcher = self._path_matcher(self.exclude)
        rel = str(file_path.relative_to(src_dir))
        if matcher(rel):
            return True
        return self.match_exclude is not None and self.match_exclude(file_path)

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
            with open(file_path, encoding="utf-8") as f:
                f.readline()
                newline = getattr(f, "newlines", None)
                if isinstance(newline, tuple):
                    newline = newline[0]
                return newline
        except Exception:
            return None
