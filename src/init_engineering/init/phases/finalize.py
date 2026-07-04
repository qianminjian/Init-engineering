"""Phase 4: finalize — 写入 .ae-answers.yml + 增量/全量 copytree.

来源: scaffold_phase_funcs.py phase_finalize + _atomic_copytree + _write_replay (2026-07-03 拆分).

PR#3 P1-1: merge_incremental 从 scaffold_hooks.py 迁入 — 消除跨模块延迟 import,
phases/finalize 真正自包含,与 scaffold_hooks 解耦。
"""

from __future__ import annotations

import logging
import os as _os
import shutil
import subprocess
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
        # PR#3 P1-1: merge_incremental 已在同模块,无需延迟 import
        created, skipped = merge_incremental(tmpdir, dst_path, created_files)
        if not quiet:
            # PE-AUDIT-P0-2: 进度消息走 logger
            _logger.info(
                "\n✓ 增量模式：已补充 %d 个文件，跳过 %d 个已有文件",
                len(created), len(skipped),
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
            # PE-AUDIT-P0-2: 进度消息走 logger
            _logger.info("✓ 项目已生成: %s", dst_path)
            _logger.info("  文件数: %d", file_count)
            _logger.info("  下一步: cd %s && git log", dst_path.name)
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

    PE-P0-4: 排除生成产物目录 (.venv / node_modules / target / dist / __pycache__)。
    这些是 run_builtin_hooks 在 tmpdir 创建的 build artifacts,
    含指向 tmpdir 路径的 shebang/二进制引用 — 复制到 dst 后会失效。
    dst 的依赖安装在 phase_post_install 重新执行。
    """
    import time as _time

    partial = dst.with_name(f"{dst.name}.partial-{int(_time.time() * 1000)}")
    new_marker = dst.with_name(f"{dst.name}.new")

    # PE-P0-4: 复制时排除生成产物 (与 .gitignore 默认行为一致)
    _EXCLUDED_FROM_COPY = frozenset({
        ".venv", "venv", "env", ".env",  # Python venv
        "node_modules", ".pnpm-store",   # Node.js
        "target",                         # Rust
        "dist", "build", ".next",         # 构建产物
        "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",  # Python 缓存
        ".turbo", ".parcel-cache",        # 各类缓存
    })

    def _ignore_build_artifacts(directory: str, names: list[str]) -> set[str]:
        return {n for n in names if n in _EXCLUDED_FROM_COPY}

    try:
        shutil.copytree(src, partial, ignore=_ignore_build_artifacts)
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


def phase_post_install(
    answers,
    dst_path: Path,
    strict: bool = False,
    quiet: bool = False,
    no_install: bool = False,
    timeout: int | None = None,
) -> None:
    """PE-P0-4: 在 dst_path (而非 tmpdir) 重新执行依赖安装。

    run_builtin_hooks 在 tmpdir 跑 uv sync 创建的 .venv,
    复制到 dst 后 shebang 指向已清理的 tmpdir 路径 → venv 失效。
    此函数在 dst 重新安装依赖,生成正确 shebang 的 .venv。

    no_install=True 时跳过 (与 --no-install CLI flag 联动)。
    timeout=None 走 _DEFAULT_SUBPROCESS_TIMEOUT (300s)。

    PE-AUDIT-P0-2: 业务消息走 _logger 而非 print()
    PE-AUDIT-P0-1: subprocess.run 加 timeout (网络挂死兜底)
    """
    from ..scaffold_hooks import (
        _DEFAULT_SUBPROCESS_TIMEOUT,
        _PM_INSTALL_CMD,
        _has_package_file,
        _validate_package_manager,
    )

    effective_timeout = timeout if timeout is not None else _DEFAULT_SUBPROCESS_TIMEOUT

    if no_install:
        if not quiet:
            _logger.info("  (skipping post-install: --no-install flag set)")
        return

    pm = answers.get("package_manager")
    if not pm or not _has_package_file(dst_path, pm):
        return

    install_cmd = _PM_INSTALL_CMD.get(pm)
    if install_cmd is None:
        if not quiet:
            _logger.info("  (skipping %s install: no separate install phase)", pm)
        return

    _validate_package_manager(pm)

    try:
        result = subprocess.run(
            install_cmd, cwd=dst_path, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=effective_timeout,
        )
        if result.returncode != 0:
            cmd_str = " ".join(install_cmd)
            if strict:
                from ..errors import HookExecutionError
                raise HookExecutionError(command=cmd_str, exit_code=result.returncode, stderr=result.stderr)
            if not quiet:
                _logger.warning("warning: %s failed: exit=%d", cmd_str, result.returncode)
    except (FileNotFoundError, OSError) as e:
        cmd_str = " ".join(install_cmd)
        if strict:
            from ..errors import HookExecutionError
            raise HookExecutionError(command=cmd_str, exit_code=127, stderr=str(e))
        if not quiet:
            _logger.warning("warning: %s not found: %s", cmd_str, e)
    except subprocess.TimeoutExpired:
        cmd_str = " ".join(install_cmd)
        if strict:
            from ..errors import HookExecutionError
            raise HookExecutionError(command=cmd_str, exit_code=-1, stderr=f"timed out after {effective_timeout}s")
        if not quiet:
            _logger.warning("warning: %s timed out after %ds", cmd_str, effective_timeout)


def merge_incremental(
    tmpdir: Path,
    dst_path: Path,
    created_files: set[str],
) -> tuple[list[Path], list[Path]]:
    """A1: 增量模式合并 — 逐文件复制,跳过已存在 + .git/。

    PR#3 P1-1: 从 scaffold_hooks.py 迁入 — 让 phases/finalize.py 自包含,
    消除 scaffold.py → scaffold_hooks.merge_incremental 与 phases/finalize.py
    的跨模块延迟 import 循环隐患。

    Args:
        tmpdir: 临时生成目录
        dst_path: 目标目录
        created_files: 收集已创建文件相对路径的集合 (会被原地修改)

    Returns:
        (created_files, skipped_files) 绝对路径列表
    """
    created: list[Path] = []
    skipped: list[Path] = []
    for src_file in tmpdir.rglob("*"):
        if src_file.is_dir():
            continue
        rel = src_file.relative_to(tmpdir)
        # A1: 跳过 .git/ 目录
        if any(part == ".git" for part in rel.parts):
            continue
        dst_file = dst_path / rel
        if dst_file.exists():
            skipped.append(dst_file)
            continue
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        shutil.copymode(src_file, dst_file)
        created_files.add(str(rel))
        created.append(dst_file)
    return created, skipped


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