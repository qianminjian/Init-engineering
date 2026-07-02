"""Concurrent file lock — 防多 ae init 进程冲突。

来源：InitWorker 原始 inline 实现拆分（501→300 行）。

设计：
- 文件式锁（.ae-init.lock）+ fcntl flock(LOCK_EX | LOCK_NB)
- 跨平台：Linux/macOS 原生支持 fcntl；Windows 不支持 fcntl → 抛 TargetDirectoryError
- 异常转 TargetDirectoryError（exit_code=4），与 _phase_detect 既有语义一致
"""

from __future__ import annotations

import os
from pathlib import Path

from .errors import TargetDirectoryError

try:
    import fcntl  # Linux/macOS only
except ImportError:
    fcntl = None  # type: ignore[assignment]


class InitLock:
    """单目录级并发互斥锁。

    Usage:
        with InitLock.acquire(dst_path) as lock:
            # 临界区：单进程独占 dst_path
            ...
    """

    def __init__(self, dst_path: Path):
        self.dst_path = dst_path
        self.lock_file: Path = dst_path / ".ae-init.lock"
        self._fd: int | None = None

    def acquire(self) -> "InitLock":
        if fcntl is None:
            # Windows 不支持 fcntl，无法可靠实现并发锁 — 拒绝运行而非假装成功
            raise TargetDirectoryError(
                f"InitLock 不支持 Windows 平台 (fcntl 模块不可用)。"
                f"并发执行 ae init 可能导致模板渲染冲突。"
                f"请在 WSL/Linux/macOS 上运行，或使用串行调度避免并发。"
                f"详见 https://github.com/qianminjian/Init-engineering/issues/new?template=windows.md"
            )
        self._fd = os.open(str(self.lock_file), os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            os.close(self._fd)
            self._fd = None
            # B2: 清理 stale lock 文件 — O_CREAT 已创建, 必须显式 unlink 避免残留
            try:
                self.lock_file.unlink()
            except OSError:
                pass
            raise TargetDirectoryError(
                f"目录 {self.dst_path.name} 正在被另一个 ae init 进程使用。"
                f"请等待完成后再试，或删除 .ae-init.lock 强制解锁。"
            )
        return self

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            os.close(self._fd)
        except Exception:
            pass
        finally:
            self._fd = None
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
        except Exception:
            pass

    @classmethod
    def acquire_for(cls, dst_path: Path) -> "InitLock":
        """便捷 API — 直接拿到锁对象（手动管理 release）。

        推荐使用 `with` 语句（见 __enter__/__exit__）。
        """
        lock = cls(dst_path)
        lock.acquire()
        return lock

    def __enter__(self) -> "InitLock":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
        return False
