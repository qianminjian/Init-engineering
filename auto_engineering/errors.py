"""Init-Engineering 错误体系.

从 init/errors.py 重新导出，保持向后兼容。
v5.0 之前的历史错误码(ErrorCode/AEError)已废弃。
"""

from auto_engineering.init.errors import (
    ConfigFileError,
    ConfigLoaderSecurityError,
    HookExecutionError,
    InitError,
    InitInterruptedError,
    TargetDirectoryError,
    TaskExecutionError,
    TemplateRenderError,
    UnsatisfiedPrerequisiteError,
    ValidationError,
)

__all__ = [
    "InitError",
    "ConfigFileError",
    "UnsatisfiedPrerequisiteError",
    "TargetDirectoryError",
    "ValidationError",
    "TaskExecutionError",
    "TemplateRenderError",
    "InitInterruptedError",
    "ConfigLoaderSecurityError",
    "HookExecutionError",
]
