"""FR-093 / SC-011: the six core command skills teach only the shipped model (WP17, #7285).

The guard fails on four kinds of stale text: the retired ``spec-kitty merge``
command, a manual stale-lane recipe (``cd .worktrees/...`` then ``git merge`` or
``git rebase``), advice to hand-commit status files, and lease-behaviour text
(the lease is not shipped, C-007). Each pattern carries a planted-string
self-test so the guard cannot pass vacuously.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.fast]

SKILLS_ROOT = Path(__file__).resolve().parents[2] / "src" / "charter" / "offering" / "skills"
GUARDED_SKILLS: tuple[str, ...] = (
    "spec-kitty-implement-review",
    "spec-kitty-git-workflow",
    "spec-kitty-program-orchestrate",
    "spec-kitty-mission-review",
    "spk-gate-consolidate",
    "spk-run-blocked-recovery",
)

#: ``spec-kitty merge`` but not ``spec-kitty merge-driver-*``.
RETIRED_MERGE_COMMAND = re.compile(r"spec-kitty merge(?![-\w])")
#: ``cd .worktrees/...`` followed shortly by a hand ``git merge`` / ``git rebase``.
MANUAL_STALE_LANE_RECIPE = re.compile(r"cd \.worktrees/[\s\S]{0,400}?git (?:merge|rebase)\b")
#: Advice to commit status files by hand.
HAND_STATUS_COMMIT = re.compile(
    r"commit (?:all )?status (?:changes|files)|git add [^\n]*status\.(?:events\.jsonl|json)|git commit [^\n]*status\.(?:events\.jsonl|json)",
    re.IGNORECASE,
)
#: Lease behaviour (word "lease", not "release").
LEASE_TEXT = re.compile(r"\blease[sd]?\b", re.IGNORECASE)

FORBIDDEN: dict[str, re.Pattern[str]] = {
    "retired spec-kitty merge command": RETIRED_MERGE_COMMAND,
    "manual stale-lane recipe": MANUAL_STALE_LANE_RECIPE,
    "hand status commit advice": HAND_STATUS_COMMIT,
    "lease behaviour text": LEASE_TEXT,
}

PLANTED: dict[str, str] = {
    "retired spec-kitty merge command": "Then run `spec-kitty merge --mission demo`.",
    "manual stale-lane recipe": "cd .worktrees/demo-lane-a\ngit merge kitty/mission-demo --no-edit",
    "hand status commit advice": "Commit all status changes from main in one batch.",
    "lease behaviour text": "The implementation lease is released on transition.",
}


def scan(text: str) -> list[str]:
    """Return the names of every forbidden pattern ``text`` contains."""
    return [name for name, pattern in FORBIDDEN.items() if pattern.search(text)]


def _skill_files() -> list[Path]:
    return [SKILLS_ROOT / name / "SKILL.md" for name in GUARDED_SKILLS]


def test_six_skill_files_are_scanned() -> None:
    files = [path for path in _skill_files() if path.is_file()]
    assert len(files) == 6


@pytest.mark.parametrize("skill", GUARDED_SKILLS)
def test_skill_carries_no_forbidden_text(skill: str) -> None:
    text = (SKILLS_ROOT / skill / "SKILL.md").read_text(encoding="utf-8")
    assert scan(text) == []


@pytest.mark.parametrize("name", sorted(FORBIDDEN))
def test_planted_string_is_caught(name: str, tmp_path: Path) -> None:
    planted = tmp_path / "SKILL.md"
    planted.write_text(f"# Planted\n\n{PLANTED[name]}\n", encoding="utf-8")
    assert name in scan(planted.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "allowed",
    [
        "spec-kitty consolidate --mission demo",
        "git config merge.spec-kitty-event-log.driver 'spec-kitty merge-driver-event-log %O %A %B'",
        "Release it after the loop ends.",
        "spec-kitty agent tasks status --mission demo",
    ],
)
def test_allowed_text_passes(allowed: str) -> None:
    assert scan(allowed) == []
