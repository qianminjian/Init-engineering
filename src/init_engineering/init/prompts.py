"""InteractivePrompt — 交互式问答 + 项目类型/嵌套模板选择.

来源：
- copier/_user_data.py:297-460 — Question.get_default_rendered() + render_value()
- cookiecutter/prompt.py:284-363 — prompt_for_config() 两遍循环 + 进度显示
- cookiecutter/prompt.py:61-80 — read_user_yes_no() 灵活的布尔解析

接口：
  InteractivePrompt(questions, answers, backend=None) -> .run() -> AnswersMap
  prompt_for_project_type / prompt_for_nested_template — 独立选择函数

架构: 核心层不直接依赖 click, 通过 PromptBackend 协议注入用户交互实现。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import jinja2.sandbox
from jinja2 import StrictUndefined

from ._shared.prompt_backend import BasicPromptBackend, PromptBackend, UserAbort
from .answers import AnswersMap
from .errors import ValidationError

_logger = logging.getLogger(__name__)
from .config_types import Question  # noqa: E402


class InteractivePrompt:
    """逐一展示 Question。

    参考 Cookiecutter prompt_for_config() 的两遍循环结构：
    - 第一遍：简单类型（str/bool/int/float/choice/secret）→ 先收集基础信息
    - 第二遍：复杂类型（json/yaml）→ 依赖基础信息可渲染
    同时借鉴 Copier Question 的 when 条件跳过逻辑。

    示例用法：
        questions: list[Question] = [...]
        answers = AnswersMap(defaults={"name": "test"})
        prompt = InteractivePrompt(questions, answers)
        result = prompt.run()  # 返回更新后的 AnswersMap
    """

    def __init__(
        self,
        questions: list[Question],
        answers: AnswersMap,
        backend: PromptBackend | None = None,
    ):
        self.questions = questions
        self.answers = answers
        self._backend = backend or BasicPromptBackend()
        self._jinja_env = jinja2.sandbox.SandboxedEnvironment(undefined=StrictUndefined)

    def run(self) -> AnswersMap:
        """执行交互式问答。返回更新后的 AnswersMap。

        ⚠ 副作用: 返回的是构造时传入的 self.answers 对象 (原地修改),
        非新拷贝。调用者应据此处理引用语义。

        两遍循环：
        1. 第一遍：简单类型 → 收集基础变量
        2. 第二遍：复杂类型 → 依赖第一遍的变量进行渲染
        """
        context = self.answers.combined()

        # 第一遍：简单类型（非 json/yaml）
        for i, q in enumerate(self._visible_questions("simple")):
            self._ask_one(q, context, progress=f"[{i + 1}/{len(self.questions)}]")
            context = self.answers.combined()  # 刷新 context 供后续 when 判断

        # 第二遍：复杂类型（json/yaml — 依赖第一遍收集的变量）
        for q in self._visible_questions("complex"):
            self._ask_one(q, context, progress="")
            context = self.answers.combined()

        return self.answers

    # ── 类型分发 (替代 _PROMPT_DISPATCH dict) ──────────────

    def _prompt_str(self, q: Question, _ctx: dict) -> str:
        return self._backend.prompt(q.help, default=q.default or "")

    def _prompt_bool(self, q: Question, _ctx: dict) -> bool:
        return self._backend.confirm(
            q.help,
            default=q.default if isinstance(q.default, bool) else True,
        )

    def _prompt_int(self, q: Question, _ctx: dict) -> int:
        return self._backend.prompt(q.help, type=int, default=q.default or 0)

    def _prompt_float(self, q: Question, _ctx: dict) -> float:
        return self._backend.prompt(q.help, type=float, default=q.default or 0.0)

    def _prompt_choice(self, q: Question, _ctx: dict) -> str:
        choices = list(q.choices) if isinstance(q.choices, list) else list(q.choices.keys())
        while True:
            raw = self._backend.prompt(
                q.help,
                default=q.default,
                show_default=True,
            )
            if raw in choices:
                return raw
            self._backend.echo(f"  ✗ 无效选项: {raw}，有效选项: {choices}", err=True)

    def _prompt_secret(self, q: Question, _ctx: dict) -> str:
        if hasattr(self._backend, "hide_input"):
            return self._backend.hide_input(q.help, default=str(q.default or ""))
        return self._backend.prompt(q.help, default=str(q.default or ""))

    def _prompt_json(self, q: Question, _ctx: dict) -> str:
        return self._backend.prompt(q.help, default=str(q.default or "{}"))

    def _prompt_yaml(self, q: Question, _ctx: dict) -> str:
        return self._backend.prompt(q.help, default=str(q.default or ""))

    def _make_multiselect_prompter(self, q: Question) -> Callable:
        """构建 multiselect 类型的 prompt 函数."""
        choices_list = (
            list(q.choices)
            if isinstance(q.choices, list)
            else list(q.choices.keys())
        )
        default_str = (
            ",".join(q.default)
            if isinstance(q.default, list)
            else q.default or ""
        )

        def _prompt(_q, _ctx, _choices=choices_list, _default=default_str):
            while True:
                raw = self._backend.prompt(
                    _q.help,
                    default=_default,
                    show_default=True,
                )
                selected = [s.strip() for s in raw.split(",") if s.strip()]
                invalid = [s for s in selected if s not in _choices]
                if invalid:
                    self._backend.echo(
                        f"  ✗ 无效选项: {invalid}，有效选项: {_choices}", err=True
                    )
                    continue
                if not selected:
                    self._backend.echo("  ✗ 请至少选择一个选项", err=True)
                    continue
                return "\n".join(f"- {v}" for v in selected)

        return _prompt

    def _get_prompt_fn(self, type_name: str) -> Callable:
        dispatch = {
            "str": self._prompt_str,
            "bool": self._prompt_bool,
            "int": self._prompt_int,
            "float": self._prompt_float,
            "choice": self._prompt_choice,
            "secret": self._prompt_secret,
            "json": self._prompt_json,
            "yaml": self._prompt_yaml,
        }
        return dispatch.get(type_name, self._prompt_str)

    def _ask_one(self, q: Question, context: dict, progress: str = "") -> None:
        """询问单个问题。

        流程（6 步）：
        1. CLI flag 已提供 → 跳过
        2. when 条件检查 → 不满足则跳过
        3. 类型推导 + multiselect 分发
        4. 渲染默认值（Jinja2 模板）
        5. 循环 prompt → cast → validate（最多 5 次重试）
        6. 存入 answers.interactive
        """
        # CLI flag 已提供 → 跳过
        if q.var_name in self.answers.cli_overrides:
            return

        # when 条件不满足 → 跳过
        if not q.render_when(context, self._jinja_env):
            return

        type_name = q.get_type_name()
        if q.multiselect:
            prompt_fn = self._make_multiselect_prompter(q)
        else:
            prompt_fn = self._get_prompt_fn(type_name)

        # 渲染 default（来源：Copier Question.get_default_rendered()）
        rendered_default = self._render_default(q, context)

        # 临时替换 q.default 为渲染后的值
        orig_default = q.default
        q.default = rendered_default

        try:
            prefix = f"  {progress} " if progress else "  "
            self._backend.echo(f"{prefix}{q.help}")

            max_retries = 5
            for attempt in range(max_retries):
                try:
                    raw_value = prompt_fn(q, context)
                except UserAbort:
                    raise ValidationError(
                        "非 TTY 环境无法交互，请使用 --defaults 非交互模式",
                        field_name=q.var_name,
                    ) from None
                if isinstance(raw_value, tuple):
                    raw_value = "\n".join(f"- {v}" for v in raw_value)
                try:
                    value = q.cast_answer(raw_value)
                except TypeError as e:
                    _logger.debug(
                        "cast_answer TypeError (var=%s, raw=%r): %s",
                        q.var_name, raw_value, e,
                        exc_info=True,
                    )
                    if attempt == max_retries - 1:
                        raise ValidationError(
                            f"类型转换失败 (已达最大重试 {max_retries}): {e}",
                            field_name=q.var_name,
                        ) from e
                    self._backend.echo(f"  ✗ 类型转换失败: {e}", err=True)
                    continue
                except ValueError as e:
                    if attempt == max_retries - 1:
                        raise ValidationError(
                            f"类型转换失败 (已达最大重试 {max_retries}): {e}",
                            field_name=q.var_name,
                        ) from e
                    self._backend.echo(f"  ✗ 类型转换失败: {e}", err=True)
                    continue

                error = q.render_validator(value, context, self._jinja_env)
                if error:
                    if attempt == max_retries - 1:
                        raise ValidationError(
                            f"校验失败 (已达最大重试 {max_retries}): {error}",
                            field_name=q.var_name,
                        )
                    self._backend.echo(f"  ✗ {error}", err=True)
                    continue
                break
        finally:
            q.default = orig_default

        self.answers.interactive[q.var_name] = value

    def _visible_questions(self, pass_name: str) -> list[Question]:
        """过滤出当前遍应展示的问题。"""
        result = []
        for q in self.questions:
            if q.var_name in self.answers.cli_overrides:
                continue
            type_name = q.get_type_name()
            if pass_name == "simple":
                if type_name not in ("json", "yaml"):
                    result.append(q)
            else:  # "complex"
                if type_name in ("json", "yaml"):
                    result.append(q)
        return result

    def _render_default(self, q: Question, context: dict) -> Any:
        """渲染 Jinja2 模板默认值。"""
        if q.default is None:
            return None
        if isinstance(q.default, (bool, int, float)):
            return q.default
        if isinstance(q.default, str) and "{{" in q.default:
            tpl = self._jinja_env.from_string(q.default)
            return tpl.render(**context)
        return q.default


# ─── 项目类型 + 嵌套模板选择 (从 _prompt_select.py 折叠) ──────────


def prompt_for_project_type(
    available_types: list[str],
    *,
    _input_fn=None,
    backend: PromptBackend | None = None,
) -> str:
    """当无法自动检测项目类型且非 --defaults 模式时调用。"""
    be = backend or BasicPromptBackend()
    if _input_fn is None:
        _input_fn = be.prompt
    types_list = ", ".join(available_types)
    max_retries = 5
    attempts = 0
    while True:
        attempts += 1
        if attempts > max_retries:
            raise ValidationError(
                f"超过最大重试次数 ({max_retries})，请使用 --type 指定项目类型",
                field_name="project_type",
            )
        try:
            choice = _input_fn(
                f"请选择项目类型 (可选: {types_list})",
                type=None,
                show_default=False,
            )
        except UserAbort:
            raise ValidationError(
                "非 TTY 环境无法交互选择项目类型，请使用 --type 指定",
                field_name="project_type",
            ) from None
        if choice in available_types:
            return choice
        be.echo(f"  ✗ 无效类型: {choice}，有效类型: {types_list}", err=True)


def prompt_for_nested_template(
    nested: dict[str, dict[str, str]],
    no_input: bool = False,
    preferred: str | None = None,
    *,
    _input_fn: Callable | None = None,
    backend: PromptBackend | None = None,
) -> str | None:
    """交互式选择嵌套模板变体。"""
    if not nested:
        return None
    choices = {label: cfg.get("title", label) for label, cfg in nested.items()}
    if no_input:
        if preferred and preferred in nested:
            return nested[preferred].get("path")
        if preferred:
            raise ValueError(
                f"非交互模式下 preferred template '{preferred}' 不在 nested 选项 "
                f"({', '.join(nested.keys())}) 中，无法自动选择。"
            )
        first_key = next(iter(nested.keys()))
        return nested[first_key].get("path")
    if preferred and preferred in nested:
        return nested[preferred].get("path")
    be = backend or BasicPromptBackend()
    prompt_fn = _input_fn if _input_fn is not None else be.prompt
    try:
        choice = prompt_fn(
            "请选择模板变体",
            default=next(iter(choices.keys())),
            show_default=True,
        )
    except UserAbort:
        raise ValidationError(
            "非 TTY 环境无法交互选择模板变体，请使用 --defaults 或 --language 指定",
            field_name="nested_template",
        ) from None
    if choice not in nested:
        # 如果 prompt 返回不在 nested 中的值，尝试 fallback
        for key, cfg in nested.items():
            if cfg.get("title", key) == choice:
                return cfg.get("path")
        return None
    return nested.get(choice, {}).get("path")
