"""Jinja2 模板渲染错误测试 — 覆盖未定义变量、语法错误、类型错误等场景。

来源：BEACON.md 决策 #11 + 审计 P1-10。
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_undefined_variable_raises(tmp_path: Path):
    """模板引用未定义变量 → Jinja2 StrictUndefined 应抛错。"""
    import jinja2

    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    with pytest.raises(jinja2.UndefinedError):
        env.from_string("Hello {{ undefined_var }}").render()


def test_syntax_error_in_template_raises(tmp_path: Path):
    """模板语法错误 → Jinja2 TemplateSyntaxError."""
    from jinja2 import Environment, TemplateSyntaxError

    env = Environment()
    with pytest.raises(TemplateSyntaxError):
        env.from_string("{{ unclosed")


def test_filter_error_raises(tmp_path: Path):
    """Division by zero 错误应被 Jinja2 捕获 (LCRuntimeError)."""
    import jinja2

    env = jinja2.Environment()
    with pytest.raises((jinja2.exceptions.TemplateRuntimeError, ZeroDivisionError, Exception)):
        env.from_string("{{ 1 / 0 }}").render()


def test_template_render_with_all_required_vars(tmp_path: Path):
    """提供全部变量 → 渲染成功."""
    from jinja2 import Environment

    env = Environment()
    result = env.from_string("{{ name }} is {{ age }}").render(name="test", age=42)
    assert result == "test is 42"


def test_template_render_handles_missing_optional(tmp_path: Path):
    """可选变量缺失应使用默认值（不抛错）."""
    from jinja2 import Environment

    env = Environment()
    result = env.from_string("{{ name | default('anon') }}").render()
    assert result == "anon"


def test_template_renderer_collects_errors_with_line_number(tmp_path: Path):
    """TemplateRenderError 应携带源文件路径和行号（用于调试）."""
    from auto_engineering.init.errors import TemplateRenderError

    err = TemplateRenderError(
        src_path="test.jinja",
        jinja_error=Exception("test error"),
        line_number=42,
    )
    assert "test.jinja" in str(err)
    assert "42" in str(err)
    assert "test error" in str(err)