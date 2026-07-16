"""ProjectDetector — 项目类型自动检测（签名 + 深度分析）。

来源：SST 框架扫描 → 依赖解析 → 框架识别 → 配置推断。

v2.5: 拆出 per-language analyzers → detector_analyzers.py,
helper detection functions → detector_helpers.py,
constants → detector_constants.py。
本模块仅保留 ProjectDetector class（编排 detector_analyzers + detector_helpers）。
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
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
    strip_xml_ns,
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
            result = analyze_java(pom_xml, result, project_root=self.dst_path)
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
                            tree = ET.parse(pom)
                            root_el = tree.getroot()

                            has_modules = any(strip_xml_ns(c.tag) == "modules" for c in root_el)
                            if has_modules:
                                best_dir = d
                                break
                        except (ET.ParseError, OSError):
                            _logger.debug(
                                "无法解析 %s, 跳过", pom, exc_info=True,
                            )
                    if sig == "pom.xml":
                        result = analyze_java(best_dir / "pom.xml", result, project_root=self.dst_path)
                    else:
                        result = analyze_gradle(best_dir / sig, result)
                    if result.language == "java":
                        break

        # v5.6: 扫描同级目录中引用聚合 POM 为 <parent> 的独立模块（Issue #6 修复）
        # tmp/pom.xml 聚合了 8 个子模块，但 tmp-manage/pom.xml 和 tmp-window/pom.xml
        # 以 tmp 为 <parent> 且不在 <modules> 中 — 需要单独扫描并追加到模块列表
        if result.language == "java" and result._java_info and result._java_info.get("modules"):
            java_info = result._java_info
            existing_modules = set(java_info["modules"])
            aggregator_artifact_id = java_info.get("artifact_id", "")
            aggregator_path = java_info.get("aggregator_path", "")
            if aggregator_artifact_id:
                try:
                    for entry in self.dst_path.iterdir():
                        if not entry.is_dir() or entry.name.startswith("."):
                            continue
                        sibling_pom = entry / "pom.xml"
                        if not sibling_pom.exists():
                            continue
                        try:
                            stree = ET.parse(sibling_pom)
                            sroot = stree.getroot()
                            s_parent_artifact_id = None
                            for schild in sroot:
                                if strip_xml_ns(schild.tag) == "parent":
                                    for spc in schild:
                                        if strip_xml_ns(spc.tag) == "artifactId":
                                            s_parent_artifact_id = (spc.text or "").strip()
                                            break
                                    break
                            if s_parent_artifact_id == aggregator_artifact_id:
                                # 追加为独立模块路径
                                rel_path = str(entry.relative_to(self.dst_path))
                                if rel_path not in existing_modules:
                                    java_info["modules"].append(rel_path)
                                    _logger.info(
                                        "发现独立模块（不在聚合 POM <modules> 中）: %s",
                                        rel_path,
                                    )
                        except (ET.ParseError, OSError):
                            _logger.debug("跳过无法解析的 POM: %s", sibling_pom, exc_info=True)
                except PermissionError:
                    _logger.debug("无法扫描项目目录", exc_info=True)

        # 包管理器：优先使用语言分析器已设置的值（如 analyze_java 设置的 "mvn"），
        # 只在未设置时才用根目录 lock 文件推断。防止聚合目录场景被覆盖为 None。
        if not result.package_manager:
            result.package_manager = _detect_package_manager(self.dst_path)
        result.test_runner = _detect_test_runner(self.dst_path, result.language)
        result.ci_platform = _detect_ci_platform(self.dst_path)
        result.has_lefthook = (self.dst_path / "lefthook.yml").exists()
        result.has_docker = (self.dst_path / "Dockerfile").exists()

        # v5.3: Java 项目优先用 artifact_id 作为 project_name，
        # 但聚合目录（根目录无构建文件）需恢复为根目录名 —
        # analyze_java() 内部已将 project_name 设为子目录的 artifact_id
        _root_has_build = any([
            pkg_json.exists(), pyproject.exists(), go_mod.exists(),
            cargo_toml.exists(), pom_xml.exists(), build_gradle.exists(),
            build_gradle_kts.exists(),
        ])
        if not _root_has_build:
            result.project_name = self.dst_path.resolve().name

        # v5.6 Phase G: 深度分析发现具体构建系统时，覆盖签名级类型（如 spec-doc）。
        # design/*.md 签名过于宽泛，会使任何含有设计文档的项目被误判为 spec-doc，
        # 导致 monorepo/Java 初始化路径被完全跳过。
        # 规则: 语言分析器确认了编程语言 + monorepo 候选 → 一定是 monorepo。
        if "monorepo" in result.candidates and result.language is not None:
            result.project_type = "monorepo"
        elif result.project_type is None and "monorepo" in result.candidates:
            result.project_type = "monorepo"

        # ── 隐藏目录元数据提取 ──
        if self.include_hidden:
            from .detector_qoder import analyze_qoder_repowiki

            qoder_info = analyze_qoder_repowiki(self.dst_path)
            if qoder_info is not None:
                result._qoder_info = qoder_info
                # qoder 描述优先于 pom.xml 的 groupId:artifactId
                if qoder_info.get("project_description"):
                    result.project_description = qoder_info["project_description"]

        return result
