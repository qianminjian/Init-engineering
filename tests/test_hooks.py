"""HookRunner 测试 — 渲染生命周期钩子 (5 类钩子).

TDD RED 阶段：测试应 FAIL 因为 HookRunner 尚未实现。

来源: design/v5.0-Design-Init.md §5.2
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestHookRunnerBeforeRenderer:
    """before_renderer_hook — 渲染开始前调用."""

    def test_hook_runner_before_renderer(self, tmp_path, caplog):
        """before_renderer hook 应在渲染开始前被调用."""
        from auto_engineering.init.hooks import HookRunner, HookSpec

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # HookSpec: before_renderer 返回 Jinja2 模板列表
        spec = HookSpec(
            before_renderer=["echo 'before renderer: {{ project_name }}'"],
            after_renderer=None,
            before_copy_file=None,
            after_copy_file=None,
            on_exists=None,
        )

        runner = HookRunner(project_dir, spec=spec)
        context = {"project_name": "test-project"}

        # Mock subprocess.run at module level
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            runner.before_renderer_hook(context)

        # Verify hook was called
        mock_run.assert_called_once()

    def test_hook_runner_before_renderer_skipped_when_spec_none(self, tmp_path, caplog):
        """before_renderer hook 应在 spec.before_renderer=None 时跳过."""
        from auto_engineering.init.hooks import HookRunner, HookSpec

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        spec = HookSpec()  # all None
        runner = HookRunner(project_dir, spec=spec)
        context = {"project_name": "test-project"}

        with patch("subprocess.run") as mock_run:
            runner.before_renderer_hook(context)

        mock_run.assert_not_called()


class TestHookRunnerAfterRenderer:
    """after_renderer_hook — 渲染结束后调用."""

    def test_hook_runner_after_renderer(self, tmp_path, caplog):
        """after_renderer hook 应在渲染结束后被调用，传入 generated_files."""
        from auto_engineering.init.hooks import HookRunner, HookSpec

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        spec = HookSpec(
            before_renderer=None,
            after_renderer=["echo 'after renderer'"],
            before_copy_file=None,
            after_copy_file=None,
            on_exists=None,
        )

        runner = HookRunner(project_dir, spec=spec)
        context = {"project_name": "test-project"}
        generated_files = [Path("README.md"), Path("CLAUDE.md")]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            runner.after_renderer_hook(context, generated_files)

        mock_run.assert_called_once()


class TestHookRunnerBeforeCopyFile:
    """before_copy_file_hook — 复制单个文件前调用."""

    def test_hook_runner_before_copy_file(self, tmp_path, caplog):
        """before_copy_file hook 应在复制单个文件前被调用."""
        from auto_engineering.init.hooks import HookRunner, HookSpec

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        spec = HookSpec(
            before_renderer=None,
            after_renderer=None,
            before_copy_file=["echo 'before copy'"],
            after_copy_file=None,
            on_exists=None,
        )

        runner = HookRunner(project_dir, spec=spec)
        context = {"project_name": "test-project"}
        src = Path("/template/README.md.jinja")
        dst = Path("/tmp/render/README.md")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            runner.before_copy_file_hook(src, dst, context)

        mock_run.assert_called_once()


class TestHookRunnerAfterCopyFile:
    """after_copy_file_hook — 复制单个文件后调用."""

    def test_hook_runner_after_copy_file(self, tmp_path, caplog):
        """after_copy_file hook 应在复制单个文件后被调用."""
        from auto_engineering.init.hooks import HookRunner, HookSpec

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        spec = HookSpec(
            before_renderer=None,
            after_renderer=None,
            before_copy_file=None,
            after_copy_file=["echo 'after copy'"],
            on_exists=None,
        )

        runner = HookRunner(project_dir, spec=spec)
        context = {"project_name": "test-project"}
        src = Path("/template/README.md.jinja")
        dst = Path("/tmp/render/README.md")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            runner.after_copy_file_hook(src, dst, context)

        mock_run.assert_called_once()


class TestHookRunnerOnExists:
    """on_exists_hook — 目标文件已存在时调用."""

    def test_hook_runner_on_exists(self, tmp_path, caplog):
        """on_exists hook 应在目标文件已存在时被调用."""
        from auto_engineering.init.hooks import HookRunner, HookSpec

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        spec = HookSpec(
            before_renderer=None,
            after_renderer=None,
            before_copy_file=None,
            after_copy_file=None,
            on_exists=["echo 'file exists'"],
        )

        runner = HookRunner(project_dir, spec=spec)
        dst_rel_path = "README.md"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            runner.on_exists_hook(dst_rel_path)

        mock_run.assert_called_once()


class TestHookRunnerNonBlocking:
    """钩子执行失败不应阻断渲染主流程."""

    def test_hook_runner_fails_are_non_blocking(self, tmp_path, caplog):
        """钩子执行失败应 log warning 并继续，不应抛出异常阻断主流程."""
        from auto_engineering.init.hooks import HookRunner, HookSpec

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        spec = HookSpec(
            before_renderer=["exit 1"],  # Simulate hook failure
            after_renderer=None,
            before_copy_file=None,
            after_copy_file=None,
            on_exists=None,
        )

        runner = HookRunner(project_dir, spec=spec)
        context = {"project_name": "test-project"}

        # Should not raise, just log warning
        with caplog.at_level(logging.WARNING):
            runner.before_renderer_hook(context)

        # Non-blocking guarantee: no exception raised


class TestHookSpecDataclass:
    """HookSpec 数据类定义."""

    def test_hook_spec_defaults_to_none(self):
        """HookSpec 所有字段默认应为 None."""
        from auto_engineering.init.hooks import HookSpec

        spec = HookSpec()
        assert spec.before_renderer is None
        assert spec.after_renderer is None
        assert spec.before_copy_file is None
        assert spec.after_copy_file is None
        assert spec.on_exists is None

    def test_hook_spec_accepts_list_values(self):
        """HookSpec 字段应接受 list[str] 值."""
        from auto_engineering.init.hooks import HookSpec

        spec = HookSpec(
            before_renderer=["echo 1", "echo 2"],
            after_renderer=["echo after"],
        )
        assert spec.before_renderer == ["echo 1", "echo 2"]
        assert spec.after_renderer == ["echo after"]
