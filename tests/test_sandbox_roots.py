"""P1-3: ProjectEnvironment sandbox_roots 集成测试.

Tasks:
    1. test_project_environment_sandbox_roots_field — ProjectEnvironment 有 sandbox_roots 字段
    2. test_include_within_sandbox_allowed — include 在 sandbox 内允许
    3. test_include_outside_sandbox_rejected — include 在 sandbox 外拒绝
    4. test_include_path_traversal_rejected — 路径遍历 !include ../../../etc/passwd 拒绝

Success criteria:
    - pytest tests/test_sandbox_roots.py -v --no-cov --timeout=60 PASS
    - `!include ../../etc/passwd` 被拒绝
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from init_engineering.config.environment import ProjectEnvironment
from init_engineering.init.config_loader import _load_yaml_with_includes
from init_engineering.init.errors import ConfigLoaderSecurityError


class TestProjectEnvironmentSandboxRoots:
    """Task 4: ProjectEnvironment.sandbox_roots 字段."""

    def test_sandbox_roots_field_exists(self):
        """ProjectEnvironment 有 sandbox_roots 字段,默认空列表."""
        env = ProjectEnvironment()
        assert hasattr(env, "sandbox_roots")
        assert isinstance(env.sandbox_roots, list)
        assert env.sandbox_roots == []

    def test_sandbox_roots_can_be_set(self):
        """sandbox_roots 可被赋值."""
        env = ProjectEnvironment(sandbox_roots=["/allowed/path", "/another/path"])
        assert env.sandbox_roots == ["/allowed/path", "/another/path"]

    def test_sandbox_roots_saved_and_loaded(self, tmp_path: Path):
        """save/resolve 循环保持 sandbox_roots."""
        env = ProjectEnvironment(
            project_name="test",
            sandbox_roots=["/sandbox/a", "/sandbox/b"],
        )
        env.save(tmp_path)

        # resolve 应该加载保存的 sandbox_roots
        resolved = ProjectEnvironment.resolve(tmp_path)
        assert resolved.sandbox_roots == ["/sandbox/a", "/sandbox/b"]


class TestIncludeWithinSandbox:
    """Task 2: include 路径在 sandbox 内允许."""

    def test_include_within_sandbox_allowed(self, tmp_path: Path):
        """合法 include (在 sandbox 内) → 正常加载."""
        # 构造: sandbox=/tmp/sandbox, 允许 include /tmp/sandbox/_partial.yml
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        partial = sandbox / "_partial.yml"
        partial.write_text("key: value\n")

        # 创建 config.yml 在 sandbox 内
        config = sandbox / "config.yml"
        config.write_text("included: !include _partial.yml\n")

        # include 在 sandbox 内 → 允许
        result = _load_yaml_with_includes(
            config,
            sandbox_roots=[str(sandbox)],
        )
        assert result.get("included", {}).get("key") == "value"

    def test_include_single_file_within_sandbox(self, tmp_path: Path):
        """单文件 !include 在 sandbox 内 → 正常合并."""
        sandbox = tmp_path / "myproject"
        sandbox.mkdir()
        partial = sandbox / "_data.yml"
        partial.write_text("foo: bar\n")
        config = sandbox / "ae-template.yml"
        config.write_text("data: !include _data.yml\n")

        result = _load_yaml_with_includes(config, sandbox_roots=[str(sandbox)])
        assert result["data"]["foo"] == "bar"


class TestIncludeOutsideSandbox:
    """Task 3: include 路径在 sandbox 外拒绝."""

    def test_include_outside_sandbox_rejected(self, tmp_path: Path):
        """sandbox 外文件 → 抛出安全异常."""
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        allowed_file = sandbox / "_allowed.yml"
        allowed_file.write_text("ok: true\n")

        # 构造恶意文件在 sandbox 外
        outside = tmp_path / "outside"
        outside.mkdir()
        malicious = outside / "_evil.yml"
        malicious.write_text("pwned: true\n")

        # 创建 config 在 sandbox 内,但 include 指向外部
        config = sandbox / "config.yml"
        config.write_text("included: !include ../outside/_evil.yml\n")

        # 应该被拒绝
        with pytest.raises(ConfigLoaderSecurityError) as exc_info:
            _load_yaml_with_includes(config, sandbox_roots=[str(sandbox)])
        assert "sandbox" in str(exc_info.value).lower() or "outside" in str(exc_info.value).lower()

    def test_include_different_sandbox_not_allowed(self, tmp_path: Path):
        """另一个 sandbox 目录中的文件 → 拒绝."""
        sandbox_a = tmp_path / "sandbox_a"
        sandbox_b = tmp_path / "sandbox_b"
        sandbox_a.mkdir()
        sandbox_b.mkdir()

        file_a = sandbox_a / "_file.yml"
        file_a.write_text("from_a: true\n")

        config_b = sandbox_b / "config.yml"
        # sandbox_a 和 sandbox_b 是兄弟目录, 从 sandbox_b 到 sandbox_a 需要 ../sandbox_a
        config_b.write_text("included: !include ../sandbox_a/_file.yml\n")

        # sandbox_b 不允许 include sandbox_a 的文件
        with pytest.raises(ConfigLoaderSecurityError):
            _load_yaml_with_includes(config_b, sandbox_roots=[str(sandbox_b)])


class TestIncludePathTraversal:
    """Task 4: 路径遍历 !include ../../etc/passwd 拒绝."""

    def test_include_path_traversal_rejected(self, tmp_path: Path):
        """路径遍历 !include ../outside/file.yml → sandbox_roots 非空时拒绝."""
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir(parents=True)

        # 创建 outside 目录 (sandbox 的兄弟)
        outside = tmp_path / "outside"
        outside.mkdir()
        evil_file = outside / "_evil.yml"
        evil_file.write_text("pwned: true\n")

        # 正常配置文件在 sandbox 内
        config = sandbox / "ae-template.yml"
        # 尝试 ../outside/_evil.yml 跳出 sandbox
        config.write_text("dangerous: !include ../outside/_evil.yml\n")

        with pytest.raises(ConfigLoaderSecurityError) as exc_info:
            _load_yaml_with_includes(config, sandbox_roots=[str(sandbox)])
        # 验证拒绝原因包含路径信息
        error_msg = str(exc_info.value).lower()
        assert "sandbox" in error_msg or "outside" in error_msg or "template" in error_msg

    def test_path_traversal_with_realpath_normalization(self, tmp_path: Path):
        """symlink 路径遍历也被 realpath 归一化后拒绝."""
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()

        # 创建 symlink 指向 sandbox 外
        real_outside = tmp_path / "outside_dir"
        real_outside.mkdir()
        evil_file = real_outside / "_evil.yml"
        evil_file.write_text("evil: true\n")

        link_path = sandbox / "link_to_outside"
        try:
            link_path.symlink_to(real_outside)
        except OSError:
            pytest.skip("symlink not supported on this filesystem")

        config = sandbox / "config.yml"
        config.write_text("included: !include link_to_outside/_evil.yml\n")

        # symlink 解析后 realpath 应该指向 sandbox 外,被拒绝
        with pytest.raises(ConfigLoaderSecurityError):
            _load_yaml_with_includes(config, sandbox_roots=[str(sandbox)])


class TestSandboxRootsBackwardCompatibility:
    """sandbox_roots=None (默认) → 不校验,保持向后兼容."""

    def test_no_sandbox_roots_means_no_check(self, tmp_path: Path):
        """sandbox_roots=None (默认) → 不校验, 保持向后兼容."""
        partial = tmp_path / "_partial.yml"
        partial.write_text("key: value\n")
        config = tmp_path / "config.yml"
        config.write_text("included: !include _partial.yml\n")

        # 无 sandbox_roots 时,现有行为不变
        result = _load_yaml_with_includes(config, sandbox_roots=None)
        assert result["included"]["key"] == "value"

    def test_empty_sandbox_roots_list_allows_nothing(self, tmp_path: Path):
        """sandbox_roots=[] (空列表) → 任何 include 都被拒绝."""
        partial = tmp_path / "_partial.yml"
        partial.write_text("key: value\n")
        config = tmp_path / "config.yml"
        config.write_text("included: !include _partial.yml\n")

        # 空 sandbox_roots 意味着严格模式,不允许任何 include
        with pytest.raises(ConfigLoaderSecurityError):
            _load_yaml_with_includes(config, sandbox_roots=[])
