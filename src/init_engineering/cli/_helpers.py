"""CLI helpers — 错误脱敏 + 日志配置.

从 cli/__init__.py 拆分 (2026-07-03 深度审计 P2-A):
原文件 427 行超 300 行约束, 拆出 update/status 命令 + helpers
(本模块) + 命令注册到 cli/__init__.py, 三处拆分后均 ≤ 300 行.
"""

from __future__ import annotations

import logging.config
import uuid


def sanitize_error(msg: str) -> str:
    """P2-13: 错误消息脱敏 — 替换常见 secret 模式为 [REDACTED]."""
    import re as _re

    patterns = [
        # 长 token / api key (>=20 字符的 base64/hex)
        (r"(?i)(token|api[_-]?key|secret|password|access[_-]?key)\s*[=:]\s*['\"]?[\w\-\+\\\/\.]{16,}['\"]?",
         r"\1=[REDACTED]"),
        # Bearer token
        (r"(?i)Bearer\s+[\w\-\.]{16,}", "Bearer [REDACTED]"),
        # JWT 风格 (xxx.yyy.zzz)
        (r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", "[REDACTED-JWT]"),
    ]
    for pat, repl in patterns:
        msg = _re.sub(pat, repl, msg)
    return msg


def configure_logging(verbose: bool) -> None:
    """配置 logging — B7: 结构化 + session_id；B9: dictConfig 强制覆盖.

    ⚠ 全局副作用: 调用 logging.config.dictConfig 修改进程级 root logger,
    测试中可能改变其他模块的日志行为。测试后用 reset_logging() 恢复。

    设计：
    - 默认 INFO 级别（plain text）
    - --verbose 升级到 DEBUG
    - 全局注入 ae_session_id (uuid4 前 8 位) 用于日志关联
    - 使用 dictConfig 而非 basicConfig — 避免用户/agent 已有 logger 配置失效。
      调用方（特别是测试）应在完成后调用 reset_logging() 恢复默认配置。
    """
    session_id = uuid.uuid4().hex[:8]
    level = "DEBUG" if verbose else "INFO"

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "format": f"%(asctime)s [%(levelname)s] [ae:{session_id}] [%(name)s] %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            },
        },
        "handlers": {
            "stderr": {
                "class": "logging.StreamHandler",
                "formatter": "structured",
                "stream": "ext://sys.stderr",
            },
        },
        "root": {
            "level": level,
            "handlers": ["stderr"],
        },
    })


def reset_logging() -> None:
    """恢复 logging 到默认配置 — configure_logging() 的反操作。

    用于测试 teardown 或需要撤销 configure_logging() 全局副作用的场景。
    """
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(levelname)s: %(message)s",
            },
        },
        "handlers": {
            "stderr": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stderr",
            },
        },
        "root": {
            "level": "WARNING",
            "handlers": ["stderr"],
        },
    })


