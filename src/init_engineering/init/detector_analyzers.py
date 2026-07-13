"""Per-language analyzers — 拆自 detector.py (v2.5: 382→可控)。

设计：
- 依赖解析逻辑（node/python/go）各自独立
- 框架列表来自 detector_constants（避免 detector ↔ detector_analyzers 循环依赖）
- 每个 analyzer 接受 lang-specific 文件路径 + DetectionResult，原地修改 result
"""

from __future__ import annotations

import json
import logging
import re
import tomllib  # Python ≥3.11 stdlib (project requires-python >=3.11,<3.14)
import xml.etree.ElementTree as ET
from pathlib import Path

_logger = logging.getLogger(__name__)

from .detector_constants import (  # noqa: E402
    _GO_FRAMEWORKS,
    _JAVA_FRAMEWORKS,
    _NODE_FRAMEWORKS,
    _PYTHON_FRAMEWORKS,
    DetectionResult,
)


def analyze_node(pkg_path: Path, dst_path: Path, result: DetectionResult) -> None:
    """分析 Node.js 项目 — package.json + tsconfig。Modifies result in place."""
    result.language = "typescript"
    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _logger.debug("无法解析 package.json: %s", pkg_path, exc_info=True)
        return

    result.project_description = data.get("description", "")

    all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    for name, framework in _NODE_FRAMEWORKS:
        if (
            name in all_deps or any(k.startswith(name + "/") for k in all_deps)
        ) and framework not in result.frameworks:
            result.frameworks.append(framework)

    tsconfig = dst_path / "tsconfig.json"
    deps_str = str(all_deps)
    if not tsconfig.exists() and "typescript" not in deps_str:
        result.language = "javascript"

    if "pnpm" in str(data.get("scripts", {})):
        result.package_manager = "pnpm"



def analyze_python(py_path: Path, result: DetectionResult) -> None:
    """分析 Python 项目 — pyproject.toml (PEP 621)。Modifies result in place."""
    result.language = "python"
    try:
        data = tomllib.loads(py_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, tomllib.TOMLDecodeError):
        _logger.debug("无法解析 pyproject.toml: %s", py_path, exc_info=True)
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
    """分析 Go 项目 — go.mod。Modifies result in place."""
    result.language = "go"
    try:
        content = go_path.read_text(encoding="utf-8")
    except OSError:
        _logger.debug("无法读取 go.mod: %s", go_path, exc_info=True)
        return

    m = re.search(r"^module\s+(.+)$", content, re.MULTILINE)
    if m:
        mod_path = m.group(1).strip()
        result.project_name = mod_path.rsplit("/", 1)[-1]

    for name, framework in _GO_FRAMEWORKS:
        if re.search(rf"github\.com/.*/{name}\b", content):
            result.frameworks.append(framework)



def analyze_java(pom_path: Path, result: DetectionResult) -> None:
    """分析 Java/Maven 项目 — pom.xml (Maven) 或 build.gradle (Gradle).

    Extracts: Java version, groupId/artifactId, Spring Boot version,
    detected frameworks, packaging type, multi-module detection.
    """
    result.language = "java"

    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()
    except (ET.ParseError, OSError):
        _logger.debug("无法解析 pom.xml: %s", pom_path, exc_info=True)
        return

    # Extract Maven coordinates
    # Strip namespace from tag for easier matching
    def tag(el):
        return el.tag.rsplit("}", 1)[-1] if "}" in el.tag else el.tag

    group_id = None
    artifact_id = None
    version = None
    java_version = None
    spring_boot_version = None
    packaging = "jar"
    has_spring_boot_starter = False
    is_multi_module = False
    dependencies: list[str] = []

    for child in root:
        t = tag(child)
        text = (child.text or "").strip()
        if t == "groupId":
            group_id = text
        elif t == "artifactId":
            artifact_id = text
        elif t == "version":
            version = text
        elif t == "packaging":
            packaging = text
        elif t == "modules":
            is_multi_module = True
            for mod in child:
                if tag(mod) == "module" and mod.text:
                    dependencies.append(f"module:{mod.text.strip()}")
        elif t == "properties":
            for prop in child:
                ptag = tag(prop)
                ptext = (prop.text or "").strip()
                if ptag.endswith("java.version") or ptag == "maven.compiler.source":
                    java_version = ptext
                elif ptag.endswith("spring-boot.version") or ptag == "spring-boot.version":
                    spring_boot_version = ptext
        elif t == "dependencyManagement" or t == "dependencies":
            for dep_elem in child:
                if tag(dep_elem) == "dependency":
                    gid = aid = vid = ""
                    for dep_child in dep_elem:
                        dt = tag(dep_child)
                        dtext = (dep_child.text or "").strip()
                        if dt == "groupId":
                            gid = dtext
                        elif dt == "artifactId":
                            aid = dtext
                        elif dt == "version":
                            vid = dtext
                    if aid:
                        dependencies.append(f"{gid}:{aid}" + (f":{vid}" if vid else ""))
                        if "spring-boot-starter" in aid:
                            has_spring_boot_starter = True
                            if not spring_boot_version and vid:
                                spring_boot_version = vid

    # Set project name from artifactId or directory
    if artifact_id:
        result.project_name = artifact_id
    elif not result.project_name or result.project_name == pom_path.parent.name:
        result.project_name = pom_path.parent.resolve().name

    # Detect frameworks from dependencies
    deps_str = " ".join(dependencies)
    for name, framework in _JAVA_FRAMEWORKS:
        if name in deps_str:
            result.frameworks.append(framework)

    # Detect Spring Boot version from parent
    if not spring_boot_version:
        for child in root:
            if tag(child) == "parent":
                for pc in child:
                    pct = tag(pc)
                    pctext = (pc.text or "").strip()
                    if pct == "artifactId" and "spring-boot-starter-parent" in pctext:
                        has_spring_boot_starter = True
                    elif pct == "version" and has_spring_boot_starter:
                        spring_boot_version = pctext

    # Multi-module detection: Maven projects with <packaging>pom</packaging> are monorepos
    if (
        is_multi_module
        and packaging == "pom"
        and dependencies
        and "monorepo" not in result.candidates
        and result.project_type != "monorepo"
    ):
        result.candidates.append("monorepo")

    # Store rich metadata
    result.project_description = (
        f"{group_id}:{artifact_id}" if group_id and artifact_id
        else result.project_description
    )

    # Store extra detection info for downstream use
    if result._java_info is None:
        result._java_info = {}
    result._java_info.update({
        "group_id": group_id,
        "artifact_id": artifact_id,
        "version": version or "",
        "java_version": java_version or "",
        "spring_boot_version": spring_boot_version or "",
        "packaging": packaging,
        "is_multi_module": is_multi_module,
        "build_tool": "maven",
    })



def analyze_gradle(gradle_path: Path, result: DetectionResult) -> None:
    """分析 Java/Gradle 项目 — build.gradle / build.gradle.kts (basic detection)."""
    result.language = "java"
    try:
        content = gradle_path.read_text(encoding="utf-8")
    except OSError:
        _logger.debug("无法读取 %s", gradle_path, exc_info=True)
        return

    # Detect Spring Boot via plugin
    if "spring-boot" in content or "org.springframework.boot" in content:
        result.frameworks.append("Spring Boot")

    # Detect other frameworks
    if "quarkus" in content.lower():
        result.frameworks.append("Quarkus")
    if "micronaut" in content.lower():
        result.frameworks.append("Micronaut")

    if result._java_info is None:
        result._java_info = {}
    result._java_info.update({
        "build_tool": "gradle",
    })

    if not result.project_name:
        result.project_name = gradle_path.parent.resolve().name

    return result
