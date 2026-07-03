"""P1-4 + P1-5: TemplateConfig preserve_symlinks + templates_suffix 透传测试.

验证:
1. TemplateConfig dataclass 有 preserve_symlinks 和 templates_suffix 字段
2. config_loader.load_template_config() 正确加载这两个字段
3. InitWorker._phase_render() 将这两个字段透传给 render_to()
4. render_to() 将这两个参数传给 TemplateRenderer
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from init_engineering.init.config import TemplateConfig
from init_engineering.init.config_loader import load_template_config
from init_engineering.init.scaffold_phases import InitWorker
from init_engineering.init.scaffold_render import render_to


class TestTemplateConfigFields:
    """Task 1-2: TemplateConfig 有 preserve_symlinks 和 templates_suffix 字段."""

    def test_template_config_has_preserve_symlinks_field(self) -> None:
        """TemplateConfig dataclass 有 preserve_symlinks: bool 字段, 默认 True."""
        cfg = TemplateConfig(template_dir=Path("."))
        assert hasattr(cfg, "preserve_symlinks")
        assert isinstance(cfg.preserve_symlinks, bool)
        assert cfg.preserve_symlinks is True

    def test_template_config_has_templates_suffix_field(self) -> None:
        """TemplateConfig dataclass 有 templates_suffix: str 字段, 默认 .jinja."""
        from init_engineering.init.config_types import DEFAULT_TEMPLATES_SUFFIX

        cfg = TemplateConfig(template_dir=Path("."))
        assert hasattr(cfg, "templates_suffix")
        assert isinstance(cfg.templates_suffix, str)
        assert cfg.templates_suffix == DEFAULT_TEMPLATES_SUFFIX
        assert cfg.templates_suffix == ".jinja"


class TestConfigLoaderLoadsFields:
    """Task 3: config_loader 正确加载 preserve_symlinks 和 templates_suffix."""

    def test_config_loader_loads_preserve_symlinks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_template_config 能从 _preserve_symlinks: false 加载."""
        template_dir = tmp_path / "templates" / "mytype"
        template_dir.mkdir(parents=True)
        (template_dir / "ae-template.yml").write_text(
            textwrap.dedent("""\
                _preserve_symlinks: false
                project_name:
                  default: my-project
            """)
        )
        from init_engineering.init import config_loader

        monkeypatch.setattr(config_loader, "TEMPLATES_ROOT", tmp_path / "templates")
        cfg = load_template_config("mytype")
        assert cfg.preserve_symlinks is False

    def test_config_loader_loads_templates_suffix(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_template_config 能从 _templates_suffix: ".tmpl" 加载."""
        template_dir = tmp_path / "templates" / "mytype"
        template_dir.mkdir(parents=True)
        (template_dir / "ae-template.yml").write_text(
            textwrap.dedent("""\
                _templates_suffix: ".tmpl"
                project_name:
                  default: my-project
            """)
        )
        from init_engineering.init import config_loader

        monkeypatch.setattr(config_loader, "TEMPLATES_ROOT", tmp_path / "templates")
        cfg = load_template_config("mytype")
        assert cfg.templates_suffix == ".tmpl"

    def test_config_loader_preserves_default_preserve_symlinks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """未指定 _preserve_symlinks 时, 默认保留 True."""
        template_dir = tmp_path / "templates" / "mytype"
        template_dir.mkdir(parents=True)
        (template_dir / "ae-template.yml").write_text(
            textwrap.dedent("""\
                project_name:
                  default: my-project
            """)
        )
        from init_engineering.init import config_loader

        monkeypatch.setattr(config_loader, "TEMPLATES_ROOT", tmp_path / "templates")
        cfg = load_template_config("mytype")
        assert cfg.preserve_symlinks is True

    def test_config_loader_preserves_default_templates_suffix(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """未指定 _templates_suffix 时, 默认使用 .jinja."""
        template_dir = tmp_path / "templates" / "mytype"
        template_dir.mkdir(parents=True)
        (template_dir / "ae-template.yml").write_text(
            textwrap.dedent("""\
                project_name:
                  default: my-project
            """)
        )
        from init_engineering.init import config_loader

        monkeypatch.setattr(config_loader, "TEMPLATES_ROOT", tmp_path / "templates")
        cfg = load_template_config("mytype")
        assert cfg.templates_suffix == ".jinja"


class TestRenderToReceivesFields:
    """Task 4-6: render_to() 接收 preserve_symlinks 和 templates_suffix."""

    def test_render_to_receives_preserve_symlinks_from_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TemplateConfig.preserve_symlinks 透传到 TemplateRenderer."""
        template_dir = tmp_path / "templates" / "mytype"
        template_dir.mkdir(parents=True)
        (template_dir / "ae-template.yml").write_text(
            textwrap.dedent("""\
                _preserve_symlinks: false
                project_name:
                  default: my-project
            """)
        )
        from init_engineering.init import config_loader

        monkeypatch.setattr(config_loader, "TEMPLATES_ROOT", tmp_path / "templates")
        cfg = load_template_config("mytype")
        assert cfg.preserve_symlinks is False

        # 验证 InitWorker._phase_render 透传逻辑
        # CLI 参数优先, 否则用 TemplateConfig 值
        with patch.object(
            InitWorker,
            "_phase_detect",
            return_value=None,
        ), patch.object(
            InitWorker,
            "_phase_prompt",
            return_value=None,
        ), patch.object(
            InitWorker,
            "_check_template_version",
            return_value=None,
        ), patch(
            "init_engineering.init.scaffold_phase_funcs._render_to"
        ) as mock_render:
            mock_render.return_value = []
            worker = InitWorker(
                dst_path=tmp_path / "project",
                project_type="mytype",
                defaults=True,
            )
            worker._template = cfg
            worker._answers = worker._answers
            worker._phase_render(tmp_path / "tmp")
            call_kwargs = mock_render.call_args.kwargs
            assert call_kwargs["preserve_symlinks"] is False

    def test_render_to_receives_templates_suffix_from_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TemplateConfig.templates_suffix 透传到 TemplateRenderer."""
        template_dir = tmp_path / "templates" / "mytype"
        template_dir.mkdir(parents=True)
        (template_dir / "ae-template.yml").write_text(
            textwrap.dedent("""\
                _templates_suffix: ".tmpl"
                project_name:
                  default: my-project
            """)
        )
        from init_engineering.init import config_loader

        monkeypatch.setattr(config_loader, "TEMPLATES_ROOT", tmp_path / "templates")
        cfg = load_template_config("mytype")
        assert cfg.templates_suffix == ".tmpl"

        with patch.object(
            InitWorker,
            "_phase_detect",
            return_value=None,
        ), patch.object(
            InitWorker,
            "_phase_prompt",
            return_value=None,
        ), patch.object(
            InitWorker,
            "_check_template_version",
            return_value=None,
        ), patch(
            "init_engineering.init.scaffold_phase_funcs._render_to"
        ) as mock_render:
            mock_render.return_value = []
            worker = InitWorker(
                dst_path=tmp_path / "project",
                project_type="mytype",
                defaults=True,
            )
            worker._template = cfg
            worker._answers = worker._answers
            worker._phase_render(tmp_path / "tmp")
            call_kwargs = mock_render.call_args.kwargs
            assert call_kwargs["templates_suffix"] == ".tmpl"

    def test_render_to_cli_override_preserve_symlinks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI 参数 preserve_symlinks 优先于 TemplateConfig 值."""
        template_dir = tmp_path / "templates" / "mytype"
        template_dir.mkdir(parents=True)
        (template_dir / "ae-template.yml").write_text(
            textwrap.dedent("""\
                _preserve_symlinks: false
                project_name:
                  default: my-project
            """)
        )
        from init_engineering.init import config_loader

        monkeypatch.setattr(config_loader, "TEMPLATES_ROOT", tmp_path / "templates")
        cfg = load_template_config("mytype")
        assert cfg.preserve_symlinks is False

        with patch.object(
            InitWorker,
            "_phase_detect",
            return_value=None,
        ), patch.object(
            InitWorker,
            "_phase_prompt",
            return_value=None,
        ), patch.object(
            InitWorker,
            "_check_template_version",
            return_value=None,
        ), patch(
            "init_engineering.init.scaffold_phase_funcs._render_to"
        ) as mock_render:
            mock_render.return_value = []
            # CLI 传入 preserve_symlinks=True, 应覆盖模板的 false
            worker = InitWorker(
                dst_path=tmp_path / "project",
                project_type="mytype",
                defaults=True,
                preserve_symlinks=True,
            )
            worker._template = cfg
            worker._answers = worker._answers
            worker._phase_render(tmp_path / "tmp")
            call_kwargs = mock_render.call_args.kwargs
            assert call_kwargs["preserve_symlinks"] is True

    def test_render_to_cli_override_templates_suffix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI 参数 templates_suffix 优先于 TemplateConfig 值."""
        template_dir = tmp_path / "templates" / "mytype"
        template_dir.mkdir(parents=True)
        (template_dir / "ae-template.yml").write_text(
            textwrap.dedent("""\
                _templates_suffix: ".tmpl"
                project_name:
                  default: my-project
            """)
        )
        from init_engineering.init import config_loader

        monkeypatch.setattr(config_loader, "TEMPLATES_ROOT", tmp_path / "templates")
        cfg = load_template_config("mytype")
        assert cfg.templates_suffix == ".tmpl"

        with patch.object(
            InitWorker,
            "_phase_detect",
            return_value=None,
        ), patch.object(
            InitWorker,
            "_phase_prompt",
            return_value=None,
        ), patch.object(
            InitWorker,
            "_check_template_version",
            return_value=None,
        ), patch(
            "init_engineering.init.scaffold_phase_funcs._render_to"
        ) as mock_render:
            mock_render.return_value = []
            # CLI 传入 templates_suffix=".custom", 应覆盖模板的 .tmpl
            worker = InitWorker(
                dst_path=tmp_path / "project",
                project_type="mytype",
                defaults=True,
                templates_suffix=".custom",
            )
            worker._template = cfg
            worker._answers = worker._answers
            worker._phase_render(tmp_path / "tmp")
            call_kwargs = mock_render.call_args.kwargs
            assert call_kwargs["templates_suffix"] == ".custom"
