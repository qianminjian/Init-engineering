"""Cross-layer detection utilities — 可供 config/ 和 init/ 同时使用."""

from __future__ import annotations

import json
from pathlib import Path

_LOCK_FILE_MAP: dict[str, str] = {
    "package-lock.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "bun.lockb": "bun",
    "uv.lock": "uv",
    "poetry.lock": "poetry",
    "Pipfile.lock": "pipenv",
}

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
