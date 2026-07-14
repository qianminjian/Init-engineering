"""Skill 指令解析 — _parse_prompt().

将结构化命令字符串解析为 (action, project_path, options) 三元组。
"""

from __future__ import annotations

import re


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

    # detect
    detect_match = re.match(r"^detect\s+(.+)$", prompt)
    if detect_match:
        return ("detect", detect_match.group(1).strip(), {})

    # analyze
    analyze_match = re.match(r"^(?:analyze|analyse)\s+(.+)$", prompt)
    if analyze_match:
        return ("analyze", analyze_match.group(1).strip(), {})

    # init (支持 --analyze 子模式)
    init_match = re.match(r"^init\s+(.+)$", prompt)
    if init_match:
        args_str = init_match.group(1).strip()
        options = {}
        project_path = None

        # 解析选项 — 先收集所有 --key 及其值, 剩余 token 为 project_path
        consumed_indices: set[int] = set()
        parts = args_str.split()

        # --analyze 特殊处理: 将 init --analyze <path> 路由到分析模式
        if "--analyze" in parts:
            idx = parts.index("--analyze")
            project_path = parts[idx + 1] if idx + 1 < len(parts) else "."
            return ("analyze", project_path, options)

        # 解析选项: --key val → options[key] = val, 同时标记 consumed_indices
        i = 0
        while i < len(parts):
            if parts[i].startswith("--"):
                key = parts[i][2:]  # strip leading --
                consumed_indices.add(i)
                if i + 1 < len(parts) and not parts[i + 1].startswith("--"):
                    options[key] = parts[i + 1]
                    consumed_indices.add(i + 1)
                    i += 1
                else:
                    options[key] = "true"
            i += 1

        # 取第一个未消费的非 -- token 为 project_path
        for i, part in enumerate(parts):
            if i not in consumed_indices:
                project_path = part
                break

        return ("init", project_path, options)

    return ("unknown", None, {})
