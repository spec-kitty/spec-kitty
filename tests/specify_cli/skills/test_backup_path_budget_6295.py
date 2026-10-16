"""Regression guard for #6295 -- the migration-backup path length budget.

`spec-kitty upgrade` retains a user file before overwriting it by copying it under
``<project_root>/.kittify/.migration-backup/agent-skills/state-v1-<id>/<installed-path>``.
When ``<id>`` was the full 64-hex SHA-256 the fixed overhead was ~206 characters,
so on Windows with the default ``LongPathsEnabled=0`` any project root deeper than
~54 characters pushed the backup member past the 260-char MAX_PATH ceiling and the
upgrade failed (orthogonal to the read-only #6228). The fix truncates the backup id
(``installer._BACKUP_ID_HEX``) so the layout fits an ordinary deep Windows root.

This is a cross-platform structural guard -- pure path arithmetic over the **real
production allocation** (``prepare_skill_backup`` builds the actual ``state-v1-<id>``
root, and the member mirrors the installed path verbatim). It runs per PR on every
platform, so a regression that regrows the backup id (or otherwise inflates the
overhead) reds here before it can strand a Windows upgrade again.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.skills.installer import SkillBackupReplacement, prepare_skill_backup
from specify_cli.tool_surface.operations import FileState

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: Classic Win32 ``MAX_PATH`` ceiling (``LongPathsEnabled=0``, no ``\\?\`` prefix).
MAX_PATH = 260

#: A representative managed skill reference file -- a real currently-shipped charter
#: skill (the longest-named one), mirrored verbatim under the backup root. Any managed
#: skill reference member is retained the same way; this is the worst current case.
REPRESENTATIVE_INSTALLED_MEMBER = ".agents/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md"

#: A reasonable budget for an ordinary Windows project root, e.g.
#: ``C:\Users\firstname.lastname\source\repos\acme-platform\spec-kitty`` (~65 chars).
#: The backup layout must leave at least this much room for the project root under
#: ``MAX_PATH``.
REASONABLE_WINDOWS_ROOT_BUDGET = 72


def _real_backup_overhead(tmp_path: Path) -> int:
    """Characters the real backup layout appends after the project root.

    Built end-to-end from production: ``prepare_skill_backup`` allocates the actual
    ``.kittify/.migration-backup/agent-skills/state-v1-<id>`` root (no writes), and the
    member mirrors the installed path exactly as ``_archive_existing_path`` writes it.
    """
    replacement = SkillBackupReplacement(
        REPRESENTATIVE_INSTALLED_MEMBER,
        FileState("file", sha256="a" * 64, mode=0o444),
        FileState("file", sha256="b" * 64, mode=0o444),
    )
    prepared = prepare_skill_backup(tmp_path, (replacement,))
    member = prepared.root / Path(REPRESENTATIVE_INSTALLED_MEMBER)
    return len(member.as_posix()) - len(tmp_path.as_posix())


def test_backup_overhead_leaves_room_for_a_reasonable_windows_root(tmp_path: Path) -> None:
    """The fixed backup overhead must not consume the whole ``MAX_PATH`` budget.

    The layout must leave at least ``REASONABLE_WINDOWS_ROOT_BUDGET`` characters for the
    project root. With the full 64-hex id the overhead was ~206, leaving only ~54 -- the
    #6295 defect. The truncated id brings it comfortably under budget.
    """
    overhead = _real_backup_overhead(tmp_path)
    assert overhead + REASONABLE_WINDOWS_ROOT_BUDGET <= MAX_PATH, (
        f"skill-backup layout appends {overhead} chars after the project root, leaving only "
        f"{MAX_PATH - overhead} for the root -- less than the {REASONABLE_WINDOWS_ROOT_BUDGET}-char "
        "budget an ordinary deep Windows project root needs (#6295). Keep the backup id short "
        "(installer._BACKUP_ID_HEX) and the member tree from growing."
    )


def test_backup_id_directory_name_stays_short(tmp_path: Path) -> None:
    """Pin the backup id length: a regression back to the full 64-hex id reds here.

    The ``state-v1-`` prefix plus the truncated hex id (and an optional ``-{index}``
    collision suffix) must stay well short of the 64-hex regression that caused #6295.
    """
    replacement = SkillBackupReplacement(
        REPRESENTATIVE_INSTALLED_MEMBER,
        FileState("file", sha256="a" * 64, mode=0o444),
        FileState("file", sha256="b" * 64, mode=0o444),
    )
    prepared = prepare_skill_backup(tmp_path, (replacement,))
    assert prepared.root.name.startswith("state-v1-")
    assert len(prepared.root.name) <= 32, (
        f"backup id directory '{prepared.root.name}' ({len(prepared.root.name)} chars) is too long; the full 64-hex id overran Windows MAX_PATH (#6295)."
    )
