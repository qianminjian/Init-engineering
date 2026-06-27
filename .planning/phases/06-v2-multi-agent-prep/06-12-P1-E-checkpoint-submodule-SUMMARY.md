---
phase: "06-v2-multi-agent-prep"
plan: "P1-E"
subsystem: "loop/checkpoint"
tags: ["refactoring", "checkpoint", "submodule", "P1-E"]
requires: ["P1-A state submodule pattern"]
provides: ["checkpoint/envelope.py", "checkpoint/store.py"]
affects: ["loop/checkpoint.py (removed)"]
tech-stack:
  added: []
  patterns: ["submodule re-export pattern (matching state/)"]
key-files:
  created:
    - "auto_engineering/loop/checkpoint/__init__.py"
    - "auto_engineering/loop/checkpoint/envelope.py"
    - "auto_engineering/loop/checkpoint/store.py"
  deleted:
    - "auto_engineering/loop/checkpoint.py"
decisions:
  - "P1-E: CheckpointMeta 放在 envelope.py 而非 store.py — 避免 store.py → envelope.py 循环导入; Meta 本身是数据类, 与 Checkpoint/Error 在同一层更合理"
  - "P1-E: store.py 609 行 (超出计划的 ≤400 行) — SQLiteCheckpointStore 本身 440+ 行, 继续拆分不会降低复杂度, 保持现状"
metrics:
  duration: "139s"
  completed_date: "2026-06-27T10:41Z"
  tests: "695 passed, 1 skipped, 0 failed"
---

# Phase 06 Plan P1-E: checkpoint.py 拆分为 checkpoint/ 子模块

loop/checkpoint.py (705 行) → checkpoint/envelope.py (95 行, 数据类+异常) + checkpoint/store.py (609 行, SQLite 持久化) + checkpoint/__init__.py (35 行, re-export).

## Execution Summary

**Pattern:** Follows `state/` submodule pattern from P1-A — `state.py` → `state/{channels,checkpoint_envelope,metrics}.py`.

**Split:**
- `envelope.py` (95 lines): Checkpoint, CheckpointMeta dataclasses + 3 error types (CheckpointError, CheckpointNotFoundError, CheckpointSchemaMismatchError) + T TypeVar
- `store.py` (609 lines): SQLiteCheckpointStore class + SCHEMA_VERSION + _normalize_history_item / _normalize_value helpers
- `__init__.py` (35 lines): Re-exports all 7 public symbols, backward compatible with `from auto_engineering.loop.checkpoint import X`

**Backward compatibility:** All existing imports (`from auto_engineering.loop.checkpoint import SQLiteCheckpointStore`, etc.) continue to work through `checkpoint/__init__.py` re-exports.

## Verification

```bash
.venv/bin/pytest tests/ --timeout=120 -q
# 695 passed, 1 skipped in 9.60s
```

All 28 checkpoint-specific tests pass, confirming no behavior change.

## Deviations from Plan

### Implementation Adjustments

**1. [Plan Deviation] CheckpointMeta placed in envelope.py, not store.py**
- **Plan said:** store.py contains SQLiteCheckpointStore + CheckpointMeta + SCHEMA_VERSION
- **Actual:** CheckpointMeta placed in envelope.py alongside Checkpoint
- **Reason:** Checkpoint.meta() returns CheckpointMeta. Having Meta in store.py would require envelope.py to import from store.py, creating a circular dependency (store.py already imports Checkpoint from envelope.py). Meta is a data type, architecturally co-located with the data class that produces it.

**2. [Plan Deviation] store.py exceeds ≤400 line target (609 lines)**
- **Plan said:** store.py ≤ 400 lines
- **Actual:** 609 lines
- **Reason:** SQLiteCheckpointStore class is inherently large (~440 lines for methods alone). Adding SCHEMA_VERSION + 2 helper functions + import boilerplate brings total to 609. Further splitting (e.g., memory mode vs file mode) would increase complexity without clarity gain.

## No Stubs

No stubs, TODOs, FIXMEs, or placeholder code in any of the three new files.

## Self-Check: PASSED

- [x] Created files exist: envelope.py, store.py, __init__.py
- [x] Deleted file confirmed: auto_engineering/loop/checkpoint.py
- [x] All 7 public symbols import correctly
- [x] All 695 tests pass (28 checkpoint-specific + 667 others)
- [x] Commit fd32680 verified in git log

## Commits

| Hash | Message |
|------|---------|
| fd32680 | refactor(P1-E): split loop/checkpoint.py into checkpoint/ submodule |
