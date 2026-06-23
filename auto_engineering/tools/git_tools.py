"""Git 工具."""

from .base import BaseTool, ToolResult


class GitStatusTool(BaseTool):
    name = "git_status"
    description = "查看 git 工作区和暂存区状态。"
    parameters = {}

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="")


class GitCommitTool(BaseTool):
    name = "git_commit"
    description = "提交所有变更。"
    parameters = {"message": {"type": "string", "description": "commit 信息"}}

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="")


class GitDiffTool(BaseTool):
    name = "git_diff"
    description = "查看当前变更的 diff。"
    parameters = {"target": {"type": "string", "description": "比较目标"}}

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="")
