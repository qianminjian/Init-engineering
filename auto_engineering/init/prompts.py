"""InteractivePrompt — 交互式问答."""

import click

from .config import Question
from .answers import AnswersMap


class InteractivePrompt:
    def __init__(self, questions: list[Question], answers: AnswersMap):
        self.questions = questions
        self.answers = answers

    def run(self) -> AnswersMap:
        return self.answers


def prompt_for_project_type(available_types: list[str]) -> str:
    return click.prompt(
        "请选择项目类型",
        type=click.Choice(available_types),
        show_choices=True,
    )
