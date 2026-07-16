"""Skill 指令解析 — _parse_prompt().

将结构化命令字符串解析为 (action, project_path, options) 三元组。
"""

from __future__ import annotations

import re


def _parse_options_from_args(args_str: str, options: dict) -> str | None:
    """从参数字符串中提取 --key val 选项，返回未消费的 project_path。

    副作用：修改 options dict，将解析出的选项写入。
    返回值：剩余的第一个非选项 token 作为 project_path，无则返回 None。
    """
    consumed_indices: set[int] = set()
    parts = args_str.split()

    i = 0
    while i < len(parts):
        if parts[i].startswith("--"):
            token = parts[i][2:]
            consumed_indices.add(i)
            if "=" in token:
                key, val = token.split("=", 1)
                options[key] = val
            elif i + 1 < len(parts) and not parts[i + 1].startswith("--"):
                options[token] = parts[i + 1]
                consumed_indices.add(i + 1)
                i += 1
            else:
                options[token] = "true"
        i += 1

    for idx, part in enumerate(parts):
        if idx not in consumed_indices:
            return part
    return None


def _parse_prompt(prompt: str) -> tuple[str, str | None, dict]:
    """解析 prompt 为 action/project_path/options。

    解析策略（按优先级）：
    1. 匹配 "detect <path>" → detect action
    2. 匹配 "analyze <path>" → analyze action
    3. 匹配 "init <args>" → 先检查 --analyze 子模式（路由到 analyze），
       再扫描 --key value 选项标记消费的 token，剩余第一个未消费 token 为 project_path

    支持的格式:
        "init my-project --type app-service"
        "init /path/to/project --type library"
        "analyze /path/to/project"
        "analyze ."
        "detect ."
        "init my-project"
    """
    prompt = prompt.strip()

    # list-types (no args)
    if re.match(r"^list-types$", prompt):
        return ("list-types", None, {})

    # list-templates [--type <type>]
    lt_match = re.match(r"^list-templates(?:\s+--type\s+(\S+))?$", prompt)
    if lt_match:
        opts = {}
        if lt_match.group(1):
            opts["type"] = lt_match.group(1)
        return ("list-templates", None, opts)

    # detect
    detect_match = re.match(r"^detect\s+(.+)$", prompt)
    if detect_match:
        return ("detect", detect_match.group(1).strip(), {})

    # analyze
    analyze_match = re.match(r"^(?:analyze|analyse)\s+(.+)$", prompt)
    if analyze_match:
        args_str = analyze_match.group(1).strip()
        options = {}
        project_path = _parse_options_from_args(args_str, options)
        return ("analyze", project_path, options)

    # init (支持 --analyze 子模式)
    init_match = re.match(r"^init\s+(.+)$", prompt)
    if init_match:
        args_str = init_match.group(1).strip()
        options: dict = {}
        parts = args_str.split()

        # --analyze 特殊处理: 将 init --analyze <path> 路由到分析模式
        if "--analyze" in parts:
            idx = parts.index("--analyze")
            project_path = parts[idx + 1] if idx + 1 < len(parts) and not parts[idx + 1].startswith("--") else "."
            return ("analyze", project_path, options)

        project_path = _parse_options_from_args(args_str, options)
        return ("init", project_path, options)

    return ("unknown", None, {})
