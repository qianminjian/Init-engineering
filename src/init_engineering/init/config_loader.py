"""TemplateConfig YAML 加载逻辑 — ae-template.yml 解析 + !include 安全校验。

使用方: scaffold_phases.py → InitWorker._load_config。
类型定义见 config_types.py。
"""

from __future__ import annotations

from pathlib import Path
import logging
from typing import Any

import yaml

_logger = logging.getLogger(__name__)

from ._shared.path_utils import is_path_under_any_root
from .config_types import DEFAULT_EXCLUDE, TEMPLATES_ROOT, Question, Task
from .errors import ConfigFileError, ConfigLoaderSecurityError


def load_template_config(project_type: str, sandbox_roots: list[str] | None = None) -> "TemplateConfig":  # noqa: F821
    """加载并解析 ae-template.yml，返回 TemplateConfig 实例。

    完整流程：
    1. 读取 templates/<project_type>/ae-template.yml
    2. 解析 !include 标签（递归合并）
    3. 分离 _ 前缀配置与问题定义
    4. 解析 _tasks 列表到 tasks_before / tasks_after
    5. 处理 nested_templates 子模板
    6. 构造 TemplateConfig

    Args:
        project_type: 项目类型 (templates/<project_type>/)
        sandbox_roots: 可选的 sandbox 根目录列表。若非空, !include 路径必须
            在这些根目录下 (realpath 归一化防 symlink 穿越)。
    """
    from .config_types import TemplateConfig

    config_path = TEMPLATES_ROOT / project_type / "ae-template.yml"
    if not config_path.exists():
        raise ConfigFileError(f"模板配置文件不存在: {config_path}")

    # 支持 !include 标签合并（来源: Copier _template.py:92-106 YAML !include）
    raw = _load_yaml_with_includes(config_path, sandbox_roots=sandbox_roots)

    # 分离 _ 前缀配置与问题定义（来源：Copier filter_config）
    questions_data: dict[str, Any] = {}
    config_kwargs: dict[str, Any] = {}
    for key, value in raw.items():
        if key.startswith("_"):
            config_key = key[1:]  # 去 _ 前缀
            if config_key == "tasks":
                if not isinstance(value, list):
                    raise ConfigFileError(
                        f"_tasks 必须是 list, 实际是 {type(value).__name__}"
                    )
                _parse_tasks(value, config_kwargs)
            elif config_key == "exclude":
                config_kwargs["exclude"] = DEFAULT_EXCLUDE + list(value)
            elif config_key == "skip_if_exists":
                config_kwargs["skip_if_exists"] = list(value)
            elif config_key == "envops":
                config_kwargs["envops"] = {**config_kwargs.get("envops", {}), **value}
            elif config_key == "no_render":
                config_kwargs["no_render"] = list(value)
            elif config_key == "external_data":
                if not isinstance(value, dict):
                    raise ConfigFileError(
                        f"_external_data 必须是 mapping, 实际是 {type(value).__name__}"
                    )
                config_kwargs["external_data"] = dict(value)
            elif config_key == "nested_templates":
                if not isinstance(value, dict):
                    raise ConfigFileError(
                        f"_nested_templates 必须是 mapping, 实际是 {type(value).__name__}"
                    )
                config_kwargs["nested_templates"] = dict(value)
            elif config_key == "subdirectory":
                config_kwargs["subdirectory"] = str(value)
            elif config_key == "templates_suffix":
                config_kwargs["templates_suffix"] = str(value)
            elif config_key == "min_ae_version":
                config_kwargs["min_ae_version"] = str(value)
            elif config_key == "message_before":
                config_kwargs["message_before"] = str(value)
            elif config_key == "message_after":
                config_kwargs["message_after"] = str(value)
            else:
                _logger.warning(
                    "未知的 _ 前缀配置键: _%s (值=%s) — 拼写错误? 将被忽略。"
                    "已知键: tasks/exclude/skip_if_exists/envops/no_render/"
                    "external_data/nested_templates/subdirectory/templates_suffix/"
                    "min_ae_version/message_before/message_after",
                    config_key, value,
                )
                config_kwargs[config_key] = value
        else:
            questions_data[key] = value

    # 嵌套模板选择由 InteractivePrompt 处理 (prompts.py:prompt_for_nested_template)

    questions = _parse_questions(questions_data)
    return TemplateConfig(template_dir=config_path.parent, questions=questions, **config_kwargs)


def _load_yaml_with_includes(config_path: Path, sandbox_roots: list[str] | None = None) -> dict:
    """加载 YAML 并解析 !include 标签。

    来源：Copier _template.py:92-106 _include() + Loader。
    !include 后接相对路径（相对于当前配置文件），支持 glob 模式。
    被 include 的文件内容与当前文件合并。

    v2.5 P2-C-1: glob 解析后验证每个匹配 path 在 config_path.parent
    (realpath) 内, 防止恶意模板 `!include ../../../*.yml` 越界读到
    模板目录外的文件 (例如 ~/.ssh/, /etc/ 等).

    v2.5 P1-3: 若 sandbox_roots 非空,进一步验证 path 在 sandbox_roots 内.
    sandbox_roots=None (默认) 跳过第二层检查,保持向后兼容.

    PR#4 P1-5 安全加固: sandbox_roots=None 时 fallback 到 [config_path.parent]
    作为最小安全边界. 防止外部模板 `!include` 越界读取同磁盘敏感文件.
    调用方仍可通过传 sandbox_roots=[] (空列表) 显式走严格模式.
    """
    import os

    # PR#4 P1-5: 默认 fallback 到模板目录自身 — 之前完全跳过二层检查是过度宽松
    effective_sandbox_roots = (
        sandbox_roots if sandbox_roots is not None else [config_path.parent]
    )

    class _IncludeLoader(yaml.SafeLoader):
        pass

    def _include(loader: yaml.Loader, node: yaml.Node) -> Any:
        include_spec = str(loader.construct_scalar(node))
        full_paths = list(config_path.parent.glob(include_spec))
        results: list[dict] = []
        for path_obj in full_paths:
            # P2-C-1: 验证 path 在 config_path.parent 内 (realpath 防御 symlink)
            config_parent_real = os.path.realpath(config_path.parent)
            path_real = os.path.realpath(path_obj)
            root_prefix = (
                config_parent_real
                if config_parent_real.endswith(os.sep)
                else config_parent_real + os.sep
            )
            if not (
                path_real == config_parent_real
                or path_real.startswith(root_prefix)
            ):
                raise ConfigLoaderSecurityError(
                    f"!include glob '{include_spec}' 匹配到模板目录外的文件: "
                    f"{path_obj} (resolved: {path_real}). 模板目录: {config_parent_real}. "
                    f"Refusing to load (potential template injection)."
                )
            # P1-3: sandbox_roots 检查
            # sandbox_roots=None → 不检查 (向后兼容)
            # sandbox_roots=[] → 严格模式,不允许任何 include
            # sandbox_roots=["/a", "/b"] → 只允许在这些目录内
            # PR#4 P1-5: 默认 fallback 到 [config_path.parent] — 永不 None 跳过
            if not effective_sandbox_roots:
                raise ConfigLoaderSecurityError(
                    f"!include '{include_spec}' not allowed: "
                    f"sandbox_roots is empty (strict mode). "
                    f"Refusing to load (potential template injection)."
                )
            if not is_path_under_any_root(path_obj, effective_sandbox_roots):
                raise ConfigLoaderSecurityError(
                    f"!include path '{path_obj}' (resolved: {path_real}) is not under "
                    f"sandbox roots {effective_sandbox_roots}. Refusing to load "
                    f"(potential template injection)."
                )
            # P2-16: 显式 utf-8 — 防止 Windows GBK 默认编码破坏中文 yaml
            with open(path_obj, encoding="utf-8") as fh:
                for doc in yaml.safe_load_all(fh):
                    if doc:
                        results.append(doc)
        if not results:
            return None
        if len(results) == 1:
            return results[0]
        return results

    _IncludeLoader.add_constructor("!include", _include)

    # P2-16: 显式 utf-8
    with open(config_path, encoding="utf-8") as fh:
        all_docs = list(yaml.load_all(fh, Loader=_IncludeLoader))
        result: dict[str, Any] = {}
        for doc in filter(None, all_docs):
            result.update(doc)
        return result



def _parse_questions(data: dict[str, Any]) -> list[Question]:
    """将 YAML 问题定义转为 Question 对象列表。

    简化格式（来源：Copier filter_config 68-71 行）:
      key: "default value"  →  Question(var_name=key, default="default value")
    完整格式:
      key:
        type: str
        help: "..."
        default: "..."
        ...
    """
    questions: list[Question] = []
    for var_name, raw in data.items():
        if not isinstance(raw, dict):
            raw = {"default": raw}
        q_kwargs = {k: v for k, v in raw.items() if k in Question.__dataclass_fields__}
        questions.append(Question(var_name=var_name, **q_kwargs))
    return questions


def _parse_tasks(tasks_raw: list[dict[str, Any]], config_kwargs: dict[str, Any]) -> None:
    """将 _tasks 列表按默认 stage 分到 tasks_before / tasks_after。

    来源：Copier _template.py filter_config 中的 _tasks 处理。
    stage 默认为 "after"，"before" 阶段的在 v2.0（渲染）前执行。
    """
    before: list[Task] = []
    after: list[Task] = []
    for raw_task in tasks_raw:
        task_kwargs = {k: v for k, v in raw_task.items() if k in Task.__dataclass_fields__}
        task = Task(**task_kwargs)
        stage = raw_task.get("stage", "after")
        if stage == "before":
            before.append(task)
        else:
            after.append(task)
    config_kwargs["tasks_before"] = before
    config_kwargs["tasks_after"] = after
