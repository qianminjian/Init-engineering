"""AnswersMap 文件 I/O — 从 answers.py 拆分以满足 300 行约束。

save_partial / from_answers_file 的完整实现 + write_to / to_answers_file 辅助函数。
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

_logger = logging.getLogger(__name__)

# ─── 敏感字段过滤 (从 _sensitive.py 折叠) ──────────

_SENSITIVE_FIELD_PATTERNS = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "access_token", "refresh_token", "private_key", "secret_key",
    "auth", "authorization", "credential", "credentials",
})


def _is_sensitive_field(key: str) -> bool:
    """判断字段名是否暗示敏感数据（大小写不敏感）。"""
    k = key.lower()
    if k in _SENSITIVE_FIELD_PATTERNS:
        return True
    for suffix in ("_password", "_secret", "_token", "_key", "_credential"):
        if k.endswith(suffix):
            return True
    return False


def _save_partial_answers(interactive: dict, path: Path) -> Path:
    """保存已收集的部分答案。Ctrl-C 时调用。

    P2-3: 写文件前显式 chmod 0o600 (仅 owner 可读写) — 答案可能含
    project_name 推断 / 业务描述 / package_manager 等,虽然不直接是
    secret,但尽量收窄可见性。0o600 缺省安全姿态, 同一用户其他进程
    (无 root) 仍可读, 不影响 replay 使用。
    """
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
                    **interactive,
                }
            ),
            encoding="utf-8",
        )
        _os.chmod(path, 0o600)
    finally:
        _os.umask(old_umask)
    return path


def _load_answers_file(path: Path) -> dict:
    """从 .ae-answers.yml 加载 previous 层数据。

    SE-P1-2: 来源校验 — 拒绝 _meta.ae_version 与当前引擎主版本不兼容的
    文件 (防恶意/损坏的 answers 注入),并 warning 显示真实来源路径。

    Returns:
        解析后的 answers dict（不含 _meta）。

    Raises:
        ValueError: 文件格式/版本不兼容。
        OSError: 文件读取失败（透传给调用方处理）。
    """
    import yaml as _yaml

    from .. import __version__

    raw = _yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        if raw is None:
            raw = {}
        else:
            raise ValueError(
                f"answers 文件 {path} 顶层必须是 mapping, 实际是 {type(raw).__name__}"
            )
    data = dict(raw)
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
        except AttributeError:
            _logger.debug(
                "version check skipped: __version__ or meta_version parse failed",
                exc_info=True,
            )

    # DI-P1-2: schema_version 检查 — _meta.schema_version 是文件格式版本,
    # 必须等于当前支持的 schema 版本 (1)。schema 字段重命名/类型变更时 bump。
    meta_schema = _meta.get("schema_version")
    if meta_schema is not None and meta_schema != 1:
        raise ValueError(
            f"answers 文件 {path} schema_version='{meta_schema}' 不受支持。"
            f"当前引擎仅支持 schema_version=1。"
            f"请升级 ae 或使用旧版本重新生成 answers。"
        )

    return data


def _build_answers_data(combined: dict, hidden: set) -> dict:
    """生成要写入 .ae-answers.yml 的数据。过滤 hidden 和 _ 前缀内部字段。

    DI-P1-2: _meta 新增 schema_version 字段 — 标记 .ae-answers.yml 文件格式
    版本, 与 ae_version (引擎版本) 分离。引擎小版本变化不破坏格式兼容性,
    schema_version 必须显式 bump 才能引入不兼容字段 (如字段重命名/类型变更)。

    P2-11: 敏感字段过滤 — 含 password/secret/token/api_key/private_key
    的字段自动跳过, 防止 .ae-answers.yml 不慎 commit 到 git 后泄露凭据。
    """
    from .. import __version__ as _ver

    result: dict[str, Any] = {}
    result["_meta"] = {
        "ae_version": _ver,
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(),
    }
    for key, value in combined.items():
        if key.startswith("_") or key in hidden:
            continue
        if _is_sensitive_field(key):
            continue
        if isinstance(value, (str, int, float, bool, list, dict, type(None))):
            result[key] = value
    return result


def _write_answers_file(data: dict, dst: Path) -> None:
    """写入 .ae-answers.yml 到目标路径。

    P2-16: 显式 utf-8 encoding — 防止 Windows GBK 默认编码破坏中文 answers。

    Raises:
        OSError: 写入失败（目录权限/磁盘满等）。
    """
    with open(dst, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)
