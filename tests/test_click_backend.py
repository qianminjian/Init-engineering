"""ClickPromptBackend 单元测试 — 覆盖 prompt/confirm/echo/hide_input + UserAbort 传导."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import click.testing
import pytest

from init_engineering.init._shared.prompt_backend import UserAbort


class TestClickPromptBackend:
    """ClickPromptBackend 核心方法测试."""

    @pytest.fixture
    def backend(self):
        from init_engineering.cli._click_backend import ClickPromptBackend

        return ClickPromptBackend()

    def test_echo_stdout(self, backend, capsys):
        backend.echo("hello world")
        captured = capsys.readouterr()
        assert "hello world" in captured.out

    def test_echo_stderr(self, backend, capsys):
        backend.echo("error message", err=True)
        captured = capsys.readouterr()
        assert "error message" in captured.err

    def test_prompt_abort_propagates_user_abort(self, backend):
        with patch(
            "click.prompt", side_effect=click.exceptions.Abort()
        ):
            with pytest.raises(UserAbort):
                backend.prompt("question?", default="")

    def test_confirm_default_true(self, backend):
        with patch("click.confirm", return_value=True) as mock_confirm:
            result = backend.confirm("proceed?", default=True)
            assert result is True
            mock_confirm.assert_called_once_with("proceed?", default=True)

    def test_confirm_default_false(self, backend):
        with patch("click.confirm", return_value=False) as mock_confirm:
            result = backend.confirm("proceed?", default=False)
            assert result is False

    def test_confirm_abort_propagates_user_abort(self, backend):
        with patch(
            "click.confirm", side_effect=click.exceptions.Abort()
        ):
            with pytest.raises(UserAbort):
                backend.confirm("proceed?")

    def test_hide_input_returns_value(self, backend):
        with patch("click.prompt", return_value="secret123") as mock_prompt:
            result = backend.hide_input("secret:", default="")
            assert result == "secret123"
            assert mock_prompt.call_args[1]["hide_input"] is True

    def test_hide_input_abort_propagates_user_abort(self, backend):
        with patch(
            "click.prompt", side_effect=click.exceptions.Abort()
        ):
            with pytest.raises(UserAbort):
                backend.hide_input("secret:", default="")

    def test_prompt_respects_type_parameter(self, backend):
        with patch("click.prompt", return_value=42) as mock_prompt:
            result = backend.prompt("number?", type=int, default=0)
            assert result == 42
            assert mock_prompt.call_args[1]["type"] is int

    def test_prompt_value_proc_forwarded(self, backend):
        proc = lambda x: x.strip().lower()
        with patch("click.prompt", return_value="test") as mock_prompt:
            backend.prompt("val?", value_proc=proc)
            assert mock_prompt.call_args[1]["value_proc"] is proc
