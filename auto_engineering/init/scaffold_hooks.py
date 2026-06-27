"""InitWorker 钩子执行 — 内置钩子 + 增量合并 + 顶层 init_project()。

从 scaffold.py 拆分（v2.2 Phase I, P2.5）。

模块内容：
- run_builtin_hooks()  : git init / package_manager install / lefthook install / git add+commit
- merge_incremental()   : 增量模式合并（v2.0.5）
- init_project()       : 顶层便利函数
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .errors import TaskExecutionError


def run_builtin_hooks(answers, tmpdir: Path) -> None:
    """执行内置钩子:git init / package_manager install / lefthook / git add+commit。

    拆分自 InitWorker._run_builtin_hooks()，避免 scaffold_phases.py 超过 200 行。
    `answers` 参数是 InitWorker._answers（duck-typed，只需要 .get() 接口）。
    """
    # git init with branch fallback (git < 2.28 compatibility)
    result = subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=tmpdir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if (
            "unknown option" in result.stderr.lower()
            or "unknown switch" in result.stderr.lower()
        ):
            result = subprocess.run(
                ["git", "init"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )
        if result.returncode != 0:
            raise TaskExecutionError("git init", result.returncode, result.stderr)

    pm = answers.get("package_manager")
    if pm:
        result = subprocess.run([pm, "install"], cwd=tmpdir, capture_output=True, text=True)
        if result.returncode != 0:
            raise TaskExecutionError(
                f"{pm} install",
                result.returncode,
                result.stderr,
            )

    if answers.get("use_lefthook"):
        result = subprocess.run(
            ["lefthook", "install"], cwd=tmpdir, capture_output=True, text=True
        )
        if result.returncode != 0:
            raise TaskExecutionError(
                "lefthook install",
                result.returncode,
                result.stderr,
            )

    result = subprocess.run(
        ["git", "add", "-A"],
        cwd=tmpdir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # A3: git add 失败非阻塞 (warning to stderr)
        print(
            f"warning: git add failed: {result.stderr.strip()}", file=sys.stderr
        )

    result = subprocess.run(
        ["git", "commit", "-m", "chore(init): scaffolded by ae init"],
        cwd=tmpdir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # A3: git commit 失败非阻塞 (warning to stderr),不中断后续任务
        print(
            f"warning: git commit failed: {result.stderr.strip()}",
            file=sys.stderr,
        )


def merge_incremental(
    tmpdir: Path,
    dst_path: Path,
    created_files: set[str],
) -> tuple[list[Path], list[Path]]:
    """A1: 增量模式合并 — 逐文件复制,跳过已存在 + .git/。

    拆分自 InitWorker._phase_merge()，避免 scaffold_phases.py 超过 200 行。

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
