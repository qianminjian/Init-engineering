"""ProjectDetector — 项目类型自动检测（签名 + 深度分析）。

来源：SST 框架扫描 → 依赖解析 → 框架识别 → 配置推断。

v2.5: 拆出 per-language analyzers → detector_analyzers.py,
helper detection functions → detector_helpers.py,
constants → detector_constants.py。
本模块仅保留 ProjectDetector class（编排 detector_analyzers + detector_helpers）。
"""

from __future__ import annotations

from pathlib import Path

from .._shared.detection import (
    detect_ci_platform as _detect_ci_platform,
    detect_package_manager as _detect_package_manager,
    detect_test_runner as _detect_test_runner,
)
from .detector_analyzers import analyze_go, analyze_node, analyze_python
from .detector_constants import FRAMEWORK_SIGNATURES, DetectionResult
from .detector_helpers import (
    check_pkg_dep,
    signature_matches as _signature_matches,
)

class ProjectDetector:
    """扫描目标目录，推断项目类型与配置。"""

    def __init__(self, target_dir: Path):
        self.target_dir = target_dir

    def detect(self) -> str | None:
        """返回唯一匹配的项目类型，0 或多于 1 个匹配返回 None。"""
        candidates = self.list_candidates()
        if len(candidates) == 1:
            return candidates[0]
        return None

    def list_candidates(self) -> list[str]:
        """返回所有匹配的项目类型列表。"""
        matches = []
        for ptype, signatures in FRAMEWORK_SIGNATURES:
            if any(_signature_matches(self.target_dir, sig) for sig in signatures):
                # mcp-server 与 app-service 共享 package.json 签名，需额外消歧义
                if ptype == "mcp-server" and not check_pkg_dep(
                    self.target_dir,
                    lambda deps: "@modelcontextprotocol/sdk" in str(deps),
                ):
                    continue
                matches.append(ptype)
        return matches

    def analyze(self) -> DetectionResult:
        """深度分析目标目录，返回完整检测结果."""
        result = DetectionResult(
            candidates=self.list_candidates(),
            project_type=self.detect(),
        )
        result.project_name = self.target_dir.resolve().name

        pkg_json = self.target_dir / "package.json"
        pyproject = self.target_dir / "pyproject.toml"
        go_mod = self.target_dir / "go.mod"
        cargo_toml = self.target_dir / "Cargo.toml"

        if pkg_json.exists():
            analyze_node(pkg_json, self.target_dir, result)
        if pyproject.exists():
            analyze_python(pyproject, result)
        if go_mod.exists():
            analyze_go(go_mod, result)
        if cargo_toml.exists():
            result.language = "rust"

        result.package_manager = _detect_package_manager(self.target_dir)
        result.test_runner = _detect_test_runner(self.target_dir, result.language)
        result.ci_platform = _detect_ci_platform(self.target_dir)
        result.has_lefthook = (self.target_dir / "lefthook.yml").exists()
        result.has_docker = (self.target_dir / "Dockerfile").exists()

        return result
