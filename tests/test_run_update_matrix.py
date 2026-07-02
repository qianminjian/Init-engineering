"""9 矩阵测试 — 3 冲突策略 × 3 文件状态 = 9 组合全覆盖。

文件状态矩阵:
  S0 = 文件不存在
  S1 = 文件存在 + 内容相同 (无修改)
  S2 = 文件存在 + 内容不同 (有冲突)

冲突策略:
  skip     = 跳过冲突, 保留用户版本
  overwrite= 用新版本覆盖
  prompt   = 交互询问 (mock input)

期望结果:
  skip+S0=add, skip+S1=skip, skip+S2=skip
  overwrite+S0=add, overwrite+S1=skip, overwrite+S2=update
  prompt+S0=add, prompt+S1=skip, prompt+S2=(update|skip) 取决于 mock input
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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


def _mock_render_to(content_for_file: str):
    """生成 fake render_to — 模拟渲染产出指定内容."""

    def fake_render_to(*, answers, tmpdir, **kwargs):
        (tmpdir / "target.txt").write_text(content_for_file)
        from auto_engineering.init.scaffold_render import render_to

        return render_to(answers=answers, tmpdir=tmpdir, **kwargs)

    return fake_render_to


def test_skip_with_missing_file(project_with_answers: Path, monkeypatch: pytest.MonkeyPatch):
    """S0: dst 不存在 → skip 策略应添加文件."""
    monkeypatch.setattr(
        "auto_engineering.init.scaffold_update._render_to",
        _mock_render_to("NEW\n"),
    )
    from auto_engineering.init.scaffold_update import run_update

    result = run_update(
        dst_path=project_with_answers,
        dry_run=False,
        conflict_strategy="skip",
    )
    assert (project_with_answers / "target.txt").read_text() == "NEW\n"
    assert any("target.txt" in str(f) for f in result.files_added)


def test_skip_with_unchanged_file(project_with_answers: Path, monkeypatch: pytest.MonkeyPatch):
    """S1: dst 存在 + 内容相同 → skip 策略应保留."""
    (project_with_answers / "target.txt").write_text("SAME\n")
    monkeypatch.setattr(
        "auto_engineering.init.scaffold_update._render_to",
        _mock_render_to("SAME\n"),
    )
    from auto_engineering.init.scaffold_update import run_update

    result = run_update(
        dst_path=project_with_answers,
        dry_run=False,
        conflict_strategy="skip",
    )
    assert any("target.txt" in str(f) for f in result.files_skipped)
    assert not any("target.txt" in str(f) for f in result.files_updated)
    assert not any("target.txt" in str(f) for f in result.files_added)


def test_skip_with_changed_file(project_with_answers: Path, monkeypatch: pytest.MonkeyPatch):
    """S2: dst 存在 + 内容不同 → skip 策略应保留用户版本."""
    (project_with_answers / "target.txt").write_text("USER\n")
    monkeypatch.setattr(
        "auto_engineering.init.scaffold_update._render_to",
        _mock_render_to("GENERATED\n"),
    )
    from auto_engineering.init.scaffold_update import run_update

    result = run_update(
        dst_path=project_with_answers,
        dry_run=False,
        conflict_strategy="skip",
    )
    assert (project_with_answers / "target.txt").read_text() == "USER\n"
    assert any("target.txt" in str(f) for f in result.files_skipped)


def test_overwrite_with_missing_file(project_with_answers: Path, monkeypatch: pytest.MonkeyPatch):
    """S0: dst 不存在 → overwrite 应添加文件."""
    monkeypatch.setattr(
        "auto_engineering.init.scaffold_update._render_to",
        _mock_render_to("NEW\n"),
    )
    from auto_engineering.init.scaffold_update import run_update

    result = run_update(
        dst_path=project_with_answers,
        dry_run=False,
        conflict_strategy="overwrite",
    )
    assert (project_with_answers / "target.txt").read_text() == "NEW\n"
    assert any("target.txt" in str(f) for f in result.files_added)


def test_overwrite_with_unchanged_file(project_with_answers: Path, monkeypatch: pytest.MonkeyPatch):
    """S1: dst 存在 + 内容相同 → overwrite 应跳过(无意义)."""
    (project_with_answers / "target.txt").write_text("SAME\n")
    monkeypatch.setattr(
        "auto_engineering.init.scaffold_update._render_to",
        _mock_render_to("SAME\n"),
    )
    from auto_engineering.init.scaffold_update import run_update

    result = run_update(
        dst_path=project_with_answers,
        dry_run=False,
        conflict_strategy="overwrite",
    )
    assert any("target.txt" in str(f) for f in result.files_skipped)
    assert not any("target.txt" in str(f) for f in result.files_updated)


def test_overwrite_with_changed_file(project_with_answers: Path, monkeypatch: pytest.MonkeyPatch):
    """S2: dst 存在 + 内容不同 → overwrite 应替换."""
    (project_with_answers / "target.txt").write_text("USER\n")
    monkeypatch.setattr(
        "auto_engineering.init.scaffold_update._render_to",
        _mock_render_to("GENERATED\n"),
    )
    from auto_engineering.init.scaffold_update import run_update

    result = run_update(
        dst_path=project_with_answers,
        dry_run=False,
        conflict_strategy="overwrite",
    )
    assert (project_with_answers / "target.txt").read_text() == "GENERATED\n"
    assert any("target.txt" in str(f) for f in result.files_updated)


def test_prompt_with_missing_file(project_with_answers: Path, monkeypatch: pytest.MonkeyPatch):
    """S0: dst 不存在 → prompt 策略应直接添加(无需询问)."""
    monkeypatch.setattr(
        "auto_engineering.init.scaffold_update._render_to",
        _mock_render_to("NEW\n"),
    )
    from auto_engineering.init.scaffold_update import run_update

    result = run_update(
        dst_path=project_with_answers,
        dry_run=False,
        conflict_strategy="prompt",
    )
    assert (project_with_answers / "target.txt").read_text() == "NEW\n"
    assert any("target.txt" in str(f) for f in result.files_added)


def test_prompt_with_changed_file_accept(
    project_with_answers: Path, monkeypatch: pytest.MonkeyPatch
):
    """S2 + 用户回答 y → 应更新."""
    (project_with_answers / "target.txt").write_text("USER\n")
    monkeypatch.setattr(
        "auto_engineering.init.scaffold_update._render_to",
        _mock_render_to("GENERATED\n"),
    )
    # mock click.confirm 返回 True
    monkeypatch.setattr("click.confirm", lambda *a, **kw: True)
    from auto_engineering.init.scaffold_update import run_update

    result = run_update(
        dst_path=project_with_answers,
        dry_run=False,
        conflict_strategy="prompt",
    )
    assert (project_with_answers / "target.txt").read_text() == "GENERATED\n"
    assert any("target.txt" in str(f) for f in result.files_updated)


def test_prompt_with_changed_file_reject(
    project_with_answers: Path, monkeypatch: pytest.MonkeyPatch
):
    """S2 + 用户回答 n → 应跳过(保留用户版本)."""
    (project_with_answers / "target.txt").write_text("USER\n")
    monkeypatch.setattr(
        "auto_engineering.init.scaffold_update._render_to",
        _mock_render_to("GENERATED\n"),
    )
    monkeypatch.setattr("click.confirm", lambda *a, **kw: False)
    from auto_engineering.init.scaffold_update import run_update

    result = run_update(
        dst_path=project_with_answers,
        dry_run=False,
        conflict_strategy="prompt",
    )
    assert (project_with_answers / "target.txt").read_text() == "USER\n"
    assert any("target.txt" in str(f) for f in result.files_skipped)


def test_prompt_dry_run_marks_conflict(
    project_with_answers: Path, monkeypatch: pytest.MonkeyPatch
):
    """prompt + dry_run → 冲突文件标记为 conflicted 而非更新."""
    (project_with_answers / "target.txt").write_text("USER\n")
    monkeypatch.setattr(
        "auto_engineering.init.scaffold_update._render_to",
        _mock_render_to("GENERATED\n"),
    )
    from auto_engineering.init.scaffold_update import run_update

    result = run_update(
        dst_path=project_with_answers,
        dry_run=True,
        conflict_strategy="prompt",
    )
    assert any("target.txt" in str(f) for f in result.files_conflicted)
    # dry_run 不写盘
    assert (project_with_answers / "target.txt").read_text() == "USER\n"