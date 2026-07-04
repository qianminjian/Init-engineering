"""Concurrent file lock — 防多 ae init 进程冲突。

来源：InitWorker 原始 inline 实现拆分（501→300 行）。

设计：
- 文件式锁（.ae-init.lock）+ fcntl flock(LOCK_EX | LOCK_NB) (Linux/macOS)
- Windows 降级：DI-P1-1 改用 msvcrt.locking (Windows 原生文件锁) — 与 fcntl 语义对齐
- P2-7: 心跳机制 — 锁文件写入 PID + 时间戳, 进程死锁时另一进程可识别并强制释放
- 异常转 TargetDirectoryError（exit_code=4），与 _phase_detect 既有语义一致
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

from .errors import TargetDirectoryError

_logger = logging.getLogger(__name__)

try:
    import fcntl  # Linux/macOS only
except ImportError:
    fcntl = None  # type: ignore[assignment]

# DI-P1-1: Windows 文件锁降级 — msvcrt.locking 语义与 fcntl.flock 近似
# (单文件字节级互斥),都是 OS 层 advisory lock,跨进程可见
IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    try:
        import msvcrt  # type: ignore[import-not-found]
    except ImportError:
        msvcrt = None  # type: ignore[assignment]
else:
    msvcrt = None  # type: ignore[assignment]


class InitLock:
    """单目录级并发互斥锁。

    Usage:
        with InitLock.acquire(dst_path) as lock:
            # 临界区：单进程独占 dst_path
            ...
    """

    # msvcrt.locking mode: LK_NBLCK = 非阻塞独占锁
    _LK_NBLCK = 2
    _LK_UNLCK = 0

    # P2-7: 心跳配置 — 锁文件写入 PID + timestamp, 进程死锁可识别
    # _HEARTBEAT_INTERVAL: 多久写一次心跳 (秒)
    # _HEARTBEAT_TIMEOUT: 多久无心跳认为持锁进程死亡 (秒, 3x interval)
    _HEARTBEAT_INTERVAL = 30
    _HEARTBEAT_TIMEOUT = 90

    def __init__(self, dst_path: Path):
        self.dst_path = dst_path
        self.lock_file: Path = dst_path / ".ae-init.lock"
        self._fd: int | None = None
        self._last_heartbeat: float = 0.0

    def acquire(self) -> InitLock:
        if fcntl is None and not IS_WINDOWS:
            # 非 Windows 平台 + 无 fcntl = 异常环境（如 musl + 某些裁剪）
            raise TargetDirectoryError(
                f"InitLock 不支持当前平台 (fcntl 模块不可用, sys.platform={sys.platform})。"
                f"并发执行 ae init 可能导致模板渲染冲突。"
                f"请在 WSL/Linux/macOS/Windows 上运行，或使用串行调度避免并发。"
            )
        if fcntl is None and IS_WINDOWS and msvcrt is None:
            # Windows 但 msvcrt 不可用 — 极少见 (Cygwin 等)
            raise TargetDirectoryError(
                "InitLock 在 Windows 上需 msvcrt 模块 (用于文件锁)。"
                "当前环境 msvcrt 不可用, 请使用 CPython 官方发行版。"
            )

        # P2-7: acquire 前检查 stale lock — 读心跳, 超过 _HEARTBEAT_TIMEOUT
        # 且持锁 PID 不存在 → 视为死锁, 强制 unlink 后重试
        if self.lock_file.exists():
            self._try_reap_stale_lock()

        self._fd = os.open(str(self.lock_file), os.O_CREAT | os.O_RDWR)
        try:
            if fcntl is not None:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                # DI-P1-1: Windows 降级 — msvcrt.locking LK_NBLCK
                # 锁 1 字节, 跨进程 OS 层 advisory lock
                # 失败 → OSError (errno 13 / 36 on Windows = LockViolation)
                msvcrt.locking(self._fd, self._LK_NBLCK, 1)  # type: ignore[union-attr]
            # P2-7: 拿到锁后立刻写一次心跳
            self._write_heartbeat()
        except (BlockingIOError, OSError, PermissionError) as lock_err:
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
            ) from lock_err
        return self

    def _write_heartbeat(self) -> None:
        """P2-7: 写心跳到锁文件 — PID + timestamp, 供其他进程识别死锁."""
        if self._fd is None:
            return
        try:
            payload = f"pid={os.getpid()}\nts={time.time():.0f}\n".encode()
            os.lseek(self._fd, 0, 0)
            os.write(self._fd, payload)
            os.ftruncate(self._fd, len(payload))
            self._last_heartbeat = time.time()
        except OSError:
            pass

    def maybe_heartbeat(self) -> None:
        """P2-7: 距上次心跳超过 _HEARTBEAT_INTERVAL → 续心跳.

        调用方应在长任务中周期性调用 (e.g. 每渲染 N 个文件后).
        InitWorker 暂时未调用 (P2-7 仅为机制预留, 真正集成在后续版本).
        """
        if self._fd is None:
            return
        if time.time() - self._last_heartbeat >= self._HEARTBEAT_INTERVAL:
            self._write_heartbeat()

    def _try_reap_stale_lock(self) -> None:
        """P2-7: 检查锁文件心跳 — 持锁进程死亡时强制清理.

        逻辑:
        1. 读锁文件内容, 解析 PID + ts
        2. 持锁 PID 在 /proc 中存在 → 进程还活着, 不要动
        3. ts 距今 < _HEARTBEAT_TIMEOUT → 可能只是慢任务, 不要动
        4. PID 死亡 + ts 超时 → 死锁, unlink 锁文件
        """
        try:
            content = self.lock_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        pid = None
        ts = None
        for line in content.splitlines():
            if line.startswith("pid="):
                try:
                    pid = int(line.split("=", 1)[1])
                except ValueError:
                    pass
            elif line.startswith("ts="):
                try:
                    ts = float(line.split("=", 1)[1])
                except ValueError:
                    pass
        if pid is None or ts is None:
            return  # 无心跳格式, 不动
        # P2-3: 跨平台 PID 存活检测 — os.kill(pid, 0) Windows 不支持
        if _is_pid_alive(pid):
            return  # 进程在, 锁有效
        if time.time() - ts < self._HEARTBEAT_TIMEOUT:
            return  # 时间未到, 等待
        # 死锁 — 强制清理
        _logger.warning(
            "reaping stale lock file %s (pid=%d, last heartbeat %.0fs ago)",
            self.lock_file, pid, time.time() - ts,
        )
        try:
            self.lock_file.unlink()
        except OSError:
            pass

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            if fcntl is not None:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            else:
                # DI-P1-1: Windows 释放锁 — 解锁那 1 字节
                msvcrt.locking(self._fd, self._LK_UNLCK, 1)  # type: ignore[union-attr]
        except Exception as exc:
            _logger.debug("flock unlock failed (ignored): %s", exc)
        try:
            os.close(self._fd)
        except Exception as exc:
            _logger.debug("fd close failed (ignored): %s", exc)
        finally:
            self._fd = None
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
        except Exception as exc:
            _logger.debug("lock file unlink failed (ignored): %s", exc)

    @classmethod
    def acquire_for(cls, dst_path: Path) -> InitLock:
        """便捷 API — 直接拿到锁对象（手动管理 release）。

        推荐使用 `with` 语句（见 __enter__/__exit__）。
        """
        lock = cls(dst_path)
        lock.acquire()
        return lock

    def __enter__(self) -> InitLock:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
        return False


def _is_pid_alive(pid: int) -> bool:
    """P2-3: 跨平台 PID 存活检测.

    Unix:  os.kill(pid, 0) — signal 0 = 不真发信号, 仅检查存在/权限.
          进程不存在 → ProcessLookupError; 权限不足 → PermissionError (但存活).
    Windows: os.kill 不支持 signal 0 (直接调 TerminateProcess, signal 0 参数非法).
          改用 ctypes OpenProcess + GetExitCodeProcess,STILL_ACTIVE=259 表示存活.

    Returns:
        True if process exists and is running, False otherwise.
    """
    if IS_WINDOWS:
        return _is_pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # 存在但无权限 → 进程确实活着
        return True
    except OSError:
        return False


def _is_pid_alive_windows(pid: int) -> bool:
    """P2-3: Windows 专用 — ctypes 调用 OpenProcess + GetExitCodeProcess.

    PROCESS_QUERY_LIMITED_INFORMATION (0x1000) 是最低权限查询句柄,
    普通用户 token 即可打开. STILL_ACTIVE (259) 表示进程尚未退出.
    """
    try:
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    except OSError:
        return False
