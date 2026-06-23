"""质量闸门 — Python 代码级检查（借鉴 LangGraph interrupt_before/after）.

核心类:
    Gate           — 闸门基类
    PlanExistsGate — plan 文件存在检查
    GitCleanGate   — git status 干净检查
    TestsPassGate  — 测试全绿检查
"""

from .base import Gate, GateResult
from .gates import PlanExistsGate, GitCleanGate, TestsPassGate, GitDiffExistsGate

__all__ = ["Gate", "GateResult", "PlanExistsGate", "GitCleanGate", "TestsPassGate", "GitDiffExistsGate"]
