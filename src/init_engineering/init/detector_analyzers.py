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
    GO_FRAMEWORKS,
    JAVA_FRAMEWORKS,
    NODE_FRAMEWORKS,
    PYTHON_FRAMEWORKS,
    DetectionResult,
)


def analyze_node(pkg_path: Path, project_dir: Path, result: DetectionResult) -> DetectionResult:
    """分析 Node.js 项目 — package.json + tsconfig。

    ⚠ 原地修改 result 并返回，调用方应使用返回值。
    """
    result.language = "typescript"
    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _logger.debug("无法解析 package.json: %s", pkg_path, exc_info=True)
        return result

    result.project_description = data.get("description", "")

    all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    for name, framework in NODE_FRAMEWORKS:
        if (
            name in all_deps or any(k.startswith(name + "/") for k in all_deps)
        ) and framework not in result.frameworks:
            result.frameworks.append(framework)

    tsconfig = project_dir / "tsconfig.json"
    deps_str = str(all_deps)
    if not tsconfig.exists() and "typescript" not in deps_str:
        result.language = "javascript"

    if "pnpm" in str(data.get("scripts", {})):
        result.package_manager = "pnpm"

    result._node_info = {
        "package_name": data.get("name", ""),
        "package_version": data.get("version", ""),
    }

    return result



def analyze_python(py_path: Path, result: DetectionResult) -> DetectionResult:
    """分析 Python 项目 — pyproject.toml (PEP 621)。

    ⚠ 副作用: 原地修改 result
    (result.language, result.project_description, result.frameworks, result.package_manager)。
    """
    result.language = "python"
    try:
        data = tomllib.loads(py_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        _logger.debug("无法解析 pyproject.toml: %s", py_path, exc_info=True)
        return result

    project = data.get("project", {})
    result.project_description = project.get("description", "")

    deps_list: list[str] = list(project.get("dependencies", []))
    optional = project.get("optional-dependencies", {})
    if isinstance(optional, dict):
        for extra_deps in optional.values():
            if isinstance(extra_deps, list):
                deps_list.extend(extra_deps)
    deps_str = " ".join(deps_list)
    for name, framework in PYTHON_FRAMEWORKS:
        if name in deps_str:
            result.frameworks.append(framework)

    build_backend = "unknown"
    if "build-system" in data:
        build_backend = str(data["build-system"].get("build-backend", ""))
    if "poetry" in build_backend:
        result.package_manager = "poetry"
    elif "uv" in build_backend or "uv" in str(data.get("tool", {})):
        result.package_manager = "uv"

    result._python_info = {
        "build_backend": build_backend,
        "dependencies": deps_list,
    }

    return result



def analyze_go(go_path: Path, result: DetectionResult) -> DetectionResult:
    """分析 Go 项目 — go.mod。

    ⚠ 副作用: 原地修改 result (result.language, result.project_name, result.frameworks)。
    """
    result.language = "go"
    try:
        content = go_path.read_text(encoding="utf-8")
    except OSError:
        _logger.debug("无法读取 go.mod: %s", go_path, exc_info=True)
        return result

    module_path = ""
    m = re.search(r"^module\s+(.+)$", content, re.MULTILINE)
    if m:
        module_path = m.group(1).strip()
        result.project_name = module_path.rsplit("/", 1)[-1]

    for name, framework in GO_FRAMEWORKS:
        if re.search(rf"github\.com/.*/{name}\b", content):
            result.frameworks.append(framework)

    result._go_info = {
        "module_path": module_path,
    }

    return result



def analyze_java(pom_path: Path, result: DetectionResult, project_root: Path | None = None) -> DetectionResult:
    """分析 Java/Maven 项目 — pom.xml (Maven) 或 build.gradle (Gradle).

    ⚠ 副作用: 原地修改 result (result.language, result.package_manager, result.test_runner,
    result.project_name, result.frameworks, result.candidates, result._java_info 等)。

    Extracts: Java version, groupId/artifactId, Spring Boot version,
    detected frameworks, packaging type, multi-module detection.

    project_root: 项目根目录（dst_path）。非 None 时计算 pom_path 相对路径，
    用于拼接模块路径前缀。例如 tmp/pom.xml 的 <module>tmp-boot</module>
    → 模块路径为 tmp/tmp-boot。
    """
    result.language = "java"
    result.package_manager = "mvn"
    result.test_runner = result.test_runner or "mvn test"

    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()
    except (ET.ParseError, OSError):
        _logger.debug("无法解析 pom.xml: %s", pom_path, exc_info=True)
        return result

    from .detector_helpers import strip_xml_ns as tag

    # Extract Maven coordinates — strip namespace from tag for easier matching
    group_id = None
    artifact_id = None
    version = None
    java_version = None
    spring_boot_version = None
    packaging = "jar"
    has_spring_boot_starter = False
    is_multi_module = False
    dependencies: list[str] = []
    modules: list[str] = []

    for child in root:
        t = tag(child.tag)
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
                if tag(mod.tag) == "module" and mod.text:
                    mod_name = mod.text.strip()
                    modules.append(mod_name)
                    dependencies.append(f"module:{mod_name}")
        elif t == "properties":
            for prop in child:
                ptag = tag(prop.tag)
                ptext = (prop.text or "").strip()
                if ptag.endswith("java.version") or ptag == "maven.compiler.source":
                    java_version = ptext
                elif ptag.endswith("spring-boot.version") or ptag == "spring-boot.version":
                    spring_boot_version = ptext
        elif t == "dependencyManagement" or t == "dependencies":
            for dep_elem in child:
                if tag(dep_elem.tag) == "dependency":
                    gid = aid = vid = ""
                    for dep_child in dep_elem:
                        dt = tag(dep_child.tag)
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
    for name, framework in JAVA_FRAMEWORKS:
        if name in deps_str:
            result.frameworks.append(framework)

    # Detect Spring Boot version from parent
    if not spring_boot_version:
        for child in root:
            if tag(child.tag) == "parent":
                for pc in child:
                    pct = tag(pc.tag)
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

    # v5.6: 计算 POM 相对项目根目录的路径（用于模块路径前缀）
    aggregator_path = ""
    if project_root is not None:
        try:
            aggregator_path = str(pom_path.parent.resolve().relative_to(project_root.resolve()))
            if aggregator_path == ".":
                aggregator_path = ""
        except ValueError:
            aggregator_path = ""

    # v5.6: 校验 pom.xml 声明的模块是否在磁盘上存在（在路径拼接前，用原始模块名）
    project_dir = pom_path.parent
    missing_modules: list[str] = []
    extra_dirs: list[str] = []
    if is_multi_module and modules:
        disk_dirs = {d.name for d in project_dir.iterdir() if d.is_dir() and not d.name.startswith(".")}
        declared = set(modules)
        missing_modules = sorted(declared - disk_dirs)
        # 磁盘上存在的目录但未在 pom.xml 声明（排除已知非模块目录）
        _known_non_module = {"src", "target", "design", "docs", "_scratch", ".github", ".mvn"}
        potential_extra = sorted(disk_dirs - declared - _known_non_module)
        # 只标记包含 src/ 或 pom.xml 的目录为可能遗漏的模块
        extra_dirs = [d for d in potential_extra
                      if (project_dir / d / "pom.xml").exists()
                      or (project_dir / d / "src").exists()]
    if missing_modules:
        _logger.warning(
            "pom.xml 声明了 %d 个模块在磁盘上不存在: %s",
            len(missing_modules), ", ".join(missing_modules),
        )

    # 模块路径拼接父 POM 相对路径（Issue #5 修复）
    # tmp/pom.xml 的 <module>tmp-boot</module> → 模块路径为 tmp/tmp-boot
    if aggregator_path:
        prefix = aggregator_path + "/"
        modules = [prefix + m for m in modules]
        dependencies = [
            f"{prefix}{dep.removeprefix('module:')}" if dep.startswith("module:") else dep
            for dep in dependencies
        ]

    # P1-2: 校验 spring_boot_version 是否为官方版本格式 (x.y.z)
    # 非标准版本（如 "JIANGSU.SR1" 来自非官方 parent POM）会被舍弃
    if spring_boot_version and not re.match(r'^\d+\.\d+\.\d+$', spring_boot_version):
        _logger.debug("Non-standard Spring Boot version ignored: %s", spring_boot_version)
        spring_boot_version = None

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
        "dependencies": dependencies,
        "modules": modules,
        "module_missing": missing_modules,
        "module_extra_dirs": extra_dirs,
        "aggregator_path": aggregator_path,
    })

    return result



def analyze_gradle(gradle_path: Path, result: DetectionResult) -> DetectionResult:
    """分析 Java/Gradle 项目 — build.gradle / build.gradle.kts (basic detection).

    原地修改 result 并返回，调用方应使用返回值。
    """
    result.language = "java"
    result.package_manager = "gradle"
    result.test_runner = result.test_runner or "gradle test"
    try:
        content = gradle_path.read_text(encoding="utf-8")
    except OSError:
        _logger.debug("无法读取 %s", gradle_path, exc_info=True)
        return result

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
