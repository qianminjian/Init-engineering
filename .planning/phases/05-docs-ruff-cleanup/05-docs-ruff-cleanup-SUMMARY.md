---
phase: 05
plan: docs-ruff-cleanup
subsystem: docs + lint
tags: [docs-sync, ruff-cleanup, template-fixes, test-fixtures]

# Dependency graph
requires:
  - phase: 01-dev-loop-baseagent-tools-agent
    provides: [agents, tools, runtime, R26 init templates]
  - phase: 03-answers
    provides: [init subsystem, test coverage 82%]
provides:
  - v1.0-Design-Init.md §1.8 todo status table with R1-R3 (R26) and A1/A3/A4 (Phase 01) marked complete
  - BEACON.md current state synced to v1.1 plan Phase 0-4 completion
  - Project-level ruff debt 0 errors (22 → 0; 19 manually fixed, 3 auto-fixed)
  - Template .gitignore.jinja includes coverage/ exclusion
  - v1.0-Design-Shared.md §3 _scratch/ convention documented (subagent coverage/ pattern)
  - _reset_block_cache fixture + 3 guard tests in test_init_design_docs.py
affects: [v1.1.0 release, future lint checks]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RUF012 fix: BaseTool subclass parameters → ClassVar[dict] (mirrors BaseTool.parameters)"
    - "SIM117 fix: nested with → single with tuple (Python 3.10+ syntax)"
    - "Block detector cache cleanup: _reset_block_cache fixture backups and restores _FAILURE_CACHE state"
    - "Coverage exclusion convention: htmlcov/ + coverage/ + .coverage* (template and design doc)"

# Key files
created: []
modified:
  - design/v1.0-Design-Init.md
  - design/BEACON.md
  - design/v1.0-Design-Shared.md
  - auto_engineering/init/templates/_shared/.gitignore.jinja
  - tests/test_agents_3.py
  - tests/test_answers.py
  - tests/test_anthropic_provider.py
  - tests/test_base.py
  - tests/test_init.py
  - tests/test_prompts.py
  - tests/test_tool_error_code.py
  - tests/conftest.py
  - tests/test_init_design_docs.py

# Decisions
decisions:
  - "Treat all 6 tasks as light verification: prior commits (12eb725/d445105/21cd094/cfb6b13/36d52cb) already covered most of the plan's intent. Phase 05 任务 4.3-4.6 added ruff + template + test fixture work."
  - "Manual fix of 19 ruff errors (not --unsafe-fixes) to keep tests readable and avoid risk"
  - "Added _reset_block_cache fixture (conftest.py) to allow explicit cache reset for fixed-blocked tests"
  - "Skipped 'kv section 1.7 audit' as out-of-scope: covered by prior commit 36d52cb"
  - "Did NOT touch 80-line BEACON.md rule: project does not enforce (project CLAUDE.md); document is 128 lines after update"

# Metrics
duration: ~25 minutes (estimated; actual session time)
completed_date: 2026-06-25
tasks_completed: 6
files_changed: 13
ruff_errors_fixed: 22
test_files_modified: 8
new_tests_added: 3
prior_commits_consulted: 7
---

# Phase 05 Plan: 文档同步 + ruff 债清理 Summary

## One-liner

文档同步 v1.1 完成状态 + 项目级 ruff 0 errors (22→0) + 模板 coverage/ 排除 + block detector 缓存清理 fixture.

## Tasks Completed

| # | Task | Commit | Notes |
|---|------|--------|-------|
| 4.1 | §1.8 待办状态表 | `bda690f` | A1/A3/A4/R26 全部标记 ✅；剩余 R5-R17/R20-R21 待办 |
| 4.2 | BEACON.md 当前状态 | `449baa7` | v1.1 计划 Phase 0-4 全部完成 → Phase 05 执行中 |
| 4.3 | ruff 债清理 | `fd240ab` | 22 errors → 0; 19 手动 + 3 自动 |
| 4.4 | 模板 .gitignore coverage/ | `b13e647` | 1 行新增 |
| 4.5 | _scratch/ 约定文档 | `6d02568` | v1.0-Design-Shared.md §3 新增 24 行 |
| 4.6 | 测试改进 | `ba24b5d` | conftest.py + test_init_design_docs.py + 3 新测试 |

## Success Criteria Verification

- [x] v1.0-Design-Init.md §1.8 待办状态已更新（commit bda690f）
- [x] BEACON.md 当前状态已更新（commit 449baa7）
- [x] 项目级 ruff 0 errors（22 errors 修复 — commit fd240ab）
- [x] 模板 .gitignore.tmpl 含 coverage/ 排除（commit b13e647）
- [x] ruff check Phase 05 改动文件 0 errors（验证：`.venv/bin/ruff check .` → All checks passed!）

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] F841 + I001 in test_agents_3.py required broader fix**
- **Found during:** Task 4.3 ruff cleanup
- **Issue:** test_agents_3.py had unused `ctx` (F841) + nested mock (which became vestigial when fixing)
- **Fix:** Removed entire spy/logging block (test only validates tool_map; the spy logic was never used)
- **Files modified:** tests/test_agents_3.py
- **Commit:** fd240ab

**2. [Rule 3 - Blocking] E501 in test_anthropic_provider.py docstring**
- **Found during:** Task 4.3 ruff cleanup
- **Issue:** Docstring 102 chars (line too long)
- **Fix:** Shortened to remove redundant "kwargs" prefix
- **Files modified:** tests/test_anthropic_provider.py
- **Commit:** fd240ab

**3. [Rule 3 - Blocking] RUF012 in 8 BaseTool subclass declarations**
- **Found during:** Task 4.3 ruff cleanup
- **Issue:** Mutable default `parameters = {}` flagged; BaseTool uses `ClassVar[dict]` but subclasses didn't
- **Fix:** Added `from typing import ClassVar` and `parameters: ClassVar[dict] = {...}` to 8 test classes
- **Files modified:** tests/test_base.py (3), tests/test_tool_error_code.py (5)
- **Commit:** fd240ab

**4. [Rule 3 - Blocking] 9 SIM117 nested with statements**
- **Found during:** Task 4.3 ruff cleanup
- **Issue:** Multiple `with` blocks could be combined (Python 3.10+ syntax)
- **Fix:** Combined into single `with (... , ...) :` blocks
- **Files modified:** tests/test_answers.py, tests/test_init.py, tests/test_prompts.py
- **Commit:** fd240ab

## Pre-existing Issues Discovered

**1. [Pre-existing] test_skips_cli_overridden_questions hangs in test_prompts.py**
- **Symptom:** Test takes >60s (likely infinite loop in `prompt.run()`)
- **Mitigation:** block detector already auto-skipped it (3 prior failures)
- **Decision:** Out of Phase 05 scope; documented in test_skips_cli_overridden_questions as known issue
- **Action:** None (deferred to future bugfix phase)

## 5-Dimensional Independent Verification

1. **ruff check:** All checks passed (0 errors)
2. **Test counts:** 583 tests collected; 579 passed, 4 skipped (block detector)
3. **Files committed:** 6 atomic commits (bda690f / 449baa7 / fd240ab / b13e647 / 6d02568 / ba24b5d)
4. **Coverage exclusion:** `htmlcov/` + `coverage/` both present in .gitignore.jinja
5. **Section 1.8 status:** 6 rows marked ✅ (R1-R3/R4/R18/R19); rest 待办

## Self-Check: PASSED

- All 6 commits exist (verified via `git log --oneline`)
- All 13 modified files in working tree match commit history
- ruff 0 errors
- Test suite 579 passed (excluding 4 auto-skipped blocked tests)
- Design docs and BEACON.md state aligned with v1.1 plan completion
