"""_LazyExternalDict — 外部数据懒加载 + sandbox 校验.

从 init/answers.py 拆分 (code review 2026-07-04):
answers.py 379 行超 300 行约束, 拆出 external_data 相关类型 + 加载 helper.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from ._shared.path_utils import is_path_under_any_root


def _load_external_file(
    file_path: Path,
    effective_roots: list[Path],
    var_key: str = "",
) -> Any:
    """P2-9: 共享 external_data 文件加载 + sandbox 校验.

    Args:
        file_path: 外部数据文件路径
        effective_roots: 已应用的 sandbox roots (调用方负责 fallback 策略).
                         空列表 = 跳过校验 (caller 显式选择信任).
        var_key: 可选,用于错误信息 (提示哪个模板变量触发了此路径).

    Returns:
        解析后的数据 (dict / list / scalar),文件不存在返回 None.

    Raises:
        ValueError: 路径不在 sandbox 内 (potential template injection).
    """
    if effective_roots and not is_path_under_any_root(file_path, effective_roots):
        key_hint = f" (key='{var_key}')" if var_key else ""
        raise ValueError(
            f"external_data path '{file_path}'{key_hint} "
            f"not under sandbox roots {effective_roots}. "
            f"Refusing to load (potential template injection)."
        )
    if not file_path.exists():
        return None
    if file_path.suffix == ".json":
        return json.loads(file_path.read_text())
    # YAML: safe_load = SafeLoader (禁用任意 Python 对象反序列化)
    return yaml.safe_load(file_path.read_text())


class _LazyExternalDict:
    """Lazy-loading dictionary for external data files.

    Only loads a file when its key is first accessed. 来源：Copier _external_data + LazyDict 模式。
    Supports YAML (.yml/.yaml) and JSON (.json) files.

    v2.5: 加 sandbox_roots — 模板的 external_data 路径必须落在 sandbox_roots
    内 (realpath 双侧校验), 防止恶意模板读 /etc/passwd 等敏感文件.
    """

    def __init__(
        self,
        external_map: dict[str, str],
        sandbox_roots: list[Path] | None = None,
    ) -> None:
        self._external_map = external_map  # {var_name: file_path}
        self._sandbox_roots = sandbox_roots or []
        self._cache: dict[str, Any] = {}

    def __getitem__(self, key: str) -> Any:
        if key not in self._cache:
            # P2-9: 委托给共享 helper — sandbox 校验 + YAML/JSON dispatch
            self._cache[key] = _load_external_file(
                Path(self._external_map[key]),
                effective_roots=self._sandbox_roots,
                var_key=key,
            )
        return self._cache[key]

    def __contains__(self, key: str) -> bool:
        return key in self._external_map

    def __iter__(self):
        return iter(self._external_map)

    def __len__(self) -> int:
        return len(self._external_map)

    def keys(self):
        return self._external_map.keys()

    def items(self):
        for k in self._external_map:
            yield (k, self[k])

    def __repr__(self) -> str:
        return f"_LazyExternalDict(keys={list(self._external_map.keys())})"
