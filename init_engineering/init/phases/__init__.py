"""5 阶段流水线 — 子模块包 (P2-B 拆分).

模块结构:
- detect.py    : phase_detect + _raise_nonempty + _validate_project_type
- prompt.py    : phase_prompt
- render.py    : phase_render
- finalize.py  : phase_finalize + _atomic_copytree + _write_replay

scaffold_phase_funcs.py 仍 re-export 所有 phase_* 函数 (向后兼容旧 import 路径).
"""

from .detect import phase_detect
from .finalize import phase_finalize
from .prompt import phase_prompt
from .render import phase_render

__all__ = [
    "phase_detect",
    "phase_finalize",
    "phase_prompt",
    "phase_render",
]