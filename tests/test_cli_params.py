"""CLI 参数测试 — v5.5 精简后.

v5.5 移除的 CLI 选项:
- --templates-suffix / --preserve-symlinks (内部 API 保留，CLI 不暴露)
- --hook-timeout / --force-unsafe-template / --telemetry
"""

from pathlib import Path

import pytest
from click.testing import CliRunner


_runner = CliRunner()


class TestRemovedCliOptions:
    """v5.5: 确认已移除的选项不出现在 --help 中."""

    def test_help_does_not_show_templates_suffix(self):
        """--templates-suffix 已从 CLI 移除."""
        from init_engineering.cli import init
        result = _runner.invoke(init, ["--help"])
        assert result.exit_code == 0
        assert "--templates-suffix" not in result.output

    def test_help_does_not_show_preserve_symlinks(self):
        """--preserve-symlinks 已从 CLI 移除."""
        from init_engineering.cli import init
        result = _runner.invoke(init, ["--help"])
        assert result.exit_code == 0
        assert "--preserve-symlinks" not in result.output

    def test_help_does_not_show_hook_timeout(self):
        """--hook-timeout 已从 CLI 移除."""
        from init_engineering.cli import init
        result = _runner.invoke(init, ["--help"])
        assert result.exit_code == 0
        assert "--hook-timeout" not in result.output

    def test_help_does_not_show_telemetry(self):
        """--telemetry 已从 CLI 移除."""
        from init_engineering.cli import init
        result = _runner.invoke(init, ["--help"])
        assert result.exit_code == 0
        assert "--telemetry" not in result.output

    def test_new_standalone_commands_exist(self):
        """ae analyze / list-types / list-templates 作为独立命令存在."""
        from init_engineering.cli import main
        result = _runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "analyze" in result.output
        assert "list-types" in result.output
        assert "list-templates" in result.output

    def test_analyze_command_has_help(self):
        """ae analyze --help 正常显示."""
        from init_engineering.cli import main
        result = _runner.invoke(main, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "分析存量项目" in result.output
        assert "--include-hidden" in result.output


class TestInitWorkerInternalParams:
    """InitWorker 内部 API 保留 templates_suffix / preserve_symlinks（不通过 CLI 暴露）."""

    def test_initworker_accepts_templates_suffix_param(self):
        """InitWorker.__init__ 仍接受 templates_suffix 参数（内部 API）."""
        from init_engineering.init.scaffold_phases import InitWorker

        with InitWorker(
            dst_path=Path("/tmp/test"),
            project_type="app-service",
            templates_suffix=".j2",
        ) as worker:
            assert worker.templates_suffix == ".j2"

    def test_initworker_accepts_preserve_symlinks_param(self):
        """InitWorker.__init__ 仍接受 preserve_symlinks 参数（内部 API）."""
        from init_engineering.init.scaffold_phases import InitWorker

        with InitWorker(
            dst_path=Path("/tmp/test"),
            project_type="app-service",
            preserve_symlinks=False,
        ) as worker:
            assert worker.preserve_symlinks is False
