"""Phase 1: detect — 模式判定 + 项目类型检测 + 并发锁.

来源: init/scaffold_phases.py → phases/detect.py (2026-07-03 拆分).
"""

from __future__ import annotations

import contextlib
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
            if not (dst_path / ".ae-answers.yml").exists():
                if not project_type and defaults:
                    raise TargetDirectoryError(
                        "目录非空但缺少 .ae-answers.yml 基线文件，且无法自动检测项目类型。"
                        " 使用 --type 指定类型后重试，或 --force 进行完整初始化。"
                    )
                if project_type:
                    _logger.warning(
                        "目录非空但缺少 .ae-answers.yml 基线文件，增量模式可能遗漏文件。"
                        " 建议: 先 ae init --type %s --defaults --force 完整初始化。",
                        project_type,
                    )
                else:
                    _logger.warning(
                        "目录非空但缺少 .ae-answers.yml 基线文件，增量模式可能遗漏文件。"
                        " 建议: 先 ae init --type <type> --defaults --force 完整初始化。"
                    )
        elif not force:
            _raise_nonempty(dst_path)
        else:
            mode = "fresh"
    else:
        mode = "fresh"

    # Acquire concurrent lock (after non-empty check, before project detection)
    # B1: 必须把锁对象返回给 worker,否则 fd 立刻 GC → 锁瞬间释放,两个 init 进程会
    # 同时进入渲染/合并阶段并破坏目标目录。
    lock: InitLock | None = None
    if not pretend:
        created_dst = False
        if not dst_path.exists():
            dst_path.mkdir(parents=True, exist_ok=True)
            created_dst = True
        try:
            lock = InitLock.acquire_for(dst_path)
        except (OSError, TargetDirectoryError):
            _logger.exception("获取 InitLock 失败 (dst=%s)", dst_path)
            if created_dst and dst_path.exists() and not any(dst_path.iterdir()):
                with contextlib.suppress(OSError):
                    dst_path.rmdir()
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