"""闸门基类."""

from dataclasses import dataclass


@dataclass
class GateResult:
    """闸门检查结果。"""

    passed: bool
    message: str = ""

    @classmethod
    def pass_(cls, msg: str = "") -> "GateResult":
        return cls(passed=True, message=msg)

    @classmethod
    def fail(cls, msg: str) -> "GateResult":
        return cls(passed=False, message=msg)


class Gate:
    """闸门基类。参考 LangGraph interrupt_before/after 模式。"""

    def check(self, stage, context) -> GateResult:
        raise NotImplementedError
