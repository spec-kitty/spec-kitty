"""The asset-preservation decision surface.

``guard_destructive_removal`` is the single chokepoint every mutating-flow
cleanup routes its destructive removals through (charter L463-479). It PERFORMS
the removal itself when ownership is proven, and preserves-or-archives (never
deletes) when it is not — so a routed site carries no raw ``rmtree``/``unlink``
literal and the WP09 census is non-vacuous by construction (contract C1
invariant 0; mirrors ``git/destructive_guard.py::guarded_worktree_remove``).

Outcomes for one candidate ``path``:

* **owned** (the prover returns a proof) → the guard removes it (``rmtree`` when
  ``is_tree``, else ``unlink``/``rmdir``); the caller then prunes any manifest
  entry.
* **unprovable, parent survives** (``backup_parent is None``) → preserve in
  place; nothing is removed.
* **unprovable, parent being removed** (``backup_parent`` given) → archive the
  content verbatim into a timestamped backup, then remove the original, so the
  user's bytes survive and the site stays literal-free.

Every outcome exits success; preservation is signalled by the returned verdict's
diagnostic (a warning the caller surfaces), never by a non-zero exit (FR-008).
"""

from __future__ import annotations

import shutil
import stat
import sys
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specify_cli.asset_preservation.backup import archive_into
from specify_cli.asset_preservation.provers import OwnershipProver
from specify_cli.tool_surface.operations import OwnershipProof

__all__ = [
    "OverwriteVerdict",
    "OwnershipVerdict",
    "guard_destructive_overwrite",
    "guard_destructive_removal",
]


@dataclass(frozen=True)
class OverwriteVerdict:
    """The guard's decision for one candidate OVERWRITE (charter L463-479).

    ``proceed`` is ``True`` only when the write may go ahead — either because
    the destination is absent and the replacement is substantive, the
    destination is proven package-owned, or the caller is authorized to
    replace unproven-owned bytes. ``backup_path`` is set only when the guard
    archived existing user bytes before an authorized overwrite.
    """

    proceed: bool
    reason: str
    diagnostic: str
    backup_path: Path | None


@dataclass(frozen=True)
class OwnershipVerdict:
    """The guard's decision for one candidate path.

    ``owned`` is ``True`` only when a concrete :class:`OwnershipProof` was
    produced (and the guard removed the path). On preservation ``owned`` is
    ``False`` and ``preserved_path`` names where the content now lives (in place,
    or the archived copy); ``backup_path`` is set only when archived.
    """

    owned: bool
    proof: OwnershipProof | None
    preserved_path: Path | None
    backup_path: Path | None
    reason: str
    diagnostic: str


def _display_rel(path: Path, project_path: Path) -> str:
    try:
        return path.relative_to(project_path).as_posix()
    except ValueError:
        return path.name


def _make_writable(path: Path) -> None:
    """Best-effort: add the owner-write bit to *path* so a retried removal can
    proceed. Never raises — a failed chmod just means the retry below fails
    with its own, more specific OSError."""
    with suppress(OSError):
        path.chmod(path.stat().st_mode | stat.S_IWRITE)


def _retry_writable(path: Path, operation: Callable[[], None]) -> None:
    """Run *operation* once; on PermissionError/OSError, make *path* AND its
    parent writable (removal is governed by the parent directory's write bit
    on POSIX, and by the path's own read-only attribute on Windows — chmod
    both so either cause is cleared) and retry exactly once."""
    try:
        operation()
    except OSError:
        _make_writable(path)
        _make_writable(path.parent)
        operation()


def _rmtree_retry_handler(function: Callable[..., Any], name: str, exc_info: Any) -> None:  # noqa: ANN401 - matches shutil's onerror/onexc callback contract
    """``shutil.rmtree`` error handler: make the failing member (and its
    parent) writable and retry the failing operation once."""
    del exc_info  # unused: the cause doesn't change the recovery action
    failing = Path(name)
    _make_writable(failing)
    _make_writable(failing.parent)
    function(name)


def _rmtree_with_retry(path: Path) -> None:
    # Python 3.12+ deprecates ``onerror`` (DeprecationWarning) in favor of
    # ``onexc``, whose callback receives the exception itself rather than a
    # ``sys.exc_info()`` triple; the 3.11 stub doesn't expose ``onexc`` at
    # all, so the call is branched on the running interpreter.
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_rmtree_retry_handler)
    else:
        shutil.rmtree(path, onerror=_rmtree_retry_handler)


def _remove(path: Path, *, is_tree: bool) -> None:
    """The guard's own removal — the ONLY raw destructive literals in the routed
    flow (this module is not in the WP09-censused mutating-flow module set).

    Retries once, chmod'ing the target writable, on a read-only-attributed
    package-owned file or directory (a proven-owned path must still be
    removable even when it was installed read-only)."""
    if path.is_symlink() or path.is_file():
        _retry_writable(path, path.unlink)
    elif path.is_dir():
        if is_tree:
            _rmtree_with_retry(path)
        else:
            _retry_writable(path, path.rmdir)


def guard_destructive_removal(
    path: Path,
    project_path: Path,
    *,
    prover: OwnershipProver,
    is_tree: bool = False,
    backup_parent: Path | None = None,
    dry_run: bool = False,
) -> OwnershipVerdict:
    """Prove-or-preserve/archive one path; the guard performs any removal itself."""
    rel = _display_rel(path, project_path)

    if not path.exists() and not path.is_symlink():
        return OwnershipVerdict(
            owned=False,
            proof=None,
            preserved_path=None,
            backup_path=None,
            reason="absent",
            diagnostic=f"Skipped {rel}; path is absent",
        )

    proof = prover.prove(path, project_path)
    if proof is not None:
        if not dry_run:
            _remove(path, is_tree=is_tree)
        # Mirror the preserve branch's dry-run honesty: report what a real run
        # WOULD do, not a removal that a forecast did not perform.
        verb = "Would remove" if dry_run else "Removed"
        return OwnershipVerdict(
            owned=True,
            proof=proof,
            preserved_path=None,
            backup_path=None,
            reason=f"package-owned ({proof.kind})",
            diagnostic=f"{verb} package-owned {rel} (proof: {proof.kind})",
        )

    reason = "not package-owned"
    if backup_parent is None:
        return OwnershipVerdict(
            owned=False,
            proof=None,
            preserved_path=path,
            backup_path=None,
            reason=reason,
            diagnostic=f"Preserved {rel}; {reason} (name is not ownership proof) — left in place",
        )

    if dry_run:
        return OwnershipVerdict(
            owned=False,
            proof=None,
            preserved_path=path,
            backup_path=None,
            reason=reason,
            diagnostic=f"Would preserve {rel}; {reason} — would archive before parent removal",
        )

    archived = archive_into(path, project_path, backup_parent)
    _remove(path, is_tree=is_tree)
    return OwnershipVerdict(
        owned=False,
        proof=None,
        preserved_path=archived,
        backup_path=archived,
        reason=reason,
        diagnostic=(f"Preserved {rel}; {reason} — archived to {_display_rel(archived, project_path)} before parent removal"),
    )


def _overwrite_absent(rel: str, *, replacement_substantive: bool) -> OverwriteVerdict:
    if not replacement_substantive:
        return OverwriteVerdict(
            proceed=False,
            reason="absent-empty-replacement",
            diagnostic=f"Refused to fabricate an empty {rel}; destination is absent and replacement is not substantive",
            backup_path=None,
        )
    return OverwriteVerdict(
        proceed=True,
        reason="absent",
        diagnostic=f"Proceeding; {rel} is absent",
        backup_path=None,
    )


def _overwrite_existing(
    dest: Path,
    project_path: Path,
    rel: str,
    *,
    replacement_substantive: bool,
    authorized: bool,
    prover: OwnershipProver | None,
    backup_parent: Path | None,
) -> OverwriteVerdict:
    proof = prover.prove(dest, project_path) if prover is not None else None
    if proof is not None:
        return OverwriteVerdict(
            proceed=True,
            reason=f"package-owned ({proof.kind})",
            diagnostic=f"Proceeding over package-owned {rel} (proof: {proof.kind})",
            backup_path=None,
        )

    if not replacement_substantive:
        return OverwriteVerdict(
            proceed=False,
            reason="would-truncate-to-empty",
            diagnostic=f"Refused to truncate {rel} to empty; existing bytes are not proven package-owned",
            backup_path=None,
        )

    if not authorized:
        return OverwriteVerdict(
            proceed=False,
            reason="unauthorized",
            diagnostic=f"Refused to overwrite {rel}; not proven package-owned and not authorized",
            backup_path=None,
        )

    backup_path: Path | None = None
    if backup_parent is not None:
        backup_path = archive_into(dest, project_path, backup_parent)
    diagnostic = f"Proceeding to overwrite {rel}; authorized"
    if backup_path is not None:
        diagnostic = f"Proceeding to overwrite {rel}; archived to {_display_rel(backup_path, project_path)} first"
    return OverwriteVerdict(
        proceed=True,
        reason="authorized-overwrite",
        diagnostic=diagnostic,
        backup_path=backup_path,
    )


def guard_destructive_overwrite(
    dest: Path,
    project_path: Path,
    *,
    replacement_substantive: bool,
    authorized: bool,
    prover: OwnershipProver | None = None,
    backup_parent: Path | None = None,
) -> OverwriteVerdict:
    """Prove-or-refuse one candidate OVERWRITE of ``dest`` (charter L463-479).

    Pure decision surface (mirrors :func:`guard_destructive_removal`): the only
    I/O it performs is the optional pre-overwrite archive when *authorizing* a
    replacement of unproven-owned bytes and ``backup_parent`` is given. The
    caller decides how to surface a ``proceed=False`` refusal and performs the
    write itself on ``proceed=True`` — this primitive never writes the
    replacement content.

    Truth table (``dest`` existence × ``replacement_substantive`` ×
    ``authorized`` — a proven package-owned ``dest`` always proceeds):

    * absent, non-substantive replacement → refuse (never fabricate empty).
    * absent, substantive replacement → proceed.
    * exists (unproven), non-substantive replacement → refuse, any
      ``authorized`` (never truncate to empty, even under ``--force``).
    * exists (unproven), substantive replacement, unauthorized → refuse.
    * exists (unproven), substantive replacement, authorized → proceed
      (archives first when ``backup_parent`` is given).
    * exists, proven package-owned (via ``prover``) → proceed regardless of
      ``replacement_substantive``/``authorized``.
    """
    rel = _display_rel(dest, project_path)
    exists = dest.exists() or dest.is_symlink()

    if not exists:
        return _overwrite_absent(rel, replacement_substantive=replacement_substantive)

    return _overwrite_existing(
        dest,
        project_path,
        rel,
        replacement_substantive=replacement_substantive,
        authorized=authorized,
        prover=prover,
        backup_parent=backup_parent,
    )
