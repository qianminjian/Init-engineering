"""InitWorker — 5 阶段流水线编排器（参考 Copier Worker）。

v2.2 Phase I 拆分（backward-compat re-export 层）。

实际实现已拆到：
- scaffold_phases.py : InitResult dataclass + InitWorker 5 阶段流水线
- scaffold_hooks.py  : 内置钩子执行
- phases/finalize.py : 增量合并 (PR#3 P1-1)

本模块保持旧路径 from init.scaffold import ... 可工作（见 __all__）。
"""

from pathlib import Path

from .scaffold_hooks import run_builtin_hooks
from .scaffold_phases import InitResult, InitWorker

# PR#3 P1-1: 放最后 — phases.finalize 触发 phases/__init__.py → phases/render.py
# → scaffold_phase_funcs.py → phases.render 循环,需 scaffold_phase_funcs 先加载完
from .phases.finalize import merge_incremental

__all__ = [
    "InitResult",
    "InitWorker",
    "init_project",
    "merge_incremental",
    "run_builtin_hooks",
]


def init_project(dst_path: str | Path, project_type: str | None = None, **kwargs) -> InitResult:
    with InitWorker(dst_path=Path(dst_path), project_type=project_type, **kwargs) as w:
        return w.execute()
