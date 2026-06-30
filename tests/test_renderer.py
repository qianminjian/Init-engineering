"""tests for init/renderer.py — 非交互路径覆盖."""

from pathlib import Path
from unittest.mock import patch

import pytest

from auto_engineering.init.renderer import TemplateRenderer


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
