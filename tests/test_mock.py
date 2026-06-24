"""Tests for runtime/mock.py — Phase 2 T4.

TDD: 把 ScriptedMockRuntime + StepLimitedMockRuntime 从 tests/conftest.py 移到
auto_engineering/runtime/mock.py(解决 cli.py 反向依赖).

验收:
    1. 可从 auto_engineering.runtime.mock import ScriptedMockRuntime 等
    2. tests.conftest 的 import 仍工作(re-export)
    3. 行为与原 conftest 版本一致
"""

from __future__ import annotations

import pytest

from auto_engineering.engine.state import LoopState
from auto_engineering.runtime.mock import (
    ScriptedMockRuntime,
    StepLimitedMockRuntime,
)
from tests.conftest import run_async


class TestMockImportPath:
    """Mock 类在新位置 + tests.conftest 仍可 import."""

    def test_scripted_mock_importable_from_runtime(self):
        assert ScriptedMockRuntime.__module__ == "auto_engineering.runtime.mock"

    def test_step_limited_mock_importable_from_runtime(self):
        assert StepLimitedMockRuntime.__module__ == "auto_engineering.runtime.mock"

    def test_scripted_mock_same_class_as_conftest(self):
        """tests.conftest.ScriptedMockRuntime 应是同一类(避免双份)."""
        from tests.conftest import ScriptedMockRuntime as ConftestMock

        assert ScriptedMockRuntime is ConftestMock

    def test_step_limited_mock_same_class_as_conftest(self):
        from tests.conftest import StepLimitedMockRuntime as ConftestMock

        assert StepLimitedMockRuntime is ConftestMock


class TestScriptedMockRuntime:
    """ScriptedMockRuntime 行为(回归测试,验证移动后行为不变)."""

    def test_execute_returns_configured_writes(self):
        rt = ScriptedMockRuntime(
            {
                "architect": {"plan": "p", "file_list": ["x.py"]},
            }
        )
        # 构造最小 Stage
        from auto_engineering.engine.graph import Stage

        stage = Stage(
            name="architect",
            agent_type="architect",
            description_template="",
            expected_output="",
            output_channels=["plan", "file_list"],
        )
        result = run_async(rt.execute(stage, LoopState()))
        assert result.stage == "architect"
        assert result.writes == {"plan": "p", "file_list": ["x.py"]}

    def test_execute_unknown_stage_raises(self):
        rt = ScriptedMockRuntime({"architect": {"plan": "p"}})
        from auto_engineering.engine.graph import Stage

        stage = Stage(
            name="unknown",
            agent_type="unknown",
            description_template="",
            expected_output="",
        )
        try:
            run_async(rt.execute(stage, LoopState()))
        except AssertionError as e:
            assert "no script for stage 'unknown'" in str(e)
        else:
            pytest.fail("Expected AssertionError")

    def test_call_log_records_stage_names(self):
        rt = ScriptedMockRuntime(
            {
                "a": {"x": 1},
                "b": {"y": 2},
            }
        )
        from auto_engineering.engine.graph import Stage

        run_async(
            rt.execute(
                Stage(name="a", agent_type="a", description_template="", expected_output=""),
                LoopState(),
            )
        )
        run_async(
            rt.execute(
                Stage(name="b", agent_type="b", description_template="", expected_output=""),
                LoopState(),
            )
        )
        assert rt.call_log == ["a", "b"]


class TestStepLimitedMockRuntime:
    """StepLimitedMockRuntime 行为(MAJOR→APPROVE 回路测试)."""

    def test_critic_returns_major_then_approve(self):
        from auto_engineering.engine.graph import Stage

        rt = StepLimitedMockRuntime(major_count=1)

        # 第一次 critic → MAJOR
        result_major = run_async(
            rt.execute(
                Stage(
                    name="critic", agent_type="critic", description_template="", expected_output=""
                ),
                LoopState(),
            )
        )
        assert result_major.writes["verdict"] == "MAJOR"

        # 第二次 critic → APPROVE
        result_approve = run_async(
            rt.execute(
                Stage(
                    name="critic", agent_type="critic", description_template="", expected_output=""
                ),
                LoopState(),
            )
        )
        assert result_approve.writes["verdict"] == "APPROVE"

    def test_critic_count_increments(self):
        rt = StepLimitedMockRuntime(major_count=3)
        assert rt.critic_calls == 0
        from auto_engineering.engine.graph import Stage

        for _ in range(3):
            run_async(
                rt.execute(
                    Stage(
                        name="critic",
                        agent_type="critic",
                        description_template="",
                        expected_output="",
                    ),
                    LoopState(),
                )
            )
        assert rt.critic_calls == 3


class TestMockAgentProtocolConformance:
    """Mock 类应该实现 Agent Protocol(duck typing,AgentRuntime 可用)."""

    def test_scripted_mock_satisfies_agent_protocol(self):
        from auto_engineering.runtime.runtime import Agent

        rt = ScriptedMockRuntime({"architect": {"plan": "p"}})
        # Runtime_checkable Protocol 应该 isinstance 检查通过
        assert isinstance(rt, Agent)

    def test_step_limited_mock_satisfies_agent_protocol(self):
        from auto_engineering.runtime.runtime import Agent

        rt = StepLimitedMockRuntime(major_count=1)
        assert isinstance(rt, Agent)
