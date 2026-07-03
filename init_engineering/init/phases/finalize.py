"""Phase 4: finalize — 写入 .ae-answers.yml + 增量/全量 copytree.

来源: scaffold_phase_funcs.py phase_finalize + _atomic_copytree + _write_replay (2026-07-03 拆分).
"""

from __future__ import annotations

import logging
import os as _os
import shutil
from datetime import datetime
from pathlib import Path

from ..answers import AnswersMap
from ..config import TemplateConfig

_logger = logging.getLogger(__name__)


def phase_finalize(
    answers: AnswersMap,
    project_type: str | None,
    template: TemplateConfig,
    tmpdir: Path,
    dst_path: Path,
    created_files: set[str],
    mode: str,
    quiet: bool,
    generated: list[Path] | None = None,
) -> bool:
    """写入 .ae-answers.yml + 增量/全量 copytree。

    Returns:
        did_create_dst: 本次是否创建了目标目录（用于错误清理）。
    """
    answers.write_to(tmpdir / ".ae-answers.yml")

    # project_type 已在 phase_detect 入口做过白名单校验 (防路径穿越)
    raw_type = project_type or "unknown"
    _write_replay(answers, raw_type)

    if mode == "incremental":
        from ..scaffold_hooks import merge_incremental
        created, skipped = merge_incremental(tmpdir, dst_path, created_files)
        if not quiet:
            print(
                f"\n✓ 增量模式：已补充 {len(created)} 个文件，"
                f"跳过 {len(skipped)} 个已有文件"
            )
        return False
    else:
        did_create_dst = not dst_path.exists()
        if did_create_dst:
            dst_path.mkdir(parents=True)
        # A2: 原子写 — 先写 dst.partial-<ts>/ 再 rename，避免 SIGKILL/IO 错误留半成品
        _atomic_copytree(tmpdir, dst_path)
        if not quiet:
            # P2-2: 真实文件数 — 之前写死 "文件数: 0" 是 bug, 用 generated 实际计数
            file_count = len(generated) if generated else sum(1 for _ in dst_path.rglob("*") if _.is_file())
            print(f"✓ 项目已生成: {dst_path}")
            print(f"  文件数: {file_count}")
            print(f"  下一步: cd {dst_path.name} && git log")
        return did_create_dst


def _atomic_copytree(src: Path, dst: Path) -> None:
    """原子复制目录树 — partial 写完先 rename → dst.new 再 rmtree(dst) 最后 rename → dst。

    设计要点:
    - 写失败 → dst_path 保持原状（不污染）
    - 写成功 → 真正的"原子替换"语义,任意步骤失败均可恢复
    - 失败后清理 partial 目录避免残留

    三步原子化:
    1. shutil.copytree(src, partial)         — 失败:仅 partial 不存在,无副作用
    2. partial.replace(dst + ".new")         — 失败:dst/.new/partial 三者共存
       (rename 不覆盖非空,先放到 .new 占位,旧 dst 不动)
    3. rmtree(dst) + .new.replace(dst)       — 失败:旧 dst 已删但 .new 在,
       极小窗口期,SIGKILL 后下次 init 可从 .new 恢复

    对比 v1 (rmtree + rename): SIGKILL 在 rmtree 完成后/rename 前会导致数据全丢。
    新版 SIGKILL 落入任何窗口,均保留至少一个完整版本(src-tmpdir 或 dst.new)。
    """
    import time as _time

    partial = dst.with_name(f"{dst.name}.partial-{int(_time.time() * 1000)}")
    new_marker = dst.with_name(f"{dst.name}.new")
    try:
        shutil.copytree(src, partial)
        # 第 1 步:将 partial 重命名为 .new (单次 rename 原子)
        partial.replace(new_marker)
        # 第 2 步:移除旧 dst (如存在)
        if dst.exists():
            shutil.rmtree(dst)
        # 第 3 步:.new 原子替换为 dst
        new_marker.replace(dst)
    except Exception:
        # 失败清理:partial 和 .new 都尝试回收
        shutil.rmtree(partial, ignore_errors=True)
        shutil.rmtree(new_marker, ignore_errors=True)
        raise


def _write_replay(answers: AnswersMap, raw_type: str) -> None:
    """写入 replay 文件 (best-effort, 失败不阻断主流程)。

    大规模投产要点:
    1. 目录权限 0o700 (仅当前用户可读写), 文件权限 0o600
    2. 每类型最多保留 REPLAY_RETENTION 个最新文件, 超出按 mtime 删除
    3. umask 0o077 兜底 (避免新建文件因 umask 022 默认值泄露)
    4. 写失败仅 log warning, 不影响 init 主体
    """
    REPLAY_RETENTION = 100
    try:
        replay_root = Path.home() / ".ae-replays"
        replay_dir = replay_root / raw_type
        old_umask = _os.umask(0o077)
        try:
            replay_dir.mkdir(parents=True, exist_ok=True)
            _os.chmod(replay_dir, 0o700)
            replay_file = replay_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.yml"
            answers.write_to(replay_file)
            _os.chmod(replay_file, 0o600)
        finally:
            _os.umask(old_umask)

        # Retention: 仅保留最近 REPLAY_RETENTION 个, 按 mtime 升序删除
        existing = sorted(replay_dir.glob("*.yml"), key=lambda p: p.stat().st_mtime)
        excess = len(existing) - REPLAY_RETENTION
        for stale in existing[:max(0, excess)]:
            try:
                stale.unlink()
            except OSError:
                pass
    except OSError:
        # best-effort: replay 失败不应阻断 init 主体
        _logger.warning(
            "replay write to ~/.ae-replays/%s/ failed (continuing)", raw_type,
            exc_info=True,
        )