"""InitError 体系."""


class InitError(Exception):
    exit_code: int = 1


class ConfigFileError(InitError):
    exit_code = 2


class UnsatisfiedPrerequisiteError(InitError):
    exit_code = 3


class TargetDirectoryError(InitError):
    exit_code = 4


class ValidationError(InitError):
    exit_code = 5


class TaskExecutionError(InitError):
    exit_code = 6

    def __init__(self, command: str, returncode: int, stderr: str):
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"Task '{command}' failed (exit={returncode}): {stderr}")


class TemplateRenderError(InitError):
    exit_code = 7

    def __init__(self, src_path: str, jinja_error: Exception):
        self.src_path = src_path
        self.jinja_error = jinja_error
        super().__init__(f"Template render error in {src_path}: {jinja_error}")


class InitInterruptedError(InitError):
    exit_code = 130
