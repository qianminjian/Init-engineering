"""tests for config/settings.py — _int_env / _float_env error paths."""

from __future__ import annotations

import os

import pytest

from auto_engineering.config.settings import _float_env, _int_env


class TestIntEnv:
    """_int_env — ValueError 路径."""

    def test_valid_int_returns_int(self, monkeypatch):
        monkeypatch.setenv("TEST_INT", "42")
        assert _int_env("TEST_INT", 10) == 42

    def test_missing_env_returns_default(self, monkeypatch):
        monkeypatch.delenv("TEST_INT_MISSING", raising=False)
        assert _int_env("TEST_INT_MISSING", 99) == 99

    def test_empty_env_returns_default(self, monkeypatch):
        monkeypatch.setenv("TEST_INT_EMPTY", "")
        assert _int_env("TEST_INT_EMPTY", 7) == 7

    def test_invalid_int_raises_value_error(self, monkeypatch):
        """非法整数环境变量 → ValueError."""
        monkeypatch.setenv("TEST_INVALID_INT", "not-a-number")
        with pytest.raises(ValueError) as exc_info:
            _int_env("TEST_INVALID_INT", 10)
        assert "TEST_INVALID_INT" in str(exc_info.value)


class TestFloatEnv:
    """_float_env — ValueError 路径."""

    def test_valid_float_returns_float(self, monkeypatch):
        monkeypatch.setenv("TEST_FLOAT", "3.14")
        assert _float_env("TEST_FLOAT", 1.0) == 3.14

    def test_missing_env_returns_default(self, monkeypatch):
        monkeypatch.delenv("TEST_FLOAT_MISSING", raising=False)
        assert _float_env("TEST_FLOAT_MISSING", 2.5) == 2.5

    def test_empty_env_returns_default(self, monkeypatch):
        monkeypatch.setenv("TEST_FLOAT_EMPTY", "")
        assert _float_env("TEST_FLOAT_EMPTY", 2.5) == 2.5

    def test_invalid_float_raises_value_error(self, monkeypatch):
        """非法浮点数环境变量 → ValueError."""
        monkeypatch.setenv("TEST_INVALID_FLOAT", "not-a-float")
        with pytest.raises(ValueError) as exc_info:
            _float_env("TEST_INVALID_FLOAT", 1.0)
        assert "TEST_INVALID_FLOAT" in str(exc_info.value)


class TestSettingsFromEnv:
    """Settings.from_env() 路径."""

    def test_from_env_with_api_key(self, monkeypatch):
        """有 API key 时正常返回 Settings."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        from auto_engineering.config.settings import Settings
        s = Settings.from_env()
        assert s.anthropic_api_key == "sk-test-key"

    def test_from_env_llm_agent_skips_key_check(self, monkeypatch):
        """CLAUDE_CODE 环境变量存在时跳过 API key 检查."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("CLAUDE_CODE", "true")
        from auto_engineering.config.settings import Settings
        s = Settings.from_env()
        assert s.anthropic_api_key == ""

    def test_from_env_missing_api_key_raises(self, monkeypatch):
        """无 API key 且非 LLM agent 时抛 ValueError."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("CLAUDE_CODE", raising=False)
        from auto_engineering.config.settings import Settings
        with pytest.raises(ValueError) as exc_info:
            Settings.from_env()
        assert "ANTHROPIC_API_KEY" in str(exc_info.value)
