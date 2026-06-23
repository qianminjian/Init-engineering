"""全局配置."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    """项目级配置。从 pyproject.toml + 环境变量加载。"""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096
    workspace_root: Path = field(default_factory=Path.cwd)


# 全局单例
settings = Settings()
