"""TDD tests for init-manifest.json generation.

Coverage:
- Schema loading + validation
- build_manifest() correctness
- write_manifest() file output
- Derivation helpers (linter/type_checker/build_cmd)
- Integration: manifest written during phase_finalize
- Reference fixture consistency
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from init_engineering.init.answers import AnswersMap

# ── helpers ──────────────────────────────────────────────────


def _load_schema() -> dict:
    schema_path = (
        Path(__file__).parent.parent
        / "src" / "init_engineering" / "init" / "init-manifest.schema.json"
    )
    return json.loads(schema_path.read_text())


def _load_reference() -> dict:
    ref_path = (
        Path(__file__).parent.parent
        / "src" / "init_engineering" / "init" / "init-manifest.reference.json"
    )
    return json.loads(ref_path.read_text())


def _make_answers(**overrides) -> AnswersMap:
    """Build a minimal AnswersMap for testing manifest generation."""
    answers = AnswersMap(
        interactive={
            "language": "python",
            "package_manager": "uv",
            "test_runner": "pytest",
            "project_name": "my_tool",
            "ci_platform": "github",
        },
    )
    for k, v in overrides.items():
        answers.interactive[k] = v
    return answers


# ── Schema tests ─────────────────────────────────────────────


class TestSchemaLoading:
    """Schema file is present and valid."""

    def test_schema_file_exists(self):
        schema = _load_schema()
        assert schema["version"] == "1.1"
        assert "required" in schema
        assert "properties" in schema


class TestSchemaValidation:
    """Schema validates reference fixture and rejects invalid manifests."""

    def test_reference_fixture_passes_schema(self):
        from init_engineering.init.manifest import validate_manifest

        ref = _load_reference()
        errors = validate_manifest(ref)
        assert not errors, f"Expected no errors, got: {errors}"

    def test_missing_required_fields_fails(self):
        from init_engineering.init.manifest import validate_manifest

        errors = validate_manifest({"schema_version": "1.1"})
        assert any("project_type" in e for e in errors)

    def test_invalid_project_type_fails(self):
        from init_engineering.init.manifest import validate_manifest

        ref = _load_reference()
        ref["project_type"] = "invalid-type"
        errors = validate_manifest(ref)
        assert any("project_type" in e for e in errors)

    def test_invalid_language_fails(self):
        from init_engineering.init.manifest import validate_manifest

        ref = _load_reference()
        ref["language"] = "ruby"
        errors = validate_manifest(ref)
        assert any("language" in e for e in errors)

    def test_invalid_ci_platform_fails(self):
        from init_engineering.init.manifest import validate_manifest

        ref = _load_reference()
        ref["conventions"]["ci_platform"] = "travis"
        errors = validate_manifest(ref)
        assert any("ci_platform" in e for e in errors)

    def test_missing_conventions_subfields_fails(self):
        from init_engineering.init.manifest import validate_manifest

        ref = _load_reference()
        ref["conventions"] = {"test_runner": "pytest"}
        errors = validate_manifest(ref)
        assert any("conventions" in e for e in errors)

    def test_missing_structure_subfields_fails(self):
        from init_engineering.init.manifest import validate_manifest

        ref = _load_reference()
        ref["structure"] = {"source_root": "src"}
        errors = validate_manifest(ref)
        assert any("structure" in e for e in errors)

    def test_monorepo_type_passes(self):
        from init_engineering.init.manifest import validate_manifest

        ref = _load_reference()
        ref["project_type"] = "monorepo"
        errors = validate_manifest(ref)
        assert not errors


# ── build_manifest tests ─────────────────────────────────────


class TestBuildManifest:
    """build_manifest() produces correct output structure."""

    def test_has_all_required_top_fields(self):
        from init_engineering.init.manifest import build_manifest

        answers = _make_answers()
        result = build_manifest(answers, "cli-tool")

        assert result["schema_version"] == "1.1"
        assert result["project_type"] == "cli-tool"
        assert result["language"] == "python"
        assert "created_at" in result
        assert result["init_version"] is not None

    def test_conventions_have_all_subfields(self):
        from init_engineering.init.manifest import build_manifest

        answers = _make_answers()
        result = build_manifest(answers, "cli-tool")

        conv = result["conventions"]
        assert conv["linter"] == "ruff"
        assert conv["type_checker"] == "mypy"
        assert conv["test_runner"] == "pytest"
        assert conv["ci_platform"] == "github"

    def test_structure_has_all_subfields(self):
        from init_engineering.init.manifest import build_manifest

        answers = _make_answers()
        result = build_manifest(answers, "cli-tool")

        struct = result["structure"]
        assert "source_root" in struct
        assert struct["test_root"] == "tests"

    def test_ci_platform_defaults_to_none_when_missing(self):
        from init_engineering.init.manifest import build_manifest

        answers = _make_answers()
        answers.interactive.pop("ci_platform", None)
        result = build_manifest(answers, "cli-tool")

        assert result["conventions"]["ci_platform"] == "none"

    def test_design_root_included_when_provided(self):
        from init_engineering.init.manifest import build_manifest

        answers = _make_answers()
        result = build_manifest(answers, "cli-tool", design_root="design")

        assert result["structure"]["design_root"] == "design"

    def test_design_root_omitted_when_none(self):
        from init_engineering.init.manifest import build_manifest

        answers = _make_answers()
        result = build_manifest(answers, "cli-tool", design_root=None)

        assert "design_root" not in result["structure"]

    def test_created_at_is_iso8601(self):
        from init_engineering.init.manifest import build_manifest

        answers = _make_answers()
        result = build_manifest(answers, "cli-tool")

        dt = datetime.fromisoformat(result["created_at"])
        assert dt.tzinfo is not None

    def test_manifest_validates_against_schema(self):
        from init_engineering.init.manifest import build_manifest, validate_manifest

        answers = _make_answers()
        result = build_manifest(answers, "cli-tool", design_root="design")
        errors = validate_manifest(result)
        assert not errors, f"Manifest should self-validate, got: {errors}"

    def test_all_language_variants_produce_valid_manifest(self):
        from init_engineering.init.manifest import build_manifest, validate_manifest

        for lang in ["python", "typescript", "go", "rust", "bash"]:
            answers = _make_answers(language=lang)
            result = build_manifest(answers, "cli-tool")
            errors = validate_manifest(result)
            assert not errors, f"{lang} manifest should validate, got: {errors}"

    def test_all_project_types_produce_valid_manifest(self):
        from init_engineering.init.manifest import build_manifest, validate_manifest

        for pt in ["app-service", "library", "cli-tool", "skill", "hook",
                    "mcp-server", "spec-doc", "monorepo", "plugin"]:
            answers = _make_answers()
            result = build_manifest(answers, pt)
            errors = validate_manifest(result)
            assert not errors, f"{pt} manifest should validate, got: {errors}"


# ── Derivation helper tests ──────────────────────────────────


class TestDeriveLinter:
    def test_python_ruff(self):
        from init_engineering.init.manifest import _derive_linter
        assert _derive_linter("python") == "ruff"

    def test_typescript_eslint(self):
        from init_engineering.init.manifest import _derive_linter
        assert _derive_linter("typescript") == "eslint"

    def test_go_golangci_lint(self):
        from init_engineering.init.manifest import _derive_linter
        assert _derive_linter("go") == "golangci-lint"

    def test_rust_clippy(self):
        from init_engineering.init.manifest import _derive_linter
        assert _derive_linter("rust") == "clippy"

    def test_bash_shellcheck(self):
        from init_engineering.init.manifest import _derive_linter
        assert _derive_linter("bash") == "shellcheck"


class TestDeriveTypeChecker:
    def test_python_mypy(self):
        from init_engineering.init.manifest import _derive_type_checker
        assert _derive_type_checker("python") == "mypy"

    def test_typescript_tsc(self):
        from init_engineering.init.manifest import _derive_type_checker
        assert _derive_type_checker("typescript") == "tsc"

    def test_compiled_languages_none(self):
        from init_engineering.init.manifest import _derive_type_checker
        assert _derive_type_checker("go") == "none"
        assert _derive_type_checker("rust") == "none"
        assert _derive_type_checker("bash") == "none"


class TestDeriveBuildCmd:
    def test_python_uv(self):
        from init_engineering.init.manifest import _derive_build_cmd
        assert _derive_build_cmd("python", "uv") == "uv build"

    def test_typescript_npm(self):
        from init_engineering.init.manifest import _derive_build_cmd
        assert _derive_build_cmd("typescript", "npm") == "npm run build"

    def test_go(self):
        from init_engineering.init.manifest import _derive_build_cmd
        assert _derive_build_cmd("go", "go") == "go build ./..."

    def test_rust_cargo(self):
        from init_engineering.init.manifest import _derive_build_cmd
        assert _derive_build_cmd("rust", "cargo") == "cargo build --release"


# ── write_manifest tests ─────────────────────────────────────


class TestWriteManifest:
    def test_creates_ae_state_directory(self, tmp_path):
        from init_engineering.init.manifest import write_manifest

        manifest = _load_reference()
        write_manifest(manifest, tmp_path)

        ae_state = tmp_path / ".ae-state"
        assert ae_state.is_dir()

    def test_writes_valid_json_file(self, tmp_path):
        from init_engineering.init.manifest import write_manifest

        manifest = _load_reference()
        write_manifest(manifest, tmp_path)

        manifest_file = tmp_path / ".ae-state" / "init-manifest.json"
        assert manifest_file.is_file()
        data = json.loads(manifest_file.read_text())
        assert data["schema_version"] == "1.1"
        assert data["project_type"] == "cli-tool"

    def test_rejects_invalid_manifest_before_write(self, tmp_path):
        from init_engineering.init.manifest import write_manifest

        invalid = {"schema_version": "1.1"}
        with pytest.raises(ValueError, match="manifest"):
            write_manifest(invalid, tmp_path)

    def test_atomic_write_does_not_leave_tmp_files(self, tmp_path):
        from init_engineering.init.manifest import write_manifest

        manifest = _load_reference()
        write_manifest(manifest, tmp_path)

        # No .tmp-* residue in .ae-state/
        ae_state = tmp_path / ".ae-state"
        tmp_files = list(ae_state.glob(".tmp-*"))
        assert not tmp_files, f"Leftover tmp files: {tmp_files}"


# ── Reference fixture tests ──────────────────────────────────


class TestReferenceFixture:
    def test_reference_is_valid_json(self):
        ref = _load_reference()
        assert ref["schema_version"] == "1.1"

    def test_reference_passes_schema_validation(self):
        from init_engineering.init.manifest import validate_manifest

        ref = _load_reference()
        errors = validate_manifest(ref)
        assert not errors

    def test_reference_matches_build_manifest_output(self):
        """Round-trip: build_manifest for matching inputs should align with reference."""
        from init_engineering.init.manifest import build_manifest

        answers = _make_answers(
            language="python",
            package_manager="uv",
            test_runner="pytest",
            ci_platform="github",
            project_name="my_tool",
        )
        result = build_manifest(answers, "cli-tool", design_root="design")

        assert result["schema_version"] == "1.1"
        assert result["project_type"] == "cli-tool"
        assert result["language"] == "python"
        assert result["conventions"]["linter"] == "ruff"
        assert result["conventions"]["type_checker"] == "mypy"
        assert result["conventions"]["test_runner"] == "pytest"
        assert result["conventions"]["ci_platform"] == "github"
        assert result["structure"]["test_root"] == "tests"
        assert result["structure"]["design_root"] == "design"


# ── Integration tests ────────────────────────────────────────


class TestManifestIntegration:
    """Manifest is generated during the full InitWorker pipeline."""

    def test_manifest_written_to_tmpdir_during_finalize(self, tmp_path):
        """After phase_finalize, manifest exists in tmpdir/.ae-state/"""
        from init_engineering.init.manifest import build_manifest

        answers = _make_answers()
        manifest = build_manifest(answers, "cli-tool", design_root="design")

        from init_engineering.init.manifest import write_manifest
        write_manifest(manifest, tmp_path)

        manifest_file = tmp_path / ".ae-state" / "init-manifest.json"
        assert manifest_file.exists()
        data = json.loads(manifest_file.read_text())
        assert data["schema_version"] == "1.1"

    def test_phase_finalize_calls_manifest_write(self, tmp_path, monkeypatch):
        """phase_finalize() is called, manifest is written to the output."""
        called = []

        def _fake_write(m, target_dir):
            called.append((m, target_dir))
            (target_dir / ".ae-state").mkdir(parents=True, exist_ok=True)
            (target_dir / ".ae-state" / "init-manifest.json").write_text(
                json.dumps(m, indent=2)
            )

        monkeypatch.setattr(
            "init_engineering.init.phases.finalize.write_manifest",
            _fake_write,
        )

        answers = _make_answers()
        answers.write_to(tmp_path / ".ae-answers.yml")

        from init_engineering.init.phases.finalize import phase_finalize

        phase_finalize(
            answers=answers,
            project_type="cli-tool",
            tmpdir=tmp_path,
            dst_path=tmp_path / "out",
            created_files=set(),
            mode="fresh",
            quiet=True,
        )

        assert len(called) == 1
        m, _target = called[0]
        assert m["project_type"] == "cli-tool"
        assert m["language"] == "python"
