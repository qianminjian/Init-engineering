"""Helper detection functions — 拆自 detector.py (v2.5: 382→可控).

设计:
- detect_*() / signature_matches() / check_pkg_dep() 一律下沉到本模块
- detector.py 只保留 datatypes + ProjectDetector class
- detect_package_manager/detect_test_runner/detect_ci_platform 提取到
  _shared.detection (config/ 层可跨层复用, 不破坏 config → init 层级)
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import Callable
from pathlib import Path

_logger = logging.getLogger(__name__)


def strip_xml_ns(tag: str) -> str:
    """剥离 XML 命名空间前缀 — 如 {http://maven.apache.org/POM/4.0.0}groupId → groupId."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def check_pkg_dep(dst_path: Path, check_fn: Callable[[dict], bool]) -> bool:
    """Check package.json dependencies.

    Args:
        dst_path: project root
        check_fn: callback receiving dependencies dict, returning bool
    """
    pkg = dst_path / "package.json"
    if not pkg.exists():
        return False
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
        return check_fn(data.get("dependencies", {}))
    except (json.JSONDecodeError, OSError):
        _logger.debug("无法解析 package.json: %s", pkg, exc_info=True)
        return False


def signature_matches(dst_path: Path, sig: str, *, max_depth: int = 0) -> bool:
    """Check if a signature matches — supports glob wildcards + optional shallow recursion.

    max_depth=0: only check dst_path (default, backward compat)
    max_depth=1: check dst_path + immediate subdirectories
    max_depth=2: check dst_path + 2 levels of subdirectories
    """
    if _check_sig_at(dst_path, sig):
        return True
    if max_depth <= 0:
        return False
    try:
        for child in dst_path.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                if _check_sig_at(child, sig):
                    return True
                if max_depth >= 2:
                    for grandchild in child.iterdir():
                        if (grandchild.is_dir()
                                and not grandchild.name.startswith(".")
                                and _check_sig_at(grandchild, sig)):
                            return True
    except OSError:
        _logger.debug("递归扫描 %s 失败", dst_path, exc_info=True)
    return False


def _check_sig_at(base: Path, sig: str) -> bool:
    """Check a single directory for a signature match (no recursion)."""
    if sig.endswith("/"):
        return (base / sig).exists()
    if "*" in sig or "?" in sig or "[" in sig:
        import fnmatch

        rel_dir = sig.rsplit("/", 1)[0] if "/" in sig else ""
        pattern = sig.rsplit("/", 1)[-1]
        search_dir = base / rel_dir if rel_dir else base
        if not search_dir.exists():
            return False
        for entry in search_dir.iterdir():
            if entry.is_file() and fnmatch.fnmatch(entry.name, pattern):
                return True
        return False
    return (base / sig).exists()


def find_signatures_in_tree(
    dst_path: Path, signatures: list[str], max_depth: int = 2,
) -> dict[str, list[Path]]:
    """Find which subdirectories match which signatures — for workspace/monorepo detection.

    Returns: {sig: [matching_directory_path, ...]}
    """
    result: dict[str, list[Path]] = {}
    dirs_to_check = [dst_path]
    if max_depth >= 1:
        with contextlib.suppress(OSError):
            dirs_to_check += [
                child for child in dst_path.iterdir()
                if child.is_dir() and not child.name.startswith(".")
            ]
    for d in dirs_to_check:
        for sig in signatures:
            if _check_sig_at(d, sig):
                result.setdefault(sig, []).append(d)
    return result
