"""Performance benchmark tests — 大规模模板渲染基准.

P3 audit finding: 无大规模模板渲染基准
验证: 100+ 模板文件渲染在 5s 内完成
"""

import time
import string
from pathlib import Path

import pytest

from init_engineering.init.renderer import TemplateRenderer


class TestRenderingBenchmark:
    """100+ 模板渲染性能基准."""

    def test_100_templates_render_under_5s(self, tmp_path: Path):
        """渲染 100 个模板文件应在 5 秒内完成."""
        src = tmp_path / "src"
        src.mkdir()

        # 生成 100 个模板文件，含 Jinja2 变量
        for i in range(100):
            tmpl = src / f"file_{i:03d}.txt.jinja"
            tmpl.write_text(f"Hello {{ name }}, this is file {i:03d}!")

        # 生成 10 个含模板变量的路径
        for i in range(10):
            dir_with_template = src / f"project_{{ name }}_{i:02d}"
            dir_with_template.mkdir()
            (dir_with_template / "readme.md").write_text(f"README for variant {i}")

        dst = tmp_path / "dst"

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={"name": "benchmark"},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
        )

        start = time.perf_counter()
        result = renderer.render_to(dst)
        elapsed = time.perf_counter() - start

        file_count = len(result)
        assert file_count >= 100, f"Expected >= 100 rendered files, got {file_count}"
        assert elapsed < 5.0, f"Rendering {file_count} files took {elapsed:.3f}s (limit: 5.0s)"

    def test_deep_nested_rendering_performance(self, tmp_path: Path):
        """深度嵌套目录（5 层 × 5 文件/层）渲染基准."""
        src = tmp_path / "src"
        src.mkdir()

        # 构建深度嵌套: a/b/c/d/e/, 每层 5 模板文件
        current = src
        for depth, letter in enumerate(string.ascii_lowercase[:5]):
            current = current / letter
            current.mkdir()
            for i in range(5):
                (current / f"tmpl_{i}.txt.jinja").write_text(f"Depth {depth}, file {i}: {{ name }}")

        dst = tmp_path / "dst"

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={"name": "deep"},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
        )

        start = time.perf_counter()
        result = renderer.render_to(dst)
        elapsed = time.perf_counter() - start

        assert len(result) == 25  # 5 layers × 5 files
        assert elapsed < 2.0, f"Deep nested rendering took {elapsed:.3f}s (limit: 2.0s)"

    def test_template_dir_priority_rendering(self, tmp_path: Path):
        """多 source 模板目录（_shared + features + type_dir）渲染基准.

        模拟 build_template_dirs 产出的真实目录结构.
        """
        _shared = tmp_path / "_shared"
        _shared.mkdir()
        for i in range(20):
            (_shared / f"shared_{i:03d}.txt.jinja").write_text(f"Shared {i}: {{ name }}")

        feature = tmp_path / "_features" / "typescript"
        feature.mkdir(parents=True)
        for i in range(15):
            (feature / f"feature_{i:03d}.txt.jinja").write_text(f"Feature {i}: {{ name }}")

        type_dir = tmp_path / "app-service"
        type_dir.mkdir()
        for i in range(15):
            (type_dir / f"type_{i:03d}.txt.jinja").write_text(f"Type {i}: {{ name }}")

        dst = tmp_path / "dst"

        renderer = TemplateRenderer(
            template_dirs=[_shared, feature, type_dir],
            context={"name": "multi"},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
        )

        start = time.perf_counter()
        result = renderer.render_to(dst)
        elapsed = time.perf_counter() - start

        assert len(result) == 50  # 20 + 15 + 15
        assert elapsed < 3.0, f"Multi-source rendering took {elapsed:.3f}s (limit: 3.0s)"

    def test_binary_files_mixed_with_templates(self, tmp_path: Path):
        """混合二进制文件 + 模板文件的渲染基准."""
        src = tmp_path / "src"
        src.mkdir()

        # 50 个文本模板 + 50 个二进制文件
        for i in range(50):
            (src / f"tmpl_{i:03d}.txt.jinja").write_text(f"Template {i}: {{ name }}")
            (src / f"binary_{i:03d}.png").write_bytes(bytes(range(min(i, 256))))

        dst = tmp_path / "dst"

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={"name": "mixed"},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
        )

        start = time.perf_counter()
        result = renderer.render_to(dst)
        elapsed = time.perf_counter() - start

        assert len(result) == 100
        assert elapsed < 5.0, f"Mixed binary+template rendering took {elapsed:.3f}s (limit: 5.0s)"

    def test_overwrite_performance_regression(self, tmp_path: Path):
        """覆盖模式性能回归 — 先创建再覆盖 100 文件."""
        src = tmp_path / "src"
        src.mkdir()
        for i in range(100):
            (src / f"file_{i:03d}.txt.jinja").write_text(f"v2: {{ name }} file {i}")

        dst = tmp_path / "dst"
        dst.mkdir()
        # Pre-populate destination with old versions
        for i in range(100):
            (dst / f"file_{i:03d}.txt").write_text(f"v1: old file {i}")

        renderer = TemplateRenderer(
            template_dirs=[src],
            context={"name": "overwrite"},
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=True,
        )

        start = time.perf_counter()
        result = renderer.render_to(dst)
        elapsed = time.perf_counter() - start

        assert len(result) == 100
        assert elapsed < 5.0, f"Overwrite rendering took {elapsed:.3f}s (limit: 5.0s)"


class TestBuildTemplateDirsPerformance:
    """build_template_dirs 性能基准."""

    def test_build_template_dirs_performance(self, tmp_path: Path):
        """build_template_dirs 应在 50ms 内完成."""
        from init_engineering.init.scaffold_render import build_template_dirs

        type_dir = Path(__file__).parent.parent / "src" / "init_engineering" / "init" / "templates" / "app-service"

        start = time.perf_counter()
        dirs = build_template_dirs(
            {"language": "typescript", "use_docker": True, "ci_platform": "github"},
            type_dir,
        )
        elapsed = time.perf_counter() - start

        assert len(dirs) >= 4
        assert elapsed < 0.05, f"build_template_dirs took {elapsed*1000:.1f}ms (limit: 50ms)"
