"""任务编排 — 借鉴 CrewAI crew.py.

核心类:
    Task              — 描述 + 验收标准 + Agent + 上下文
    SequentialProcess — 顺序任务执行
    Crew              — kickoff() 入口
"""

from .task import Task
from .process import SequentialProcess
from .crew import Crew

__all__ = ["Task", "SequentialProcess", "Crew"]
