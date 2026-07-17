"""Phase 1: detect — 模式判定 + 项目类型检测 + 并发锁.

来源: init/scaffold_phases.py → phases/detect.py (2026-07-03 拆分).
"""

from __future__ import annotations

import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

from ..config_types import TEMPLATES_ROOT  # noqa: E402
from ..detector import ProjectDetector  # noqa: E402
from ..detector_constants import DetectionResult  # noqa: E402
from ..errors import TargetDirectoryError  # noqa: E402
from ..prompts import prompt_for_project_type  # noqa: E402
from ..scaffold_lock import InitLock  # noqa: E402
from ..scaffold_prereq import check_basic_tools, check_language_tools  # noqa: E402
from . import validate_project_type  # noqa: E402


def phase_detect(
    project_type: str | None,
    dst_path: Path,
    language: str | None,
    skip_tasks: bool,
    incremental: bool,
    force: bool,
    pretend: bool,
    defaults: bool,
    *,
    include_hidden: bool = False,
) -> tuple[str, str, DetectionResult | None, InitLock | None]:
    """Phase detect: 增量/全量模式判定 + 类型检测 + 锁.

    ⚠ 副作用:
    - 非空目录无 --force --incremental 时抛出 TargetDirectoryError
    - 获取 InitLock (写入 .ae-init.lock)，返回给调用方释放
    - 调用 ProjectDetector.analyze() 读取磁盘文件

    Returns:
        (project_type, mode, detection, lock) tuple。
        lock 为 None 当 pretend=True（dry-run 不持有锁）。
    """
    # 白名单校验：防 project_type 注入 '../etc' 落到 ~/.ae-replays/<type>/
    if project_type:
        validate_project_type(project_type)

    if dst_path.exists() and any(dst_path.iterdir()):
        if incremental:
            mode = "incremental"
            # v5.6: merge_incremental() 基于文件系统直接对比（tmpdir vs dst_path），
            # 逐文件判断"跳过已有/补充缺失"。不需要 .ae-answers.yml 基线文件——
            # 它是 init 的产出物（Phase 5 写入），不是前提条件。
            # 设计 §8 状态机规定：非空目录 + --incremental → incremental mode。
        elif not force:
            _raise_nonempty(dst_path)
        else:
            mode = "fresh"
    else:
        mode = "fresh"

    # Acquire concurrent lock (after non-empty check, before project detection)
    # B1: 必须把锁对象返回给 worker,否则 fd 立刻 GC → 锁瞬间释放,两个 init 进程会
    # 同时进入渲染/合并阶段并破坏目标目录。
    # acquire_for 内部处理目录创建（锁保护下），避免 TOCTOU 竞态。
    lock: InitLock | None = None
    if not pretend:
        try:
            lock = InitLock.acquire_for(dst_path)
        except (OSError, TargetDirectoryError):
            _logger.exception("获取 InitLock 失败 (dst=%s)", dst_path)
            raise

    # 始终运行检测分析 — 即使用户已提供 project_type，
    # 仍需要 language/package_manager/test_runner 等自动检测结果
    detector = ProjectDetector(dst_path, include_hidden=include_hidden)
    analysis = detector.analyze()
    if not project_type:
        project_type = analysis.project_type
        if not project_type:
            if defaults:
                raise TargetDirectoryError("无法自动检测项目类型，请用 --type 指定")
            available = [
                d.name
                for d in TEMPLATES_ROOT.iterdir()
                if d.is_dir() and not d.name.startswith("_")
            ]
            project_type = prompt_for_project_type(available)

    # 增量模式下检测置信度低时输出警告，让调用方（如 Claude Code agent）
    # 有机会介入纠正，而非静默推进到渲染阶段。
    if incremental and analysis and analysis.confidence == "low":
        _logger.warning(
            "项目类型检测置信度为 low（%s），--incremental 模式将跳过交互确认。"
            "如果类型不正确，请用 --type 显式指定。信号来源: candidates=%s, language=%s",
            project_type, analysis.candidates, analysis.language,
        )

    check_basic_tools()
    check_language_tools(language, skip_tasks)
    return project_type, mode, analysis, lock


def _raise_nonempty(dst_path: Path) -> None:
    """非空目录无 --force --incremental 时抛 TargetDirectoryError。

    调用方已在三元表达式中检查 incremental=True 路径，
    故本函数不需要 incremental 参数。
    """
    raise TargetDirectoryError(
        f"目录 {dst_path.name} 非空。使用 --force 强制覆盖，"
        f"--incremental 增量补充缺失文件，"
        f"或在空目录/新目录中运行 ae init"
    )