"""工具系统 — Agent 可用的文件/Bash/Git/测试工具.

核心类:
    BaseTool      — 工具基类 (JSON Schema + 安全执行)
    ReadFileTool  — 读取文件
    WriteFileTool — 创建/覆写文件
    EditFileTool  — 精确字符串替换
    RunBashTool   — 执行 shell 命令
    GitCommitTool — 提交变更
    RunTestsTool  — 运行测试
"""

from .base import BaseTool, ToolResult
from .file_tools import ReadFileTool, WriteFileTool, EditFileTool, SearchCodeTool, ListDirTool
from .bash_tools import RunBashTool
from .git_tools import GitStatusTool, GitCommitTool, GitDiffTool
from .test_tools import RunTestsTool

__all__ = [
    "BaseTool", "ToolResult",
    "ReadFileTool", "WriteFileTool", "EditFileTool", "SearchCodeTool", "ListDirTool",
    "RunBashTool",
    "GitStatusTool", "GitCommitTool", "GitDiffTool",
    "RunTestsTool",
]
