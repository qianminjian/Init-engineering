"""Helper detection functions — 拆自 detector.py (v2.5: 382→可控)。

设计：
- _detect_package_manager() / _detect_test_runner() / _detect_ci_platform() / _signature_matches() / _check_pkg_dep() 一律下沉到本模块
- detector.py 只保留 datatypes + ProjectDetector class
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

# ─── 包管理器检测 ─────────────────────────────────────────────────────

_LOCK_FILE_MAP: dict[str, str] = {
    "package-lock.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "bun.lockb": "bun",
    "uv.lock": "uv",
    "poetry.lock": "poetry",
    "Pipfile.lock": "pipenv",
}

# ─── 测试框架检测 ─────────────────────────────────────────────────────

_TEST_CONFIG_MAP: dict[str, str] = {
    "vitest.config.ts": "vitest",
    "vitest.config.js": "vitest",
    "vitest.config.mjs": "vitest",
    "jest.config.ts": "jest",
    "jest.config.js": "jest",
    "jest.config.mjs": "jest",
    "pytest.ini": "pytest",
    "tox.ini": "pytest",
    "pyproject.toml": "pytest",
}

# ─── CI 平台检测 ──────────────────────────────────────────────────────

_CI_DETECT_MAP: dict[str, str] = {
    ".github/workflows": "github",
    ".gitlab-ci.yml": "gitlab",
}


def detect_package_manager(target_dir: Path) -> str | None:
    """通过 lock 文件推断包管理器。有多个时按优先级返回."""
    priority = ["pnpm-lock.yaml", "yarn.lock", "bun.lockb", "package-lock.json",
                "uv.lock", "poetry.lock", "Pipfile.lock"]
    for lock in priority:
        if (target_dir / lock).exists():
            return _LOCK_FILE_MAP[lock]
    pkg_json = target_dir / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text())
            pm = data.get("packageManager", "")
            if isinstance(pm, str) and pm:
                return pm.split("@")[0]
        except (json.JSONDecodeError, OSError):
            pass
    return None


def detect_test_runner(target_dir: Path, language: str | None = None) -> str | None:
    """通过配置文件和依赖推断测试框架."""
    for config, runner in _TEST_CONFIG_MAP.items():
        if (target_dir / config).exists():
            return runner
    if language == "python":
        return "pytest"
    if language in ("typescript", "javascript"):
        pkg = target_dir / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                if "vitest" in deps:
                    return "vitest"
                if "jest" in deps:
                    return "jest"
            except (json.JSONDecodeError, OSError):
                pass
        return "vitest"
    if language == "go":
        return "go test"
    if language == "rust":
        return "cargo test"
    return None


def detect_ci_platform(target_dir: Path) -> str | None:
    """通过 CI 配置文件推断 CI 平台."""
    for config_dir, platform in _CI_DETECT_MAP.items():
        path = target_dir / config_dir
        if path.exists() and (path.is_dir() or path.is_file()):
            return platform
    return None


def check_pkg_dep(target_dir: Path, check_fn: Callable[[dict], bool]) -> bool:
    """检查 package.json 依赖.

    Args:
        target_dir: 项目根
        check_fn: 接收 dependencies 字典返回 bool 的回调
    """
    pkg = target_dir / "package.json"
    if not pkg.exists():
        return False
    try:
        data = json.loads(pkg.read_text())
        return check_fn(data.get("dependencies", {}))
    except (json.JSONDecodeError, OSError):
        return False


def signature_matches(target_dir: Path, sig: str) -> bool:
    """检查签名是否匹配 — 支持 glob 通配符."""
    if sig.endswith("/"):
        return (target_dir / sig).exists()
    if "*" in sig or "?" in sig or "[" in sig:
        import fnmatch

        rel_dir = sig.rsplit("/", 1)[0] if "/" in sig else ""
        pattern = sig.rsplit("/", 1)[-1]
        base = target_dir / rel_dir if rel_dir else target_dir
        if not base.exists():
            return False
        for entry in base.iterdir():
            if entry.is_file() and fnmatch.fnmatch(entry.name, pattern):
                return True
        return False
    return (target_dir / sig).exists()
