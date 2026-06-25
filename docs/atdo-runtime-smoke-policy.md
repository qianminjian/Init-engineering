# atdo Runtime Smoke Policy (项目级)

> 创建：2026-06-25 | 阶段：v2.1 FINAL PHASE (P1.6)
> 位置：`docs/` = 永久资产，不 gitignore

## Why

v2.1 Phase 1 审计发现 atdo Plan 报告虚化案例（agent 报告 SUCCESS 但实际功能未完整实现）。
详见 `_proc-use/_bug-info/atdo-report-fabrication-2026-06-25.md`。

## 规则

每 phase 完成后，orchestrator 必须跑 **runtime smoke**（Python 直接调用核心功能），
不只依赖 5 维静态检查：

| 维度 | 类型 | 说明 |
|------|------|------|
| fileExistence | 静态 | 文件存在 |
| syntax | 静态 | 语法过 |
| diffRange | 静态 | diff 范围合理 |
| debugResidue | 静态 | 无调试残留 |
| secretScan | 静态 | 无密钥 |
| **runtimeSmoke** | **动态** | **Python 直接调用核心功能，验证端到端集成** |

## 强制要求

1. **save/load/serialize 等持久化功能**：必须真跑 `save → load` 验证 round-trip
2. **Orchestrator 集成**：必须真跑 Gate + 真调 LLM evaluator（不能 mock 绕过）
3. **CLI 集成**：必须真 `subprocess` 跑 CLI 验证 `help` + `exit code`
4. **测试严禁用空状态绕过真实场景**：空 `LoopState()` / 空 `gate_results={}` / 空 `_build_history` 等

## 防护

- Plan 报告 SUCCESS 前必须含 runtime smoke PASS（写入 Phase summary）
- atdo protocol 应在 Step 3 增加 `runtime_smoke` 维度
- agent 自报 `methodology=proxy` 时强制 runtime smoke

## 工具

- `scripts/atdo_smoke.py` — Runtime smoke helper（5 维 + runtime_smoke）

## 引用

- `_proc-use/_bug-info/atdo-report-fabrication-2026-06-25.md` — 虚化案例全记录
- `design/BEACON.md` 决策 18 — 协议层强制要求