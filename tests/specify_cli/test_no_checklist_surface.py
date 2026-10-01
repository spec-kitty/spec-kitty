"""Aggregate scanner — verify the deprecated `/spec-kitty.checklist`
slash-command surface is fully retired (FR-003, FR-004 / WP04 / #815).

This is the future-proofing regression: if a future change recreates the
deprecated surface anywhere under the scanned roots, both tests fail.

Allowlist
---------
Legitimate "checklist" concepts are carved out so the scanner only flags
the retired command surface:

* `kitty-specs/<m>/checklists/` — the canonical mission requirements
  checklist artifact (C-003) MUST keep working.
* `RELEASE_CHECKLIST.md` — repo release checklist, unrelated.
* Any filename containing `release_checklist` / `release-checklist` /
  `review_checklist` / `review-checklist` — generic concepts.
"""

from __future__ import annotations

import re
from pathlib import Path


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]

# The slash-command identifier itself — must be gone everywhere.
CHECKLIST_CMD_RE = re.compile(r"/?spec-kitty\.checklist\b")

# Deprecated agent-surface filenames. The allowlist below carves out
# legitimate "checklist" concepts (mission requirements checklist,
# release checklist, review checklist) so the scanner only flags the
# retired command surface.
CHECKLIST_FILENAME_RE = re.compile(r"(^|[/\\])checklist(\.SKILL|\.prompt)?\.md$")

SCAN_ROOTS = [
    "src/specify_cli/missions",
    "tests/specify_cli/regression",
    "tests/specify_cli/skills/__snapshots__",
    "docs",
]

# Per-agent rendered surfaces (rendered into the dev project itself).
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

# Allowlist: reserved for legitimate "checklist" concepts unrelated to
# the retired slash command. Anything matching is skipped by the scanner.
ALLOWLIST_PREFIXES = (
    "kitty-specs/",  # mission-level checklists/ directory is canonical
    # Historical engineering analysis (triage / closeout / retrospectives) is
    # narrative prose about the retired command, not a live command surface.
    # (The 01KSMG8Y closeout moved from docs/ to docs/plans/engineering-notes/,
    # then to docs/archive/plans/engineering-notes/ in #5428; see #5505.)
    "docs/archive/plans/engineering-notes/",
    "docs/changelog/",  # immutable changelog documenting the REMOVED command, not a live surface
)

ALLOWLIST_FILENAMES = (
    "RELEASE_CHECKLIST.md",
    # Generated dashboard backlog asset; lists historical issue titles
    # (e.g. "#635 Deprecate /spec-kitty.checklist") for narrative context,
    # not as a prescriptive command surface.
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


def test_no_checklist_filenames_in_scan_roots():
    offenders = []
    for rel in SCAN_ROOTS + AGENT_DIRS:
        for path in _walk(REPO_ROOT / rel):
            if _is_allowlisted(path):
                continue
            if CHECKLIST_FILENAME_RE.search(str(path)):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, (
        "Found deprecated checklist filenames:\n  " + "\n  ".join(offenders)
    )


def test_no_checklist_command_string_in_scan_roots():
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
    assert not offenders, (
        "Found references to /spec-kitty.checklist:\n  " + "\n  ".join(offenders)
    )
