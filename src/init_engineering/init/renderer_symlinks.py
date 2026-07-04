"""TemplateRenderer symlink handling — extracted from renderer.py (PR#3 P1-2).

将 ~40 行 symlink 处理逻辑独立成模块,renderer.py 主线只剩核心渲染循环。
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from ._shared.io import _atomic_write_binary, _atomic_write_text, detect_newline, is_binary
from .errors import TemplateRenderError


def resolve_symlink(
    src_file: Path,
    dst_file: Path,
    *,
    preserve_symlinks: bool,
) -> tuple[bool, str | None]:
    """处理模板中的 symlink 文件。

    返回 (handled, skip_reason):
    - handled=True: 已写入 dst_file (主流程可跳过)
    - handled=False + skip_reason: 已跳过(skip_reason='dangling')
    - handled=False + skip_reason=None: 不是 symlink 或无法处理 (主流程继续)

    Why split: 包含 dangling 处理 + 路径穿越 guard + 解析模式两种行为,
    单独成函数后主 render_to 循环可读性提升。
    """
    if not src_file.is_symlink():
        return False, None

    target = src_file.resolve()

    if preserve_symlinks:
        if not target.exists():
            return True, "dangling"  # 跳过 dangling symlink
        try:
            raw_target = os.readlink(src_file)
        except OSError:
            return True, "unreadable"
        if ".." in raw_target:
            raise TemplateRenderError(
                str(src_file),
                ValueError(
                    f"symlink target '{raw_target}' contains '..', refusing to copy"
                ),
            )
        try:
            dst_file.symlink_to(target)
        except OSError:
            return True, "symlink_failed"
        return True, None

    # preserve_symlinks=False: 解析为内容
    if not target.exists():
        return True, "dangling"  # dangling → 跳过
    if is_binary(str(target)):
        _atomic_write_binary(dst_file, target)
    else:
        newline = detect_newline(target)
        _atomic_write_text(dst_file, target.read_text(), newline=newline)
    try:
        shutil.copymode(src_file, dst_file)
    except OSError:
        pass
    return True, None