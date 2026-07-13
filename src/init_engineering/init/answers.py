"""AnswersMap — 6 层优先级答案解析（含 external_data 懒加载）.

来源：Copier _user_data.py:70-133 AnswersMap + _external_data + LazyDict
"""

from __future__ import annotations

import json
import os as _os
import sys
import tempfile
from collections import ChainMap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# B3: BUILTIN_VARS 改用 MappingProxyType 不可变视图, 防止任何位置污染模块级 dict
# current_year 不再 import 时计算 (跨年 daemon 风险), 改在 AnswersMap.combined() 动态算
from types import MappingProxyType
from typing import Any

import yaml

from .. import __version__ as _ae_version
from ._answers_io import (
    _build_answers_data,
    _load_answers_file,
    _save_partial_answers,
    _write_answers_file,
)
from ._shared.path_utils import is_path_under_any_root

BUILTIN_VARS: MappingProxyType = MappingProxyType({
    "_folder_name": "",
    # P2-2: _ae_python/_ae_version 在 combined() 动态计算 (与 current_year 同模式),
    # 避免 import 时硬编码导致跨升级版本号不同步。
    "sep": _os.sep,
    "os": {"linux": "linux", "darwin": "macos", "win32": "windows"}.get(sys.platform, "linux"),
})


def _current_year_builtin() -> str:
    """动态计算 current_year — 避免 import 时 frozen 跨年任务."""
    return str(datetime.now().year)


def _current_month_builtin() -> str:
    """动态计算 current_month — 零填充两位，用于模板日期."""
    return f"{datetime.now().month:02d}"


def _current_day_builtin() -> str:
    """动态计算 current_day — 零填充两位，用于模板日期."""
    return f"{datetime.now().day:02d}"


def _python_executable_builtin() -> str:
    """P2-2: 动态取 sys.executable — 避免 import 时冻结.

    场景: 进程内 Python 升级 (如 uv pip install --python 重定向) 后,
    import 阶段的 sys.executable 已过时. combined() 每次重读确保最新.
    """
    return sys.executable


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

    _MISSING = object()

    def get(self, key: str, default: Any = _MISSING) -> Any:
        """按优先级链查找变量：cli → interactive → previous → defaults → builtins → external。

        行为与 dict.get() 一致：未找到时返回 default，default 未传时返回 None。

        ⚠ 隐式 IO: external 层 key 会触发 _load_external() 磁盘读取。

        Args:
            key: 变量名
            default: 未找到时返回此值（默认 None）。
        """
        try:
            for layer in [
                self.cli_overrides,
                self.interactive,
                self.previous,
                self.defaults,
                self.builtins,
            ]:
                if key in layer:
                    val = layer[key]
                    if val is not None:
                        return val
                    # key 存在但值为 None: 返回 None, 不继续查低优先级层
                    return None
            if key in self.external:
                return self._load_external(key)
            raise KeyError(key)
        except KeyError:
            if default is not self._MISSING:
                return default
            return None

    def combined(self, now: datetime | None = None) -> dict[str, Any]:
        """全量合并。用于 Jinja2 渲染上下文。外挂 _external_data 键（懒加载）。

        B3: current_year 在此方法调用时动态计算 (跨年 daemon / agent 任务场景)。
        P2-2: _ae_python 同模式 — 避免 import 时 frozen, 跨进程 Python 升级后失效。
        now: 可注入时钟 — 测试 freeze time 时传入, 默认当前时间。
        """
        dt = now or datetime.now()
        result = dict(
            ChainMap(
                self.cli_overrides,
                self.interactive,
                self.previous,
                self.defaults,
                self.builtins,
            )
        )
        # B3: 动态注入日期变量 — 每次调用重新计算, 避免 frozen 在 import 时
        result["current_year"] = str(dt.year)
        result["current_month"] = f"{dt.month:02d}"
        result["current_day"] = f"{dt.day:02d}"
        # P2-2: 动态注入 _ae_python — 同 current_year 模式, 防止跨升级失效
        result["_ae_python"] = _python_executable_builtin()
        # P2-10: _ae_version — 与 __version__ 同步, 避免硬编码 (IN-09: 已提升到模块级)
        result["_ae_version"] = _ae_version
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

        PR#4 P1-5 安全加固: external_sandbox_roots 为空时 fallback 到
        [cwd, home, tempdir] 作为最小安全边界. 之前完全跳过检查会让攻击者
        通过 external_data 读 ~/.ssh/ /etc/passwd 等敏感文件.
        tempfile.gettempdir() 是必要的 — 测试与 install hook 常把临时文件
        放这里, 不纳入会让所有 tmpfile-based fixture 报路径穿越.

        P2-9: 委托 _load_external_file — 共享 sandbox 校验 + YAML/JSON dispatch.
        """
        if key not in self._external_cache:
            # PR#4 P1-5: 默认 fallback, 永不跳过检查
            effective_roots = (
                [Path(r) for r in self.external_sandbox_roots]
                if self.external_sandbox_roots
                else [Path.cwd(), Path.home(), Path(tempfile.gettempdir())]
            )
            self._external_cache[key] = _load_external_file(
                Path(self.external[key]),
                effective_roots=effective_roots,
                var_key=key,
            )
        return self._external_cache[key]

    def save_partial(self, path: Path | None = None) -> Path:
        """保存已收集的部分答案。Ctrl-C 时调用。"""
        if path is None:
            path = Path.home() / ".ae-partial-answers.yml"
        return _save_partial_answers(self.interactive, path)

    @classmethod
    def from_answers_file(cls, path: Path) -> AnswersMap:
        """从 .ae-answers.yml 加载 previous 层。

        SE-P1-2: 来源校验 — 拒绝 _meta.ae_version 与当前引擎主版本不兼容的
        文件 (防恶意/损坏的 answers 注入)。

        Raises:
            ValidationError: 文件无法读取或格式错误。
        """
        from .errors import ValidationError

        try:
            return cls(previous=_load_answers_file(path))
        except OSError as e:
            raise ValidationError(
                f"无法读取 answers 文件 {path}: {e}",
                field_name="answers_file",
            ) from e
        except ValueError as e:
            raise ValidationError(
                f"answers 文件 {path} 格式或版本不兼容: {e}",
                field_name="answers_file",
            ) from e

    def to_answers_file(self) -> dict:
        """生成要写入 .ae-answers.yml 的数据。过滤 hidden 和 _ 前缀内部字段。"""
        return _build_answers_data(self.combined(), self.hidden)

    def write_to(self, dst: Path) -> None:
        """写入 .ae-answers.yml 到目标路径。

        Raises:
            OSError: 写入失败（目录权限/磁盘满等）。
        """
        _write_answers_file(self.to_answers_file(), dst)

    def __getitem__(self, key: str) -> Any:
        value = self.get(key)
        if value is None and key not in self:
            raise KeyError(
                f"'{key}' 不在 answers 中。请确认该变量已在 ae-template.yml 的 questions "
                f"中定义，或在 CLI 中通过对应 flag 提供。"
            ) from None
        return value

    def __contains__(self, key: str) -> bool:
        """检查 key 是否在任一优先级层中。

        ⚠ 隐式 IO: external 层 key 会触发 _load_external() 磁盘读取。
        对性能敏感的热路径应优先检查内层 (in cli_overrides/interactive/previous/defaults/builtins)。
        """
        for layer in [
            self.cli_overrides,
            self.interactive,
            self.previous,
            self.defaults,
            self.builtins,
        ]:
            if key in layer:
                return True
        return key in self.external


# ─── external_data 懒加载 (从 _lazy_external.py 折叠) ──────────


def _load_external_file(
    file_path: Path,
    effective_roots: list[Path],
    var_key: str = "",
) -> Any:
    """共享 external_data 文件加载 + sandbox 校验."""
    if effective_roots and not is_path_under_any_root(file_path, effective_roots):
        key_hint = f" (key='{var_key}')" if var_key else ""
        raise ValueError(
            f"external_data path '{file_path}'{key_hint} "
            f"not under sandbox roots {effective_roots}."
        )
    if not file_path.exists():
        return None
    if file_path.suffix == ".json":
        return json.loads(file_path.read_text(encoding="utf-8"))
    return yaml.safe_load(file_path.read_text(encoding="utf-8"))


class _LazyExternalDict:
    """Lazy-loading dictionary for external data files.

    来源：Copier _external_data + LazyDict 模式。
    Supports YAML (.yml/.yaml) and JSON (.json) files.
    """

    def __init__(
        self,
        external_map: dict[str, str],
        sandbox_roots: list[Path] | None = None,
    ) -> None:
        import tempfile

        self._external_map = external_map
        # PR#4 P1-5 fallback: 与 _load_external() 一致，sandbox_roots 为空时
        # 用 [cwd, home, tempdir] 作为最小安全边界，防止路径穿越。
        self._sandbox_roots = sandbox_roots or [
            Path.cwd(), Path.home(), Path(tempfile.gettempdir())
        ]
        self._cache: dict[str, Any] = {}

    def __getitem__(self, key: str) -> Any:
        if key not in self._cache:
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
