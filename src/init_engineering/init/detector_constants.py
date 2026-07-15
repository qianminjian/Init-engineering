"""Detector constants — DetectionResult + framework + package manager 映射。

拆自 detector.py (v2.5)：为打破 detector ↔ detector_analyzers 循环依赖。

所有跨模块共享的常量都集中到本文件（pure data，无导入）。
"""

from __future__ import annotations

__all__ = ["FRAMEWORK_SIGNATURES", "DetectionResult"]

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
    _java_info: dict | None = None
    _python_info: dict | None = None
    _go_info: dict | None = None
    _node_info: dict | None = None
    _qoder_info: dict | None = None

    def as_answers(self) -> dict[str, object]:
        """转为 AnswersMap 兼容的键值对，跳过 None/空值。

        v5.4: 全量暴露 — DetectionResult 公共字段 + _*_info 展平，30+ 变量进入模板上下文。
        """
        result: dict[str, object] = {}
        # ── 公共字段 ──
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
        if self.project_description:
            result["project_description"] = self.project_description
        if self.frameworks:
            result["frameworks"] = self.frameworks
        if self.has_lefthook:
            result["use_lefthook"] = True
        if self.has_docker:
            result["use_docker"] = True
        # ── _java_info 展平 ──
        if self._java_info:
            _java_export_keys = (
                "java_version", "spring_boot_version",
                "kotlin_version", "scala_version", "groovy_version",
            )
            for k in _java_export_keys:
                v = self._java_info.get(k)
                if v:
                    result[f"detected_{k}"] = v
            if self._java_info.get("packaging"):
                result["java_packaging"] = self._java_info["packaging"]
            if self._java_info.get("is_multi_module"):
                result["is_multi_module"] = True
            if self._java_info.get("group_id"):
                result["java_group_id"] = self._java_info["group_id"]
            if self._java_info.get("artifact_id"):
                result["java_artifact_id"] = self._java_info["artifact_id"]
            if self._java_info.get("build_tool"):
                result["java_build_tool"] = self._java_info["build_tool"]
            if self._java_info.get("version"):
                result["java_version_num"] = self._java_info["version"]
            deps = self._java_info.get("dependencies")
            if deps:
                result["java_dependencies"] = ", ".join(deps)
            mods = self._java_info.get("modules")
            if mods:
                result["java_modules"] = ", ".join(mods)
        # ── _python_info 展平 ──
        if self._python_info:
            if self._python_info.get("build_backend"):
                result["python_build_backend"] = self._python_info["build_backend"]
            py_deps = self._python_info.get("dependencies")
            if py_deps:
                result["python_dependencies"] = py_deps
        # ── _go_info 展平 ──
        if self._go_info:
            if self._go_info.get("module_path"):
                result["go_module_path"] = self._go_info["module_path"]
        # ── _node_info 展平 ──
        if self._node_info:
            if self._node_info.get("package_name"):
                result["node_package_name"] = self._node_info["package_name"]
            if self._node_info.get("package_version"):
                result["node_package_version"] = self._node_info["package_version"]
        # ── _qoder_info 展平 ──
        if self._qoder_info:
            if self._qoder_info.get("project_title"):
                result["qoder_project_title"] = self._qoder_info["project_title"]
            if self._qoder_info.get("project_description"):
                result["qoder_project_description"] = self._qoder_info["project_description"]
            if self._qoder_info.get("module_count"):
                result["qoder_module_count"] = self._qoder_info["module_count"]
            mods = self._qoder_info.get("modules")
            if mods:
                result["qoder_modules"] = [
                    {"key": m["key"], "title": m["title"]}
                    for m in mods if m.get("key")
                ]
        return result


# ─── 框架识别 ────────────────────────────────────────────────────────

NODE_FRAMEWORKS: list[tuple[str, str]] = [
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

PYTHON_FRAMEWORKS: list[tuple[str, str]] = [
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

GO_FRAMEWORKS: list[tuple[str, str]] = [
    ("gin", "Gin"),
    ("echo", "Echo"),
    ("chi", "Chi"),
    ("fiber", "Fiber"),
    ("iris", "Iris"),
    ("beego", "Beego"),
]

JAVA_FRAMEWORKS: list[tuple[str, str]] = [
    ("spring-boot-starter", "Spring Boot"),
    ("spring-cloud-starter", "Spring Cloud"),
    ("quarkus", "Quarkus"),
    ("micronaut", "Micronaut"),
    ("jakarta", "Jakarta EE"),
    ("javalin", "Javalin"),
    ("helidon", "Helidon"),
    ("vertx", "Vert.x"),
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
    (
        "library",
        ["pyproject.toml", "setup.py", "Cargo.toml", "go.mod",
         "pom.xml", "build.gradle", "build.gradle.kts"],
    ),
    ("app-service", ["package.json", "pom.xml", "build.gradle", "build.gradle.kts"]),
]
