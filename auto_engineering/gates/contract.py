"""v2.0 Phase 04 — Gate 3: Contract (跨 Agent 契约检查).

设计来源: design/v2.0-Analysis-Loop.md §五 Phase 2 Gate 3.

设计决策 (P0-18 in v2.0 §五 table 6):
    - 单 Agent 场景: 跳过(无跨 Agent 契约概念)
    - 多 Agent 场景: 检查 .ae-contracts/ 下定义的契约 vs 各 Agent 实际实现
    - 当前 Phase 04 仅实现"单 Agent 跳过 + 多 Agent 占位"骨架
    - 完整 contract 校验在 Phase 05+ (有 RoundPlan 落地后)

核心 API:
    ContractGate.check(agent_count: int, contracts: dict | None) -> Verdict
"""

from __future__ import annotations

from pathlib import Path

from auto_engineering.gates.base import Gate, Verdict


class ContractGate(Gate):
    """Gate 3: 跨 Agent 契约检查.

    单 Agent 场景 → 跳过 (passed=True, "single agent").
    多 Agent 场景 → 检查 contracts 一致性(Phase 04: 占位).

    Args:
        contracts_dir: 契约定义目录(默认 .ae-contracts/)
    """

    name = "contract"

    def __init__(self, contracts_dir: str | Path | None = None):
        self.contracts_dir = Path(contracts_dir) if contracts_dir else Path(".ae-contracts")

    def run(
        self,
        project_root: Path,
        agent_count: int = 1,
        contracts: dict | None = None,
    ) -> Verdict:
        """执行契约检查.

        Args:
            project_root: 项目根目录(占位用, 未深度使用)
            agent_count: Agent 数量. 1 = 单 Agent (skip); >=2 = 多 Agent
            contracts: 契约字典(可选). Phase 04 暂未使用.

        Returns:
            Verdict: passed=True (skip 或检查通过)
        """
        # 单 Agent → 跳过
        if agent_count <= 1:
            return Verdict.passed(
                "skip: single agent mode, no cross-agent contract",
                gate_name=self.name,
            )

        # 多 Agent → Phase 04 占位: 若 contracts 为空, 视为通过(无契约违反)
        # 完整契约校验待 Phase 05+ (RoundPlan 落地后)
        if not contracts:
            return Verdict.passed(
                f"skip: multi-agent ({agent_count}) but no contracts defined",
                gate_name=self.name,
            )

        # Phase 05+ 实现: 校验各 Agent 实现 vs contracts
        # 当前占位: 仅校验 contracts 字典结构
        if not isinstance(contracts, dict):
            return Verdict.failed(
                f"contracts 必须是 dict, 实际为 {type(contracts).__name__}",
                gate_name=self.name,
            )

        return Verdict.passed(
            f"multi-agent ({agent_count}) contracts check passed (placeholder)",
            gate_name=self.name,
        )