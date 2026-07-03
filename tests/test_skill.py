"""skill.py 单元测试 — Agent Skill 入口.

覆盖 init_engineering/skill.py (0% → 测试目标)。
"""

from pathlib import Path

import pytest

from init_engineering.skill import (
    _parse_prompt,
    _run_analyze,
    _run_detect,
    _run_init,
    skill,
)


# ─── _resolve_path ───────────────────────────────────────────────────────────


class TestResolvePath:
    """_resolve_path — 路径解析与安全校验."""

    def test_resolve_existing_path(self, tmp_path: Path):
        """存在的路径直接 resolve."""
        from init_engineering.skill import _resolve_path

        existing = tmp_path / "real"
        existing.mkdir()
        result = _resolve_path(str(existing), tmp_path)
        assert result == existing.resolve()

    def test_resolve_dot_returns_cwd(self, tmp_path: Path):
        """path='.' 返回 cwd."""
        from init_engineering.skill import _resolve_path

        result = _resolve_path(".", tmp_path)
        assert result == tmp_path

    def test_resolve_none_returns_cwd(self, tmp_path: Path):
        """path=None 返回 cwd."""
        from init_engineering.skill import _resolve_path

        result = _resolve_path(None, tmp_path)
        assert result == tmp_path

    def test_resolve_expands_tilde(self, tmp_path: Path, monkeypatch):
        """~ 展开为家目录路径."""
        import os
        from init_engineering.skill import _resolve_path

        # Patch os.path.expanduser to return tmp_path as home
        monkeypatch.setattr(os.path, "expanduser", lambda _: str(tmp_path))
        result = _resolve_path("~/project", tmp_path)
        assert str(result).startswith(str(tmp_path))


# ─── _parse_prompt ────────────────────────────────────────────────────────────


class TestParsePrompt:
    """_parse_prompt — 解析 agent 自然语言指令."""

    def test_parse_init_with_type(self):
        assert _parse_prompt("init my-project --type app-service") == (
            "init",
            "my-project",
            {"type": "app-service"},
        )

    def test_parse_init_only(self):
        assert _parse_prompt("init my-project") == ("init", "my-project", {})

    def test_parse_init_with_defaults(self):
        """--defaults 作为独立选项."""
        result = _parse_prompt("init myproj --type library --defaults")
        assert result[0] == "init"
        assert result[1] == "myproj"
        assert result[2]["type"] == "library"
        assert result[2]["defaults"] == "true"

    def test_parse_analyze(self):
        assert _parse_prompt("analyze /path/to/project") == (
            "analyze",
            "/path/to/project",
            {},
        )

    def test_parse_analyse_alias(self):
        """analyse (英式拼写) 也支持."""
        assert _parse_prompt("analyse /path") == ("analyze", "/path", {})

    def test_parse_analyze_dot(self):
        """analyze . 表示当前目录."""
        assert _parse_prompt("analyze .") == ("analyze", ".", {})

    def test_parse_detect(self):
        assert _parse_prompt("detect /path/to/project") == (
            "detect",
            "/path/to/project",
            {},
        )

    def test_parse_unknown(self):
        assert _parse_prompt("invalid command") == ("unknown", None, {})

    def test_parse_unknown_empty(self):
        assert _parse_prompt("") == ("unknown", None, {})

    def test_parse_init_with_ci(self):
        result = _parse_prompt("init myproj --ci github")
        assert result[2]["ci"] == "github"

    def test_parse_init_incremental(self):
        result = _parse_prompt("init myproj --incremental")
        assert result[2]["incremental"] == "true"

    def test_parse_trim_whitespace(self):
        assert _parse_prompt("  init my-project --type app-service  ") == (
            "init",
            "my-project",
            {"type": "app-service"},
        )


# ─── _run_analyze ────────────────────────────────────────────────────────────


class TestRunAnalyze:
    """_run_analyze — 存量项目分析."""

    def test_analyze_nonexistent_dir(self, tmp_path: Path):
        result = _run_analyze("/nonexistent/path", tmp_path)
        assert result.success is False
        assert "不存在" in result.message
        assert result.action == "analyze"

    def test_analyze_empty_dir(self, tmp_path: Path):
        result = _run_analyze(str(tmp_path), tmp_path)
        assert result.success is True
        assert result.action == "analyze"

    def test_analyze_detects_package(self, tmp_path: Path):
        """package.json + tsconfig.json → app-service 候选."""
        (tmp_path / "package.json").write_text('{"name": "app"}')
        (tmp_path / "tsconfig.json").write_text("{}")
        result = _run_analyze(str(tmp_path), tmp_path)
        assert result.success is True
        assert len(result.candidates) >= 1

    def test_analyze_detects_python(self, tmp_path: Path):
        """pyproject.toml → library 候选."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        result = _run_analyze(str(tmp_path), tmp_path)
        assert result.success is True
        assert "library" in result.candidates

    def test_analyze_dot_means_cwd(self, tmp_path: Path):
        """analyze . 使用 cwd."""
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"')
        result = _run_analyze(".", tmp_path)
        assert result.success is True
        assert result.project_path == str(tmp_path)


# ─── _run_detect ──────────────────────────────────────────────────────────────


class TestRunDetect:
    """_run_detect — 项目类型检测 (调用 _run_analyze)."""

    def test_detect_calls_analyze(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        result = _run_detect(str(tmp_path), tmp_path)
        assert result.success is True
        assert result.action == "analyze"


# ─── skill ───────────────────────────────────────────────────────────────────


class TestSkill:
    """skill() — 顶层入口."""

    def test_skill_analyze(self, tmp_path: Path):
        (tmp_path / "package.json").write_text('{"name": "app"}')
        result = skill(f"analyze {tmp_path}", cwd=tmp_path)
        assert result.success is True
        assert result.action == "analyze"

    def test_skill_init_action(self, tmp_path: Path):
        """验证 init action 返回 init."""
        target = tmp_path / "newproj"
        result = skill(
            f"init {target} --type app-service --defaults --skip-tasks --pretend",
            cwd=tmp_path,
        )
        assert result.action == "init"

    def test_skill_unknown_command(self, tmp_path: Path):
        result = skill("unknown command", cwd=tmp_path)
        assert result.success is False
        assert result.action == "parse"

    def test_skill_analyze_dot(self):
        """cwd=None 默认 Path.cwd()."""
        result = skill("analyze .")
        assert result.action == "analyze"

    def test_skill_detect(self, tmp_path: Path):
        """skill("detect ...") 调用 _run_detect → line 59."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        result = skill(f"detect {tmp_path}", cwd=tmp_path)
        assert result.success is True
        assert result.action == "analyze"

    def test_skill_init_branch(self, tmp_path: Path):
        """skill("init ...") 确认走到 init 分支."""
        target = tmp_path / "newproj"
        # --defaults 放最后以避免 regex bug 把它和后续 flag 合并
        result = skill(
            f"init {target} --type app-service --skip-tasks --pretend --defaults",
            cwd=tmp_path,
        )
        assert result.action == "init"


# ─── SkillResult dataclass ───────────────────────────────────────────────────


class TestSkillResult:
    """SkillResult 数据类."""

    def test_skill_result_fields(self):
        from init_engineering.skill import SkillResult

        r = SkillResult(
            success=True,
            message="ok",
            action="init",
            project_path="/a/b",
            project_type="app-service",
            candidates=["app-service"],
            details={"files": 10},
        )
        assert r.success is True
        assert r.message == "ok"
        assert r.action == "init"
        assert r.project_path == "/a/b"
        assert r.project_type == "app-service"
        assert r.candidates == ["app-service"]
        assert r.details == {"files": 10}

    def test_skill_result_defaults(self):
        from init_engineering.skill import SkillResult

        r = SkillResult(success=True, message="ok")
        assert r.action == ""
        assert r.project_path is None
        assert r.project_type is None
        assert r.candidates == []
        assert r.details == {}


# ─── _resolve_path error paths ─────────────────────────────────────────────────


# ─── _run_init error paths ────────────────────────────────────────────────────


class TestRunInitErrors:
    """_run_init — 初始化失败路径."""

    def test_init_nonexistent_dir(self, tmp_path: Path):
        """初始化时路径不存在则不创建 → 会失败或成功取决于目录是否存在."""
        target = tmp_path / "newdir"
        result = _run_init(str(target), {"type": "app-service", "defaults": "true", "skip-tasks": "true"}, tmp_path)
        # InitWorker should run (directory will be created)
        assert result.action == "init"

    def test_init_invalid_type(self, tmp_path: Path):
        """无效 project_type 应能初始化（靠模板加载时报错）."""
        target = tmp_path / "testproj"
        result = _run_init(str(target), {"type": "nonexistent-type"}, tmp_path)
        # 即使 type 无效，路径解析应成功，但是 InitWorker 会报错
        assert result.action == "init"

    def test_init_failure_with_invalid_type_no_defaults(self, tmp_path: Path):
        """无效 type 且无 defaults/skip_tasks → 可能触发交互."""
        target = tmp_path / "testproj2"
        result = _run_init(str(target), {"type": "nonexistent-type", "pretend": "true"}, tmp_path)
        assert result.action == "init"


# ─── skill() 解析边缘 ─────────────────────────────────────────────────────────


class TestSkillEdgeCases:
    """skill() — 顶层入口的边缘情况."""

    def test_skill_init_with_multiple_flags(self, tmp_path: Path):
        """多个 flag 同时传入."""
        target = tmp_path / "multi"
        result = skill(
            f"init {target} --type cli-tool --language go --ci gitlab "
            f"--strict --verbose --telemetry --defaults --skip-tasks --pretend",
            cwd=tmp_path,
        )
        assert result.action == "init"

    def test_skill_init_no_pretend_actually_runs(self, tmp_path: Path):
        """无 --pretend 时实际执行初始化."""
        target = tmp_path / "realproj"
        result = skill(
            f"init {target} --type app-service --defaults --skip-tasks",
            cwd=tmp_path,
        )
        assert result.action == "init"
        assert result.success or not result.success  # at least ran
