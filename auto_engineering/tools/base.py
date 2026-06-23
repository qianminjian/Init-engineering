"""工具基类."""

from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class ToolResult:
    """工具执行结果。"""
    success: bool
    content: str
    error: str | None = None


class BaseTool(ABC):
    """工具基类。"""

    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        ...

    def to_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.parameters,
                "required": list(self.parameters.keys()),
            },
        }
