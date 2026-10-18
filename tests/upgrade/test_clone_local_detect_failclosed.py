"""The reselection gate never probes a clone-local migration's detect() (ADR 2026-10-17-1).

History: #6350 (the #6233 clone-local reselection) routed the skip decision for a
``clone_local_effect`` migration through ``BaseMigration.reselect_when_recorded`` ->
``detect()``, and its follow-up (6a9aba609a) made that probe fail closed so a
pathological checkout (an unreadable or directory ``.gitattributes`` whose
``detect()`` raises ``OSError``) could not crash the whole upgrade.

The explicit two-partition migration ledger SUPERSEDES that mechanism: a clone-local
migration's applied authority IS its per-clone (gitignored) ledger, so a pulled clone
with an EMPTY per-clone ledger re-selects it by ledger-diff and the runner's ``detect()``
idempotency guard no-ops when the effect is already present. ``reselect_when_recorded``
is now ``runs_first and structural_detect`` only -- a clone-local migration is NOT
``runs_first``, so the hook short-circuits to ``False`` WITHOUT ever calling
``structural_detect`` or ``detect()``.

That makes #6350's fail-closed OUTCOME hold by construction: the reselection gate cannot
crash on a clone-local ``detect()`` that raises, because it never invokes it. These tests
pin that property (a regression that re-wired clone-local reselection back through
``detect()`` would reintroduce the #6350 crash). The clone-local re-apply OUTCOME itself
-- empty per-clone ledger => re-selected => effect re-applied -- is proven by
``tests/upgrade/test_clone_local_selection.py``.
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
def test_reselection_gate_never_invokes_clone_local_detect(tmp_path: Path, exc: Exception) -> None:
    """A clone-local detect() that raises is NEVER called by the reselection gate.

    Under the ledger model clone-local reselection is owned by the per-clone ledger
    partition, not this hook, so ``reselect_when_recorded`` returns ``False`` without
    touching ``detect()`` -- a raising ``detect()`` can never propagate out of the gate
    (the crash-proof-by-construction guarantee that supersedes #6350's fail-closed probe).
    """
    migration = _clone_local_migration(detect_raises=exc)
    assert migration.reselect_when_recorded(tmp_path) is False


def test_detect_absent_does_not_reselect_via_the_hook(tmp_path: Path) -> None:
    """Effect absent (detect() True) does NOT reselect via the hook.

    The pulled-clone re-apply still happens -- but it is driven by the EMPTY per-clone
    ledger partition (ledger-diff selection), proven in test_clone_local_selection.py, not
    by ``reselect_when_recorded``, which is ``runs_first``-only now.
    """
    migration = _clone_local_migration(detect_returns=True)
    assert migration.reselect_when_recorded(tmp_path) is False


def test_detect_present_does_not_reselect(tmp_path: Path) -> None:
    """Effect present (detect() False) also does not reselect via the hook."""
    migration = _clone_local_migration(detect_returns=False)
    assert migration.reselect_when_recorded(tmp_path) is False
