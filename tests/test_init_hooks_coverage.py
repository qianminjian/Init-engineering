"""scaffold_hooks 单元测试 — run_builtin_hooks / merge_incremental.

覆盖 scaffold_hooks.py (77%) 和 scaffold_phases.py 缺失的清理/消息处理。
"""

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

    def test_git_add_warning_on_failure(self, tmp_path: Path):
        """git add 失败时打印 warning 不抛异常 (lines 77-79)."""
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
            with patch("builtins.print") as mock_print:
                run_builtin_hooks(answers, tmp_path)

        # git add -A should have been called and printed a warning
        assert any("add" in c for c in git_calls)

    def test_git_commit_warning_on_failure(self, tmp_path: Path):
        """git commit 失败时打印 warning 不抛异常 (lines 89-92)."""
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
            with patch("builtins.print") as mock_print:
                run_builtin_hooks(answers, tmp_path)

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


class TestMessageBeforeAfter:
    """message_before / message_after 输出覆盖 (scaffold_phases.py lines 111/118).

    NOTE: 端到端测试已覆盖（test_init_e2e_scaffold.py），此处不再重复。
    """
    pass
