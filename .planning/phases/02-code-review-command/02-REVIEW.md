---
phase: 02-code-review
reviewed: 2026-07-14T20:00:00Z
depth: deep
files_reviewed: 52
files_reviewed_list:
  - src/init_engineering/__init__.py
  - src/init_engineering/_shared/__init__.py
  - src/init_engineering/_shared/detection.py
  - src/init_engineering/_shared/io.py
  - src/init_engineering/_shared/path_utils.py
  - src/init_engineering/cli/__init__.py
  - src/init_engineering/cli/__main__.py
  - src/init_engineering/cli/_click_backend.py
  - src/init_engineering/cli/_helpers.py
  - src/init_engineering/cli/_list_cmds.py
  - src/init_engineering/cli/commands.py
  - src/init_engineering/cli/subcommands.py
  - src/init_engineering/config/__init__.py
  - src/init_engineering/config/environment.py
  - src/init_engineering/init/__init__.py
  - src/init_engineering/init/_answers_io.py
  - src/init_engineering/init/_shared/__init__.py
  - src/init_engineering/init/_shared/exclude.py
  - src/init_engineering/init/_shared/io.py
  - src/init_engineering/init/_shared/path_utils.py
  - src/init_engineering/init/_shared/prompt_backend.py
  - src/init_engineering/init/answers.py
  - src/init_engineering/init/config_loader.py
  - src/init_engineering/init/config_types.py
  - src/init_engineering/init/detector.py
  - src/init_engineering/init/detector_analyzers.py
  - src/init_engineering/init/detector_constants.py
  - src/init_engineering/init/detector_helpers.py
  - src/init_engineering/init/errors.py
  - src/init_engineering/init/hooks.py
  - src/init_engineering/init/manifest.py
  - src/init_engineering/init/phases/__init__.py
  - src/init_engineering/init/phases/detect.py
  - src/init_engineering/init/phases/finalize.py
  - src/init_engineering/init/phases/prompt.py
  - src/init_engineering/init/phases/render.py
  - src/init_engineering/init/prompts.py
  - src/init_engineering/init/renderer.py
  - src/init_engineering/init/scaffold_hooks.py
  - src/init_engineering/init/scaffold_lock.py
  - src/init_engineering/init/scaffold_phases.py
  - src/init_engineering/init/scaffold_prereq.py
  - src/init_engineering/init/scaffold_question_eval.py
  - src/init_engineering/init/scaffold_render.py
  - src/init_engineering/init/scaffold_tasks_runner.py
  - src/init_engineering/init/scaffold_update.py
  - src/init_engineering/skill/__init__.py
  - src/init_engineering/skill/_parse.py
  - src/init_engineering/skill/_runner.py
  - src/init_engineering/skill/_types.py
  - src/init_engineering/skill.py
  - src/init_engineering/telemetry.py
findings:
  critical: 0
  warning: 5
  info: 2
  total: 7
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-07-14T20:00:00Z
**Depth:** deep
**Files Reviewed:** 52
**Status:** issues_found

## Summary

Deep adversarial audit of 52 Python files in `src/init_engineering/`. Systematic coverage of: exception handling (every `except` block traced), boundary conditions (null/None/empty paths), race conditions (fcntl lock protocol), resource leaks (fd lifecycle), `__all__` export correctness, `_`-prefix cross-module discipline, type safety (`Any` usage), and duplicate code patterns.

**Overall assessment:** No critical vulnerabilities, data loss risks, or crash-causing bugs found. Seven findings total — five warnings and two informational items — all in the category of diagnostic completeness (missing `exc_info=True` in exception handlers) and overly broad catch clauses. The code is well-structured, the lock protocol is sound, resource cleanup is complete, and all public API exports are verified importable.

**Key concern:** Six exception handlers across `scaffold_question_eval.py`, `scaffold_tasks_runner.py`, and `scaffold_hooks.py` catch exceptions with `logger.debug()` or `logger.warning()` but omit `exc_info=True`, discarding the traceback. When these exceptions fire in production (e.g., git config timeout on NFS, Jinja2 template syntax error), the root cause cannot be diagnosed from logs alone.

---

## Structural Findings (fallow)

No structural pre-pass provided for this review run. All findings below are from direct adversarial code review.

---

## Warnings

### WR-01: Missing `exc_info=True` in Jinja2 TemplateError catches

**File:** `src/init_engineering/init/scaffold_question_eval.py:47-48, 62-63`
**Issue:** Two `except jinja2.TemplateError` blocks log via `_logger.debug()` but omit `exc_info=True`. When a template author's `when` condition or `default` Jinja2 expression fails to render, the traceback is discarded — only the exception message string is logged. Diagnosis of template syntax errors (undefined variables, filter errors) requires the full traceback showing which template line failed.

**Evidence (lines 47-48):**
```python
except jinja2.TemplateError as e:
    _logger.debug("when 条件渲染失败, 保留 question: %s → %s", q.when, e)
```

**Evidence (lines 62-63):**
```python
except jinja2.TemplateError as e:
    _logger.debug("default 渲染失败, 保留原始值: %s → %s", q.default, e)
```

**Fix:**
```python
except jinja2.TemplateError as e:
    _logger.debug("when 条件渲染失败, 保留 question: %s → %s", q.when, e, exc_info=True)
```
Apply to both locations (lines 48 and 63).

---

### WR-02: Missing `exc_info=True` in subprocess TimeoutExpired catch

**File:** `src/init_engineering/init/scaffold_tasks_runner.py:83-84`
**Issue:** The `_git_status_clean()` Jinja2 helper catches `subprocess.TimeoutExpired` and logs a warning, but omits `exc_info=True`. When `git status --porcelain` times out (e.g., NFS mount, corrupt repo, disk I/O stall), the warning only says "timed out after 10s" without the traceback showing the exact command line, the timeout value, or which `subprocess_run` call in the call chain triggered it.

**Evidence (lines 83-84):**
```python
except subprocess.TimeoutExpired:
    _logger.warning("git status --porcelain timed out after 10s, assuming dirty repo")
    return False
```

**Fix:**
```python
except subprocess.TimeoutExpired:
    _logger.warning(
        "git status --porcelain timed out after 10s, assuming dirty repo",
        exc_info=True,
    )
    return False
```

---

### WR-03: Missing `exc_info=True` in git config timeout debug catches

**File:** `src/init_engineering/init/scaffold_hooks.py:171-172, 180-181`
**Issue:** `_ensure_git_config()` catches `subprocess.TimeoutExpired` in two locations and logs debug messages without `exc_info=True`. These are best-effort fallbacks ("using global defaults"), but when git config consistently times out, the missing traceback prevents diagnosis of whether the timeout is in the subprocess spawn, the git invocation, or a hanging pipe read.

**Evidence (lines 171-172):**
```python
except subprocess.TimeoutExpired:
    _logger.debug("git config %s timed out, using global defaults", key)
    continue
```

**Evidence (lines 180-181):**
```python
except subprocess.TimeoutExpired:
    _logger.debug("git config %s (set default) timed out, using global defaults", key)
    continue
```

**Fix:** Add `exc_info=True` to both `_logger.debug()` calls.

---

### WR-04: TimeoutExpired root cause lost when delegating to `_fail` closure

**File:** `src/init_engineering/init/scaffold_hooks.py:193, 202, 277, 317`
**Issue:** Four `except subprocess.TimeoutExpired` blocks in builtin hook functions delegate to the inner `_fail()` closure, passing only a synthetic message (e.g., "git init timed out after 15s"). The original `TimeoutExpired` exception — which carries the actual command line, the timeout duration, and any partial stdout/stderr — is entirely discarded. The `HookExecutionError` raised by `_fail` (in strict mode) has the synthetic message but none of the original exception context. In non-strict mode, `_logger.warning` receives the synthetic string without traceback.

**Evidence (line 193):**
```python
except subprocess.TimeoutExpired:
    _fail("git init", -1, "git init timed out after 15s")
    return False
```

**Evidence (line 277):**
```python
except subprocess.TimeoutExpired:
    _fail(label, -1, f"{label} timed out after {tmout}s")
    git_ok = False
    continue
```

**Fix:** Log with `exc_info=True` before delegating to `_fail`, or pass the exception to `_fail` so it can use exception chaining:
```python
except subprocess.TimeoutExpired as e:
    _logger.debug("git init timed out", exc_info=True)
    _fail("git init", -1, f"git init timed out after 15s: {e}")
    return False
```

---

### WR-05: Overly broad `ValueError` in tomllib except clause

**File:** `src/init_engineering/init/detector_analyzers.py:70`
**Issue:** The `except` clause catches `(OSError, ValueError, tomllib.TOMLDecodeError)`. `tomllib.TOMLDecodeError` is a subclass of `ValueError` in Python 3.11+, making the bare `ValueError` redundant AND overly broad. If any future code change introduces a `ValueError` from a different source inside the `try` block (e.g., from `result` field assignment), it would be silently swallowed as a "parse error" and the detection would return incomplete results without warning.

**Evidence (lines 68-72):**
```python
try:
    data = tomllib.loads(py_path.read_text(encoding="utf-8"))
except (OSError, ValueError, tomllib.TOMLDecodeError):
    _logger.debug("无法解析 pyproject.toml: %s", py_path, exc_info=True)
    return result
```

**Fix:** Remove the redundant `ValueError`. `tomllib.TOMLDecodeError` already covers all TOML parse errors:
```python
except (OSError, tomllib.TOMLDecodeError):
    _logger.debug("无法解析 pyproject.toml: %s", py_path, exc_info=True)
    return result
```

---

## Info

### IN-01: Silent OSError swallowing in security-critical path validation

**File:** `src/init_engineering/init/_shared/path_utils.py:25-26, 32-33`
**Issue:** `is_path_under_any_root()` is a security boundary function used by `external_data` sandbox checks and `!include` path traversal prevention. When `os.path.realpath()` or `os.path.exists()` raises `OSError` (e.g., permission denied on parent directory, NFS I/O error), the function silently returns `False`. A `False` result means "path not in sandbox" — which triggers a `ValueError` rejection in the caller. If the OSError was transient, a legitimate external data file is incorrectly rejected. If it was a permission error, the user gets a confusing "path traversal" error instead of "permission denied."

**Evidence (lines 25-26):**
```python
except (OSError, RuntimeError):
    return False
```

**Fix:** Add a debug-level log before returning `False`:
```python
except (OSError, RuntimeError) as e:
    _logger.debug("path_utils: realpath/resolve failed for %s: %s", file_path, e, exc_info=True)
    return False
```
Note: requires importing `logging` into `path_utils.py` which currently has no logger.

---

### IN-02: Silent exception swallowing in file type detection predicates

**File:** `src/init_engineering/init/_shared/io.py:112-113, 121-122, 134-135`
**Issue:** `is_binary()` and `detect_newline()` are predicate functions that silently return defaults on I/O errors. `is_binary()` returns `False` (i.e., "this is text") when it cannot read the file, and `detect_newline()` returns `None` (i.e., "unknown newline style") on failure. The callers (`_write_copy`, `_write_rendered`, `resolve_symlink`) use these return values to decide whether to render as text or copy as binary. An I/O error (permission denied, file deleted between check and use) in these predicates causes incorrect file handling with no diagnostic.

**Evidence (lines 112-113):**
```python
except OSError:
    return False
```

**Fix:** Add debug logging at the predicate level, or have callers handle the case where both `is_binary` and the read may fail:
```python
except OSError:
    _logger.debug("is_binary: cannot read %s, assuming text", path, exc_info=True)
    return False
```
Note: `_shared/io.py` already has `_logger` defined at module level.

---

## Verified Pass Items

The following checklist items were verified and found to be correct:

| # | Item | Result |
|---|------|--------|
| 1 | **Exception handling at specified locations** — config_types.py:156,165 (raise), hooks.py:70 (exc_info), scaffold_update.py:265 (exc_info), _answers_io.py:112 (exc_info), renderer.py:84,214,224,236 (raise), prompts.py:218 (exc_info), answers.py:112 (intentional flow control) | PASS |
| 2 | **Race conditions — scaffold_lock.py fcntl protocol** — stale lock reaping TOCTOU sub-scenario analyzed. Linked-by-inode fcntl prevents concurrent acquisition even when `_try_reap_stale_lock` and `os.open()` race. | PASS |
| 3 | **Resource leaks — scaffold_lock.py fd lifecycle** — `acquire()` closes fd on lock failure. `release()` always sets `_fd = None` in finally. `__exit__` always calls `release()`. All paths clean. | PASS |
| 4 | **Naming consistency** — audit-backlog #1 (dst_path/target_dir/project_dir mix) confirmed as known issue. No new naming inconsistencies found. | 已知-跳过 |
| 5 | **`_`-prefix cross-module discipline** — `skill/__init__.py` imports `_parse_prompt`, `_run_*` from subpackage modules; these are intra-package and not re-exported in `__all__`. No violation. | PASS |
| 6 | **`__all__` export correctness** — All 4 `__init__.py` files verified. Every symbol in `__all__` is importable (13 from init/, 1 from config/, 3 from _shared/). | PASS |
| 7 | **Type safety (`Any` usage)** — `PromptBackend` Protocol uses `Any` for `default`/`type`/`value_proc` (inherent to Protocol design). `AnswersMap.get()` returns `-> Any` per audit-backlog #3. No new `Any` escapes found. | 已知-跳过 |
| 8 | **Duplicate code (>3x)** — No 3+ repetition patterns found. The five `_phase_*` thin wrappers in scaffold_phases.py have different argument sets and call different phase functions. | PASS |
| 9 | **No `eval()`/`exec()` usage** — Confirmed across all 52 files. | PASS |
| 10 | **No hardcoded secrets** — Confirmed. `_SENSITIVE_FIELD_PATTERNS` in `_answers_io.py` is a denylist (correct direction). | PASS |
| 11 | **`tomllib` import (Python >=3.11)** — Used correctly in `detector_analyzers.py`. Project requires `>=3.11,<3.14`. | PASS |

---

_Reviewed: 2026-07-14T20:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
