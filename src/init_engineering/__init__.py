"""Init-Engineering — Agent Skill 模式项目环境初始化工具.

两种初始化模式：
    存量项目：通过代码分析自动识别项目类型、依赖、配置，自动化初始化
    新项目：向导式询问确认方向，生成定制化项目骨架

命令:
    ae init <project>         项目环境初始化
"""

# v1.0 — 单一版本号：包版本与模板引擎版本统一。
# 所有 ae-engineering 副本（CLI、模板引擎、AE_PHASE 钩子）必须
# 引用本变量，避免版本漂移。详见 design/BEACON.md 设计决策 #5。
__version__ = "1.0.0"

__all__ = ["__version__"]
