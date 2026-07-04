"""Backward-compat shim — phase 函数实际在 phases/ 子包.

P2-B (2026-07-03 深度审计): scaffold_phase_funcs.py 379 行超 300 行约束,
拆分为 phases/{detect,prompt,render,finalize}.py.

子包命名选 phases/ 而非 scaffold_phases/ 是为了避免与 init/scaffold_phases.py
(InitWorker 主类所在模块) 同名冲突 — Python 包模块同名时包优先,会覆盖主类.

旧 import 路径 `from init_engineering.init.scaffold_phase_funcs import phase_*`
继续工作, 函数已迁移到子包, 此模块仅 re-export.
"""

from __future__ import annotations

# Re-export 5 个 phase_* 函数保持向后兼容
from .phases.detect import _validate_project_type, phase_detect
from .phases.finalize import phase_finalize
from .phases.prompt import phase_prompt
from .phases.render import phase_render
from .phases.tasks import phase_tasks

# 测试 patch("init_engineering.init.scaffold_phase_funcs._render_to") 需暴露此名.
# 用 __getattr__ (PEP 562) 懒加载, 避免与 phases/ 子包 import 时的循环依赖:
#   phases/__init__ → phases/render → scaffold_render (OK)
#   scaffold_phase_funcs → phases/detect → phases/__init__ (循环)
# _render_to 仅在测试 patch 时访问, 懒加载不影响生产路径.
def __getattr__(name):
    if name == "_render_to":
        from .scaffold_render import render_to
        return render_to
    raise AttributeError(f"module 'scaffold_phase_funcs' has no attribute {name!r}")


__all__ = [
    "_render_to",
    "_validate_project_type",
    "phase_detect",
    "phase_finalize",
    "phase_prompt",
    "phase_render",
    "phase_tasks",
]