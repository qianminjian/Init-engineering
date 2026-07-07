"""Detector constants — DetectionResult + framework + package manager 映射。

拆自 detector.py (v2.5)：为打破 detector ↔ detector_analyzers 循环依赖。

所有跨模块共享的常量都集中到本文件（pure data，无导入）。
"""

from __future__ import annotations

__all__ = ["DetectionResult", "FRAMEWORK_SIGNATURES"]

from dataclasses import dataclass, field


@dataclass
class DetectionResult:
    """深度分析结果 — 可用于填充 AnswersMap 默认值。"""

    project_type: str | None = None
    candidates: list[str] = field(default_factory=list)
    language: str | None = None
    package_manager: str | None = None
    test_runner: str | None = None
    ci_platform: str | None = None
    frameworks: list[str] = field(default_factory=list)
    has_lefthook: bool = False
    has_docker: bool = False
    project_name: str | None = None
    project_description: str = ""

    def as_answers(self) -> dict[str, object]:
        """转为 AnswersMap 兼容的键值对，跳过 None/空值。"""
        result: dict[str, object] = {}
        if self.project_type:
            result["project_type"] = self.project_type
        if self.language:
            result["language"] = self.language
        if self.package_manager:
            result["package_manager"] = self.package_manager
        if self.test_runner:
            result["test_runner"] = self.test_runner
        if self.ci_platform:
            result["ci_platform"] = self.ci_platform
        if self.project_name:
            result["project_name"] = self.project_name
        if self.has_lefthook:
            result["use_lefthook"] = True
        if self.has_docker:
            result["use_docker"] = True
        return result


# ─── 框架识别 ────────────────────────────────────────────────────────

_NODE_FRAMEWORKS: list[tuple[str, str]] = [
    ("next", "Next.js"),
    ("express", "Express"),
    ("fastify", "Fastify"),
    ("koa", "Koa"),
    ("nest", "NestJS"),
    ("react", "React"),
    ("vue", "Vue.js"),
    ("svelte", "Svelte"),
    ("angular", "Angular"),
    ("nuxt", "Nuxt.js"),
    ("remix", "Remix"),
    ("astro", "Astro"),
    ("hono", "Hono"),
]

_PYTHON_FRAMEWORKS: list[tuple[str, str]] = [
    ("fastapi", "FastAPI"),
    ("flask", "Flask"),
    ("django", "Django"),
    ("litestar", "Litestar"),
    ("sanic", "Sanic"),
    ("tornado", "Tornado"),
    ("aiohttp", "aiohttp"),
    ("bottle", "Bottle"),
    ("pyramid", "Pyramid"),
]

_GO_FRAMEWORKS: list[tuple[str, str]] = [
    ("gin", "Gin"),
    ("echo", "Echo"),
    ("chi", "Chi"),
    ("fiber", "Fiber"),
    ("iris", "Iris"),
    ("beego", "Beego"),
]


# ─── 签名检测 ────────────────────────────────────────────────────────

# 签名按 specificity 降序排列 — 同名签名文件（如 package.json 被 mcp-server 和
# app-service 共享）靠排在前面 + ADVANCED_CHECKS 消歧义。颠倒顺序会导致误判。
FRAMEWORK_SIGNATURES: list[tuple[str, list[str]]] = [
    ("plugin", [".claude-plugin/"]),
    ("monorepo", ["pnpm-workspace.yaml", "lerna.json", "turbo.json", "nx.json"]),
    ("skill", [".claude/skills/"]),
    ("hook", [".claude/hooks/"]),
    ("spec-doc", ["design/BEACON.md", "design/*.md"]),
    ("mcp-server", ["package.json"]),
    ("cli-tool", ["src/cli.py", "src/cli/__init__.py", "src/cli.ts", "cmd/"]),
    ("library", ["pyproject.toml", "setup.py", "Cargo.toml", "go.mod"]),
    ("app-service", ["package.json"]),
]
