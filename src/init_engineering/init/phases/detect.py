"""Phase 1: detect — 模式判定 + 项目类型检测 + 并发锁.

来源: init/scaffold_phases.py → phases/detect.py (2026-07-03 拆分).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

_logger = logging.getLogger(__name__)

from ..config_types import TEMPLATES_ROOT
from ..detector import ProjectDetector
from ..detector_constants import DetectionResult
from ..errors import TargetDirectoryError, ValidationError
from ..prompts import prompt_for_project_type
from ..scaffold_lock import InitLock
from ..scaffold_prereq import check_basic_tools, check_language_tools


def phase_detect(
    project_type: str | None,
    dst_path: Path,
    language: str | None,
    skip_tasks: bool,
    incremental: bool,
    force: bool,
    pretend: bool,
    defaults: bool,
) -> tuple[str, str, DetectionResult | None, InitLock | None]:
    """Phase detect: 增量/全量模式判定 + 类型检测 + 锁.

    Returns:
        (project_type, mode, detection, lock) tuple。
        lock 为 None 当 pretend=True（dry-run 不持有锁）。
    """
    # 白名单校验：防 project_type 注入 '../etc' 落到 ~/.ae-replays/<type>/
    if project_type:
        validate_project_type(project_type)

    if dst_path.exists() and not force:
        if any(dst_path.iterdir()):
            mode = "incremental" if incremental else _raise_nonempty(dst_path, incremental)
        else:
            mode = "fresh"
    else:
        mode = "fresh"

    # Acquire concurrent lock (after non-empty check, before project detection)
    # B1: 必须把锁对象返回给 worker,否则 fd 立刻 GC → 锁瞬间释放,两个 init 进程会
    # 同时进入渲染/合并阶段并破坏目标目录。
    # PE-P1-1: 若 InitLock.acquire_for 失败,回滚刚 mkdir 的空目录,不留半成品
    lock: InitLock | None = None
    if not pretend:
        created_dst = False
        if not dst_path.exists():
            dst_path.mkdir(parents=True, exist_ok=True)
            created_dst = True
        try:
            lock = InitLock.acquire_for(dst_path)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            _logger.exception("获取 InitLock 失败 (dst=%s)", dst_path)
            # 锁获取失败 → 回滚空目录
            if created_dst and dst_path.exists() and not any(dst_path.iterdir()):
                try:
                    dst_path.rmdir()
                except OSError:
                    pass
            raise

    analysis: DetectionResult | None = None
    if not project_type:
        detector = ProjectDetector(dst_path)
        analysis = detector.analyze()
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


def _raise_nonempty(dst_path: Path, incremental: bool) -> str:
    if incremental:
        return "incremental"
    raise TargetDirectoryError(
        f"目录 {dst_path.name} 非空。使用 --force 强制覆盖，"
        f"--incremental 增量补充缺失文件，"
        f"或在空目录/新目录中运行 ae init"
    )


def validate_project_type(project_type: str) -> None:
    """防路径穿越：project_type 仅允许字母/数字/下划线/连字符。

    来源：所有项目类型（CLI / detector / 交互）都需通过此校验。
    之前在 phase_finalize 校验，但 ~/.ae-replays/<type>/ 路径已在更早阶段生成。
    """
    if not re.match(r"^[A-Za-z0-9_-]+$", project_type):
        raise ValidationError(
            f"project_type '{project_type}' 含非法字符。"
            f"只允许字母/数字/下划线/连字符 (防路径穿越)."
        )