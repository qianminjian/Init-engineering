"""路径安全校验工具 — is_path_under_any_root() 跨模块复用。

防御: 外部路径（external_data / !include）可能被恶意模板利用读取敏感文件。
用 os.path.realpath 双侧归一化 (macOS symlink 安全), 文件不存在时回退到 lexical 解析。

使用方: answers.py (external_data 沙箱) + config_loader.py (!include 沙箱)。
"""

from __future__ import annotations

import os
from pathlib import Path


def resolve_user_path(path: str | None, cwd: Path) -> Path:
    """安全解析用户提供的路径。

    - None / "." → cwd
    - 其他 → expanduser → resolve（存在时）/ absolute（非存在时）
    - 非存在路径中含 .. 穿越家目录时，抛出 ValueError
    """
    import os

    if path in (None, "."):
        return cwd
    raw = Path(path)
    expanded = raw.expanduser()
    try:
        return expanded.resolve()
    except (FileNotFoundError, OSError):
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


def is_path_under_any_root(file_path: Path, roots: list[Path] | list[str]) -> bool:
    """检查 file_path 是否在任一 root 下 (realpath 双侧 + lexical fallback).

    macOS symlink 安全: 文件存在时双侧 realpath 归一化; 不存在时回退 lexical。
    """
    try:
        if os.path.exists(file_path):
            target = os.path.realpath(file_path)
        else:
            target = str(file_path.resolve())
    except (OSError, RuntimeError):
        return False

    for root in roots:
        root_path = Path(root) if isinstance(root, str) else root
        try:
            root_real = os.path.realpath(root_path)
        except OSError:
            continue
        root_prefix = root_real if root_real.endswith(os.sep) else root_real + os.sep
        if target == root_real or target.startswith(root_prefix):
            return True
    return False
