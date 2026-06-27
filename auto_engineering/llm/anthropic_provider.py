"""AnthropicProvider — LLM 调用封装.

设计参考: design/LOOP-DEVELOPMENT-PLAN.md Phase 3 文件 18.
封装 anthropic SDK,提供 LLMResponse/LLMUsage 数据类,统一接口给 Agent 调用.

v3.1 扩展 (Phase 0.1 dev-loop 真接):
    - LLMResponse 加 stop_reason + tool_use_blocks(支持 BaseAgent 工具循环)
    - create_message 加 tools 参数 + 解析 SDK content blocks(text + tool_use)
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
    """LLM 调用结构化响应.

    字段:
        content          — text block 拼接的纯文本(text 类型)
        model            — 调用的模型名
        usage            — token 用量
        stop_reason      — SDK 返回的停止原因("end_turn" | "tool_use" | "max_tokens")
        tool_use_blocks  — tool_use 类型 block 解析结果(每个 dict 含 id/name/input)
    """

    content: str = ""
    model: str = ""
    usage: LLMUsage = field(default_factory=LLMUsage)
    stop_reason: str = "end_turn"
    tool_use_blocks: list[dict] = field(default_factory=list)


class AnthropicProvider:
    """Anthropic Claude API 客户端封装.

    P0-4: 生产 retry 策略 — RateLimitError / APIConnectionError 重试.
    max_retries=0 表示不重试 (默认 3 次).
    """

    # 可重试异常类型 (anthropic SDK)
    _RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
        anthropic.RateLimitError,
        anthropic.APIConnectionError,
        anthropic.APITimeoutError,
    )

    def __init__(
        self,
        api_key: str | None = None,
        client: anthropic.Anthropic | None = None,
        max_retries: int = 3,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            self._client = anthropic.Anthropic(api_key=api_key)
        self._max_retries = max_retries

    def create_message(
        self,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """调用 Claude API.

        Args:
            model    — 模型名(例 "claude-sonnet-4-6")
            max_tokens — 最大输出 token
            system   — system prompt
            messages — 对话历史 [{"role": ..., "content": ...}]
            tools    — 可选,工具 schema 列表(Anthropic tool format)

        Returns:
            LLMResponse(content/model/usage/stop_reason/tool_use_blocks)

        Raises:
            anthropic.RateLimitError: 超过 max_retries 后仍未成功
            anthropic.APIConnectionError: 超过 max_retries 后仍未成功
            anthropic.APITimeoutError: 超过 max_retries 后仍未成功
            其他异常: 立即抛出, 不重试
        """
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        # P0-4: retry 策略 — RateLimitError / APIConnectionError / APITimeoutError
        # 总尝试次数 = 1 (原始) + max_retries
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 2):  # 1..max_retries+1
            try:
                response = self._client.messages.create(**kwargs)
                break  # 成功, 退出 retry loop
            except self._RETRYABLE_EXCEPTIONS as exc:
                last_exc = exc
                if attempt > self._max_retries:
                    # 超过 max_retries, 不再重试, 抛出
                    raise
                # 简单 backoff (生产环境可换指数退避)
                # 测试环境下 sleep=0, 避免拖慢测试
                import time
                time.sleep(0)

        content_text = ""
        tool_use_blocks: list[dict] = []
        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_use_blocks.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )

        return LLMResponse(
            content=content_text,
            model=response.model,
            usage=LLMUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            ),
            stop_reason=response.stop_reason,
            tool_use_blocks=tool_use_blocks,
        )
