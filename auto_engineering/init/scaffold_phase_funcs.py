"""5 阶段流水线方法函数 — 拆自 InitWorker (v2.5: 360→可控)。

为保持 InitWorker 简洁，每个 _phase_*() 实现提取为模块级函数。
调用约定：通过命名参数显式传 InitWorker 实例 + 上下文参数。
"""

from __future__ import annotations

import logging
import os as _os
import re
import shutil
from datetime import datetime
from pathlib import Path

from .answers import AnswersMap
from .config import TEMPLATES_ROOT, TemplateConfig
from .detector import ProjectDetector
from .errors import TargetDirectoryError
from .hooks import HookRunner
from .prompts import (
    InteractivePrompt,
    prompt_for_nested_template,
    prompt_for_project_type,
)
from .scaffold_lock import InitLock

_logger = logging.getLogger(__name__)
from .scaffold_prereq import check_basic_tools, check_language_tools
from .scaffold_question_eval import evaluate_question_defaults
from .scaffold_render import render_to as _render_to


def phase_finalize(
    answers: AnswersMap,
    project_type: str | None,
    template: TemplateConfig,
    tmpdir: Path,
    dst_path: Path,
    created_files: set[str],
    mode: str,
    quiet: bool,
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
        from .scaffold_hooks import merge_incremental
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
            print(f"✓ 项目已生成: {dst_path}")
            print(f"  文件数: 0")  # caller to inject
            print(f"  下一步: cd {dst_path.name} && git log")
        return did_create_dst


def _atomic_copytree(src: Path, dst: Path) -> None:
    """原子复制目录树 — 先写 dst.partial-<ts>/ 再 rename。

    设计要点:
    - 写失败 → dst_path 保持原状（不污染）
    - 写成功 → 单次 rename 操作 (POSIX 原子) 替换 dst_path 内容
    - 失败后清理 partial 目录避免残留

    注意: rename 不能直接覆盖非空目录,先 rmtree(dst) 再 rename 达到原子替换语义。
    在 rmtree 之前 partial 已就绪,即使 rmtree 成功而 rename 失败,partial 仍可
    fallback move;若 rmtree 失败则保留原状(优于直接污染 dst)。
    """
    import time as _time

    partial = dst.with_name(f"{dst.name}.partial-{int(_time.time() * 1000)}")
    try:
        shutil.copytree(src, partial)
        # 原子替换:先移除旧 dst (如存在),再 rename partial → dst
        if dst.exists():
            shutil.rmtree(dst)
        partial.replace(dst)
    except Exception:
        shutil.rmtree(partial, ignore_errors=True)
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


def phase_detect(
    project_type: str | None,
    dst_path: Path,
    language: str | None,
    skip_tasks: bool,
    incremental: bool,
    force: bool,
    pretend: bool,
    defaults: bool,
) -> tuple[str, str, ProjectDetector | None, InitLock | None]:
    """Phase detect: 增量/全量模式判定 + 类型检测 + 锁。

    Returns:
        (project_type, mode, detector, lock) tuple。
        lock 为 None 当 pretend=True（dry-run 不持有锁）。
    """
    # 白名单校验：防 project_type 注入 '../etc' 落到 ~/.ae-replays/<type>/
    if project_type:
        _validate_project_type(project_type)

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
    lock: InitLock | None = None
    if not pretend:
        if not dst_path.exists():
            dst_path.mkdir(parents=True, exist_ok=True)
        lock = InitLock.acquire_for(dst_path)

    detector = None
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
    return project_type, mode, detector, lock


def _raise_nonempty(dst_path: Path, incremental: bool) -> str:
    if incremental:
        return "incremental"
    raise TargetDirectoryError(
        f"目录 {dst_path.name} 非空。使用 --force 强制覆盖，"
        f"--incremental 增量补充缺失文件，"
        f"或在空目录/新目录中运行 ae init"
    )


def _validate_project_type(project_type: str) -> None:
    """防路径穿越：project_type 仅允许字母/数字/下划线/连字符。

    来源：所有项目类型（CLI / detector / 交互）都需通过此校验。
    之前在 phase_finalize 校验，但 ~/.ae-replays/<type>/ 路径已在更早阶段生成。
    """
    if not re.match(r"^[A-Za-z0-9_-]+$", project_type):
        raise ValueError(
            f"project_type '{project_type}' 含非法字符。"
            f"只允许字母/数字/下划线/连字符 (防路径穿越)."
        )


def phase_prompt(
    project_type: str,
    defaults: bool,
    previous_answers: AnswersMap | None,
    *,
    language: str | None,
    package_manager: str | None,
    ci_platform: str | None,
    test_runner: str | None,
    use_typescript: bool | None,
    use_lefthook: bool | None,
    use_docker: bool | None,
    detection: ProjectDetector | None,
) -> tuple[TemplateConfig, AnswersMap]:
    """加载 TemplateConfig + 应用 CLI overrides + 评估 question + 交互 prompt."""
    template = TemplateConfig.load(project_type or "")
    if template.nested_templates:
        # 选择 nested template 策略:
        # 1. 若 language 在 nested_templates 键中 → 直接选它（CLI 透传 language）
        # 2. defaults 模式自动选第一个
        # 3. 非 defaults 模式交互式询问用户
        preferred = language if language in template.nested_templates else None
        chosen = prompt_for_nested_template(
            template.nested_templates,
            no_input=defaults,
            preferred=preferred,
        )
        if chosen:
            template.template_dir = template.template_dir / chosen

    cli_overrides = {}
    for key, val in [
        ("language", language),
        ("package_manager", package_manager),
        ("ci_platform", ci_platform),
        ("test_runner", test_runner),
        ("use_typescript", use_typescript),
        ("use_lefthook", use_lefthook),
        ("use_docker", use_docker),
    ]:
        if val is not None:
            cli_overrides[key] = val

    answers = AnswersMap(
        defaults={q.var_name: q.default for q in template.questions},
        cli_overrides=cli_overrides,
        previous=previous_answers.previous if previous_answers else {},
        external=template.external_data,
        # A5 安全: external_data sandbox root 强制白名单 (TEMPLATES_ROOT + home)
        # 不再信任 template.template_dir (攻击者可控 via --template-dir)
        external_sandbox_roots=[TEMPLATES_ROOT, Path.home()],
    )
    answers.builtins["project_type"] = project_type or ""
    if detection is not None:
        if detection.language:
            answers.builtins.setdefault("language", detection.language)
        if detection.package_manager:
            answers.builtins.setdefault("package_manager", detection.package_manager)
        if detection.test_runner:
            answers.builtins.setdefault("test_runner", detection.test_runner)
        if detection.ci_platform:
            answers.builtins.setdefault("ci_platform", detection.ci_platform)

    for var in ["project_description", "language", "package_manager",
                "test_runner", "ci_platform", "project_type"]:
        if var not in answers:
            answers.builtins[var] = ""

    evaluate_question_defaults(template, answers)

    if not defaults:
        prompt = InteractivePrompt(template.questions, answers)
        try:
            answers = prompt.run()
        except KeyboardInterrupt:
            answers.save_partial()
            from .errors import InitInterruptedError
            raise InitInterruptedError() from None

    return template, answers


def phase_render(
    answers: AnswersMap,
    template: TemplateConfig,
    dst_path: Path,
    tmpdir: Path,
    *,
    overwrite: bool,
    templates_suffix: str | None,
    preserve_symlinks: bool | None,
    template_dir_override: Path | None,
    strict: bool,
) -> list[Path]:
    """渲染到 tmpdir（含 before/after 钩子）."""
    templates_suffix = (
        templates_suffix
        if templates_suffix is not None
        else template.templates_suffix
    )
    preserve_symlinks = (
        preserve_symlinks
        if preserve_symlinks is not None
        else template.preserve_symlinks
    )

    hook_runner = HookRunner(dst_path, strict=strict)
    context = answers.combined()
    hook_runner.before_renderer_hook(context)

    generated = _render_to(
        answers=answers,
        folder_name=dst_path.name,
        template_dir=template.template_dir,
        subdirectory=template.subdirectory,
        external_template_dir=template_dir_override,
        exclude=template.exclude,
        skip_if_exists=template.skip_if_exists,
        no_render=template.no_render,
        envops=template.envops,
        overwrite=overwrite,
        tmpdir=tmpdir,
        exclude_callback=template.exclude_callback,
        templates_suffix=templates_suffix,
        preserve_symlinks=preserve_symlinks,
        on_exists=hook_runner.on_exists_hook,
    )

    hook_runner.after_renderer_hook(context, generated)
    return generated
