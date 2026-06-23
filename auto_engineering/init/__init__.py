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

from .scaffold import InitWorker, InitResult, init_project
from .config import TemplateConfig, Question, Task
from .answers import AnswersMap
from .prompts import InteractivePrompt, prompt_for_project_type
from .renderer import TemplateRenderer
from .hooks import TaskRunner
from .detector import ProjectDetector
from .errors import (
    InitError,
    ConfigFileError,
    UnsatisfiedPrerequisiteError,
    TargetDirectoryError,
    ValidationError,
    TaskExecutionError,
    TemplateRenderError,
    InitInterruptedError,
)

__all__ = [
    "InitWorker", "InitResult", "init_project",
    "TemplateConfig", "Question", "Task",
    "AnswersMap",
    "InteractivePrompt", "prompt_for_project_type",
    "TemplateRenderer",
    "TaskRunner",
    "ProjectDetector",
    # Errors
    "InitError",
    "ConfigFileError",
    "UnsatisfiedPrerequisiteError",
    "TargetDirectoryError",
    "ValidationError",
    "TaskExecutionError",
    "TemplateRenderError",
    "InitInterruptedError",
]
