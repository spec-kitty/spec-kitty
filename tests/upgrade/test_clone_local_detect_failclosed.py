"""The reselection gate probes clone-local detect() fail-closed (#6350 review follow-up).

``BaseMigration.reselect_when_recorded`` is reached by both the runner skip gate and
the selection arm (``registry._clone_local_selected_below_window``); neither wraps its
``detect()`` call in ``registry._detect_fail_closed``. A clone-local migration's
``detect()`` probes real on-disk state (a merge-driver migration reads ``.gitattributes``
via ``read_text()``); a pathological checkout -- an unreadable or directory
``.gitattributes`` -- raises ``OSError``. Before this fix that propagated out of the gate
and crashed the whole upgrade before any migration ran. The gate now fails closed: a probe
error reselects the migration (so the runner records a fail-closed failure) instead of
aborting the run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.gitignore_manager import GitignorePathError
from specify_cli.upgrade.migrations.base import (
    BaseMigration,
    MigrationResult,
    MigrationStateUnreadableError,
)


def _clone_local_migration(*, detect_returns: bool | None = None, detect_raises: Exception | None = None) -> BaseMigration:
    """A minimal clone-local migration whose detect() returns or raises as directed."""

    class _Probe(BaseMigration):
        migration_id = "9.9.9_failclosed_probe"
        description = "clone-local detect() probe for the reselection gate"
        target_version = "9.9.9"
        clone_local_effect = True

        def detect(self, project_path: Path) -> bool:  # noqa: ARG002 -- directed by the factory
            if detect_raises is not None:
                raise detect_raises
            assert detect_returns is not None
            return detect_returns

        def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002 -- not exercised here
            return True, ""

        def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002
            raise AssertionError("apply() must not run inside the reselection gate")

    return _Probe()


@pytest.mark.parametrize(
    "exc",
    [
        OSError("permission denied reading .gitattributes"),
        PermissionError(".gitattributes unreadable"),
        IsADirectoryError(".gitattributes is a directory"),
        MigrationStateUnreadableError("state unreadable"),
        GitignorePathError(".gitignore is a symlink"),
    ],
    ids=["oserror", "permission", "isadir", "state-unreadable", "gitignore-symlink"],
)
def test_detect_probe_error_fails_closed_to_reselect(tmp_path: Path, exc: Exception) -> None:
    """A clone-local detect() that raises makes reselect fail closed (True), never propagate."""
    migration = _clone_local_migration(detect_raises=exc)
    # Must not raise, and must reselect so the runner records a fail-closed failure.
    assert migration.reselect_when_recorded(tmp_path) is True


def test_detect_absent_reselects(tmp_path: Path) -> None:
    """Effect absent (detect() True) still reselects -- the ordinary pulled-clone case."""
    migration = _clone_local_migration(detect_returns=True)
    assert migration.reselect_when_recorded(tmp_path) is True


def test_detect_present_settles(tmp_path: Path) -> None:
    """Effect present (detect() False) settles -- no reselection, no over-run."""
    migration = _clone_local_migration(detect_returns=False)
    assert migration.reselect_when_recorded(tmp_path) is False
