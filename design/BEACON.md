> 来源：@design/INDEX.md | 创建：2026-06-24 | 更新：2026-06-25 | 阶段：v2.0 全部完成（v1.0 init/dev-loop 基线 + v1.1 修复 + v2.0 多 Agent 并发）

## 目标与成功标准

1. **ae init 命令**：用户输入 `ae init my-project --type app-service`，产出完整可运行的项目骨架
2. **ae dev-loop 命令**：用户输入需求文本，系统自动完成 Architect → Developer → Critic 循环，输出代码变更 + 测试通过
3. **确定性 Guardrail**：每个 Stage 前后自动检查 Guardrail 条件（结构化 GuardrailResult，pass/block/drop/retry 四态）
4. **Checkpoint 恢复**：中断后可从 checkpoint 恢复，不丢失进度
5. **结构化 Agent 输出**：Agent 输出按 output_schema 约束，双层防御解析（schema + regex fallback）
6. **多 Agent 并发**（v2.0）：Round 内多 Agent asyncio.gather 并行执行，文件隔离确定性检查 + 4 级收敛判定 + SQLite Checkpoint 持久化
7. **7 道 Gate**（v2.0）：safety/lint/type_check/contract/test/coverage/build 全链路质量保证

## 范围边界

**做：**
- init: 多层模板目录组合（_shared + _features + type）、from-answers 恢复、路径穿越防护、内置钩子错误传播
- LoopEngine（while True + tick/after_tick）+ StageGraph + AgentRuntime
- 单 Agent 串行执行、SQLite checkpoint、Claude API output_json
- GuardrailChain + RetryPolicy + CancellationToken + ErrorCode 体系
- **v2.0：Channel 系统（LastValue/Accumulating/Barrier）+ Task DAG + check_file_isolation + Round asyncio.gather + 7 道 Gate + CLI v2（ae checkpoint v2 / ae status 增强）**

**不做：**
- init: 增量模式、嵌套模板交互选择、远程模板（v1.1+）
- ~~多 Agent 并行（v2.0）~~ → **已在 v2.0 实现**
- ~~7 道 Gate~~ → **已在 v2.0 实现**
- ~~Channel 系统~~ → **已在 v2.0 实现**
- 多 LLM Provider、Web UI
- CrewAI 风格 Memory/RAG、AutoGen 风格 Pub/Sub、Jinja2 用于 Task 描述

## 设计决策

| # | 决策 | 理由 | 日期 |
|---|------|------|------|
| 1 | 三层架构：LoopEngine → StageGraph → AgentRuntime | 控制流/路由/执行三者职责分离 | 2026-06-24 |
| 2 | 全链路 async | 统一异步模型 | 2026-06-24 |
| 3 | dataclass 非 Pydantic | 核心模型轻量，LLM 输出用 output_schema | 2026-06-24 |
| 4 | GuardrailChain 替代 Gate | 参考 CrewAI GuardrailResult + AutoGen DropMessage | 2026-06-24 |
| 5 | init 审计后优先断路修复 | 3 个断路点使当前 init 代码在真实场景基本不可用 | 2026-06-24 |
| 6 | AnthropicProvider 封装在 llm/ | 不混入 agent 代码，方便测试 mock | 2026-06-24 |
| 7 | Phase 1 编码前先清理现状 | 占位符命名 `DevLoop*` 与 v3.0 `LoopEngine*` 冲突；`crew/contracts/tasks/runtime/registry.py/runtime/messages.py` 应删；SHARED.md 目录结构未同步 v3.0 | 2026-06-24 |
| 8 | render_description 空值整行删除 | v3.0 §3.1 注释承诺"条件逻辑在 render_description 中处理"但未实现；developer 模板 "上一轮审查反馈：{critic_feedback}" 首轮产生空行干扰 LLM | 2026-06-24 |
| 9 | run() 退出前同步 checkpoint.status | v3.0 §2.1 tick() 改 self.status 但不写 checkpoint，LoopResult.status 错位 | 2026-06-24 |
| 10 | developer→critic 边显式注册 | v3.0 §三 build_dev_loop_graph 漏 add_edge，critic 永不调度 | 2026-06-24 |
| 11 | **v2.0 是增量式演进，不是删除式重构** | v1.0-LOOP.md §八 提议删除 engine/crew/runtime/tools 三层；v2.0 实际采取增量路径 — 在 engine/runtime/tools 基础上**新增** loop/ 子系统作为 v2.0 主体，避免重写风险 | 2026-06-25 |
| 12 | **v2.0 删除项取消：保留 engine/runtime/tools 作为旧路径兼容** | Phase 05 决策：CLI 仍 import engine/runtime/tools（旧路径保留），v2.0 loop/ 是叠加而非替代 | 2026-06-25 |
| 13 | **Channel 系统采用 dataclass + 显式 Channel 基类** | v2.0-Analysis-Loop.md §4.4 提议 Pydantic；实际用 dataclass（决策 3 保持一致） | 2026-06-25 |
| 14 | **check_file_isolation 是确定性检查，不是 LLM 自检** | v2.0-Analysis-Loop.md §4.3 原则：Orchestrator 规划阶段 Python 代码检查，文件集冲突则拆分/串行，不依赖 Agent 自觉 | 2026-06-25 |
| 15 | **Gate 3（Contract）单 Agent 跳过，多 Agent 启用** | Phase 04 决策：6 道 Gate 实现 + Gate 3 占位 | 2026-06-25 |

## 当前状态

**阶段：** v2.0 全部完成（v1.0 init/dev-loop 基线 + v1.1 修复 + v2.0 多 Agent 并发 + 7 Gates + CLI v2） — Phase 05 文档同步执行中

**最近动作：**
- 2026-06-25 v2.0 Phase 04 完成（`da759cd`）— 7 道 Gate + CLI v2（ae checkpoint v2 / ae status 增强）+ 27 测试覆盖
- 2026-06-25 v2.0 Phase 03 完成（`23584b6`）— Round asyncio.gather + Orchestrator 主循环 + Task DAG + check_file_isolation
- 2026-06-25 v2.0 Phase 02 完成（`704987d`）— 4 级收敛判定 + SQLite Checkpoint 持久化
- 2026-06-25 v2.0 Phase 01 完成（`3857366`）— Channel 系统 + LoopState 容器
- 2026-06-25 R26 init 模板 design 嵌入（`36d52cb`）+ 文档命名重构（重命名为 v1.0-Design-* / v1.1-Audit-Report / v1.1-Plan-Dev / v2.0-Analysis-Loop）
- 2026-06-25 R26+ pytest 内存管理规则沉淀为产品级最佳实践（`efe8583`）

**下一步：** Phase 05 收尾 → v2.0 完成 → 用户 manual gate（端到端真跑 ANTHROPIC_API_KEY）

**阻塞项：** 无

**v2.0 落地里程碑：**
- Phase 01（c3077bf/3857366/73ee4bc）：Channel 系统（LastValue/Accumulating/Barrier）+ LoopState dataclass 容器
- Phase 02（1dd2ff8/4038ca2/704987d）：ConvergenceJudge 4 级判定 + SQLiteCheckpointStore 事务持久化 + resume 校验
- Phase 03（4f3d932/3a3edd1/23584b6）：TaskDAG + topological_sort + check_file_isolation + Round.run asyncio.gather + Orchestrator 主循环
- Phase 04（feb4af8/d864ad8/5a63696/006b8df/da759cd）：7 Gates（safety/lint/type_check/test/coverage/build 6 实现 + contract 占位）+ ae checkpoint v2 + ae status 增强 + 27 测试

**v2.0 删除项取消（Phase 05 Task 5.5 决策）：**
- ❌ v2.0-Analysis-Loop.md §八 计划删除 `engine/` (4 files) + `crew/` (3 files) + `runtime/` (3 files) + `tools/` (5 files)
- ✅ 实际：CLI 仍 import `auto_engineering.engine/runtime/tools`（旧路径），v2.0 loop/ 是叠加而非替代
- 理由：v1.1 实际工作非 stub，删除重写风险 > 增量叠加收益；engine/runtime/tools 与 loop/ 共存，loop/ 是 v2.0+ 的首选路径

**Plan init-TODO.md 产出（2026-06-24）：**
- Phase 01（A1-A7）：7 atomic commits `00a94bb`/`961ca2a`/`8387bdd`/`ec2e108`/`92c3d32`/`74e16d7`/`e2044d6`
  - A1 增量模式（§1.3.10 P0）/ A2 current_phase 传递 / A3 git 非阻塞 / A4 symlink 处理
  - A5 `_warn_undetectable` / A6 spec-doc glob / A7 package_manager 默认 npm
- Phase 02（B1-B3）：8 项目类型 E2E 全过 / 增量模式幂等验证 / `--skip-tasks` 隔离 pnpm 缺失环境
- Phase 03（C1-C2）：hooks.py 31%→88% / scaffold.py 60%→62% / 11+1 新测试

**状态转换节点**：init 子系统从"§1.3 设计-实现偏差 7 项未修复"→"§1.3 100% 完成"

**Plan A 测试**：40 passed (33 原 + 7 新) in 0.12s
- 新增：B1 interrupt_after_breaks_loop / B3 context_manager_yields_store / B5 name_collision_raises + 2 add_edge tests / B6 resume_with_done_checkpoint_raises + resume_with_pending_checkpoint_works
- 覆盖率：state 100% / messages 100% / checkpoint 89% / graph 95% / loop 82% / errors 87%

**Plan A 审计**：0 blockers, 2 P3 warnings (add_conditional_edge 未做 START/END 守卫 / docstring 命名一致性)。Gate Integration: 0 errors

**v3.0 → v3.1 修复（D1-D6 + B1-B6 全部完成）：**
- D1 §3.1 build_dev_loop_graph 补 developer→critic 边（f4f9b9c 修复）
- D2 §3.1 render_description 空值整行删除（f4f9b9c 修复）
- D3 §2.1 run() 退出前同步 checkpoint.status（f4f9b9c 修复）
- D4 §2.1 run() while 循环 status.startswith('interrupt') 时 break（v1.1 Plan A.01 TDD 修复，test_interrupt_after_breaks_loop）
- D5 §7.4 → §7.4.1 增量差异小节，消除 §2.1 与 §7.4 run() 互指（v1.1 Plan A.01）
- D6 §八 8.1 parse_agent_output 注释说明 partial JSON 处理（v1.1 Plan A.01，Phase 3 实现）
- B1 interrupt_after break（同 D4，复测 PASS）
- B3 CheckpointStore 实现 __enter__/__exit__ context manager（Plan A.02 TDD）
- B5 Stage name collision 防御（add_stage 拒绝 __start__/__end__ / add_edge 拒绝 START sentinel，END sentinel 允许）（Plan A.02 TDD）
- B6 resume() 状态校验（拒绝 done checkpoint；要求 run() 持久化最终 status 到 DB）（Plan A.02 TDD）

**清理（决策 1C）：**
- 删 `crew/`, `contracts/`, `tasks/`, `runtime/registry.py`, `runtime/messages.py`, 旧 `engine/*.py`
- 重写 `runtime/__init__.py`（仅 AgentRuntime）
- 同步 `SHARED.md §三/§七` 对齐 v3.0

**审计报告：**
- `design/v1.1-Audit-Report.md` — 架构审计（P0-P2 + 3 个附录；合并 LOOP-AUDIT/AUDIT-SUPPLEMENT/P1 完成状态）
- `design/v1.0-Design-Init.md §1.7` — init 实现偏差审计（21 偏差项）
- `design/v1.0-Design-Init.md §1.8/§1.9` — init 修复实施计划 + Phase 01 完成状态

**下一步：** v1.1 收官（v1.1.0 tag + 发布说明）

**阻塞项：** 无

## 设计演进日志

| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-06-25 | v2.0 全部完成（Phase 01-04）+ Phase 05 删除项决策 | 决策 11/12：v2.0 是增量式，loop/ 与 engine/runtime/tools 共存；commit 链 `c3077bf`→`3857366`→`73ee4bc`→`1dd2ff8`→`4038ca2`→`704987d`→`4f3d932`→`3a3edd1`→`23584b6`→`feb4af8`→`d864ad8`→`5a63696`→`006b8df`→`da759cd` |
| 2026-06-25 | v1.1 计划 Phase 0-4 全部完成（清理 + P0-P2 修复 + Runtime/Guardrail + Agent/Tools + CLI/可观测性） | 见 v1.1-Plan-Dev.md §一问题清单，9 项全部关闭；commit 链 `b6f9a4a`→`3b76826`→`cfb6b13`→`21cd094`→`ddf176c`→`d445105`→`12eb725` |
| 2026-06-25 | 文档命名重构（v1.0-Design-* / v1.1-* / v2.0-Analysis-*） + INDEX.md 合并日志 | 消除 v1.0/v1.1/v2.0 命名不一致；设计文档可追溯 |
| 2026-06-25 | R26 init 模板嵌入 design/ + R26+ pytest 内存规则沉淀为产品级实践 | 模板项目开箱即用设计资产管理 + 16G 内存约束 |
| 2026-06-24 | Plan A bug 修复完成（D1-D6 v3.0 → v3.1） | 第四轮审计发现 6 处设计/代码不一致；D4 interrupt_after TDD 修复，新增 test_interrupt_after_breaks_loop |
| 2026-06-24 | dev-loop Phase 1 编码完成 | 33 测试全绿；v3.0 → v3.1 三处 bug 修复 |
| 2026-06-24 | 现状清理：删 crew/contracts/tasks/runtime/registry+messages；同步 SHARED.md v3.0 | 占位符命名与 v3.0 冲突 + 文档间不一致 |
| 2026-06-24 | init 深度审计：21 个偏差项，设计文档更新 + 修复计划 | 对照设计+实现+Copier/Cookiecutter/Yeoman 源码逐模块检查 |
| 2026-06-24 | dev-loop 第三轮审计：6 设计 bug + 4 缺失维度 | 挑剔的独立审计角度验证可落地性 |
| 2026-06-24 | dev-loop 补充审计：10 个优化点 | 对照 CrewAI/AutoGen/LangGraph 源码补充维度 |
| 2026-06-24 | dev-loop 初始审计：17 个优化点 | 编码前对照源码验证设计质量 |

## 待解决问题

[Q?] 是否需要 streaming 进度输出？— CLI UX 决策
[Q?] `_features/` 的 ae-feature.yml 声明式配置需要什么字段？— R17 实现时确定
[Q?] 增量模式何时排期？— 当前计划 P3（v1.1），可提前如果存量项目接入是刚需

## 引用文件

@design/INDEX.md — 文档索引（含合并日志/归档清单）
@design/v1.0-Design-Shared.md — 共享架构基线（v3.0 对齐）
@design/v1.0-Design-Loop.md — dev-loop 子系统设计（v3.0）
@design/v1.0-Design-Init.md — init 子系统设计 + 实现偏差审计（§1.7）+ 修复计划（§二）
@design/v1.0-Design-Templates.md — 模板资产定义
@design/v1.1-Audit-Report.md — 架构审计报告（P0-P2 + 3个附录）
@design/v1.1-Plan-Dev.md — 整合开发计划（问题清单 + Phase 0-5）
@design/his_bak/v1.1-TODO-LIST.md — 当前 TODO 清单（已归档）
@design/v2.0-Analysis-Loop.md — v2.0 多 Agent 并发架构（**§八 删除项已取消，详见 BEACON.md 决策 11/12**）
@design/v2.0-Design-Loop.md — v2.0 dev-loop 设计基线（基于 v2.0-Analysis-Loop.md 实际落地）
@design/his_bak/ — 历史归档（审计报告/执行计划/设计文档）
@tests/conftest.py — MockRuntime + checkpoint_dir fixture

