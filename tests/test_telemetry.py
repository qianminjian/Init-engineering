"""telemetry.py 测试 — 匿名遥测模块全覆盖."""

from __future__ import annotations

import json
import os
from unittest.mock import Mock, patch

import pytest

from auto_engineering.telemetry import TelemetryEvent, _is_enabled, send


class TestIsEnabled:
    def test_disabled_by_default(self):
        """默认不启用遥测."""
        assert not _is_enabled()

    def test_enabled_with_1(self, monkeypatch):
        monkeypatch.setenv("AE_TELEMETRY", "1")
        assert _is_enabled()

    def test_enabled_with_true(self, monkeypatch):
        monkeypatch.setenv("AE_TELEMETRY", "true")
        assert _is_enabled()

    def test_enabled_with_yes(self, monkeypatch):
        monkeypatch.setenv("AE_TELEMETRY", "yes")
        assert _is_enabled()

    def test_disabled_with_0(self, monkeypatch):
        monkeypatch.setenv("AE_TELEMETRY", "0")
        assert not _is_enabled()

    def test_disabled_with_false(self, monkeypatch):
        monkeypatch.setenv("AE_TELEMETRY", "false")
        assert not _is_enabled()

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("AE_TELEMETRY", "TRUE")
        assert _is_enabled()


class TestTelemetryEvent:
    def test_default_values(self):
        event = TelemetryEvent()
        assert event.ae_version == ""
        assert event.command == ""
        assert event.success is True
        assert event.duration_ms == 0

    def test_populated_event(self):
        event = TelemetryEvent(
            ae_version="1.0.0",
            command="init",
            project_type="app-service",
            language="python",
            success=True,
            duration_ms=1234,
        )
        assert event.ae_version == "1.0.0"
        assert event.language == "python"
        assert event.duration_ms == 1234

    def test_event_serializable(self):
        event = TelemetryEvent(ae_version="1.0.0", command="init")
        data = json.dumps({"ae_version": event.ae_version, "command": event.command})
        parsed = json.loads(data)
        assert parsed["ae_version"] == "1.0.0"


class TestSend:
    def test_noop_when_disabled(self, monkeypatch):
        monkeypatch.delenv("AE_TELEMETRY", raising=False)
        event = TelemetryEvent()
        # 不应抛出, 也不发送请求
        send(event)
        # python_version/os_name 在 enabled 时才填充
        assert event.python_version == ""
        assert event.os_name == ""

    def test_fills_platform_info_when_enabled(self, monkeypatch):
        monkeypatch.setenv("AE_TELEMETRY", "1")
        event = TelemetryEvent()
        # mock urlopen 避免实际网络请求
        with patch("urllib.request.urlopen", side_effect=Exception("no network")):
            send(event)
        assert event.python_version != ""
        assert event.os_name != ""

    def test_sends_when_enabled(self, monkeypatch):
        monkeypatch.setenv("AE_TELEMETRY", "1")
        event = TelemetryEvent(ae_version="1.0.0", command="status")
        # P2-8: telemetry 改用自定义 opener (ProxyHandler({})) 禁 proxy,
        # 所以 mock 需打 build_opener().open 链路
        mock_opener = Mock()
        with patch("urllib.request.build_opener", return_value=mock_opener):
            send(event)
        mock_opener.open.assert_called_once()

    def test_swallows_network_error(self, monkeypatch):
        monkeypatch.setenv("AE_TELEMETRY", "1")
        event = TelemetryEvent()
        mock_opener = Mock()
        mock_opener.open.side_effect = OSError("network down")
        with patch("urllib.request.build_opener", return_value=mock_opener):
            send(event)  # 不应抛出

    def test_swallows_url_error(self, monkeypatch):
        """F4: URL/network 错误 (URLError 来自真实 urllib) — 应静默吞掉."""
        from urllib.error import URLError
        monkeypatch.setenv("AE_TELEMETRY", "1")
        event = TelemetryEvent()
        mock_opener = Mock()
        mock_opener.open.side_effect = URLError("no internet")
        with patch("urllib.request.build_opener", return_value=mock_opener):
            send(event)  # 不应抛出

    def test_swallows_build_opener_failure(self, monkeypatch):
        """F4: build_opener 本身失败 (极少见, 但 try/except 应覆盖)."""
        monkeypatch.setenv("AE_TELEMETRY", "1")
        event = TelemetryEvent()
        with patch("urllib.request.build_opener", side_effect=ValueError("bad handler")):
            send(event)  # 不应抛出

    def test_swallows_timeout(self, monkeypatch):
        monkeypatch.setenv("AE_TELEMETRY", "1")
        event = TelemetryEvent()
        mock_opener = Mock()
        mock_opener.open.side_effect = TimeoutError("timeout")
        with patch("urllib.request.build_opener", return_value=mock_opener):
            send(event)  # 不应抛出

    def test_swallows_json_error(self, monkeypatch):
        monkeypatch.setenv("AE_TELEMETRY", "1")
        event = TelemetryEvent()
        with patch("json.dumps", side_effect=TypeError("bad data")):
            send(event)  # 不应抛出

    def test_send_payload_is_valid_json(self, monkeypatch):
        monkeypatch.setenv("AE_TELEMETRY", "1")
        event = TelemetryEvent(ae_version="2.0.0", command="init", project_type="cli-tool")
        captured_payload = []

        def capture(req, timeout=None):
            captured_payload.append(req.data)
            return Mock(read=Mock(return_value=b"ok"))

        mock_opener = Mock()
        mock_opener.open.side_effect = capture
        with patch("urllib.request.build_opener", return_value=mock_opener):
            send(event)

        data = json.loads(captured_payload[0])
        assert data["ae_version"] == "2.0.0"
        assert data["project_type"] == "cli-tool"
        assert "python_version" in data
        assert "os_name" in data
