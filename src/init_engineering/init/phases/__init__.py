"""5 阶段流水线子模块包。

各阶段实现在对应子模块中，外部通过 scaffold_phases.py 导入。
"""

from __future__ import annotations

import re

from ..errors import ValidationError


def validate_project_type(project_type: str) -> None:
    """防路径穿越：project_type 仅允许字母/数字/下划线/连字符。

    来源：所有项目类型（CLI / detector / 交互）都需通过此校验。
    之前在 phase_finalize 校验，但 ~/.ae-replays/<type>/ 路径已在更早阶段生成。
    """
    if not re.match(r"^[A-Za-z0-9_-]+$", project_type):
        raise ValidationError(
            f"project_type '{project_type}' 含非法字符。"
            f"只允许字母/数字/下划线/连字符 (防路径穿越)."
        )
