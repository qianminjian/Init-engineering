"""P2-3: ConfigLoaderSecurityError 异常类测试.

Tasks:
    1. test_config_loader_security_error_class — ConfigLoaderSecurityError 类存在
    2. test_include_outside_sandbox_raises_security_error — sandbox 外 include 被拒绝
    3. test_include_path_traversal_raises_security_error — 路径遍历 !include 被拒绝
    4. test_security_error_is_init_error_subclass — ConfigLoaderSecurityError 是 InitError 子类

Success criteria:
    - pytest tests/test_config_loader_security.py -v --no-cov --timeout=60 PASS
    - ConfigLoaderSecurityError 是 InitError 的子类
"""

from __future__ import annotations

from pathlib import Path

import pytest

from init_engineering.init.config_loader import _load_yaml_with_includes
from init_engineering.init.errors import ConfigLoaderSecurityError, InitError


class TestConfigLoaderSecurityErrorClass:
    """Task 1: ConfigLoaderSecurityError 类结构."""

    def test_security_error_class_exists(self):
        """ConfigLoaderSecurityError 类存在且可导入."""
        assert ConfigLoaderSecurityError is not None

    def test_security_error_exit_code(self):
        """ConfigLoaderSecurityError 有 exit_code=8."""
        assert ConfigLoaderSecurityError.exit_code == 8

    def test_security_error_accepts_message(self):
        """ConfigLoaderSecurityError 接受字符串消息."""
        err = ConfigLoaderSecurityError("test message")
        assert str(err) == "test message"
        assert err.message == "test message"


class TestSecurityErrorInheritance:
    """Task 4: ConfigLoaderSecurityError 是 InitError 子类."""

    def test_security_error_is_init_error_subclass(self):
        """ConfigLoaderSecurityError 继承自 InitError."""
        assert issubclass(ConfigLoaderSecurityError, InitError)

    def test_security_error_is_exception_subclass(self):
        """ConfigLoaderSecurityError 继承自 Exception."""
        assert issubclass(ConfigLoaderSecurityError, Exception)


class TestIncludeOutsideSandbox:
    """Task 2: include 路径在 sandbox 外拒绝并抛出 ConfigLoaderSecurityError."""

    def test_include_outside_sandbox_raises_security_error(self, tmp_path: Path):
        """sandbox 外文件 → 抛出 ConfigLoaderSecurityError (非 ValueError)."""
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

        # 应该被拒绝, 且抛出 ConfigLoaderSecurityError (不是 ValueError)
        with pytest.raises(ConfigLoaderSecurityError) as exc_info:
            _load_yaml_with_includes(config, sandbox_roots=[str(sandbox)])
        assert "sandbox" in str(exc_info.value).lower() or "outside" in str(exc_info.value).lower()

    def test_empty_sandbox_roots_raises_security_error(self, tmp_path: Path):
        """sandbox_roots=[] → 任何 include 都被 ConfigLoaderSecurityError 拒绝."""
        partial = tmp_path / "_partial.yml"
        partial.write_text("key: value\n")
        config = tmp_path / "config.yml"
        config.write_text("included: !include _partial.yml\n")

        with pytest.raises(ConfigLoaderSecurityError):
            _load_yaml_with_includes(config, sandbox_roots=[])


class TestIncludePathTraversal:
    """Task 3: 路径遍历 !include ../../etc/passwd 拒绝并抛出 ConfigLoaderSecurityError."""

    def test_include_path_traversal_raises_security_error(self, tmp_path: Path):
        """路径遍历 !include ../outside/file.yml → ConfigLoaderSecurityError."""
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

    def test_path_traversal_via_symlink_raises_security_error(self, tmp_path: Path):
        """symlink 路径遍历 → ConfigLoaderSecurityError."""
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

        config = sandbox / "ae-template.yml"
        config.write_text("included: !include link_to_outside/_evil.yml\n")

        # symlink 解析后 realpath 应该指向 sandbox 外,被 ConfigLoaderSecurityError 拒绝
        with pytest.raises(ConfigLoaderSecurityError):
            _load_yaml_with_includes(config, sandbox_roots=[str(sandbox)])
