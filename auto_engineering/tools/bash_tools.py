"""Bash 工具."""

from .base import BaseTool, ToolResult


class RunBashTool(BaseTool):
    name = "run_bash"
    description = "执行 shell 命令并返回输出。"
    parameters = {
        "command": {"type": "string", "description": "要执行的 shell 命令"},
        "timeout": {"type": "integer", "description": "超时秒数，默认 120"},
    }

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="")
