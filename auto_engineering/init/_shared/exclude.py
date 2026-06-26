"""init 默认 exclude 回调 + spec 解析工具.

来源：Copier _main.py:753 match_exclude(self) -> Callable[[Path], bool].

设计：
- default_match_exclude: 默认排除 .git/ / __pycache__/ / .venv/ / node_modules/
  以及以 . 开头的隐藏文件 / .pyc / .DS_Store.
- parse_exclude_callback: 解析 "module:function" 格式 spec, 返回可调用对象.
  解析失败时分别抛 ImportError / AttributeError / ValueError, 调用方可分别处理.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path

# 默认排除目录名（来源: Copier _template.py:DEFAULT_EXCLUDE 增强版）
_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "node_modules",
    }
)

# 默认排除文件名（任一祖先路径或文件名命中即排除）
_EXCLUDED_NAMES: frozenset[str] = frozenset(
    {
        ".DS_Store",
    }
)

# 默认排除后缀
_EXCLUDED_SUFFIXES: tuple[str, ...] = (".pyc",)


def default_match_exclude(path: Path) -> bool:
    """默认 exclude 回调 — 排除常见构建/版本控制/缓存产物.

    规则（按顺序短路求值）:
    1. 路径中任一段在 _EXCLUDED_DIRS (.git, __pycache__, .venv, node_modules) → True
    2. 路径中任一段在 _EXCLUDED_NAMES (.DS_Store) → True
    3. 文件名以 . 开头（隐藏文件）→ True
    4. 文件名后缀在 _EXCLUDED_SUFFIXES (.pyc) → True
    5. 其他 → False

    Args:
        path: 模板中的相对路径 (Jinja2 渲染后)

    Returns:
        True 表示应排除该路径.
    """
    parts = path.parts
    if any(p in _EXCLUDED_DIRS for p in parts):
        return True
    if any(p in _EXCLUDED_NAMES for p in parts):
        return True
    name = path.name
    if name.startswith("."):
        return True
    if path.suffix in _EXCLUDED_SUFFIXES:
        return True
    return False


def parse_exclude_callback(spec: str) -> Callable[[Path], bool]:
    """解析 "module:function" 格式 spec, 返回可调用对象.

    Examples:
        'auto_engineering.init._shared.exclude:default_match_exclude'
        'my_project.custom_exclude:my_match'

    Args:
        spec: "module.path:function_name" 格式字符串

    Returns:
        已解析的回调函数 (Callable[[Path], bool]).

    Raises:
        ValueError: spec 不含 ":" 分隔符
        ImportError: module_path 无法导入
        AttributeError: module 中无 func_name
    """
    if ":" not in spec:
        raise ValueError(
            f"无效 exclude_callback spec: {spec!r} (需 'module:function' 格式)"
        )
    module_path, func_name = spec.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)
