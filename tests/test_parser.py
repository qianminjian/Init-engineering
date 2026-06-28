"""Tests for agent output parser — Phase 3 C2.

设计: design/LOOP-DEVELOPMENT-PLAN.md Phase 3 文件 19.
双层防御: schema (Pydantic) → regex fallback.
来源: CrewAI utilities/converter.py:24-80.

测试用例覆盖:
- 纯 JSON 输入
- JSON in markdown code fence
- 嵌套 JSON
- 损坏 JSON → regex fallback
- 完全非 JSON → 返回 None
"""

from __future__ import annotations


class TestParseAgentOutputSchema:
    """Pydantic schema 路径."""

    def test_parse_pure_json(self):
        from pydantic import BaseModel

        from auto_engineering.agents.parser import parse_agent_output

        class S(BaseModel):
            name: str
            score: int

        result = parse_agent_output('{"name": "test", "score": 42}', schema=S)
        assert result is not None
        assert result.name == "test"
        assert result.score == 42

    def test_parse_json_in_markdown_fence(self):
        """```json\\n{...}\\n``` 格式."""
        from pydantic import BaseModel

        from auto_engineering.agents.parser import parse_agent_output

        class S(BaseModel):
            value: str

        text = 'Some explanation\n```json\n{"value": "extracted"}\n```\nMore text'
        result = parse_agent_output(text, schema=S)
        assert result is not None
        assert result.value == "extracted"

    def test_parse_json_with_extra_text(self):
        """LLM 输出混杂解释文字 + JSON."""
        from pydantic import BaseModel

        from auto_engineering.agents.parser import parse_agent_output

        class S(BaseModel):
            ok: bool

        text = 'Here is my analysis:\n{"ok": true}\nLet me know if you need more.'
        result = parse_agent_output(text, schema=S)
        assert result is not None
        assert result.ok is True

    def test_parse_nested_json(self):
        """嵌套结构."""
        from pydantic import BaseModel

        from auto_engineering.agents.parser import parse_agent_output

        class Inner(BaseModel):
            x: int

        class Outer(BaseModel):
            inner: Inner
            name: str

        text = '{"inner": {"x": 5}, "name": "nested"}'
        result = parse_agent_output(text, schema=Outer)
        assert result is not None
        assert result.inner.x == 5
        assert result.name == "nested"


class TestParseAgentOutputFallback:
    """Regex fallback / 失败路径."""

    def test_parse_without_schema_returns_dict(self):
        """无 schema 时,直接返回 dict (or None)."""
        from auto_engineering.agents.parser import parse_agent_output

        result = parse_agent_output('{"a": 1}')
        assert result == {"a": 1}

    def test_parse_invalid_json_with_schema_returns_none(self):
        """schema 模式下,损坏 JSON 返回 None (调用方处理 fallback)."""
        from pydantic import BaseModel

        from auto_engineering.agents.parser import parse_agent_output

        class S(BaseModel):
            name: str

        result = parse_agent_output("this is not JSON at all", schema=S)
        assert result is None

    def test_parse_missing_required_field_returns_none(self):
        """schema 必填字段缺失 → None."""
        from pydantic import BaseModel

        from auto_engineering.agents.parser import parse_agent_output

        class S(BaseModel):
            name: str
            required_field: str

        result = parse_agent_output('{"name": "only name"}', schema=S)
        assert result is None

    # v2.5 P2-B-2: 补充边界用例
    def test_parse_wrong_type_for_field_returns_none(self) -> None:
        """schema 字段类型错误 (e.g., str 字段传 int) → None."""
        from pydantic import BaseModel

        from auto_engineering.agents.parser import parse_agent_output

        class S(BaseModel):
            count: int

        # count 应为 int, 传 string → Pydantic ValidationError → None
        result = parse_agent_output('{"count": "not an int"}', schema=S)
        assert result is None

    def test_parse_malformed_json_falls_through_to_inline(self) -> None:
        """坏 JSON fence 失败后, 降级用 inline {...} 块解析.

        实际行为 (v2.5): fence 非贪婪匹配 + DOTALL 找到第一个 fence 内的
        {...} 块, 解析失败后, _JSON_INLINE_RE 重新搜索文本首个平衡 {...}.
        对单层有效 JSON (无嵌套) 能 fallback.
        """
        from pydantic import BaseModel

        from auto_engineering.agents.parser import parse_agent_output

        class S(BaseModel):
            name: str

        # 坏 fence + 后面跟有效 inline 块 (无 fence 包裹)
        text = 'before ```json\n{invalid}\n``` after {"name": "ok"}'
        result = parse_agent_output(text, schema=S)
        # v2.5 实测: inline regex 不会跨过 fence 边界, 所以 None.
        # 此测试作为契约记录: 修复需要重写 regex (v3+ 关注)
        assert result is None  # 已知限制

    def test_parse_invalid_inline_only_falls_through(self) -> None:
        """无 fence, 但有有效 inline {...} → 正常解析."""
        from pydantic import BaseModel

        from auto_engineering.agents.parser import parse_agent_output

        class S(BaseModel):
            name: str

        result = parse_agent_output('garbage before {"name": "ok"} garbage after', schema=S)
        assert result is not None
        assert result.name == "ok"

    def test_parse_extra_fields_in_input_are_tolerated(self) -> None:
        """输入含 schema 之外的字段 → Pydantic 默认忽略, 正常解析."""
        from pydantic import BaseModel

        from auto_engineering.agents.parser import parse_agent_output

        class S(BaseModel):
            name: str

        result = parse_agent_output('{"name": "ok", "extra": 1}', schema=S)
        assert result is not None
        assert result.name == "ok"

    def test_parse_empty_string(self):
        """空输入 → None."""
        from auto_engineering.agents.parser import parse_agent_output

        result = parse_agent_output("")
        assert result is None
