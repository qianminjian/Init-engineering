"""v2.3-B: channel_versions 增量触发算法.

借鉴 LangGraph Pregel.get_new_channel_versions() (pregel/main.py:1140, 1736-1740).
简化: 比较 old vs new versions dict, 返回本轮被修改的 channel 名 set.

Phase 2.3-B 用例: Loop 引擎每步调用 get_new_channel_versions(state.channel_versions, prev_versions)
→ 返回被修改的 channel 集合 → 驱动下游任务触发.
"""

from __future__ import annotations


def get_new_channel_versions(
    prev_versions: dict[str, int], current_versions: dict[str, int]
) -> set[str]:
    """返回本轮 (round/step) 被修改的 channel 名集合.

    Args:
        prev_versions: 上一轮的 channel_versions dict (本轮初基线)
        current_versions: 本轮末的 channel_versions dict (LoopState.channel_versions)

    Returns:
        set[str]: 被修改 (新增 / 删除 / version 累加) 的 channel 名

    算法 (LangGraph pregel/main.py:1736-1740 简化):
        1. 遍历 current_versions → 若 version > prev (或 prev 缺失) → 加入 modified
        2. 遍历 prev_versions → 若 key 不在 current 中 → 视为删除, 加入 modified
    """
    modified: set[str] = set()

    # 1. 当前 versions 中所有 key: 若 version 累加或新增, 视为修改
    for name, ver in current_versions.items():
        prev_ver = prev_versions.get(name, 0)
        if ver > prev_ver:
            modified.add(name)

    # 2. prev 中存在但 current 中不存在的 key → 视为删除/重置
    for name in prev_versions:
        if name not in current_versions:
            modified.add(name)

    return modified


__all__ = ["get_new_channel_versions"]