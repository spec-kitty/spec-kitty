"""Regression coverage for #3651 on the 2 hard-crash migration sites.

PR #3679 introduced ``write_generated_file`` (the canonical restore→write→
strip-permission-bit writer) and routed 16 migrations through it, but left 5
sibling migrations writing bare ``Path.write_text(...)`` to the same
read-only-destined agent command/skill surfaces (``runtime/agent_commands.py``
and ``runtime/agent_skills.py`` chmod these trees ``& ~0o222``). Two of those
five have no ``try/except`` around the write at all, so a re-run against an
already-generated (and therefore read-only) target raises ``PermissionError``
and aborts the whole upgrade — #3651 verbatim:

1. ``m_3_2_0rc35_kittify_profile_handoff.py`` (``_apply_patch_to_file``) —
   writes ``.agents/skills/spec-kitty.*/SKILL.md``.
2. ``m_0_11_3_workflow_agent_flag.py`` (``_update_workflow_lines``) — writes
   ``spec-kitty.implement.md`` / ``spec-kitty.review.md`` in agent command
   dirs.

Each test below creates a read-only target file that already needs the
migration's edit, then asserts ``apply()`` does not raise ``PermissionError``
and that the edit is actually applied (not silently dropped).
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_0_11_3_workflow_agent_flag import (
    WorkflowAgentFlagMigration,
)
from specify_cli.upgrade.migrations.m_3_2_0rc35_kittify_profile_handoff import (
    KittifyProfileHandoffMigration,
    _HANDOFF_SENTINEL,
)
from tests._support.eacces import deny_path_method

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Spec Kitty"], cwd=root, check=True, capture_output=True)


_SKILL_IMPLEMENT_WITHOUT_HANDOFF = """\
---
title: /spec-kitty.implement
---

# /spec-kitty.implement - Implement Work Package

## Output

Record your changes.
"""


def test_kittify_profile_handoff_rewrites_readonly_skill_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A previously-generated read-only SKILL.md must not crash the upgrade.

    Before the fix, ``_apply_patch_to_file`` calls a bare
    ``path.write_text(...)`` with no surrounding ``try/except`` — the
    ``PermissionError`` raised on a 0o444 target propagates straight out of
    ``apply()`` and aborts the upgrade.
    """
    project_path = tmp_path
    _init_git_repo(project_path)

    skill_path = project_path / ".agents" / "skills" / "spec-kitty.implement" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(_SKILL_IMPLEMENT_WITHOUT_HANDOFF, encoding="utf-8")
    skill_path.chmod(0o444)
    # Root writes through a 0o444 file, so deny an in-place Path write of it
    # for every uid (#5691). The managed writer's contract is to replace the
    # file, never to rewrite it in place, so the denial does not lift.
    for attr in ("write_text", "write_bytes"):
        deny_path_method(monkeypatch, attr, skill_path)

    migration = KittifyProfileHandoffMigration()

    # Assumption check: the migration recognizes this file needs the edit.
    assert _HANDOFF_SENTINEL not in skill_path.read_text(encoding="utf-8")

    # Act — must not raise PermissionError.
    result = migration.apply(project_path, dry_run=False)

    # Assert: succeeded and the edit was actually applied, not dropped.
    assert result.success is True
    new_content = skill_path.read_text(encoding="utf-8")
    assert _HANDOFF_SENTINEL in new_content, "edit must be applied, not silently skipped"

    # The file must be left read-only again (managed generated-file state).
    assert stat.S_IMODE(skill_path.stat().st_mode) & 0o222 == 0


def test_workflow_agent_flag_rewrites_readonly_command_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A previously-generated read-only implement.md must not crash the upgrade.

    Before the fix, ``_update_workflow_lines`` calls a bare
    ``path.write_text(...)`` with no surrounding ``try/except`` — the
    ``PermissionError`` raised on a 0o444 target propagates straight out of
    ``apply()`` and aborts the upgrade.
    """
    project_path = tmp_path
    _init_git_repo(project_path)
    (project_path / ".kittify").mkdir()

    command_path = project_path / ".claude" / "commands" / "spec-kitty.implement.md"
    command_path.parent.mkdir(parents=True)
    command_path.write_text("spec-kitty agent action implement WP01\n", encoding="utf-8")
    command_path.chmod(0o444)
    # Root writes through a 0o444 file, so deny an in-place Path write of it
    # for every uid (#5691). The managed writer's contract is to replace the
    # file, never to rewrite it in place, so the denial does not lift.
    for attr in ("write_text", "write_bytes"):
        deny_path_method(monkeypatch, attr, command_path)

    migration = WorkflowAgentFlagMigration()

    # Assumption check: the migration recognizes this file needs the edit.
    assert migration.detect(project_path) is True

    # Act — must not raise PermissionError.
    result = migration.apply(project_path, dry_run=False)

    # Assert: succeeded and the edit was actually applied, not dropped.
    assert result.success is True
    new_content = command_path.read_text(encoding="utf-8")
    assert "spec-kitty agent action implement WP01 --agent claude" in new_content, "edit must be applied, not silently skipped"

    # The file must be left read-only again (managed generated-file state).
    assert stat.S_IMODE(command_path.stat().st_mode) & 0o222 == 0
