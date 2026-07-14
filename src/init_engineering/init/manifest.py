"""init-manifest.json generation — Init → Loop contract fulfillment.

Schema SSOT: init-manifest.schema.json (version 1.1, copied from Loop repo).
Reference fixture: init-manifest.reference.json (shared between repos).

Validation reads the schema file and applies its constraints, so the schema
remains the single source of truth without requiring the jsonschema package.
"""

from __future__ import annotations

import functools
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ._shared.io import next_tmp_suffix  # 线程安全的临时文件后缀，见 _shared/io.py
from .answers import AnswersMap

_logger = logging.getLogger(__name__)

# ── Language → tool derivation maps ──────────────────────────

_LINTER_MAP: dict[str, str] = {
    "python": "ruff",
    "typescript": "eslint",
    "go": "golangci-lint",
    "rust": "clippy",
    "bash": "shellcheck",
}

_TYPE_CHECKER_MAP: dict[str, str] = {
    "python": "mypy",
    "typescript": "tsc",
    "go": "none",
    "rust": "none",
    "bash": "none",
}

_BUILD_CMD_MAP: dict[str, dict[str, str | None]] = {
    "python": {"uv": "uv build", "pip": None, "poetry": "poetry build"},
    "typescript": {"npm": "npm run build", "yarn": "yarn build", "pnpm": "pnpm build"},
    "go": {"go": "go build ./..."},
    "rust": {"cargo": "cargo build --release"},
    "bash": {},
}


def _derive_linter(language: str) -> str:
    return _LINTER_MAP.get(language, "unknown")


def _derive_type_checker(language: str) -> str:
    return _TYPE_CHECKER_MAP.get(language, "none")


def _derive_build_cmd(language: str, package_manager: str | None) -> str | None:
    pm_map = _BUILD_CMD_MAP.get(language, {})
    if not pm_map:
        return None
    if package_manager:
        return pm_map.get(package_manager)
    return None


def _derive_source_root(answers: AnswersMap) -> str:
    """Derive source_root from answers or sensible default per language."""
    src_root = answers.get("source_root", default=None)
    if src_root:
        return src_root

    language = answers.get("language", default="python")
    if language in ("python", "go"):
        return answers.get("project_name", default="src")
    return "src"


# ── Schema loading ───────────────────────────────────────────


@functools.lru_cache(maxsize=1)
def _load_schema() -> dict:
    """Load and cache the schema file. Cached for the process lifetime."""
    schema_path = Path(__file__).parent / "init-manifest.schema.json"
    try:
        return json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        err = RuntimeError(
            f"Failed to load manifest schema from {schema_path}: {e}"
        )
        err.recovery_hint = (
            "确认 init-manifest.schema.json 存在且格式正确，"
            "或重新安装 init_engineering 包"
        )
        raise err from e


# ── Manifest validation ──────────────────────────────────────


def validate_manifest(manifest: dict) -> list[str]:
    """Validate manifest against init-manifest.schema.json.

    Returns a list of error messages. Empty list means valid.
    """
    schema = _load_schema()
    errors: list[str] = []

    # Required top-level fields
    for field in schema.get("required", []):
        if field not in manifest or manifest[field] is None:
            errors.append(f"Missing required field: {field}")

    props = schema.get("properties", {})

    # project_type enum
    pt_enum = props.get("project_type", {}).get("enum", [])
    if pt_enum and manifest.get("project_type") not in pt_enum:
        errors.append(
            f"Invalid project_type '{manifest.get('project_type')}'"
            f"; must be one of {pt_enum}"
        )

    # language enum
    lang_enum = props.get("language", {}).get("enum", [])
    if lang_enum and manifest.get("language") not in lang_enum:
        errors.append(
            f"Invalid language '{manifest.get('language')}'"
            f"; must be one of {lang_enum}"
        )

    # conventions sub-object
    conv_schema = props.get("conventions", {})
    if conv_schema:
        conv = manifest.get("conventions", {})
        if not isinstance(conv, dict):
            errors.append("conventions must be an object")
        else:
            for field in conv_schema.get("required", []):
                if field not in conv or conv[field] is None:
                    errors.append(f"Missing required field: conventions.{field}")

            conv_props = conv_schema.get("properties", {})
            for field, field_schema in conv_props.items():
                val = conv.get(field)
                if val is None:
                    continue
                expected_type = field_schema.get("type")
                if expected_type == "string" and not isinstance(val, str):
                    errors.append(
                        f"conventions.{field} must be a string, got {type(val).__name__}"
                    )
                elif expected_type == "integer" and not isinstance(val, int):
                    errors.append(
                        f"conventions.{field} must be an integer, got {type(val).__name__}"
                    )

            ci_enum = conv_props.get("ci_platform", {}).get("enum", [])
            if (
                ci_enum
                and conv.get("ci_platform") is not None
                and conv.get("ci_platform") not in ci_enum
            ):
                errors.append(
                    f"Invalid conventions.ci_platform"
                    f" '{conv.get('ci_platform')}'"
                    f"; must be one of {ci_enum}"
                )

    # structure sub-object
    struct_schema = props.get("structure", {})
    if struct_schema:
        struct = manifest.get("structure", {})
        if not isinstance(struct, dict):
            errors.append("structure must be an object")
        else:
            for field in struct_schema.get("required", []):
                if field not in struct or struct[field] is None:
                    errors.append(f"Missing required field: structure.{field}")

    return errors


# ── Manifest builder ─────────────────────────────────────────


def build_manifest(
    answers: AnswersMap,
    project_type: str,
    *,
    design_root: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a manifest dict conforming to schema 1.1.

    Args:
        answers: Resolved AnswersMap from the init pipeline.
        project_type: Detected or CLI-overridden project type.
        design_root: Optional design doc directory path (e.g. "design").
        now: Optional clock injection for test time freezing.

    Returns:
        Manifest dict ready for validation and serialization.
    """
    from .. import __version__ as _ae_version

    dt = now or datetime.now(UTC)

    language = answers.get("language", default="unknown")
    package_manager = answers.get("package_manager", default=None)
    test_runner = answers.get("test_runner", default="unknown")
    ci_platform = answers.get("ci_platform", default=None) or "none"
    framework = answers.get("framework", default=None)
    source_root = _derive_source_root(answers)

    conventions: dict[str, Any] = {
        "linter": _derive_linter(language),
        "type_checker": _derive_type_checker(language),
        "test_runner": test_runner,
        "ci_platform": ci_platform,
    }

    build_cmd = _derive_build_cmd(language, package_manager)
    if build_cmd:
        conventions["build_cmd"] = build_cmd

    structure: dict[str, Any] = {
        "source_root": source_root,
        "test_root": "tests",
    }
    if design_root:
        structure["design_root"] = design_root

    manifest: dict[str, Any] = {
        "schema_version": "1.1",
        "project_type": project_type,
        "language": language,
        "created_at": dt.isoformat(),
        "init_version": _ae_version,
        "conventions": conventions,
        "structure": structure,
        "templates_applied": [project_type, language],
        "answers": answers.combined(),
    }

    if framework:
        manifest["framework"] = framework

    return manifest


# ── Manifest writer ──────────────────────────────────────────


def write_manifest(manifest: dict, target_dir: Path) -> Path:
    """Validate manifest and write to target_dir/.ae-state/init-manifest.json.

    Args:
        manifest: Manifest dict to write.
        target_dir: Directory containing .ae-state/ (created if needed).

    Returns:
        Path to the written manifest file.

    Raises:
        ValueError: If manifest fails schema validation.
    """
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError(
            f"Manifest validation failed — refusing to write invalid manifest: {'; '.join(errors)}"
        )

    ae_state = target_dir / ".ae-state"
    ae_state.mkdir(parents=True, exist_ok=True)

    dest = ae_state / "init-manifest.json"
    content = json.dumps(manifest, indent=2, ensure_ascii=False, default=str)

    # Atomic write via temp file then rename
    tmp = ae_state / f".tmp-init-manifest-{next_tmp_suffix()}.json"
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(dest)
    except OSError:
        _logger.debug("Failed to write manifest", exc_info=True)
        # best-effort cleanup: tmp file may be left behind on failure, but missing_ok=True
        # prevents cleanup error from masking the original exception
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise

    return dest
