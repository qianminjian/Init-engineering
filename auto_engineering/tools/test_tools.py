"""测试工具."""

from .base import BaseTool, ToolResult


class RunTestsTool(BaseTool):
    name = "run_tests"
    description = "运行项目测试。"
    parameters = {"scope": {"type": "string", "description": "测试范围: all/unit/integration/coverage"}}

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="")
