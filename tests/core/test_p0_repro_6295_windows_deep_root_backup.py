"""OPEN P0 #6295 -- red-first reproduction (Windows-only; p0_repro lane).

``spec-kitty upgrade`` fails on Windows with a ``MAX_PATH`` error (``WinError 3``/
``206`` -- "The filename or extension is too long") when it has to retain a user
file before overwriting it, on any project rooted more than ~54 characters deep.
Clearing the read-only bit does not help -- this is orthogonal to #6228; the backup
path is simply too long for the OS to create.

Root cause (``src/specify_cli/skills/installer.py``): the migration-backup layout
mirrors the full managed skill tree verbatim under a long, fixed prefix::

    <project_root>/.kittify/.migration-backup/agent-skills/state-v1-<sha256>/<dest>

where ``<sha256>`` is a *full* 64-hex SHA-256 (``prepare_skill_backup`` ->
``_backup_parent``) and ``<dest>`` is the ENTIRE installed skill path mirrored
byte-for-byte (``_archive_existing_path``). That fixed overhead is ~206 characters
appended after the project root, so with the Windows default ``LongPathsEnabled=0``
any moderately deep project root pushes the backup member past the 260-character
``MAX_PATH`` ceiling and ``create_skill_backup`` / the verbatim copy raises ``OSError``.

This is **Windows-only** as an I/O failure: POSIX has no 260-char path ceiling, so the
backup write succeeds on Linux. It is therefore gated to ``win32`` and runs on the
nightly ``windows-p0-repro`` lane -- honestly red until this bug is fixed (see
``.github/workflows/ci-nightly.yml``). On the Linux ``p0-repro`` lane it is
collected-but-skipped (reported as "no verdict"), which is honest: Linux cannot
confirm or clear this bug. The cross-platform structural reproduction of the same
defect (pure path arithmetic, reds on Linux too) is
``tests/specify_cli/skills/test_p0_repro_6295_backup_path_maxpath.py``.

Caveat: if a Windows runner has ``LongPathsEnabled=1`` (and the long-path-aware Python
manifest in effect), the OS accepts >260-char paths and this I/O repro passes even
unfixed -- the p0_repro summary then reports it as passing. The structural companion
above is the authoritative gate; it does not depend on the runner's registry state.

Ideal, asserted here and RED on Windows until #6295 is fixed: the migration-backup
archive step of ``spec-kitty upgrade`` must succeed (retain the user file and return a
readable backup member) for an ordinary deep-rooted project. The fix PR removes the
``p0_repro`` marker. See ADR 2026-07-17-1 and
docs/development/reference/red-main-and-release-readiness.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from specify_cli.skills.installer import _archive_existing_path

pytestmark = [pytest.mark.unit]

#: A representative managed skill reference file, installed under the project and then
#: retained verbatim by the backup. This is a real currently-shipped charter skill (the
#: longest-named one); any managed skill reference member is mirrored the same way.
INSTALLED_MEMBER = Path(".agents/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md")


@pytest.mark.p0_repro(issue=6295)
@pytest.mark.skipif(
    sys.platform != "win32",
    reason="#6295 is a Windows MAX_PATH failure: POSIX has no 260-char path ceiling, so the backup write succeeds on non-win32.",
)
def test_upgrade_backup_succeeds_for_a_deep_rooted_project(tmp_path: Path) -> None:
    # An ordinary deep-rooted project: pytest's Windows tmp_path already sits well past
    # ~54 characters (a realistic user location), which is all the defect needs.
    project = tmp_path / "proj"
    dest = project / INSTALLED_MEMBER
    dest.parent.mkdir(parents=True)
    dest.write_text("user-authored skill reference content\n", encoding="utf-8")

    # Ideal: the migration-backup archive step retains the user file under a backup path
    # that fits MAX_PATH, exactly as `spec-kitty upgrade` must be able to on Windows.
    # Today the full-SHA-256 + full-tree-mirror layout makes the backup member exceed 260
    # characters, so create_skill_backup / the verbatim copy raises OSError (WinError 3/206).
    backup_root = _archive_existing_path(dest, project, None)

    backup_member = backup_root / dest.relative_to(project)
    assert backup_member.is_file(), "the user file must be retained under the backup root"
    assert backup_member.read_text(encoding="utf-8") == "user-authored skill reference content\n"
    assert not dest.exists(), "the archived source is moved into the backup, not left in place"
