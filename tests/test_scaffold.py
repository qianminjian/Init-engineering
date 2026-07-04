"""tests for init/scaffold.py — init_project 顶层入口 + backward-compat re-exports.

PR#5 P1-6: 原 test_scaffold.py 仅 1 个 import 测试 (孤儿文件).
scaffold.py 实为 backward-compat re-export shim (InitResult/InitWorker/merge_incremental/
run_builtin_hooks/init_project), 需专项测试覆盖:

1. init_project() 顶层入口能正常调用 (已有 1 个, 补 preset 透传)
2. __all__ 完整 re-export — 防止 backward-compat 路径悄悄消失
3. scaffold.py 的 re-export 与原模块是同一对象 (防止双份定义 drift)
"""

from pathlib import Path

from init_engineering.init import scaffold as scaffold_module
from init_engineering.init.phases.finalize import merge_incremental as _orig_merge
from init_engineering.init.scaffold import (
    InitResult,
    InitWorker,
    init_project,
    merge_incremental,
    run_builtin_hooks,
)
from init_engineering.init.scaffold_hooks import run_builtin_hooks as _orig_hooks


class TestInitProject:
    """init_project — 顶层入口函数 (scaffold.py:33-35)."""

    def test_init_project_returns_init_result(self, tmp_path: Path):
        """init_project(dst_path, project_type, **kwargs) 返回 InitResult."""
        proj = tmp_path / "testproj"
        result = init_project(
            str(proj),
            project_type="app-service",
            defaults=True,
            skip_tasks=True,
            pretend=True,
        )
        assert result.dst_path == proj
        assert isinstance(result.files, list)

    def test_init_project_accepts_path_object(self, tmp_path: Path):
        """init_project 接受 Path 对象 (不必 str)."""
        proj = tmp_path / "p"
        result = init_project(
            proj,
            project_type="library",
            defaults=True,
            pretend=True,
        )
        assert result.dst_path == proj

    def test_init_project_kwargs_propagate(self, tmp_path: Path):
        """**kwargs 透传到 InitWorker (含 hook_timeout / no_install 等)."""
        proj = tmp_path / "p"
        result = init_project(
            proj,
            project_type="library",
            defaults=True,
            pretend=True,
            no_install=True,
            hook_timeout=10,
        )
        assert result.project_type == "library"


class TestReExportBackwardCompat:
    """scaffold.py 作为 backward-compat re-export 层 — 防止双份定义 drift."""

    def test_merge_incremental_is_same_object(self):
        """merge_incremental re-export 与原模块是同一对象 (PR#3 P1-1)."""
        assert merge_incremental is _orig_merge

    def test_run_builtin_hooks_is_same_object(self):
        """run_builtin_hooks re-export 与原模块是同一对象."""
        assert run_builtin_hooks is _orig_hooks

    def test_initworker_reexport_works(self):
        """InitWorker re-export 可正常使用 (创建实例)."""
        worker = InitWorker(
            dst_path=Path("/tmp/test"),
            project_type="library",
            defaults=True,
        )
        assert worker.dst_path == Path("/tmp/test")
        assert worker.project_type == "library"

    def test_initresult_reexport_works(self):
        """InitResult re-export 可正常使用."""
        # InitResult dataclass 字段检查
        from dataclasses import fields
        f_names = {f.name for f in fields(InitResult)}
        assert "dst_path" in f_names
        assert "project_type" in f_names
        assert "files" in f_names

    def test_all_exports_present(self):
        """__all__ 完整 — 防止悄悄从 backward-compat 路径删除符号."""
        assert set(scaffold_module.__all__) == {
            "InitResult",
            "InitWorker",
            "init_project",
            "merge_incremental",
            "run_builtin_hooks",
        }