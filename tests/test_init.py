"""E2E tests for ae init command."""

import subprocess
import tempfile
from pathlib import Path


def run_ae(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "ae"] + args,
        capture_output=True, text=True,
    )


class TestInitHelp:
    def test_help_output(self):
        result = run_ae(["init", "--help"])
        assert result.returncode == 0
        assert "--type" in result.stdout
        assert "--defaults" in result.stdout
        assert "--force" in result.stdout
        assert "--pretend" in result.stdout
        assert "--skip-tasks" in result.stdout
        assert "--no-cleanup" in result.stdout

    def test_all_flags_present(self):
        """Verify all 13 flags appear in help."""
        result = run_ae(["init", "--help"])
        flags = [
            "--type", "--defaults", "--force", "--from-answers",
            "--package-manager", "--ci", "--test-runner",
            "--no-typescript", "--no-lefthook",
            "--pretend", "--skip-tasks", "--no-cleanup", "--quiet",
        ]
        for flag in flags:
            assert flag in result.stdout, f"Missing flag: {flag}"


class TestInitPretend:
    def test_pretend_no_files_created(self):
        tmp = Path(tempfile.mkdtemp())
        target = tmp / "test-project"
        result = run_ae([
            "init", str(target),
            "--type", "app-service",
            "--defaults",
            "--pretend",
            "--force",
        ])
        assert result.returncode == 0
        assert "DRY RUN" in result.stdout
        assert not target.exists()

    def test_pretend_with_skip_tasks(self):
        tmp = Path(tempfile.mkdtemp())
        target = tmp / "test-project2"
        result = run_ae([
            "init", str(target),
            "--type", "library",
            "--defaults",
            "--pretend",
            "--skip-tasks",
            "--force",
        ])
        assert result.returncode == 0
        assert "DRY RUN" in result.stdout


class TestAeStatus:
    def test_status_output(self):
        result = run_ae(["status"])
        assert result.returncode == 0
        assert "当前目录" in result.stdout
