# Shared detection utilities — consumed by both config/ and init/ layers.

from .detection import detect_ci_platform, detect_package_manager, detect_test_runner

__all__ = [
    "detect_ci_platform",
    "detect_package_manager",
    "detect_test_runner",
]
