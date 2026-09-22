"""Tests for the retired profile-context migration.

The legacy /spec-kitty.profile-context command is no longer part of the
consumer command registry. The migration now removes stale generated copies and
must not recreate them.
"""

from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: A genuinely package-owned generated command carries the version marker, which
#: is what authorizes the retirement delete now that the migration is routed
#: through the ownership guard (a name match alone no longer proves ownership).
_OWNED = "<!-- spec-kitty-command-version: 4.0.0 -->\nlegacy profile-context body\n"


def _write_config(project_path: Path, agents: list[str]) -> None:
    """Write .kittify/config.yaml with the given agent list."""
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        "agents:\n  available:\n"
        + "".join(f"    - {a}\n" for a in agents)
    )


def _make_agent_dir(project_path: Path, agent_root: str, subdir: str) -> Path:
    """Create an agent command directory and return its Path."""
    p = project_path / agent_root / subdir
    p.mkdir(parents=True, exist_ok=True)
    return p


@pytest.fixture()
def migration():
    from specify_cli.upgrade.migrations.m_2_2_0_profile_context_deployment import (
        ProfileContextDeploymentMigration,
    )

    return ProfileContextDeploymentMigration()


# ---------------------------------------------------------------------------
# scenario 1 – removes stale files from configured agents
# ---------------------------------------------------------------------------


def test_migration_removes_from_configured_agents(tmp_path: Path, migration) -> None:
    """Migration removes spec-kitty.profile-context.md in each configured agent dir."""
    _write_config(tmp_path, ["claude", "opencode"])
    claude_dir = _make_agent_dir(tmp_path, ".claude", "commands")
    opencode_dir = _make_agent_dir(tmp_path, ".opencode", "command")
    (claude_dir / "spec-kitty.profile-context.md").write_text(_OWNED, encoding="utf-8")
    (opencode_dir / "spec-kitty.profile-context.md").write_text(_OWNED, encoding="utf-8")

    result = migration.apply(tmp_path)

    assert result.success
    assert not (tmp_path / ".claude" / "commands" / "spec-kitty.profile-context.md").exists()
    assert not (tmp_path / ".opencode" / "command" / "spec-kitty.profile-context.md").exists()


# ---------------------------------------------------------------------------
# T033 scenario 2 – skips unconfigured agents
# ---------------------------------------------------------------------------


def test_migration_skips_unconfigured_agents(tmp_path: Path, migration) -> None:
    """Migration does NOT remove agent dirs that are not in config.yaml."""
    _write_config(tmp_path, ["opencode"])
    claude_dir = _make_agent_dir(tmp_path, ".claude", "commands")   # exists but NOT configured
    opencode_dir = _make_agent_dir(tmp_path, ".opencode", "command")  # configured
    (claude_dir / "spec-kitty.profile-context.md").write_text(_OWNED, encoding="utf-8")
    (opencode_dir / "spec-kitty.profile-context.md").write_text(_OWNED, encoding="utf-8")

    result = migration.apply(tmp_path)

    assert result.success
    assert (tmp_path / ".claude" / "commands" / "spec-kitty.profile-context.md").exists()
    assert not (tmp_path / ".opencode" / "command" / "spec-kitty.profile-context.md").exists()


# ---------------------------------------------------------------------------
# T033 scenario 3 – idempotent
# ---------------------------------------------------------------------------


def test_migration_idempotent(tmp_path: Path, migration) -> None:
    """Running the migration twice produces no errors and does not recreate files."""
    _write_config(tmp_path, ["claude"])
    claude_dir = _make_agent_dir(tmp_path, ".claude", "commands")
    (claude_dir / "spec-kitty.profile-context.md").write_text(_OWNED, encoding="utf-8")

    result1 = migration.apply(tmp_path)
    result2 = migration.apply(tmp_path)

    assert result1.success
    assert result2.success

    dest = tmp_path / ".claude" / "commands" / "spec-kitty.profile-context.md"
    assert not dest.exists()
    assert list(dest.parent.glob("spec-kitty.profile-context*")) == []


# ---------------------------------------------------------------------------
# T033 scenario 4 – skips missing directory
# ---------------------------------------------------------------------------


def test_migration_skips_missing_directory(tmp_path: Path, migration) -> None:
    """Migration silently skips an agent that is configured but whose dir was deleted."""
    _write_config(tmp_path, ["claude"])
    # Do NOT create .claude/commands/ — simulate manual deletion

    result = migration.apply(tmp_path)

    assert result.success
    assert not (tmp_path / ".claude" / "commands" / "spec-kitty.profile-context.md").exists()
