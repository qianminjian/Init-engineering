"""File I/O helpers — atomic write + binary detection.

PR#3 P1-2: 从 renderer.py 拆分,避免单文件 300+ 行。
PR#5 P1-9: temp 文件名加 pid + counter 防 fast 重入碰撞.

设计:
- _atomic_write_* : 流式原子写 (PE-P1-5)
  - 写 .tmp-<pid>-<ts>-<counter> → rename 替换,防 SIGKILL 留半文件
  - 流式 (64KB chunks) 避免 read_text 一次性加载
- is_binary : 纯字节启发式检测,替代 binaryornot (最后发布 2020,无 3.13 兼容保证)
"""

from __future__ import annotations

import os
import shutil
import threading
import time as _time
from pathlib import Path

_CHUNK_SIZE = 64 * 1024  # 64KB

# PR#5 P1-9: 进程级 counter + 线程锁 — fast 重入时 monotonic_ns 可能碰撞
# (.tmp-<ts> 文件冲突 → rename 失败). 加 pid (跨进程) + counter (同进程)
# 一起保证 .tmp 路径唯一.
_TMP_COUNTER = 0
_TMP_COUNTER_LOCK = threading.Lock()


def _next_tmp_suffix() -> str:
    """生成唯一的 .tmp 后缀 (pid-ts-counter)."""
    global _TMP_COUNTER
    with _TMP_COUNTER_LOCK:
        _TMP_COUNTER += 1
        counter = _TMP_COUNTER
    return f"{os.getpid()}-{_time.monotonic_ns()}-{counter}"


def _atomic_write_text(dst: Path, content: str, newline: str | None = None) -> None:
    """流式原子写文本文件。"""
    partial = dst.with_name(f"{dst.name}.tmp-{_next_tmp_suffix()}")
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
    partial = dst.with_name(f"{dst.name}.tmp-{_next_tmp_suffix()}")
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