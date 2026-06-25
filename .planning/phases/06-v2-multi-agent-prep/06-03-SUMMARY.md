# Phase 03 (v2.0) Plan 06-v2-multi-agent-prep — Orchestrator + Round + Multi-Agent Concurrency Summary

## One-liner

Multi-Agent 并发调度 (asyncio.gather) + Task DAG + 文件隔离检查 + Round 生命周期 + Orchestrator 主循环 + 19 测试全过。

## Task Completion

| Task | Status | Commit | Files |
|------|--------|--------|-------|
| 3.1 plan.py (Task DAG + check_file_isolation) | ✅ | 4f3d932 | auto_engineering/loop/plan.py |
| 3.2 round.py (Round + asyncio) | ✅ | 3a3edd1 | auto_engineering/loop/round.py |
| 3.3 orchestrator.py (主循环 + 收敛判定) | ✅ | 3a3edd1 | auto_engineering/loop/orchestrator.py |
| 3.4 tests/test_loop_orchestrator.py | ✅ | 4f3d932 | tests/test_loop_orchestrator.py |

## Deliverables

### auto_engineering/loop/plan.py (~245 行)

- `Task` dataclass: id / agent_type / description / target_files (frozenset) / depends_on / estimated_minutes / status
- `TaskDAG`: nodes + `topological_sort()` (Kahn algorithm, O(V+E))
- `topological_sort()`: 便捷函数 + 循环检测
- `check_file_isolation()`: 按 topological levels 分组检查文件冲突
  - 串行 task (有 deps 关系) 即使共享文件也算合法
  - 并行 task (同 level) 必须 target_files 无交集
- `Plan`: tasks + `validate()` + `parallelism_groups()` + `get_task()`
- `ConflictError`: 暴露给 Orchestrator (raise_on_conflict=True)
- `TaskStatus` (StrEnum): PENDING/IN_PROGRESS/COMPLETED/FAILED/BLOCKED

### auto_engineering/loop/round.py (~190 行)

- `TaskOutcome`: task_id / status / output / error / duration
- `RoundResult`: round_id / outcomes / started_at / finished_at
  - `completed_count` / `failed_count` / `all_succeeded` / `duration` properties
- `run_round()`: asyncio.gather 并行调度所有 task
  - `_execute_single` 包装异常 → failed outcome (保护 gather)
  - `CancellationToken` 集成 (每 task 入口 check)
- `Round` dataclass: metadata + `execute()` 委托 run_round

### auto_engineering/loop/orchestrator.py (~190 行)

- `OrchestratorConfig`: max_rounds + convergence_config
- `Orchestrator.run()` 主循环:
  1. `Plan.validate()` (DAG + 文件隔离)
  2. for round in 1..max_rounds:
     - cancellation check (Round 边界)
     - `_select_round_tasks()` (Phase 3 简化: 每轮重跑)
     - `run_round` → RoundResult
     - `_build_history()` (Phase 3 mock: semantic_satisfied=None)
     - `ConvergenceJudge.evaluate()` → verdict
     - `should_stop` → 退出
  3. 达到 max_rounds → LEVEL_HARD_LIMIT
- 复用 Phase 02 `ConvergenceJudge` (4 级判定)
- 复用 `CancellationToken` (v1.1 cli.py 拆分到 runtime/cancellation.py)

### auto_engineering/runtime/cancellation.py (~40 行)

- `CancellationToken` 从 cli.py 拆分到 runtime/ 模块
- 避免 loop 模块反向引用 cli.py (cli.py 引入多个重模块)

### tests/test_loop_orchestrator.py (19 用例, ≥10 目标达成)

| Section | Cases | Status |
|---------|-------|--------|
| A. TaskDAG 拓扑排序 | 3 (linear / diamond / cycle) | ✅ |
| B. check_file_isolation | 4 (no conflict / conflict / 串行豁免 / raise) | ✅ |
| C. Plan parallelism_groups | 4 (3 independent / diamond / validate pass / raise) | ✅ |
| D. Round asyncio.gather | 3 (single / 真并行 < 串行 / 失败聚合) | ✅ |
| E. Orchestrator 完整流程 | 4 (单 Agent / 多 Agent / 硬上限 / 冲突传播) | ✅ |
| F. CancellationToken 整合 | 1 (取消停止 loop) | ✅ |

## Design Decisions

1. **asyncio.gather 并发模型**: 不使用 Worktree 隔离 (LLM 调用 I/O bound, asyncio 天然适配)
2. **文件隔离确定性检查**: Plan.validate() 调用 check_file_isolation, 任务拆分阶段拦截冲突
3. **StrEnum for TaskStatus**: 替代 `class TaskStatus(str, Enum)` (ruff UP042)
4. **Phase 3 mock semantics**: semantic_satisfied=None, gate_results={} — 让 ConvergenceJudge 不触发, 由硬上限终止 (真实 LLM 评估 Phase 4+ 接)
5. **CancellationToken 模块拆分**: cli.py 重依赖多, 拆分到 runtime/cancellation.py 避免循环

## Constraints Verified

- [x] **TaskDAG 拓扑排序正确**: 3 用例 (linear/diamond/cycle)
- [x] **check_file_isolation 拦截 target_files 冲突**: 4 用例
- [x] **asyncio.gather 多 Agent 真并行 (2+ agents)**: `test_run_round_multiple_tasks_run_concurrently` 验证 3 task * 0.1s 并行耗时 < 0.25s (vs 串行 0.3s)
- [x] **Orchestrator 单 Agent + 多 Agent 流程跑通**: 2 用例
- [x] **复用 Phase 02 收敛判定**: Orchestrator 集成 ConvergenceJudge, LEVEL_HARD_LIMIT 在 max_rounds 测试中验证
- [x] **tests/test_loop_orchestrator.py ≥10 用例全过**: 19/19 pass
- [x] **ruff 0 errors**: All checks passed
- [x] **不删除 v1.1 任何代码**: 仅新增 plan.py / round.py / orchestrator.py / cancellation.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CancellationToken 导入路径**
- **Found during:** Task 3.1 test design
- **Issue:** 原设计 v1.1 CancellationToken 在 cli.py, 但 cli.py 导入大量重模块 (engine/agents/llm/runtime/tools), 反向引用会拖慢测试
- **Fix:** 拆分到 `auto_engineering/runtime/cancellation.py`, cli.py 保留旧引用以兼容
- **Files modified:** auto_engineering/runtime/cancellation.py (new), auto_engineering/runtime/__init__.py (re-export), auto_engineering/loop/orchestrator.py (import)
- **Commit:** 4f3d932

**2. [Rule 3 - Blocking] Phase 3 mock semantic 语义冲突**
- **Found during:** Task 3.3 orchestrator test debugging
- **Issue:** `_build_history()` 初始设 `semantic_satisfied=True`, 导致 Level 1 GOAL_ACHIEVED 在 round 1 后立即触发, 无法测试硬上限路径
- **Fix:** 改为 `semantic_satisfied=None` (Phase 3 mock 不评估 LLM, 让硬上限生效), 同时调整 `test_orchestrator_respects_max_rounds` 用 `stagnation_threshold=10` 防止停滞检测干扰
- **Files modified:** auto_engineering/loop/orchestrator.py, tests/test_loop_orchestrator.py
- **Commit:** 4f3d932, 3a3edd1

## Auth Gates

None — 本 phase 无需认证。

## Test Results

```
tests/test_loop_orchestrator.py ............................. 19 passed
tests/test_loop_state_v2.py ................................. 21 passed
tests/test_loop_convergence.py .............................. 39 passed
                                              Total:       79 passed in 0.73s
```

ruff: `All checks passed!`

## Key Files

- `/Users/minjianq/Documents/06-Mi-Model-Rule/Auto-engineering/auto_engineering/loop/plan.py`
- `/Users/minjianq/Documents/06-Mi-Model-Rule/Auto-engineering/auto_engineering/loop/round.py`
- `/Users/minjianq/Documents/06-Mi-Model-Rule/Auto-engineering/auto_engineering/loop/orchestrator.py`
- `/Users/minjianq/Documents/06-Mi-Model-Rule/Auto-engineering/auto_engineering/runtime/cancellation.py`
- `/Users/minjianq/Documents/06-Mi-Model-Rule/Auto-engineering/tests/test_loop_orchestrator.py`

## Commits

- `4f3d932`: feat(2.0-03): Task DAG + Plan + check_file_isolation + 19 tests (5 files, +809/-4)
- `3a3edd1`: feat(2.0-03): Round asyncio.gather + Orchestrator 主循环 (2 files, +408)

## Metrics

- **Duration**: ~7 minutes
- **Files created**: 5 (plan.py, round.py, orchestrator.py, cancellation.py, test_loop_orchestrator.py)
- **Files modified**: 2 (loop/__init__.py, runtime/__init__.py)
- **Lines added**: ~1217 (production ~625 + tests ~592)
- **Tests added**: 19 (≥10 目标超额达成)
- **ruff errors**: 0

## Next Phase

Phase 04: CLI 集成 + 清理
- `cli.py` 重写 (`ae dev` / `ae dev-loop` / `ae status` / `ae checkpoint`)
- 删除 `engine/` (4 files) + `crew/` (3 files) + `runtime/` 中旧文件
- 删除 `tools/` (5 files), 内容整合到 `agents/tools.py` (Phase 4+ 任务)
- 更新 `pyproject.toml` + `CLAUDE.md`