"""tests for init_engineering.init._shared.exclude module.

Ref: Copier _main.py:753 match_exclude(self) -> Callable[[Path], bool].
"""

from __future__ import annotations

from pathlib import Path

import pytest

from init_engineering.init._shared.exclude import (
    default_match_exclude,
    parse_exclude_callback,
)


class TestDefaultMatchExclude:
    """Test default_match_exclude behavior."""

    def test_excludes_git(self) -> None:
        """Git directory should be excluded."""
        assert default_match_exclude(Path(".git"))
        assert default_match_exclude(Path("project/.git"))
        assert default_match_exclude(Path("project/.git/config"))
        assert default_match_exclude(Path(".git/hooks"))

    def test_excludes_venv(self) -> None:
        """.venv directory should be excluded."""
        assert default_match_exclude(Path(".venv"))
        assert default_match_exclude(Path("project/.venv"))
        assert default_match_exclude(Path("project/.venv/lib"))

    def test_excludes_pycache(self) -> None:
        """__pycache__ directory should be excluded."""
        assert default_match_exclude(Path("__pycache__"))
        assert default_match_exclude(Path("project/__pycache__"))
        assert default_match_exclude(Path("project/__pycache__/module.pyc"))

    def test_excludes_node_modules(self) -> None:
        """node_modules directory should be excluded."""
        assert default_match_exclude(Path("node_modules"))
        assert default_match_exclude(Path("project/node_modules"))
        assert default_match_exclude(Path("project/node_modules/package/index.js"))

    def test_excludes_ds_store(self) -> None:
        """.DS_Store file should be excluded."""
        assert default_match_exclude(Path(".DS_Store"))
        assert default_match_exclude(Path("project/.DS_Store"))
        assert default_match_exclude(Path("project/path/.DS_Store"))

    def test_excludes_env(self) -> None:
        """.env file should be excluded."""
        assert default_match_exclude(Path(".env"))
        assert default_match_exclude(Path("project/.env"))
        assert default_match_exclude(Path("project/config/.env"))

    def test_excludes_pyc(self) -> None:
        """.pyc files should be excluded."""
        assert default_match_exclude(Path("module.pyc"))
        assert default_match_exclude(Path("__pycache__/module.cpython-312.pyc"))
        assert default_match_exclude(Path("project/cache.pyc"))

    def test_includes_normal_files(self) -> None:
        """Normal files should NOT be excluded."""
        # Source files
        assert not default_match_exclude(Path("module.py"))
        assert not default_match_exclude(Path("project/module.py"))
        # Config files
        assert not default_match_exclude(Path(".gitignore"))
        assert not default_match_exclude(Path(".editorconfig"))
        assert not default_match_exclude(Path("pyproject.toml"))
        assert not default_match_exclude(Path(".ruff_config.toml"))
        # Directories
        assert not default_match_exclude(Path("src"))
        assert not default_match_exclude(Path("project/src"))
        # Special files
        assert not default_match_exclude(Path("README.md"))
        assert not default_match_exclude(Path("package.json"))

    def test_includes_nested_normal_files(self) -> None:
        """Files in excluded directories are excluded via parent path check."""
        # Note: default_match_exclude checks if ANY part is in _EXCLUDED_DIRS
        # So files inside .git, __pycache__, etc. are excluded via path parts
        assert default_match_exclude(Path(".git/config"))
        assert default_match_exclude(Path("__pycache__/module.pyc"))


class TestParseExcludeCallback:
    """Test parse_exclude_callback spec parsing."""

    def test_valid_spec(self) -> None:
        """Valid 'module:function' spec should return callable."""
        callback = parse_exclude_callback(
            "init_engineering.init._shared.exclude:default_match_exclude"
        )
        assert callable(callback)
        # Verify it works
        assert callback(Path(".git")) is True
        assert callback(Path("module.py")) is False

    def test_invalid_module(self) -> None:
        """Invalid module path should raise ImportError."""
        with pytest.raises(ImportError):
            parse_exclude_callback("nonexistent_module:func")

    def test_invalid_function(self) -> None:
        """Valid module but invalid function should raise AttributeError."""
        with pytest.raises(AttributeError):
            parse_exclude_callback(
                "init_engineering.init._shared.exclude:nonexistent_func"
            )

    def test_missing_colon(self) -> None:
        """Spec without colon should raise ValueError."""
        with pytest.raises(ValueError, match="module:function"):
            parse_exclude_callback("init_engineering.init._shared.exclude")

    def test_empty_spec(self) -> None:
        """Empty spec should raise ValueError."""
        with pytest.raises(ValueError, match="module:function"):
            parse_exclude_callback("")
