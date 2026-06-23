"""ProjectDetector — 项目类型自动检测（SST 模式）."""

from pathlib import Path

FRAMEWORK_SIGNATURES: list[tuple[str, list[str]]] = [
    ("monorepo",    ["pnpm-workspace.yaml", "lerna.json", "turbo.json", "nx.json"]),
    ("skill",       [".claude/skills/"]),
    ("hook",        [".claude/hooks/"]),
    ("spec-doc",    ["design/BEACON.md"]),
    ("mcp-server",  ["package.json"]),
    ("cli-tool",    ["package.json"]),
    ("library",     ["pyproject.toml", "setup.py", "Cargo.toml", "go.mod"]),
    ("app-service", ["package.json"]),
]


class ProjectDetector:
    def __init__(self, target_dir: Path):
        self.target_dir = target_dir

    def detect(self) -> str | None:
        matches = self.list_candidates()
        if len(matches) == 1:
            return matches[0]
        return None

    def list_candidates(self) -> list[str]:
        matches = []
        for ptype, signatures in FRAMEWORK_SIGNATURES:
            if any((self.target_dir / sig).exists() for sig in signatures):
                matches.append(ptype)
        return matches
