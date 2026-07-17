"""PR#4 P1-3/P1-4/P1-5 安全硬化测试.

P1-3: hooks.py string-mode cmd shlex.split 防护
P1-4: --template-dir 白名单硬阻断 + --force-unsafe-template 绕过
P1-5: sandbox_roots=None fallback (config_loader.py + answers.py)
"""

import subprocess
from pathlib import Path

import pytest

from init_engineering.init.config_loader import _load_yaml_with_includes
from init_engineering.init.answers import AnswersMap
from init_engineering.init.errors import TaskExecutionError


# ─── P1-3: string cmd shlex.split ─────────────────────────────────────────


class TestStringCmdShlexSplit:
    """PR#4 P1-3: string-mode cmd 强制 shlex.split → argv 数组."""

    def _run_capture(self, tmp_path: Path, task):
        """Helper: run task, return captured subprocess.run kwargs."""
        from init_engineering.init.hooks import TaskRunner

        captured = {}

        def fake_run(*args, **kwargs):
            captured.update(kwargs)
            captured.setdefault("args", args[0] if args else None)
            r = type("R", (), {"returncode": 0, "stderr": "", "stdout": ""})()
            return r

        import unittest.mock as mock
        runner = TaskRunner(tmp_path, current_phase="test")
        with mock.patch("subprocess.run", side_effect=fake_run):
            runner.run([task], {}, _FakeJinjaEnv())
        return captured

    def test_string_cmd_split_into_argv(self, tmp_path: Path):
        """空格分隔的字符串应被 tokenize 成多个 argv."""
        from init_engineering.init.config_types import Task

        task = Task(cmd="echo hello world")
        captured = self._run_capture(tmp_path, task)
        # shlex.split("echo hello world") → ["echo", "hello", "world"]
        assert captured["args"] == ["echo", "hello", "world"]

    def test_string_cmd_with_quotes_preserved(self, tmp_path: Path):
        """带引号的字符串应保留空格 (shlex 解析)."""
        from init_engineering.init.config_types import Task

        task = Task(cmd='echo "hello world"')
        captured = self._run_capture(tmp_path, task)
        # shlex.split 保留引号内空格
        assert captured["args"] == ["echo", "hello world"]

    def test_string_cmd_shlex_failure_raises(self, tmp_path: Path):
        """引号不匹配应抛 TaskExecutionError (不是 subprocess 错误)."""
        from init_engineering.init.config_types import Task
        from init_engineering.init.hooks import TaskRunner

        task = Task(cmd='echo "unclosed quote')
        runner = TaskRunner(tmp_path, current_phase="test")
        with pytest.raises(TaskExecutionError, match="shlex.split"):
            runner.run([task], {}, _FakeJinjaEnv())

    def test_list_cmd_unchanged(self, tmp_path: Path):
        """list 模式 cmd 不走 shlex.split."""
        from init_engineering.init.config_types import Task

        task = Task(cmd=["echo", "hello"])
        captured = self._run_capture(tmp_path, task)
        assert captured["args"] == ["echo", "hello"]


class _FakeJinjaEnv:
    """让 TaskRunner.run 直接用 raw string 渲染 (无 jinja 占位符时无变化)."""

    class _Template:
        def __init__(self, s):
            self.s = s

        def render(self, **_):
            return self.s

    def from_string(self, s):
        return _FakeJinjaEnv._Template(s)


# ─── P1-5: sandbox_roots=None fallback ────────────────────────────────────


class TestSandboxRootsFallback:
    """PR#4 P1-5: sandbox_roots=None 时 fallback 到 [config_path.parent]."""

    def test_load_yaml_with_includes_default_fallback(self, tmp_path: Path):
        """sandbox_roots=None → fallback 到 [config_path.parent], 阻止 !include 越界."""
        cfg = tmp_path / "ae.yml"
        cfg.write_text("foo: bar\n")
        result = _load_yaml_with_includes(cfg)
        assert result == {"foo": "bar"}

    def test_load_yaml_with_includes_explicit_empty_strict(self, tmp_path: Path):
        """sandbox_roots=[] 显式空列表 → 严格模式,任何 include 拒."""
        from init_engineering.init.errors import ConfigLoaderSecurityError

        # 创建一个 !include 模板 (单文件 in sandbox)
        partial = tmp_path / "_partial.yml"
        partial.write_text("x: 1\n")
        cfg = tmp_path / "ae.yml"
        cfg.write_text("data: !include _partial.yml\n")

        with pytest.raises(ConfigLoaderSecurityError, match="strict mode"):
            _load_yaml_with_includes(cfg, sandbox_roots=[])

    def test_answers_external_default_fallback_blocks_etc_passwd(self, tmp_path: Path):
        """sandbox_roots=空时, external_data 读 /etc/passwd 应被拒绝."""
        answers = AnswersMap(
            external={"k": "/etc/passwd"},
            external_sandbox_roots=[],
        )
        with pytest.raises(ValueError, match="not under sandbox roots"):
            answers._load_external("k")

    def test_answers_external_fallback_allows_tmpdir(self, tmp_path: Path):
        """sandbox_roots=空时, external_data 读 tmpdir 应放行 (回归保护)."""
        ext = tmp_path / "data.yml"
        ext.write_text("a: 1\n")
        answers = AnswersMap(
            external={"k": str(ext)},
            external_sandbox_roots=[],
        )
        # 第一次访问触发 lazy load
        val = answers._load_external("k")
        assert val == {"a": 1}

    def test_answers_external_explicit_sandbox_still_enforced(self, tmp_path: Path):
        """external_sandbox_roots 非空时, 范围外路径应被拒 (原行为不变)."""
        answers = AnswersMap(
            external={"k": str(tmp_path / "not-in-sandbox.yml")},
            external_sandbox_roots=["/only/this/path"],
        )
        with pytest.raises(ValueError, match="not under sandbox roots"):
            answers._load_external("k")


# ─── P1-4: --template-dir 硬阻断 ──────────────────────────────────────────


class TestTemplateDirHardBlock:
    """PR#4 P1-4: --template-dir 白名单硬阻断（v5.5: --force-unsafe-template 已移除，安全路径外一律拒绝）."""

    def test_unsafe_template_dir_blocked_by_default(self, tmp_path: Path):
        """非白名单路径 + 无 bypass → 抛 UsageError."""
        from click.testing import CliRunner
        from init_engineering.cli import init as cli_init

        # 创建一个远离 cwd / home / /tmp 的"恶意"路径
        bad_dir = Path("/tmp/ae-test-bad-template-dir-xyz")
        bad_dir.mkdir(exist_ok=True)
        (bad_dir / "ae-template.yml").write_text("name: x\n")
        try:
            runner = CliRunner()
            result = runner.invoke(
                cli_init,
                [
                    str(tmp_path / "out"),
                    "--template-dir", str(bad_dir),
                    "--defaults",
                    "--skip-tasks",
                ],
            )
            # 由于安全根包含 /tmp, /tmp 下路径仍安全 — 测一个非 /tmp 的位置
            # 实际方案: 用一个不在安全根列表的路径
            from pathlib import Path as _P
            non_safe = _P("/var/tmp/ae-malicious")
            non_safe.mkdir(parents=True, exist_ok=True)
            (non_safe / "ae-template.yml").write_text("name: x\n")
            result = runner.invoke(
                cli_init,
                [
                    str(tmp_path / "out"),
                    "--template-dir", str(non_safe),
                    "--defaults",
                    "--skip-tasks",
                ],
            )
            assert result.exit_code != 0
            assert "不在安全路径内" in result.output or "not in" in result.output.lower()
        finally:
            import shutil
            shutil.rmtree(bad_dir, ignore_errors=True)
            shutil.rmtree(Path("/var/tmp/ae-malicious"), ignore_errors=True)

    def test_non_safe_template_dir_always_blocked(self, tmp_path: Path):
        """v5.5: --force-unsafe-template 已移除，非白名单路径一律拒绝."""
        from click.testing import CliRunner
        from init_engineering.cli import init as cli_init

        from pathlib import Path as _P
        non_safe = _P("/var/tmp/ae-malicious-bypass")
        non_safe.mkdir(parents=True, exist_ok=True)
        (non_safe / "ae-template.yml").write_text(
            "_questions:\n  - {var_name: project_name, type: str, default: x}\n"
        )
        try:
            runner = CliRunner()
            result = runner.invoke(
                cli_init,
                [
                    str(tmp_path / "out"),
                    "--template-dir", str(non_safe),
                    "--defaults",
                    "--skip-tasks",
                ],
            )
            assert result.exit_code != 0
            assert "不在安全路径内" in result.output
        finally:
            import shutil
            shutil.rmtree(non_safe, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])