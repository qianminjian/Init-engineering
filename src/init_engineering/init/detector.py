"""ProjectDetector — 项目类型自动检测（签名 + 深度分析）。

来源：SST 框架扫描 → 依赖解析 → 框架识别 → 配置推断。

v2.5: 拆出 per-language analyzers → detector_analyzers.py,
helper detection functions → detector_helpers.py,
constants → detector_constants.py。
本模块仅保留 ProjectDetector class（编排 detector_analyzers + detector_helpers）。
"""

from __future__ import annotations

import logging
from pathlib import Path

from .._shared.detection import (
    detect_ci_platform as _detect_ci_platform,
)
from .._shared.detection import (
    detect_package_manager as _detect_package_manager,
)
from .._shared.detection import (
    detect_test_runner as _detect_test_runner,
)
from .detector_analyzers import (
    analyze_go,
    analyze_gradle,
    analyze_java,
    analyze_node,
    analyze_python,
)
from .detector_constants import FRAMEWORK_SIGNATURES, DetectionResult
from .detector_helpers import (
    check_pkg_dep,
    find_signatures_in_tree,
)
from .detector_helpers import (
    signature_matches as _signature_matches,
)

_logger = logging.getLogger(__name__)


class ProjectDetector:
    """扫描目标目录，推断项目类型与配置。"""

    def __init__(self, dst_path: Path, *, include_hidden: bool = False):
        self.dst_path = dst_path
        self.include_hidden = include_hidden

    def _detect(self) -> str | None:
        """返回唯一匹配的项目类型，0 或多于 1 个匹配返回 None。"""
        candidates = self.list_candidates()
        if len(candidates) == 1:
            return candidates[0]
        return None

    def list_candidates(self, *, recursive: bool = False) -> list[str]:
        """返回所有匹配的项目类型列表。

        recursive=True: 根目录无匹配时浅递归子目录 (max_depth=2),
        用于存量项目分析 — 父目录聚合多子项目的工作区。
        """
        matches = []
        for ptype, signatures in FRAMEWORK_SIGNATURES:
            if any(_signature_matches(self.dst_path, sig, max_depth=2 if recursive else 0, include_hidden=self.include_hidden)
                   for sig in signatures):
                # mcp-server 与 app-service 共享 package.json 签名，需额外消歧义
                if ptype == "mcp-server" and not check_pkg_dep(
                    self.dst_path,
                    lambda deps: "@modelcontextprotocol/sdk" in str(deps),
                ):
                    continue
                matches.append(ptype)
        return matches

    def analyze(self) -> DetectionResult:
        """深度分析目标目录，返回完整检测结果."""
        # First pass: root-level scan
        candidates = self.list_candidates()
        # Second pass: recursive scan if root found nothing (workspace aggregation dirs)
        if not candidates:
            candidates = self.list_candidates(recursive=True)

        result = DetectionResult(
            candidates=candidates,
            project_type=self._detect(),
        )
        result.project_name = self.dst_path.resolve().name

        pkg_json = self.dst_path / "package.json"
        pyproject = self.dst_path / "pyproject.toml"
        go_mod = self.dst_path / "go.mod"
        cargo_toml = self.dst_path / "Cargo.toml"
        pom_xml = self.dst_path / "pom.xml"
        build_gradle = self.dst_path / "build.gradle"
        build_gradle_kts = self.dst_path / "build.gradle.kts"

        if pkg_json.exists():
            result = analyze_node(pkg_json, self.dst_path, result)
        if pyproject.exists():
            result = analyze_python(pyproject, result)
        if go_mod.exists():
            result = analyze_go(go_mod, result)
        if cargo_toml.exists():
            result.language = "rust"
        if pom_xml.exists():
            result = analyze_java(pom_xml, result)
        elif build_gradle_kts.exists():
            result = analyze_gradle(build_gradle_kts, result)
        elif build_gradle.exists():
            result = analyze_gradle(build_gradle, result)
        elif not result.language:
            # Root has no build files — try recursive scan for Java projects
            # (common in workspace aggregator dirs: parent dir → subdirs with pom.xml)
            java_sigs = find_signatures_in_tree(
                self.dst_path, ["pom.xml", "build.gradle", "build.gradle.kts"], max_depth=1,
                include_hidden=self.include_hidden,
            )
            if java_sigs:
                for sig, dirs in java_sigs.items():
                    pom_dirs = sorted(dirs, key=lambda d: d.name)
                    # Prefer parent POM (multi-module, packaging=pom) over leaf POMs
                    best_dir = pom_dirs[0]
                    for d in pom_dirs:
                        pom = d / sig
                        try:
                            import xml.etree.ElementTree as ET

                            from .detector_helpers import strip_xml_ns

                            tree = ET.parse(pom)
                            root = tree.getroot()

                            has_modules = any(strip_xml_ns(c.tag) == "modules" for c in root)
                            if has_modules:
                                best_dir = d
                                break
                        except (ET.ParseError, OSError):
                            _logger.debug(
                                "无法解析 %s, 跳过", pom, exc_info=True,
                            )
                    if sig == "pom.xml":
                        result = analyze_java(best_dir / "pom.xml", result)
                    else:
                        result = analyze_gradle(best_dir / sig, result)
                    if result.language == "java":
                        break

        result.package_manager = _detect_package_manager(self.dst_path)
        result.test_runner = _detect_test_runner(self.dst_path, result.language)
        result.ci_platform = _detect_ci_platform(self.dst_path)
        result.has_lefthook = (self.dst_path / "lefthook.yml").exists()
        result.has_docker = (self.dst_path / "Dockerfile").exists()

        return result
