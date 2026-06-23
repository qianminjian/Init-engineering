"""init/dev-loop 共享契约 — 从 .ae-answers.yml + 代码自检测解析工程环境.

解析流程见 design/v1.0-DESIGN.md §4.5.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ProjectEnvironment:
    """项目工程环境。由 init 写入，dev-loop 消费。"""

    project_name: str = ""
    project_description: str = ""
    project_type: str = ""
    package_manager: str = ""
    test_runner: str = ""
    use_typescript: bool = False
    use_lefthook: bool = False
    ci_platform: str | None = None
    has_git: bool = True

    @classmethod
    def resolve(cls, project_root: Path) -> "ProjectEnvironment":
        """从 .ae-answers.yml + 代码自检测 解析工程环境。"""
        answers_file = project_root / ".ae-answers.yml"

        if answers_file.exists():
            env = cls._from_answers_file(answers_file)
            changed = env._sync_detectable(project_root)
            if changed:
                env.save(project_root)
            return env
        else:
            env = cls._from_detection(project_root)
            env.save(project_root)
            return env

    @classmethod
    def _from_answers_file(cls, path: Path) -> "ProjectEnvironment":
        data = yaml.safe_load(path.read_text()) or {}
        meta = data.pop("_meta", {})
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in field_names})

    @classmethod
    def _from_detection(cls, root: Path) -> "ProjectEnvironment":
        return cls(
            project_name=root.resolve().name,
            package_manager=cls._detect_package_manager(root) or "",
            test_runner=cls._detect_test_runner(root) or "",
            use_typescript=(root / "tsconfig.json").exists(),
            use_lefthook=(root / "lefthook.yml").exists(),
            ci_platform=cls._detect_ci(root),
            has_git=(root / ".git").exists(),
        )

    @staticmethod
    def _detect_package_manager(root: Path) -> str | None:
        for fname, pm in [
            ("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"),
            ("package-lock.json", "npm"), ("bun.lock", "bun"),
            ("poetry.lock", "poetry"), ("uv.lock", "uv"),
        ]:
            if (root / fname).exists():
                return pm
        return None

    @staticmethod
    def _detect_test_runner(root: Path) -> str | None:
        for cfg, runner in [
            ("vitest.config.ts", "vitest"), ("vitest.config.js", "vitest"),
            ("jest.config.ts", "jest"), ("jest.config.js", "jest"),
            ("pytest.ini", "pytest"), ("pyproject.toml", None),
        ]:
            if cfg == "pyproject.toml" and (root / cfg).exists():
                return "pytest"
            if (root / cfg).exists():
                return runner
        return None

    @staticmethod
    def _detect_ci(root: Path) -> str | None:
        if (root / ".github/workflows").exists():
            return "github"
        if (root / ".gitlab-ci.yml").exists():
            return "gitlab"
        return None

    def _sync_detectable(self, root: Path) -> bool:
        """对可判定项执行代码检测，不一致则更新。"""
        changed = False
        detections = {
            "package_manager": self._detect_package_manager(root),
            "test_runner": self._detect_test_runner(root),
            "ci_platform": self._detect_ci(root),
            "use_typescript": (root / "tsconfig.json").exists(),
            "use_lefthook": (root / "lefthook.yml").exists(),
            "has_git": (root / ".git").exists(),
        }
        for field_name, detected in detections.items():
            if detected is not None and getattr(self, field_name) != detected:
                setattr(self, field_name, detected)
                changed = True
        return changed

    def save(self, project_root: Path) -> None:
        """写回 .ae-answers.yml。"""
        from datetime import datetime
        answers_file = project_root / ".ae-answers.yml"
        data = {
            f.name: getattr(self, f.name)
            for f in self.__dataclass_fields__.values()
            if not f.name.startswith("_")
        }
        if answers_file.exists():
            existing = yaml.safe_load(answers_file.read_text()) or {}
            meta = existing.get("_meta", {})
        else:
            meta = {}
        meta["updated_at"] = datetime.now().isoformat()
        data["_meta"] = meta
        answers_file.write_text(yaml.dump(data, allow_unicode=True))
