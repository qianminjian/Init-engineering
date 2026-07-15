"""CLI commands 单元测试.

覆盖:
- cmd_list_types / cmd_list_templates (v5.5: 提升为独立命令)
- cmd_analyze (v5.5: 提升为独立命令 ae analyze)
- ConflictStrategy enum
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from init_engineering.cli._list_cmds import cmd_analyze, cmd_list_templates, cmd_list_types
from init_engineering.init.scaffold_update import ConflictStrategy


class TestListTypes:
    """cmd_list_types — ae list-types 命令."""

    def test_lists_available_types(self, tmp_path: Path, capsys):
        """列出 templates/ 下所有非 _ 开头的目录."""
        (tmp_path / "app-service").mkdir()
        (tmp_path / "cli-tool").mkdir()
        (tmp_path / "_shared").mkdir()  # should be excluded

        cmd_list_types(tmp_path)
        captured = capsys.readouterr()
        assert "app-service" in captured.out
        assert "cli-tool" in captured.out
        assert "_shared" not in captured.out

    def test_cli_list_types_command(self):
        """ae list-types CLI 命令正常执行."""
        runner = CliRunner()
        from init_engineering.cli import main
        result = runner.invoke(main, ["list-types"])
        assert result.exit_code == 0
        assert "app-service" in result.output or "cli-tool" in result.output


class TestListTemplates:
    """cmd_list_templates — ae list-templates 命令."""

    def test_lists_files_by_type(self, tmp_path: Path, capsys):
        """列出每个类型的模板文件."""
        type_dir = tmp_path / "app-service"
        type_dir.mkdir()
        (type_dir / "README.md.jinja").write_text("")

        cmd_list_templates(tmp_path)
        captured = capsys.readouterr()
        assert "[app-service]" in captured.out
        assert "README.md.jinja" in captured.out

    def test_excludes_hidden_files(self, tmp_path: Path, capsys):
        """隐藏文件 (. 开头) 不在列表中."""
        type_dir = tmp_path / "cli-tool"
        type_dir.mkdir()
        (type_dir / "main.py.jinja").write_text("")
        (type_dir / ".hidden").write_text("")

        cmd_list_templates(tmp_path)
        captured = capsys.readouterr()
        assert "main.py.jinja" in captured.out
        assert ".hidden" not in captured.out

    def test_cli_list_templates_command(self):
        """ae list-templates CLI 命令正常执行."""
        runner = CliRunner()
        from init_engineering.cli import main
        result = runner.invoke(main, ["list-templates"])
        assert result.exit_code == 0


class TestCmdAnalyze:
    """cmd_analyze — ae analyze 命令."""

    def test_analyze_empty_dir(self, tmp_path: Path, capsys):
        """空目录分析."""
        project = tmp_path / "empty"
        project.mkdir()

        from init_engineering.init.detector import ProjectDetector

        cmd_analyze(project, ProjectDetector)
        captured = capsys.readouterr()
        assert "分析目录" in captured.out

    def test_analyze_python_project(self, tmp_path: Path, capsys):
        """Python 项目检测."""
        project = tmp_path / "pyproj"
        project.mkdir()
        (project / "pyproject.toml").write_text("[project]\nname = 'test'")

        from init_engineering.init.detector import ProjectDetector

        cmd_analyze(project, ProjectDetector)
        captured = capsys.readouterr()
        assert "分析目录" in captured.out
        assert "Python" in captured.out or "python" in captured.out or "语言" in captured.out

    def test_analyze_with_type_override(self, tmp_path: Path, capsys):
        """P1: --type 与 analyze 同用时传参不崩溃."""
        project = tmp_path / "simple"
        project.mkdir()
        (project / ".claude-plugin").mkdir()

        from init_engineering.init.detector import ProjectDetector

        cmd_analyze(project, ProjectDetector, project_type="plugin")
        captured = capsys.readouterr()
        assert "分析目录" in captured.out

    def test_analyze_with_type_disambiguates_multi_candidates(self, tmp_path: Path, capsys):
        """P1: 多候选时 --type 可消歧义，显示 '使用 --type 指定类型'."""
        project = tmp_path / "multi"
        project.mkdir()
        (project / "pom.xml").write_text(
            "<project><modelVersion>4.0.0</modelVersion>"
            "<groupId>com.example</groupId>"
            "<artifactId>test</artifactId>"
            "<version>1.0</version></project>"
        )

        from init_engineering.init.detector import ProjectDetector

        cmd_analyze(project, ProjectDetector, project_type="library")
        captured = capsys.readouterr()
        assert "使用 --type 指定类型: library" in captured.out

    def test_cli_analyze_command(self, tmp_path: Path):
        """ae analyze CLI 命令正常执行."""
        project = tmp_path / "proj"
        project.mkdir()
        (project / "pyproject.toml").write_text("[project]\nname = 'test'")

        runner = CliRunner()
        from init_engineering.cli import main
        result = runner.invoke(main, ["analyze", str(project)])
        assert result.exit_code == 0
        assert "分析目录" in result.output

    def test_cli_analyze_nonexistent_dir(self):
        """ae analyze 不存在的目录报错."""
        runner = CliRunner()
        from init_engineering.cli import main
        result = runner.invoke(main, ["analyze", "/nonexistent/path/xyz"])
        assert result.exit_code != 0


class TestLegacyBackwardCompat:
    """v5.5: 向后兼容 — init 上的 --list-types/--list-templates/--analyze 仍可用但会 warning."""

    def test_legacy_list_types_on_init(self, tmp_path: Path):
        """ae init --list-types 仍然可用（deprecated warning）."""
        runner = CliRunner()
        from init_engineering.cli import main
        result = runner.invoke(main, ["init", "--list-types"])
        assert result.exit_code == 0
        assert "已废弃" in result.output

    def test_legacy_analyze_on_init(self, tmp_path: Path):
        """ae init --analyze <path> 仍然可用（deprecated warning）."""
        project = tmp_path / "proj"
        project.mkdir()
        runner = CliRunner()
        from init_engineering.cli import main
        result = runner.invoke(main, ["init", "--analyze", str(project)])
        assert result.exit_code == 0
        assert "已废弃" in result.output


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
