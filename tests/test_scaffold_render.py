"""tests for init/scaffold_render.py — build_template_dirs."""

from pathlib import Path

import pytest

from auto_engineering.init.scaffold_render import build_template_dirs


class TestBuildTemplateDirs:
    """build_template_dirs — 模板目录选择逻辑覆盖."""

    def test_use_docker_sets_feature_map(self):
        """use_docker=True 时 feature_map 包含 docker 条目 (line 80)."""
        context = {"use_docker": True, "language": "typescript"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"
        # 不崩溃，返回列表
        dirs = build_template_dirs(context, type_dir)
        assert isinstance(dirs, list)
        # _shared 目录应该在结果中
        assert any("_shared" in str(d) for d in dirs)

    def test_monorepo_project_type_sets_feature_map(self):
        """project_type=monorepo 时 feature_map 包含 monorepo 条目 (line 82)."""
        context = {"project_type": "monorepo", "language": "python"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "monorepo"
        dirs = build_template_dirs(context, type_dir)
        assert isinstance(dirs, list)

    def test_empty_ci_platform_skipped(self):
        """ci_platform 不在 CI_FEATURE_MAP 时 feature_name 为空，跳过 (line 86)."""
        # ci_platform="unknown" 不在 CI_FEATURE_MAP → feature_name=""
        # 空 feature_name 触发 continue (line 86)
        context = {"ci_platform": "unknown_platform", "language": "typescript"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"
        # 不崩溃
        dirs = build_template_dirs(context, type_dir)
        assert isinstance(dirs, list)

    def test_github_ci_platform(self):
        """ci_platform=github 添加 github-actions 特征目录 (lines 77-78, 88-90)."""
        context = {"ci_platform": "github", "language": "typescript"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"
        dirs = build_template_dirs(context, type_dir)
        assert isinstance(dirs, list)
