"""PromptBackend protocol + BasicPromptBackend — 解耦 init 核心层与 CLI 库。

init 核心层不应直接依赖 click。BasicPromptBackend 使用 stdlib (input/print)
作为默认实现，CLI 层注入 ClickPromptBackend 提供丰富终端体验。
"""

from __future__ import annotations

from typing import Any, Protocol


class PromptBackend(Protocol):
    """用户交互后端协议 — init 核心层通过此接口与用户交互。

    CLI 层注入 ClickPromptBackend (包装 click.prompt/confirm/echo)。
    测试层注入 mock backend 避免真实终端交互。
    """

    def echo(self, message: str, *, err: bool = False) -> None:
        """输出消息。err=True 时输出到 stderr。"""
        ...

    def prompt(
        self,
        text: str,
        *,
        default: Any = None,
        type: Any = None,
        show_default: bool = True,
        value_proc: Any = None,
    ) -> Any:
        """提示用户输入。type 为 None 时返回字符串。"""
        ...

    def confirm(self, text: str, *, default: bool = False) -> bool:
        """确认 yes/no 问题。"""
        ...

    def hide_input(self, text: str, *, default: str = "") -> str:
        """提示用户输入敏感信息（不回显）。"""
        ...


class UserAbort(Exception):
    """用户主动中断交互 (等价于 click.exceptions.Abort)。"""


class BasicPromptBackend:
    """stdlib 默认实现 — 使用 print/input, 无外部依赖。

    CLI 层可注入 ClickPromptBackend 替代此默认实现。
    """

    def echo(self, message: str, *, err: bool = False) -> None:
        import sys

        out = sys.stderr if err else sys.stdout
        print(message, file=out)

    def prompt(
        self,
        text: str,
        *,
        default: Any = None,
        type: Any = None,
        show_default: bool = True,
        value_proc: Any = None,
    ) -> Any:
        import sys

        if not sys.stdin.isatty():
            raise UserAbort(
                "stdin 不是终端（Claude Code / CI / 管道）。"
                " 请使用 --defaults 非交互模式，或通过 CLI 参数指定所有必要选项。"
            )
        if show_default and default is not None:
            text = f"{text} [{default}]"
        try:
            raw = input(f"{text}: ")
        except (EOFError, KeyboardInterrupt):
            raise UserAbort() from None
        if not raw and default is not None:
            raw = str(default)
        if type is not None and raw:
            try:
                raw = type(raw)
            except (ValueError, TypeError):
                raise ValueError(
                    f"无法将输入值转换为 {type.__name__}: {raw!r}"
                ) from None
        if value_proc is not None and raw:
            raw = value_proc(raw)
        return raw

    def hide_input(self, text: str, *, default: str = "") -> str:
        import getpass
        import sys

        if not sys.stdin.isatty():
            raise UserAbort(
                "stdin 不是终端。请使用 --defaults 非交互模式。"
            )
        if default:
            text = f"{text} [{default}]"
        try:
            raw = getpass.getpass(f"{text}: ")
        except (EOFError, KeyboardInterrupt):
            raise UserAbort() from None
        return raw if raw else default

    def confirm(self, text: str, *, default: bool = False) -> bool:
        suffix = " [Y/n]" if default else " [y/N]"
        try:
            raw = input(f"{text}{suffix}: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            raise UserAbort() from None
        if not raw:
            return default
        return raw in ("y", "yes")
