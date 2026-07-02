"""AnswersMap — 6 层优先级答案解析（含 external_data 懒加载）.

来源：Copier _user_data.py:70-133 AnswersMap + _external_data + LazyDict
"""

import os as _os
import sys
from collections import ChainMap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ._shared.path_utils import is_path_under_any_root

# B3: BUILTIN_VARS 改用 MappingProxyType 不可变视图, 防止任何位置污染模块级 dict
# current_year 不再 import 时计算 (跨年 daemon 风险), 改在 AnswersMap.combined() 动态算
from types import MappingProxyType

BUILTIN_VARS: MappingProxyType = MappingProxyType({
    # v1.0: 与 __version__ 同步 — 单版本号策略 (BEACON.md 决策 #5)。
    # 模板中可用 {{ _ae_version }} 判断引擎能力，向后兼容字段名 `_ae_version`。
    "_ae_version": "1.0.0",
    "_folder_name": "",
    "_ae_python": sys.executable,
    "sep": _os.sep,
    "os": {"linux": "linux", "darwin": "macos", "win32": "windows"}.get(sys.platform, "linux"),
})


def _current_year_builtin() -> str:
    """动态计算 current_year — 避免 import 时 frozen 跨年任务."""
    return str(datetime.now().year)


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
            file_path = Path(self._external_map[key])
            if self._sandbox_roots and not is_path_under_any_root(
                file_path, self._sandbox_roots
            ):
                raise ValueError(
                    f"external_data path '{file_path}' (key='{key}') "
                    f"not under sandbox roots {self._sandbox_roots}. "
                    f"Refusing to load (potential template injection)."
                )
            if file_path.exists():
                if file_path.suffix in (".yml", ".yaml"):
                    data = yaml.safe_load(file_path.read_text())
                elif file_path.suffix == ".json":
                    import json

                    data = json.loads(file_path.read_text())
                else:
                    # 非 YAML/JSON 后缀：显式用 SafeLoader，禁用任意 Python 对象反序列化
                    data = yaml.load(file_path.read_text(), Loader=yaml.SafeLoader)
                self._cache[key] = data
            else:
                self._cache[key] = None
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


@dataclass
class AnswersMap:
    """6 层优先级 ChainMap（简化自 Copier 的 8 层）。

    优先级（从高到低）：
    1. cli_overrides  — 命令行 --flag 参数（最高优先级）
    2. interactive    — 交互式问答输入
    3. previous       — 从 .ae-answers.yml 加载的历史答案
    4. defaults       — ae-template.yml 中定义的默认值
    5. builtins       — 内置变量（_ae_version 等，最低优先级）
    6. external       — 外部数据懒加载（来源：Copier _external_data + LazyDict）
    """

    cli_overrides: dict = field(default_factory=dict)
    interactive: dict = field(default_factory=dict)
    previous: dict = field(default_factory=dict)
    defaults: dict = field(default_factory=dict)
    # B3: builtins 拷贝自 MappingProxyType (普通 dict 副本, 可写但不影响模块级 BUILTIN_VARS)
    # current_year 不在这里 — 在 combined() 动态注入
    builtins: dict = field(default_factory=lambda: dict(BUILTIN_VARS))
    external: dict[str, str] = field(default_factory=dict)
    hidden: set = field(default_factory=set)
    # v2.5 P1-S3: external_data 路径沙箱 (防 /etc/passwd 读取)
    external_sandbox_roots: list[str] = field(default_factory=list)
    _external_cache: dict[str, Any] = field(default_factory=dict, init=False)

    def get(self, key: str) -> Any:
        for layer in [
            self.cli_overrides,
            self.interactive,
            self.previous,
            self.defaults,
            self.builtins,
        ]:
            val = layer.get(key)
            if val is not None:
                return val
        if key in self.external:
            return self._load_external(key)
        raise KeyError(key)

    def combined(self) -> dict[str, Any]:
        """全量合并。用于 Jinja2 渲染上下文。外挂 _external_data 键（懒加载）。

        B3: current_year 在此方法调用时动态计算 (跨年 daemon / agent 任务场景)。
        """
        result = dict(
            ChainMap(
                self.cli_overrides,
                self.interactive,
                self.previous,
                self.defaults,
                self.builtins,
            )
        )
        # B3: 动态注入 current_year — 每次调用重新计算, 避免 frozen 在 import 时的年份
        result["current_year"] = _current_year_builtin()
        if self.external:
            result["_external_data"] = _LazyExternalDict(
                self.external,
                sandbox_roots=[
                    Path(r) for r in self.external_sandbox_roots
                ],
            )
        return result

    def _load_external(self, key: str) -> Any:
        """懒加载外部数据文件。来源：Copier _external_data()。

        v2.5 P1-S3: 若 external_sandbox_roots 非空, 验证路径必须在
        sandbox 根内 (realpath 双侧), 否则抛 ValueError 防路径穿越.
        """
        if key not in self._external_cache:
            file_path = Path(self.external[key])
            if self.external_sandbox_roots and not is_path_under_any_root(
                file_path,
                [Path(r) for r in self.external_sandbox_roots],
            ):
                raise ValueError(
                    f"external_data path '{file_path}' (key='{key}') "
                    f"not under sandbox roots {self.external_sandbox_roots}. "
                    f"Refusing to load (potential template injection)."
                )
            if file_path.exists():
                # 显式 SafeLoader — 禁用 YAML 反序列化任意 Python 对象
                data = yaml.load(file_path.read_text(), Loader=yaml.SafeLoader)
                self._external_cache[key] = data
            else:
                self._external_cache[key] = None
        return self._external_cache[key]

    def hide(self, key: str) -> None:
        """标记字段不写入 .ae-answers.yml。来源：Copier AnswersMap.hide()"""
        self.hidden.add(key)

    def save_partial(self, path: Path | None = None) -> Path:
        """保存已收集的部分答案。Ctrl-C 时调用。"""
        if path is None:
            path = Path.home() / ".ae-partial-answers.yml"
        path.write_text(
            yaml.dump(
                {
                    "_meta": {"saved_at": datetime.now().isoformat(), "partial": True},
                    **self.interactive,
                }
            )
        )
        return path

    @classmethod
    def from_answers_file(cls, path: Path) -> "AnswersMap":
        """从 .ae-answers.yml 加载 previous 层。"""
        data = yaml.safe_load(path.read_text()) or {}
        _meta = data.pop("_meta", {})
        return cls(previous=data)

    def to_answers_file(self) -> dict:
        """生成要写入 .ae-answers.yml 的数据。过滤 hidden 和 _ 前缀内部字段。"""
        result = {}
        result["_meta"] = {
            "ae_version": self.builtins.get("_ae_version", "1.0.0"),
            "created_at": datetime.now().isoformat(),
        }
        combined = self.combined()
        for key, value in combined.items():
            if key.startswith("_") or key in self.hidden:
                continue
            if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                result[key] = value
        return result

    def write_to(self, dst: Path) -> None:
        """写入 .ae-answers.yml 到目标路径。"""
        with open(dst, "w") as f:
            yaml.dump(self.to_answers_file(), f, allow_unicode=True)

    def __getitem__(self, key: str) -> Any:
        try:
            return self.get(key)
        except KeyError:
            raise KeyError(key) from None

    def __contains__(self, key: str) -> bool:
        try:
            self.get(key)
            return True
        except KeyError:
            return False
