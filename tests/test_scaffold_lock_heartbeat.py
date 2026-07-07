"""F2: InitLock 陈旧锁检测 + stale lock reap — 投产前补直接测试.

锁文件写入 PID + timestamp，进程死锁时另一进程可识别并强制释放。
_write_heartbeat() 在 acquire() 时写一次（非周期性），下次 acquire()
前的 _try_reap_stale_lock() 验证。

覆盖:
1. _try_reap_stale_lock: 死锁 PID + 超时 → unlink 锁文件
2. _try_reap_stale_lock: PID 存活 → 不动
3. _try_reap_stale_lock: 时间未到 → 不动 (即使 PID 已死)
4. _try_reap_stale_lock: 心跳格式损坏 → 不动
5. _write_heartbeat: _fd=None 时 no-op
6. acquire: 锁文件存在且死锁 → reap 后正常获取

为什么 mock os.kill: 测试运行在真实进程, 不能 kill 真实进程. mock
os.kill(pid, 0) 返回 OSError 表示 PID 不存在, 模拟"死亡".
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest import mock

import pytest

from init_engineering.init.errors import TargetDirectoryError
from init_engineering.init.scaffold_lock import InitLock


# 注: scaffold_lock.acquire() 用 fcntl.flock — 在 Linux/macOS CI 上真实存在.
# reap 路径在 acquire 之前, 不依赖 flock, 所以下面多数测试不需要 fcntl mocking.


def _write_heartbeat_file(path: Path, pid: int, ts: float) -> None:
    """写入模拟心跳文件 (格式与 _write_heartbeat 一致)."""
    path.write_text(f"pid={pid}\nts={ts:.0f}\n", encoding="utf-8")


def test_reap_stale_lock_dead_pid_old_timestamp(tmp_path: Path) -> None:
    """死锁: PID 不存在 + ts 超时 → reap."""
    lock = InitLock(tmp_path)
    _write_heartbeat_file(lock.lock_file, pid=999999, ts=time.time() - 400)

    with mock.patch("os.kill", side_effect=ProcessLookupError("not found")):
        lock._try_reap_stale_lock()

    assert not lock.lock_file.exists(), "stale lock 应被清理"


def test_reap_stale_lock_alive_pid_not_reaped(tmp_path: Path) -> None:
    """活锁: PID 存活 → 不动."""
    lock = InitLock(tmp_path)
    _write_heartbeat_file(lock.lock_file, pid=os.getpid(), ts=time.time() - 400)

    with mock.patch("os.kill", return_value=None):  # 不抛 → 进程存在
        lock._try_reap_stale_lock()

    assert lock.lock_file.exists(), "活锁不应被 reap"


def test_reap_stale_lock_dead_pid_within_timeout_not_reaped(tmp_path: Path) -> None:
    """PID 死亡但时间未到 _STALE_LOCK_GRACE_PERIOD → 不动 (可能是慢任务, 不是死锁)."""
    lock = InitLock(tmp_path)
    _write_heartbeat_file(lock.lock_file, pid=999998, ts=time.time() - 10)  # 10s < 300s

    with mock.patch("os.kill", side_effect=ProcessLookupError("not found")):
        lock._try_reap_stale_lock()

    assert lock.lock_file.exists(), "未到超时不应 reap"


def test_reap_stale_lock_malformed_heartbeat_not_reaped(tmp_path: Path) -> None:
    """心跳格式损坏 → 不动 (避免误删用户文件)."""
    lock = InitLock(tmp_path)
    lock.lock_file.write_text("garbage data\n", encoding="utf-8")

    # 不应崩溃, 也不应 unlink
    lock._try_reap_stale_lock()
    assert lock.lock_file.exists(), "无法解析心跳不应 reap"


def test_write_heartbeat_no_fd_is_noop(tmp_path: Path) -> None:
    """_fd=None 时 _write_heartbeat 是 no-op (避免 release 后误写)."""
    lock = InitLock(tmp_path)
    lock._fd = None
    with mock.patch("os.write") as write_mock:
        lock._write_heartbeat()
        write_mock.assert_not_called()


def test_acquire_reaps_stale_lock_then_succeeds(tmp_path: Path) -> None:
    """完整流程: acquire() 遇到死锁 → reap → 正常获取."""
    # 写一个死锁的心跳文件 (用 InitLock 实例计算 lock_file 路径)
    lock = InitLock(tmp_path)
    _write_heartbeat_file(lock.lock_file, pid=999997, ts=time.time() - 400)
    assert lock.lock_file.exists()

    with mock.patch("os.kill", side_effect=ProcessLookupError("not found")):
        # fcntl.flock 在 macOS/Linux 上真实存在 — 不需 mock
        with InitLock.acquire_for(tmp_path) as acquired:
            assert acquired._fd is not None

    # 退出 with 后应清理
    assert not lock.lock_file.exists()