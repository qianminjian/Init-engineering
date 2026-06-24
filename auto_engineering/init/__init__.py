"""项目初始化 — 借鉴 Copier Worker + Cookiecutter generate.

核心类:
    InitWorker         — 5 阶段流水线编排
    TemplateConfig     — ae-template.yml 解析
    AnswersMap         — 5 层优先级答案解析
    InteractivePrompt  — 交互式问答
    TemplateRenderer   — Jinja2 双层渲染引擎
    TaskRunner         — pre/post 钩子执行
    ProjectDetector    — 项目类型自动检测
"""

from .answers import AnswersMap
from .config import Question, Task, TemplateConfig
from .detector import ProjectDetector
from .errors import (
    ConfigFileError,
    InitError,
    InitInterruptedError,
    TargetDirectoryError,
    TaskExecutionError,
    TemplateRenderError,
    UnsatisfiedPrerequisiteError,
    ValidationError,
)
from .hooks import TaskRunner
from .prompts import InteractivePrompt, prompt_for_project_type
from .renderer import TemplateRenderer
from .scaffold import InitResult, InitWorker, init_project

__all__ = [
    "AnswersMap",
    "ConfigFileError",
    # Errors
    "InitError",
    "InitInterruptedError",
    "InitResult",
    "InitWorker",
    "InteractivePrompt",
    "ProjectDetector",
    "Question",
    "TargetDirectoryError",
    "Task",
    "TaskExecutionError",
    "TaskRunner",
    "TemplateConfig",
    "TemplateRenderError",
    "TemplateRenderer",
    "UnsatisfiedPrerequisiteError",
    "ValidationError",
    "init_project",
    "prompt_for_project_type",
]
