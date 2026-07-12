"""路径安全工具 — resolve_user_path 供 skill.py 使用。

来源: init/_shared/path_utils.py (WR-02 封装修复: skill.py 不应 import init 私有子包)。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

_logger = logging.getLogger(__name__)


def resolve_user_path(path: str | None, cwd: Path) -> Path:
    """安全解析用户提供的路径。

    - None / "." → cwd
    - 其他 → expanduser → resolve（存在时）/ absolute（非存在时）
    - 非存在路径中含 .. 穿越家目录时，抛出 ValueError
    """
    if path in (None, "."):
        return cwd
    raw = Path(path)
    expanded = raw.expanduser()
    try:
        return expanded.resolve()
    except (FileNotFoundError, OSError):
        _logger.debug("resolve failed for %r, using abspath fallback", path, exc_info=True)
        resolved = Path(os.path.abspath(str(expanded)))
        home = Path.home().resolve()
        try:
            resolved.resolve().relative_to(home)
        except ValueError as e:
            if not str(resolved).startswith(str(home)):
                raise ValueError(
                    f"路径指向家目录以外: {path!r} → {resolved}"
                ) from e
        return resolved
