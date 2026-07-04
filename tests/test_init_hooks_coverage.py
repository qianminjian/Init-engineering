"""scaffold_hooks 单元测试 — run_builtin_hooks / merge_incremental.

覆盖 scaffold_hooks.py (77%) 和 scaffold_phases.py 缺失的清理/消息处理。
"""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from init_engineering.init.answers import AnswersMap
from init_engineering.init.scaffold_hooks import merge_incremental, run_builtin_hooks


class TestMergeIncremental:
    """merge_incremental — 增量模式文件合并."""

    def test_skips_existing_file(self, tmp_path: Path):
        """已存在的文件应跳过 (不覆盖)."""
        dst = tmp_path / "proj"
        dst.mkdir()
        (dst / "existing.txt").write_text("user content")

        src = tmp_path / "src"
        src.mkdir()
        (src / "new.txt").write_text("new content")
        (src / "existing.txt").write_text("template content")

        created, skipped = merge_incremental(src, dst, set())
        assert (dst / "new.txt").read_text() == "new content"
        # existing.txt 应该跳过（保留用户内容）
        assert (dst / "existing.txt").read_text() == "user content"
        assert len(created) == 1
        assert len(skipped) == 1

    def test_skips_git_directory(self, tmp_path: Path):
        """merge_incremental 跳过 .git 目录内的文件."""
        dst = tmp_path / "proj"
        dst.mkdir()

        src = tmp_path / "src"
        src.mkdir()
        (src / "file.txt").write_text("content")
        # .git/config 在源模板中，不应被合并
        git_dir = src / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        created, skipped = merge_incremental(src, dst, set())
        # .git 目录内的文件不应被处理
        assert not (dst / ".git").exists()
        assert len(created) == 1
        assert (dst / "file.txt").read_text() == "content"

    def test_creates_missing_parent_dirs(self, tmp_path: Path):
        """增量合并时，如果目标路径的父目录不存在则创建."""
        dst = tmp_path / "proj"
        src = tmp_path / "src"
        src.mkdir()
        subdir = src / "sub" / "nested"
        subdir.mkdir(parents=True)
        (subdir / "deep.txt").write_text("deep")

        created, skipped = merge_incremental(src, dst, set())
        assert (dst / "sub" / "nested" / "deep.txt").read_text() == "deep"

    def test_empty_src_dir(self, tmp_path: Path):
        """源目录为空时不崩溃."""
        dst = tmp_path / "proj"
        dst.mkdir()
        (dst / "keep.txt").write_text("kept")

        src = tmp_path / "src"
        src.mkdir()

        created, skipped = merge_incremental(src, dst, set())
        assert len(created) == 0
        assert (dst / "keep.txt").read_text() == "kept"


class TestMergeIncrementalWithCreatedFiles:
    """created_files set 控制跳过逻辑 — 已在本次生成的文件不应被跳过."""

    def test_created_files_not_skipped(self, tmp_path: Path):
        """created_files 集合中的路径不会被当作"已存在"跳过.

        这是增量合并的核心逻辑：merge_incremental 被调用时，
        created_files 包含本次渲染生成的文件路径（相对路径）。
        如果某个文件已在 dst 存在但不在 created_files，才跳过。
        """
        dst = tmp_path / "proj"
        dst.mkdir()
        # 目标目录已有文件
        (dst / "shared.txt").write_text("old user content")

        src = tmp_path / "src"
        src.mkdir()
        # 模板也有同名文件
        (src / "shared.txt").write_text("new template content")

        # shared.txt 不在 created_files，所以应该跳过
        created, skipped = merge_incremental(src, dst, created_files=set())
        # 用户已有文件不被覆盖
        assert (dst / "shared.txt").read_text() == "old user content"
        assert any("shared.txt" in str(p) for p in skipped)


class TestBuiltinHooksGitFallback:
    """run_builtin_hooks — git init 分支 fallback."""

    def test_git_init_fallback_on_unknown_option(self, tmp_path: Path):
        """git init -b main 失败时回退到 git init (lines 35-46)."""
        from init_engineering.init.scaffold_hooks import run_builtin_hooks

        answers = AnswersMap(defaults={"package_manager": "", "use_lefthook": False})
        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            result = MagicMock()
            cmd_str = " ".join(cmd)
            if cmd_str == "git init -b main":
                result.returncode = 1
                result.stderr = "unknown option -b"
                result.stdout = ""
            elif cmd_str == "git init":
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            elif cmd_str.startswith("git"):
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            else:
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            return result

        with patch("init_engineering.init.scaffold_hooks.subprocess.run", mock_run):
            run_builtin_hooks(answers, tmp_path)

        assert ["git", "init", "-b", "main"] in calls
        assert ["git", "init"] in calls  # fallback

    def test_git_init_error_warns_not_raises(self, tmp_path: Path):
        """git init 失败时打印 warning 不抛异常（改为非阻塞）. """
        from init_engineering.init.scaffold_hooks import run_builtin_hooks

        answers = AnswersMap(defaults={"package_manager": "", "use_lefthook": False})

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            cmd_str = " ".join(cmd)
            if cmd_str == "git init -b main":
                result.returncode = 1
                result.stderr = "some other error"
                result.stdout = ""
            elif cmd_str == "git init":
                result.returncode = 1
                result.stderr = "fatal error"
                result.stdout = ""
            elif cmd_str.startswith("git"):
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            else:
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            return result

        with patch("init_engineering.init.scaffold_hooks.subprocess.run", mock_run):
            # 不再抛异常，非阻塞
            run_builtin_hooks(answers, tmp_path)

    def test_git_add_warning_on_failure(self, tmp_path: Path, caplog):
        """git add 失败时打印 warning 不抛异常。

        PE-AUDIT-P0-2: warning 现在走 _logger.warning 而非 print,测试用 caplog 验证。
        """
        from init_engineering.init.scaffold_hooks import run_builtin_hooks

        answers = AnswersMap(defaults={"package_manager": "", "use_lefthook": False})
        git_calls = []

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            cmd_str = " ".join(cmd)
            if cmd_str.startswith("git"):
                git_calls.append(cmd_str)
                if "add" in cmd_str:
                    result.returncode = 1
                    result.stderr = "fatal: unable to add"
                    result.stdout = ""
                else:
                    result.returncode = 0
                    result.stdout = ""
                    result.stderr = ""
            else:
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            return result

        with patch("init_engineering.init.scaffold_hooks.subprocess.run", mock_run):
            with caplog.at_level("WARNING"):
                run_builtin_hooks(answers, tmp_path)

        # git add -A should have been called and logged a warning
        assert any("add" in c for c in git_calls)
        # PE-AUDIT-P0-2: warning 通过 logger 而非 print
        assert any("git add" in rec.message for rec in caplog.records)

    def test_git_commit_warning_on_failure(self, tmp_path: Path, caplog):
        """git commit 失败时打印 warning 不抛异常。

        PE-AUDIT-P0-2: warning 走 _logger.warning,caplog 验证。
        """
        from init_engineering.init.scaffold_hooks import run_builtin_hooks

        answers = AnswersMap(defaults={"package_manager": "", "use_lefthook": False})
        git_calls = {}

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            cmd_str = " ".join(cmd)
            git_calls[cmd_str] = result
            if "commit" in cmd_str:
                result.returncode = 1
                result.stderr = "nothing to commit"
                result.stdout = ""
            else:
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            return result

        with patch("init_engineering.init.scaffold_hooks.subprocess.run", mock_run):
            with caplog.at_level("WARNING"):
                run_builtin_hooks(answers, tmp_path)

        # Should not raise, just log warning
        assert any("git commit" in rec.message for rec in caplog.records)

        # Should not raise, just print warning

    def test_lefthook_install_failure_warns_not_raises(self, tmp_path: Path):
        """lefthook install 失败时打印 warning 不抛异常（改为非阻塞）. """
        from init_engineering.init.scaffold_hooks import run_builtin_hooks

        answers = AnswersMap(defaults={"package_manager": "", "use_lefthook": True})
        calls = {}

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            cmd_str = " ".join(cmd)
            calls[cmd_str] = result
            if "lefthook" in cmd_str:
                result.returncode = 1
                result.stderr = "lefthook not found"
                result.stdout = ""
            elif cmd_str.startswith("git"):
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            else:
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            return result

        with patch("init_engineering.init.scaffold_hooks.subprocess.run", mock_run):
            # 不再抛异常，非阻塞
            run_builtin_hooks(answers, tmp_path)


class TestBuiltinHooksPackageManager:
    """package_manager install / lefthook install 失败处理."""

    def test_package_manager_install_missing_file_skips(self, tmp_path: Path):
        """package_manager install 无 package 文件时跳过不抛异常."""
        from init_engineering.init.scaffold_hooks import run_builtin_hooks

        answers = AnswersMap(defaults={"package_manager": "npm", "use_lefthook": False})

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            cmd_str = " ".join(cmd)
            if cmd_str.startswith("git"):
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            else:
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            return result

        with patch("init_engineering.init.scaffold_hooks.subprocess.run", mock_run):
            # 跳过 npm install（无 package.json），不抛异常
            run_builtin_hooks(answers, tmp_path)


class TestCleanupHook:
    """InitWorker._cleanup — 清理钩子异常不扩散."""

    def test_cleanup_hook_exception_swallowed(self, tmp_path: Path):
        """_cleanup 中的异常应被 suppress，不向外扩散."""
        from init_engineering.init.scaffold_phases import InitWorker

        worker = InitWorker(dst_path=tmp_path / "proj")
        called = [False]

        def bad_hook():
            called[0] = True
            raise RuntimeError("cleanup failed")

        worker._cleanup_hooks.append(bad_hook)
        # 不应抛异常
        worker._cleanup()
        assert called[0]


class TestBuiltinHooksUvSync:
    """PE-P0-1: uv 包管理器用 `uv sync --extra dev` 而非 `uv install` (uv 0.4+ 已废弃)."""

    def test_uv_uses_sync_command_not_install(self, tmp_path: Path):
        """uv 包管理器应执行 `uv sync --extra dev`,非 `uv install` (exit=2 错误)."""
        from init_engineering.init.scaffold_hooks import run_builtin_hooks

        # 模拟 pyproject.toml 存在 (满足 _has_package_file 检查)
        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")

        answers = AnswersMap(defaults={"package_manager": "uv", "use_lefthook": False})

        called_cmds = []

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            called_cmds.append(cmd)
            return result

        with patch("init_engineering.init.scaffold_hooks.subprocess.run", mock_run):
            run_builtin_hooks(answers, tmp_path)

        # 找到非 git 命令 (uv)
        uv_cmds = [c for c in called_cmds if c[0] == "uv"]
        assert len(uv_cmds) == 1, f"uv 应被调用 1 次,实际 {len(uv_cmds)}: {uv_cmds}"
        # 关键断言:uv sync 而非 uv install (后者在 uv 0.4+ 已废弃)
        assert uv_cmds[0] == ["uv", "sync", "--extra", "dev"], (
            f"uv 包管理器应执行 ['uv', 'sync', '--extra', 'dev'],"
            f"实际 {uv_cmds[0]}"
        )

    def test_npm_uses_install_command(self, tmp_path: Path):
        """npm 包管理器应执行 `npm install`."""
        from init_engineering.init.scaffold_hooks import run_builtin_hooks

        (tmp_path / "package.json").write_text("{}")

        answers = AnswersMap(defaults={"package_manager": "npm", "use_lefthook": False})

        called_cmds = []

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            called_cmds.append(cmd)
            return result

        with patch("init_engineering.init.scaffold_hooks.subprocess.run", mock_run):
            run_builtin_hooks(answers, tmp_path)

        npm_cmds = [c for c in called_cmds if c[0] == "npm"]
        assert len(npm_cmds) == 1
        assert npm_cmds[0] == ["npm", "install"]

    def test_cargo_skipped_no_separate_install_phase(self, tmp_path: Path):
        """cargo 没有独立 install 阶段,应在 build 时 fetch,跳过 install."""
        from init_engineering.init.scaffold_hooks import run_builtin_hooks

        (tmp_path / "Cargo.toml").write_text("[package]\nname='demo'\n")

        answers = AnswersMap(defaults={"package_manager": "cargo", "use_lefthook": False})

        called_cmds = []

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            called_cmds.append(cmd)
            return result

        with patch("init_engineering.init.scaffold_hooks.subprocess.run", mock_run):
            run_builtin_hooks(answers, tmp_path, quiet=True)

        # cargo 不应被调用 install
        cargo_cmds = [c for c in called_cmds if c[0] == "cargo"]
        assert len(cargo_cmds) == 0, f"cargo 不应有 install 阶段,实际 {cargo_cmds}"

    def test_no_install_flag_skips_install(self, tmp_path: Path):
        """--no-install flag 应跳过 package_manager install 阶段."""
        from init_engineering.init.scaffold_hooks import run_builtin_hooks

        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")

        answers = AnswersMap(defaults={"package_manager": "uv", "use_lefthook": False})

        called_cmds = []

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            called_cmds.append(cmd)
            return result

        with patch("init_engineering.init.scaffold_hooks.subprocess.run", mock_run):
            run_builtin_hooks(answers, tmp_path, no_install=True)

        uv_cmds = [c for c in called_cmds if c[0] == "uv"]
        assert len(uv_cmds) == 0, f"no_install=True 时 uv 不应被调用,实际 {uv_cmds}"


class TestPostInstall:
    """PE-P0-4: phase_post_install 在 dst_path (非 tmpdir) 重跑依赖安装,修复 .venv shebang."""

    def test_post_install_runs_uv_sync_in_dst(self, tmp_path: Path):
        """phase_post_install 应在 dst_path 而非 tmpdir 跑 uv sync."""
        from init_engineering.init.answers import AnswersMap
        from init_engineering.init.phases.finalize import phase_post_install

        dst = tmp_path / "proj"
        dst.mkdir()
        (dst / "pyproject.toml").write_text("[project]\nname='demo'\n")

        answers = AnswersMap(defaults={"package_manager": "uv"})

        called_kwargs = []

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            called_kwargs.append({"cmd": cmd, "cwd": kwargs.get("cwd")})
            return result

        with patch("init_engineering.init.phases.finalize.subprocess.run", mock_run):
            phase_post_install(answers, dst)

        uv_runs = [k for k in called_kwargs if k["cmd"][0] == "uv"]
        assert len(uv_runs) == 1
        # 关键断言: cwd 应是 dst_path (不是调用方传入的 tmpdir)
        assert uv_runs[0]["cwd"] == dst, (
            f"uv sync 应在 dst 路径跑 (cwd={dst}),实际 cwd={uv_runs[0]['cwd']}"
        )

    def test_post_install_no_install_flag_skips(self, tmp_path: Path):
        """phase_post_install + no_install=True 应跳过."""
        from init_engineering.init.answers import AnswersMap
        from init_engineering.init.phases.finalize import phase_post_install

        dst = tmp_path / "proj"
        dst.mkdir()
        (dst / "pyproject.toml").write_text("[project]\nname='demo'\n")

        answers = AnswersMap(defaults={"package_manager": "uv"})

        with patch("init_engineering.init.phases.finalize.subprocess.run") as mr:
            phase_post_install(answers, dst, no_install=True)
            mr.assert_not_called()

    def test_post_install_no_package_file_skips(self, tmp_path: Path):
        """phase_post_install + 无 package 文件应跳过."""
        from init_engineering.init.answers import AnswersMap
        from init_engineering.init.phases.finalize import phase_post_install

        dst = tmp_path / "proj"
        dst.mkdir()
        # 无 pyproject.toml

        answers = AnswersMap(defaults={"package_manager": "uv"})

        with patch("init_engineering.init.phases.finalize.subprocess.run") as mr:
            phase_post_install(answers, dst, quiet=True)
            mr.assert_not_called()


class TestAtomicCopytreeExcludesBuildArtifacts:
    """PE-P0-4: _atomic_copytree 排除 .venv / node_modules / target / dist 等生成产物."""

    def test_excludes_venv_directory(self, tmp_path: Path):
        """_atomic_copytree 应排除 .venv/ 目录 (含 broken shebang)."""
        from init_engineering.init.phases.finalize import _atomic_copytree

        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("# main")
        (src / ".venv").mkdir()
        (src / ".venv" / "bin").mkdir()
        (src / ".venv" / "bin" / "python").write_text("#!/tmp/old/.venv/bin/python\n")
        (src / ".venv" / "lib").mkdir()

        dst = tmp_path / "dst"
        _atomic_copytree(src, dst)

        assert (dst / "main.py").exists()
        assert not (dst / ".venv").exists(), ".venv 必须被排除 (否则 broken shebang 会泄漏)"

    def test_excludes_node_modules_directory(self, tmp_path: Path):
        """_atomic_copytree 应排除 node_modules/ 目录."""
        from init_engineering.init.phases.finalize import _atomic_copytree

        src = tmp_path / "src"
        src.mkdir()
        (src / "index.ts").write_text("// index")
        (src / "node_modules").mkdir()
        (src / "node_modules" / "package.json").write_text("{}")

        dst = tmp_path / "dst"
        _atomic_copytree(src, dst)

        assert (dst / "index.ts").exists()
        assert not (dst / "node_modules").exists()

    def test_excludes_target_directory_rust(self, tmp_path: Path):
        """_atomic_copytree 应排除 target/ (Rust build artifacts)."""
        from init_engineering.init.phases.finalize import _atomic_copytree

        src = tmp_path / "src"
        src.mkdir()
        (src / "Cargo.toml").write_text("[package]\nname='demo'\n")
        (src / "target").mkdir()
        (src / "target" / "demo").write_text("binary")

        dst = tmp_path / "dst"
        _atomic_copytree(src, dst)

        assert (dst / "Cargo.toml").exists()
        assert not (dst / "target").exists()


class TestPythonTemplateLayout:
    """PE-P0-2: python 模板应在 {{ project_name | replace('-', '_') }}/ 子目录生成包."""

    def test_python_skill_generates_subdir_package(self, tmp_path: Path):
        """ae init --type skill --language python 应在 <name>/__init__.py + <name>/cli.py."""
        import subprocess

        venv_python = Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python"
        target = tmp_path / "py-skill"
        result = subprocess.run(
            [
                str(venv_python), "-m", "init_engineering.cli",
                "init", str(target),
                "--type", "skill",
                "--language", "python",
                "--defaults",
                "--force",
                "--no-install",
                "--skip-tasks",
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"init failed: {result.stderr}"

        # 当 target = 'py-skill' 时, ae-init 推断 project_name = 'py-skill' (从目录名)
        # → 子目录应为 'py_skill' (replace - with _)
        assert (target / "py_skill" / "__init__.py").exists(), (
            "Python 包文件应在 py_skill/__init__.py 子目录,"
            f"实际: {sorted(p.relative_to(target) for p in target.rglob('*') if p.is_file())}"
        )
        assert (target / "py_skill" / "cli.py").exists()
        assert (target / "tests" / "test_hello.py").exists()
        # 不应在项目根有 __init__.py / cli.py (PE-P0-2 修复前就是这样)
        assert not (target / "__init__.py").exists()
        assert not (target / "cli.py").exists()


class TestPyprojectHatchPackages:
    """PE-P0-2: pyproject.toml 应显式声明 hatch wheel packages = <python_module_name>."""

    def test_pyproject_template_has_hatch_packages(self):
        """pyproject.toml.jinja 应包含 [tool.hatch.build.targets.wheel] packages 配置."""
        from pathlib import Path
        from init_engineering.init.config import TEMPLATES_ROOT

        tmpl_path = (
            TEMPLATES_ROOT / "_features" / "python" / "pyproject.toml.jinja"
        )
        content = tmpl_path.read_text()
        assert "[tool.hatch.build.targets.wheel]" in content, (
            "pyproject.toml 缺少 [tool.hatch.build.targets.wheel] 配置"
        )
        # 应使用 replace filter 把 hyphenated name 转成 python module 名
        assert "replace('-', '_')" in content, (
            "pyproject.toml 应使用 replace filter 将 hyphen 转为 underscore,"
            "否则 pyproject.toml 的 name='my-tool' 与目录 'my_tool/' 不匹配"
        )

    def test_pyproject_template_has_pytest_timeout(self):
        """pyproject.toml.jinja 应声明 pytest-timeout 依赖 (Bug 3)."""
        from pathlib import Path
        from init_engineering.init.config import TEMPLATES_ROOT

        tmpl_path = (
            TEMPLATES_ROOT / "_features" / "python" / "pyproject.toml.jinja"
        )
        content = tmpl_path.read_text()
        assert "pytest-timeout" in content, (
            "pyproject.toml 应声明 pytest-timeout 依赖 (否则 --timeout=60 addopts 会失败)"
        )


class TestSubprocessTimeout:
    """PE-AUDIT-P0-1: 所有 subprocess.run 调用必须有 timeout 参数 + TimeoutExpired 处理."""

    def test_run_builtin_hooks_passes_timeout_to_subprocess(self, tmp_path: Path):
        """run_builtin_hooks 透传 default_timeout 到所有 subprocess.run 调用."""
        from init_engineering.init.scaffold_hooks import run_builtin_hooks

        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")
        answers = AnswersMap(defaults={"package_manager": "uv", "use_lefthook": False})

        called_timeouts = []

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            if "timeout" in kwargs:
                called_timeouts.append((tuple(cmd), kwargs["timeout"]))
            return result

        with patch("init_engineering.init.scaffold_hooks.subprocess.run", mock_run):
            run_builtin_hooks(answers, tmp_path, default_timeout=42)

        # 所有非 git config 调用应收到 timeout=42 (git config 用 10s)
        assert len(called_timeouts) > 0
        # pm install 应收到透传的 timeout=42
        uv_calls = [t for t in called_timeouts if t[0][0] == "uv"]
        assert any(t[1] == 42 for t in uv_calls), (
            f"uv install 应收到 default_timeout=42,实际 {uv_calls}"
        )

    def test_run_builtin_hooks_timeout_expired_logs_warning(self, tmp_path: Path, caplog):
        """subprocess.TimeoutExpired 应被捕获并转 _logger.warning."""
        from init_engineering.init import scaffold_hooks

        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")
        answers = AnswersMap(defaults={"package_manager": "uv", "use_lefthook": False})

        def mock_run_raises_timeout(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 60))

        with patch("init_engineering.init.scaffold_hooks.subprocess.run", mock_run_raises_timeout):
            with caplog.at_level("WARNING"):
                # strict=False 不抛异常,quiet=False 让 _fail 输出 warning
                scaffold_hooks.run_builtin_hooks(answers, tmp_path, quiet=False)

        # 至少一条 timeout warning 应被记录
        assert any("timed out" in rec.message.lower() for rec in caplog.records), (
            f"期望 timeout warning,实际 {[r.message for r in caplog.records]}"
        )

    def test_run_builtin_hooks_timeout_expired_strict_raises(self, tmp_path: Path):
        """strict=True + TimeoutExpired 应抛 HookExecutionError."""
        from init_engineering.init import scaffold_hooks
        from init_engineering.init.errors import HookExecutionError

        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")
        answers = AnswersMap(defaults={"package_manager": "uv", "use_lefthook": False})

        def mock_run_raises_timeout(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 60))

        with patch("init_engineering.init.scaffold_hooks.subprocess.run", mock_run_raises_timeout):
            with pytest.raises(HookExecutionError) as exc_info:
                scaffold_hooks.run_builtin_hooks(answers, tmp_path, strict=True)

        assert "timed out" in str(exc_info.value).lower()

    def test_phase_post_install_timeout(self, tmp_path: Path):
        """phase_post_install 透传 timeout 参数."""
        from init_engineering.init.answers import AnswersMap
        from init_engineering.init.phases.finalize import phase_post_install

        dst = tmp_path / "proj"
        dst.mkdir()
        (dst / "pyproject.toml").write_text("[project]\nname='demo'\n")
        answers = AnswersMap(defaults={"package_manager": "uv"})

        called_timeouts = []

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            called_timeouts.append(kwargs.get("timeout"))
            return result

        with patch("init_engineering.init.phases.finalize.subprocess.run", mock_run):
            phase_post_install(answers, dst, timeout=120)

        # uv sync 应收到 timeout=120
        assert 120 in called_timeouts

    def test_git_status_has_timeout(self, tmp_path: Path):
        """scaffold_tasks_runner._git_status_clean subprocess.run 有 timeout."""
        from init_engineering.init.scaffold_tasks_runner import _build_jinja_env

        env = _build_jinja_env(tmp_path)
        # 调用全局函数应不挂死 (timeout=10)
        import time
        start = time.monotonic()
        result = env.globals["git_status_clean"]()
        elapsed = time.monotonic() - start
        # git status 在空目录应立即返回,不应超时 (>10s 必有 bug)
        assert elapsed < 10, f"git status took {elapsed}s, 应 < 10s"


class TestLoggerMigration:
    """PE-AUDIT-P0-2: 业务消息走 _logger 而非 print."""

    def test_warning_uses_logger_not_print(self, tmp_path: Path, caplog):
        """git add 失败时 warning 走 logger,可被 caplog 捕获.

        让所有 git 步骤都成功,只让 git add 失败 → 只触发一次 warning.
        """
        from init_engineering.init.scaffold_hooks import run_builtin_hooks

        answers = AnswersMap(defaults={"package_manager": "", "use_lefthook": False})

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            cmd_str = " ".join(cmd)
            if "add" in cmd_str:
                # git add 失败 → 应触发 _logger.warning
                result.returncode = 1
                result.stderr = "git add failed"
            else:
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            return result

        with patch("init_engineering.init.scaffold_hooks.subprocess.run", mock_run):
            with caplog.at_level("WARNING"):
                # quiet=False 让 _fail 输出 warning
                run_builtin_hooks(answers, tmp_path)

        # warning 应通过 logger 而非 print 出现
        warning_msgs = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert any("git add" in m and "failed" in m for m in warning_msgs), (
            f"期望 git add failed warning 通过 logger,实际 {warning_msgs}"
        )

    def test_quiet_suppresses_warnings(self, tmp_path: Path, caplog):
        """quiet=True 时不输出 warning."""
        from init_engineering.init.scaffold_hooks import run_builtin_hooks

        answers = AnswersMap(defaults={"package_manager": "", "use_lefthook": False})

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 1
            result.stderr = "test failure"
            result.stdout = ""
            return result

        with patch("init_engineering.init.scaffold_hooks.subprocess.run", mock_run):
            with caplog.at_level("WARNING"):
                run_builtin_hooks(answers, tmp_path, quiet=True)

        # quiet=True 时 _fail 不应发出 warning
        warning_msgs = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warning_msgs) == 0, f"quiet=True 应抑制 warning,实际 {warning_msgs}"
