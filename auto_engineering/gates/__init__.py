"""v2.0 Phase 04 — 7 道 Gate + 向后兼容层.

设计来源: design/v2.0-Analysis-Loop.md §五 Phase 2.

Phase 04 新增:
    - Gate.run(project_root) 接口 → Verdict
    - Verdict 数据类(passed / message / gate_name)
    - 7 道 Gate: safety / lint / type_check / contract / test / coverage / build

向后兼容(Phase 1 / Phase 2):
    - Gate 基类保留(check 接口保留供 Guardrail 体系使用)
    - GuardrailResult / DropOutput / GuardrailChain 不动
    - 5 个内置 Guardrail 不动
"""

from __future__ import annotations

# v1.1 Guardrail 体系(向后兼容)
from .base import Gate, GateResult, Verdict  # noqa: F401
from .builtin import (  # noqa: F401
    GitCleanGuardrail,
    GitDiffExistsGuardrail,
    PlanExistsGuardrail,
    RequirementGuardrail,
    TestsPassGuardrail,
)

# v2.0 Phase 04 — 7 道 Gate
from .build import BuildGate  # noqa: F401
from .contract import ContractGate  # noqa: F401
from .coverage import CoverageGate  # noqa: F401
from .lint import LintGate  # noqa: F401
from .safety import SafetyGate  # noqa: F401
from .test import TestGate  # noqa: F401
from .type_check import TypeCheckGate  # noqa: F401

# Guardrail 体系(向后兼容)
from .guardrail import (  # noqa: F401
    DropOutput,
    GuardrailChain,
    GuardrailHandler,
    GuardrailResult,
)

# v2.0 7 道 Gate 的注册表(便于 Orchestrator 调度)
V2_GATES: list[type[Gate]] = [
    SafetyGate,
    LintGate,
    TypeCheckGate,
    ContractGate,
    TestGate,
    CoverageGate,
    BuildGate,
]


__all__ = [
    # v2.0 新接口
    "Verdict",
    # v2.0 7 道 Gate
    "SafetyGate",
    "LintGate",
    "TypeCheckGate",
    "ContractGate",
    "TestGate",
    "CoverageGate",
    "BuildGate",
    "V2_GATES",
    # 向后兼容
    "DropOutput",
    "Gate",
    "GateResult",
    "GitCleanGuardrail",
    "GitDiffExistsGuardrail",
    "GuardrailChain",
    "GuardrailHandler",
    "GuardrailResult",
    "PlanExistsGuardrail",
    "RequirementGuardrail",
    "TestsPassGuardrail",
]