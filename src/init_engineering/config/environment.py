"""ProjectEnvironment — 从 .ae-answers.yml + 代码自检测解析工程环境.

解析流程见 design/v2.0-DESIGN.md §4.5 + design/v2.0-SHARED.md §共享契约.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ProjectEnvironment:
    """项目工程环境。由 init 写入, 其他工具按需读取。

    use_typescript / use_lefthook / has_git 是检测结果的持久化快照,
    同时被 init 流水线 (scaffold_render / scaffold_hooks) 和 ae status 命令消费,
    不是 status-only 属性。
    """

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
    def resolve(cls, project_root: Path) -> ProjectEnvironment:
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
    def _from_answers_file(cls, path: Path) -> ProjectEnvironment:
        from init_engineering._shared.io import read_yaml

        data = read_yaml(path)
        data.pop("_meta", {})
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in field_names})

    @classmethod
    def _from_detection(cls, root: Path) -> ProjectEnvironment:
        return cls(
            project_name=root.resolve().name,
            # A7: package_manager 缺检测结果时默认 "npm"
            package_manager=cls._detect_package_manager(root) or "npm",
            test_runner=cls._detect_test_runner(root) or "",
            use_typescript=(root / "tsconfig.json").exists(),
            use_lefthook=(root / "lefthook.yml").exists(),
            ci_platform=cls._detect_ci(root),
            has_git=(root / ".git").exists(),
        )

    @staticmethod
    def _detect_package_manager(root: Path) -> str | None:
        from init_engineering._shared.detection import detect_package_manager as _detect_pm
        return _detect_pm(root)

    @staticmethod
    def _detect_test_runner(root: Path) -> str | None:
        from init_engineering._shared.detection import detect_test_runner as _detect_tr
        return _detect_tr(root)

    @staticmethod
    def _detect_ci(root: Path) -> str | None:
        from init_engineering._shared.detection import detect_ci_platform as _detect_ci_plat
        return _detect_ci_plat(root)

    # 6 个可客观判定的字段 — _sync_detectable 只处理这些
    _DETECTABLE_FIELDS: frozenset[str] = frozenset([
        "package_manager",
        "test_runner",
        "ci_platform",
        "use_typescript",
        "use_lefthook",
        "has_git",
    ])

    def _sync_detectable(self, root: Path) -> bool:
        """对可判定项执行代码检测，不一致则静默更新。"""
        changed = False
        detections = {
            "package_manager": self._detect_package_manager(root),
            "test_runner": self._detect_test_runner(root),
            "ci_platform": self._detect_ci(root),
            "use_typescript": (root / "tsconfig.json").exists(),
            "use_lefthook": (root / "lefthook.yml").exists(),
            "has_git": (root / ".git").exists(),
        }
        if set(detections.keys()) != set(self._DETECTABLE_FIELDS):
            raise ValueError(
                f"_sync_detectable keys {set(detections.keys())} "
                f"!= _DETECTABLE_FIELDS {set(self._DETECTABLE_FIELDS)}"
            )
        for field_name, detected in detections.items():
            if detected is not None and getattr(self, field_name) != detected:
                setattr(self, field_name, detected)
                changed = True
        return changed

    def warn_undetectable(self, root: Path) -> list[str]:
        """A5: 列出当前无法自动判定的字段 (供 CLI 层 warning 提示).

        Returns:
            不可判定字段名列表 (如 ['package_manager', 'test_runner']).
        """
        undetectable = []
        # 复用检测逻辑 — 若检测结果为 None/False,说明无法判定
        detections = {
            "package_manager": self._detect_package_manager(root),
            "test_runner": self._detect_test_runner(root),
            "ci_platform": self._detect_ci(root),
            "use_typescript": (root / "tsconfig.json").exists() or None,
            "use_lefthook": (root / "lefthook.yml").exists() or None,
            "has_git": (root / ".git").exists() or None,
        }
        for field_name, detected in detections.items():
            if detected is None:
                undetectable.append(field_name)
        return undetectable

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
            from init_engineering._shared.io import read_yaml

            existing = read_yaml(answers_file)
            meta = existing.get("_meta", {})
        else:
            meta = {}
        meta["updated_at"] = datetime.now().astimezone().isoformat()  # PR#5 P2-10: 加 tz
        data["_meta"] = meta
        answers_file.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
