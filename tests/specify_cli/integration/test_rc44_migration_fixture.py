"""rc44-era migration acceptance fixture (T041, FR-041).

Certification gate for the whole mission: a project frozen in the state that
existed just before this mission's changes — ``claude`` + ``codex`` configured,
a stale (short) command-skill manifest, and **no** native agent-profile
directories — must, after ``spec-kitty upgrade --yes``, satisfy ALL of:

  * ``.claude/agents/`` exists and contains ``*.md`` profiles with frontmatter
  * ``.codex/agents/`` exists and contains ``*.toml`` profiles
  * the command-skill manifest is repaired to the canonical entry count
  * ``doctor tool-surfaces --kind agent-profile --json`` reports zero
    missing/stale/drifted for claude and codex
  * the upgrade exits 0

The fixture deliberately drives the **real** CLI (``spec-kitty init`` then
``spec-kitty upgrade``) rather than calling ``run_surface_repair`` directly:
calling it would bypass the init/upgrade wiring and pass even if the commands
were never connected to the repair service (FR-001/FR-002).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from specify_cli.skills.command_installer import CANONICAL_COMMANDS

from ..tool_surface.integration._compat_support import run_spec_kitty

pytestmark = [pytest.mark.integration, pytest.mark.non_sandbox]

_HEALTHY_AGENT_STATES = {"present", "not_applicable"}


@pytest.fixture
def rc44_project(tmp_path: Path) -> Path:
    """Return a project frozen in rc44 state (claude+codex, short manifest, no profiles).

    Built by first running a real ``init`` (so the project owns canonical
    templates and a self-consistent manifest), then degrading it to the rc44
    shape the upgrade path must heal.
    """
    init_result = run_spec_kitty(
        "init", "--ai", "claude,codex", "--non-interactive", cwd=tmp_path
    )
    assert init_result.returncode == 0, (
        f"init failed:\nstdout: {init_result.stdout}\nstderr: {init_result.stderr}"
    )

    # Degrade 1 — remove native agent-profile directories entirely.
    for profile_dir in ((tmp_path / ".claude" / "agents"), (tmp_path / ".codex" / "agents")):
        if profile_dir.exists():
            shutil.rmtree(profile_dir)

    # Degrade 2 — truncate the manifest to a single entry (rc44 had fewer
    # commands than the current canonical set).
    manifest_path = tmp_path / ".kittify" / "command-skills-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["entries"] = manifest["entries"][:1]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return tmp_path


def test_upgrade_heals_rc44_project(rc44_project: Path) -> None:
    """Full upgrade from rc44 state heals all surfaces and repairs the manifest."""
    result = run_spec_kitty("upgrade", "--yes", cwd=rc44_project)
    assert result.returncode == 0, (
        f"upgrade --yes failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Native agent-profile directories recreated for both configured agents.
    claude_agents = rc44_project / ".claude" / "agents"
    codex_agents = rc44_project / ".codex" / "agents"
    assert claude_agents.exists(), ".claude/agents/ must be created by upgrade"
    assert codex_agents.exists(), ".codex/agents/ must be created by upgrade"

    claude_mds = list(claude_agents.glob("*.md"))
    assert claude_mds, ".claude/agents/ must contain at least one .md profile"
    for md in claude_mds:
        content = md.read_text(encoding="utf-8")
        assert content.startswith("---"), f"{md.name} must have YAML frontmatter"

    codex_tomls = list(codex_agents.glob("*.toml"))
    assert codex_tomls, ".codex/agents/ must contain at least one .toml profile"

    # Manifest repaired to the canonical entry count.
    manifest = json.loads(
        (rc44_project / ".kittify" / "command-skills-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest.get("schema_version") == 1
    assert "entries" in manifest, "repaired manifest must use the 'entries' key"
    assert len(manifest["entries"]) == len(CANONICAL_COMMANDS), (
        f"manifest has {len(manifest['entries'])} entries, "
        f"expected {len(CANONICAL_COMMANDS)}"
    )


def test_doctor_agent_profile_clean_after_rc44_upgrade(rc44_project: Path) -> None:
    """After healing, ``doctor`` reports no missing/stale/drifted agent profiles."""
    upgrade = run_spec_kitty("upgrade", "--yes", cwd=rc44_project)
    assert upgrade.returncode == 0, upgrade.stderr

    doctor = run_spec_kitty(
        "doctor", "tool-surfaces", "--kind", "agent-profile", "--json", cwd=rc44_project
    )
    payload = doctor.json()
    states = {surface["state"] for surface in payload["surfaces"]}
    assert states <= _HEALTHY_AGENT_STATES, (
        f"unhealthy agent-profile states after rc44 upgrade: "
        f"{states - _HEALTHY_AGENT_STATES}"
    )
    tools = {surface["tool"] for surface in payload["surfaces"]}
    assert {"claude", "codex"} <= tools, (
        "both configured agents must appear in the agent-profile surface report"
    )
    assert payload["ok"] is True, "doctor must report ok after rc44 healing"


def test_rc44_upgrade_is_idempotent(rc44_project: Path) -> None:
    """A second upgrade after healing changes nothing (NFR-006)."""
    first = run_spec_kitty("upgrade", "--yes", cwd=rc44_project)
    assert first.returncode == 0, first.stderr

    before = {
        path.relative_to(rc44_project): path.read_bytes()
        for path in rc44_project.rglob("*")
        if path.is_file()
    }
    second = run_spec_kitty("upgrade", "--yes", cwd=rc44_project)
    assert second.returncode == 0, second.stderr
    after = {
        path.relative_to(rc44_project): path.read_bytes()
        for path in rc44_project.rglob("*")
        if path.is_file()
    }
    assert after == before, "second rc44 upgrade must not change any file bytes"
