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

from .path_guard import PathGuard


# Kind → staging content subdirectory name (mirrors final doctrine layout).
# Singular names match the .gitignore whitelist (directive/, tactic/).
_KIND_SUBDIR: dict[str, str] = {
    "directive": "directive",
    "tactic": "tactic",
    "styleguide": "styleguide",
}


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


__all__ = ["StagingDir"]
