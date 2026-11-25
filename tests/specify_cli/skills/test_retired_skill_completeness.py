"""Every skill name removed from the shipped catalog is retired, and shipped skills route only to shipped skills (#7702).

The completeness guard reads a frozen list, not git history: a shallow clone or a
history rewrite must not weaken it. ``EVER_SHIPPED_SKILL_NAMES`` is that list.
Adding a skill means adding its name here; removing or renaming one means adding
the old name to ``RETIRED_CANONICAL_SKILL_NAMES`` so the global skill sync
retires an unedited old copy instead of preserving it as a custom skill.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from specify_cli.skills.registry import SkillRegistry
from specify_cli.skills.retired import RETIRED_CANONICAL_SKILL_NAMES, RETIRED_STANDALONE_SKILL_NAMES

pytestmark = [pytest.mark.fast]

#: Every canonical skill name the package has shipped, frozen (append-only).
EVER_SHIPPED_SKILL_NAMES = frozenset(
    {
        # Shipped today.
        "adversarial-squad",
        "spec-kitty",
        "spec-kitty-git-workflow",
        "spec-kitty-implement-review",
        "spec-kitty-mission-review",
        "spec-kitty-mission-system",
        "spec-kitty-orchestrator-api-operator",
        "spec-kitty-program-orchestrate",
        "spec-kitty-runtime-next",
        "spec-kitty-runtime-review",
        "spec-kitty-setup-doctor",
        "spk-admin-agent-config",
        "spk-admin-git-workflow",
        "spk-admin-setup-doctor",
        "spk-admin-upgrade",
        "spk-charter-glossary",
        "spk-charter-governance",
        "spk-charter-profile-load",
        "spk-charter-spdd-reasons",
        "spk-gate-accept",
        "spk-gate-consolidate",
        "spk-gate-mission-review",
        "spk-gate-retrospective",
        "spk-integrate-orchestrator-api",
        "spk-meta-skill-authoring",
        "spk-meta-skill-map",
        "spk-mission-documentation",
        "spk-mission-plan",
        "spk-mission-research",
        "spk-mission-specify",
        "spk-mission-tasks",
        "spk-mission-types",
        "spk-practice-bulk-edit",
        "spk-practice-semantic-compression",
        "spk-practice-show-me",
        "spk-run-blocked-recovery",
        "spk-run-implement-review",
        "spk-run-next",
        "spk-run-program-orchestrate",
        "spk-run-review-wp",
        "spk-run-verdict-capture",
        "spk-start-agent-surface",
        "spk-start-command-map",
        "spk-start-first-mission",
        "spk-start-here",
        # Removed since; each must stay retired.
        "ad-hoc-profile-load",
        "debugger-debbie",
        "paula-patterns",
        "spec-kitty-bulk-edit-classification",
        "spec-kitty-charter-doctrine",
        "spec-kitty-constitution-doctrine",
        "spec-kitty-glossary-context",
        "spec-kitty-spdd-reasons",
        "spk-admin-dashboard",
        "spk-doctrine-bulk-edit",
        "spk-doctrine-charter",
        "spk-doctrine-glossary",
        "spk-doctrine-profile-load",
        "spk-doctrine-semantic-compression",
        "spk-doctrine-show-me",
        "spk-doctrine-spdd-reasons",
        "spk-gate-merge",
        "spk-start-first-feature",
        "spk-team-auth",
        "spk-team-connectors",
        "spk-team-sync",
        "spk-team-tracker",
        "spk-team-upsun-cli-sync",
    }
)

#: A concrete ``spk-*`` skill name: two or more segments after ``spk``, not a
#: family glob (``spk-gate-*``) and not a reference file name (``spk-skill-map.md``).
_SPK_NAME = re.compile(r"(?<![\w-])spk(?:-[a-z0-9]+){2,}(?![\w*-]|\.\w)")


#: Retired skill names that are also live agent-profile ids: skill text may name the profile.
_LIVE_AGENT_PROFILE_IDS = frozenset({"debugger-debbie", "paula-patterns"})


def _registry() -> SkillRegistry:
    return SkillRegistry.from_package()


def _shipped_names() -> set[str]:
    return {skill.name for skill in _registry().discover_skills()}


def _shipped_text_files() -> list[Path]:
    root = Path(_registry()._skills_root)
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in {".md", ".yaml", ".yml", ".txt"})


def _scan(pattern: re.Pattern[str]) -> dict[str, set[str]]:
    hits: dict[str, set[str]] = {}
    for path in _shipped_text_files():
        for name in pattern.findall(path.read_text(encoding="utf-8")):
            hits.setdefault(name, set()).add(path.name if path.parent.name == "skills" else f"{path.parent.name}/{path.name}")
    return hits


def test_every_shipped_skill_is_in_the_frozen_list() -> None:
    missing = _shipped_names() - EVER_SHIPPED_SKILL_NAMES
    assert not missing, f"add the new skill name(s) to EVER_SHIPPED_SKILL_NAMES: {sorted(missing)}"


def test_every_removed_skill_name_is_retired() -> None:
    removed = EVER_SHIPPED_SKILL_NAMES - _shipped_names()
    assert "spk-gate-merge" in removed, "control: the #7702 rename is in the removed set"
    unretired = removed - RETIRED_CANONICAL_SKILL_NAMES
    assert not unretired, f"add the removed skill name(s) to RETIRED_CANONICAL_SKILL_NAMES: {sorted(unretired)}"


def test_no_shipped_skill_is_retired() -> None:
    overlap = _shipped_names() & (RETIRED_CANONICAL_SKILL_NAMES - RETIRED_STANDALONE_SKILL_NAMES)
    assert not overlap, sorted(overlap)


def test_shipped_skill_text_names_only_shipped_spk_skills() -> None:
    shipped = _shipped_names()
    hits = _scan(_SPK_NAME)
    assert "spk-gate-consolidate" in hits, "control: the scan sees skill routes"
    dangling = {name: sorted(files) for name, files in hits.items() if name not in shipped}
    assert not dangling, f"shipped skill text routes to unshipped skills: {dangling}"


def test_shipped_skill_text_names_no_retired_skill() -> None:
    names = RETIRED_CANONICAL_SKILL_NAMES - RETIRED_STANDALONE_SKILL_NAMES - _LIVE_AGENT_PROFILE_IDS
    retired_names = sorted(names, key=len, reverse=True)
    pattern = re.compile(r"(?<![\w-])(" + "|".join(map(re.escape, retired_names)) + r")(?![\w*-]|\.\w)")
    hits = _scan(pattern)
    assert not hits, f"shipped skill text names retired skills: { {n: sorted(f) for n, f in hits.items()} }"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("route to `spk-gate-merge`.", ["spk-gate-merge"]),
        ("- `spk-gate-*`: accept", []),
        ("`references/spk-skill-map.md`", []),
        ("use the `spk-charter-*` family", []),
        ("then `spk-run-next`, then", ["spk-run-next"]),
        ("Then use spk-gate-merge.", ["spk-gate-merge"]),
    ],
)
def test_spk_name_pattern(text: str, expected: list[str]) -> None:
    assert _SPK_NAME.findall(text) == expected
