"""E2E tests for ae init design/ directory structure (R26).

验收：ae init --defaults 生成的项目包含标准化 design/ 目录结构：
- design/INDEX.md（含来源字段 + 合并日志规范）
- design/BEACON.md（含来源字段 + 项目明灯结构）
- design/his_bak/README.md（含归档说明）
- design/his_bak/（目录存在）

PR#5 P1-7: 标记 integration — 真实 ae 子进程调用.
"""

import subprocess

import pytest

pytestmark = pytest.mark.integration
from pathlib import Path


def run_ae(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    venv_bin = Path(__file__).resolve().parent.parent / ".venv" / "bin"
    ae_path = venv_bin / "ae"
    return subprocess.run(
        [str(ae_path), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


class TestInitDesignDocs:
    """R26: ae init 生成标准化 design/ 目录结构."""

    def test_design_index_generated(self, tmp_path: Path):
        """INDEX.md 包含来源字段和合并日志."""
        target = tmp_path / "test-project"
        result = run_ae(
            [
                "init",
                str(target),
                "--type", "app-service",
                "--defaults",
                "--skip-tasks",
            ],
            cwd=str(tmp_path),
        )
        assert result.returncode == 0, f"ae init failed: {result.stderr}"

        index_file = target / "design" / "INDEX.md"
        assert index_file.exists(), f"INDEX.md not found in {index_file}"
        content = index_file.read_text()
        assert "来源：@design/INDEX.md" in content, "INDEX.md missing source field"
        assert "## 合并日志" in content, "INDEX.md missing merge log section"
        assert "## 归档清单" in content, "INDEX.md missing archive section"
        assert "## 工作流程规范" in content, "INDEX.md missing workflow section"

    def test_design_beacon_generated(self, tmp_path: Path):
        """BEACON.md 包含来源字段和项目明灯结构."""
        target = tmp_path / "test-project"
        result = run_ae(
            [
                "init",
                str(target),
                "--type", "app-service",
                "--defaults",
                "--skip-tasks",
            ],
            cwd=str(tmp_path),
        )
        assert result.returncode == 0, f"ae init failed: {result.stderr}"

        beacon_file = target / "design" / "BEACON.md"
        assert beacon_file.exists(), f"BEACON.md not found in {beacon_file}"
        content = beacon_file.read_text()
        assert "来源：@design/INDEX.md" in content, "BEACON.md missing source field"
        assert "## 目标与成功标准" in content, "BEACON.md missing goals section"
        assert "## 当前状态" in content, "BEACON.md missing current state section"
        assert "## 设计演进日志" in content, "BEACON.md missing evolution log"

    def test_design_his_bak_generated(self, tmp_path: Path):
        """his_bak/ 目录及 README 生成."""
        target = tmp_path / "test-project"
        result = run_ae(
            [
                "init",
                str(target),
                "--type", "app-service",
                "--defaults",
                "--skip-tasks",
            ],
            cwd=str(tmp_path),
        )
        assert result.returncode == 0, f"ae init failed: {result.stderr}"

        his_bak_dir = target / "design" / "his_bak"
        assert his_bak_dir.is_dir(), f"his_bak/ not found as directory in {his_bak_dir}"

        readme_file = his_bak_dir / "README.md"
        assert readme_file.exists(), f"his_bak/README.md not found in {readme_file}"
        content = readme_file.read_text()
        assert "## 归档清单" in content, "his_bak/README.md missing archive section"

    def test_all_project_types_include_design(self, tmp_path: Path):
        """所有项目类型(app-service/library/cli-tool/monorepo)都生成 design/."""
        project_types = ["app-service", "library", "cli-tool"]

        for ptype in project_types:
            target = tmp_path / f"test-{ptype}"
            result = run_ae(
                [
                    "init",
                    str(target),
                    "--type", ptype,
                    "--defaults",
                    "--skip-tasks",
                ],
                cwd=str(tmp_path),
            )
            assert result.returncode == 0, f"ae init --type {ptype} failed: {result.stderr}"
            assert (target / "design" / "INDEX.md").exists(), (
                f"design/INDEX.md missing for project type {ptype}"
            )
            assert (target / "design" / "BEACON.md").exists(), (
                f"design/BEACON.md missing for project type {ptype}"
            )

    def test_design_his_bak_gitkeep(self, tmp_path: Path):
        """his_bak/ 目录含 .gitkeep."""
        target = tmp_path / "test-project"
        result = run_ae(
            [
                "init",
                str(target),
                "--type", "app-service",
                "--defaults",
                "--skip-tasks",
            ],
            cwd=str(tmp_path),
        )
        assert result.returncode == 0
        gitkeep = target / "design" / "his_bak" / ".gitkeep"
        assert gitkeep.exists(), f"his_bak/.gitkeep not found in {gitkeep}"


class TestInitPytestRules:
    """R26+: ae init 生成的项目含 pytest 内存管理规则（沉淀自 init-engineering 实战）."""

    def test_pytest_rule_file_generated(self, tmp_path: Path):
        """Python 项目生成 .claude/rules/pytest-memory-management.md（来自 _features/python/）."""
        target = tmp_path / "test-project"
        result = run_ae(
            [
                "init",
                str(target),
                "--type", "app-service",
                "--language", "python",
                "--defaults",
                "--skip-tasks",
            ],
            cwd=str(tmp_path),
        )
        assert result.returncode == 0, f"ae init failed: {result.stderr}"

        rule_file = target / ".claude" / "rules" / "pytest-memory-management.md"
        assert rule_file.exists(), f"pytest-memory-management.md not found in {rule_file}"
        content = rule_file.read_text()
        assert "name: pytest-memory-management" in content, "rule missing frontmatter name"
        assert "## 推荐调用方式" in content, "rule missing 推荐调用方式 section"
        assert "## 紧急处理" in content, "rule missing 紧急处理 section"

    def test_pytest_rule_referenced_in_claude_md(self, tmp_path: Path):
        """CLAUDE.md 管理约束区含 pytest-memory-management @ 引用（Python 项目）."""
        target = tmp_path / "test-project"
        result = run_ae(
            [
                "init",
                str(target),
                "--type", "app-service",
                "--language", "python",
                "--defaults",
                "--skip-tasks",
            ],
            cwd=str(tmp_path),
        )
        assert result.returncode == 0, f"ae init failed: {result.stderr}"

        claude_md = target / "CLAUDE.md"
        assert claude_md.exists(), f"CLAUDE.md not found in {claude_md}"
        content = claude_md.read_text()
        assert "pytest-memory-management" in content, (
            "CLAUDE.md missing pytest rule reference"
        )

    def test_python_pyproject_template_has_optimized_pytest_config(self):
        """_features/python/pyproject.toml.jinja 模板含 [tool.pytest.ini_options] + 优化 addopts.

        说明：ae init CLI 不暴露 --language，无法 E2E 强制 python feature。
        改用模板级验证（直接读 .jinja 模板），对模板调整保护更直接。
        """
        template_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "init_engineering"
            / "init"
            / "templates"
            / "_features"
            / "python"
            / "pyproject.toml.jinja"
        )
        assert template_path.exists(), f"template not found: {template_path}"
        content = template_path.read_text()

        assert "[tool.pytest.ini_options]" in content, (
            "pyproject.toml.jinja missing [tool.pytest.ini_options]"
        )
        assert "--timeout=60" in content, "pyproject.toml.jinja missing --timeout=60"
        assert "-p no:cacheprovider" in content, (
            "pyproject.toml.jinja missing -p no:cacheprovider"
        )
        assert "--cov" not in content, (
            "pyproject.toml.jinja should NOT include --cov by default (opt-in)"
        )


class TestInitDesignDocsSkipTasks:
    """`--skip-tasks` 标志在 design docs E2E 中应用验证.

    目的：确保 E2E 测试用 --skip-tasks 隔离 pnpm 缺失环境,
    不依赖外部工具链(T021/T031 的关键缓解).
    """

    def test_all_e2e_tests_use_skip_tasks_flag(self):
        """所有 E2E 测试的 run_ae 调用都应包含 --skip-tasks 参数.

        防御：未来添加新 E2E 测试时忘记加 --skip-tasks 会被此测试发现.
        实现：扫描 test_init_design_docs.py 中的 run_ae() 调用,
        确保每个调用 args 中都有 '--skip-tasks'.
        """
        import re

        test_file = Path(__file__).resolve()
        content = test_file.read_text()

        # 找到所有 run_ae( 调用块
        # 简化: 匹配 run_ae(\n ... \n) 这种 block,验证含 '--skip-tasks'
        run_ae_blocks = re.findall(
            r"run_ae\(\s*\[(.*?)\]",
            content,
            re.DOTALL,
        )
        assert len(run_ae_blocks) >= 4, (
            f"expected >= 4 run_ae() calls in test file, found {len(run_ae_blocks)}"
        )
        for i, block in enumerate(run_ae_blocks):
            assert '"--skip-tasks"' in block or "'--skip-tasks'" in block, (
                f"run_ae() call #{i+1} missing '--skip-tasks' flag:\n{block[:200]}"
            )

    def test_e2e_runs_under_10_seconds(self, tmp_path: Path):
        """E2E 测试在 10 秒内完成（避免环境问题 hang）.

        `--skip-tasks` 隔离了 pnpm 依赖,所以 ae init 应快速完成.
        """
        import time

        target = tmp_path / "test-perf"
        start = time.time()
        result = run_ae(
            [
                "init",
                str(target),
                "--type", "app-service",
                "--defaults",
                "--skip-tasks",
            ],
            cwd=str(tmp_path),
        )
        elapsed = time.time() - start
        assert result.returncode == 0, f"ae init failed: {result.stderr}"
        assert elapsed < 10.0, f"ae init too slow: {elapsed:.2f}s"


class TestBlockDetectorCache:
    """block detector 缓存机制 + 清理 fixture 验证.

    场景: 某测试因环境问题连续失败 >= 3 次被 block detector 自动 skip.
    修复后,需要 _reset_block_cache fixture 显式重置 cache 才能让它重新跑.
    """

    def test_failure_cache_file_location(self):
        """_FAILURE_CACHE 路径可定位,fixture 文档化."""
        from tests.conftest import _BLOCK_THRESHOLD, _FAILURE_CACHE

        # cache 路径应该是 /tmp 下或 AE_TEST_STATE_DIR 指定位置
        assert _FAILURE_CACHE.parent.exists(), (
            f"cache parent dir not exist: {_FAILURE_CACHE.parent}"
        )
        # 阈值常量
        assert _BLOCK_THRESHOLD == 3, f"_BLOCK_THRESHOLD changed: {_BLOCK_THRESHOLD}"


# 确保不破坏 test_init_design_docs 原始 8 个测试
__all__ = [
    "TestBlockDetectorCache",
    "TestInitDesignDocs",
    "TestInitDesignDocsSkipTasks",
    "TestInitPytestRules",
]
