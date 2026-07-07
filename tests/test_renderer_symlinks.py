"""renderer_symlinks.py 单元测试 — symlink 处理 (P1-11).

覆盖 resolve_symlink 的 3 种行为路径：
- preserve_symlinks=True: 保留 symlink / dangling 跳过 / 路径穿越拒绝
- preserve_symlinks=False: 解析内容 / dangling 跳过
"""

from pathlib import Path

import pytest

from init_engineering.init.renderer import resolve_symlink


class TestResolveSymlinkPreserve:
    """preserve_symlinks=True — 保留符号链接."""

    def test_preserve_normal_symlink(self, tmp_path: Path):
        """正常 symlink 文件 → 在目标创建新 symlink."""
        target = tmp_path / "real.txt"
        target.write_text("hello")
        src = tmp_path / "link.txt"
        src.symlink_to(target)

        dst = tmp_path / "out" / "link.txt"
        dst.parent.mkdir(parents=True, exist_ok=True)

        handled, skip_reason = resolve_symlink(src, dst, preserve_symlinks=True)
        assert handled is True
        assert skip_reason is None
        assert dst.is_symlink()
        assert dst.read_text() == "hello"

    def test_preserve_dangling_symlink(self, tmp_path: Path):
        """dangling symlink → 跳过."""
        src = tmp_path / "dangling.txt"
        src.symlink_to(tmp_path / "nonexistent.txt")

        dst = tmp_path / "out" / "dangling.txt"
        dst.parent.mkdir(parents=True, exist_ok=True)

        handled, skip_reason = resolve_symlink(src, dst, preserve_symlinks=True)
        assert handled is True
        assert skip_reason == "dangling"
        assert not dst.exists()

    def test_preserve_refuses_dotdot_target(self, tmp_path: Path):
        """含 .. 的 symlink → 抛出 TemplateRenderError.

        创建相对 symlink "../escape.txt" 并确保 resolve 后的 target 存在，
        让代码走到 os.readlink → ".." 检查分支。
        """
        # Create the resolved target so exists() check passes
        escape_target = tmp_path.parent / "escape.txt"
        escape_target.write_text("escaped")
        try:
            src = tmp_path / "evil.txt"
            src.symlink_to("../escape.txt")
            dst = tmp_path / "out" / "evil.txt"
            dst.parent.mkdir(parents=True, exist_ok=True)

            with pytest.raises(Exception) as exc_info:
                resolve_symlink(src, dst, preserve_symlinks=True)
            assert ".." in str(exc_info.value).lower()
        finally:
            escape_target.unlink(missing_ok=True)


class TestResolveSymlinkNoPreserve:
    """preserve_symlinks=False — 解析为内容."""

    def test_no_preserve_resolves_content(self, tmp_path: Path):
        """symlink → 复制实际内容."""
        target = tmp_path / "real.txt"
        target.write_text("resolved content")
        src = tmp_path / "link.txt"
        src.symlink_to(target)

        dst = tmp_path / "out" / "link.txt"
        dst.parent.mkdir(parents=True, exist_ok=True)

        handled, skip_reason = resolve_symlink(src, dst, preserve_symlinks=False)
        assert handled is True
        assert skip_reason is None
        assert dst.exists()
        assert not dst.is_symlink()
        assert dst.read_text() == "resolved content"

    def test_no_preserve_dangling_symlink(self, tmp_path: Path):
        """dangling symlink → 跳过."""
        src = tmp_path / "dangling.txt"
        src.symlink_to(tmp_path / "nonexistent.txt")

        dst = tmp_path / "out" / "dangling.txt"
        dst.parent.mkdir(parents=True, exist_ok=True)

        handled, skip_reason = resolve_symlink(src, dst, preserve_symlinks=False)
        assert handled is True
        assert skip_reason == "dangling"
        assert not dst.exists()


class TestResolveSymlinkNotSymlink:
    """非 symlink 文件."""

    def test_regular_file_not_handled(self, tmp_path: Path):
        """普通文件 → handled=False."""
        src = tmp_path / "regular.txt"
        src.write_text("plain file")

        dst = tmp_path / "out" / "regular.txt"
        dst.parent.mkdir(parents=True, exist_ok=True)

        handled, skip_reason = resolve_symlink(src, dst, preserve_symlinks=True)
        assert handled is False
        assert skip_reason is None

    def test_directory_not_handled(self, tmp_path: Path):
        """目录 → handled=False."""
        src = tmp_path / "subdir"
        src.mkdir()

        dst = tmp_path / "out" / "subdir"

        handled, skip_reason = resolve_symlink(src, dst, preserve_symlinks=True)
        assert handled is False
        assert skip_reason is None
