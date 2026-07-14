"""Skill 执行器 — _run_analyze / _run_init / _run_detect.

从 skill.py 拆分（P1-3），减少单文件行数。
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from .._shared.path_utils import resolve_user_path

_logger = logging.getLogger(__name__)


def _run_analyze(
    project_path: str | None,
    cwd: Path,
    *,
    _detector_cls: type | None = None,
    options: dict | None = None,
) -> "SkillResult":
    """运行存量项目分析。

    Args:
        project_path: 目标路径
        cwd: 当前工作目录
        _detector_cls: 测试注入点 — 替换 ProjectDetector 类
        options: 解析出的选项字典（如 {"include-hidden": "true"}）
    """
    from init_engineering.init.detector import ProjectDetector

    from ._types import SkillResult

    detector_cls = _detector_cls if _detector_cls is not None else ProjectDetector
    opts = options or {}

    try:
        target = resolve_user_path(project_path, cwd)
    except ValueError as e:
        _logger.debug("路径解析失败: %s", e, exc_info=True)
        return SkillResult(success=False, message=str(e), action="analyze")

    if not target.exists():
        return SkillResult(
            success=False,
            message=f"目录不存在: {target}。请确认路径拼写，或将项目文件放入该目录后重试。",
            action="analyze",
        )

    detector = detector_cls(target, include_hidden=opts.get("include-hidden") == "true")
    result = detector.analyze()

    if result.candidates:
        return SkillResult(
            success=True,
            message=f"检测到 {len(result.candidates)} 个项目类型候选",
            action="analyze",
            project_path=str(target),
            project_type=result.project_type,
            candidates=result.candidates,
            details={
                "candidates": result.candidates,
                "detected": result.project_type,
                "language": result.language,
                "package_manager": result.package_manager,
                "test_runner": result.test_runner,
                "ci_platform": result.ci_platform,
                "frameworks": result.frameworks,
                "has_docker": result.has_docker,
                "has_lefthook": result.has_lefthook,
            },
        )
    else:
        return SkillResult(
            success=True,
            message="未检测到已知项目类型",
            action="analyze",
            project_path=str(target),
            candidates=[],
        )


def _run_init(
    project_path: str | None,
    options: dict,
    cwd: Path,
    *,
    _worker_cls: type | None = None,
) -> "SkillResult":
    """运行项目初始化。

    Args:
        project_path: 目标路径
        options: CLI 选项字典
        cwd: 当前工作目录
        _worker_cls: 测试注入点 — 替换 InitWorker 类
    """
    from init_engineering.init import InitWorker
    from init_engineering.init.config_types import NEGATED_FLAG_MAP
    from init_engineering.init.errors import InitError

    from ._types import SkillResult

    worker_cls = _worker_cls if _worker_cls is not None else InitWorker

    try:
        dst_path = resolve_user_path(project_path, cwd)
    except ValueError as e:
        return SkillResult(success=False, message=str(e), action="init")

    # 构建 CLI 参数
    kwargs = {}
    for key, val in options.items():
        # 转换 CLI 选项名到 InitWorker 参数名
        param_map = {
            "type": "project_type",
            "language": "language",
            "package-manager": "package_manager",
            "ci": "ci_platform",
            "test-runner": "test_runner",
            "defaults": "defaults",
            "force": "force",
            "quiet": "quiet",
            "incremental": "incremental",
            "strict": "strict",
            "verbose": "verbose",
            "include-hidden": "include_hidden",
            **NEGATED_FLAG_MAP,
        }
        if key in param_map:
            param = param_map[key]
            if key in NEGATED_FLAG_MAP:
                kwargs[param] = False
            elif val == "true":
                kwargs[param] = True
            elif val not in ("true", "false"):
                kwargs[param] = val

    # 非 TTY 环境（Claude Code / CI / 管道）自动启用 defaults，
    # 避免 BasicPromptBackend.input() 挂死等待不可用的 stdin。
    if not sys.stdin.isatty() and not kwargs.get("defaults"):
        _logger.info("非 TTY 环境，自动启用 --defaults 模式")
        kwargs["defaults"] = True

    try:
        worker = worker_cls(dst_path=dst_path, **kwargs)
        result = worker.execute()
        return SkillResult(
            success=True,
            message=f"项目已初始化: {result.dst_path}",
            action="init",
            project_path=str(result.dst_path),
            project_type=result.project_type,
            details={"files_count": len(result.files)},
        )
    except (KeyboardInterrupt, SystemExit):
        raise
    except (InitError, OSError, ValueError, subprocess.TimeoutExpired) as e:
        _logger.exception("InitWorker 执行失败: %s", e)
        hint = getattr(e, "recovery_hint", "")
        if hint:
            hint = f"。建议: {hint}"
        else:
            hint = "。内部错误，请用 --verbose 查看详细日志，或提交 issue 附带 traceback"
        return SkillResult(
            success=False,
            message=f"初始化失败: {e}{hint}",
            action="init",
            project_path=str(dst_path),
        )
    except Exception as e:
        _logger.exception("InitWorker 执行失败 (未预期异常): %s", e)
        return SkillResult(
            success=False,
            message=(
                f"初始化失败 (内部错误): {e}。"
                "请用 --verbose 查看详细日志，或提交 issue 附带 traceback"
            ),
            action="init",
            project_path=str(dst_path),
        )


def _run_detect(project_path: str | None, cwd: Path, *, options: dict | None = None) -> "SkillResult":
    """运行项目类型检测（不初始化）。"""
    result = _run_analyze(project_path, cwd, options=options)
    result.action = "detect"
    return result
