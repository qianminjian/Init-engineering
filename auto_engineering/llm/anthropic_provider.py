"""AnthropicProvider — LLM 调用封装.

设计参考: design/LOOP-DEVELOPMENT-PLAN.md Phase 3 文件 18.
封装 anthropic SDK,提供 LLMResponse/LLMUsage 数据类,统一接口给 Agent 调用.
"""

from __future__ import annotations

from dataclasses import dataclass

import anthropic


@dataclass
class LLMUsage:
    """Token 用量统计."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LLMResponse:
    """LLM 调用结构化响应."""

    content: str
    model: str
    usage: LLMUsage


class AnthropicProvider:
    """Anthropic Claude API 客户端封装."""

    def __init__(
        self,
        api_key: str | None = None,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            self._client = anthropic.Anthropic(api_key=api_key)

    def create_message(
        self,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict],
    ) -> LLMResponse:
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            usage=LLMUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            ),
        )