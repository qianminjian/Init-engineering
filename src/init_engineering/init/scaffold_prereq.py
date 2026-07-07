"""Prerequisite checks — 模板版本 + 工具链检查。

从 scaffold_phases.py 拆分（v2.5：501→300 行）。

设计：
- _check_template_version() : 模板 _min_ae_version vs 已安装 __version__
- _check_language_tools()    : 跳过 --skip-tasks 时不检查编译器/运行时
"""

from __future__ import annotations

import shutil

from packaging.version import parse

from .. import __version__
from .errors import ConfigFileError, UnsatisfiedPrerequisiteError


def check_template_version(min_ae_version: str) -> None:
    """校验 ae 包装版本是否满足模板要求的 min_ae_version.

    若模板未声明 min_ae_version → 静默通过。
    不通过 → 抛 ConfigFileError(exit_code=2)。
    """
    if not min_ae_version:
        return
    installed = parse(__version__)
    required = parse(min_ae_version)
    if installed < required:
        raise ConfigFileError(
            f"模板要求 ae >= {min_ae_version}，当前版本 {__version__}"
        )


# 语言 → 必需工具映射（仅在 not skip_tasks 时检查；模板渲染不需要编译器）
_LANG_TOOL_MAP: dict[str, tuple[str, str]] = {
    "typescript": ("node", "Node.js"),
    "javascript": ("node", "Node.js"),
    "go": ("go", "Go"),
    "rust": ("cargo", "Cargo"),
}


def check_language_tools(language: str | None, skip_tasks: bool) -> None:
    """若指定语言且不跳过任务，检查对应运行时工具。

    Skip tasks 时只检查 git + python3（在 check_basic_tools）。
    """
    if skip_tasks or not language:
        return
    lang_tool = _LANG_TOOL_MAP.get(language)
    if lang_tool is None:
        return
    cmd, name = lang_tool
    if shutil.which(cmd) is None:
        raise UnsatisfiedPrerequisiteError(
            f"未找到 {name} ({cmd})，但项目语言为 {language}。"
            f" 使用 --skip-tasks 跳过构建步骤，或安装后重试。"
        )


def check_basic_tools() -> None:
    """基础工具链 — git + python3 必备（即使 --skip-tasks 也需要）。"""
    for cmd, name in [("git", "Git"), ("python3", "Python 3")]:
        if shutil.which(cmd) is None:
            raise UnsatisfiedPrerequisiteError(
                f"未找到 {name}。请先安装（例如: brew install {cmd} 或检查 PATH）。"
            )
