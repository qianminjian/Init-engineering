"""Per-language analyzers — 拆自 detector.py (v2.5: 382→可控)。

设计：
- 依赖解析逻辑（node/python/go）各自独立
- 框架列表来自 detector_constants（避免 detector ↔ detector_analyzers 循环依赖）
- 每个 analyzer 接受 lang-specific 文件路径 + DetectionResult，原地修改 result
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from .detector_constants import (
    _GO_FRAMEWORKS,
    _NODE_FRAMEWORKS,
    _PYTHON_FRAMEWORKS,
    DetectionResult,
)


def analyze_node(pkg_path: Path, target_dir: Path, result: DetectionResult) -> None:
    """分析 Node.js 项目 — package.json + tsconfig。"""
    result.language = "typescript"
    try:
        data = json.loads(pkg_path.read_text())
    except (json.JSONDecodeError, OSError):
        return

    result.project_description = data.get("description", "")

    all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    for name, framework in _NODE_FRAMEWORKS:
        if name in all_deps or any(k.startswith(name + "/") for k in all_deps):
            if framework not in result.frameworks:
                result.frameworks.append(framework)

    tsconfig = target_dir / "tsconfig.json"
    deps_str = str(all_deps)
    if not tsconfig.exists() and "typescript" not in deps_str:
        result.language = "javascript"

    if "pnpm" in str(data.get("scripts", {})):
        result.package_manager = "pnpm"


def analyze_python(py_path: Path, result: DetectionResult) -> None:
    """分析 Python 项目 — pyproject.toml (PEP 621)。"""
    result.language = "python"
    try:
        data = tomllib.loads(py_path.read_text())
    except Exception:
        return

    project = data.get("project", {})
    result.project_description = project.get("description", "")

    deps_list: list[str] = list(project.get("dependencies", []))
    optional = project.get("optional-dependencies", {})
    if isinstance(optional, dict):
        for extra_deps in optional.values():
            if isinstance(extra_deps, list):
                deps_list.extend(extra_deps)
    deps_str = " ".join(deps_list)
    for name, framework in _PYTHON_FRAMEWORKS:
        if name in deps_str:
            result.frameworks.append(framework)

    build_backend = "unknown"
    if "build-system" in data:
        build_backend = str(data["build-system"].get("build-backend", ""))
    if "poetry" in build_backend:
        result.package_manager = "poetry"
    elif "uv" in build_backend or "uv" in str(data.get("tool", {})):
        result.package_manager = "uv"


def analyze_go(go_path: Path, result: DetectionResult) -> None:
    """分析 Go 项目 — go.mod。"""
    result.language = "go"
    try:
        content = go_path.read_text()
    except OSError:
        return

    m = re.search(r"^module\s+(.+)$", content, re.MULTILINE)
    if m:
        mod_path = m.group(1).strip()
        result.project_name = mod_path.rsplit("/", 1)[-1]

    for name, framework in _GO_FRAMEWORKS:
        if re.search(rf"github\.com/.*/{name}\b", content):
            result.frameworks.append(framework)
