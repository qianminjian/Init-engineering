"""Phase 2: prompt — 加载 TemplateConfig + 应用 CLI overrides + 交互问答.

来源: scaffold_phase_funcs.py phase_prompt (2026-07-03 拆分).
"""

from __future__ import annotations

from pathlib import Path

from ..answers import AnswersMap
from ..config import TEMPLATES_ROOT, TemplateConfig
from ..detector import ProjectDetector
from ..errors import InitInterruptedError
from ..prompts import InteractivePrompt, prompt_for_nested_template
from ..scaffold_question_eval import evaluate_question_defaults


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
    detection: ProjectDetector | None,
) -> tuple[TemplateConfig, AnswersMap]:
    """加载 TemplateConfig + 应用 CLI overrides + 评估 question + 交互 prompt."""
    template = TemplateConfig.load(project_type or "")
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
        if detection.language:
            answers.builtins.setdefault("language", detection.language)
        if detection.package_manager:
            answers.builtins.setdefault("package_manager", detection.package_manager)
        if detection.test_runner:
            answers.builtins.setdefault("test_runner", detection.test_runner)
        if detection.ci_platform:
            answers.builtins.setdefault("ci_platform", detection.ci_platform)

    # 检查 var 单个字符串,不是 list in AnswersMap (会触发 __contains__ 内部迭代 ChainMap)
    for var in ["project_description", "language", "package_manager",
                "test_runner", "ci_platform", "project_type"]:
        if var not in answers:  # __contains__ 处理单 key
            answers.builtins[var] = ""

    evaluate_question_defaults(template, answers)

    if not defaults:
        prompt = InteractivePrompt(template.questions, answers)
        try:
            answers = prompt.run()
        except KeyboardInterrupt:
            answers.save_partial()
            raise InitInterruptedError() from None

    return template, answers