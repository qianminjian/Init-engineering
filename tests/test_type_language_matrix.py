"""类型 × 语言 32 组合测试 — 补齐模板组合覆盖率。

来源：BEACON.md 决策 + 审计 P1-9。

覆盖矩阵：
  - app-service / cli-tool / library / monorepo × typescript / python / go / rust = 16 组合
  - skill / hook × bash / python / typescript = 6 组合
  - mcp-server × typescript = 1 组合
  - spec-doc × typescript / python / go / rust = 4 组合
  合计：27 组合
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _run_ae_init(
    target: Path,
    project_type: str,
    language: str,
    *,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """调用 ae init --defaults 验证某个 project_type × language 组合能成功渲染."""
    venv_bin = Path(__file__).resolve().parent.parent / ".venv" / "bin"
    ae_path = venv_bin / "ae"
    args = [
        str(ae_path),
        "init",
        str(target),
        "--type", project_type,
        "--language", language,
        "--defaults",
        "--skip-tasks",
    ]
    if extra_args:
        args.extend(extra_args)
    return subprocess.run(args, capture_output=True, text=True)


def _language_marker(language: str) -> str:
    """返回验证文件应包含的语言标识符."""
    return {
        "typescript": "tsconfig.json",
        "python": "pyproject.toml",
        "go": "go.mod",
        "rust": "Cargo.toml",
        "bash": ".sh",
    }.get(language, "")


# ─── 4 主类型 × 4 语言 = 16 组合 ────────────────────────────────────────


@pytest.mark.parametrize("project_type", ["app-service", "cli-tool", "library", "monorepo"])
@pytest.mark.parametrize("language", ["typescript", "python", "go", "rust"])
def test_main_type_language_combo(project_type: str, language: str, tmp_path: Path):
    """4 主类型 × 4 语言组合 — 验证模板渲染不报错 + 产出语言标记文件."""
    target = tmp_path / f"{project_type}-{language}"
    result = _run_ae_init(target, project_type, language)

    assert result.returncode == 0, (
        f"ae init failed for {project_type}/{language}: "
        f"returncode={result.returncode}, stderr={result.stderr}"
    )
    assert target.exists(), f"target {target} not created"

    marker = _language_marker(language)
    if marker:
        # 检查是否生成对应的语言标记文件（顶层）
        has_marker = any(
            f.name == marker or f.name == f"{marker}.jinja"
            for f in target.rglob(marker)
        )
        # 因 .jinja 后缀在渲染时被剥离，target.txt 顶层应出现 marker 文件
        # 或在 monorepo 的子目录中
        if not has_marker and project_type != "monorepo":
            # 只对非 monorepo 严格检查顶层 marker
            assert any(f.name == marker for f in target.iterdir()), (
                f"{project_type}/{language}: 期望顶层生成 {marker}, "
                f"实际目录: {list(f.name for f in target.iterdir())[:10]}"
            )


# ─── skill / hook × 3 语言 = 6 组合 ──────────────────────────────────────


@pytest.mark.parametrize("language", ["bash", "python", "typescript"])
def test_skill_language_combo(language: str, tmp_path: Path):
    """skill 类型 × 3 语言."""
    target = tmp_path / f"skill-{language}"
    result = _run_ae_init(target, "skill", language)
    assert result.returncode == 0, f"skill/{language}: {result.stderr}"
    assert target.exists()


@pytest.mark.parametrize("language", ["bash", "python", "typescript"])
def test_hook_language_combo(language: str, tmp_path: Path):
    """hook 类型 × 3 语言."""
    target = tmp_path / f"hook-{language}"
    result = _run_ae_init(target, "hook", language)
    assert result.returncode == 0, f"hook/{language}: {result.stderr}"
    assert target.exists()


# ─── mcp-server × typescript = 1 组合 ─────────────────────────────────────


def test_mcp_server_typescript(tmp_path: Path):
    """mcp-server 类型 (固定 TypeScript)."""
    target = tmp_path / "mcp"
    result = _run_ae_init(target, "mcp-server", "typescript")
    assert result.returncode == 0, f"mcp-server: {result.stderr}"
    assert target.exists()


# ─── spec-doc × 4 语言 = 4 组合 ──────────────────────────────────────────


@pytest.mark.parametrize("language", ["typescript", "python", "go", "rust"])
def test_spec_doc_language_combo(language: str, tmp_path: Path):
    """spec-doc 类型 × 4 语言（仅作代码示例，不生成可执行代码）."""
    target = tmp_path / f"spec-{language}"
    result = _run_ae_init(target, "spec-doc", language)
    assert result.returncode == 0, f"spec-doc/{language}: {result.stderr}"
    assert target.exists()


# ─── 边界场景 ─────────────────────────────────────────────────────────────


def test_app_service_with_ci_and_lefthook_and_docker(tmp_path: Path):
    """app-service + CI + Lefthook + Docker 全开 — 验证条件渲染联动."""
    target = tmp_path / "app-full"
    result = _run_ae_init(
        target, "app-service", "python",
        extra_args=["--ci", "github", "--use-lefthook", "--use-docker"],
    )
    assert result.returncode == 0, f"full combo: {result.stderr}"
    assert target.exists()


def test_app_service_python_no_typescript(tmp_path: Path):
    """app-service python --no-typescript — 验证 --no-typescript 关闭."""
    target = tmp_path / "app-py-no-ts"
    result = _run_ae_init(
        target, "app-service", "python",
        extra_args=["--no-typescript"],
    )
    assert result.returncode == 0, f"--no-typescript: {result.stderr}"