"""InitError 体系 — 所有 init 子系统异常的基类。

参考来源：copier/errors.py:54-175 — CopierError → UserMessageError 三层继承。

接口约定：所有异常必须有 exit_code: int 属性，Click 入口据此设置 sys.exit(code)。
"""

from __future__ import annotations


class InitError(Exception):
    """基类，所有 init 异常继承此。

    exit_code 由 Click 入口读取并设置为进程退出码。
    recovery_hint 为可选的恢复建议，由 CLI 入口展示给用户。
    """

    exit_code: int = 1
    recovery_hint: str | None = None


class ConfigFileError(InitError):
    """ae-template.yml 不存在、格式错误、版本不兼容。"""

    exit_code = 2

    def __init__(self, message: str, *, config_path: str | None = None, reason: str | None = None):
        self.config_path = config_path
        self.reason = reason
        hint_parts = ["检查模板目录是否存在，确认 ae-template.yml 格式正确"]
        if config_path:
            hint_parts.append(f"config_path={config_path}")
        if reason:
            hint_parts.append(f"reason={reason}")
        self.recovery_hint = "；".join(hint_parts)
        super().__init__(message)


class UnsatisfiedPrerequisiteError(InitError):
    """git/node/python 等必需工具未安装。"""

    exit_code = 3

    def __init__(self, message: str, *, missing_tool: str = ""):
        if missing_tool:
            self.recovery_hint = f"安装 {missing_tool} 后重试，或检查 PATH 环境变量"
        else:
            self.recovery_hint = "安装缺失的工具后重试，或检查 PATH 环境变量"
        super().__init__(message)


class TargetDirectoryError(InitError):
    """目标目录不可写 / 非空且无 --force。"""

    exit_code = 4
    recovery_hint = "使用 --force 覆盖非空目录或 --incremental 增量补充"


class ValidationError(InitError):
    """用户输入校验失败（validator 返回非空）。"""

    exit_code = 5
    recovery_hint = "请根据提示修正输入值，或使用 --defaults 跳过交互"

    def __init__(
        self,
        message: str,
        *,
        field_name: str | None = None,
        raw_value: str | int | float | bool | list | None = None,
        constraint: str | None = None,
    ):
        self.field_name = field_name
        self.raw_value = raw_value
        self.constraint = constraint
        if field_name:
            hint = f"请修正 [{field_name}] 的值"
            if constraint:
                hint += f"（约束: {constraint}）"
            self.recovery_hint = hint
            super().__init__(f"校验失败 [{field_name}]: {message}")
        else:
            super().__init__(message)


class TaskExecutionError(InitError):
    """钩子命令执行失败。携带 process.returncode + stderr。"""

    exit_code = 6
    recovery_hint = "检查命令是否正确安装，确认网络连接正常，或使用 --skip-tasks 跳过钩子"

    def __init__(self, command: str, returncode: int, stderr: str):
        self.command = command
        self.subprocess_returncode = returncode
        self.stderr = stderr or ""
        preview = self.stderr[:500] + "..." if len(self.stderr) > 500 else self.stderr
        super().__init__(f"Task '{command}' failed (exit={returncode}): {preview}")


class TemplateRenderError(InitError):
    """Jinja2 渲染异常。携带源文件路径和行号。"""

    exit_code = 7
    recovery_hint = "检查模板文件中的 Jinja2 语法，确认变量名拼写正确"

    def __init__(self, src_path: str, jinja_error: Exception, line_number: int | None = None):
        self.src_path = src_path
        self.jinja_error = jinja_error
        self.line_number = line_number
        if line_number is not None:
            super().__init__(
                f"Template render error in {src_path} line {line_number}: {jinja_error}"
            )
        else:
            super().__init__(f"Template render error in {src_path}: {jinja_error}")


class InitInterruptedError(InitError):
    """用户 Ctrl-C 中断。部分答案已保存到 ~/.ae-partial-answers.yml。"""

    exit_code = 130
    recovery_hint = "使用 --from-answers ~/.ae-partial-answers.yml 恢复上次进度"


class ConfigLoaderSecurityError(InitError):
    """!include 路径安全校验失败 (越界/sandbox 违反/路径遍历)。"""

    exit_code = 8
    recovery_hint = "确认 !include 路径在项目目录或 white-listed sandbox 根目录内"

    def __init__(self, detail: str):
        super().__init__(detail)


class HookExecutionError(InitError):
    """钩子命令执行失败（strict 模式下抛出，非 strict 模式仅为 warning）。"""

    exit_code = 9
    recovery_hint = (
        "检查钩子命令是否正确。去掉 --strict 可让非关键钩子失败时降级为 warning 而非终止"
    )

    def __init__(self, command: str, subprocess_returncode: int = 1, stderr: str = ""):
        self.command = command
        self.subprocess_returncode = subprocess_returncode
        self.stderr = stderr or ""
        preview = self.stderr[:500] + "..." if len(self.stderr) > 500 else self.stderr
        super().__init__(f"Hook '{command}' failed (exit={subprocess_returncode}): {preview}")


class PathTraversalError(InitError):
    """路径穿越检测 — working_directory / external_data / !include 越界。"""

    exit_code = 10
    recovery_hint = "确认路径在项目目录或沙箱根目录内，或使用 --force-unsafe-path 显式绕过"
