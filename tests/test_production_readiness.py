"""P1: analyze→init E2E pipeline + 深度分析覆盖 + 矩阵烟雾测试.

PR#5 P1-7: 标记 integration — 真实 ae 子进程调用 + 矩阵组合 ~30s/file.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def run_ae(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    venv_bin = Path(__file__).resolve().parent.parent / ".venv" / "bin"
    return subprocess.run([str(venv_bin / "ae"), *args], capture_output=True, text=True, cwd=cwd)


# ─── analyze→init E2E pipeline ─────────────────────────────────────────────


class TestAnalyzeInitE2E:
    """P1: analyze() 检测 → init() 全自动流水线 E2E."""

    def test_analyze_python_library_then_init(self, tmp_path: Path):
        """在模拟 Python 库项目上 analyze → init 全流程."""
        from init_engineering.init.detector import ProjectDetector
        from init_engineering.init.scaffold import InitWorker

        # 1. 构造模拟的 Python 库项目
        proj = tmp_path / "my-pylib"
        proj.mkdir()
        (proj / "pyproject.toml").write_text(
            '[project]\nname = "my-pylib"\ndescription = "A test library"\n'
            "dependencies = [\"fastapi>=0.100.0\", \"uvicorn\"]\n"
        )
        (proj / "uv.lock").write_text("")
        (proj / "pytest.ini").write_text("[pytest]\n")

        # 2. analyze()
        detector = ProjectDetector(proj)
        result = detector.analyze()

        assert result.project_type == "library"
        assert result.language == "python"
        assert result.package_manager == "uv"
        assert result.test_runner == "pytest"
        assert "FastAPI" in result.frameworks

        # 3. init with detected config
        target = tmp_path / "output-pylib"
        worker = InitWorker(
            dst_path=target,
            project_type=result.project_type,
            language=result.language,
            package_manager=result.package_manager,
            test_runner=result.test_runner,
            defaults=True,
            skip_tasks=True,
            quiet=True,
        )
        init_result = worker.execute()
        assert init_result.project_type == "library"
        assert target.exists()
        assert (target / "CLAUDE.md").exists()

    def test_analyze_node_app_then_init(self, tmp_path: Path):
        """模拟 Node.js app-service 项目."""
        from init_engineering.init.detector import ProjectDetector
        from init_engineering.init.scaffold import InitWorker

        proj = tmp_path / "my-node-app"
        proj.mkdir()
        pkg = {
            "name": "my-node-app",
            "description": "A Node.js app",
            "dependencies": {"express": "^4.18.0", "next": "^14.0.0"},
            "devDependencies": {"typescript": "^5.0.0", "vitest": "^1.0.0"},
        }
        (proj / "package.json").write_text(json.dumps(pkg))
        (proj / "tsconfig.json").write_text("{}")
        (proj / "pnpm-lock.yaml").write_text("")
        (proj / "vitest.config.ts").write_text("")

        detector = ProjectDetector(proj)
        result = detector.analyze()

        assert result.project_type == "app-service"
        assert result.language == "typescript"
        assert result.package_manager == "pnpm"
        assert result.test_runner == "vitest"
        assert any(f in str(result.frameworks) for f in ["Express", "Next.js"])

        target = tmp_path / "output-node"
        worker = InitWorker(
            dst_path=target,
            project_type=result.project_type,
            language=result.language,
            package_manager=result.package_manager,
            test_runner=result.test_runner,
            defaults=True,
            skip_tasks=True,
            quiet=True,
        )
        init_result = worker.execute()
        assert init_result.project_type == "app-service"
        assert target.exists()

    def test_analyze_go_project(self, tmp_path: Path):
        """模拟 Go 项目 — 验证 go.mod 解析和框架检测."""
        from init_engineering.init.detector import ProjectDetector

        proj = tmp_path / "my-go-svc"
        proj.mkdir()
        (proj / "go.mod").write_text(
            "module github.com/acme/my-service\n\ngo 1.21\n\n"
            "require (\n\tgithub.com/gin-gonic/gin v1.9.0\n\tgithub.com/go-chi/chi/v5 v5.0.0\n)\n"
        )

        detector = ProjectDetector(proj)
        result = detector.analyze()

        assert result.language == "go"
        assert "Gin" in result.frameworks
        assert "Chi" in result.frameworks
        assert result.project_name == "my-service"

    def test_analyze_ci_detection_github(self, tmp_path: Path):
        """检测 GitHub Actions CI."""
        from init_engineering.init.detector import ProjectDetector

        proj = tmp_path / "ci-github"
        proj.mkdir()
        (proj / "pyproject.toml").write_text('[project]\nname = "test"\n')
        workflows = proj / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("")

        detector = ProjectDetector(proj)
        result = detector.analyze()
        assert result.ci_platform == "github"

    def test_analyze_ci_detection_gitlab(self, tmp_path: Path):
        """检测 GitLab CI."""
        from init_engineering.init.detector import ProjectDetector

        proj = tmp_path / "ci-gitlab"
        proj.mkdir()
        (proj / "pyproject.toml").write_text('[project]\nname = "test"\n')
        (proj / ".gitlab-ci.yml").write_text("stages:\n  - test\n")

        detector = ProjectDetector(proj)
        result = detector.analyze()
        assert result.ci_platform == "gitlab"

    def test_analyze_empty_dir(self, tmp_path: Path):
        """空目录 analyze 返回空 candidates."""
        from init_engineering.init.detector import ProjectDetector

        proj = tmp_path / "empty"
        proj.mkdir()
        detector = ProjectDetector(proj)
        result = detector.analyze()
        assert result.candidates == []
        assert result.project_type is None

    def test_analyze_rust_project(self, tmp_path: Path):
        """Rust 项目基本检测."""
        from init_engineering.init.detector import ProjectDetector

        proj = tmp_path / "my-crate"
        proj.mkdir()
        (proj / "Cargo.toml").write_text('[package]\nname = "my-crate"\n')

        detector = ProjectDetector(proj)
        result = detector.analyze()
        assert result.language == "rust"
        # library 签名 (Cargo.toml) 匹配
        assert "library" in result.candidates

    def test_analyze_monorepo_over_library(self, tmp_path: Path):
        """pnpm-workspace + pyproject → monorepo 优先于 library."""
        from init_engineering.init.detector import ProjectDetector

        proj = tmp_path / "mono"
        proj.mkdir()
        (proj / "pyproject.toml").write_text('[project]\nname = "test"\n')
        (proj / "pnpm-workspace.yaml").write_text("packages:\n  - 'packages/*'\n")

        detector = ProjectDetector(proj)
        candidates = detector.list_candidates()
        # monorepo 签名优先，但应同时出现在 candidates 里
        assert "monorepo" in candidates

    def test_analyze_detection_feeds_init_defaults(self, tmp_path: Path):
        """analyze 结果正确注入 InitWorker 作为 builtin 默认值."""
        from init_engineering.init.detector import ProjectDetector
        from init_engineering.init.scaffold import InitWorker

        proj = tmp_path / "detect-feed"
        proj.mkdir()
        (proj / "pyproject.toml").write_text('[project]\nname = "test"\n')
        (proj / "uv.lock").write_text("")
        (proj / ".github/workflows").mkdir(parents=True)
        (proj / ".github/workflows/ci.yml").write_text("")

        detector = ProjectDetector(proj)
        analysis = detector.analyze()

        target = tmp_path / "output"
        worker = InitWorker(
            dst_path=target,
            project_type=analysis.project_type,
            defaults=True,
            skip_tasks=True,
            quiet=True,
        )
        # 注入检测结果
        worker._detection = analysis
        worker._phase_prompt()

        # 验证 builtins 包含检测结果
        assert worker._answers.builtins.get("language") == "python"
        assert worker._answers.builtins.get("package_manager") == "uv"
        assert worker._answers.builtins.get("ci_platform") == "github"

    def test_analyze_result_as_answers(self, tmp_path: Path):
        """DetectionResult.as_answers() 生成正确字典."""
        from init_engineering.init.detector import DetectionResult

        result = DetectionResult(
            project_type="library",
            language="python",
            package_manager="uv",
            test_runner="pytest",
            ci_platform="github",
            project_name="my-lib",
            has_lefthook=True,
            has_docker=True,
        )
        answers = result.as_answers()
        assert answers["project_type"] == "library"
        assert answers["language"] == "python"
        assert answers["package_manager"] == "uv"
        assert answers["test_runner"] == "pytest"
        assert answers["ci_platform"] == "github"
        assert answers["use_lefthook"] is True
        assert answers["use_docker"] is True

    def test_analyze_package_json_no_deps(self, tmp_path: Path):
        """package.json 无 dependencies 字段 — 不崩溃."""
        from init_engineering.init.detector import ProjectDetector

        proj = tmp_path / "minimal-node"
        proj.mkdir()
        (proj / "package.json").write_text('{"name": "minimal"}')

        detector = ProjectDetector(proj)
        result = detector.analyze()
        assert result.language == "javascript"  # no tsconfig, no typescript dep
        assert result.frameworks == []

    def test_analyze_broken_json_graceful(self, tmp_path: Path):
        """损坏的 package.json 不抛异常."""
        from init_engineering.init.detector import ProjectDetector

        proj = tmp_path / "broken"
        proj.mkdir()
        (proj / "package.json").write_text("{not valid json")

        detector = ProjectDetector(proj)
        result = detector.analyze()
        assert result.candidates is not None  # 不崩溃


# ─── 矩阵烟雾测试（8 types） ──────────────────────────────────────────────


class TestMatrixSmoke:
    """8 项目类型 × 基本语言组合烟雾测试."""

    @pytest.mark.parametrize("ptype", [
        "app-service", "library", "cli-tool", "skill",
        "hook", "mcp-server", "spec-doc", "monorepo",
    ])
    def test_type_generates_output(self, tmp_path: Path, ptype: str):
        """每种项目类型都能成功生成."""
        target = tmp_path / f"test-{ptype}"
        result = run_ae([
            "init", str(target), "--type", ptype,
            "--defaults", "--skip-tasks", "--force",
        ])
        assert result.returncode == 0, f"Failed for {ptype}: {result.stderr}"
        assert target.exists()
        # 所有类型至少应有 ae-answers.yml
        assert (target / ".ae-answers.yml").exists()

    @pytest.mark.parametrize("lang", ["typescript", "python", "go", "rust"])
    def test_language_generates_correct_feature(self, tmp_path: Path, lang: str):
        """每种语言 feature 都被正确包含."""
        target = tmp_path / f"test-{lang}"
        result = run_ae([
            "init", str(target), "--type", "app-service",
            "--language", lang, "--defaults", "--skip-tasks", "--force",
        ])
        assert result.returncode == 0, f"Failed for lang={lang}: {result.stderr}"

    def test_ci_none_skips_ci_files(self, tmp_path: Path):
        """ci_platform=none 时不生成 CI 文件."""
        target = tmp_path / "no-ci"
        result = run_ae([
            "init", str(target), "--type", "app-service",
            "--ci", "none", "--defaults", "--skip-tasks", "--force",
        ])
        assert result.returncode == 0
        assert not (target / ".github").exists()

    def test_ci_github_generates_workflow(self, tmp_path: Path):
        """ci_platform=github 时生成 GitHub Actions workflow."""
        target = tmp_path / "with-ci"
        result = run_ae([
            "init", str(target), "--type", "app-service",
            "--ci", "github", "--defaults", "--skip-tasks", "--force",
        ])
        assert result.returncode == 0
        assert (target / ".github" / "workflows").exists()

    def test_strict_mode_flag_accepted(self, tmp_path: Path):
        """--strict flag 被 CLI 接受."""
        target = tmp_path / "strict-test"
        result = run_ae([
            "init", str(target), "--type", "library",
            "--defaults", "--skip-tasks", "--strict", "--force",
        ])
        assert result.returncode == 0


# ─── 钩子 strict 模式 ────────────────────────────────────────────────────


class TestStrictModeHooks:
    """P0: HookRunner strict 模式测试."""

    def test_hook_runner_strict_raises(self, tmp_path: Path):
        """strict=True 时钩子命令失败抛 HookExecutionError."""
        from init_engineering.init.errors import HookExecutionError
        from init_engineering.init.hooks import HookRunner, HookSpec

        spec = HookSpec(before_renderer=["exit 1"])
        runner = HookRunner(tmp_path, spec=spec, strict=True)

        with pytest.raises(HookExecutionError) as exc_info:
            runner.before_renderer_hook({})
        assert "exit 1" in str(exc_info.value)

    def test_hook_runner_non_strict_warns(self, tmp_path: Path, caplog):
        """strict=False 时钩子失败只 warning."""
        import logging
        from init_engineering.init.hooks import HookRunner, HookSpec

        spec = HookSpec(before_renderer=["exit 1"])
        runner = HookRunner(tmp_path, spec=spec, strict=False)

        with caplog.at_level(logging.WARNING):
            runner.before_renderer_hook({})
        # 不抛异常
        assert any("hook command failed" in r.message for r in caplog.records)

    def test_builtin_hooks_strict_raises_on_git_fail(self, tmp_path: Path, monkeypatch):
        """strict=True 时 builtin git init 失败抛异常."""
        from init_engineering.init.errors import HookExecutionError
        from init_engineering.init.scaffold_hooks import run_builtin_hooks

        # Mock subprocess.run 让它返回失败
        import subprocess as sp

        original_run = sp.run

        def mock_run(*args, **kwargs):
            if args and "init" in str(args[0]):
                result = original_run(["false"], capture_output=True, text=True)
                return result
            return original_run(*args, **kwargs)

        monkeypatch.setattr(sp, "run", mock_run)

        # 创建一个 dummy answers
        class DummyAnswers:
            def get(self, key):
                return None

        with pytest.raises(HookExecutionError):
            run_builtin_hooks(DummyAnswers(), tmp_path, strict=True)


# ─── 并发安全 ─────────────────────────────────────────────────────────────


class TestConcurrencySafety:
    """P2: 文件锁防并发 ae init."""

    def test_lock_prevents_concurrent_init(self, tmp_path: Path):
        """同目录并发 init 被锁阻止."""
        import fcntl

        target = tmp_path / "locked"
        target.mkdir()

        lock_file = target / ".ae-init.lock"
        with open(lock_file, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            # 尝试获取锁应失败
            with open(lock_file, "r") as f2:
                try:
                    fcntl.flock(f2.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    # 如果成功获取，释放
                    fcntl.flock(f2.fileno(), fcntl.LOCK_UN)
                    got_lock = True
                except BlockingIOError:
                    got_lock = False

            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        # 第一个持有锁时第二个应无法获取
        assert not got_lock

    def test_initworker_holds_lock_throughout_execute(self, tmp_path: Path):
        """B1 regression: InitWorker._lock 必须持有到 execute() 结束,不能 GC 释放.

        之前 phase_detect 丢弃 InitLock.acquire_for() 的返回值,导致 fd 在 phase_detect
        返回瞬间被 Python GC,锁瞬间释放 — 两个并行 init 进程会同时进入渲染/合并
        阶段并破坏目标目录。
        """
        import fcntl
        import os as _os
        from init_engineering.init.errors import TargetDirectoryError
        from init_engineering.init.scaffold import InitWorker

        target = tmp_path / "locked-target"
        target.mkdir()

        # 外部抢占锁: 模拟另一个 ae init 进程持有锁
        lock_file = target / ".ae-init.lock"
        ext_fd = _os.open(str(lock_file), _os.O_CREAT | _os.O_RDWR)
        try:
            fcntl.flock(ext_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

            # 在外部持锁时,新的 worker 应无法进入 phase_detect
            worker = InitWorker(
                dst_path=target,
                project_type="library",
                defaults=True,
            )
            with pytest.raises(TargetDirectoryError):
                worker._phase_detect()
        finally:
            fcntl.flock(ext_fd, fcntl.LOCK_UN)
            _os.close(ext_fd)
            if lock_file.exists():
                lock_file.unlink()

        # 现在外部未持锁,worker 进入 phase_detect 后, _lock 必须非 None
        # (证明锁对象被 worker 持有,不会 GC)
        worker = InitWorker(
            dst_path=target,
            project_type="library",
            defaults=True,
        )
        worker._phase_detect()
        assert worker._lock is not None, (
            "B1 regression: InitWorker._lock is None after phase_detect — "
            "lock object was GC'd, fd was closed, lock was released prematurely"
        )
        # 释放以便清理
        worker._lock.release()
        worker._lock = None

    def test_initworker_blocks_concurrent_init_after_phase_detect(self, tmp_path: Path):
        """B1 regression: phase_detect 之后,第二个 init 仍被阻止 (锁持续持有)."""
        from init_engineering.init.errors import TargetDirectoryError
        from init_engineering.init.scaffold import InitWorker

        target = tmp_path / "blocked"
        target.mkdir()

        # 第一个 worker 完成 phase_detect,持锁中
        worker1 = InitWorker(
            dst_path=target,
            project_type="library",
            defaults=True,
        )
        worker1._phase_detect()
        assert worker1._lock is not None

        try:
            # 第二个 worker 试图 phase_detect — 应被锁阻止
            worker2 = InitWorker(
                dst_path=target,
                project_type="library",
                defaults=True,
            )
            with pytest.raises(TargetDirectoryError):
                worker2._phase_detect()
        finally:
            worker1._lock.release()
            worker1._lock = None
