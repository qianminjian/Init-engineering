"""AnswersMap — 6 层优先级答案解析（含 external_data 懒加载）.

来源：Copier _user_data.py:70-133 AnswersMap + _external_data + LazyDict
"""

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

from ._shared.path_utils import is_path_under_any_root

BUILTIN_VARS: MappingProxyType = MappingProxyType({
    # v1.0: 与 __version__ 同步 — 单版本号策略 (BEACON.md 决策 #5)。
    # 模板中可用 {{ _ae_version }} 判断引擎能力，向后兼容字段名 `_ae_version`。
    "_ae_version": "1.0.0",
    "_folder_name": "",
    # P2-2: _ae_python 不再 import 时冻结 — 在 combined() 动态计算 (与 current_year 同模式)
    "sep": _os.sep,
    "os": {"linux": "linux", "darwin": "macos", "win32": "windows"}.get(sys.platform, "linux"),
})


def _current_year_builtin() -> str:
    """动态计算 current_year — 避免 import 时 frozen 跨年任务."""
    return str(datetime.now().year)


def _python_executable_builtin() -> str:
    """P2-2: 动态取 sys.executable — 避免 import 时冻结.

    场景: 进程内 Python 升级 (如 uv pip install --python 重定向) 后,
    import 阶段的 sys.executable 已过时. combined() 每次重读确保最新.
    """
    return sys.executable


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
        P2-2: _ae_python 同模式 — 避免 import 时 frozen, 跨进程 Python 升级后失效。
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
        # P2-2: 动态注入 _ae_python — 同 current_year 模式, 防止跨升级失效
        result["_ae_python"] = _python_executable_builtin()
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

    def hide(self, key: str) -> None:
        """标记字段不写入 .ae-answers.yml。来源：Copier AnswersMap.hide()"""
        self.hidden.add(key)

    def save_partial(self, path: Path | None = None) -> Path:
        """保存已收集的部分答案。Ctrl-C 时调用。

        P2-3: 写文件前显式 chmod 0o600 (仅 owner 可读写) — 答案可能含
        project_name 推断 / 业务描述 / package_manager 等,虽然不直接是
        secret,但尽量收窄可见性。0o600 缺省安全姿态, 同一用户其他进程
        (无 root) 仍可读, 不影响 replay 使用。
        """
        if path is None:
            path = Path.home() / ".ae-partial-answers.yml"
        import os as _os

        old_umask = _os.umask(0o077)
        try:
            path.write_text(
                yaml.dump(
                    {
                        "_meta": {
                            # PR#5 P2-10: 加 UTC tz — 跨时区复用无歧义
                            "saved_at": datetime.now().astimezone().isoformat(),
                            "partial": True,
                        },
                        **self.interactive,
                    }
                )
            )
            _os.chmod(path, 0o600)
        finally:
            _os.umask(old_umask)
        return path

    @classmethod
    def from_answers_file(cls, path: Path) -> "AnswersMap":
        """从 .ae-answers.yml 加载 previous 层。

        SE-P1-2: 来源校验 — 拒绝 _meta.ae_version 与当前引擎主版本不兼容的
        文件 (防恶意/损坏的 answers 注入),并 warning 显示真实来源路径。
        """
        from .. import __version__

        data = yaml.safe_load(path.read_text()) or {}
        if not isinstance(data, dict):
            raise ValueError(
                f"answers 文件 {path} 顶层必须是 mapping, 实际是 {type(data).__name__}"
            )
        _meta = data.pop("_meta", {}) or {}
        if not isinstance(_meta, dict):
            _meta = {}

        # SE-P1-2: 版本兼容性检查 — _meta.ae_version 缺失 → 警告但不拒绝
        # (旧文件可能没有 _meta); 存在但主版本不匹配 → 拒绝加载
        meta_version = _meta.get("ae_version")
        if meta_version:
            try:
                current_major = __version__.split(".")[0]
                file_major = str(meta_version).split(".")[0]
                if file_major != current_major:
                    raise ValueError(
                        f"answers 文件 {path} ae_version='{meta_version}' "
                        f"与当前引擎主版本 '{__version__}' 不兼容。"
                        f"主版本变化时 answers 字段可能不兼容, 拒绝加载以防误用。"
                        f"如确认来源可信, 请删除 _meta.ae_version 后重试。"
                    )
            except (IndexError, AttributeError):
                pass

        # DI-P1-2: schema_version 检查 — _meta.schema_version 是文件格式版本,
        # 必须等于当前支持的 schema 版本 (1)。schema 字段重命名/类型变更时 bump。
        # 缺失 schema_version → 警告但不拒绝 (旧 v1.0 文件无此字段)
        meta_schema = _meta.get("schema_version")
        if meta_schema is not None and meta_schema != 1:
            raise ValueError(
                f"answers 文件 {path} schema_version='{meta_schema}' 不受支持。"
                f"当前引擎仅支持 schema_version=1。"
                f"请升级 ae 或使用旧版本重新生成 answers。"
            )

        return cls(previous=data)

    def to_answers_file(self) -> dict:
        """生成要写入 .ae-answers.yml 的数据。过滤 hidden 和 _ 前缀内部字段。

        DI-P1-2: _meta 新增 schema_version 字段 — 标记 .ae-answers.yml 文件格式
        版本, 与 ae_version (引擎版本) 分离。引擎小版本变化不破坏格式兼容性,
        schema_version 必须显式 bump 才能引入不兼容字段 (如字段重命名/类型变更)。

        P2-11: 敏感字段过滤 — 含 password/secret/token/api_key/private_key
        的字段自动跳过, 防止 .ae-answers.yml 不慎 commit 到 git 后泄露凭据。
        """
        result = {}
        result["_meta"] = {
            "ae_version": self.builtins.get("_ae_version", "1.0.0"),
            "schema_version": 1,  # DI-P1-2: .ae-answers.yml 格式 schema 版本
            # PR#5 P2-10: 加 UTC tz — datetime.now() 无时区信息, 跨时区复用易混淆
            "created_at": datetime.now().astimezone().isoformat(),
        }
        combined = self.combined()
        for key, value in combined.items():
            if key.startswith("_") or key in self.hidden:
                continue
            # P2-11: 敏感字段过滤 — 不写入 .ae-answers.yml
            if _is_sensitive_field(key):
                continue
            if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                result[key] = value
        return result

    def write_to(self, dst: Path) -> None:
        """写入 .ae-answers.yml 到目标路径。

        P2-16: 显式 utf-8 encoding — 防止 Windows GBK 默认编码破坏中文 answers。
        """
        with open(dst, "w", encoding="utf-8") as f:
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


# P2-11: 敏感字段名白名单 (含常见 secret 命名约定, 跨语言通用)
_SENSITIVE_FIELD_PATTERNS = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "access_token", "refresh_token", "private_key", "secret_key",
    "auth", "authorization", "credential", "credentials",
})


def _is_sensitive_field(key: str) -> bool:
    """P2-11: 判断字段名是否暗示敏感数据 (大小写不敏感)."""
    k = key.lower()
    if k in _SENSITIVE_FIELD_PATTERNS:
        return True
    # 含常见 secret 后缀 (e.g. db_password, github_token)
    for suffix in ("_password", "_secret", "_token", "_key", "_credential"):
        if k.endswith(suffix):
            return True
    return False
