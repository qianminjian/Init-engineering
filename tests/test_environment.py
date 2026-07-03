"""Tests for config/environment.py — load_ae_answers + preflight + ProjectEnvironment.

覆盖:
    - load_ae_answers: 文件存在/缺失/字段冲突
    - preflight: git/API key/磁盘/Python 版本校验
    - ProjectEnvironment: save/sync/resolve
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from init_engineering.config.environment import (
    ProjectEnvironment,
    load_ae_answers,
    preflight,
)


class TestLoadAeAnswers:
    """load_ae_answers(project_root) — 读 .ae-answers.yml."""

    def test_returns_dict_when_file_exists(self, tmp_path: Path):
        """RED: 存在 .ae-answers.yml 时返回 dict."""
        answers_file = tmp_path / ".ae-answers.yml"
        answers_file.write_text(
            "project_name: test-project\npackage_manager: uv\nuse_typescript: false\n"
        )
        result = load_ae_answers(tmp_path)
        assert result is not None
        assert result["project_name"] == "test-project"
        assert result["package_manager"] == "uv"
        assert result["use_typescript"] is False

    def test_returns_none_when_file_missing(self, tmp_path: Path):
        """RED: .ae-answers.yml 不存在时返回 None."""
        result = load_ae_answers(tmp_path)
        assert result is None

    def test_strips_meta_block(self, tmp_path: Path):
        """RED: _meta 块不参与字段合并,作为元数据保留."""
        answers_file = tmp_path / ".ae-answers.yml"
        answers_file.write_text("_meta:\n  updated_at: '2026-01-01'\nproject_name: x\n")
        result = load_ae_answers(tmp_path)
        assert result is not None
        assert "_meta" in result
        assert result["project_name"] == "x"

    def test_returns_empty_dict_for_empty_file(self, tmp_path: Path):
        """RED: 空 YAML 文件返回空 dict."""
        answers_file = tmp_path / ".ae-answers.yml"
        answers_file.write_text("")
        result = load_ae_answers(tmp_path)
        assert result == {} or result is None

    def test_returns_dict_for_malformed_but_readable_yaml(self, tmp_path: Path):
        """RED: 合法 YAML 即使字段少也返回 dict."""
        answers_file = tmp_path / ".ae-answers.yml"
        answers_file.write_text("project_type: cli-tool\n")
        result = load_ae_answers(tmp_path)
        assert result is not None
        assert result["project_type"] == "cli-tool"


class TestPreflight:
    """preflight(project_root) — 入口前置校验."""

    def test_passes_in_valid_git_repo(self, tmp_path: Path, monkeypatch):
        """RED: 合法 git 仓库 + 有 API key 时 preflight 通过."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        (tmp_path / ".git").mkdir()
        preflight(tmp_path)

    def test_raises_systemexit_without_api_key(self, tmp_path: Path, monkeypatch):
        """RED: 缺 ANTHROPIC_API_KEY 时 preflight 抛 SystemExit."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        (tmp_path / ".git").mkdir()
        with pytest.raises(SystemExit):
            preflight(tmp_path)

    def test_raises_systemexit_outside_git_repo(self, tmp_path: Path, monkeypatch):
        """RED: 非 git 仓库时 preflight 抛 SystemExit."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        with pytest.raises(SystemExit):
            preflight(tmp_path)

    def test_systemexit_code_is_one_on_failure(self, tmp_path: Path, monkeypatch):
        """RED: 失败时 SystemExit code=1."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        (tmp_path / ".git").mkdir()
        with pytest.raises(SystemExit) as exc_info:
            preflight(tmp_path)
        assert exc_info.value.code == 1

    def test_preflight_skips_api_key_in_llm_agent(self, tmp_path: Path, monkeypatch):
        """CLAUDE_CODE 环境变量存在时跳过 API key 检查."""
        monkeypatch.setenv("CLAUDE_CODE", "true")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        (tmp_path / ".git").mkdir()
        preflight(tmp_path)  # 不应抛异常

    def test_preflight_python_version_check(self, tmp_path: Path, monkeypatch):
        """Python < 3.12 时抛 SystemExit."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        (tmp_path / ".git").mkdir()
        # Patch with a mock that has .major/.minor attrs like real sys.version_info
        import sys as sys_module
        class FakeVersionInfo:
            def __init__(self):
                self.major = 3
                self.minor = 11
        with patch.object(sys_module, "version_info", FakeVersionInfo()):
            with pytest.raises(SystemExit):
                preflight(tmp_path)

    def test_preflight_disk_space_insufficient(self, tmp_path: Path, monkeypatch):
        """磁盘空间 < 100MB 时抛 SystemExit."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        (tmp_path / ".git").mkdir()
        # Mock disk_usage to return a fake disk usage with low free space
        class _FakeDiskUsage:
            def __init__(self, total, used, free):
                self.total = total
                self.used = used
                self.free = free
        with patch.object(shutil, "disk_usage", return_value=_FakeDiskUsage(100 * 1024 * 1024, 50 * 1024 * 1024, 40 * 1024 * 1024)):
            with pytest.raises(SystemExit):
                preflight(tmp_path)


class TestProjectEnvironment:
    """ProjectEnvironment — save/resolve/sync."""

    def test_save_creates_file(self, tmp_path: Path):
        """save() 创建 .ae-answers.yml 文件."""
        env = ProjectEnvironment(project_name="test", project_type="app-service")
        env.save(tmp_path)
        assert (tmp_path / ".ae-answers.yml").exists()

    def test_save_preserves_existing_meta(self, tmp_path: Path):
        """save() 保留已有 _meta 并追加 updated_at."""
        answers_file = tmp_path / ".ae-answers.yml"
        answers_file.write_text("_meta:\n  created_at: '2026-01-01'\nproject_name: old\n")
        env = ProjectEnvironment(project_name="new")
        env.save(tmp_path)
        content = answers_file.read_text()
        assert "updated_at" in content
        assert "created_at" in content

    def test_resolve_from_detection_when_no_answers_file(self, tmp_path: Path):
        """无 .ae-answers.yml 时走 _from_detection 分支，project_name 取目录名."""
        (tmp_path / ".git").mkdir()
        env = ProjectEnvironment.resolve(tmp_path)
        # _from_detection sets project_name = root.resolve().name
        assert env.project_name == tmp_path.resolve().name

    def test_detect_ci_github(self, tmp_path: Path):
        """.github/workflows 目录 → github."""
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        detected = ProjectEnvironment._detect_ci(tmp_path)
        assert detected == "github"

    def test_detect_ci_gitlab(self, tmp_path: Path):
        """.gitlab-ci.yml 文件 → gitlab."""
        (tmp_path / ".gitlab-ci.yml").write_text("test: true")
        detected = ProjectEnvironment._detect_ci(tmp_path)
        assert detected == "gitlab"

    def test_detect_ci_none(self, tmp_path: Path):
        """无 CI 配置 → None."""
        detected = ProjectEnvironment._detect_ci(tmp_path)
        assert detected is None

    def test_sync_detectable_changes_field(self, tmp_path: Path):
        """_sync_detectable 检测到不一致时更新字段并返回 True."""
        env = ProjectEnvironment(project_name="test", test_runner=None)
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'")
        changed = env._sync_detectable(tmp_path)
        assert changed is True
        assert env.test_runner == "pytest"

    def test_warn_undetectable_returns_fields(self, tmp_path: Path):
        """_warn_undetectable 返回不可判定字段列表."""
        env = ProjectEnvironment(project_name="test", package_manager=None)
        result = env._warn_undetectable(tmp_path)
        assert "package_manager" in result
