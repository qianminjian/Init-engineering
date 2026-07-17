"""ClickPromptBackend — click 实现的 PromptBackend, 供 CLI 层注入 init 核心。

用法:
    from init_engineering.cli._click_backend import ClickPromptBackend
    from init_engineering.init._shared.prompt_backend import BasicPromptBackend

    backend = ClickPromptBackend() if sys.stdout.isatty() else BasicPromptBackend()
    worker = InitWorker(..., prompt_backend=backend)
"""

from __future__ import annotations

from typing import Any

import click

from init_engineering.init._shared.prompt_backend import UserAbort


class ClickPromptBackend:
    """PromptBackend 的 click 实现 — 提供颜色、choice 类型、Abort 处理。"""

    def echo(self, message: str, *, err: bool = False) -> None:
        click.echo(message, err=err)

    def prompt(
        self,
        text: str,
        *,
        default: Any = None,
        type: Any = None,
        show_default: bool = True,
        value_proc: Any = None,
    ) -> Any:
        kwargs: dict[str, Any] = {"default": default, "show_default": show_default}
        if type is not None:
            kwargs["type"] = type
        if value_proc is not None:
            kwargs["value_proc"] = value_proc
        try:
            return click.prompt(text, **kwargs)
        except click.exceptions.Abort:
            raise UserAbort() from None

    def hide_input(self, text: str, *, default: str = "") -> str:
        try:
            return click.prompt(text, default=default, hide_input=True)
        except click.exceptions.Abort:
            raise UserAbort() from None

    def confirm(self, text: str, *, default: bool = False) -> bool:
        try:
            return click.confirm(text, default=default)
        except click.exceptions.Abort:
            raise UserAbort() from None
