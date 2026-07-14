---
phase: 02-code-review-command
reviewed: 2026-07-12T21:00:00Z
depth: deep
files_reviewed: 39
files_reviewed_list:
  - src/init_engineering/__init__.py
  - src/init_engineering/skill.py
  - src/init_engineering/telemetry.py
  - src/init_engineering/_shared/__init__.py
  - src/init_engineering/_shared/detection.py
  - src/init_engineering/_shared/io.py
  - src/init_engineering/cli/__init__.py
  - src/init_engineering/cli/__main__.py
  - src/init_engineering/cli/_helpers.py
  - src/init_engineering/cli/commands.py
  - src/init_engineering/cli/subcommands.py
  - src/init_engineering/config/__init__.py
  - src/init_engineering/config/environment.py
  - src/init_engineering/init/__init__.py
  - src/init_engineering/init/_answers_io.py
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
  - src/init_engineering/init/_shared/__init__.py
  - src/init_engineering/init/_shared/exclude.py
  - src/init_engineering/init/_shared/io.py
  - src/init_engineering/init/_shared/path_utils.py
  - src/init_engineering/init/init-manifest.schema.json
  - src/init_engineering/init/init-manifest.reference.json
findings:
  critical: 2
  warning: 5
  info: 5
  total: 12
status: issues_found
---

# Phase 2: Code Review Report — Architecture + Virtualization Audit

**Reviewed:** 2026-07-12T21:00:00Z
**Depth:** deep (cross-file import tracing, dependency direction analysis, design-vs-code divergence)
**Files Reviewed:** 39 source files + 2 JSON schema/fixture files
**Status:** issues_found

## Summary

Deep architecture audit of the Init-Engineering codebase (39 Python source files, ~4,500 LOC). The codebase is well-structured overall with correct dependency direction (outer layers depend on inner layers), no circular imports, and all >300-line files are at or near the boundary. The 5-phase pipeline is correctly implemented.

**Key concerns**: Two critical findings: (1) the init-manifest schema file drifts from the Init-Loop contract by including `"plugin"` in the project_type enum, which would cause Loop to reject manifests for plugin-type projects; (2) a sandbox bypass in `_LazyExternalDict` that allows external data file reads without path validation when `external_sandbox_roots` is empty — the two code paths (`AnswersMap._load_external` vs `_LazyExternalDict.__getitem__`) have inconsistent sandbox enforcement.

---

## Critical Issues

### CR-01: Schema Drift — `init-manifest.schema.json` includes `"plugin"` not in contract

**File:** `src/init_engineering/init/init-manifest.schema.json:11`
**Issue:** The schema file lists 9 project types including `"plugin"`, but INIT-LOOP-CONTRACT.md §3 and §5.1 define only 8 types (app-service, library, cli-tool, skill, hook, mcp-server, spec-doc, monorepo). The `"plugin"` type has a template directory and FRAMEWORK_SIGNATURE entry, but the contract with Loop does not include it. If Init generates a manifest with `project_type: "plugin"`, Loop's jsonschema validator would reject it because `"plugin"` is not in the contract's enum.

Evidence:
- Schema file line 11: `"enum": ["app-service","library","cli-tool","skill","hook","mcp-server","spec-doc","monorepo","plugin"]` — 9 values
- Contract §3: lists 8 project_type values without "plugin"
- Contract §5.1 schema: 8 values without "plugin"
- `detector_constants.py:98`: `("plugin", [".claude-plugin/"])` — signature exists
- `templates/plugin/` directory exists

**Impact**: Init can generate valid manifests for `plugin` type that Loop will reject. Broken interoperability.

**Fix options** (user must decide):
- **Option A**: Remove `"plugin"` from schema file enum and from FRAMEWORK_SIGNATURES to align with contract. Delete `templates/plugin/` directory.
- **Option B**: Add `"plugin"` to contract (bump schema to 1.2, sync both repos per contract §5).

---

### CR-02: Security — `_LazyExternalDict` sandbox bypass when `external_sandbox_roots` is empty

**File:** `src/init_engineering/init/answers.py:150-156, 281-296`
**Issue:** The `_LazyExternalDict` class (instantiated in `combined()`) does NOT apply the same sandbox fallback that `AnswersMap._load_external()` applies. When `external_sandbox_roots` is empty (the default), `_LazyExternalDict.__getitem__` passes `effective_roots=[]` to `_load_external_file`, causing the sandbox check on line 261 (`if effective_roots and ...`) to be skipped entirely.

Two inconsistent code paths:
1. `answers.get("key")` → `_load_external()` → fallback `effective_roots=[cwd, home, tempdir]` → **sandbox enforced**
2. `combined()["_external_data"]["key"]` → `_LazyExternalDict.__getitem__()` → `effective_roots=[]` → **sandbox bypassed**

The bypass path is used by Jinja2 templates during rendering (Phase 3) when a template accesses `_external_data.some_key`.

**Fix:**
```python
# In answers.py, _LazyExternalDict.__getitem__ (line 290-296):
def __getitem__(self, key: str) -> Any:
    import tempfile as _tempfile
    if key not in self._cache:
        # Apply same fallback as AnswersMap._load_external()
        effective_roots = (
            self._sandbox_roots
            if self._sandbox_roots
            else [Path.cwd(), Path.home(), Path(_tempfile.gettempdir())]
        )
        self._cache[key] = _load_external_file(
            Path(self._external_map[key]),
            effective_roots=effective_roots,
            var_key=key,
        )
    return self._cache[key]
```

Alternatively, pass the resolved fallback roots from `combined()` instead of raw `self.external_sandbox_roots`:
```python
# In combined() (line 150-156):
if self.external:
    import tempfile
    effective = (
        [Path(r) for r in self.external_sandbox_roots]
        if self.external_sandbox_roots
        else [Path.cwd(), Path.home(), Path(tempfile.gettempdir())]
    )
    result["_external_data"] = _LazyExternalDict(self.external, sandbox_roots=effective)
```

---

## Warnings

### WR-01: Dead Code — `init/_shared/io.py:read_yaml()` has zero callers

**File:** `src/init_engineering/init/_shared/io.py:125-131`
**Issue:** The `read_yaml` function in `init/_shared/io.py` is a thin wrapper that delegates to `_shared/io.py:read_yaml`. No module imports from `init_engineering.init._shared.io`. All consumers use `init_engineering._shared.io.read_yaml` directly or via package-level imports. The docstring says "向后兼容 re-export" but there is no forward usage.

**Fix:** Delete lines 125-131. If `read_yaml` needs to exist in `init._shared`, re-export it in `init/_shared/__init__.py` instead.

---

### WR-02: Cross-Layer Encapsulation Violation — `skill.py` imports from `init._shared`

**File:** `src/init_engineering/skill.py:23`
**Issue:** `skill.py` (package root) imports `resolve_user_path` from `init._shared.path_utils`. The `_shared` module is inside the `init` subpackage and its `_` prefix conventionally marks it as internal/private. This breaks encapsulation: the top-level `skill.py` reaches into `init`'s private internals.

`resolve_user_path` is a general-purpose path resolution utility (handles `None`, `.`, `~` expansion, symlink resolution). It belongs in the package-level `_shared/` module, not inside `init/_shared/`.

**Fix:**
1. Move `resolve_user_path` from `init/_shared/path_utils.py` to `_shared/path_utils.py` (or `_shared/io.py`).
2. Update `skill.py` import to `from ._shared.path_utils import resolve_user_path`.
3. Keep a re-export shim in `init/_shared/path_utils.py` if any tests depend on the old path.

---

### WR-03: Incomplete Schema Validation in `manifest.py`

**File:** `src/init_engineering/init/manifest.py:95-164`
**Issue:** `validate_manifest()` manually replicates a subset of JSON Schema constraints instead of using a proper JSON Schema validator. It checks enum values and required fields but does NOT validate field types. The following would pass validation silently:
- `"linter": 123` (should be string)
- `"source_root": null` (should be string)
- `"build_cmd": true` (should be string)

The schema file requires `linter`, `type_checker`, `test_runner`, `source_root`, `test_root` to be strings, but the manual validator only checks for their presence.

**Fix:** Use `jsonschema` library for validation, or add type checks to the manual validator:
```python
# In validate_manifest(), after checking required fields:
_string_fields_conv = ["linter", "type_checker", "test_runner", "build_cmd"]
for field in _string_fields_conv:
    val = conv.get(field)
    if val is not None and not isinstance(val, str):
        errors.append(f"conventions.{field} must be a string, got {type(val).__name__}")

_string_fields_struct = ["source_root", "test_root", "design_root"]
for field in _string_fields_struct:
    val = struct.get(field)
    if val is not None and not isinstance(val, str):
        errors.append(f"structure.{field} must be a string, got {type(val).__name__}")
```

---

### WR-04: `build_manifest()` Hardcodes `"test_root": "tests"` Without Detection

**File:** `src/init_engineering/init/manifest.py:208`
**Issue:** The manifest always sets `"test_root": "tests"` regardless of the actual test directory convention used by the project. The detector (`detector.py`) already detects test frameworks but does not detect the test directory name. Projects using `test/`, `spec/`, `__tests__/`, or `src/tests/` would get an incorrect manifest.

**Fix:**
```python
# In build_manifest(), derive test_root from answers or detection:
test_root = answers.get("test_root", default=None) or "tests"
structure: dict[str, Any] = {
    "source_root": source_root,
    "test_root": test_root,
}
```

---

### WR-05: Design Doc vs Code Divergence — Features Marked "Not Configurable" Are Configurable

**File:** `design/v5.0-Design-Init.md` §14, lines 30-31
**Issue:** The design document states `preserve_symlinks` is "仅 TemplateRenderer 硬编码，CLI/InitWorker 层不可传" and `templates_suffix` is "仅 YAML 可配，CLI/InitWorker 层不可传". However, the actual code has wired both through:
- `InitWorker` fields: `templates_suffix: str | None = None` (scaffold_phases.py:83), `preserve_symlinks: bool | None = None` (scaffold_phases.py:84)
- CLI passthrough: `cli/__init__.py` passes CLI flags into `InitWorker`
- TemplateRenderer accepts both as constructor parameters (renderer.py:108-109)

The code is correct; the design document is outdated. This is a documentation debt issue — future developers reading the design doc will think these features don't exist at the CLI layer when they do.

**Fix:** Update `design/v5.0-Design-Init.md` §14 table to reflect current implementation: change both status columns from "P2: 差配置层" to "已实现".

---

## Info

### IN-01: CLAUDE.md Lists Folded Module `renderer_symlinks.py`

**File:** `CLAUDE.md:95`
**Issue:** The architecture table references `renderer_symlinks.py` as a separate module, but it was folded into `renderer.py` (line 21: "P2: renderer_symlinks.py 已折叠"). Documentation drift.

**Fix:** Remove `renderer_symlinks.py` from CLAUDE.md architecture table, replace with note that symlink resolution lives in `renderer.py:resolve_symlink()`.

---

### IN-02: Empty `phases/__init__.py` — No Public API

**File:** `src/init_engineering/init/phases/__init__.py`
**Issue:** The `__init__.py` contains only a docstring with no imports or exports. All phase functions (`phase_detect`, `phase_prompt`, `phase_render`, `phase_finalize`, `phase_post_install`) are imported directly from submodules by `scaffold_phases.py` using `from .phases.detect import phase_detect` etc.

Either add re-exports for a clean public API (`from .detect import phase_detect` etc.) or the `__init__.py` is a no-op.

**Fix:** Add canonical re-exports:
```python
from .detect import phase_detect
from .prompt import phase_prompt
from .render import phase_render
from .finalize import phase_finalize, phase_post_install

__all__ = ["phase_detect", "phase_prompt", "phase_render", "phase_finalize", "phase_post_install"]
```

---

### IN-03: Two `_shared` Subpackages with Overlapping `io.py` Modules

**Files:** `src/init_engineering/_shared/io.py` and `src/init_engineering/init/_shared/io.py`
**Issue:** Both contain `io.py` modules at different package levels with the same name `_shared`. The package-level `_shared/io.py` has only `read_yaml`. The init-level `init/_shared/io.py` has `atomic_write_*`, `is_binary`, `detect_newline`, and a dead `read_yaml` wrapper. The naming collision creates confusion: which `_shared.io` is being imported?

**Fix:** Either:
- Consolidate both into one `_shared/io.py` at the package level (remove `init/_shared/io.py`).
- Or rename `init/_shared/` to `init/_internals/` or `init/_lib/` to distinguish from the package-level `_shared/`.

---

### IN-04: Lazy Version Import in `manifest.py:build_manifest()`

**File:** `src/init_engineering/init/manifest.py:186`
**Issue:** `from .. import __version__` is a lazy import inside `build_manifest()`, executed on every call. Since `init_engineering/__init__.py` has no subpackage imports, this could safely be a module-level import (or cached with `functools.lru_cache`).

**Fix:** Either move to module level:
```python
from .. import __version__ as _ae_version
```
Or cache:
```python
@functools.lru_cache(maxsize=1)
def _get_ae_version() -> str:
    from .. import __version__
    return __version__
```

---

### IN-05: `templates_applied` Field Too Generic

**File:** `src/init_engineering/init/manifest.py:221`
**Issue:** `"templates_applied": [project_type]` always outputs just the project type (e.g., `["cli-tool"]`). The contract example shows `["python-cli"]` which includes language info. The current output loses information about which language-specific templates were actually applied.

**Fix:**
```python
templates = [project_type]
if language and language != "unknown":
    templates.insert(0, f"{language}-{project_type}")
manifest["templates_applied"] = templates
```

---

## Dependency Graph

```
                    ┌──────────────────────────────────────┐
                    │        init_engineering/             │
                    │        __init__.py (__version__)      │
                    │        skill.py                      │
                    │        telemetry.py                  │
                    └──────┬───────────┬───────────────────┘
                           │           │
              ┌────────────┘           └────────────┐
              ▼                                     ▼
    ┌──────────────────┐              ┌──────────────────────┐
    │   _shared/       │              │   cli/               │
    │   detection.py   │              │   __init__.py (main) │
    │   io.py          │              │   commands.py        │
    │                  │              │   subcommands.py     │
    │ (leaf: no deps   │              │   __main__.py        │
    │  on subpackages) │              └────────┬─────────────┘
    └──────┬───────────┘                       │
           │                                   │ imports
           │ (detector.py                      │ InitWorker,
           │  imports from                     │ ProjectDetector,
           │  _shared.detection)               │ AnswersMap, etc.
           │                                   │
           ▼                                   ▼
    ┌──────────────────────────────────────────────────────┐
    │   init/                                              │
    │   ┌─────────────────────────────────────┐            │
    │   │ Core Types & Config                 │            │
    │   │  answers.py  ← config_loader.py     │            │
    │   │  config_types.py (Question/Task/    │            │
    │   │    TemplateConfig)                  │            │
    │   │  errors.py (9 exception classes)    │            │
    │   │  detector.py → detector_constants   │            │
    │   │    → detector_analyzers             │            │
    │   │    → detector_helpers               │            │
    │   └─────────────────────────────────────┘            │
    │                                                      │
    │   ┌─────────────────────────────────────┐            │
    │   │ Rendering Engine                    │            │
    │   │  renderer.py (TemplateRenderer)     │            │
    │   │  prompts.py (InteractivePrompt)     │            │
    │   │  hooks.py (TaskRunner)              │            │
    │   │  manifest.py (build/write/validate) │            │
    │   └─────────────────────────────────────┘            │
    │                                                      │
    │   ┌─────────────────────────────────────┐            │
    │   │ Scaffold (Orchestration Layer)       │            │
    │   │  scaffold_phases.py (InitWorker)     │            │
    │   │  scaffold_render.py (build_dirs/     │            │
    │   │    render_to)                        │            │
    │   │  scaffold_hooks.py (builtin hooks)   │            │
    │   │  scaffold_tasks_runner.py            │            │
    │   │  scaffold_prereq.py (version/tool    │            │
    │   │    checks)                           │            │
    │   │  scaffold_question_eval.py           │            │
    │   │  scaffold_lock.py (InitLock/fcntl)   │            │
    │   │  scaffold_update.py (run_update)     │            │
    │   └─────────────────────────────────────┘            │
    │                                                      │
    │   ┌─────────────────────────────────────┐            │
    │   │ Phase Functions                     │            │
    │   │  phases/detect.py                   │            │
    │   │  phases/prompt.py                   │            │
    │   │  phases/render.py                   │            │
    │   │  phases/finalize.py                 │            │
    │   └─────────────────────────────────────┘            │
    │                                                      │
    │   ┌─────────────────────────────────────┐            │
    │   │ Internal Utils (_shared/)            │            │
    │   │  io.py (atomic_write, is_binary)    │            │
    │   │  path_utils.py (is_path_under_any)  │            │
    │   │  exclude.py (match_exclude)          │            │
    │   └─────────────────────────────────────┘            │
    └──────────────────────────────────────────────────────┘
                           ▲
                           │
              ┌────────────┘
              │
    ┌──────────────────┐
    │   config/        │
    │   environment.py │
    │ (imports from    │
    │  _shared.io &    │
    │  _shared.detect) │
    └──────────────────┘
```

**Dependency direction**: Correct. All layers follow outer → inner flow:
- `cli/` → `init/` (commands import InitWorker, ProjectDetector, AnswersMap)
- `config/` → `_shared/` (environment.py imports from package-level _shared)
- `skill.py` → `init/` (via `_shared.path_utils` — **violation**: import of private subpackage)
- `init/phases/` → `init/` (phases import from parent init modules)
- `init/scaffold_*.py` → `init/` (scaffold modules import from sibling init modules)
- `_shared/` → (leaf — no dependencies on subpackages)

**No circular imports detected.** The `from .. import __version__` in `answers.py` and `scaffold_prereq.py` is safe because `init_engineering/__init__.py` has zero subpackage imports.

---

## PASS Items (Verified Clean)

- **Module boundaries**: `cli/`, `config/`, `init/`, `_shared/` layers are well-defined. `init/phases/` is a proper subpackage with focused single-responsibility files.
- **No circular dependencies**: All relative imports form a DAG. No bidirectional `import` or `from ... import` cycles.
- **God Class/Function**: No file exceeds the 300-line guideline by more than a reasonable margin. The 5 largest files (prompts.py:336, commands.py:372, finalize.py:327, skill.py:318, scaffold_phases.py:302) are at/near the boundary with clear single responsibilities.
- **Error propagation**: All 9 exception classes have proper `exit_code` attributes and meaningful error messages. Error handling in `scaffold_phases.execute()` properly cleans up on failure.
- **Path traversal defense**: `is_path_under_any_root()` uses `os.path.realpath` bilateral normalization for macOS symlink safety. Both `config_loader.py` and `answers.py` use it consistently for `!include` and `external_data` path validation.
- **Jinja2 sandbox**: `SandboxedEnvironment` with `StrictUndefined` is used in renderer, prompts, and hooks. No raw `eval()` or `exec()` calls.
- **Command injection prevention**: `TaskRunner.run()` uses `subprocess.run(cmd, list)` with `shell=False` by default. `shell=True` requires explicit `Task.shell=True` configuration.
- **Concurrency**: `InitLock` uses `fcntl.flock` with exclusive lock + heartbeat file. `_tmp_suffix` uses thread-safe counter.
- **AnswersMap.get()**: Returns `None` for missing keys (consistent with `dict.get()`), not `KeyError`. Falls through to `external` layer correctly.
- **Telemetry**: Defaults to `localhost`, requires explicit opt-in consent. No hardcoded secrets.
- **Schema file exists**: `init-manifest.schema.json` and `init-manifest.reference.json` are present at `src/init_engineering/init/`.
- **Reference fixture**: `init-manifest.reference.json` exists for cross-repo validation.
- **Manifest integration**: `phase_finalize()` correctly calls `build_manifest()` + `write_manifest()`, writing to `.ae-state/init-manifest.json`.

---

_Reviewed: 2026-07-12T21:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
