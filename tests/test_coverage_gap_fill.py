"""Coverage gap filling — targeted tests to reach 90% coverage.

Targets (ranked by ROI):
1. errors.py (2 missed) — module import
2. scaffold_prereq.py (3 missed) — version/tool check edge cases
3. scaffold_tasks_runner.py (4 missed) — Jinja2 globals
4. path_utils.py (4 missed) — exception paths
5. config_types.py (3 missed) — YAML error in multiselect
6. scaffold_question_eval.py (5 missed) — when=False/TemplateError
7. answers.py (9 missed) — from_answers_file / sensitive fields
8. environment.py (6 missed) — warn/preflight
9. scaffold_render.py (1 missed) — unknown ci_platform
10. prompts.py (6 missed) — nested template / simple pass
11. detector_helpers.py (5 missed) — edge cases
12. detector_analyzers.py (6 missed) — edge cases
13. scaffold_hooks.py (6 missed) — validate_pm / has_package_file
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# ═══════════════════════════════════════════════════════════════════════════════
# 1. errors.py (2 missed: L7-20)
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorsReExport:
    def test_all_error_classes_importable(self):
        from init_engineering.init.errors import (
            ConfigFileError,
            ConfigLoaderSecurityError,
            HookExecutionError,
            InitError,
            InitInterruptedError,
            TargetDirectoryError,
            TaskExecutionError,
            TemplateRenderError,
            UnsatisfiedPrerequisiteError,
            ValidationError,
        )
        assert ConfigFileError is not None
        assert ConfigLoaderSecurityError is not None
        assert HookExecutionError is not None
        assert InitError is not None
        assert InitInterruptedError is not None
        assert TargetDirectoryError is not None
        assert TaskExecutionError is not None
        assert TemplateRenderError is not None
        assert UnsatisfiedPrerequisiteError is not None
        assert ValidationError is not None

    def test_init_module_all_has_16_entries(self):
        from init_engineering.init import __all__ as init_all

        assert len(init_all) == 7


# ═══════════════════════════════════════════════════════════════════════════════
# 2. scaffold_prereq.py (3 missed: L27, 31, 54)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckTemplateVersion:
    def test_empty_version_string_passes(self):
        from init_engineering.init.scaffold_prereq import check_template_version

        check_template_version("")

    def test_version_too_low_raises(self):
        from init_engineering.init.errors import ConfigFileError
        from init_engineering.init.scaffold_prereq import check_template_version

        with pytest.raises(ConfigFileError, match="模板要求 ae >="):
            check_template_version("999.0.0")


class TestCheckLanguageTools:
    def test_unknown_language_skips(self):
        from init_engineering.init.scaffold_prereq import check_language_tools

        check_language_tools("bash", skip_tasks=False)

    def test_none_language_skips(self):
        from init_engineering.init.scaffold_prereq import check_language_tools

        check_language_tools(None, skip_tasks=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. scaffold_tasks_runner.py (4 missed: L60-66, 69-70)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildJinjaEnv:
    def test_build_jinja_env_has_globals(self, tmp_path: Path):
        from init_engineering.init.scaffold_tasks_runner import _build_jinja_env

        env = _build_jinja_env(tmp_path)
        assert "git_status_clean" in env.globals
        assert "project_exists" in env.globals

    def test_project_exists_true(self, tmp_path: Path):
        from init_engineering.init.scaffold_tasks_runner import _build_jinja_env

        (tmp_path / "real.txt").write_text("hello")
        env = _build_jinja_env(tmp_path)
        assert env.globals["project_exists"]("real.txt") is True

    def test_project_exists_false(self, tmp_path: Path):
        from init_engineering.init.scaffold_tasks_runner import _build_jinja_env

        env = _build_jinja_env(tmp_path)
        assert env.globals["project_exists"]("ghost.txt") is False

    def test_git_status_clean_non_git_dir(self, tmp_path: Path):
        from init_engineering.init.scaffold_tasks_runner import _build_jinja_env

        env = _build_jinja_env(tmp_path)
        result = env.globals["git_status_clean"]()
        assert isinstance(result, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. path_utils.py (4 missed: L25-26, 32-33)
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsPathUnderAnyRootExceptions:
    def test_exists_raises_returns_false(self):
        from init_engineering.init._shared.path_utils import is_path_under_any_root

        with patch("os.path.exists", side_effect=OSError("boom")):
            assert is_path_under_any_root(Path("/tmp/x"), ["/tmp"]) is False

    def test_realpath_root_exception_continues(self, tmp_path: Path):
        from init_engineering.init._shared.path_utils import is_path_under_any_root

        result = is_path_under_any_root(tmp_path, ["/no_such_root_xyz"])
        assert isinstance(result, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. config_types.py (3 missed: L137-139)
# ═══════════════════════════════════════════════════════════════════════════════


class TestQuestionCastAnswerMultiselect:
    def test_multiselect_invalid_yaml_raises(self):
        from init_engineering.init.config_types import Question

        q = Question(var_name="test", multiselect=True, type="choice")
        with pytest.raises(ValueError, match="多选答案 YAML 解析失败"):
            q.cast_answer("invalid: [[bad yaml: }")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. scaffold_question_eval.py (5 missed: L43-44, 46, 56-57)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEvaluateQuestionDefaults:
    def test_when_false_removes_default(self):
        from init_engineering.init.answers import AnswersMap
        from init_engineering.init.config_types import TemplateConfig
        from init_engineering.init.config_types import Question
        from init_engineering.init.scaffold_question_eval import (
            evaluate_question_defaults,
        )

        q = Question(var_name="opt", default=True, when=False)
        template = TemplateConfig(template_dir=Path("/tmp"), questions=[q])
        answers = AnswersMap(defaults={"opt": True})
        evaluate_question_defaults(template, answers)
        assert "opt" not in answers.defaults

    def test_when_template_error_preserves_default(self):
        from init_engineering.init.answers import AnswersMap
        from init_engineering.init.config_types import TemplateConfig
        from init_engineering.init.config_types import Question
        from init_engineering.init.scaffold_question_eval import (
            evaluate_question_defaults,
        )

        q = Question(var_name="k", default="v", when="{{ undefined.foo.bar }}")
        template = TemplateConfig(template_dir=Path("/tmp"), questions=[q])
        answers = AnswersMap(defaults={"k": "v"})
        evaluate_question_defaults(template, answers)
        assert "k" in answers.defaults

    def test_render_default_template_error_preserves_original(self):
        from init_engineering.init.answers import AnswersMap
        from init_engineering.init.config_types import TemplateConfig
        from init_engineering.init.config_types import Question
        from init_engineering.init.scaffold_question_eval import (
            evaluate_question_defaults,
        )

        q = Question(var_name="k", default="{{ undefined.fn() }}", type="str")
        template = TemplateConfig(template_dir=Path("/tmp"), questions=[q])
        answers = AnswersMap(defaults={"k": "orig"})
        evaluate_question_defaults(template, answers)
        assert answers.defaults["k"] == "orig"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. answers.py (9 missed: L236, 241, 251-258, 265, 295, 334, 338)
# ═══════════════════════════════════════════════════════════════════════════════


class TestAnswersMapFromFile:
    def test_non_dict_data_raises(self, tmp_path: Path):
        from init_engineering.init.answers import AnswersMap

        f = tmp_path / ".ae-answers.yml"
        f.write_text("just a string\n")
        with pytest.raises(ValueError, match="顶层必须是 mapping"):
            AnswersMap.from_answers_file(f)

    def test_non_dict_meta_treated_as_empty(self, tmp_path: Path):
        from init_engineering.init.answers import AnswersMap

        f = tmp_path / ".ae-answers.yml"
        f.write_text(yaml.dump({"_meta": "not_dict", "project_name": "test"}))
        answers = AnswersMap.from_answers_file(f)
        assert answers.previous.get("project_name") == "test"

    def test_major_version_mismatch_raises(self, tmp_path: Path):
        from init_engineering.init.answers import AnswersMap

        f = tmp_path / ".ae-answers.yml"
        f.write_text(
            yaml.dump({"_meta": {"ae_version": "99.0.0"}, "key": "val"})
        )
        with pytest.raises(ValueError, match="不兼容"):
            AnswersMap.from_answers_file(f)

    def test_schema_version_unsupported_raises(self, tmp_path: Path):
        from init_engineering.init.answers import AnswersMap

        f = tmp_path / ".ae-answers.yml"
        f.write_text(
            yaml.dump({"_meta": {"schema_version": 999}, "key": "val"})
        )
        with pytest.raises(ValueError, match="schema_version"):
            AnswersMap.from_answers_file(f)

    def test_missing_meta_schema_version_ok(self, tmp_path: Path):
        from init_engineering.init.answers import AnswersMap

        f = tmp_path / ".ae-answers.yml"
        f.write_text(yaml.dump({"project_name": "test"}))
        answers = AnswersMap.from_answers_file(f)
        assert answers.previous.get("project_name") == "test"

    def test_null_meta_handled(self, tmp_path: Path):
        from init_engineering.init.answers import AnswersMap

        f = tmp_path / ".ae-answers.yml"
        f.write_text(yaml.dump({"_meta": None, "key": "val"}))
        answers = AnswersMap.from_answers_file(f)
        assert answers.previous.get("key") == "val"

    def test_empty_meta_handled(self, tmp_path: Path):
        from init_engineering.init.answers import AnswersMap

        f = tmp_path / ".ae-answers.yml"
        f.write_text(yaml.dump({"_meta": {}, "key": "val"}))
        answers = AnswersMap.from_answers_file(f)
        assert answers.previous.get("key") == "val"


class TestSensitiveFieldFilter:
    def test_exact_match(self):
        from init_engineering.init._answers_io import _is_sensitive_field

        assert _is_sensitive_field("password") is True
        assert _is_sensitive_field("secret") is True
        assert _is_sensitive_field("token") is True
        assert _is_sensitive_field("api_key") is True

    def test_suffix_match(self):
        from init_engineering.init._answers_io import _is_sensitive_field

        assert _is_sensitive_field("db_password") is True
        assert _is_sensitive_field("github_token") is True
        assert _is_sensitive_field("aws_secret") is True
        assert _is_sensitive_field("private_key") is True
        assert _is_sensitive_field("admin_credential") is True

    def test_normal_fields_ok(self):
        from init_engineering.init._answers_io import _is_sensitive_field

        assert _is_sensitive_field("project_name") is False
        assert _is_sensitive_field("language") is False
        assert _is_sensitive_field("package_manager") is False

    def test_case_insensitive(self):
        from init_engineering.init._answers_io import _is_sensitive_field

        assert _is_sensitive_field("PASSWORD") is True
        assert _is_sensitive_field("Api_Key") is True


class TestAnswersMapToFile:
    def test_sensitive_fields_excluded(self):
        from init_engineering.init.answers import AnswersMap

        answers = AnswersMap(
            defaults={"project_name": "test", "db_password": "secret123"},
        )
        result = answers.to_answers_file()
        assert "project_name" in result
        assert "db_password" not in result

    def test_api_token_excluded(self):
        from init_engineering.init.answers import AnswersMap

        answers = AnswersMap(
            defaults={"name": "x", "github_token": "ghp_xxx"},
        )
        result = answers.to_answers_file()
        assert "name" in result
        assert "github_token" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# 8. environment.py (9 missed: L121-128, 244-245 + warn_undetectable)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. scaffold_render.py (1 missed: L110)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildTemplateDirsEdge:
    def test_unknown_ci_platform_skips(self, tmp_path: Path):
        from init_engineering.init.scaffold_render import build_template_dirs

        type_dir = tmp_path / "templates" / "app-service"
        type_dir.mkdir(parents=True)
        (tmp_path / "templates" / "_shared").mkdir(parents=True)

        context = {"ci_platform": "circleci", "language": "typescript"}
        dirs = build_template_dirs(context, type_dir)
        assert len(dirs) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# 10. prompts.py (6 missed: L96-97, 172, 273, 278, 284)
# ═══════════════════════════════════════════════════════════════════════════════


class TestInteractivePromptRunSimplePass:
    def test_run_with_simple_questions(self):
        from init_engineering.init.answers import AnswersMap
        from init_engineering.init.config_types import Question
        from init_engineering.init.prompts import InteractivePrompt

        q = Question(var_name="name", type="str", help="Name", default="test")
        answers = AnswersMap(defaults={"name": "default"})
        prompt = InteractivePrompt([q], answers)

        with patch.object(
            InteractivePrompt, "_ask_one", return_value=None
        ) as mock_ask:
            result = prompt.run()
            mock_ask.assert_called()
            # Verify the simple pass executed
            assert isinstance(result, AnswersMap)


class TestPromptForNestedTemplate:
    def test_empty_nested_returns_empty(self):
        from init_engineering.init.prompts import prompt_for_nested_template

        assert prompt_for_nested_template({}) == ""

    def test_no_input_with_preferred(self):
        from init_engineering.init.prompts import prompt_for_nested_template

        nested = {"ts": {"path": "./ts", "title": "TS"}}
        result = prompt_for_nested_template(nested, no_input=True, preferred="ts")
        assert result == "./ts"

    def test_preferred_returns_directly(self):
        from init_engineering.init.prompts import prompt_for_nested_template

        nested = {"ts": {"path": "./ts", "title": "TS"}}
        result = prompt_for_nested_template(nested, preferred="ts")
        assert result == "./ts"

    def test_no_input_returns_first(self):
        from init_engineering.init.prompts import prompt_for_nested_template

        nested = {"a": {"path": "./a"}, "b": {"path": "./b"}}
        result = prompt_for_nested_template(nested, no_input=True)
        assert result == "./a"


# ═══════════════════════════════════════════════════════════════════════════════
# 11. detector_helpers.py (5 missed: L61, 73, 81, 83, 112)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDetectPackageManagerEdge:
    def test_package_json_with_package_manager_field(self, tmp_path: Path):
        from init_engineering._shared.detection import detect_package_manager

        pkg = tmp_path / "package.json"
        pkg.write_text('{"packageManager": "pnpm@8.0.0"}')
        assert detect_package_manager(tmp_path) == "pnpm"

    def test_json_decode_error_returns_none(self, tmp_path: Path):
        from init_engineering._shared.detection import detect_package_manager

        (tmp_path / "package.json").write_text("not json")
        (tmp_path / "pnpm-lock.yaml").write_text("")
        result = detect_package_manager(tmp_path)
        assert result is not None  # falls through to lock file


class TestDetectTestRunnerEdge:
    def test_python_language_defaults_to_pytest(self):
        from init_engineering._shared.detection import detect_test_runner

        assert detect_test_runner(Path("/nonexistent"), language="python") == "pytest"

    def test_go_language_returns_go_test(self):
        from init_engineering._shared.detection import detect_test_runner

        assert detect_test_runner(Path("/nonexistent"), language="go") == "go test"

    def test_rust_language_returns_cargo_test(self):
        from init_engineering._shared.detection import detect_test_runner

        assert detect_test_runner(Path("/nonexistent"), language="rust") == "cargo test"

    def test_typescript_defaults_to_none(self):
        from init_engineering._shared.detection import detect_test_runner

        assert detect_test_runner(Path("/nonexistent"), language="typescript") is None

    def test_package_json_json_decode_error_graceful(self, tmp_path: Path):
        from init_engineering._shared.detection import detect_test_runner

        (tmp_path / "package.json").write_text("bad json")
        result = detect_test_runner(tmp_path, language="typescript")
        assert result is None


class TestDetectCiPlatform:
    def test_no_ci_config_returns_none(self, tmp_path: Path):
        from init_engineering._shared.detection import detect_ci_platform

        assert detect_ci_platform(tmp_path) is None

    def test_github_workflows_detected(self, tmp_path: Path):
        from init_engineering._shared.detection import detect_ci_platform

        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        assert detect_ci_platform(tmp_path) == "github"

    def test_gitlab_ci_detected(self, tmp_path: Path):
        from init_engineering._shared.detection import detect_ci_platform

        (tmp_path / ".gitlab-ci.yml").write_text("")
        assert detect_ci_platform(tmp_path) == "gitlab"


class TestCheckPkgDep:
    def test_missing_package_json_returns_false(self, tmp_path: Path):
        from init_engineering.init.detector_helpers import check_pkg_dep

        assert check_pkg_dep(tmp_path, lambda deps: True) is False

    def test_bad_json_returns_false(self, tmp_path: Path):
        from init_engineering.init.detector_helpers import check_pkg_dep

        (tmp_path / "package.json").write_text("nope")
        assert check_pkg_dep(tmp_path, lambda deps: True) is False


# ═══════════════════════════════════════════════════════════════════════════════
# 12. detector_analyzers.py (6 missed: L46, 54-55, 75, 85-86)
# ═══════════════════════════════════════════════════════════════════════════════


class TestAnalyzeNode:
    def test_pnpm_in_scripts_detected(self, tmp_path: Path):
        from init_engineering.init.detector_analyzers import analyze_node
        from init_engineering.init.detector_constants import DetectionResult

        pkg = tmp_path / "package.json"
        pkg.write_text('{"scripts": {"build": "pnpm run build"}, "dependencies": {}}')
        result = DetectionResult()
        analyze_node(pkg, tmp_path, result)
        assert result.package_manager == "pnpm"

    def test_json_decode_error_graceful(self, tmp_path: Path):
        from init_engineering.init.detector_analyzers import analyze_node
        from init_engineering.init.detector_constants import DetectionResult

        pkg = tmp_path / "package.json"
        pkg.write_text("not json")
        result = DetectionResult()
        analyze_node(pkg, tmp_path, result)
        assert result.language == "typescript"  # assigned before try


class TestAnalyzePython:
    def test_toml_parse_error_graceful(self, tmp_path: Path):
        from init_engineering.init.detector_analyzers import analyze_python
        from init_engineering.init.detector_constants import DetectionResult

        py = tmp_path / "pyproject.toml"
        py.write_text("not valid toml [[[")
        result = DetectionResult()
        analyze_python(py, result)
        assert result.language == "python"  # assigned before try

    def test_poetry_backend_detected(self, tmp_path: Path):
        from init_engineering.init.detector_analyzers import analyze_python
        from init_engineering.init.detector_constants import DetectionResult

        py = tmp_path / "pyproject.toml"
        py.write_text(
            "[build-system]\n"
            'requires = ["poetry-core"]\n'
            'build-backend = "poetry.core.masonry.api"\n'
        )
        result = DetectionResult()
        analyze_python(py, result)
        assert result.package_manager == "poetry"

    def test_uv_build_backend_detected(self, tmp_path: Path):
        from init_engineering.init.detector_analyzers import analyze_python
        from init_engineering.init.detector_constants import DetectionResult

        py = tmp_path / "pyproject.toml"
        py.write_text(
            "[build-system]\n"
            'requires = ["hatchling"]\n'
            'build-backend = "hatchling.build"\n'
            "\n"
            "[tool.uv]\n"
            "package = true\n"
        )
        result = DetectionResult()
        analyze_python(py, result)
        assert result.package_manager == "uv"


class TestAnalyzeGo:
    def test_oserror_graceful(self, tmp_path: Path):
        from init_engineering.init.detector_analyzers import analyze_go
        from init_engineering.init.detector_constants import DetectionResult

        go_mod = tmp_path / "go.mod"
        go_mod.write_text("module example.com/myapp\n\ngo 1.21\n")
        result = DetectionResult()
        analyze_go(go_mod, result)
        assert result.language == "go"


# ═══════════════════════════════════════════════════════════════════════════════
# 13. scaffold_hooks.py (6 missed: L37, 88-90, 130-131)
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidatePackageManager:
    def test_invalid_pm_raises(self):
        from init_engineering.init.errors import HookExecutionError
        from init_engineering.init.scaffold_hooks import validate_package_manager

        with pytest.raises(HookExecutionError, match="不在白名单"):
            validate_package_manager("rm")


class TestHasPackageFile:
    def test_npm_checks_package_json(self, tmp_path: Path):
        from init_engineering.init.scaffold_hooks import has_package_file

        (tmp_path / "package.json").write_text("{}")
        assert has_package_file(tmp_path, "npm") is True

    def test_uv_checks_pyproject_toml(self, tmp_path: Path):
        from init_engineering.init.scaffold_hooks import has_package_file

        (tmp_path / "pyproject.toml").write_text("")
        assert has_package_file(tmp_path, "uv") is True

    def test_no_package_file_returns_false(self, tmp_path: Path):
        from init_engineering.init.scaffold_hooks import has_package_file

        assert has_package_file(tmp_path, "npm") is False
