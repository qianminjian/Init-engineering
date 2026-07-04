"""Tests for config/environment.py — ProjectEnvironment."""

from __future__ import annotations

from pathlib import Path

from init_engineering.config.environment import ProjectEnvironment


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