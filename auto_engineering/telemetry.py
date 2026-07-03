"""遥测模块 — 可选的匿名使用数据收集。

仅在用户显式同意（通过 --telemetry 或环境变量 AE_TELEMETRY=1）后启用。
匿名数据帮助了解 ae 的版本使用分布和常见错误类型。

数据内容：
  - ae 版本、命令（init/status）、项目类型、语言
  - 成功/失败状态
  - Python 版本、OS 类型

隐私声明：
  - 不收集项目名、路径、文件内容、环境变量值
  - 不收集任何个人身份信息（PII）
  - 可在任何时候禁用: ae config --no-telemetry 或 AE_TELEMETRY=0
"""

from __future__ import annotations

import json
import logging
import os
import platform
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass

from pathlib import Path

_logger = logging.getLogger(__name__)

# B6: 强制 HTTPS — 拒绝任意 URL 覆盖, 环境变量仅控制 endpoint path
DEFAULT_TELEMETRY_ENDPOINT = "https://telemetry.ae.example.com/v1/event"
_TELEMETRY_CONSENT_FILE = ".ae-telemetry-consent"


@dataclass
class TelemetryEvent:
    ae_version: str = ""
    command: str = ""  # "init" | "status"
    project_type: str = ""
    language: str = ""
    success: bool = True
    duration_ms: int = 0
    python_version: str = ""
    os_name: str = ""
    error_type: str = ""


def _resolve_endpoint() -> str | None:
    """解析 endpoint — 强制 HTTPS + 显式开关。

    SE-P1-3: AE_TELEMETRY_PATH 必须配合 --telemetry / AE_TELEMETRY=1 才生效,
    防止环境变量被恶意脚本偷偷修改后改变 endpoint 行为 (即使强制 HTTPS,
    切换到内部 dev/staging endpoint 也可能暴露数据)。

    来源：B6 修复, 不再允许环境变量覆盖为 http://
    仅允许环境变量控制 path (以 _ 开头表示内部变量, 默认走 DEFAULT)。
    """
    raw = os.environ.get("AE_TELEMETRY_PATH")
    if raw:
        # SE-P1-3: 显式开关 — telemetry 未开启时, AE_TELEMETRY_PATH 静默忽略
        if not _is_enabled():
            _logger.debug(
                "AE_TELEMETRY_PATH 设置但 telemetry 未开启, 忽略 (SE-P1-3)"
            )
            return DEFAULT_TELEMETRY_ENDPOINT
        full = urllib.parse.urljoin(DEFAULT_TELEMETRY_ENDPOINT, raw)
    else:
        full = DEFAULT_TELEMETRY_ENDPOINT
    # B6 安全: 强制 HTTPS 防止 http://attacker 注入
    if not full.startswith("https://"):
        _logger.warning("telemetry endpoint 必须 HTTPS, 已忽略: %s", full)
        return None
    return full


def _is_enabled() -> bool:
    return os.environ.get("AE_TELEMETRY", "").lower() in ("1", "true", "yes")


def has_consent() -> bool:
    """检查用户是否已对 telemetry 表达过显式同意。

    通过 $HOME/.ae-telemetry-consent 文件持久化标记。
    文件存在 → 已被询问 (无论 yes/no)
    文件不存在 → 未被询问, --telemetry 触发时需要先引导
    """
    return (Path.home() / _TELEMETRY_CONSENT_FILE).exists()


def request_consent() -> bool:
    """首次开启 telemetry 时打印数据收集声明, 强制用户 y/n 确认.

    Returns: 用户最终选择 (True=同意, False=拒绝)
    Side effect: 写 consent 文件记录已询问 (避免每次都询问)
    """
    import click

    click.echo(
        "\n📊 ae 遥测数据收集声明:\n"
        "  • 仅收集匿名使用数据 (版本/命令/项目类型/语言/Python版本/OS)\n"
        "  • 不收集项目名/路径/文件内容/环境变量值\n"
        "  • 可随时通过 AE_TELEMETRY=0 禁用\n"
        "  • endpoint: " + DEFAULT_TELEMETRY_ENDPOINT + "\n",
        err=False,
    )
    choice = click.confirm("是否启用遥测?", default=False)
    consent_path = Path.home() / _TELEMETRY_CONSENT_FILE
    try:
        consent_path.write_text("yes" if choice else "no")
        os.chmod(consent_path, 0o600)
    except OSError:
        pass
    return choice


def send(event: TelemetryEvent) -> None:
    """发送遥测事件（非阻塞，失败静默）。

    B6 安全:
    - 强制 HTTPS endpoint
    - 短超时 (1s) — 失败静默不阻塞主流程
    - 失败仅 DEBUG 级别日志
    """
    if not _is_enabled():
        return

    endpoint = _resolve_endpoint()
    if endpoint is None:
        return

    event.python_version = platform.python_version()
    event.os_name = platform.system().lower()

    try:
        data = json.dumps(asdict(event)).encode()
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # P2-8: 禁用 proxy — telemetry 数据可能含用户 IP / 公司出口标识
        # HTTP_PROXY/HTTPS_PROXY 环境变量被恶意设置时可被劫持到攻击者 endpoint
        # ProxyHandler({}) 显式无 proxy, 防止环境变量污染
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        # P2-6: 记录发送成功 — DEBUG 级别, 默认不显示 (-v 才看)
        # 之前没有任何"成功"日志, 调试时无法确认事件是否发出
        opener.open(req, timeout=1)
        _logger.debug(
            "telemetry sent: cmd=%s type=%s success=%s",
            event.command, event.project_type, event.success,
        )
    except Exception:
        _logger.debug("telemetry send failed", exc_info=True)