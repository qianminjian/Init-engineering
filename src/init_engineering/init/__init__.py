"""项目初始化 — 借鉴 Copier Worker + Cookiecutter generate。

公开 API：InitWorker / AnswersMap / TemplateConfig / ProjectDetector / error 类。
内部实现细节（InteractivePrompt / TemplateRenderer / TaskRunner 等）通过子模块导入。
"""

from .answers import AnswersMap
from .config_types import TemplateConfig
from .detector import ProjectDetector
from .errors import ConfigFileError, InitError
from .scaffold_phases import InitResult, InitWorker

__all__ = [
    "AnswersMap",
    "ConfigFileError",
    "InitError",
    "InitResult",
    "InitWorker",
    "ProjectDetector",
    "TemplateConfig",
]
