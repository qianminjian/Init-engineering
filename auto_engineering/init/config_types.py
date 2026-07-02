"""ae-template.yml 类型定义 — Question / Task / 共享常量。

参考来源：
- copier/_user_data.py:136-295 — Question dataclass 定义
- copier/_template.py:162-188 — Task dataclass 定义

本模块只放类型与常量，YAML 解析逻辑见 config.py 的 TemplateConfig。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jinja2
import yaml

# ─── 常量 ────────────────────────────────────────────────────────────────────

TEMPLATES_ROOT = Path(__file__).parent / "templates"

# 默认排除列表（来源: Copier _template.py:DEFAULT_EXCLUDE）
DEFAULT_EXCLUDE = [
    "ae-template.yml",
    "ae-template.yaml",
    "ae-feature.yml",
    "*.tmpl",
    "~*",
    "*.py[co]",
    "__pycache__",
    ".git",
    ".DS_Store",
    ".svn",
]

DEFAULT_TEMPLATES_SUFFIX = ".jinja"


# ─── Question ─────────────────────────────────────────────────────────────────


@dataclass
class Question:
    """单个交互式问题。

    参考 Copier _user_data.py:137-221 的 Question dataclass。

    关键设计：
    - type 可从 default 值自动推断（default=True → type="bool"）
    - when/validator 为 Jinja2 模板字符串，渲染后判断
    - choices 支持 list[str] 或 dict[label, value]
    - secret=True 时 default 不能为空（Copier 规则）
    """

    var_name: str  # 变量名，对应 ae-template.yml 的 key
    type: str = ""  # str|bool|int|float|json|yaml|choice，空字符串=自动推导
    help: str = ""  # 提示文本
    default: Any = None  # 默认值
    choices: list[str] | dict[str, Any] | None = None
    when: str | bool = True  # Jinja2 条件
    validator: str = ""  # Jinja2 校验模板，空=不校验
    secret: bool = False
    multiselect: bool = False
    placeholder: str = ""

    def get_type_name(self) -> str:
        """返回最终类型名。空字符串时从 default 类型推导。

        来源：Copier _user_data.py Question._check_type() 类型推导逻辑。
        """
        if self.type:
            return self.type
        default_type_map = {
            bool: "bool",
            int: "int",
            float: "float",
            list: "json" if self.multiselect else "yaml",
            dict: "json",
            str: "str",
        }
        mapped = default_type_map.get(type(self.default))
        if mapped:
            return mapped
        if self.default is not None:
            return "yaml"
        return "str"

    def render_when(self, context: dict, jinja_env: jinja2.Environment) -> bool:
        """渲染 when 条件。来源：Copier _user_data.py Question.get_when()"""
        if isinstance(self.when, bool):
            return self.when
        tpl = jinja_env.from_string(str(self.when))
        result = tpl.render(**context).strip()
        return result.lower() not in ("false", "no", "0", "")

    def render_validator(self, value: Any, context: dict, jinja_env: jinja2.Environment) -> str:
        """渲染 validator 模板，返回错误信息或空字符串。

        来源：Copier _user_data.py Question._get_answer_validation_error()
        """
        if not self.validator:
            return ""
        tpl = jinja_env.from_string(self.validator)
        return tpl.render(**{**context, self.var_name: value}).strip()

    def cast_answer(self, raw: str) -> Any:
        """将用户输入的字符串转为目标类型。

        来源：Copier _user_data.py CAST_STR_TO_NATIVE 字典。
        支持：str / bool / int / float / json / yaml / choice 七种类型。
        """
        type_name = self.get_type_name()
        if type_name == "str":
            return raw
        if type_name == "bool":
            # click.confirm 返回 bool 值，click.prompt 返回字符串
            if isinstance(raw, bool):
                return raw
            return raw.strip().lower() in ("yes", "y", "true", "t", "1")
        if type_name == "int":
            return int(raw)
        if type_name == "float":
            return float(raw)
        if type_name in ("json", "yaml"):
            if not raw.strip():
                return None
            try:
                return yaml.safe_load(raw)
            except yaml.YAMLError as e:
                raise ValueError(f"YAML 解析失败: {e}") from e
        if type_name == "choice":
            if self.multiselect and isinstance(raw, str):
                # multiselect choice 用户输入是 YAML list 字符串，转为 Python list
                if not raw.strip():
                    return []
                try:
                    return yaml.safe_load(raw)
                except yaml.YAMLError as e:
                    raise ValueError(f"多选答案 YAML 解析失败: {e}") from e
            return raw
        return raw


# ─── Task ──────────────────────────────────────────────────────────────────────


@dataclass
class Task:
    """单个钩子命令。

    参考 Copier _template.py:162-188 Task dataclass。

    - cmd: 命令字符串（可含 Jinja2 变量）或命令列表（安全模式，无 shell 注入）
    - when: Jinja2 条件，False → 跳过
    - working_directory: 相对于项目根目录的执行路径
    - extra_vars: 注入为 Jinja 渲染变量（_ 前缀）和环境变量（大写）
    - shell: 是否启用 shell 模式（默认 False，list 命令始终 False）
      启用后 Jinja2 渲染结果通过 shell 执行（支持 && || | 等），
      但存在 Jinja2 沙箱穿透后的命令注入风险。仅在需要 shell
      特性时显式设为 True。
    """

    cmd: str | list[str]
    when: str | bool = True
    working_directory: str = ""
    extra_vars: dict[str, Any] = field(default_factory=dict)
    shell: bool = False
