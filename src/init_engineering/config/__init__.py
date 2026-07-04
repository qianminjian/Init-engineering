"""项目配置.

核心类:
    Settings            — 全局配置
    ProjectEnvironment  — 从 .ae-answers.yml + 代码自检测解析工程环境
"""

from .environment import ProjectEnvironment
from .settings import Settings

__all__ = [
    "ProjectEnvironment",
    "Settings",
]