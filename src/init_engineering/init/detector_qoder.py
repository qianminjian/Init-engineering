"""Qoder/Repowiki 隐藏目录分析器 — 从 AI 生成的知识库提取项目元数据。

触发条件：--include-hidden 且 .qoder/repowiki/knowledge/ 存在。
提取信息：项目描述、模块结构、技术栈补充。
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

_logger = logging.getLogger(__name__)

_INDEX_YAML_REL = ".qoder/repowiki/knowledge/zh/_index.yaml"
_OVERVIEW_MD_REL = ".qoder/repowiki/knowledge/zh/{dir_name}/概述.md"


def analyze_qoder_repowiki(dst_path: Path) -> dict | None:
    """从 .qoder/repowiki 提取项目元数据。

    Returns:
        dict with keys: project_title, project_description, modules(list of dict),
        module_count, has_qoder. 若未找到 repowiki 则返回 None。
    """
    index_path = dst_path / _INDEX_YAML_REL
    if not index_path.exists():
        return None

    try:
        raw = index_path.read_text(encoding="utf-8")
        index = yaml.safe_load(raw)
    except (OSError, yaml.YAMLError) as e:
        _logger.debug("无法解析 _index.yaml: %s", e)
        return None

    if not isinstance(index, dict) or "modules" not in index:
        return None

    raw_modules: dict = index.get("modules", {})
    if not raw_modules:
        return None

    modules = []
    project_title = ""
    project_description = ""

    for mod_key, mod_data in raw_modules.items():
        if not isinstance(mod_data, dict):
            continue
        title = mod_data.get("title", "")
        dir_name = mod_data.get("dir_name", "")
        scope = mod_data.get("scope", [])
        related_to = mod_data.get("related_to", [])
        depends_on = mod_data.get("depends_on", [])

        modules.append({
            "key": mod_key,
            "title": title,
            "dir_name": dir_name,
            "scope": scope if isinstance(scope, list) else [],
            "related_to": [r.get("path", r) if isinstance(r, dict) else r
                           for r in related_to] if isinstance(related_to, list) else [],
            "depends_on": depends_on if isinstance(depends_on, list) else [],
        })

        # Root module has key "" — project-level metadata
        if mod_key == "" and title:
            project_title = title
            overview_path = dst_path / _OVERVIEW_MD_REL.format(dir_name=dir_name)
            if overview_path.exists():
                try:
                    text = overview_path.read_text(encoding="utf-8").strip()
                    if text:
                        project_description = text
                except OSError:
                    _logger.debug("无法读取概述: %s", overview_path)

    real_modules = [m for m in modules if m["key"] != ""]
    return {
        "project_title": project_title,
        "project_description": project_description,
        "modules": modules,
        "module_count": len(real_modules),
        "has_qoder": True,
    }
