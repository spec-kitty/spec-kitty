"""OPEN P0 #6295 -- red-first reproduction (cross-platform; p0_repro lane).

``spec-kitty upgrade`` fails on Windows with a ``MAX_PATH`` error (``WinError 3``/
``206`` -- "The filename or extension is too long") when it has to retain a user
file before overwriting it, on any project rooted more than ~54 characters deep.
Clearing the read-only bit does not help -- this is orthogonal to #6228; the path
is simply too long to create.

Root cause (``src/specify_cli/skills/installer.py``): the migration-backup layout
mirrors the full managed skill tree verbatim under a long, fixed prefix::

    <project_root>/.kittify/.migration-backup/agent-skills/state-v1-<sha256>/<dest>

where ``<sha256>`` is a *full* 64-hex SHA-256 (``prepare_skill_backup``,
``_backup_parent``) and ``<dest>`` is the ENTIRE installed skill path mirrored
byte-for-byte (``_archive_existing_path`` copies ``dest.relative_to(project_path)``
under the backup root). For a representative managed skill reference file that fixed
overhead is ~206 characters appended after the project root, so on Windows with the
default ``LongPathsEnabled=0`` any project root longer than ~54 characters pushes the
backup member past the 260-character ``MAX_PATH`` ceiling.

This reproduction is **pure path arithmetic over the real production layout**
(``_backup_parent`` + a real 64-hex SHA-256 digest + a real shipped managed skill
reference member), so it reds on Linux too -- more valuable than a Windows-only I/O
test, because it gates the fix wherever CI runs. The companion Windows-only I/O repro
is ``tests/core/test_p0_repro_6295_windows_deep_root_backup.py``.

Ideal, asserted here and RED until #6295 is fixed: the backup layout's fixed overhead
must be small enough that an ordinary deep Windows project root still fits within
``MAX_PATH``. The fix PR removes the ``p0_repro`` marker. See ADR 2026-07-17-1 and
docs/development/reference/red-main-and-release-readiness.md.
"""

from __future__ import annotations

import hashlib
from pathlib import PurePosixPath

import pytest

from specify_cli.skills.installer import _backup_parent

pytestmark = [pytest.mark.unit]

#: Classic Win32 ``MAX_PATH`` ceiling (``LongPathsEnabled=0``, no ``\\?\`` prefix).
MAX_PATH = 260

#: A representative managed skill reference file, mirrored verbatim under the backup
#: root. This is a real currently-shipped charter skill (the longest-named one); the
#: invariant under test is the length budget, not this exact file -- any managed skill
#: reference member is mirrored the same way.
REPRESENTATIVE_INSTALLED_MEMBER = PurePosixPath(".agents/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md")

#: A reasonable budget for an ordinary Windows project root, e.g.
#: ``C:\Users\firstname.lastname\source\repos\acme-platform\spec-kitty`` (~65 chars).
#: The backup layout must leave at least this much room for the project root under
#: ``MAX_PATH``.
REASONABLE_WINDOWS_ROOT_BUDGET = 72


def _backup_member_overhead() -> int:
    """Characters the real backup layout appends after the project root.

    Built from the production functions, not a reimplementation: the managed
    ``_backup_parent`` prefix, the ``state-v1-`` segment with a real 64-hex
    SHA-256 digest, and a representative installed skill member mirrored verbatim.
    Root-independent, because the backup member is always the project root plus
    this fixed suffix.
    """
    measurement_root = PurePosixPath("/r")
    parent = _backup_parent(measurement_root)  # type: ignore[arg-type]
    # A real SHA-256 hexdigest: the backup identity is always a *full* 64-hex digest.
    digest = hashlib.sha256(b"spec-kitty-6295-representative-backup-manifest").hexdigest()  # noqa: TID251 -- length-of-backup-identity probe, not charter hashing
    assert len(digest) == 64, "a SHA-256 hexdigest is 64 hex characters"
    backup_member = parent / f"state-v1-{digest}" / REPRESENTATIVE_INSTALLED_MEMBER
    return len(backup_member.as_posix()) - len(measurement_root.as_posix())


@pytest.mark.p0_repro(issue=6295)
def test_backup_overhead_leaves_room_for_a_reasonable_windows_root() -> None:
    """The fixed backup overhead must not consume the whole ``MAX_PATH`` budget.

    Today the overhead is ~206 characters, leaving only ~54 for the entire project
    root -- far too little for an ordinary Windows location. The ideal: the layout
    leaves at least ``REASONABLE_WINDOWS_ROOT_BUDGET`` characters for the root.
    """
    overhead = _backup_member_overhead()
    assert overhead + REASONABLE_WINDOWS_ROOT_BUDGET <= MAX_PATH, (
        f"skill-backup layout appends {overhead} chars after the project root, leaving only "
        f"{MAX_PATH - overhead} for the root -- less than the {REASONABLE_WINDOWS_ROOT_BUDGET}-char "
        "budget an ordinary deep Windows project root needs (#6295). Shorten the backup "
        "layout (e.g. a truncated backup id and/or not mirroring the full managed skill tree)."
    )


@pytest.mark.p0_repro(issue=6295)
def test_backup_path_fits_max_path_for_an_ordinary_deep_windows_root() -> None:
    """The computed backup member path for a representative deep root must fit ``MAX_PATH``.

    ``C:\\Users\\firstname.lastname\\source\\repos\\acme-platform\\spec-kitty`` is an
    ordinary -- not pathological -- Windows project root. Today the backup member for a
    managed skill reference under it exceeds 260 characters, so ``spec-kitty upgrade``
    cannot create the backup and fails.
    """
    # Measured as a character count (separators are one char on every platform); this
    # root is 65 characters, a realistic corporate Windows layout.
    representative_root_len = len("C:/Users/firstname.lastname/source/repos/acme-platform/spec-kitty")
    full_backup_path_len = representative_root_len + _backup_member_overhead()
    assert full_backup_path_len <= MAX_PATH, (
        f"backup member path is {full_backup_path_len} chars for a {representative_root_len}-char "
        f"Windows project root -- past the {MAX_PATH}-char MAX_PATH ceiling, so `spec-kitty upgrade` "
        "cannot create the migration backup on Windows (#6295)."
    )
