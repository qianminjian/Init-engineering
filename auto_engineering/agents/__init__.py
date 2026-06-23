"""Agent 实现 — Claude API 驱动的智能角色.

核心类:
    BaseAgent       — LLM 调用 + 工具绑定
    ArchitectAgent  — 需求分析 → 实现计划
    DeveloperAgent  — TDD 三步循环实现
    CriticAgent     — 代码审查
"""

from .base import BaseAgent
from .architect import ArchitectAgent
from .developer import DeveloperAgent
from .critic import CriticAgent

__all__ = ["BaseAgent", "ArchitectAgent", "DeveloperAgent", "CriticAgent"]
