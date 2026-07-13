"""Phase 2: prompt — 加载 TemplateConfig + 应用 CLI overrides + 交互问答.

来源: init/scaffold_phases.py → phases/prompt.py (2026-07-03 拆分).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .._shared.prompt_backend import PromptBackend
from ..answers import AnswersMap
from ..config_loader import load_template_config
from ..config_types import TEMPLATES_ROOT, TemplateConfig
from ..detector import DetectionResult
from ..errors import InitInterruptedError
from ..prompts import InteractivePrompt, prompt_for_nested_template
from ..scaffold_question_eval import evaluate_question_defaults

_logger = logging.getLogger(__name__)


def phase_prompt(
    project_type: str,
    defaults: bool,
    previous_answers: AnswersMap | None,
    *,
    language: str | None,
    package_manager: str | None,
    ci_platform: str | None,
    test_runner: str | None,
    use_typescript: bool | None,
    use_lefthook: bool | None,
    use_docker: bool | None,
    detection: DetectionResult | None,
    dst_path: Path | None = None,
    prompt_backend: PromptBackend | None = None,
) -> tuple[TemplateConfig, AnswersMap]:
    """加载 TemplateConfig + 应用 CLI overrides + 评估 question + 交互 prompt."""
    template = load_template_config(project_type or "")
    if template.nested_templates:
        # 选择 nested template 策略:
        # 1. 若 language 在 nested_templates 键中 → 直接选它（CLI 透传 language）
        # 2. defaults 模式自动选第一个
        # 3. 非 defaults 模式交互式询问用户
        preferred = language if language in template.nested_templates else None
        chosen = prompt_for_nested_template(
            template.nested_templates,
            no_input=defaults,
            preferred=preferred,
            backend=prompt_backend,
        )
        if chosen:
            template.template_dir = template.template_dir / chosen

    cli_overrides = {}
    for key, val in [
        ("language", language),
        ("package_manager", package_manager),
        ("ci_platform", ci_platform),
        ("test_runner", test_runner),
        ("use_typescript", use_typescript),
        ("use_lefthook", use_lefthook),
        ("use_docker", use_docker),
    ]:
        if val is not None:
            cli_overrides[key] = val

    answers = AnswersMap(
        defaults={q.var_name: q.default for q in template.questions},
        cli_overrides=cli_overrides,
        previous=previous_answers.previous if previous_answers else {},
        external=template.external_data,
        # A5 安全: external_data sandbox root 强制白名单 (TEMPLATES_ROOT + home)
        # 不再信任 template.template_dir (攻击者可控 via --template-dir)
        external_sandbox_roots=[TEMPLATES_ROOT, Path.home()],
    )
    answers.builtins["project_type"] = project_type or ""
    if detection is not None:
        for k, v in detection.as_answers().items():
            # 只将真正从项目文件检测到的字段放入 defaults（覆盖模板默认值）
            # project_name 始终为目录名，不是检测结果，不覆盖模板默认
            if k in ("language", "package_manager", "test_runner", "ci_platform",
                       "use_lefthook", "use_docker"):
                answers.defaults[k] = v

    # 检查 var 单个字符串,不是 list in AnswersMap (会触发 __contains__ 内部迭代 ChainMap)
    for var in ["project_description", "language", "package_manager",
                "test_runner", "ci_platform", "project_type"]:
        if var not in answers:  # __contains__ 处理单 key
            answers.builtins[var] = ""

    # --defaults 模式: project_name 使用目标目录名而非硬编码 "my-app"
    if defaults and dst_path is not None:
        dir_name = dst_path.resolve().name
        if dir_name and dir_name != ".":
            answers.defaults["project_name"] = dir_name

    evaluate_question_defaults(template, answers)

    # PM 可用性检查：默认 PM 不可用时自动降级（仅 defaults 层，CLI 显式指定不覆盖）
    # 必须在 evaluate_question_defaults 之后，确保 Jinja2 模板默认值已渲染
    _check_pm_availability(answers)

    if not defaults:
        prompt = InteractivePrompt(template.questions, answers, backend=prompt_backend)
        try:
            answers = prompt.run()
        except KeyboardInterrupt:
            answers.save_partial()
            raise InitInterruptedError() from None

    return template, answers


def _check_pm_availability(answers: AnswersMap) -> None:
    """检测包管理器 CLI 可用性，不可用时自动降级。

    仅当 package_manager 来自 defaults 层（非 CLI/interactive 显式指定）时才检查。
    Node.js PM 降级链: pnpm → npm, yarn → npm, bun → npm。

    ⚠ 副作用: 降级时会直接修改 answers.defaults["package_manager"]。
    """
    pm = answers.get("package_manager")
    if not pm:
        return
    # 用户显式指定（CLI 或交互）→ 不覆盖
    if pm in answers.cli_overrides or pm in answers.interactive:
        return
    if shutil.which(pm) is not None:
        return
    # PM 不可用，尝试降级
    node_fallbacks = {"pnpm": "npm", "yarn": "npm", "bun": "npm"}
    fallback = node_fallbacks.get(pm)
    if fallback and shutil.which(fallback):
        _logger.warning(
            "%s 未安装，已自动降级为 %s。安装 %s 后可重新初始化。",
            pm, fallback, pm,
        )
        answers.defaults["package_manager"] = fallback
    else:
        _logger.warning(
            "%s 未安装且无可降级方案。请安装后重新运行，或使用 --package-manager 指定。",
            pm,
        )