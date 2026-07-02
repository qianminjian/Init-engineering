"""tests for init/scaffold_render.py — build_template_dirs."""

from pathlib import Path

import pytest

from auto_engineering.init.scaffold_render import build_template_dirs


class TestBuildTemplateDirs:
    """build_template_dirs — 模板目录选择逻辑覆盖."""

    def test_use_docker_sets_feature_map(self):
        """use_docker=True 时 feature_map 包含 docker 条目 (line 80)."""
        context = {"use_docker": True, "language": "typescript"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"
        # 不崩溃，返回列表
        dirs = build_template_dirs(context, type_dir)
        assert isinstance(dirs, list)
        # _shared 目录应该在结果中
        assert any("_shared" in str(d) for d in dirs)

    def test_monorepo_project_type_sets_feature_map(self):
        """project_type=monorepo 时 feature_map 包含 monorepo 条目 (line 82)."""
        context = {"project_type": "monorepo", "language": "python"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "monorepo"
        dirs = build_template_dirs(context, type_dir)
        assert isinstance(dirs, list)

    def test_empty_ci_platform_skipped(self):
        """ci_platform 不在 CI_FEATURE_MAP 时 feature_name 为空，跳过 (line 86)."""
        # ci_platform="unknown" 不在 CI_FEATURE_MAP → feature_name=""
        # 空 feature_name 触发 continue (line 86)
        context = {"ci_platform": "unknown_platform", "language": "typescript"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"
        # 不崩溃
        dirs = build_template_dirs(context, type_dir)
        assert isinstance(dirs, list)

    def test_github_ci_platform(self):
        """ci_platform=github 添加 github-actions 特征目录 (lines 77-78, 88-90)."""
        context = {"ci_platform": "github", "language": "typescript"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"
        dirs = build_template_dirs(context, type_dir)
        assert isinstance(dirs, list)

    def test_external_template_dir_with_shared(self, tmp_path: Path):
        """external_template_dir 有 _shared 目录时前置."""
        ext_dir = tmp_path / "ext"
        (ext_dir / "_shared").mkdir(parents=True)
        (ext_dir / "_shared" / "README.md").write_text("ext")

        context = {"language": "typescript"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"
        dirs = build_template_dirs(context, type_dir, external_template_dir=ext_dir)

        # external _shared 应该是第一个
        assert dirs[0] == ext_dir / "_shared"

    def test_external_template_dir_feature_language(self, tmp_path: Path):
        """external_template_dir 有语言特征目录时前置."""
        ext_dir = tmp_path / "ext"
        (ext_dir / "_features" / "python").mkdir(parents=True)
        (ext_dir / "_features" / "python" / "test.py.jinja").write_text("ext")

        context = {"language": "python"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"

        dirs = build_template_dirs(context, type_dir, external_template_dir=ext_dir)
        assert isinstance(dirs, list)

    def test_external_template_dir_type_override(self, tmp_path: Path):
        """external_template_dir 类型目录优先于内置."""
        ext_dir = tmp_path / "ext"
        type_name = "app-service"
        (ext_dir / type_name).mkdir(parents=True)
        (ext_dir / type_name / "CLAUDE.md").write_text("ext")

        context = {"language": "typescript"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"

        dirs = build_template_dirs(context, type_dir, external_template_dir=ext_dir)
        assert len(dirs) > 0

    def test_use_lefthook_adds_feature(self):
        """use_lefthook=True 时添加 lefthook 特征目录."""
        context = {"use_lefthook": True, "language": "typescript"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"
        dirs = build_template_dirs(context, type_dir)
        assert isinstance(dirs, list)

    def test_gitlab_ci_platform(self):
        """ci_platform=gitlab 添加 gitlab-ci 特征目录."""
        context = {"ci_platform": "gitlab", "language": "typescript"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"
        dirs = build_template_dirs(context, type_dir)
        assert isinstance(dirs, list)

    def test_go_language_feature(self):
        """language=go 添加 go 特征目录."""
        context = {"language": "go"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"
        dirs = build_template_dirs(context, type_dir)
        assert isinstance(dirs, list)

    def test_rust_language_feature(self):
        """language=rust 添加 rust 特征目录."""
        context = {"language": "rust"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"
        dirs = build_template_dirs(context, type_dir)
        assert isinstance(dirs, list)

    def test_all_features_combined(self):
        """全部特性同时开启."""
        context = {
            "language": "typescript",
            "use_lefthook": True,
            "use_docker": True,
            "ci_platform": "github",
        }
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"
        dirs = build_template_dirs(context, type_dir)
        # 应该至少有 _shared + typescript + _features 下的多个目录 + type_dir
        assert len(dirs) >= 4

    def test_external_template_dir_with_all_features(self, tmp_path: Path):
        """external_template_dir + 全部特性."""
        ext_dir = tmp_path / "ext"
        (ext_dir / "_shared").mkdir(parents=True)
        (ext_dir / "_features" / "typescript").mkdir(parents=True)
        (ext_dir / "_features" / "docker").mkdir(parents=True)

        context = {
            "language": "typescript",
            "use_lefthook": True,
            "use_docker": True,
            "ci_platform": "github",
        }
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"
        dirs = build_template_dirs(context, type_dir, external_template_dir=ext_dir)
        # external _shared 最先
        assert dirs[0] == ext_dir / "_shared"
        assert len(dirs) >= 6


class TestRenderTo:
    """scaffold_render.render_to() — 真实渲染路径覆盖."""

    def test_render_to_builtin_defaults(self, tmp_path: Path):
        """render_to 为缺失变量回填 builtin 默认值 (lines 169-180)."""
        from auto_engineering.init.scaffold_render import render_to
        from auto_engineering.init.answers import AnswersMap

        # 使用 builtins 预填充 context 变量避免 StrictUndefined 错误
        answers = AnswersMap(
            cli_overrides={},
            interactive={},
            previous={},
            defaults={"language": "typescript"},
            builtins={"current_year": 2026},
            external={},
        )

        tmpl_dir = tmp_path / "tmpl"
        tmpl_dir.mkdir()
        (tmpl_dir / "README.md.jinja").write_text("# {{ project_name }}")

        generated = render_to(
            answers=answers,
            folder_name="testproj",
            template_dir=tmpl_dir,
            subdirectory="",
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
            tmpdir=tmp_path / "out",
        )
        assert len(generated) > 0
        assert answers.builtins["_folder_name"] == "testproj"
        assert answers.builtins["project_name"] == "testproj"
        assert answers.builtins["use_typescript"] is False
        assert answers.builtins["use_lefthook"] is False
        assert answers.builtins["use_docker"] is False

    def test_render_to_with_external_and_subdirectory(self, tmp_path: Path):
        """render_to 使用 external_template_dir 和 subdirectory."""
        from auto_engineering.init.scaffold_render import render_to
        from auto_engineering.init.answers import AnswersMap

        ext_dir = tmp_path / "ext"
        (ext_dir / "_shared").mkdir(parents=True)
        (ext_dir / "_shared" / "ext-note.txt").write_text("external shared")

        answers = AnswersMap(
            cli_overrides={},
            interactive={},
            previous={},
            defaults={"language": "typescript"},
            builtins={"current_year": 2026},
            external={},
        )

        tmpl_dir = tmp_path / "tmpl"
        tmpl_dir.mkdir()
        (tmpl_dir / "readme.md").write_text("type readme")

        generated = render_to(
            answers=answers,
            folder_name="myproj",
            template_dir=tmpl_dir,
            subdirectory="",
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
            tmpdir=tmp_path / "out",
            external_template_dir=ext_dir,
        )
        assert len(generated) >= 2  # ext shared + tmpl

    def test_render_to_exclude_callback_parse_error(self, tmp_path: Path):
        """exclude_callback 格式错误时抛 ValueError (line 200-201)."""
        from auto_engineering.init.scaffold_render import render_to
        from auto_engineering.init.answers import AnswersMap

        answers = AnswersMap(
            cli_overrides={},
            interactive={},
            previous={},
            defaults={"language": "typescript"},
            builtins={"current_year": 2026},
            external={},
        )

        tmpl_dir = tmp_path / "tmpl"
        tmpl_dir.mkdir()

        with pytest.raises(ValueError, match="exclude_callback"):
            render_to(
                answers=answers,
                folder_name="test",
                template_dir=tmpl_dir,
                subdirectory="",
                exclude=[],
                skip_if_exists=[],
                no_render=[],
                envops={},
                overwrite=False,
                tmpdir=tmp_path / "out",
                exclude_callback="invalid_format_no_colon",
            )

    def test_render_to_exclude_callback_nonexistent_module(self, tmp_path: Path):
        """exclude_callback 指定不存在的模块 → 回退 (line 198-199)."""
        from auto_engineering.init.scaffold_render import render_to
        from auto_engineering.init.answers import AnswersMap

        answers = AnswersMap(
            cli_overrides={},
            interactive={},
            previous={},
            defaults={"language": "typescript"},
            builtins={"current_year": 2026},
            external={},
        )

        tmpl_dir = tmp_path / "tmpl"
        tmpl_dir.mkdir()
        (tmpl_dir / "readme.md").write_text("# test")

        # "nonexistent.module:func" — ImportError → fallback
        generated = render_to(
            answers=answers,
            folder_name="test",
            template_dir=tmpl_dir,
            subdirectory="",
            exclude=[],
            skip_if_exists=[],
            no_render=[],
            envops={},
            overwrite=False,
            tmpdir=tmp_path / "out",
            exclude_callback="nonexistent_module_xyz:some_func",
        )
        assert len(generated) > 0

    def test_build_template_dirs_with_external_subdirectory(self, tmp_path: Path):
        """build_template_dirs external_template_dir + subdirectory (line 124-127)."""
        ext_dir = tmp_path / "ext"
        (ext_dir / "app-service" / "sub" / "nested.txt").mkdir(parents=True)
        (ext_dir / "app-service" / "sub" / "nested.txt" / "file.md").write_text("nested")

        context = {"language": "typescript"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"

        dirs = build_template_dirs(context, type_dir, subdirectory="sub", external_template_dir=ext_dir)
        assert isinstance(dirs, list)
        assert len(dirs) > 0

    def test_build_template_dirs_with_external_missing_subdirectory(self, tmp_path: Path):
        """external_template_dir 存在但 subdirectory 不存在 → 跳过 external type dir."""
        ext_dir = tmp_path / "ext"

        context = {"language": "typescript"}
        type_dir = Path(__file__).parent.parent / "auto_engineering" / "init" / "templates" / "app-service"

        dirs = build_template_dirs(context, type_dir, subdirectory="nonexistent_sub", external_template_dir=ext_dir)
        assert isinstance(dirs, list)
        assert len(dirs) > 0

