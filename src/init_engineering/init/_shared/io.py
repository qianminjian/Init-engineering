"""File I/O helpers — atomic write + binary detection.

PR#3 P1-2: 从 renderer.py 拆分,避免单文件 300+ 行。

设计:
- _atomic_write_* : 流式原子写 (PE-P1-5)
  - 写 .tmp-<ts> → rename 替换,防 SIGKILL 留半文件
  - 流式 (64KB chunks) 避免 read_text 一次性加载
- is_binary : 纯字节启发式检测,替代 binaryornot (最后发布 2020,无 3.13 兼容保证)
"""

from __future__ import annotations

import shutil
import time as _time
from pathlib import Path

_CHUNK_SIZE = 64 * 1024  # 64KB


def _atomic_write_text(dst: Path, content: str, newline: str | None = None) -> None:
    """流式原子写文本文件。"""
    partial = dst.with_name(f"{dst.name}.tmp-{_time.monotonic_ns()}")
    try:
        with open(partial, "w", encoding="utf-8", newline=newline) as f:
            f.write(content)
        partial.replace(dst)
    except Exception:
        try:
            partial.unlink()
        except OSError:
            pass
        raise


def _atomic_write_binary(dst: Path, src: Path) -> None:
    """流式原子写二进制文件 — 分块 64KB read+write。"""
    partial = dst.with_name(f"{dst.name}.tmp-{_time.monotonic_ns()}")
    try:
        with open(src, "rb") as f_in, open(partial, "wb") as f_out:
            while True:
                chunk = f_in.read(_CHUNK_SIZE)
                if not chunk:
                    break
                f_out.write(chunk)
        shutil.copymode(src, partial)
        partial.replace(dst)
    except Exception:
        try:
            partial.unlink()
        except OSError:
            pass
        raise


def is_binary(path: str) -> bool:
    """检测文件是否为二进制（无外部依赖，纯字节启发式）。

    算法：
    1. 读首 8KB 字节
    2. 含 NUL 字节（\\x00）→ 二进制
    3. 全部 UTF-8 可解码 → 文本
    4. 否则 → 二进制

    替代 binaryornot（最后发布 2020，无 3.13 兼容性保证）。
    """
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
    except OSError:
        return False
    if not chunk:
        return False
    if b"\x00" in chunk:
        return True
    try:
        chunk.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def detect_newline(file_path: Path) -> str | None:
    """检测文件的换行符风格。"""
    try:
        with open(file_path, encoding="utf-8") as f:
            f.readline()
            newline = getattr(f, "newlines", None)
            if isinstance(newline, tuple):
                newline = newline[0]
            return newline
    except Exception:
        return None