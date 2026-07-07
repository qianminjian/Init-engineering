"""CLI commands 单元测试 (P1-12).

覆盖 commands.py 和 subcommands.py 的纯函数路径：
- _cmd_list_types / _cmd_list_templates
- _cmd_analyze
- cmd_init 早返回分支 (--list-types / --list-templates / --analyze)
- ConflictStrategy enum
"""

from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from init_engineering.cli.commands import _cmd_analyze, _cmd_list_templates, _cmd_list_types, cmd_init
from init_engineering.cli.subcommands import update as _cli_update
from init_engineering.init.scaffold_update import ConflictStrategy


class TestListTypes:
    """_cmd_list_types — --list-types 分支."""

    def test_lists_available_types(self, tmp_path: Path, capsys):
        """列出 templates/ 下所有非 _ 开头的目录."""
        (tmp_path / "app-service").mkdir()
        (tmp_path / "cli-tool").mkdir()
        (tmp_path / "_shared").mkdir()  # should be excluded

        _cmd_list_types(tmp_path)
        captured = capsys.readouterr()
        assert "app-service" in captured.out
        assert "cli-tool" in captured.out
        assert "_shared" not in captured.out


class TestListTemplates:
    """_cmd_list_templates — --list-templates 分支."""

    def test_lists_files_by_type(self, tmp_path: Path, capsys):
        """列出每个类型的模板文件."""
        type_dir = tmp_path / "app-service"
        type_dir.mkdir()
        (type_dir / "README.md.jinja").write_text("")

        _cmd_list_templates(tmp_path)
        captured = capsys.readouterr()
        assert "[app-service]" in captured.out
        assert "README.md.jinja" in captured.out

    def test_excludes_hidden_files(self, tmp_path: Path, capsys):
        """隐藏文件 (. 开头) 不在列表中."""
        type_dir = tmp_path / "cli-tool"
        type_dir.mkdir()
        (type_dir / "main.py.jinja").write_text("")
        (type_dir / ".hidden").write_text("")

        _cmd_list_templates(tmp_path)
        captured = capsys.readouterr()
        assert "main.py.jinja" in captured.out
        assert ".hidden" not in captured.out


class TestCmdAnalyze:
    """_cmd_analyze — --analyze 分支."""

    def test_analyze_empty_dir(self, tmp_path: Path, capsys):
        """空目录分析."""
        project = tmp_path / "empty"
        project.mkdir()

        from init_engineering.init.detector import ProjectDetector

        _cmd_analyze(project, ProjectDetector)
        captured = capsys.readouterr()
        assert "分析目录" in captured.out

    def test_analyze_python_project(self, tmp_path: Path, capsys):
        """Python 项目检测."""
        project = tmp_path / "pyproj"
        project.mkdir()
        (project / "pyproject.toml").write_text("[project]\nname = 'test'")

        from init_engineering.init.detector import ProjectDetector

        _cmd_analyze(project, ProjectDetector)
        captured = capsys.readouterr()
        assert "分析目录" in captured.out
        # Should detect language or package manager
        assert "Python" in captured.out or "python" in captured.out or "语言" in captured.out


class TestCmdInitEarlyReturn:
    """cmd_init 早返回分支."""

    def test_list_types_early_return(self, tmp_path: Path):
        """--list-types 应该早返回不执行 init."""
        (tmp_path / "templates" / "app-service").mkdir(parents=True)

        from init_engineering.init.config_types import TEMPLATES_ROOT

        result = cmd_init(
            project=None,
            project_type=None,
            defaults=False,
            force=False,
            answers_file=None,
            language=None,
            package_manager=None,
            ci_platform=None,
            test_runner=None,
            use_typescript=None,
            use_lefthook=None,
            use_docker=None,
            pretend=False,
            skip_tasks=False,
            no_install=False,
            cleanup_on_error=True,
            quiet=True,
            verbose=False,
            incremental=False,
            strict=False,
            analyze_only=False,
            telemetry=False,
            list_types=True,
            list_templates=False,
            templates_suffix=None,
            preserve_symlinks=None,
            template_dir_override=None,
            hook_timeout=None,
            force_unsafe_template=False,
        )
        assert result is None  # early return

    def test_analyze_only_early_return(self, tmp_path: Path):
        """--analyze 应该早返回不执行 init."""
        project = tmp_path / "proj"
        project.mkdir()

        result = cmd_init(
            project=str(project),
            project_type=None,
            defaults=False,
            force=False,
            answers_file=None,
            language=None,
            package_manager=None,
            ci_platform=None,
            test_runner=None,
            use_typescript=None,
            use_lefthook=None,
            use_docker=None,
            pretend=False,
            skip_tasks=False,
            no_install=False,
            cleanup_on_error=True,
            quiet=True,
            verbose=False,
            incremental=False,
            strict=False,
            analyze_only=True,
            telemetry=False,
            list_types=False,
            list_templates=False,
            templates_suffix=None,
            preserve_symlinks=None,
            template_dir_override=None,
            hook_timeout=None,
            force_unsafe_template=False,
        )
        assert result is None  # early return


class TestConflictStrategy:
    """ConflictStrategy enum."""

    def test_enum_values(self):
        assert ConflictStrategy.SKIP.value == "skip"
        assert ConflictStrategy.OVERWRITE.value == "overwrite"
        assert ConflictStrategy.PROMPT.value == "prompt"

    def test_from_string(self):
        assert ConflictStrategy("skip") == ConflictStrategy.SKIP
        assert ConflictStrategy("overwrite") == ConflictStrategy.OVERWRITE

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValueError):
            ConflictStrategy("invalid")
