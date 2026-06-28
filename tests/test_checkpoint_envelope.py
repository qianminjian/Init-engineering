"""P2-B-4 (deep audit) — loop/checkpoint/envelope.py 直接测试.

95 行 envelope.py (CheckpointMeta + Checkpoint[T] + 3 异常类) 之前
仅通过 __init__.py re-export + store.py 间接使用, 没有直接测试
Checkpoint[T] 泛型 + meta() 提取 + 异常类属性. SQLiteCheckpointStore
依赖这些数据类的字段契约.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from auto_engineering.loop.checkpoint.envelope import (
    Checkpoint,
    CheckpointError,
    CheckpointMeta,
    CheckpointNotFoundError,
    CheckpointSchemaMismatchError,
)
from auto_engineering.loop.convergence import RoundHistory


class TestCheckpointMeta:
    """CheckpointMeta 轻量元数据."""

    def test_construction(self) -> None:
        now = datetime.now(timezone.utc)
        meta = CheckpointMeta(
            id="cp-1",
            round=1,
            step=0,
            created_at=now,
            schema_version=1,
        )
        assert meta.id == "cp-1"
        assert meta.round == 1
        assert meta.parent_id is None
        assert meta.tag is None

    def test_with_parent_and_tag(self) -> None:
        meta = CheckpointMeta(
            id="cp-2",
            round=2,
            step=1,
            created_at=datetime.now(timezone.utc),
            schema_version=1,
            parent_id="cp-1",
            tag="before-refactor",
        )
        assert meta.parent_id == "cp-1"
        assert meta.tag == "before-refactor"


class TestCheckpoint:
    """Checkpoint[T] 泛型 + meta() 提取."""

    def test_construction_with_state(self) -> None:
        """构造 Checkpoint, state 是 Any 类型 (典型 CheckpointEnvelope)."""
        state = {"requirement": "build X"}  # duck-typed
        cp = Checkpoint[dict](
            id="cp-1",
            round=1,
            step=0,
            state=state,
            history=[],
            created_at=datetime.now(timezone.utc),
            schema_version=1,
        )
        assert cp.state is state
        assert cp.history == []

    def test_meta_extracts_metadata(self) -> None:
        """meta() 从 Checkpoint 提取 CheckpointMeta (用于 list_all 轻量)."""
        now = datetime.now(timezone.utc)
        cp = Checkpoint[dict](
            id="cp-1",
            round=1,
            step=0,
            state={"x": 1},
            history=[RoundHistory(round_id=1)],
            created_at=now,
            schema_version=1,
            parent_id="cp-0",
            tag="manual",
        )
        meta = cp.meta()
        assert meta.id == "cp-1"
        assert meta.round == 1
        assert meta.step == 0
        assert meta.created_at == now
        assert meta.schema_version == 1
        assert meta.parent_id == "cp-0"
        assert meta.tag == "manual"

    def test_meta_excludes_state_and_history(self) -> None:
        """meta() 提取元数据, 不含 state/history (轻量目的)."""
        cp = Checkpoint[dict](
            id="cp-1",
            round=1,
            step=0,
            state={"huge": "x" * 10000},
            history=[RoundHistory(round_id=1)] * 100,
            created_at=datetime.now(timezone.utc),
            schema_version=1,
        )
        meta = cp.meta()
        # meta 没有 state/history 字段 (dataclass CheckpointMeta)
        assert not hasattr(meta, "state")
        assert not hasattr(meta, "history")


class TestCheckpointExceptions:
    """3 个异常类 + 错误链."""

    def test_checkpoint_error_is_exception(self) -> None:
        err = CheckpointError("base error")
        assert isinstance(err, Exception)
        assert str(err) == "base error"

    def test_checkpoint_not_found_error_inherits_base(self) -> None:
        err = CheckpointNotFoundError("cp-xyz not found")
        assert isinstance(err, CheckpointError)
        assert isinstance(err, Exception)
        assert "cp-xyz not found" in str(err)

    def test_checkpoint_schema_mismatch_error_attributes(self) -> None:
        """SchemaMismatchError 暴露 found/expected 字段供上层处理."""
        err = CheckpointSchemaMismatchError(found=2, expected=1)
        assert err.found == 2
        assert err.expected == 1
        assert isinstance(err, CheckpointError)
        assert "found 2" in str(err)
        assert "expected 1" in str(err)
