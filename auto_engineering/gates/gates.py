"""闸门实现."""

import subprocess
from pathlib import Path

from .base import Gate, GateResult


class PlanExistsGate(Gate):
    """Architect 完成后：plan 文件存在？"""

    def check(self, stage, context) -> GateResult:
        if not Path("design/dev-loop-plan.md").exists():
            return GateResult.fail("plan 文件不存在")
        return GateResult.pass_()


class GitCleanGate(Gate):
    """Developer 完成后：git status 干净？"""

    def check(self, stage, context) -> GateResult:
        result = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True
        )
        if result.stdout.strip():
            return GateResult.fail(f"存在未提交变更:\n{result.stdout}")
        return GateResult.pass_()


class TestsPassGate(Gate):
    """Developer 每批完成后：测试全绿？"""

    def check(self, stage, context) -> GateResult:
        result = subprocess.run(["npm", "test"], capture_output=True)
        if result.returncode != 0:
            return GateResult.fail("测试未通过")
        return GateResult.pass_()


class GitDiffExistsGate(Gate):
    """Critic 入口：有 git diff 可审查？"""

    def check(self, stage, context) -> GateResult:
        if not getattr(context, "git_commits", None):
            return GateResult.fail("无 git commit，请 Developer 先提交")
        return GateResult.pass_()
