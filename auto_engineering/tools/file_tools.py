"""文件操作工具."""

from .base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "读取文件内容。支持指定行号范围。"
    parameters = {
        "file_path": {"type": "string", "description": "文件绝对路径"},
        "offset": {"type": "integer", "description": "起始行号（从 1 开始）"},
        "limit": {"type": "integer", "description": "读取行数，默认 200"},
    }

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="")


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "创建或覆写文件。"
    parameters = {
        "file_path": {"type": "string", "description": "文件绝对路径"},
        "content": {"type": "string", "description": "文件完整内容"},
    }

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="")


class EditFileTool(BaseTool):
    name = "edit_file"
    description = "精确替换文件中的字符串。"
    parameters = {
        "file_path": {"type": "string", "description": "文件绝对路径"},
        "old_string": {"type": "string", "description": "要替换的原字符串"},
        "new_string": {"type": "string", "description": "替换后的新字符串"},
    }

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="")


class SearchCodeTool(BaseTool):
    name = "search_code"
    description = "在项目中搜索代码。"
    parameters = {
        "pattern": {"type": "string", "description": "搜索模式"},
        "path": {"type": "string", "description": "搜索路径"},
        "file_pattern": {"type": "string", "description": "文件名过滤"},
    }

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="")


class ListDirTool(BaseTool):
    name = "list_dir"
    description = "列出目录内容。"
    parameters = {"path": {"type": "string", "description": "目录路径"}}

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="")
