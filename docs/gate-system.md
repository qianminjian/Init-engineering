# Gate System — 两体系说明

> 创建：2026-06-26 | 位置：永久资产

## v1.0 Guardrail（builtin.py）

- 5 个内置 Guardrail：Requirement/PlanExists/GitClean/TestsPass/GitDiffExists
- 4 态结果：pass / block / drop / retry
- 用于 Phase 1 LoopEngine（`gates/gates.py` 旧路径）
- 向后兼容：`gates/builtin.py` + `gates/guardrail.py` 保留

## v2.0 Gate（safety/lint/type_check/test/coverage/build/contract）

- 7 道 Gate：safety / lint / type_check / contract / test / coverage / build
- 返回 Verdict（passed / message / gate_name）
- 用于 v2.0 Orchestrator（`loop/orchestrator.py`）
- 每 Round 后自动执行（传入 gates 列表）

## 关系

| 维度 | Guardrail (v1.0) | Gate (v2.0) |
|------|-----------------|-------------|
| 位置 | `gates/builtin.py` | `gates/{safety,lint,...}.py` |
| 调用者 | `GuardrailChain` | `Orchestrator` |
| 结果类型 | `GuardrailResult` (4 态) | `Verdict` (2 态) |
| 收敛判定 | GuardrailResult.action | Verdict.passed + Verdict.message |
| 生命周期 | Phase 1 | Phase 04 (v2.0) |

## 未来

两体系并存，`Gate` 是 v2.0 推荐路径。（删除 Guardrail 体系建议保留到 v3.0 整体架构清理。）