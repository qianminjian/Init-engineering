"""Agent Skill 入口 — ae init 作为 Claude Code Skill 运行.

用法:
    from init_engineering.skill import skill
    result = skill("init my-project --type app-service")
    result = skill("analyze /path/to/existing/project")

作为 Claude Code Skill 调用时, skill() 接收结构化命令字符串,
解析后调用 InitWorker 或 ProjectDetector, 返回结构化结果.

Skill 描述 (用于 Claude Code skill 注册):
    "初始化项目环境: ae init <project> --type <type>
     分析存量项目: ae init --analyze <path>"
"""

from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import click

from ._shared.path_utils import resolve_user_path

_logger = logging.getLogger(__name__)


@dataclass
class SkillResult:
    """Skill 执行结果。"""

    success: bool
    message: str
    action: str = ""  # "init", "analyze", "detect"
    project_path: str | None = None  # 展示用字符串 (str(Path)), 非 Path 对象
    project_type: str | None = None
    candidates: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


def skill(command_str: str, cwd: Path | None = None) -> SkillResult:
    """解析结构化指令并执行对应的 init 操作。

    ⚠ 隐式副作用: 未传 cwd 时默认绑定进程当前工作目录 (Path.cwd())，
    调用方应始终显式传入 cwd 以避免非确定性行为。

    Args:
        command_str: 结构化命令字符串，如 "init my-project --type app-service"
        cwd: 当前工作目录。传入 None 时回退到 Path.cwd()

    Returns:
        SkillResult: 执行结果
    """
    if cwd is None:
        cwd = Path.cwd()

    # 解析指令
    action, project_path, options = _parse_prompt(command_str)

    if action == "analyze":
        return _run_analyze(project_path, cwd)
    elif action == "init":
        return _run_init(project_path, options, cwd)
    elif action == "detect":
        return _run_detect(project_path, cwd)
    else:
        return SkillResult(
            success=False,
            message=(
                f"未知指令动词 '{action}'。"
                f"支持: init <project> [--type <type>] [options], "
                f"analyze <path>, detect <path>"
            ),
            action="parse",
        )


def _parse_prompt(prompt: str) -> tuple[str, str | None, dict]:
    """解析 prompt 为 action/project_path/options。

    解析策略（按优先级）：
    1. 匹配 "detect <path>" → detect action
    2. 匹配 "analyze <path>" → analyze action
    3. 匹配 "init <args>" → 先检查 --analyze 子模式（路由到 analyze），
       再扫描 --key value 选项标记消费的 token，剩余第一个未消费 token 为 project_path

    支持的格式:
        "init my-project --type app-service"
        "init /path/to/project --type library"
        "analyze /path/to/project"
        "analyze ."
        "detect ."
        "init my-project"
    """
    prompt = prompt.strip()

    # detect
    detect_match = re.match(r"^detect\s+(.+)$", prompt)
    if detect_match:
        return ("detect", detect_match.group(1).strip(), {})

    # analyze
    analyze_match = re.match(r"^(?:analyze|analyse)\s+(.+)$", prompt)
    if analyze_match:
        return ("analyze", analyze_match.group(1).strip(), {})

    # init (支持 --analyze 子模式)
    init_match = re.match(r"^init\s+(.+)$", prompt)
    if init_match:
        args_str = init_match.group(1).strip()
        options = {}
        project_path = None

        # 解析选项 — 先收集所有 --key 及其值, 剩余 token 为 project_path
        consumed_indices: set[int] = set()
        parts = args_str.split()

        # --analyze 特殊处理: 将 init --analyze <path> 路由到分析模式
        if "--analyze" in parts:
            idx = parts.index("--analyze")
            project_path = parts[idx + 1] if idx + 1 < len(parts) else "."
            return ("analyze", project_path, options)

        # 解析选项: --key val → options[key] = val, 同时标记 consumed_indices
        i = 0
        while i < len(parts):
            if parts[i].startswith("--"):
                key = parts[i][2:]  # strip leading --
                consumed_indices.add(i)
                if i + 1 < len(parts) and not parts[i + 1].startswith("--"):
                    options[key] = parts[i + 1]
                    consumed_indices.add(i + 1)
                    i += 1
                else:
                    options[key] = "true"
            i += 1

        # 取第一个未消费的非 -- token 为 project_path
        for i, part in enumerate(parts):
            if i not in consumed_indices:
                project_path = part
                break

        return ("init", project_path, options)

    return ("unknown", None, {})


def _run_analyze(
    project_path: str | None,
    cwd: Path,
    *,
    _detector_cls: type | None = None,
) -> SkillResult:
    """运行存量项目分析。

    Args:
        project_path: 目标路径
        cwd: 当前工作目录
        _detector_cls: 测试注入点 — 替换 ProjectDetector 类
    """
    from init_engineering.init.detector import ProjectDetector

    detector_cls = _detector_cls if _detector_cls is not None else ProjectDetector

    try:
        target = resolve_user_path(project_path, cwd)
    except ValueError as e:
        return SkillResult(success=False, message=str(e), action="analyze")

    if not target.exists():
        return SkillResult(
            success=False,
            message=f"目录不存在: {target}。请确认路径拼写，或将项目文件放入该目录后重试。",
            action="analyze",
        )

    detector = detector_cls(target)
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
) -> SkillResult:
    """运行项目初始化。

    Args:
        project_path: 目标路径
        options: CLI 选项字典
        cwd: 当前工作目录
        _worker_cls: 测试注入点 — 替换 InitWorker 类
    """
    from init_engineering.init import InitWorker
    from init_engineering.init.errors import InitError

    worker_cls = _worker_cls if _worker_cls is not None else InitWorker

    try:
        dst_path = resolve_user_path(project_path, cwd)
    except ValueError as e:
        return SkillResult(success=False, message=str(e), action="init")

    # 构建 CLI 参数
    kwargs = {}
    # --no-* 标志：存在表示否定（val == "true" 表示标志被传递）
    _negated_flags = frozenset({"no-typescript", "no-lefthook", "no-docker"})
    for key, val in options.items():
        # 转换 CLI 选项名到 InitWorker 参数名
        param_map = {
            "type": "project_type",
            "language": "language",
            "package-manager": "package_manager",
            "ci": "ci_platform",
            "test-runner": "test_runner",
            "no-typescript": "use_typescript",
            "no-lefthook": "use_lefthook",
            "no-docker": "use_docker",
            "defaults": "defaults",
            "force": "force",
            "quiet": "quiet",
            "incremental": "incremental",
            "strict": "strict",
            "verbose": "verbose",
        }
        if key in param_map:
            param = param_map[key]
            if key in _negated_flags:
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
    except (InitError, OSError, ValueError) as e:
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


def _run_detect(project_path: str | None, cwd: Path) -> SkillResult:
    """运行项目类型检测（不初始化）。"""
    result = _run_analyze(project_path, cwd)
    result.action = "detect"
    return result


# Claude Code Skill 入口点
# 当作为 Skill 调用时, Claude Code 会调用 skill() 函数
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        result = skill(" ".join(sys.argv[1:]))
        click.echo(result.message)
        sys.exit(0 if result.success else 1)
    else:
        click.echo("Usage: python -m init_engineering.skill <command>")
        click.echo("  analyze <path>  - 分析存量项目")
        click.echo("  detect <path>  - 检测项目类型")
        click.echo("  init <project> [--type <type>] - 初始化新项目")
