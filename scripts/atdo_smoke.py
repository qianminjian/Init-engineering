#!/usr/bin/env python3.12
"""atdo Runtime Smoke Helper

Validates phase completion via 5 static dimensions + 1 dynamic runtime_smoke.
See docs/atdo-runtime-smoke-policy.md for the full policy.

Usage:
    python3.12 scripts/atdo_smoke.py --phase <phase-id>

Exit codes:
    0 - All dimensions PASS
    1 - One or more dimensions FAIL
    2 - Invalid arguments
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class DimensionResult:
    name: str
    kind: str  # "static" | "dynamic"
    passed: bool
    detail: str = ""


def check_file_existence(phase: str) -> DimensionResult:
    """Static: critical v2.1 modules exist."""
    critical = [
        "auto_engineering/loop/state.py",
        "auto_engineering/loop/orchestrator.py",
        "auto_engineering/loop/checkpoint.py",
        "auto_engineering/cli.py",
        "auto_engineering/gates/__init__.py",
    ]
    missing = [p for p in critical if not (PROJECT_ROOT / p).exists()]
    return DimensionResult(
        "fileExistence", "static", not missing,
        f"missing={missing}" if missing else "all critical files present",
    )


def check_syntax(phase: str) -> DimensionResult:
    """Static: py_compile critical modules."""
    targets = [
        "auto_engineering/loop/state.py",
        "auto_engineering/loop/orchestrator.py",
        "auto_engineering/cli.py",
    ]
    import py_compile
    errors = []
    for t in targets:
        try:
            py_compile.compile(str(PROJECT_ROOT / t), doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(f"{t}: {e}")
    return DimensionResult(
        "syntax", "static", not errors,
        f"errors={errors}" if errors else "all modules compile",
    )


def check_runtime_smoke(phase: str) -> DimensionResult:
    """Dynamic: exercise CheckpointEnvelope + Channel round-trip serialization.
    v2.3 P0-A: 原 LoopState (v2.0 Pydantic) 重命名为 CheckpointEnvelope.
    """
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from auto_engineering.loop.state import (
            CheckpointEnvelope,
            LastValueChannel,
        )

        # Test 1: empty CheckpointEnvelope round-trip
        state = CheckpointEnvelope()
        dumped = state.model_dump()
        restored = CheckpointEnvelope.model_validate(dumped)
        if restored.model_dump() != dumped:
            return DimensionResult(
                "runtimeSmoke", "dynamic", False,
                "empty CheckpointEnvelope round-trip MISMATCH",
            )

        # Test 2: LastValueChannel round-trip (LangGraph style)
        ch = LastValueChannel[str]("test_channel")
        ch.update("test_value")
        ch_copy = ch.copy()
        ok_channel = ch_copy.get() == "test_value"

        # Test 3: from_checkpoint on LastValueChannel
        ch_ckpt = LastValueChannel[str]("ckpt_channel")
        ch_ckpt.from_checkpoint("checkpoint_value")
        ok_ckpt = ch_ckpt.get() == "checkpoint_value"

        if not (ok_channel and ok_ckpt):
            return DimensionResult(
                "runtimeSmoke", "dynamic", False,
                f"channel round-trip failed: copy={ok_channel} ckpt={ok_ckpt}",
            )

        return DimensionResult(
            "runtimeSmoke", "dynamic", True,
            "LoopState + LastValueChannel round-trip OK",
        )
    except Exception as e:
        return DimensionResult(
            "runtimeSmoke", "dynamic", False,
            f"exception: {type(e).__name__}: {e}",
        )


def check_debug_residue(phase: str) -> DimensionResult:
    """Static: no DEBUG residue in loop/."""
    import re
    pattern = re.compile(r"#\s*DEBUG:|#\s*FIXME:|\bprint\(.*DEBUG", re.IGNORECASE)
    targets = list((PROJECT_ROOT / "auto_engineering" / "loop").rglob("*.py"))
    residues = []
    for t in targets:
        try:
            content = t.read_text(encoding="utf-8")
        except Exception:
            continue
        for i, line in enumerate(content.splitlines(), 1):
            if pattern.search(line):
                residues.append(f"{t.name}:{i}")
    return DimensionResult(
        "debugResidue", "static", not residues,
        f"found={residues[:5]}" if residues else "clean",
    )


def check_secret_scan(phase: str) -> DimensionResult:
    """Static: no obvious secrets in loop/."""
    import re
    patterns = [
        re.compile(r"sk-ant-[a-zA-Z0-9\-]{20,}"),
        re.compile(r"Bearer\s+[a-zA-Z0-9\-_\.]{20,}"),
    ]
    targets = list((PROJECT_ROOT / "auto_engineering" / "loop").rglob("*.py"))
    hits = []
    for t in targets:
        try:
            content = t.read_text(encoding="utf-8")
        except Exception:
            continue
        for pat in patterns:
            if pat.search(content):
                hits.append(t.name)
                break
    return DimensionResult(
        "secretScan", "static", not hits,
        f"hits={hits}" if hits else "clean",
    )


DIMENSIONS = [
    check_file_existence,
    check_syntax,
    check_runtime_smoke,
    check_debug_residue,
    check_secret_scan,
]


def main() -> int:
    parser = argparse.ArgumentParser(description="atdo Runtime Smoke Helper")
    parser.add_argument("--phase", required=True, help="Phase identifier (e.g. v2.1-F)")
    args = parser.parse_args()

    print(f"[atdo-smoke] phase={args.phase}")
    print("-" * 60)

    all_pass = True
    for fn in DIMENSIONS:
        result = fn(args.phase)
        marker = "PASS" if result.passed else "FAIL"
        print(f"[{marker}] {result.name:<16} ({result.kind:<7}) {result.detail}")
        if not result.passed:
            all_pass = False

    print("-" * 60)
    if all_pass:
        print(f"[atdo-smoke] phase={args.phase} status=PASS")
        return 0
    print(f"[atdo-smoke] phase={args.phase} status=FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())