"""File I/O helpers — atomic write + binary detection.

PR#3 P1-2: 从 renderer.py 拆分,避免单文件 300+ 行。
PR#5 P1-9: temp 文件名加 pid + counter 防 fast 重入碰撞.

设计:
- atomic_write_* : 流式原子写 (PE-P1-5)
  - 写 .tmp-<pid>-<ts>-<counter> → rename 替换,防 SIGKILL 留半文件
  - 流式 (64KB chunks) 避免 read_text 一次性加载
- is_binary : 纯字节启发式检测,替代 binaryornot (最后发布 2020,无 3.13 兼容保证)
"""

from __future__ import annotations

import contextlib
import itertools
import logging
import os
import shutil
import threading
import time as _time
from collections.abc import Callable
from pathlib import Path

_logger = logging.getLogger(__name__)

_CHUNK_SIZE = 64 * 1024  # 64KB

_TMP_COUNTER = itertools.count(1)
_TMP_COUNTER_LOCK = threading.Lock()


def next_tmp_suffix() -> str:
    """生成唯一的 .tmp 后缀 (pid-ts-counter)."""
    with _TMP_COUNTER_LOCK:
        counter = next(_TMP_COUNTER)
    return f"{os.getpid()}-{_time.monotonic_ns()}-{counter}"


def _atomic_write_impl(
    partial: Path,
    dst: Path,
    write_fn: Callable[[], None],
    *,
    post_write: Callable[[], None] | None = None,
    label: str = "atomic write",
) -> None:
    """原子写通用骨架：创建 partial → write_fn() → replace → 异常清理."""
    try:
        write_fn()
        if post_write is not None:
            post_write()
        partial.replace(dst)
    except (KeyboardInterrupt, SystemExit):
        with contextlib.suppress(OSError):
            partial.unlink()
        raise
    except OSError:
        _logger.debug("%s failed: %s", label, partial, exc_info=True)
        try:
            partial.unlink()
        except OSError:
            _logger.debug("cleanup partial file failed: %s", partial, exc_info=True)
        raise


def atomic_write_text(dst: Path, content: str, newline: str | None = None) -> None:
    """流式原子写文本文件。"""
    partial = dst.with_name(f"{dst.name}.tmp-{next_tmp_suffix()}")

    def _write() -> None:
        with open(partial, "w", encoding="utf-8", newline=newline) as f:
            f.write(content)

    _atomic_write_impl(partial, dst, write_fn=_write, label="atomic write text")


def atomic_write_binary(dst: Path, src: Path) -> None:
    """流式原子写二进制文件 — 分块 64KB read+write。"""
    partial = dst.with_name(f"{dst.name}.tmp-{next_tmp_suffix()}")

    def _write_chunks() -> None:
        with open(src, "rb") as f_in, open(partial, "wb") as f_out:
            while True:
                chunk = f_in.read(_CHUNK_SIZE)
                if not chunk:
                    break
                f_out.write(chunk)

    _atomic_write_impl(
        partial, dst,
        write_fn=_write_chunks,
        post_write=lambda: shutil.copymode(src, partial),
        label="atomic write binary",
    )


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
        _logger.debug("is_binary: read failed for %s", path, exc_info=True)
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
                newline = max(newline, key=len)
            return newline
    except (OSError, UnicodeDecodeError):
        _logger.debug("detect_newline failed for %s", file_path, exc_info=True)
        return None