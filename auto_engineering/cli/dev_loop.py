"""CLI dev_loop 核心 — _build_v2_agent_runtime / _run_v2_orchestrator.

从 cli.py 拆分 (Plan P1-B, 原 cli.py §218-451).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auto_engineering.cli.helpers import CancellationToken, ProgressLogger, TokenTracker


@dataclass
class OrchestratorRunResult:
    """_run_v2_orchestrator 返回值 — 模拟 V1RunResult 接口."""

    status: str
    total_steps: int
    checkpoint_id: str


def _build_v2_agent_runtime(
    project_root: Path,
    progress: ProgressLogger,
    token_tracker: TokenTracker | None = None,
) -> Any:
    """构造 v2.0 Orchestrator 用的 AgentRuntime (替代 _build_v2_executor).

    v2.3 Phase H (P1.4): Orchestrator 集成 AgentRuntime, 按 task.role 路由
    调 agent.execute — 替代单一 executor callback wrapper.

    设计:
        - 3 个 role (architect/developer/critic) 全部使用真实 Agent(BaseAgent) 实例
        - 共享同一个 AnthropicProvider(llm) 和工具集
        - 每个 Agent 有不同的 system_prompt (来自 agents/prompts.py)
        - LLM 异常 → Agent.execute 内 _map_llm_exception 转为 AEError

    Args:
        project_root: 项目根目录 (沙箱白名单基址)
        progress: 进度日志 (用于记录 task 执行)
        token_tracker: Token 跟踪器 (注入 BaseAgent.execute)

    Returns:
        AgentRuntime 实例 (已注册 architect/developer/critic)
    """
    import os

    from auto_engineering.agents.base import Agent
    from auto_engineering.agents.prompts import (
        ARCHITECT_SYSTEM_PROMPT,
        CRITIC_SYSTEM_PROMPT,
        DEVELOPER_SYSTEM_PROMPT,
    )
    from auto_engineering.llm.anthropic_provider import AnthropicProvider
    from auto_engineering.runtime.runtime import AgentRuntime
    from auto_engineering.tools.bash_tools import RunBashTool
    from auto_engineering.tools.file_tools import (
        EditFileTool,
        ListDirTool,
        ReadFileTool,
        SearchCodeTool,
        WriteFileTool,
    )
    from auto_engineering.tools.git_tools import (
        GitCommitTool,
        GitDiffTool,
        GitStatusTool,
    )
    from auto_engineering.tools.test_tools import RunTestsTool

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    llm = AnthropicProvider(api_key=api_key)
    # P1.9 fix: 只有支持 project_root 的工具传 project_root (白名单沙箱)
    # P1-C: ReadFileTool 现在也支持 project_root
    tools = [
        WriteFileTool(project_root=project_root),
        EditFileTool(project_root=project_root),
        SearchCodeTool(project_root=project_root),
        ReadFileTool(project_root=project_root),
        # 不支持 project_root 的工具: ListDirTool / RunBashTool /
        # GitStatusTool / GitCommitTool / GitDiffTool / RunTestsTool
        ListDirTool(),
        RunBashTool(),
        GitStatusTool(),
        GitCommitTool(),
        GitDiffTool(),
        RunTestsTool(),
    ]
    runtime = AgentRuntime()
    runtime.register(
        "architect",
        lambda: Agent(
            llm=llm,
            role="architect",
            system_prompt=ARCHITECT_SYSTEM_PROMPT,
            tools=tools,
        ),
    )
    runtime.register(
        "developer",
        lambda: Agent(
            llm=llm,
            role="developer",
            system_prompt=DEVELOPER_SYSTEM_PROMPT,
            tools=tools,
        ),
    )
    runtime.register(
        "critic",
        lambda: Agent(
            llm=llm,
            role="critic",
            system_prompt=CRITIC_SYSTEM_PROMPT,
            tools=tools,
        ),
    )
    return runtime


def _build_v2_semantic_evaluator(
    project_root: Path,
    progress: ProgressLogger,
) -> Any:
    """构造 v2.0 Orchestrator 用的语义评估器 (简化:始终返回 True).

    Phase C 简化策略:
        - 不接 LLM (避免 mock-friendly 的"假评估"陷阱)
        - 用 Gate 跑过的结果作为代理:所有 Gate 通过 → satisfied
        - 这里返回简单的 True(让 Orchestrator 主循环跑起来)

    Args:
        project_root: 项目根目录 (备用, 当前未使用)
        progress: 进度日志 (备用)

    Returns:
        async (round_result) -> bool
    """

    async def evaluator(round_result: Any) -> bool:
        # Phase C 简化: 总是返回 True (Gate 已在 Orchestrator 内部跑过)
        return True

    return evaluator


def _run_v2_orchestrator(
    requirement: str,
    project_root: Path,
    max_rounds: int,
    progress: ProgressLogger,
    cancellation: CancellationToken,
    token_tracker: TokenTracker | None = None,
) -> OrchestratorRunResult:
    """v2.0 Orchestrator 驱动器 — 单 Agent 模式演示.

    设计要点 (Phase C):
        - 单 task / round (Phase 3 多 Agent 并发未启用, 留 Phase 4+)
        - 复用 v1.0 BaseAgent (DeveloperAgent) 作为 TaskExecutor
        - 启用 2 道 Gate (Safety + Lint) — 真集成, 非 mock
        - semantic_evaluator 简化 (始终 True, 避免 mock LLM)

    Args:
        requirement: 需求描述
        project_root: 项目根目录 (Gate 运行基址 + 沙箱白名单)
        max_rounds: 最大轮数
        progress: 进度日志
        cancellation: 取消令牌 (用户 SIGINT 触发)
        token_tracker: Token 跟踪器 (注入 BaseAgent)

    Returns:
        OrchestratorRunResult (status/total_steps/checkpoint_id)

    Raises:
        AEError: 配置错 / 业务错
    """
    import asyncio

    from auto_engineering.gates.lint import LintGate
    from auto_engineering.gates.safety import SafetyGate
    from auto_engineering.loop.convergence import ConvergenceConfig
    from auto_engineering.loop.orchestrator import (
        Orchestrator,
        OrchestratorConfig,
    )
    from auto_engineering.loop.plan import Task

    # 1. 构造 OrchestratorConfig: gates + semantic_evaluator + project_root + agent_runtime
    #    v2.3 Phase E (P1.1): max_rounds → ConvergenceConfig.max_iterations (单一来源)
    #    v2.3 Phase H (P1.4): agent_runtime 传入, 按 task.role 调度 (替代 _build_v2_executor)
    agent_runtime = _build_v2_agent_runtime(project_root, progress, token_tracker)
    config = OrchestratorConfig(
        convergence_config=ConvergenceConfig(max_iterations=max_rounds),
        gates=[SafetyGate(), LintGate()],
        semantic_evaluator=_build_v2_semantic_evaluator(project_root, progress),
        project_root=project_root,
        agent_runtime=agent_runtime,
    )

    # 2. 构造单 task (Phase C 简化: 1 个 task, developer agent)
    task = Task(
        id="t1",
        title=requirement[:50] or "Implement requirement",  # Phase 2.1-D: 非空 title
        description=requirement,
        expected_output="实现需求对应的代码变更",  # Phase 2.1-D: contract
        role="developer",
        agent_type="developer",
        target_files=frozenset(),  # 单 Agent 模式不强制隔离
        depends_on=[],
    )

    # 3. 构造 Orchestrator (v2.3 Phase H P1.4: 不再传 executor, agent_runtime 自动调度)
    orchestrator = Orchestrator(
        requirement=requirement,
        tasks=[task],
        executor=None,  # type: ignore[arg-type]  # agent_runtime 优先
        config=config,
    )

    # 5. 启动 asyncio.run (Orchestrator.run 是 async)
    history = asyncio.run(orchestrator.run(cancellation=cancellation))

    # 6. 输出总结
    total_rounds = len(history)
    status = "done" if (orchestrator.verdict and orchestrator.verdict.should_stop) else "max_rounds"
    checkpoint_id = f"v2-r{total_rounds}"

    # 进度输出
    progress.emit(
        "orchestrator_done",
        rounds=total_rounds,
        verdict_level=orchestrator.verdict.level if orchestrator.verdict else None,
        should_stop=orchestrator.verdict.should_stop if orchestrator.verdict else False,
    )

    return OrchestratorRunResult(
        status=status,
        total_steps=total_rounds,
        checkpoint_id=checkpoint_id,
    )
