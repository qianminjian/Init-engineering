"""Helper detection functions — 拆自 detector.py (v2.5: 382→可控).

设计:
- detect_*() / signature_matches() / check_pkg_dep() 一律下沉到本模块
- detector.py 只保留 datatypes + ProjectDetector class
- detect_package_manager/detect_test_runner/detect_ci_platform 提取到
  _shared.detection (config/ 层可跨层复用, 不破坏 config → init 层级)
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

_logger = logging.getLogger(__name__)

def check_pkg_dep(target_dir: Path, check_fn: Callable[[dict], bool]) -> bool:
    """Check package.json dependencies.

    Args:
        target_dir: project root
        check_fn: callback receiving dependencies dict, returning bool
    """
    pkg = target_dir / "package.json"
    if not pkg.exists():
        return False
    try:
        data = json.loads(pkg.read_text())
        return check_fn(data.get("dependencies", {}))
    except (json.JSONDecodeError, OSError):
        _logger.debug("无法解析 package.json: %s", pkg, exc_info=True)
        return False


def signature_matches(target_dir: Path, sig: str) -> bool:
    """Check if a signature matches — supports glob wildcards."""
    if sig.endswith("/"):
        return (target_dir / sig).exists()
    if "*" in sig or "?" in sig or "[" in sig:
        import fnmatch

        rel_dir = sig.rsplit("/", 1)[0] if "/" in sig else ""
        pattern = sig.rsplit("/", 1)[-1]
        base = target_dir / rel_dir if rel_dir else target_dir
        if not base.exists():
            return False
        for entry in base.iterdir():
            if entry.is_file() and fnmatch.fnmatch(entry.name, pattern):
                return True
        return False
    return (target_dir / sig).exists()
