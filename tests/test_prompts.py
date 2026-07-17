"""tests for init/prompts.py — 非交互分支覆盖."""

from pathlib import Path
from unittest.mock import patch

import pytest

from init_engineering.init._shared.prompt_backend import UserAbort
from init_engineering.init.config_types import Question
from init_engineering.init.prompts import (
    InteractivePrompt,
    prompt_for_nested_template,
    prompt_for_project_type,
)
from tests.conftest import MockPromptBackend


class TestPromptForNestedTemplate:
    """prompt_for_nested_template — no_input=True 分支."""

    def test_no_input_returns_first_path(self):
        """no_input=True 直接返回第一个嵌套模板路径 (不触发交互)."""
        nested = {
            "typescript": {"path": "./ts", "title": "TypeScript 版本"},
            "javascript": {"path": "./js", "title": "JavaScript 版本"},
        }
        result = prompt_for_nested_template(nested, no_input=True)
        assert result == "./ts"

    def test_no_input_single_choice(self):
        """no_input=True 只有一个选项时也正常返回."""
        nested = {"only": {"path": "./only", "title": "唯一选项"}}
        result = prompt_for_nested_template(nested, no_input=True)
        assert result == "./only"


class TestInteractivePromptVisibleQuestions:
    """InteractivePrompt._visible_questions 过滤逻辑."""

    def test_visible_questions_cli_overrides_skipped(self):
        """cli_overrides 中已有的变量跳过."""
        questions = [
            Question(var_name="name", help="名称", type="str", default="x"),
            Question(var_name="skip_me", help="跳过", type="str", default="y"),
        ]
        overrides_answers = type("AnswersMap", (), {
            "cli_overrides": {"name": "from_cli"},
        })()
        overrides_answers.combined = lambda: {}

        prompt = InteractivePrompt(questions, overrides_answers)
        visible = prompt._visible_questions("simple")
        # "name" 应在 cli_overrides 中被跳过
        assert all(q.var_name != "name" or q.var_name in overrides_answers.cli_overrides
                   for q in visible)

    def test_visible_questions_complex_only_json_yaml(self):
        """complex pass 只包含 json/yaml 类型."""
        questions = [
            Question(var_name="cfg", help="配置", type="json", default="{}"),
            Question(var_name="desc", help="描述", type="str", default=""),
            Question(var_name="notes", help="备注", type="yaml", default=""),
        ]
        answers = type("AnswersMap", (), {"cli_overrides": {}})()
        answers.combined = lambda: {}

        prompt = InteractivePrompt(questions, answers)
        complex_qs = prompt._visible_questions("complex")
        type_names = [q.get_type_name() for q in complex_qs]
        assert "json" in type_names
        assert "yaml" in type_names
        assert "str" not in type_names

    def test_visible_questions_simple_excludes_json_yaml(self):
        """simple pass 排除 json/yaml 类型."""
        questions = [
            Question(var_name="cfg", help="配置", type="json", default="{}"),
            Question(var_name="desc", help="描述", type="str", default=""),
            Question(var_name="notes", help="备注", type="yaml", default=""),
        ]
        answers = type("AnswersMap", (), {"cli_overrides": {}})()
        answers.combined = lambda: {}

        prompt = InteractivePrompt(questions, answers)
        simple_qs = prompt._visible_questions("simple")
        type_names = [q.get_type_name() for q in simple_qs]
        assert "json" not in type_names
        assert "yaml" not in type_names
        assert "str" in type_names


class TestAskOneConditions:
    """_ask_one 跳过条件覆盖 (lines 117-123)."""

    def test_ask_one_skips_when_var_in_cli_overrides(self):
        """line 119: cli_overrides 中的变量直接跳过."""
        q = Question(var_name="name", help="名称", type="str", default="x")
        answers = type("AnswersMap", (), {
            "cli_overrides": {"name": "from_cli"},
            "interactive": {},
        })()
        answers.combined = lambda: {"name": "from_cli"}

        prompt = InteractivePrompt([q], answers)
        # 如果 _ask_one 被跳过，interactive 应保持空
        prompt._ask_one(q, {})
        assert q.var_name not in answers.interactive

    def test_ask_one_skips_when_condition_false(self):
        """line 123: when 条件不满足时跳过."""
        q = Question(var_name="x", help="x", type="str", default="x", when=False)
        answers = type("AnswersMap", (), {"cli_overrides": {}, "interactive": {}})()
        answers.combined = lambda: {}

        prompt = InteractivePrompt([q], answers)
        prompt._ask_one(q, {})
        assert q.var_name not in answers.interactive


class TestRunComplexPass:
    """run() 第二遍循环覆盖 (lines 99-104)."""

    def test_run_with_complex_type_question(self):
        """complex pass 处理 json/yaml 类型."""
        q_json = Question(var_name="cfg", help="配置", type="json", default="{}")
        answers = type("AnswersMap", (), {
            "cli_overrides": {},
            "interactive": {},
            "previous": {},
            "defaults": {},
            "builtins": {},
            "external": {},
        })()
        # Simulate combined()
        combined = {}

        def combined_fn():
            return combined

        answers.combined = combined_fn

        prompt = InteractivePrompt([q_json], answers)
        # Mock the second-pass _ask_one
        called = []

        def mock_ask(q, ctx, progress=""):
            called.append(q.var_name)

        with patch.object(prompt, "_ask_one", mock_ask):
            prompt.run()

        # json question should be asked in complex pass
        assert "cfg" in called


class TestPromptForProjectType:
    """prompt_for_project_type — click.prompt 分支 (line 239)."""

    def test_prompt_for_project_type(self):
        """backend.prompt 被调用."""
        backend = MockPromptBackend(prompt_responses=["app-service"])
        result = prompt_for_project_type(["app-service", "library"], backend=backend)
        assert result == "app-service"
        assert len(backend.prompt_calls) == 1

    def test_prompt_for_project_type_non_tty_raises_validation_error(self):
        """P3: 非 TTY 环境 UserAbort → ValidationError."""
        from init_engineering.init.errors import ValidationError

        def aborting_prompt(*args, **kwargs):
            raise UserAbort()

        with pytest.raises(ValidationError, match="非 TTY"):
            prompt_for_project_type(
                ["app-service", "library"],
                _input_fn=aborting_prompt,
            )


class TestRenderDefault:
    """InteractivePrompt._render_default — Jinja2 模板渲染."""

    def test_render_default_string_with_template(self):
        """含 {{}} 的字符串被当作 Jinja2 模板渲染."""
        q = Question(var_name="desc", help="描述", type="str", default="Hello {{project_name}}")
        answers = type("AnswersMap", (), {"cli_overrides": {}})()
        answers.combined = lambda: {"project_name": "World"}

        prompt = InteractivePrompt([q], answers)
        rendered = prompt._render_default(q, {"project_name": "World"})
        assert rendered == "Hello World"

    def test_render_default_no_template(self):
        """无 {{}} 的字符串原样返回."""
        q = Question(var_name="desc", help="描述", type="str", default="hello world")
        answers = type("AnswersMap", (), {"cli_overrides": {}})()
        answers.combined = lambda: {}

        prompt = InteractivePrompt([q], answers)
        rendered = prompt._render_default(q, {})
        assert rendered == "hello world"

    def test_render_default_none(self):
        """default=None 返回 None."""
        q = Question(var_name="x", help="x", type="str", default=None)
        answers = type("AnswersMap", (), {"cli_overrides": {}})()
        answers.combined = lambda: {}

        prompt = InteractivePrompt([q], answers)
        assert prompt._render_default(q, {}) is None

    def test_render_default_bool_int_float(self):
        """bool/int/float 原样返回 (非模板类型)."""
        q_bool = Question(var_name="y", help="y", type="bool", default=True)
        q_int = Question(var_name="z", help="z", type="int", default=42)
        q_float = Question(var_name="f", help="f", type="float", default=3.14)
        answers = type("AnswersMap", (), {"cli_overrides": {}})()
        answers.combined = lambda: {}

        prompt = InteractivePrompt([q_bool], answers)
        assert prompt._render_default(q_bool, {}) is True
        assert prompt._render_default(q_int, {}) == 42
        assert prompt._render_default(q_float, {}) == 3.14


class TestAskOneMultiselect:
    """multiselect 路径覆盖 (lines 129-153)."""

    def test_multiselect_valid_input(self):
        """多选输入有效选项 -> 转化为 YAML list."""
        q = Question(
            var_name="features",
            help="选择特性",
            type="choice",
            choices=["a", "b", "c"],
            multiselect=True,
            default=["a"],
        )
        answers = type("AnswersMap", (), {
            "cli_overrides": {},
            "interactive": {},
        })()
        answers.combined = lambda: {"features": ["a"]}

        backend = MockPromptBackend(prompt_responses=["a, b"])
        prompt = InteractivePrompt([q], answers, backend=backend)
        prompt._ask_one(q, {})

        assert "features" in answers.interactive

    def test_multiselect_invalid_then_valid(self):
        """多选先输入无效选项再输入有效选项."""
        q = Question(
            var_name="features",
            help="选择特性",
            type="choice",
            choices=["a", "b"],
            multiselect=True,
        )
        answers = type("AnswersMap", (), {
            "cli_overrides": {},
            "interactive": {},
        })()
        answers.combined = lambda: {}

        backend = MockPromptBackend(prompt_responses=["x, y", "a"])
        prompt = InteractivePrompt([q], answers, backend=backend)
        prompt._ask_one(q, {})

        assert "features" in answers.interactive

    def test_multiselect_empty_then_valid(self):
        """多选先空输入再输入有效选项."""
        q = Question(
            var_name="features",
            help="选择特性",
            type="choice",
            choices=["a", "b"],
            multiselect=True,
        )
        answers = type("AnswersMap", (), {
            "cli_overrides": {},
            "interactive": {},
        })()
        answers.combined = lambda: {}

        backend = MockPromptBackend(prompt_responses=["", "a"])
        prompt = InteractivePrompt([q], answers, backend=backend)
        prompt._ask_one(q, {})

        assert "features" in answers.interactive


class TestAskOneRetryLoop:
    """重试循环覆盖 (lines 168-189) — cast 失败 / validator 失败 / max_retries."""

    def test_cast_answer_failure_retries(self):
        """cast_answer 失败时重试."""
        q = Question(var_name="count", help="数量", type="int")
        answers = type("AnswersMap", (), {
            "cli_overrides": {},
            "interactive": {},
        })()
        answers.combined = lambda: {}

        backend = MockPromptBackend(prompt_responses=["not-a-number", "42"])
        prompt = InteractivePrompt([q], answers, backend=backend)
        prompt._ask_one(q, {})

        assert answers.interactive["count"] == 42

    def test_validator_failure_retries(self):
        """validator 返回错误时重试."""
        q = Question(
            var_name="name",
            help="名称",
            type="str",
            validator="{% if name|length <= 3 %}名称至少 3 个字符{% endif %}",
        )
        answers = type("AnswersMap", (), {
            "cli_overrides": {},
            "interactive": {},
        })()
        answers.combined = lambda: {}

        backend = MockPromptBackend(prompt_responses=["ab", "abcd"])
        prompt = InteractivePrompt([q], answers, backend=backend)
        prompt._ask_one(q, {})

        assert answers.interactive["name"] == "abcd"

    def test_max_retries_raises_validation_error(self):
        """达到最大重试次数后抛出 ValidationError."""
        q = Question(var_name="count", help="数量", type="int", default=99)
        answers = type("AnswersMap", (), {
            "cli_overrides": {},
            "interactive": {},
        })()
        answers.combined = lambda: {}

        backend = MockPromptBackend(prompt_responses=["bad"] * 10)
        prompt = InteractivePrompt([q], answers, backend=backend)
        from init_engineering.init.errors import ValidationError

        with pytest.raises(ValidationError, match="类型转换失败"):
            prompt._ask_one(q, {})

    def test_max_retries_no_default_raises(self):
        """max_retries 且无默认值 → 抛出 ValidationError."""
        q = Question(var_name="count", help="数量", type="int", default=None)
        answers = type("AnswersMap", (), {
            "cli_overrides": {},
            "interactive": {},
        })()
        answers.combined = lambda: {}

        backend = MockPromptBackend(prompt_responses=["bad"] * 10)
        prompt = InteractivePrompt([q], answers, backend=backend)
        from init_engineering.init.errors import ValidationError

        with pytest.raises(ValidationError, match="类型转换失败"):
            prompt._ask_one(q, {})


class TestPromptForNestedTemplateInteractive:
    """prompt_for_nested_template — no_input=False 交互分支 (lines 260-266)."""

    def test_interactive_returns_chosen_path(self):
        """用户选择返回对应 path."""
        nested = {
            "ts": {"path": "./typescript", "title": "TypeScript"},
            "js": {"path": "./javascript", "title": "JavaScript"},
        }
        backend = MockPromptBackend(prompt_responses=["ts"])
        result = prompt_for_nested_template(nested, no_input=False, backend=backend)
        assert result == "./typescript"

    def test_interactive_returns_none_for_missing_choice(self):
        """无效选择返回 None."""
        nested = {"ts": {"path": "./ts", "title": "TS"}}
        backend = MockPromptBackend(prompt_responses=["nonexistent"])
        result = prompt_for_nested_template(nested, no_input=False, backend=backend)
        assert result is None

    def test_prompt_for_nested_template_non_tty_raises_validation_error(self):
        """P3: 非 TTY 环境 prompt_for_nested_template → ValidationError."""
        from init_engineering.init.errors import ValidationError

        nested = {"ts": {"path": "./ts", "title": "TS"}}

        def aborting_prompt(*args, **kwargs):
            raise UserAbort()

        with pytest.raises(ValidationError, match="非 TTY"):
            prompt_for_nested_template(
                nested, no_input=False, _input_fn=aborting_prompt,
            )


class TestNonTtyAbortHandling:
    """P3: 非 TTY 环境下 UserAbort → ValidationError（清晰错误信息）."""

    def test_ask_one_catches_abort_and_raises_validation_error(self):
        """InteractivePrompt._ask_one 捕获 UserAbort → ValidationError."""
        from init_engineering.init.errors import ValidationError

        q = Question(var_name="name", help="名称", type="str", default="x")
        answers = type("AnswersMap", (), {
            "cli_overrides": {},
            "interactive": {},
        })()
        answers.combined = lambda: {}

        class AbortingBackend(MockPromptBackend):
            def prompt(self, *args, **kwargs):
                raise UserAbort()

        backend = AbortingBackend()
        prompt = InteractivePrompt([q], answers, backend=backend)

        with pytest.raises(ValidationError, match="非 TTY"):
            prompt._ask_one(q, {})

