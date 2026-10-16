"""Windows regression guard for #6295 -- migration backup on a deep project root.

`spec-kitty upgrade` retains a user file before overwriting it by copying it under
``.kittify/.migration-backup/agent-skills/state-v1-<id>/<installed-path>``. When
``<id>`` was the full 64-hex SHA-256 the backup path overran the Windows MAX_PATH
(260) ceiling on any moderately deep project root, so ``create_skill_backup`` / the
verbatim copy raised ``OSError`` (``WinError 3``/``206``) and the upgrade failed
(orthogonal to the read-only #6228). The fix truncates the backup id
(``installer._BACKUP_ID_HEX``).

This is a Windows-only I/O guard (``windows_ci``): it drives the real
``_archive_existing_path`` backup step for a deep-rooted project and asserts it
succeeds. POSIX has no 260-char ceiling, so it is gated to ``win32``; the
cross-platform budget guard is
``tests/specify_cli/skills/test_backup_path_budget_6295.py``.

Caveat: a runner with ``LongPathsEnabled=1`` accepts >260-char paths, so this I/O
check cannot distinguish fixed from unfixed there -- the budget guard above is the
authoritative, registry-independent gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from specify_cli.skills.installer import _archive_existing_path

#: A representative managed skill reference file, installed under the project and then
#: retained verbatim by the backup. This is a real currently-shipped charter skill (the
#: longest-named one); any managed skill reference member is mirrored the same way.
INSTALLED_MEMBER = Path(".agents/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md")


@pytest.mark.windows_ci
def test_upgrade_backup_succeeds_for_a_deep_rooted_project(tmp_path: Path) -> None:
    # The ``windows_ci`` marker auto-skips off-win32 (tests/conftest.py); on Windows the
    # defect reproduces because POSIX has no 260-char path ceiling.
    assert sys.platform == "win32"
    # An ordinary deep-rooted project: pytest's Windows tmp_path already sits well past
    # ~54 characters (a realistic user location), which is all the defect needed.
    project = tmp_path / "proj"
    dest = project / INSTALLED_MEMBER
    dest.parent.mkdir(parents=True)
    dest.write_text("user-authored skill reference content\n", encoding="utf-8")

    # The migration-backup archive step must retain the user file under a backup path
    # that fits MAX_PATH, exactly as `spec-kitty upgrade` does on Windows. Before the fix
    # the full-SHA-256 id made the backup member exceed 260 chars and this raised OSError.
    backup_root = _archive_existing_path(dest, project, None)

    backup_member = backup_root / dest.relative_to(project)
    assert backup_member.is_file(), "the user file must be retained under the backup root"
    assert backup_member.read_text(encoding="utf-8") == "user-authored skill reference content\n"
    assert not dest.exists(), "the archived source is moved into the backup, not left in place"
