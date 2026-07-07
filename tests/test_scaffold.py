"""tests for init/scaffold_phases.py — InitWorker 入口。

scaffold.py (re-export shim) 已在 R7 审计中删除，scaffold_phases.py 为规范实现。
"""

from pathlib import Path

from init_engineering.init.scaffold_phases import InitResult, InitWorker


class TestInitWorkerConvenience:
    """InitWorker 直接使用 — init_project 便利函数已移除 (v1.0 audit P0#4)."""

    def test_initworker_returns_init_result(self, tmp_path: Path):
        """InitWorker(dst_path, ...).execute() 返回 InitResult."""
        proj = tmp_path / "testproj"
        with InitWorker(
            dst_path=proj,
            project_type="app-service",
            defaults=True,
            skip_tasks=True,
            pretend=True,
        ) as w:
            result = w.execute()
        assert result.dst_path == proj
        assert isinstance(result.files, list)

    def test_initworker_accepts_path_object(self, tmp_path: Path):
        """InitWorker 接受 Path 对象."""
        proj = tmp_path / "p"
        with InitWorker(
            dst_path=proj,
            project_type="library",
            defaults=True,
            pretend=True,
        ) as w:
            result = w.execute()
        assert result.dst_path == proj

    def test_initworker_kwargs_propagate(self, tmp_path: Path):
        """**kwargs 透传到 InitWorker (含 hook_timeout / no_install 等)."""
        proj = tmp_path / "p"
        with InitWorker(
            dst_path=proj,
            project_type="library",
            defaults=True,
            pretend=True,
            no_install=True,
            hook_timeout=10,
        ) as w:
            result = w.execute()
        assert result.project_type == "library"


class TestInitWorker:
    """InitWorker / InitResult dataclass 字段."""

    def test_initworker_creates(self):
        """InitWorker 创建实例."""
        worker = InitWorker(
            dst_path=Path("/tmp/test"),
            project_type="library",
            defaults=True,
        )
        assert worker.dst_path == Path("/tmp/test")
        assert worker.project_type == "library"

    def test_initresult_fields(self):
        """InitResult dataclass 字段检查."""
        from dataclasses import fields

        f_names = {f.name for f in fields(InitResult)}
        assert "dst_path" in f_names
        assert "project_type" in f_names
        assert "files" in f_names
