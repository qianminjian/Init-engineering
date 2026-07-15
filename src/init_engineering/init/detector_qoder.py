"""Qoder/Repowiki 隐藏目录分析器 — 从 AI 生成的知识库提取项目元数据。

触发条件：--include-hidden 且 .qoder/repowiki/ 存在。

v5.6 重构：单一 analyze_qoder_repowiki() 拆为 5 个子函数，覆盖 4 个数据源：
  _extract_qoder_index()         → _index.yaml (模块列表)
  _extract_qoder_tech_stack()    → 技术栈与依赖.md (技术栈摘要)
  _extract_qoder_module_details()→ 核心模块详解/*.md (模块概述)
  _extract_qoder_metadata()      → repowiki-metadata.json (知识图谱)
  _extract_qoder_quickstart()    → 快速开始.md (构建运行步骤)
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import yaml

_logger = logging.getLogger(__name__)

# ── Path constants ──────────────────────────────────────────────────────

_REPOWIKI_ROOT = ".qoder/repowiki"
_INDEX_YAML_REL = f"{_REPOWIKI_ROOT}/knowledge/zh/_index.yaml"
_TECH_STACK_MD_REL = f"{_REPOWIKI_ROOT}/zh/content/技术栈与依赖.md"
_MODULE_DETAIL_DIR_REL = f"{_REPOWIKI_ROOT}/zh/content/核心模块详解"
_QUICKSTART_MD_REL = f"{_REPOWIKI_ROOT}/zh/content/项目概述/快速开始.md"
_METADATA_JSON_REL = f"{_REPOWIKI_ROOT}/zh/meta/repowiki-metadata.json"
_OVERVIEW_MD_REL = f"{_REPOWIKI_ROOT}/knowledge/zh/{{dir_name}}/概述.md"


def analyze_qoder_repowiki(dst_path: Path) -> dict | None:
    """从 .qoder/repowiki 提取项目元数据（4 数据源聚合）。

    Returns:
        dict with keys: project_title, project_description, modules,
        module_count, has_qoder, tech_stack_summary, module_details,
        module_relations, quickstart, has_quickstart.
        若未找到 _index.yaml 则返回 None。
    """
    index_path = dst_path / _INDEX_YAML_REL
    if not index_path.exists():
        return None

    try:
        index_data = _extract_qoder_index(dst_path)
    except Exception:
        _logger.debug("_index.yaml 解析失败", exc_info=True)
        return None

    if index_data is None:
        return None

    result: dict = {**index_data, "has_qoder": True}

    # 技术栈摘要
    tech_stack = _extract_qoder_tech_stack(dst_path)
    if tech_stack:
        result["tech_stack_summary"] = tech_stack

    # 模块详细信息
    module_details = _extract_qoder_module_details(dst_path, result.get("modules", []))
    if module_details:
        result["module_details"] = module_details

    # 模块关系（从 _index.yaml depends_on 聚合）
    relations = _build_module_relations(result.get("modules", []))
    if relations:
        result["module_relations"] = relations

    # 快速开始
    quickstart = _extract_qoder_quickstart(dst_path)
    if quickstart:
        result["quickstart"] = quickstart
        result["has_quickstart"] = True
    else:
        result["has_quickstart"] = False

    # repowiki 元数据（knowledge graph 简化摘要）
    metadata = _extract_qoder_metadata(dst_path)
    if metadata:
        result["repowiki_metadata"] = metadata

    return result


# ── Sub-extractors ──────────────────────────────────────────────────────


def _extract_qoder_index(dst_path: Path) -> dict | None:
    """解析 _index.yaml — 提取模块列表 + 根模块元数据。

    Returns:
        dict with: project_title, project_description, modules(list of dict),
        module_count. None if file missing or invalid.
    """
    index_path = dst_path / _INDEX_YAML_REL
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

        # Root module (key == "") provides project-level metadata
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
    }


def _extract_qoder_tech_stack(dst_path: Path) -> str | None:
    """解析 技术栈与依赖.md — 提取技术栈文本摘要。

    提取策略：取 ## 引言 后第一个非空段落作为技术栈摘要，
    排除 cite/mermaid 代码块，截断不超过 500 字符。
    """
    tech_path = dst_path / _TECH_STACK_MD_REL
    if not tech_path.exists():
        return None

    try:
        text = tech_path.read_text(encoding="utf-8")
    except OSError:
        _logger.debug("无法读取技术栈与依赖.md")
        return None

    # 定位 ## 引言 后的第一个有意义段落
    intro_match = re.search(r'##\s+引言\s*\n', text)
    if not intro_match:
        return None

    after_intro = text[intro_match.end():]

    # 跳过 cite 块和 mermaid 块，提取第一个实际段落
    in_block = False
    lines = []
    for line in after_intro.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("<cite>") or stripped == "</cite>":
            in_block = not in_block if stripped.startswith("```") else (stripped == "<cite>")
            if lines:
                break  # end of first paragraph after block
            continue
        if in_block:
            continue
        if stripped.startswith("##") and lines:
            break  # next section
        if stripped.startswith("![") or stripped.startswith("图表来源") or stripped.startswith("章节来源"):
            continue
        if stripped:
            lines.append(stripped)

    if not lines:
        return None

    summary = " ".join(lines)
    if len(summary) > 500:
        summary = summary[:497] + "..."
    return summary


def _extract_qoder_module_details(dst_path: Path, modules: list[dict]) -> list[dict] | None:
    """遍历 核心模块详解/*.md — 提取每个模块的概述。

    文件命名约定：{模块标题} ({模块key}).md
    提取策略：取 ## 简介 后第一个非空段落。
    """
    detail_dir = dst_path / _MODULE_DETAIL_DIR_REL
    if not detail_dir.exists():
        return None

    # Build module key → title lookup
    mod_info: dict[str, str] = {}
    for m in modules:
        if m.get("key") and m["key"] != "":
            mod_info[m["key"]] = m.get("title", "")

    details = []
    for mod_key, mod_title in mod_info.items():
        # Try known naming pattern: {title} ({key}).md
        candidate = detail_dir / f"{mod_title} ({mod_key}).md"
        if not candidate.exists():
            # qoder 使用 - 而非 _ 分隔模块 key（如 tmp-boot 对应 tmp_boot）
            norm_key = mod_key.replace("_", "-")
            candidate = detail_dir / f"{mod_title} ({norm_key}).md"
        if not candidate.exists():
            # Fallback: glob for files containing either key variant
            candidates = list(detail_dir.glob(f"*({mod_key}).md"))
            if not candidates:
                candidates = list(detail_dir.glob(f"*({norm_key}).md"))
            if candidates:
                candidate = candidates[0]
            else:
                continue

        overview = _extract_section_paragraph(candidate, "简介")
        details.append({
            "key": mod_key,
            "title": mod_title,
            "overview": overview or "",
        })

    return details if details else None


def _extract_qoder_metadata(dst_path: Path) -> dict | None:
    """解析 repowiki-metadata.json — 提取简化知识图谱摘要。

    只提取关键统计信息，避免加载 >600KB 完整 JSON。
    """
    meta_path = dst_path / _METADATA_JSON_REL
    if not meta_path.exists():
        return None

    try:
        with open(meta_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        _logger.debug("repowiki-metadata.json 解析失败", exc_info=True)
        return None

    wiki_items = data.get("wiki_items", [])
    relations = data.get("knowledge_relations", [])

    return {
        "total_wiki_pages": len(wiki_items),
        "total_relations": len(relations),
        "wiki_catalog_count": len(data.get("wiki_catalogs", [])),
    }


def _extract_qoder_quickstart(dst_path: Path) -> str | None:
    """解析 快速开始.md — 提取构建/运行步骤摘要。

    提取策略：取环境搭建/项目编译/启动服务等关键段落的文本。
    """
    qs_path = dst_path / _QUICKSTART_MD_REL
    if not qs_path.exists():
        return None

    try:
        text = qs_path.read_text(encoding="utf-8")
    except OSError:
        _logger.debug("无法读取快速开始.md")
        return None

    # qoder 实际使用的段落标题（可能因项目而异，按优先级试）
    target_sections = [
        "简介",
        "环境搭建与准备",
        "环境要求",
        "项目克隆与编译",
        "构建",
        "数据库初始化",
        "启动与停止服务",
        "运行",
        "部署",
    ]

    sections: list[str] = []
    for sec in target_sections:
        content = _extract_section_paragraph(qs_path, sec)
        if content:
            sections.append(f"{sec}: {content}")
        if len(sections) >= 3:  # 最多取 3 个段落
            break

    if not sections:
        # 最后尝试：取 # 快速开始 后的第一段
        h1_match = re.search(r'#\s+快速开始\s*\n', text)
        if h1_match:
            after_h1 = text[h1_match.end():]
            paragraph = _extract_first_paragraph(after_h1)
            if paragraph:
                return paragraph[:500]

        return None

    result = "\n".join(sections)
    if len(result) > 600:
        result = result[:597] + "..."
    return result


# ── Helpers ─────────────────────────────────────────────────────────────


def _extract_section_paragraph(file_path: Path, section_name: str) -> str | None:
    """从 Markdown 文件中提取指定 section 后的第一个非空非代码段落。"""
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return None

    pattern = rf'##\s+{re.escape(section_name)}\s*\n'
    match = re.search(pattern, text)
    if not match:
        return None

    after_section = text[match.end():]

    in_block = False
    lines = []
    for line in after_section.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_block = not in_block
            if lines:
                break
            continue
        if in_block:
            continue
        if stripped.startswith("<cite>") or stripped == "</cite>":
            continue
        if stripped.startswith("##") and lines:
            break
        if stripped.startswith("![") or stripped.startswith("图表来源") or stripped.startswith("章节来源"):
            continue
        if stripped.startswith("1.") or stripped.startswith("- ") or stripped.startswith("* "):
            lines.append(stripped)
            continue
        if stripped:
            lines.append(stripped)

    if not lines:
        return None

    result = " ".join(lines)
    if len(result) > 300:
        result = result[:297] + "..."
    return result


def _extract_first_paragraph(text: str) -> str | None:
    """提取文本中的第一个非空非代码段落。"""
    in_block = False
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_block = not in_block
            if lines:
                break
            continue
        if in_block:
            continue
        if stripped.startswith("<cite>") or stripped == "</cite>":
            continue
        if stripped.startswith("#") or stripped.startswith("!["):
            continue
        if stripped.startswith("图表来源") or stripped.startswith("章节来源"):
            continue
        if stripped:
            lines.append(stripped)
        elif lines:
            break
    if not lines:
        return None
    result = " ".join(lines)
    if len(result) > 400:
        result = result[:397] + "..."
    return result


def _build_module_relations(modules: list[dict]) -> list[dict] | None:
    """从 _index.yaml modules 的 depends_on/related_to 聚合模块关系。"""
    relations = []
    for m in modules:
        key = m.get("key", "")
        if key == "":
            continue
        deps = m.get("depends_on", [])
        rels = m.get("related_to", [])
        if deps or rels:
            relations.append({
                "module": key,
                "title": m.get("title", ""),
                "depends_on": deps,
                "related_to": rels,
            })
    return relations if relations else None
