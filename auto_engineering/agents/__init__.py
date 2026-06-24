"""Agent 实现 — Claude API 驱动的智能角色.

核心类:
    BaseAgent       — LLM 调用 + 工具绑定
    ArchitectAgent  — 需求分析 → 实现计划
    DeveloperAgent  — TDD 三步循环实现
    CriticAgent     — 代码审查
"""

from .architect import ArchitectAgent
from .base import BaseAgent
from .critic import CriticAgent
from .developer import DeveloperAgent

__all__ = ["ArchitectAgent", "BaseAgent", "CriticAgent", "DeveloperAgent"]
