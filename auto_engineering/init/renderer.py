"""TemplateRenderer — Jinja2 双层渲染引擎."""

import shutil
from pathlib import Path

import jinja2


class TemplateRenderer:
    TEMPLATE_SUFFIX = ".jinja"

    def __init__(
        self,
        template_dirs: list[Path],
        context: dict,
        exclude: list[str] | None = None,
        skip_if_exists: list[str] | None = None,
        overwrite: bool = False,
    ):
        self.template_dirs = template_dirs
        self.context = context
        self.exclude = exclude or []
        self.skip_if_exists = skip_if_exists or []
        self.overwrite = overwrite
        self.env = jinja2.Environment(keep_trailing_newline=True)

    def render_to(self, dst_dir: Path) -> list[Path]:
        return []
