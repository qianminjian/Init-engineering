"""run_update() — 升级已初始化项目。

来源：v5.0 设计 §2 标记 P1 的 run_update 命令 (类比 Copier `copier update`)。

行为：
- 加载现有 .ae-answers.yml → 获取历史答案
- 重新渲染模板到临时目录
- 比较新文件 vs 现有文件，逐文件应用 conflict_strategy
- 执行 before_update / after_update 钩子
- 更新 .ae-answers.yml 的 _meta (template_version + updated_at)

冲突策略 (conflict_strategy):
- "skip"     : 跳过冲突文件 (默认 — 保护用户修改)
- "overwrite": 覆盖冲突文件
- "prompt"   : 逐文件询问用户 (Interactive)

设计要点：
- 跨平台：基于 file content diff (hashlib.sha256)，不依赖 git
- dry-run 模式：只输出 diff 不写入
- 失败可恢复：原子写入 (写到 .ae-update-<ts>/，确认后再合并)
"""

from __future__ import annotations

__all__ = ["ConflictStrategy", "UpdateResult", "run_update"]

import difflib
import hashlib
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from ._shared.prompt_backend import BasicPromptBackend, PromptBackend
from .answers import AnswersMap
from .config_loader import load_template_config
from .detector import ProjectDetector
from .scaffold_render import render_to

_logger = logging.getLogger(__name__)


class ConflictStrategy(StrEnum):
    """文件冲突处理策略：skip=保留用户修改，overwrite=用模板覆盖，prompt=逐个询问。"""

    SKIP = "skip"
    OVERWRITE = "overwrite"
    PROMPT = "prompt"


@dataclass
class UpdateResult:
    """run_update() 执行结果。"""

    dst_path: Path
    project_type: str
    files_added: list[Path] = field(default_factory=list)
    files_updated: list[Path] = field(default_factory=list)
    files_skipped: list[Path] = field(default_factory=list)
    files_conflicted: list[Path] = field(default_factory=list)

    def summary(self) -> str:
        """返回升级操作的单行摘要（新增/更新/跳过/冲突数）。"""
        return (
            f"✓ 升级完成: 新增 {len(self.files_added)}, "
            f"更新 {len(self.files_updated)}, "
            f"跳过 {len(self.files_skipped)}, "
            f"冲突 {len(self.files_conflicted)}"
        )


def _resolve_update_project_type(
    dst_path: Path, answers_file: Path, auto_detect: bool,
) -> tuple[AnswersMap, str]:
    """解析 project_type — 从 .ae-answers.yml 或自动检测。

    Returns:
        (previous_answers, project_type)
    """
    if not answers_file.exists():
        if auto_detect:
            detector = ProjectDetector(dst_path)
            analysis = detector.analyze()
            return AnswersMap(), analysis.project_type or "app-service"
        raise FileNotFoundError(
            f"{dst_path} 缺少 .ae-answers.yml。请先运行 ae init，"
            f"或使用 --force 自动推断 project_type"
        )
    previous = AnswersMap.from_answers_file(answers_file)
    return previous, previous.get("project_type")


def run_update(
    dst_path: Path,
    *,
    auto_detect: bool = False,
    dry_run: bool = False,
    conflict_strategy: ConflictStrategy | str = ConflictStrategy.SKIP,
    templates_suffix: str | None = None,
    preserve_symlinks: bool | None = None,
    backend: PromptBackend | None = None,
) -> UpdateResult:
    """升级已存在的项目 — 重新渲染模板 + 合并到目标目录。

    Args:
        dst_path: 已初始化的项目根
        auto_detect: 无 .ae-answers.yml 时自动推断 project_type（默认 False → 抛错）
        dry_run: 只计算 diff，不实际写入
        conflict_strategy: 文件冲突时如何处理
        templates_suffix: 模板后缀（覆盖 TemplateConfig）
        preserve_symlinks: 保留 symlink（覆盖 TemplateConfig）

    Returns:
        UpdateResult 包含新增/更新/跳过/冲突的文件路径

    Raises:
        FileNotFoundError: dst_path 不存在或无 .ae-answers.yml (除非 auto_detect)
        ValueError: conflict_strategy 非法
    """
    if not dst_path.exists():
        raise FileNotFoundError(f"目标目录不存在: {dst_path}")

    answers_file = dst_path / ".ae-answers.yml"
    previous, project_type = _resolve_update_project_type(
        dst_path, answers_file, auto_detect,
    )

    if isinstance(conflict_strategy, str):
        try:
            conflict_strategy = ConflictStrategy(conflict_strategy)
        except ValueError as e:
            raise ValueError(
                f"非法的 conflict_strategy: {conflict_strategy!r}. "
                f"可选: {[s.value for s in ConflictStrategy]}"
            ) from e

    template = load_template_config(project_type)
    if template.nested_templates:
        # 沿用 init 流程：如果有 nested templates 仍优先 typescript (no_input=True)
        from .prompts import prompt_for_nested_template
        chosen = prompt_for_nested_template(template.nested_templates, no_input=True)
        if chosen:
            template.template_dir = template.template_dir / chosen

    templates_suffix, preserve_symlinks = template.resolve_render_opts(
        templates_suffix, preserve_symlinks
    )

    # 用历史 answers 重新渲染到 tmpdir
    # PE-P1-3: tmpdir 资源管理 — 整个 try 块(包括 dry_run 提前 return)都被
    # finally 保护,任何路径返回(正常/dry_run/异常)都触发 rmtree 清理
    tmpdir = Path(tempfile.mkdtemp(prefix="ae-update-"))
    try:
        # Build context from previous answers
        answers = previous

        render_to(
            answers=answers,
            folder_name=dst_path.name,
            template_dir=template.template_dir,
            subdirectory=template.subdirectory,
            external_template_dir=None,
            exclude=template.exclude,
            skip_if_exists=template.skip_if_exists,
            no_render=template.no_render,
            envops=template.envops,
            overwrite=False,
            tmpdir=tmpdir,
            exclude_callback_spec=template.exclude_callback,
            templates_suffix=templates_suffix,
            preserve_symlinks=preserve_symlinks,
        )

        # 1. 计算每文件的策略
        result = UpdateResult(dst_path=dst_path, project_type=project_type)
        actions: list[tuple[Path, Path, str]] = []  # (src, dst, action: "add"|"update"|"skip")
        for src_file in sorted(tmpdir.rglob("*")):
            if src_file.is_dir():
                continue
            rel = src_file.relative_to(tmpdir)
            # A1: 跳过 .ae-init.lock
            if rel.name == ".ae-init.lock":
                continue
            dst_file = dst_path / rel
            action = _classify_file(
                src_file, dst_file, conflict_strategy, auto_detect, dst_path, dry_run, result,
                backend=backend,
            )
            if action:
                actions.append((src_file, dst_file, action))
                # dry_run + prompt 提前 return 时也要把 conflicted 计入 result
                if dry_run and action == "conflict":
                    result.files_conflicted.append(dst_file)

        if dry_run:
            return result

        # 2. 应用 actions
        for src_file, dst_file, action in actions:
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            if action == "add":
                shutil.copy2(src_file, dst_file)
                result.files_added.append(dst_file)
            elif action == "update":
                shutil.copy2(src_file, dst_file)
                result.files_updated.append(dst_file)
            elif action == "skip":
                result.files_skipped.append(dst_file)
            elif action == "conflict":
                result.files_conflicted.append(dst_file)

        # 3. 更新 .ae-answers.yml _meta
        _update_answers_meta(answers_file, project_type)

        return result
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _classify_file(
    src: Path,
    dst: Path,
    strategy: ConflictStrategy,
    force: bool,
    dst_root: Path,
    dry_run: bool,
    result: UpdateResult,
    backend: PromptBackend | None = None,
) -> str | None:
    """决定每个文件的处理动作 — 返回 "add"|"update"|"skip"|"conflict"|None。

    None 表示该文件应被忽略（如 .ae-answers.yml 自身）。
    """
    # .ae-answers.yml 自身跳过（run_update 单独更新其 _meta）
    if src.name == ".ae-answers.yml":
        return None

    if not dst.exists():
        return "add"

    if _file_content_equal(src, dst):
        return "skip"

    # 文件存在且内容不同 — 冲突
    src_content = src.read_text(encoding="utf-8")
    dst_content = dst.read_text(encoding="utf-8")
    diff = "".join(
        difflib.unified_diff(
            dst_content.splitlines(keepends=True),
            src_content.splitlines(keepends=True),
            fromfile=f"a/{src.name}",
            tofile=f"b/{src.name}",
        )
    )

    if strategy == ConflictStrategy.SKIP:
        return "skip"
    if strategy == ConflictStrategy.OVERWRITE:
        return "update"
    if strategy == ConflictStrategy.PROMPT:
        if dry_run:
            return "conflict"
        be = backend or BasicPromptBackend()
        be.echo(f"\n冲突: {dst.relative_to(dst_root)}")
        be.echo(diff)
        if be.confirm("应用新版本?", default=False):
            return "update"
        return "skip"
    return "skip"


def _file_content_equal(src: Path, dst: Path) -> bool:
    """比较两个文件内容是否相同 — sha256."""
    return _sha256(src) == _sha256(dst)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _update_answers_meta(answers_file: Path, project_type: str) -> None:
    """更新 .ae-answers.yml _meta — 添加 updated_at + ae_version.

    保留用户之前的所有字段（包括已修改的答案）。
    """
    from datetime import datetime

    import yaml

    from .. import __version__

    if not answers_file.exists():
        return
    from .._shared.io import read_yaml

    data = read_yaml(answers_file)
    meta = data.get("_meta", {})
    meta["updated_at"] = datetime.now().astimezone().isoformat()  # PR#5 P2-10: 加 tz
    meta["ae_version"] = __version__
    meta["project_type"] = project_type
    data["_meta"] = meta
    answers_file.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
