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
from .detector_constants import FRAMEWORK_SIGNATURES, TYPE_HINT_KEYWORDS, DetectionResult
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

        # ── v5.6 Phase H: 内容感知类型推断 ──
        # 增量模式或有设计文档的项目：从文档内容推断项目意图，作为补充信号。
        # 增量模式时即使已有语言信号也运行（设计文档可能提供更准确的项目类型）。
        content_type = _infer_type_from_design_docs(self.dst_path)
        if content_type:
            _logger.info("从 Markdown 文档推断项目类型 → %s (关键词匹配)", content_type)
            if result.language is None and result.project_type in (None, "spec-doc"):
                # 无代码信号时，内容推断作为主要判定依据
                result.project_type = content_type
                if content_type not in result.candidates:
                    result.candidates.append(content_type)
            elif content_type not in result.candidates:
                # 有代码信号时，内容推断作为补充参考
                result.candidates.append(content_type)

        # ── 增量模式基线校准：读取已有 BEACON.md 和 .ae-answers.yml ──
        _baseline_type = _read_design_baseline(self.dst_path)
        if _baseline_type:
            _logger.info("从设计基线读取项目类型 → %s", _baseline_type)
            if _baseline_type not in result.candidates:
                result.candidates.append(_baseline_type)
            # 基线类型优先于检测结果（用户/设计已声明过的类型）
            if result.project_type is None or result.project_type != _baseline_type:
                result.project_type = _baseline_type
                result.confidence = "high"  # 设计基线明确声明 → 高置信度

        # ── 置信度判定 ──
        # high: 设计基线声明 OR（签名匹配 + 语言分析器确认了语言）
        # low: 纯签名匹配未确认语言 / 纯内容推断 / 没有任何信号
        if result.confidence != "high":
            if result.project_type and result.language:
                result.confidence = "high"
            else:
                result.confidence = "low"

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


def _infer_type_from_design_docs(dst_path: Path) -> str | None:
    """v5.6 Phase H: 从 *.md 内容推断项目意图类型。

    扫描根目录和 design/ 下 markdown 文件的头 3000 字符，统计
    TYPE_HINT_KEYWORDS 各类型的关键词命中数。最高分 ≥ 阈值（2）时返回对应类型。

    Returns:
        推断的项目类型，或 None（内容不足以推断）。
    """
    from .detector_constants import TYPE_HINT_KEYWORDS, _TYPE_HINT_MIN_MATCHES

    # 收集 markdown 内容（每个文件头 3000 字符，控制 I/O）
    parts: list[str] = []
    # 根目录 *.md
    try:
        for md in dst_path.glob("*.md"):
            try:
                text = md.read_text(encoding="utf-8")
                parts.append(text[:3000])
            except (OSError, UnicodeDecodeError):
                continue
    except OSError:
        pass
    # design/ 目录 *.md
    design_dir = dst_path / "design"
    if design_dir.is_dir():
        try:
            for md in design_dir.glob("*.md"):
                try:
                    text = md.read_text(encoding="utf-8")
                    parts.append(text[:3000])
                except (OSError, UnicodeDecodeError):
                    continue
        except OSError:
            pass
    # styles/ 目录 — 风格文件也承载项目意图信息
    styles_dir = dst_path / "styles"
    if styles_dir.is_dir():
        try:
            for f in styles_dir.iterdir():
                if f.is_file() and f.suffix in (".md", ".txt", ".css", ".yaml", ".yml"):
                    try:
                        text = f.read_text(encoding="utf-8")
                        parts.append(text[:2000])
                    except (OSError, UnicodeDecodeError):
                        continue
        except OSError:
            pass

    if not parts:
        return None

    combined = " ".join(parts).lower()

    # 计分：每个关键词命中 +1
    scores: dict[str, int] = {}
    for ptype, keywords in TYPE_HINT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in combined)
        if score >= _TYPE_HINT_MIN_MATCHES:
            scores[ptype] = score

    if not scores:
        return None

    return max(scores, key=scores.get)


def _read_design_baseline(dst_path: Path) -> str | None:
    """从已有设计基线（BEACON.md / .ae-answers.yml）读取 project_type。

    增量模式下作为强信号：用户或设计文档已声明过的 project_type 优先于自动检测。

    Returns:
        project_type 字符串，或 None（基线不存在/无法解析）。
    """
    import yaml

    # 1. 尝试 .ae-answers.yml（结构明确，优先）
    answers_file = dst_path / ".ae-answers.yml"
    if answers_file.exists():
        try:
            data = yaml.safe_load(answers_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                pt = data.get("project_type") or data.get("_meta", {}).get("project_type")
                if pt and isinstance(pt, str) and pt.strip():
                    return pt.strip()
        except (OSError, yaml.YAMLError):
            pass

    # 2. 尝试 BEACON.md（从头部提取 project_type 或阶段信息）
    beacon = dst_path / "design" / "BEACON.md"
    if beacon.exists():
        try:
            text = beacon.read_text(encoding="utf-8")[:2000]
            import re
            # 匹配 "项目类型: xxx" 或 "project_type: xxx" 或 "类型: xxx"
            m = re.search(r'(?:项目类型|project.type|类型)[:：]\s*(\S+)', text)
            if m:
                return m.group(1)
        except OSError:
            pass

    return None
