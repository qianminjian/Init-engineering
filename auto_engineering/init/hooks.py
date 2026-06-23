"""TaskRunner — pre/post 钩子执行."""

import subprocess
from pathlib import Path

import jinja2

from .config import Task
from .errors import TaskExecutionError


class TaskRunner:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir

    def run(
        self,
        tasks: list[Task],
        context: dict,
        jinja_env: jinja2.Environment | None = None,
    ) -> None:
        pass
