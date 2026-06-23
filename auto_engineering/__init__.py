"""Auto-Engineering — 团队级 Loop 工程 + 多 Agent 协作.

架构:
    Python 控制流（确定性）        LLM 调用（智能）
    ┌──────────────────────┐     ┌──────────────────┐
    │ engine/loop.py        │     │ agents/           │
    │   while True:         │────→│   architect.py   │
    │     tick()            │     │   developer.py   │
    │     agent.execute()   │     │   critic.py      │
    │     gates.check()     │←────│                  │
    │     after_tick()      │     └──────────────────┘
    └──────────────────────┘

命令:
    ae init <project>         项目环境初始化
    ae dev-loop <requirement> 单需求开发循环
    ae status                 查看当前进度
"""

__version__ = "0.1.0"
