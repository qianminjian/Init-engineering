"""Skill 类型定义 — SkillResult. 独立模块以避免 _runner ↔ __init__ 循环依赖."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SkillResult:
    """Skill 执行结果。"""

    success: bool
    message: str
    action: str = ""  # "init", "analyze", "detect"
    project_path: str | None = None  # 展示用字符串 (str(Path)), 非 Path 对象
    project_type: str | None = None
    candidates: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
