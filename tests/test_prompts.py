"""tests for init/prompts.py — 非交互分支覆盖."""

from pathlib import Path

import pytest

from auto_engineering.init.prompts import (
    InteractivePrompt,
    prompt_for_nested_template,
)
from auto_engineering.init.config_types import Question


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
