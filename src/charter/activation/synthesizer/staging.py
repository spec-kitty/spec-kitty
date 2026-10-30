"""Stage-directory lifecycle management — WP03 (T016).

Owns the creation, population, promotion-fail, and wipe lifecycle of a
staging directory under ``.kittify/charter/.staging/<run_id>/``.

Layout inside a staging directory:
    .kittify/charter/.staging/<run_id>/
        charter-packs/
            directive/
            tactic/
            styleguide/
        charter/
            provenance/

All filesystem writes go through ``PathGuard`` (FR-016).  The staging root
is deliberately placed under the bookkeeping tree (``.kittify/charter/``) so
project charter pack consumers (which scan ``.kittify/charter-packs/``)
never traverse it. The content subtree carries the same directory name as
the live project pack root, so promotion is a 1:1 mapping.

Retention: a refused run's directory is preserved as ``<run_id>.failed/`` for
diagnosis, but only the newest ``DEFAULT_KEEP_FAILED_RUNS`` are kept (#6723).
Before that bound existed a repeatedly-refused project accumulated one directory
per attempt (#4226 counted 15, then 16, on one repository).

Context manager protocol:
    ``with StagingDir.create(repo_root, run_id) as stage:``

    On unhandled exception inside the ``with`` block the context manager calls
    ``commit_to_failed(traceback_text)``.  On success the caller **must**
    explicitly call ``stage.wipe()`` after a successful promote (T018 owns
    this sequencing — the ``with`` block itself does not auto-wipe on success
    to keep the control flow explicit).

See also:
    - data-model.md §E-9 (run-lifecycle state diagram)
    - plan.md §KD-2 (atomicity model)
    - quickstart.md §1 "What just happened under the hood" (8-step sequence)
"""

from __future__ import annotations

import contextlib
import io
import traceback
from pathlib import Path
from types import TracebackType

from ruamel.yaml import YAML

from kernel.clock import now_utc_iso
from kernel.charter_pack_paths import PROJECT_PACK_DIRNAME

from .errors import PathGuardViolation
from .path_guard import PathGuard


# Kind → staging content subdirectory name (mirrors final doctrine layout).
# Singular names match the .gitignore whitelist (directive/, tactic/).
_KIND_SUBDIR: dict[str, str] = {
    "directive": "directive",
    "tactic": "tactic",
    "styleguide": "styleguide",
}

#: Name suffix that marks a preserved failure (``<run_id>.failed``).
_FAILED_SUFFIX = ".failed"

#: How many preserved failure directories survive a refused run (#6723).
#: The latest is the one an operator diagnoses; the two before it exist so a
#: repeated refusal can be compared against its predecessors. One named
#: default feeds both the retention pass and the operator-facing hint.
DEFAULT_KEEP_FAILED_RUNS = 3


# ---------------------------------------------------------------------------
# Failure-directory retention (#6723)
# ---------------------------------------------------------------------------


def _preserved_failure_dirs(
    staging_root: Path,
) -> list[tuple[float, str, Path]]:
    """Return ``(mtime, name, path)`` for every preserved failure directory.

    Only entries whose name ends in :data:`_FAILED_SUFFIX` and that are
    directories are returned: a live ``<run_id>/`` staging directory of a
    running synthesis is never a candidate, whatever its age. Entries that
    cannot be stat'ed are skipped — retention is best-effort and must not fail
    the refusal.
    """
    try:
        entries = list(staging_root.iterdir())
    except OSError:
        return []
    found: list[tuple[float, str, Path]] = []
    for entry in entries:
        if not entry.name.endswith(_FAILED_SUFFIX):
            continue
        try:
            if entry.is_dir():
                found.append((entry.stat().st_mtime, entry.name, entry))
        except OSError:
            continue
    return found


def retention_hint() -> str:
    """Return the operator-facing sentence that names the retention bound.

    One source for the number: the refusal hint and any error message that
    mentions the preserved directory read this instead of restating it.
    """
    return f"Older failed staging directories are pruned after each refusal; the newest {DEFAULT_KEEP_FAILED_RUNS} are kept."


def retain_failed_staging_dirs(
    guard: PathGuard,
    staging_root: Path,
    *,
    keep: int = DEFAULT_KEEP_FAILED_RUNS,
    preserve: str | None = None,
) -> tuple[Path, ...]:
    """Remove all but the newest ``keep`` preserved failure directories.

    Newest-first ordering uses the directory modification time with the name as
    a descending tiebreak, so a restored or fixture tree whose directories share
    an mtime still prunes the same entries every time. ``preserve`` names the
    run whose failure was just written: it is never removed, even if an odd
    mtime or a copied tree would otherwise order it past the bound.

    Every removal goes through ``PathGuard.rmtree`` (the synthesizer's single
    write seam). The pass never raises: an unreadable entry or an unremovable
    directory simply stays, because retention must not mask the synthesis
    failure the caller is already reporting.

    Returns the directories it removed, newest-surplus first.
    """
    preserve_name = f"{preserve}{_FAILED_SUFFIX}" if preserve is not None else None
    candidates = _preserved_failure_dirs(staging_root)
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)

    removed: list[Path] = []
    for _mtime, _name, path in candidates[max(keep, 0) :]:
        if path.name == preserve_name:
            continue
        try:
            guard.rmtree(path, caller="retain_failed_staging_dirs")
        except (OSError, PathGuardViolation):
            # Best-effort: the directory stays and the refusal is still reported.
            continue
        removed.append(path)
    return tuple(removed)


class StagingDir:
    """Represents a single synthesis run's staging directory.

    Create via ``StagingDir.create(repo_root, run_id)`` — do not instantiate
    directly.

    Attributes
    ----------
    root:
        Absolute path to the staging directory
        (``.kittify/charter/.staging/<run_id>``).
    run_id:
        ULID that identifies this staging directory.
    guard:
        ``PathGuard`` instance used for all filesystem writes.
    """

    def __init__(self, root: Path, run_id: str, guard: PathGuard) -> None:
        self.root = root
        self.run_id = run_id
        self.guard = guard

    # -----------------------------------------------------------------------
    # Factory
    # -----------------------------------------------------------------------

    @classmethod
    def create(cls, repo_root: Path, run_id: str) -> StagingDir:
        """Create a new staging directory and all required subdirectories.

        Directory layout created:
            .kittify/charter/.staging/<run_id>/doctrine/directive/
            .kittify/charter/.staging/<run_id>/doctrine/tactic/
            .kittify/charter/.staging/<run_id>/doctrine/styleguide/
            .kittify/charter/.staging/<run_id>/charter/provenance/

        Parameters
        ----------
        repo_root:
            Absolute path to the repository root.
        run_id:
            ULID for this synthesis run.

        Returns
        -------
        StagingDir
            Ready-to-use staging directory instance.
        """
        guard = PathGuard(repo_root)
        staging_root = repo_root / ".kittify" / "charter" / ".staging" / run_id

        # Doctrine content subtree
        for kind_subdir in _KIND_SUBDIR.values():
            guard.mkdir(
                staging_root / PROJECT_PACK_DIRNAME / kind_subdir,
                caller="StagingDir.create",
            )

        # Charter bookkeeping subtree (provenance sidecars)
        guard.mkdir(
            staging_root / "charter" / "provenance",
            caller="StagingDir.create",
        )

        return cls(root=staging_root, run_id=run_id, guard=guard)

    # -----------------------------------------------------------------------
    # Path helpers
    # -----------------------------------------------------------------------

    def path_for_content(self, kind: str, filename: str) -> Path:
        """Return the staged location for an artifact body file.

        Parameters
        ----------
        kind:
            ``"directive"``, ``"tactic"``, or ``"styleguide"``.
        filename:
            Target filename matching the repository glob for this kind, e.g.
            ``001-my-directive.directive.yaml`` or ``my-tactic.tactic.yaml``.

        Returns
        -------
        Path
            Absolute path under ``staging/charter-packs/<kind-subdir>/<filename>``.
        """
        subdir = _KIND_SUBDIR[kind]
        return self.root / PROJECT_PACK_DIRNAME / subdir / filename

    def path_for_provenance(self, kind: str, slug: str) -> Path:
        """Return the staged location for a provenance sidecar.

        Parameters
        ----------
        kind:
            ``"directive"``, ``"tactic"``, or ``"styleguide"``.
        slug:
            Artifact slug (kebab-case).

        Returns
        -------
        Path
            Absolute path under ``staging/charter/provenance/<kind>-<slug>.yaml``.
        """
        return self.root / "charter" / "provenance" / f"{kind}-{slug}.yaml"

    # -----------------------------------------------------------------------
    # Lifecycle: failure path
    # -----------------------------------------------------------------------

    def commit_to_failed(self, cause: str) -> None:
        """Preserve the staging dir at ``<run_id>.failed/`` with a cause record.

        Renames ``.staging/<run_id>/`` → ``.staging/<run_id>.failed/`` and
        writes ``cause.yaml`` in the failed dir with ``{reason, traceback,
        timestamp}``.  This preserves diagnostic state for operator inspection
        (R-7, quickstart §8).

        If the rename fails (e.g. the failed dir already exists), the cause
        is logged to stderr but does not raise — we must not mask the
        original error.

        Parameters
        ----------
        cause:
            Human-readable failure reason (e.g. exception message or short
            description).  The current traceback is appended automatically.
        """
        failed_dir = self.root.parent / f"{self.run_id}.failed"
        tb_text = traceback.format_exc()
        try:
            # PathGuard.rename is atomic on POSIX (same filesystem)
            self.guard.rename(self.root, failed_dir, caller="StagingDir.commit_to_failed")
        except Exception:
            # Cannot rename — dir may already have been renamed or gone.
            # Fall back to writing cause inside the original root if it exists.
            failed_dir = self.root if self.root.exists() else None  # type: ignore[assignment]

        if failed_dir is not None and failed_dir.exists():
            cause_path = failed_dir / "cause.yaml"
            yaml = YAML()
            buf = io.BytesIO()
            yaml.dump(
                {
                    "reason": cause,
                    "traceback": tb_text,
                    "timestamp": now_utc_iso(),
                },
                buf,
            )
            with contextlib.suppress(Exception):
                self.guard.write_bytes(
                    cause_path,
                    buf.getvalue(),
                    caller="StagingDir.commit_to_failed[cause]",
                )

        # #6723: bound the preserved failures. The run that just failed is
        # preserved above and excluded here, so what the command reports still
        # exists; only older surplus directories are removed.
        retain_failed_staging_dirs(
            self.guard,
            self.root.parent,
            keep=DEFAULT_KEEP_FAILED_RUNS,
            preserve=self.run_id,
        )

    # -----------------------------------------------------------------------
    # Lifecycle: success path
    # -----------------------------------------------------------------------

    def wipe(self) -> None:
        """Remove the staging directory after a successful promote.

        Uses ``PathGuard.rmtree`` to stay within the allowed write surface.
        Should only be called after ALL promote ``os.replace`` calls and the
        manifest write have completed successfully (T018 controls this
        sequencing).
        """
        self.guard.rmtree(self.root, caller="StagingDir.wipe")

    # -----------------------------------------------------------------------
    # Context manager — routes unhandled exceptions to commit_to_failed
    # -----------------------------------------------------------------------

    def __enter__(self) -> StagingDir:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        if exc_type is not None:
            # Unhandled exception — preserve staging as .failed/
            cause = f"{exc_type.__name__}: {exc_val}"
            self.commit_to_failed(cause)
            # Re-raise the original exception (return False suppresses nothing)
            return False
        # Success path — caller must call wipe() explicitly after promote.
        return None


__all__ = [
    "DEFAULT_KEEP_FAILED_RUNS",
    "StagingDir",
    "retain_failed_staging_dirs",
    "retention_hint",
]
