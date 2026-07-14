"""Phase 4: finalize — 写入 .ae-answers.yml + 增量/全量 copytree.

来源: init/scaffold_phases.py → phases/finalize.py (2026-07-03 拆分).

PR#3 P1-1: merge_incremental 从 scaffold_hooks.py 迁入 — 消除跨模块延迟 import,
phases/finalize 真正自包含,与 scaffold_hooks 解耦。
"""

from __future__ import annotations

import contextlib
import logging
import os as _os
import shutil
import time as _time
from datetime import datetime
from pathlib import Path

from ..answers import AnswersMap
from ..manifest import build_manifest, write_manifest

_logger = logging.getLogger(__name__)


def phase_finalize(
    answers: AnswersMap,
    project_type: str | None,
    tmpdir: Path,
    dst_path: Path,
    created_files: set[str],
    mode: str,
    quiet: bool,
    generated: list[Path] | None = None,
) -> tuple[bool, int]:
    """Phase finalize: 写入 .ae-answers.yml + 增量/全量 copytree。

    ⚠ 副作用:
    - 写入 .ae-answers.yml 到 tmpdir
    - 写入 init-manifest.json 到 .ae-state/
    - 写入 replay 文件到 ~/.ae-replays/
    - 原子 copytree (tmpdir → dst_path): 全量模式先清空 dst_path 再复制
    - 增量模式: merge_incremental 补充缺失文件，跳过已存在文件

    Returns:
        (did_create_dst, skipped_count): 本次是否创建了目标目录，增量模式跳过的文件数。
    """
    answers.write_to(tmpdir / ".ae-answers.yml")

    # Init → Loop contract: write init-manifest.json to .ae-state/
    # Only populate design_root if a design/ directory was actually scaffolded
    _design_root = "design" if (tmpdir / "design").is_dir() else None
    manifest = build_manifest(answers, project_type or "unknown", design_root=_design_root)
    write_manifest(manifest, tmpdir)

    # P2-15: defense-in-depth 二次校验 — phase_detect 已校验,但 phase_finalize
    # 也可能从测试 / 内部 API 直接调用,绕过 phase_detect 校验链。
    # _write_replay 把 raw_type 拼到 ~/.ae-replays/<type>/ 路径,无校验即被路径穿越。
    from . import validate_project_type

    raw_type = project_type or "unknown"
    validate_project_type(raw_type)
    _write_replays(answers, raw_type)

    if mode == "incremental":
        # PR#3 P1-1: merge_incremental 已在同模块,无需延迟 import
        created, skipped = merge_incremental(tmpdir, dst_path, created_files)
        skipped_count = len(skipped)
        if not quiet:
            # PE-AUDIT-P0-2: 进度消息走 logger
            _logger.info(
                "\n✓ 增量模式：已补充 %d 个文件，跳过 %d 个已有文件",
                len(created), skipped_count,
            )
            if len(created) == 0 and not (dst_path / ".ae-answers.yml").exists():
                _logger.warning(
                    "  未添加任何新文件。目录可能已包含所有模板文件，"
                    " 或 .ae-answers.yml 基线缺失导致增量模式无法确定差异。"
                    " 使用 --force 进行完整初始化，或 --type 指定项目类型。"
                )
        return False, skipped_count
    else:
        did_create_dst = not dst_path.exists()
        if did_create_dst:
            dst_path.mkdir(parents=True)
        # A2: 原子写 — 先写 dst.partial-<ts>/ 再 rename，避免 SIGKILL/IO 错误留半成品
        _atomic_copytree(tmpdir, dst_path)
        if not quiet:
            # P2-2: 真实文件数 — 之前写死 "文件数: 0" 是 bug, 用 generated 实际计数
            file_count = (
                len(generated)
                if generated
                else sum(1 for _ in dst_path.rglob("*") if _.is_file())
            )
            # PE-AUDIT-P0-2: 进度消息走 logger
            _logger.info("✓ 项目已生成: %s", dst_path)
            _logger.info("  文件数: %d", file_count)
            _logger.info("  下一步: cd %s && git log", dst_path.name)
        return did_create_dst, 0


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
    # Resolve before .name/.with_name — Path('.') has empty .name on POSIX
    dst = dst.resolve()
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
        # 注意: copytree 内部逐文件复制,不原子 — rename 在同一 FS 上是原子的,
        # 但 copytree 中途崩溃会留下不完整的 partial 树。crash 恢复需手动删 partial/ 和 .new/。
        shutil.copytree(src, partial, ignore=_ignore_build_artifacts)
        # 第 1 步:将 partial 重命名为 .new (单次 rename 原子)
        partial.replace(new_marker)
        # 第 2 步:旧 dst 先 rename 到备份，再 replace .new → dst，失败时可恢复
        old_backup = dst.with_name(f"{dst.name}.old-{int(_time.time() * 1000)}")
        if dst.exists():
            dst.replace(old_backup)
        try:
            new_marker.replace(dst)
        except (OSError, shutil.Error):
            # replace 失败 → 恢复旧 dst 备份
            if old_backup.exists():
                old_backup.replace(dst)
            raise
        else:
            # replace 成功 → 清理备份
            if old_backup.exists():
                shutil.rmtree(old_backup, ignore_errors=True)
    except (OSError, shutil.Error):
        # 失败清理:partial 和 .new 都尝试回收
        shutil.rmtree(partial, ignore_errors=True)
        shutil.rmtree(new_marker, ignore_errors=True)
        raise


def phase_post_install(
    answers: AnswersMap,
    dst_path: Path,
    strict: bool = False,
    quiet: bool = False,
    no_install: bool = False,
    timeout: int | None = None,
) -> None:
    """PE-P0-4: 在 dst_path (而非 tmpdir) 重新执行依赖安装。

    ⚠ 副作用:
    - 执行包管理器 install 命令 (网络 I/O)，修改 dst_path 下的依赖文件
    - strict=True 时安装失败抛 HookExecutionError

    run_builtin_hooks 在 tmpdir 跑 uv sync 创建的 .venv,
    复制到 dst 后 shebang 指向已清理的 tmpdir 路径 → venv 失效。
    此函数在 dst 重新安装依赖,生成正确 shebang 的 .venv。

    no_install=True 时跳过 (与 --no-install CLI flag 联动)。
    timeout=None 走 DEFAULT_SUBPROCESS_TIMEOUT (300s)。

    PE-AUDIT-P0-2: 业务消息走 _logger 而非 print()
    PE-AUDIT-P0-1: subprocess.run 加 timeout (网络挂死兜底)
    """
    from ..scaffold_hooks import (
        DEFAULT_SUBPROCESS_TIMEOUT,
        run_pm_install_and_report,
    )

    effective_timeout = timeout if timeout is not None else DEFAULT_SUBPROCESS_TIMEOUT

    if strict:
        def _fail(cmd: str, rc: int, stderr: str) -> bool:
            from ..errors import HookExecutionError
            raise HookExecutionError(command=cmd, subprocess_returncode=rc, stderr=stderr)
    else:
        _fail = None

    run_pm_install_and_report(
        answers, dst_path, timeout=effective_timeout, quiet=quiet,
        no_install=no_install, _fail=_fail,
    )


def merge_incremental(
    tmpdir: Path,
    dst_path: Path,
    created_files: set[str],
) -> tuple[list[Path], list[Path]]:
    """A1: 增量模式合并 — 逐文件复制,跳过已存在 + .git/。

    PR#3 P1-1: 从 scaffold_hooks.py 迁入 — 让 phases/finalize.py 自包含,
    消除跨模块延迟 import 循环隐患。

    Args:
        tmpdir: 临时生成目录
        dst_path: 目标目录
        created_files: 收集已创建文件相对路径的集合 (会被原地修改)

    Returns:
        (created_files, skipped_files) 绝对路径列表
    """
    created: list[Path] = []
    skipped: list[Path] = []
    # Resolve dst_path to absolute — 防御 uv run --directory 等 CWD 变更场景
    dst_path = dst_path.resolve()
    # PR#5 P2-5: 早跳过 _shared.exclude.EXCLUDED_DIRS (与 renderer 一致)
    # 之前只在循环内后置过滤 .git, 嵌套深时仍需遍历 pack/idx
    from .._shared.exclude import EXCLUDED_DIRS
    for src_file in tmpdir.rglob("*"):
        if src_file.is_dir():
            continue
        rel = src_file.relative_to(tmpdir)
        # A1: 早跳过 .git/ / node_modules/ / __pycache__/ / .venv/
        if any(part in EXCLUDED_DIRS for part in rel.parts):
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


def _write_replays(
    answers: AnswersMap,
    raw_type: str,
    *,
    _replay_root: Path | None = None,
) -> None:
    """写入 replay 文件 (best-effort, 失败不阻断主流程).

    大规模投产要点:
    1. 目录权限 0o700 (仅当前用户可读写), 文件权限 0o600
    2. 每类型最多保留 REPLAY_RETENTION 个最新文件, 超出按 mtime 删除
    3. umask 0o077 兜底 (避免新建文件因 umask 022 默认值泄露)
    4. 写失败仅 log warning, 不影响 init 主体

    Args:
        _replay_root: 覆盖默认 ~/.ae-replays/ 根, 测试注入用
    """
    REPLAY_RETENTION = 100
    try:
        replay_root = _replay_root if _replay_root is not None else Path.home() / ".ae-replays"
        replay_dir = replay_root / raw_type
        old_umask = _os.umask(0o077)
        try:
            replay_dir.mkdir(parents=True, exist_ok=True)
            _os.chmod(replay_dir, 0o700)
            replay_file = replay_dir / (
                f"{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}"
                f"-{_os.getpid()}-{_time.monotonic_ns()}.yml"
            )
            answers.write_to(replay_file)
            _os.chmod(replay_file, 0o600)
        finally:
            _os.umask(old_umask)

        # Retention: 仅保留最近 REPLAY_RETENTION 个, 按 mtime 升序删除
        existing = sorted(replay_dir.glob("*.yml"), key=lambda p: p.stat().st_mtime)
        excess = len(existing) - REPLAY_RETENTION
        for stale in existing[:max(0, excess)]:
            with contextlib.suppress(OSError):
                stale.unlink()
    except OSError:
        # best-effort: replay 失败不应阻断 init 主体
        _logger.warning(
            "replay write to ~/.ae-replays/%s/ failed (continuing)", raw_type,
            exc_info=True,
        )