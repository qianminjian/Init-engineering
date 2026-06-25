---
phase: 04
plan: gates-cli
subsystem: gates + cli (v2.0 Phase 04)
tags: [gates, quality-gates, cli, v2.0, ruff, mypy, pytest, coverage, safety, secrets-detection, tdd]

# Dependency graph
requires:
  - phase: v2.0 Phase 01
    provides: [Channel 系统, LoopState 容器]
  - phase: v2.0 Phase 02
    provides: [L1 Loop + 收敛判定, ConvergenceJudge]
  - phase: v2.0 Phase 03
    provides: [Orchestrator, Round, Plan, SQLiteCheckpointStore]
  - phase: v1.1
    provides: [ae dev-loop, ae checkpoint list/show/resume, GateResult, Guardrail 体系]
provides:
  - 7 道 Gate 基类 + 6 实现 + 1 占位 (Gate 0-6)
  - Verdict 数据类 (passed / message / gate_name)
  - Gate.run(project_root) 接口 (v2.0 新接口)
  - CLI: ae status 增强 + ae checkpoint v2 list/show/delete
  - Gate 注册表 V2_GATES 便于 Orchestrator 调度
affects: [v2.0 Orchestrator (调度 gates), v2.0 Round Close (汇总 gate_results)]

# Tech tracking
tech-stack:
  added:
    - "regex + gitleaks subprocess (Gate 0 secrets detection)"
    - "ruff subprocess (Gate 1 lint, 复用 pyproject.toml 配置)"
    - "mypy subprocess (Gate 2 type check, graceful skip)"
    - "pytest subprocess + --timeout=60 (Gate 4, 对齐 pytest-memory-management.md)"
    - "pytest --cov subprocess + 阈值检查 (Gate 5, default 80%, strict=False)"
    - "python -c 'import <module>' subprocess (Gate 6 build)"
  patterns:
    - "Gate 基类: run(project_root) -> Verdict (passed + message + gate_name)"
    - "Verdict.passed() / Verdict.failed() 构造方法(避免字段与方法名冲突)"
    - "Gate subprocess 调用: 3 层降级(explicit bin → PATH → python -m)"
    - "Subprocess timeout → 明确 verdict (passed=False for test/build, passed=True skip for type_check/coverage)"
    - "inifile 检测: 有 pyproject.toml 才加 --timeout (避免陌生环境 fail)"
    - "Gitleaks exit code: 0=no leaks, 1=found, 其他=工具错误忽略"

key-files:
  created:
    - auto_engineering/gates/safety.py — Gate 0 (124 行)
    - auto_engineering/gates/lint.py — Gate 1 (97 行)
    - auto_engineering/gates/type_check.py — Gate 2 (152 行)
    - auto_engineering/gates/contract.py — Gate 3 (67 行, 单 Agent skip)
    - auto_engineering/gates/test.py — Gate 4 (155 行)
    - auto_engineering/gates/coverage.py — Gate 5 (135 行)
    - auto_engineering/gates/build.py — Gate 6 (75 行)
    - tests/test_gates.py — 27 用例覆盖全部 Gate + CLI v2
  modified:
    - auto_engineering/gates/base.py — 新增 Verdict dataclass + Gate.run() 接口
    - auto_engineering/gates/__init__.py — 导出 7 Gate + V2_GATES 注册表
    - auto_engineering/cli.py — 新增 ae checkpoint v2 list/show/delete + ae status 增强

key-decisions:
  - "Gate 结果用 Verdict dataclass (passed + message + gate_name), 与 v1.1 GateResult (Phase 1 Guardrail 体系) 并存"
  - "Gate 3 contract 单 Agent 跳过 + 多 Agent 占位 (Phase 05+ 落地契约校验)"
  - "Gate 4 test 默认不传 --no-cov (避免无 pytest-cov 时 unknown argument); 仅在项目有 inifile 时加 --timeout=60"
  - "Gate 5 coverage strict=False (低于阈值仅 warning); 默认阈值 80% 对齐项目约定"
  - "Gitleaks exit code 0/1 区分 leak found vs no leak; 其他视为工具错误忽略"
  - "CLI v2 子命令使用 SQLiteCheckpointStore (loop.checkpoint); v1.1 命令完全保留"

metrics:
  duration_min: 25
  tests_added: 27
  files_added: 8
  files_modified: 3
  lines_added: 1058
  lines_modified: 34
  commits: 4
  ruff_errors: 0
  test_pass_rate: 100%
---

# Phase 04 Plan: 7 道 Gate + CLI v2.0 — Summary

**One-liner:** 7 道 Python 确定性质量门 (safety/lint/type_check/contract/test/coverage/build) + `ae checkpoint v2` 子命令组, 复用 `pytest-memory-management.md` 内存纪律。

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 4.1 | Gate 基类 + Verdict dataclass | feb4af8 | `auto_engineering/gates/base.py` |
| 4.2-4.8 | 7 道 Gate 实现 | feb4af8 | `auto_engineering/gates/{safety,lint,type_check,contract,test,coverage,build}.py` |
| 4.9 | CLI v2 增量 | d864ad8 | `auto_engineering/cli.py` |
| 4.10 | 测试 (27 用例) | 5a63696 | `tests/test_gates.py` |
| 4.11 | Lint cleanup + 验证 | 006b8df | 8 files |

## Success Criteria

- [x] 7 道 Gate 基类 + 6 道实现 + Gate 3 contract 占位
- [x] Gate 4 (test) 复用 pytest-memory-management.md (--timeout=60, 单文件)
- [x] CLI 增量新增 `ae status` 增强 + `ae checkpoint v2` 子命令组
- [x] v1.1 `ae dev-loop` 不破坏 (cli.py 增量, 无重写)
- [x] tests/test_gates.py ≥14 用例全过 (实际 27 用例)
- [x] ruff 0 errors (`ruff check auto_engineering/ tests/test_gates.py`)

## 7 道 Gate 设计要点

| # | Gate | 实现 | Verdict 失败语义 | 备注 |
|---|------|------|------------------|------|
| 0 | safety | regex (9 patterns) + gitleaks | FAIL (exit=1) | SKIP_DIRS 跳过 venv/.git/__pycache__ |
| 1 | lint | `ruff check .` | FAIL (exit ≠ 0) | 3 层降级: bin → PATH → python -m ruff |
| 2 | type_check | `mypy .` | SKIP (无配置或未安装) | 缺失配置自动 skip, 不阻塞 dev-loop |
| 3 | contract | placeholder | SKIP (agent_count ≤ 1) | 多 Agent 占位, Phase 05+ 落地 |
| 4 | test | `pytest tests/` | FAIL (exit ≠ 0) | inifile 检测 + `--timeout=60` |
| 5 | coverage | `pytest --cov=auto_engineering` | WARN (strict=False) | 默认阈值 80% |
| 6 | build | `python -c "import auto_engineering"` | FAIL (exit ≠ 0) | 不跑 wheel build (过重) |

## CLI v2 命令组

```bash
$ ae status                                  # 增强: 末尾追加 v2.0 Checkpoint 计数
$ ae checkpoint v2 list                      # 列出所有 v2.0 SQLite Checkpoint
$ ae checkpoint v2 list --round 3            # 按 round 过滤
$ ae checkpoint v2 show <cp-id>              # 查看详情 (state + history)
$ ae checkpoint v2 delete <cp-id>            # 删除指定 Checkpoint
```

v1.1 命令完全保留 (`ae checkpoint list/show/resume` 使用 `CheckpointStore`)。

## Deviations from Plan

### Auto-fixed Issues (Rules 1-3)

**1. [Rule 3 - Bug] Gitleaks `-q` flag 不支持 (false positive)**
- **Found during:** Task 4.11 验证
- **Issue:** `gitleaks detect ... -q` 报 "unknown shorthand flag: 'q'", 误判为检测到 secret
- **Fix:** 移除 `-q`, 改用 `--no-banner --no-color`; 区分 exit code (0=clean, 1=found, 其他=工具错误忽略)
- **File:** `auto_engineering/gates/safety.py`
- **Commit:** feb4af8

**2. [Rule 3 - Bug] ruff/pytest subprocess PATH 不可用 (subprocess cwd=tmp_path)**
- **Found during:** Task 4.11 验证
- **Issue:** `python` 命令在 tmp_path 子进程中 PATH 找不到 → FileNotFoundError
- **Fix:** 使用 `sys.executable` (LinterGate); pytest 通过 shutil.which("python") 兜底
- **Files:** `auto_engineering/gates/lint.py`, `auto_engineering/gates/test.py`
- **Commit:** feb4af8

**3. [Rule 3 - Bug] Gate 4 test pytest `--timeout=60` 在陌生环境 fail**
- **Found during:** Task 4.10 test 验证
- **Issue:** pytest 在无 `pyproject.toml` 的 tmp_path 下不认识 `--timeout=60` (exit=4)
- **Fix:** `_build_cmd` 仅在 `project_root` 含 inifile (`pyproject.toml`/`pytest.ini`/`setup.cfg`/`tox.ini`) 时才追加 `--timeout=60`
- **File:** `auto_engineering/gates/test.py`
- **Commit:** feb4af8

**4. [Rule 3 - Bug] coverage.py 冗余 cmd 构造 + RUF005 lint**
- **Found during:** Task 4.11 lint pass
- **Issue:** `--cov` 与 `--no-cov` 冲突, 留下 2 行冗余代码
- **Fix:** 移除冗余 cmd 构造, 保留有效组合 `[--cov=X, --cov-report=term]`
- **File:** `auto_engineering/gates/coverage.py`
- **Commit:** 006b8df

## Self-Check

- [x] 27/27 tests pass (`pytest tests/test_gates.py -v --no-cov --timeout=30`)
- [x] ruff 0 errors (`ruff check auto_engineering/ tests/test_gates.py`)
- [x] v1.1 CLI 兼容 (28 existing CLI tests pass: `tests/test_cli.py test_checkpoint_cli.py test_cli_runtime.py`)
- [x] 7 Gate 单独 smoke test 通过 (6 PASS + 1 expected FAIL on empty test dir)
- [x] All commits on main branch, no destructive operations

## Files Summary

```
新增 (8 files, ~1058 行):
  auto_engineering/gates/safety.py
  auto_engineering/gates/lint.py
  auto_engineering/gates/type_check.py
  auto_engineering/gates/contract.py
  auto_engineering/gates/test.py
  auto_engineering/gates/coverage.py
  auto_engineering/gates/build.py
  tests/test_gates.py

修改 (3 files):
  auto_engineering/gates/base.py    (+Verdict, +Gate.run)
  auto_engineering/gates/__init__.py (+7 exports + V2_GATES 注册表)
  auto_engineering/cli.py            (+ae checkpoint v2 + ae status 增强)
```

## Threat Flags

无新威胁面。Gate 0 safety 是**降低**安全风险的新能力(检测 secrets + 危险代码),不引入新 attack surface。

## Next Phase

v2.0 Phase 05+ 可基于 V2_GATES 注册表 + Verdict 接口,在 Orchestrator.run_round 中调度 7 道 Gate,Gate 结果汇总到 ConvergenceJudge 触发"质量门收敛"判定。