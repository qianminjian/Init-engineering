"""tests for init/scaffold.py — init_project."""

from pathlib import Path

from auto_engineering.init.scaffold import init_project


class TestInitProject:
    """init_project — 顶层入口函数 (lines 26-28)."""

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
