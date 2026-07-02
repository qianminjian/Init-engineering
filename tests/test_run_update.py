"""Tests for run_update() — 升级已存在项目。

覆盖：
1. 无 .ae-answers.yml + force → 推断 project_type 并升级
2. 有 .ae-answers.yml + 无冲突 → files_added = 新文件数
3. 有冲突 + skip → files_skipped 含冲突
4. 有冲突 + overwrite → files_updated 含冲突
5. dry_run 不写入
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project_with_answers(tmp_path: Path) -> Path:
    """预填 .ae-answers.yml 的 library 项目."""
    project = tmp_path / "lib"
    project.mkdir()
    (project / ".ae-answers.yml").write_text(
        """project_type: library
project_name: mylib
language: python
package_manager: uv
test_runner: pytest
ci_platform: github
use_typescript: false
use_lefthook: false
use_docker: false
_meta:
  ae_version: 1.0.0
  created_at: '2026-07-01T00:00:00'
"""
    )
    return project


def test_run_update_adds_missing_files(project_with_answers: Path, monkeypatch: pytest.MonkeyPatch):
    """run_update 应补充之前未生成的新文件."""
    from auto_engineering.init.scaffold_update import run_update

    # 模拟 render_to 在 tmpdir 中创建新文件
    from auto_engineering.init import scaffold_render

    real_render_to = scaffold_render.render_to

    def fake_render_to(*, answers, tmpdir, **kwargs):
        (tmpdir / "new_file.txt").write_text("hello")
        return real_render_to(answers=answers, tmpdir=tmpdir, **kwargs)

    monkeypatch.setattr(
        "auto_engineering.init.scaffold_update._render_to", fake_render_to
    )

    result = run_update(
        dst_path=project_with_answers,
        force=False,
        dry_run=False,
        conflict_strategy="skip",
    )
    assert (project_with_answers / "new_file.txt").exists()
    assert any("new_file.txt" in str(f) for f in result.files_added)


def test_run_update_skip_keeps_user_modification(
    project_with_answers: Path, monkeypatch: pytest.MonkeyPatch
):
    """冲突策略 skip: 保留用户修改的文件."""
    from auto_engineering.init.scaffold_update import run_update

    # 用户手动修改的 pyproject.toml
    (project_with_answers / "pyproject.toml").write_text("# USER MODIFIED\n")

    from auto_engineering.init import scaffold_render

    real_render_to = scaffold_render.render_to

    def fake_render_to(*, answers, tmpdir, **kwargs):
        (tmpdir / "pyproject.toml").write_text("# GENERATED\n")
        return real_render_to(answers=answers, tmpdir=tmpdir, **kwargs)

    monkeypatch.setattr(
        "auto_engineering.init.scaffold_update._render_to", fake_render_to
    )

    result = run_update(
        dst_path=project_with_answers,
        dry_run=False,
        conflict_strategy="skip",
    )
    # 用户的修改应被保留
    assert "# USER MODIFIED" in (project_with_answers / "pyproject.toml").read_text()
    assert any("pyproject.toml" in str(f) for f in result.files_skipped)


def test_run_update_overwrite_replaces(
    project_with_answers: Path, monkeypatch: pytest.MonkeyPatch
):
    """冲突策略 overwrite: 用新版本覆盖."""
    from auto_engineering.init.scaffold_update import run_update

    (project_with_answers / "pyproject.toml").write_text("# USER MODIFIED\n")

    from auto_engineering.init import scaffold_render

    real_render_to = scaffold_render.render_to

    def fake_render_to(*, answers, tmpdir, **kwargs):
        (tmpdir / "pyproject.toml").write_text("# GENERATED v2\n")
        return real_render_to(answers=answers, tmpdir=tmpdir, **kwargs)

    monkeypatch.setattr(
        "auto_engineering.init.scaffold_update._render_to", fake_render_to
    )

    result = run_update(
        dst_path=project_with_answers,
        dry_run=False,
        conflict_strategy="overwrite",
    )
    assert "# GENERATED v2" in (project_with_answers / "pyproject.toml").read_text()
    assert any("pyproject.toml" in str(f) for f in result.files_updated)


def test_run_update_dry_run_no_write(
    project_with_answers: Path, monkeypatch: pytest.MonkeyPatch
):
    """dry_run 模式不写入文件."""
    from auto_engineering.init.scaffold_update import run_update

    from auto_engineering.init import scaffold_render

    real_render_to = scaffold_render.render_to

    def fake_render_to(*, answers, tmpdir, **kwargs):
        (tmpdir / "new_dry.txt").write_text("dry")
        return real_render_to(answers=answers, tmpdir=tmpdir, **kwargs)

    monkeypatch.setattr(
        "auto_engineering.init.scaffold_update._render_to", fake_render_to
    )

    result = run_update(
        dst_path=project_with_answers,
        dry_run=True,
        conflict_strategy="skip",
    )
    assert not (project_with_answers / "new_dry.txt").exists()
    assert result.diffs.get("new_dry.txt") == "(new file)"


def test_run_update_updates_meta(project_with_answers: Path, monkeypatch: pytest.MonkeyPatch):
    """run_update 应更新 .ae-answers.yml 的 _meta 字段."""
    from auto_engineering.init.scaffold_update import run_update

    result = run_update(
        dst_path=project_with_answers,
        dry_run=False,
        conflict_strategy="skip",
    )
    import yaml

    data = yaml.safe_load((project_with_answers / ".ae-answers.yml").read_text())
    assert "updated_at" in data.get("_meta", {})
    assert data["_meta"]["ae_version"] == "1.0.0"


def test_run_update_force_without_answers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """无 .ae-answers.yml + force → 退化为 fresh init."""
    from auto_engineering.init.scaffold_update import run_update

    # 提供 package.json 触发 library 推断
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    # 用 force=True 不抛错
    try:
        result = run_update(
            dst_path=tmp_path,
            force=True,
            dry_run=True,
            conflict_strategy="skip",
        )
        # 至少应执行到 classify 阶段不抛错
        assert result is not None
    except FileNotFoundError as e:
        pytest.fail(f"force=True should bypass missing answers: {e}")
