"""ae-template.yml 解析."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TEMPLATES_ROOT = Path(__file__).parent / "templates"


@dataclass
class Question:
    var_name: str
    type: str = ""
    help: str = ""
    default: Any = None
    choices: list[str] | dict[str, Any] | None = None
    when: str | bool = True
    validator: str = ""
    secret: bool = False
    multiselect: bool = False
    placeholder: str = ""


@dataclass
class Task:
    cmd: str | list[str]
    when: str | bool = True
    working_directory: str = ""
    extra_vars: dict[str, Any] = field(default_factory=dict)


@dataclass
class TemplateConfig:
    template_dir: Path = field(default_factory=Path)
    min_ae_version: str = "1.0.0"
    templates_suffix: str = ".jinja"
    exclude: list[str] = field(default_factory=list)
    skip_if_exists: list[str] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    tasks_before: list[Task] = field(default_factory=list)
    tasks_after: list[Task] = field(default_factory=list)
    message_before: str = ""
    message_after: str = ""

    @classmethod
    def load(cls, project_type: str) -> "TemplateConfig":
        return cls()
