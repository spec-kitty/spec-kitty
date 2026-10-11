"""#5964 unit coverage: the ``.agents/skills/`` untrack ownership selection.

``AgentsSkillsGitignoreBackfillMigration`` must untrack only the paths spec-kitty
itself projects into the shared ``.agents/skills/`` root -- never a team's own
committed skill that happens to share the prefix (#5964). The classifier
(``is_projected_skills_path`` / ``manifest_owned_skills_paths``) is the single
ownership authority this scoping is built on; these tests pin, directly and
without a git repo, that it recognises both projected shapes (the canonical
``spec-kitty.<command>`` command-skill pattern and either manifest's recorded
``installed_path``) and classifies a team skill as kept.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.clock import now_utc_iso
from specify_cli.skills import manifest_store
from specify_cli.skills.manifest import (
    ManagedFileEntry,
    ManagedSkillManifest,
    save_manifest,
)
from specify_cli.skills.manifest_store import ManifestEntry, SkillsManifest
from specify_cli.skills.ownership import is_projected_skills_path, manifest_owned_skills_paths

pytestmark = [pytest.mark.unit, pytest.mark.regression]

_COMMAND_SKILL = ".agents/skills/spec-kitty.implement/SKILL.md"
_PACK_SKILL = ".agents/skills/acme-house-style/SKILL.md"
_TEAM_SKILL = ".agents/skills/team-review/SKILL.md"


def test_canonical_command_skill_is_projected_by_pattern_alone() -> None:
    """The stable ``spec-kitty.<command>`` pattern is projected with no manifest."""
    assert is_projected_skills_path(_COMMAND_SKILL, set()) is True


def test_non_canonical_command_name_is_not_projected_by_pattern() -> None:
    """A ``spec-kitty.<unknown>`` directory is not a canonical command -> not projected by pattern."""
    assert is_projected_skills_path(".agents/skills/spec-kitty.notacommand/SKILL.md", set()) is False


def test_team_skill_is_not_projected() -> None:
    """A team-authored skill owned by neither pattern nor manifest is kept (team content)."""
    assert is_projected_skills_path(_TEAM_SKILL, set()) is False


def test_manifest_owned_pack_skill_is_projected() -> None:
    """A pack skill is projected purely by its manifest ``installed_path`` ownership."""
    assert is_projected_skills_path(_PACK_SKILL, {_PACK_SKILL}) is True


def test_command_skills_manifest_contributes_installed_paths(tmp_path: Path) -> None:
    """``manifest_owned_skills_paths`` reads ``command-skills-manifest.json`` entry paths."""
    root = tmp_path / "repo"
    root.mkdir()
    manifest = SkillsManifest(
        entries=[
            ManifestEntry(
                path=_COMMAND_SKILL,
                content_hash="0" * 64,
                agents=("codex",),
                installed_at=now_utc_iso(),
                spec_kitty_version="3.2.5",
            )
        ]
    )
    manifest_store.save(root, manifest)

    owned = manifest_owned_skills_paths(root)
    assert _COMMAND_SKILL in owned
    assert is_projected_skills_path(_COMMAND_SKILL, owned) is True


def test_skills_manifest_contributes_installed_paths(tmp_path: Path) -> None:
    """``manifest_owned_skills_paths`` reads ``skills-manifest.json`` ``installed_path`` values."""
    root = tmp_path / "repo"
    root.mkdir()
    manifest = ManagedSkillManifest(
        entries=[
            ManagedFileEntry(
                skill_name="acme-house-style",
                source_file="SKILL.md",
                installed_path=_PACK_SKILL,
                installation_class="shared-root-capable",
                agent_key="codex",
                content_hash="sha256:" + "0" * 64,
                installed_at=now_utc_iso(),
                origin="pack",
            )
        ]
    )
    save_manifest(manifest, root)

    owned = manifest_owned_skills_paths(root)
    assert _PACK_SKILL in owned
    assert is_projected_skills_path(_PACK_SKILL, owned) is True


def test_absent_manifests_yield_no_owned_paths_so_team_content_is_kept(tmp_path: Path) -> None:
    """With no manifest on disk, only the pattern projects; a team skill stays kept."""
    root = tmp_path / "repo"
    root.mkdir()
    owned = manifest_owned_skills_paths(root)
    assert owned == set()
    assert is_projected_skills_path(_TEAM_SKILL, owned) is False
    assert is_projected_skills_path(_COMMAND_SKILL, owned) is True


def test_corrupt_command_skills_manifest_is_fail_closed_toward_preservation(tmp_path: Path) -> None:
    """An unreadable manifest contributes nothing, so its paths stay tracked (never over-untrack)."""
    root = tmp_path / "repo"
    (root / ".kittify").mkdir(parents=True)
    (root / ".kittify" / "command-skills-manifest.json").write_text("{ not json", encoding="utf-8")

    owned = manifest_owned_skills_paths(root)
    assert owned == set()
    assert is_projected_skills_path(_TEAM_SKILL, owned) is False
