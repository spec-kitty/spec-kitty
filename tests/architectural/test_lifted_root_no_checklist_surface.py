"""Always-on gate: the retired ``/spec-kitty.checklist`` surface stays fully retired.

Source: ``tests/specify_cli/test_no_checklist_surface.py`` (FR-003, FR-004 /
WP04 / #815), which lives directly under ``tests/specify_cli`` — recorded
``out_of_matrix`` in ``.github/ci-module-registry.yml`` (#4374,
decide-out-of-matrix-test-dirs ledger, lift-invariant disposition).

Future-proofing regression scan: if a future change recreates the deprecated
checklist command surface (filenames or the literal ``/spec-kitty.checklist``
token) anywhere under the scanned roots, this fails. Legitimate "checklist"
concepts (the mission requirements checklist under ``kitty-specs/``, release
and review checklists) are allowlisted.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]

REPO_ROOT = Path(__file__).resolve().parents[2]

CHECKLIST_CMD_RE = re.compile(r"/?spec-kitty\.checklist\b")
CHECKLIST_FILENAME_RE = re.compile(r"(^|[/\\])checklist(\.SKILL|\.prompt)?\.md$")

SCAN_ROOTS = [
    "src/specify_cli/missions",
    "tests/specify_cli/regression",
    "tests/specify_cli/skills/__snapshots__",
    "docs",
]

AGENT_DIRS = [
    ".claude/commands",
    ".codex/prompts",
    ".gemini/commands",
    ".cursor/commands",
    ".qwen/commands",
    ".opencode/command",
    ".windsurf/workflows",
    ".kilocode/workflows",
    ".augment/commands",
    ".roo/commands",
    ".amazonq/prompts",
    ".kiro/prompts",
    ".agent/workflows",
    ".github/prompts",
    ".agents/skills",
]

ALLOWLIST_PREFIXES = (
    "kitty-specs/",
    "docs/plans/engineering-notes/",
    # Historical engineering notes moved here by the #5428 docs cleanup.
    "docs/archive/plans/engineering-notes/",
    "docs/changelog/",
)

ALLOWLIST_FILENAMES = (
    "RELEASE_CHECKLIST.md",
    "spec-kitty-backlog.html",
)

ALLOWLIST_SUBSTRINGS = (
    "release_checklist",
    "release-checklist",
    "review_checklist",
    "review-checklist",
)


def _walk(root: Path):
    if not root.exists():
        return
    for p in root.rglob("*"):
        if p.is_file():
            yield p


def _is_allowlisted(path: Path) -> bool:
    posix = path.relative_to(REPO_ROOT).as_posix()
    if any(posix.startswith(p) for p in ALLOWLIST_PREFIXES):
        return True
    if path.name in ALLOWLIST_FILENAMES:
        return True
    lowered = path.name.lower()
    return any(s in lowered for s in ALLOWLIST_SUBSTRINGS)


def test_no_checklist_filenames_in_scan_roots() -> None:
    offenders = []
    for rel in SCAN_ROOTS + AGENT_DIRS:
        for path in _walk(REPO_ROOT / rel):
            if _is_allowlisted(path):
                continue
            if CHECKLIST_FILENAME_RE.search(str(path)):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, "Found deprecated checklist filenames:\n  " + "\n  ".join(offenders)


def test_no_checklist_command_string_in_scan_roots() -> None:
    offenders = []
    for rel in SCAN_ROOTS + AGENT_DIRS:
        for path in _walk(REPO_ROOT / rel):
            if _is_allowlisted(path):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if CHECKLIST_CMD_RE.search(text):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, "Found references to /spec-kitty.checklist:\n  " + "\n  ".join(offenders)
