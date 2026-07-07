"""Shared I/O utilities — consumed by both config/ and init/ layers."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

_logger = logging.getLogger(__name__)


def read_yaml(path: Path) -> dict:
    """读取 YAML 文件，返回 dict（文件不存在或为空时返回 {}）。"""
    try:
        data = yaml.safe_load(path.read_text())
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        _logger.debug("yaml file not found, returning {}: %s", path)
        return {}
    except (OSError, yaml.YAMLError):
        _logger.debug("yaml read failed, returning {}: %s", path, exc_info=True)
        return {}
