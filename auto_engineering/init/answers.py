"""AnswersMap — 5 层优先级答案解析."""

from collections import ChainMap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

BUILTIN_VARS = {"_ae_version": "1.0.0"}


@dataclass
class AnswersMap:
    cli_overrides: dict = field(default_factory=dict)
    interactive: dict = field(default_factory=dict)
    previous: dict = field(default_factory=dict)
    defaults: dict = field(default_factory=dict)
    builtins: dict = field(default_factory=lambda: BUILTIN_VARS.copy())
    hidden: set = field(default_factory=set)

    def get(self, key: str) -> Any:
        for layer in [self.cli_overrides, self.interactive, self.previous, self.defaults, self.builtins]:
            val = layer.get(key)
            if val is not None:
                return val
        raise KeyError(key)

    def combined(self) -> dict:
        return dict(ChainMap(
            self.cli_overrides, self.interactive, self.previous,
            self.defaults, self.builtins,
        ))

    def hide(self, key: str) -> None:
        self.hidden.add(key)

    def save_partial(self, path: Path | None = None) -> Path:
        if path is None:
            path = Path.home() / ".ae-partial-answers.yml"
        path.write_text(yaml.dump({
            "_meta": {"saved_at": datetime.now().isoformat(), "partial": True},
            **self.interactive,
        }))
        return path

    @classmethod
    def from_answers_file(cls, path: Path) -> "AnswersMap":
        data = yaml.safe_load(path.read_text()) or {}
        meta = data.pop("_meta", {})
        return cls(previous=data)

    def to_answers_file(self) -> dict:
        result = {
            "_meta": {"ae_version": "1.0.0", "created_at": datetime.now().isoformat()},
        }
        for key, value in self.combined().items():
            if key.startswith("_") or key in self.hidden:
                continue
            if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                result[key] = value
        return result

    def write_to(self, dst: Path) -> None:
        with open(dst, "w") as f:
            yaml.dump(self.to_answers_file(), f, allow_unicode=True)

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        try:
            self.get(key)
            return True
        except KeyError:
            return False
