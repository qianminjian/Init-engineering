"""项目配置.

核心类:
    ProjectEnvironment  — 从 .ae-answers.yml + 代码自检测解析工程环境
"""

from .environment import ProjectEnvironment

__all__ = [
    "ProjectEnvironment",
]