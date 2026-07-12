"""InitWorker 钩子执行 — 内置钩子。

从 scaffold_phases.py 拆分（v2.2 Phase I, P2.5）。
PR#3 P1-1: merge_incremental 迁出至 phases/finalize.py (消除跨模块延迟 import 循环)。

模块内容：
- run_builtin_hooks()  : git init / package_manager install / lefthook install / git add+commit
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from .config_types import coerce_bool
from .errors import HookExecutionError

if TYPE_CHECKING:
    from .answers import AnswersMap

_logger = logging.getLogger(__name__)

# PE-AUDIT-P0-1: 默认 subprocess 超时(秒) — 防止网络挂死/锁等待导致 ae init 永久 hang.
# 各调用点可单独指定更短超时 (git config/git init/git add/git commit 是快速操作).
# 透传链路: CLI --hook-timeout → InitWorker.hook_timeout → run_tasks_phase.default_timeout
#   → run_builtin_hooks.default_timeout.
DEFAULT_SUBPROCESS_TIMEOUT = 300

# SE-P1-1: 包管理器白名单 — 防止恶意 answers (--from-answers from untrusted) 注入
# 任意命令名 (如 pm='rm' / 'curl evil.com|sh' / 'shutdown')。白名单是单一执行源,
# 与 ae-template.yml choices 一致, 任何添加/删除 PM 须同步更新两端。
_ALLOWED_PACKAGE_MANAGERS = frozenset({
    "npm", "pnpm", "yarn", "bun",  # Node.js
    "uv", "poetry", "pip",          # Python
    "cargo", "go",                   # Rust / Go
})

# PE-P0-1: 每个 PM 的依赖安装命令 — uv 不用 install 用 sync; cargo / go 无独立 install
# 阶段 (build / mod download 时下载), 标 None 跳过
PM_INSTALL_CMD: dict[str, list[str] | None] = {
    "npm": ["npm", "install"],
    "pnpm": ["pnpm", "install"],
    "yarn": ["yarn", "install"],
    "bun": ["bun", "install"],
    # uv sync 默认不含 dev extras, init 后需可跑测试 → 加上 dev
    "uv": ["uv", "sync", "--extra", "dev"],
    "poetry": ["poetry", "install"],
    "pip": ["pip", "install", "-e", "."],
    "cargo": None,                  # cargo build 自动 fetch, 无 install 阶段
    "go": None,                     # go mod download 在 build 时执行, 无 install 阶段
}


def _subprocess_ok(result: subprocess.CompletedProcess | None) -> bool:
    """检查 subprocess 结果是否成功 — result 非 None 且 returncode == 0."""
    return result is not None and result.returncode == 0


def validate_package_manager(pm: str) -> None:
    """SE-P1-1: pm 必须在白名单内 — 不在白名单直接拒绝, 不调用 subprocess.

    Why: 之前 [pm, 'install'] 直接以 pm 为 argv[0], 攻击者可在 answers 文件
    中设置 package_manager='rm' 或 'curl evil.com' 触发 RCE.
    """
    if pm not in _ALLOWED_PACKAGE_MANAGERS:
        raise HookExecutionError(
            command=f"{pm} install",
            process_exit_code=-1,
            stderr=(
                f"package_manager='{pm}' 不在白名单内 (SE-P1-1)."
                f"允许: {sorted(_ALLOWED_PACKAGE_MANAGERS)}."
                f"如需新增 PM, 请同时更新 _ALLOWED_PACKAGE_MANAGERS 与 ae-template.yml choices."
            ),
        )


def run_pm_install_cmd(
    pm: str,
    target_dir: Path,
    *,
    timeout: int = 300,
) -> subprocess.CompletedProcess:
    """验证 PM 白名单并执行安装命令。调用方负责错误报告。

    Returns:
        CompletedProcess — 调用方检查 returncode 决定成功/失败。

    Raises:
        HookExecutionError: PM 不在白名单 (SE-P1-1)。
        FileNotFoundError: PM 可执行文件未找到。
        subprocess.TimeoutExpired: 安装超时。
    """
    validate_package_manager(pm)
    install_cmd = PM_INSTALL_CMD.get(pm)
    if install_cmd is None:
        raise ValueError(f"no install command for '{pm}' (cargo/go have no separate install phase)")
    return subprocess.run(
        install_cmd, cwd=target_dir, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )


def has_package_file(tmpdir: Path, pm: str) -> bool:
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


def _is_pnpm_ignored_builds(stderr: str) -> bool:
    """检测 pnpm v11+ ERR_PNPM_IGNORED_BUILDS — 非致命错误，包已安装，仅构建脚本未执行。"""
    return "ERR_PNPM_IGNORED_BUILDS" in stderr


def _ensure_git_config(project_dir: Path) -> None:
    """确保 git user.email/user.name 在 project_dir 仓库内配置（不污染 --global）。

    B4 安全: 之前用 --global 会修改用户全局 git config, 污染其他项目的 commit author。
    改为 -C project_dir config user.email/name (仅当前仓库有效)。

    PE-AUDIT-P0-1: 加 timeout=10 — git config 是本地 file read,10s 足够;
    无 timeout 在 NFS / 损坏 repo 场景可能挂死。TimeoutExpired 被吞 — 这是
    best-effort 设置,失败用 git 默认 config 也无碍。
    """
    for key, default in [("user.email", "ae@init.local"), ("user.name", "ae init")]:
        try:
            result = subprocess.run(
                ["git", "-C", str(project_dir), "config", key],
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            # best-effort: 跳过, 用 git 全局默认即可
            continue
        if result.returncode != 0 or not result.stdout.strip():
            try:
                subprocess.run(
                    ["git", "-C", str(project_dir), "config", key, default],
                    capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                    timeout=10,
                )
            except subprocess.TimeoutExpired:
                continue


def _git_init(tmpdir: Path, _fail) -> bool:
    """git init with branch fallback (git < 2.28 compatibility)。返回 git_ok。"""
    git_ok = True
    try:
        result = subprocess.run(
            ["git", "init", "-b", "main"],
            cwd=tmpdir, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15,
        )
    except subprocess.TimeoutExpired:
        _fail("git init", -1, "git init timed out after 15s")
        return False
    if not _subprocess_ok(result):
        if "unknown option" in result.stderr.lower() or "unknown switch" in result.stderr.lower():
            try:
                result = subprocess.run(
                    ["git", "init"], cwd=tmpdir, capture_output=True,
                    text=True, encoding="utf-8", errors="replace", timeout=15,
                )
            except subprocess.TimeoutExpired:
                _fail("git init", -1, "git init timed out after 15s")
                return False
        if not _subprocess_ok(result):
            _fail("git init", result.returncode, result.stderr)
            git_ok = False
    return git_ok


def _pm_install_step(
    answers: AnswersMap, tmpdir: Path,
    timeout: int, quiet: bool, no_install: bool,
    _fail,
) -> None:
    """包管理器安装 — 从 run_builtin_hooks 提取."""
    pm = answers.get("package_manager")
    if no_install and pm:
        if not quiet:
            _logger.info("  (skipping %s install: --no-install flag set)", pm)
        return
    if not pm or not has_package_file(tmpdir, pm):
        if pm and not has_package_file(tmpdir, pm) and not quiet:
            _logger.info("  (skipping %s install: no package file found)", pm)
        return
    if PM_INSTALL_CMD.get(pm) is None:
        if not quiet:
            _logger.info("  (skipping %s install: no separate install phase)", pm)
        return
    try:
        result = run_pm_install_cmd(pm, tmpdir, timeout=timeout)
        if result.returncode != 0:
            cmd_str = " ".join(PM_INSTALL_CMD[pm])
            if _is_pnpm_ignored_builds(result.stderr):
                if not quiet:
                    _logger.warning(
                        "%s: 依赖已安装，但 pnpm 阻止了构建脚本。"
                        " 运行 'pnpm approve-builds' 批准构建后执行 'pnpm install'。",
                        cmd_str,
                    )
            else:
                _fail(cmd_str, result.returncode,
                      f"exit={result.returncode}, run '{cmd_str}' manually")
    except (FileNotFoundError, OSError) as e:
        cmd_str = " ".join(PM_INSTALL_CMD[pm])
        _fail(cmd_str, 127,
              f"'{PM_INSTALL_CMD[pm][0]}' not found ({e}), run '{cmd_str}' manually")
    except subprocess.TimeoutExpired:
        cmd_str = " ".join(PM_INSTALL_CMD[pm])
        _fail(cmd_str, -1, f"{cmd_str} timed out after {timeout}s")


def _git_add_commit_step(tmpdir: Path, git_ok: bool, _fail) -> bool:
    """git add -A + git commit — 从 run_builtin_hooks 提取."""
    if not git_ok:
        return git_ok
    for cmd, label, tmout in [
        (["git", "add", "-A"], "git add", 30),
        (["git", "commit", "-m", "chore(init): scaffolded by ae init"], "git commit", 30),
    ]:
        try:
            result = subprocess.run(
                cmd, cwd=tmpdir, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=tmout,
            )
        except subprocess.TimeoutExpired:
            _fail(label, -1, f"{label} timed out after {tmout}s")
            git_ok = False
            continue
        if not _subprocess_ok(result):
            _fail(label, result.returncode, result.stderr)
            git_ok = False
    return git_ok


def run_builtin_hooks(
    answers: AnswersMap,
    tmpdir: Path,
    strict: bool = False,
    quiet: bool = False,
    no_install: bool = False,
    default_timeout: int | None = None,
) -> None:
    """执行内置钩子:git init / package_manager install / lefthook / git add+commit。

    strict=True 时任意步骤失败抛 HookExecutionError，否则 warning 继续。
    """
    timeout = default_timeout if default_timeout is not None else DEFAULT_SUBPROCESS_TIMEOUT
    _ensure_git_config(tmpdir)

    def _fail(cmd: str, rc: int, stderr: str) -> bool:
        if strict:
            raise HookExecutionError(command=cmd, process_exit_code=rc, stderr=stderr)
        if not quiet:
            _logger.warning("%s failed: %s", cmd, stderr.strip())
        return True

    git_ok = _git_init(tmpdir, _fail)
    _pm_install_step(answers, tmpdir, timeout, quiet, no_install, _fail)

    if coerce_bool(answers.get("use_lefthook")):
        try:
            result = subprocess.run(
                ["lefthook", "install"], cwd=tmpdir, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=60,
            )
        except subprocess.TimeoutExpired:
            _fail("lefthook install", -1, "lefthook install timed out after 60s")
            result = None
        if result is not None and not _subprocess_ok(result):
            _fail("lefthook install", result.returncode, result.stderr)

    _git_add_commit_step(tmpdir, git_ok, _fail)
