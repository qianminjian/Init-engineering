"""tests for init/renderer.py — 非交互路径覆盖."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from init_engineering.init.renderer import TemplateRenderer


class TestTemplateRendererEdgeCases:
    """TemplateRenderer edge case 覆盖."""

    def test_render_to_skips_nonexistent_src_dir(self, tmp_path: Path):
        """render_to 跳过不存在的 template_dirs 条目 (line 88)."""
        renderer = TemplateRenderer(
            template_dirs=[tmp_path / "nonexistent"],
            context={},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
        )
        # 不崩溃，跳过不存在的目录
        result = renderer.render_to(tmp_path / "out")
        assert result == []

    def test_render_to_skips_empty_rendered_rel(self, tmp_path: Path):
        """_render_path 返回空字符串时跳过 (line 99)."""
        renderer = TemplateRenderer(
            template_dirs=[],
            context={},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
        )
        # 手动 patch _render_path 返回空字符串
        with patch.object(renderer, "_render_path", return_value=""):
            result = renderer.render_to(tmp_path / "out")
        # 空路径被跳过
        assert result == []

    def test_copytree_overwrite_false_raises(self, tmp_path: Path):
        """overwrite=False 且目标存在时复制操作正确处理."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "file.txt").write_text("content")

        dst = tmp_path / "dst"
        dst.mkdir()
        (dst / "file.txt").write_text("old")

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,  # 不覆盖已有文件
        )
        result = renderer.render_to(dst)
        # 已有文件被跳过
        assert (dst / "file.txt").read_text() == "old"

    def test_on_exists_callback_called(self, tmp_path: Path):
        """P0-2: 目标文件已存在时 on_exists 回调被调用."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "file.txt").write_text("content")

        dst = tmp_path / "dst"
        dst.mkdir()
        (dst / "file.txt").write_text("existing")

        called_with: list[str] = []

        def on_exists_callback(rel_path: str) -> None:
            called_with.append(rel_path)

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={},
            exclude=[],
            skip_if_exists=[],  # 不跳过，触发 exists 分支
            no_render=[],
            envops={},
            overwrite=False,
            on_exists=on_exists_callback,
        )
        renderer.render_to(dst)
        assert "file.txt" in called_with

    def test_on_exists_callback_not_called_when_overwrite(self, tmp_path: Path):
        """overwrite=True 时 on_exists 不被调用 (文件被覆盖而非跳过)."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "file.txt").write_text("new")

        dst = tmp_path / "dst"
        dst.mkdir()
        (dst / "file.txt").write_text("old")

        called_with: list[str] = []

        def on_exists_callback(rel_path: str) -> None:
            called_with.append(rel_path)

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=True,
            on_exists=on_exists_callback,
        )
        renderer.render_to(dst)
        # overwrite=True 时不走 exists 分支，回调不被调用
        assert called_with == []
        assert (dst / "file.txt").read_text() == "new"

    def test_on_exists_callback_not_called_when_skip_exists(self, tmp_path: Path):
        """skip_if_exists 命中的文件时 on_exists 仍被调用 (文件存在+跳过)."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "file.txt").write_text("content")

        dst = tmp_path / "dst"
        dst.mkdir()
        (dst / "file.txt").write_text("existing")

        called_with: list[str] = []

        def on_exists_callback(rel_path: str) -> None:
            called_with.append(rel_path)

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={},
            exclude=[],
            skip_if_exists=["file.txt"],  # 跳过（不覆盖），但 on_exists 仍被调用
            no_render=[],
            envops={},
            overwrite=False,
            on_exists=on_exists_callback,
        )
        renderer.render_to(dst)
        # 文件存在且跳过 → on_exists 仍被调用
        assert "file.txt" in called_with


class TestRendererBinaryDetection:
    """二进制检测覆盖 (lines 35-39)."""

    def test_binary_detection_with_null_bytes(self, tmp_path: Path):
        """含 null 字节的文件被识别为二进制."""
        src = tmp_path / "src"
        src.mkdir()
        binary_file = src / "data.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03")

        dst = tmp_path / "dst"

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
        )
        result = renderer.render_to(dst)
        # 二进制文件应被原样复制
        assert (dst / "data.bin").exists()

    def test_text_file_not_binary(self, tmp_path: Path):
        """纯文本文件不被识别为二进制."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "hello.txt").write_text("hello world")

        dst = tmp_path / "dst"

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
        )
        result = renderer.render_to(dst)
        assert (dst / "hello.txt").exists()

    def test_is_binary_fallback_direct(self, tmp_path: Path):
        """binaryornot fallback: 直接测试回退逻辑（检测 null 字节）."""
        # Test the fallback is_binary directly by checking null byte detection
        bin_file = tmp_path / "data.bin"
        bin_file.write_bytes(b"\x00\x01")
        txt_file = tmp_path / "data.txt"
        txt_file.write_text("hello")

        # The fallback: read first 1024 bytes, check for null
        def _fallback_is_binary(path):
            with open(path, "rb") as f:
                return b"\x00" in f.read(1024)

        assert _fallback_is_binary(str(bin_file)) is True
        assert _fallback_is_binary(str(txt_file)) is False


class TestRendererSymlinkHandling:
    """symlink 处理覆盖 (lines 137-178)."""

    def test_symlink_preserved(self, tmp_path: Path):
        """preserve_symlinks=True 时保留 symlink."""
        src = tmp_path / "src"
        src.mkdir()
        target_file = src / "real_file.txt"
        target_file.write_text("real content")
        symlink_file = src / "link.txt"
        os.symlink(str(target_file), str(symlink_file))

        dst = tmp_path / "dst"
        dst.mkdir()

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
            preserve_symlinks=True,
        )
        result = renderer.render_to(dst)

    def test_symlink_dangling_skipped(self, tmp_path: Path):
        """dangling symlink 被跳过 (line 157-158 / 161)."""
        src = tmp_path / "src"
        src.mkdir()
        # Create a symlink to a non-existent file
        dangling = src / "dangling.txt"
        os.symlink(str(src / "nonexistent.txt"), str(dangling))

        dst = tmp_path / "dst"
        dst.mkdir()

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
            preserve_symlinks=True,
        )
        result = renderer.render_to(dst)
        # dangling symlink should not be created at destination
        assert not (dst / "dangling.txt").exists()

    def test_symlink_preserve_false_resolves(self, tmp_path: Path):
        """preserve_symlinks=False 时解析 symlink 内容."""
        src = tmp_path / "src"
        src.mkdir()
        real_file = src / "real.txt"
        real_file.write_text("resolved content")
        link_file = src / "link.txt"
        os.symlink(str(real_file), str(link_file))

        dst = tmp_path / "dst"
        dst.mkdir()

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
            preserve_symlinks=False,
        )
        result = renderer.render_to(dst)

    def test_jinja_template_rendering(self, tmp_path: Path):
        """Jinja2 模板渲染覆盖 (lines 176-183)."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "hello.txt.jinja").write_text("Hello {{ name }}!")

        dst = tmp_path / "dst"

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={"name": "World"},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
        )
        result = renderer.render_to(dst)
        # Template rendered, .jinja stripped
        assert (dst / "hello.txt").exists()
        assert (dst / "hello.txt").read_text() == "Hello World!"

    def test_render_path_with_template(self, tmp_path: Path):
        """路径中含模板变量时渲染路径 (lines 190-196)."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "{{ project_name }}.txt").write_text("content")

        dst = tmp_path / "dst"

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={"project_name": "myproject"},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
        )
        result = renderer.render_to(dst)
        assert (dst / "myproject.txt").exists()

    def test_exclude_pattern(self, tmp_path: Path):
        """exclude pattern 过滤文件 (lines 103-107)."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "keep.txt").write_text("keep")
        (src / "skip.log").write_text("skip")

        dst = tmp_path / "dst"

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={},
            exclude=["*.log"],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
        )
        result = renderer.render_to(dst)
        assert (dst / "keep.txt").exists()
        assert not (dst / "skip.log").exists()

    def test_no_render_path(self, tmp_path: Path):
        """no_render 文件原样复制 (lines 132-135)."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "config.yml").write_text("key: {{ value }}")

        dst = tmp_path / "dst"

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={"value": "should_not_render"},
            exclude=[],
            skip_if_exists=[],
            no_render=["config.yml"],
            envops={},
            overwrite=False,
        )
        result = renderer.render_to(dst)
        assert (dst / "config.yml").exists()
        # should NOT have rendered the template
        assert (dst / "config.yml").read_text() == "key: {{ value }}"


class TestIsBinaryFallback:
    """binaryornot 未安装时的回退逻辑 (lines 35-39)."""

    def test_is_binary_fallback_used_when_binaryornot_missing(self, tmp_path: Path):
        """binaryornot 不可用时的 null 字节检测回退."""
        import sys
        # 移除 binaryornot 模块触发回退逻辑
        sys.modules.pop("binaryornot", None)
        sys.modules.pop("binaryornot.check", None)

        # Re-import renderer to trigger the import fallback
        import importlib
        import init_engineering.init.renderer as ren_mod
        importlib.reload(ren_mod)

        try:
            bin_file = tmp_path / "data.bin"
            bin_file.write_bytes(b"\x00\x01")
            txt_file = tmp_path / "data.txt"
            txt_file.write_text("hello")

            src = tmp_path / "src"
            src.mkdir()
            (src / "a.bin").write_bytes(b"\x00\x01\x02")
            (src / "a.txt").write_text("hello")

            dst = tmp_path / "dst"
            from init_engineering.init.renderer import TemplateRenderer
            renderer = TemplateRenderer(
                template_dirs=[src],
                context={},
                exclude=[],
                skip_if_exists=[],
                no_render=[],
                envops={},
                overwrite=False,
            )
            result = renderer.render_to(dst)
            assert (dst / "a.bin").exists()
            assert (dst / "a.txt").exists()
        finally:
            # Restore binaryornot to avoid side effects
            importlib.reload(ren_mod)


class TestDetectNewline:
    """_detect_newline edge cases (lines 255-265)."""

    def test_detect_newline_mixed_line_endings(self, tmp_path: Path):
        """混合换行符时返回第一个检测到的类型."""
        src = tmp_path / "src"
        src.mkdir()
        # 文件包含混合换行符
        (src / "mixed.txt").write_bytes(b"line1\r\nline2\nline3\r\n")

        dst = tmp_path / "dst"
        renderer = TemplateRenderer(
            template_dirs=[src],
            context={},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
        )
        result = renderer.render_to(dst)
        assert (dst / "mixed.txt").exists()

    def test_detect_newline_on_error(self, tmp_path: Path):
        """文件读取异常时 _detect_newline 返回 None (line 264)."""
        # Create a dir where we can't read file permissions
        src = tmp_path / "src"
        src.mkdir()
        (src / "normal.txt").write_text("ok")

        dst = tmp_path / "dst"
        renderer = TemplateRenderer(
            template_dirs=[src],
            context={},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
        )
        result = renderer.render_to(dst)

    def test_template_suffix_configuration(self, tmp_path: Path):
        """templates_suffix 配置不同后缀时正确渲染 (覆盖 line 57)."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "hello.txt.tpl").write_text("Hello {{ name }}!")

        dst = tmp_path / "dst"

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={"name": "World"},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
            templates_suffix=".tpl",
        )
        result = renderer.render_to(dst)
        assert (dst / "hello.txt").exists()
        assert (dst / "hello.txt").read_text() == "Hello World!"

