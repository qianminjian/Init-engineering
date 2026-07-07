"""Question 默认值评估 — Jinja2 渲染 + when 条件裁剪。

从 scaffold_phases.py 拆分（v2.5：501→300 行）。

设计：
- 遍历 TemplateConfig.questions，逐条应用 Jinja2 模板渲染 + when 条件评估
- 即使 --defaults 模式也需执行（否则 use_typescript 等 Jinja2 默认值不被渲染）
"""

from __future__ import annotations

import logging

import jinja2
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from .answers import AnswersMap
from .config_types import Question, TemplateConfig

_logger = logging.getLogger(__name__)


def evaluate_question_defaults(template: TemplateConfig, answers: AnswersMap) -> None:
    """在 AnswersMap 上原地应用 question when/默认值的 Jinja2 渲染.

    副作用（answers.defaults 会被修改）：
    - when 条件 False 时移除 defaults[q.var_name]
    - 含 {{ }} 的 default 被渲染为字符串
    - bool 类型渲染结果自动转为 Python bool（"true"/"yes"/"1"）
    """
    context = answers.combined()
    env = SandboxedEnvironment(undefined=StrictUndefined)

    for q in template.questions:
        _apply_when(q, answers, env, context)
        _render_default(q, answers, env, context)


def _apply_when(q: Question, answers: AnswersMap, env: SandboxedEnvironment, context: dict) -> None:
    if isinstance(q.when, str):
        try:
            tpl = env.from_string(q.when)
            result = tpl.render(**context)
            if not result or result.strip().lower() in ("false", "no", "0", ""):
                answers.defaults.pop(q.var_name, None)
        except jinja2.TemplateError as e:
            _logger.debug("when 条件渲染失败, 保留 question: %s → %s", q.when, e)
    elif q.when is False:
        answers.defaults.pop(q.var_name, None)


def _render_default(q: Question, answers: AnswersMap, env: SandboxedEnvironment, context: dict) -> None:
    if isinstance(q.default, str) and "{{" in q.default:
        try:
            rendered = env.from_string(q.default).render(**context)
            if q.get_type_name() == "bool":
                rendered = rendered.strip().lower() in ("true", "yes", "1")
            answers.defaults[q.var_name] = rendered
        except jinja2.TemplateError as e:
            _logger.debug("default 渲染失败, 保留原始值: %s → %s", q.default, e)
