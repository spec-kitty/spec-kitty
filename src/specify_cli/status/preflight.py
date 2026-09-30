"""Preflight helpers for transition gates.

This module provides ownership-policy helpers used by the dirty-state
preflight that backs ``agent tasks move-task`` and related transitions.

Ownership policy for ``snapshot-latest.json`` (per mission
``charter-e2e-827-followups-01KQAJA0`` and contract
``contracts/dossier-snapshot-ownership.md``): **EXCLUDE**.

The dossier snapshot at
``<feature_dir>/.kittify/dossiers/<mission_slug>/snapshot-latest.json`` is a
mutable, derived, ephemeral artifact that is recomputable from the dossier
source. It is excluded from version control via ``.gitignore`` (the common
case) AND filtered from any code path that computes dirty state in a way that
bypasses ``.gitignore`` (belt-and-suspenders, per research R6).

Per Constraint **C-006** in the spec, this module implements **exactly one**
ownership policy (EXCLUDE) — no conditional dual-policy runtime branch.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from kernel.paths import to_posix

# Glob patterns that match the dossier snapshot path. Both shapes are covered
# because the snapshot writer (`save_snapshot()` in
# ``src/specify_cli/dossier/snapshot.py``) is invoked with ``feature_dir``
# pointing either at the project root (``./.kittify/...``) or at a
# kitty-specs feature directory (``kitty-specs/<mission>/.kittify/...``).
_DOSSIER_SNAPSHOT_PATTERNS: tuple[str, ...] = (
    "**/.kittify/dossiers/*/snapshot-latest.json",
    ".kittify/dossiers/*/snapshot-latest.json",
    "kitty-specs/*/.kittify/dossiers/*/snapshot-latest.json",
)


def is_dossier_snapshot(path: str | Path) -> bool:
    """Return True if *path* matches the dossier snapshot ownership glob.

    The path is normalised to POSIX form (forward slashes) before matching so
    Windows paths classify identically. The match is anchored to the right of
    the path (``fnmatch.fnmatch``) so paths nested under arbitrary parent
    directories still classify correctly.

    Args:
        path: Filesystem path (str or :class:`pathlib.Path`) to test.

    Returns:
        True when *path* is a dossier snapshot file that the dirty-state
        preflight must ignore. False otherwise.
    """
    posix = to_posix(path)

    # Strip any leading "./" so patterns anchored at the repo root still match.
    if posix.startswith("./"):
        posix = posix[2:]

    return any(fnmatch.fnmatch(posix, pat) for pat in _DOSSIER_SNAPSHOT_PATTERNS)


__all__ = [
    "is_dossier_snapshot",
]
