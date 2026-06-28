"""P2-B-1 (deep audit) — engine/state.py 直接测试.

之前 test_type_aliases_p1b.py 只测了重命名 (LoopState → EngineState
alias) 和字段存在性, 78 行 EngineState 的核心方法 to_dict / from_dict
/ get_channels / set_channels 没有直接 round-trip 测试. SQLite checkpoint
migrate 依赖 to_dict 输出, CheckpointEnvelope.from_dict 重建, 都
需要 round-trip 保护.

测试原则 (per pytest-memory-management.md): 单文件 pytest --no-cov --timeout=60.
"""

from __future__ import annotations

import pytest

from auto_engineering.engine.state import EngineState, LoopState


class TestEngineStateRoundTrip:
    """to_dict → from_dict round-trip."""

    def test_empty_state_round_trip(self) -> None:
        """空 state round-trip."""
        original = EngineState()
        restored = EngineState.from_dict(original.to_dict())
        assert restored == original

    def test_populated_state_round_trip(self) -> None:
        """填满字段的 state round-trip."""
        original = EngineState(
            requirement="build hello world CLI",
            current_stage="developer",
            plan="1. Create main.py\n2. Add tests",
            file_list=["src/main.py", "tests/test_main.py"],
            commit_hash="abc123",
            test_results={"passed": 5, "failed": 0},
            verdict="APPROVE",
            findings=[{"severity": "info", "msg": "ok"}],
            critic_feedback="Looks good.",
        )
        restored = EngineState.from_dict(original.to_dict())
        assert restored == original
        assert restored.requirement == "build hello world CLI"
        assert restored.file_list == ["src/main.py", "tests/test_main.py"]
        assert restored.findings == [{"severity": "info", "msg": "ok"}]

    def test_to_dict_is_json_serializable(self) -> None:
        """to_dict 输出可直接 json.dumps (Checkpoint 持久化路径)."""
        import json
        state = EngineState(requirement="x", plan="p", file_list=["a.py"])
        dumped = json.dumps(state.to_dict())
        loaded = json.loads(dumped)
        assert loaded["requirement"] == "x"
        assert loaded["plan"] == "p"
        assert loaded["file_list"] == ["a.py"]


class TestFromDictDefensive:
    """from_dict 忽略未知字段 (schema 演进兼容)."""

    def test_unknown_fields_silently_dropped(self) -> None:
        """from_dict 收到 schema 中不存在的字段 → 静默忽略, 不抛 KeyError."""
        data = {
            "requirement": "x",
            "unknown_field_added_in_v2_6": "should_be_dropped",
            "another_unknown": 42,
        }
        state = EngineState.from_dict(data)
        assert state.requirement == "x"
        assert not hasattr(state, "unknown_field_added_in_v2_6")

    def test_missing_fields_use_defaults(self) -> None:
        """from_dict 缺字段时使用 dataclass 默认值."""
        state = EngineState.from_dict({"requirement": "only this"})
        assert state.requirement == "only this"
        assert state.plan == ""  # default
        assert state.file_list == []  # default factory


class TestBackwardCompatAlias:
    """P1-B 重命名: LoopState 仍是 EngineState 的 alias."""

    def test_loop_state_is_engine_state(self) -> None:
        assert LoopState is EngineState

    def test_loop_state_works_with_to_dict(self) -> None:
        """LoopState (alias) 也能 to_dict."""
        state = LoopState(requirement="via alias")
        d = state.to_dict()
        assert d["requirement"] == "via alias"


class TestGetSetChannels:
    """get_channels / set_channels 辅助方法."""

    def test_get_channels_existing(self) -> None:
        """get_channels 返回已存在字段的值."""
        state = EngineState(requirement="x", plan="p")
        result = state.get_channels(["requirement", "plan"])
        assert result == {"requirement": "x", "plan": "p"}

    def test_get_channels_missing_silently_skipped(self) -> None:
        """get_channels 对不存在的字段静默跳过 (不抛 KeyError)."""
        state = EngineState()
        result = state.get_channels(["requirement", "nonexistent_field"])
        assert result == {"requirement": ""}

    def test_set_channels_updates_fields(self) -> None:
        """set_channels 把 writes 写入对应字段."""
        state = EngineState()
        state.set_channels({"plan": "new plan", "commit_hash": "xyz"})
        assert state.plan == "new plan"
        assert state.commit_hash == "xyz"
