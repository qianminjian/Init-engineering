"""conftest.py — pytest 共享 fixtures.

Phase 2+ 实装 AgentRuntime 后,Mock 类移到 auto_engineering.runtime.mock.
本文件只 re-export(保持测试 import 兼容),不再重复定义.

fixtures:
    checkpoint_dir — 每个测试用独立 tmp 目录存 checkpoint SQLite.
    run_async      — 同步上下文跑 async 协程.

v3.1 B3: CheckpointStore 实现 __enter__/__exit__,测试中可用 with 模式消除 ResourceWarning.
"""

import asyncio

import pytest

# Re-export from production code(避免 cli.py 反向依赖 conftest)
from auto_engineering.runtime.mock import (  # noqa: F401
    ScriptedMockRuntime,
    StepLimitedMockRuntime,
)


@pytest.fixture
def checkpoint_dir(tmp_path):
    """每个测试用独立 tmp 目录存 checkpoint SQLite."""
    return str(tmp_path / ".ae-checkpoints")


def run_async(coro):
    """同步上下文跑 async 协程. Phase 1 不引入 pytest-asyncio 依赖."""
    return asyncio.run(coro)
