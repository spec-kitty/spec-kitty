"""Migration: repair historical sweep-created mission overrides (#6548).

``2.0.6_consistency_sweep`` of an older build classified every file under
``.kittify/missions/<mission>/`` as CUSTOMIZED and moved it into
``.kittify/overrides/missions/<mission>/`` — including files the package ships,
and files byte-identical to the shipped copy. The counterpart lookup missed the
shipped file because it joined a second ``missions/`` segment onto an asset root
that already ends in ``missions/``. ``runtime/migrate.py`` now maps a project
mission path through :func:`specify_cli.runtime.migrate.shipped_mission_counterpart`,
so a *new* classification run compares against the right shipped file.

Two things that leaves un-repaired, which is what this migration exists for:

* ``2.0.7_fix_stale_overrides`` — the step whose job is exactly this cleanup —
  applies the same two wrong joins to a path relative to ``.kittify/overrides/``,
  so it finds no counterpart even for a byte-identical override and reports
  "not needed". It is a shipped migration body: frozen (DIRECTIVE_044), never
  edited in place, and already recorded as settled on the projects that ran it.
* ``4.0.0rc8_retire_stale_mission_template_forks`` repairs 15 named
  documentation/research template fork copies. An override a sweep created for
  ``software-dev`` — or any other mission file the package ships — is not one
  of those names.

So this is a new, separately-ledgered step that reads
``.kittify/overrides/missions/**`` and classifies each file against the shipped
file at the same mission-relative path:

* **identical** — bytes proven equal to the shipped counterpart → REMOVED
  through ``guard_destructive_removal`` with a canonical-bytes prover. The
  override tier exists for customisations; once the copy is gone the canonical
  tier resolves again (the global runtime or the packs copy).
* **differs** — a counterpart exists but the bytes differ → PRESERVED verbatim
  and named in a warning. Under #4961 differing bytes cannot be proven
  package-owned, so deleting them is ruled out; ``2.0.7`` could not have removed
  them either, and the operator decides.
* **no counterpart** — a custom mission, or a file the package does not ship at
  that path → never read, never named, never touched.

The comparison is exact bytes (the same question ``classify_asset`` asks with
``filecmp`` two modules away); a CRLF working-tree copy therefore reads as
``differs`` and is preserved and named, not deleted.

**No directory is created or removed**, and a symlinked ``.kittify``,
``overrides`` or ``missions`` component — or a symlinked override — is refused
with a warning, so nothing outside the project is read or removed.
``apply()`` is idempotent: a second run finds no candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from specify_cli.asset_preservation import CanonicalContentProver, guard_destructive_removal
from specify_cli.runtime.home import get_package_asset_root
from specify_cli.runtime.migrate import shipped_mission_counterpart

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "4.0.0rc8_repair_historical_sweep_overrides"
TARGET_VERSION = "4.0.0rc8"

_OVERRIDE_DIR: tuple[str, ...] = (".kittify", "overrides")
_MISSION_DIR = "missions"


def kept_warning(rel: str) -> str:
    """Warning for an override that differs from the file the package ships."""
    return (
        f"Kept {rel}: it differs from the file Spec Kitty ships at that path, so it is "
        "treated as your edit — and it still overrides the shipped file. Delete it to use "
        "the shipped version."
    )


def skipped_tree_warning(rel: str) -> str:
    """Warning for a path component that is a symlink or not a directory."""
    return f"Historical override cleanup skipped {rel}: it is a symlink or not a directory; nothing there was changed"


def skipped_symlink_warning(rel: str) -> str:
    """Warning for an override file that is a symlink."""
    return f"Skipped {rel}: it is a symlink, so it was not compared and not removed"


def _rel(path: Path, project_path: Path) -> str:
    try:
        return path.relative_to(project_path).as_posix()
    except ValueError:
        return str(path)


@dataclass(frozen=True)
class _Candidate:
    """One override file that has a shipped counterpart at the same path."""

    path: Path
    counterpart: Path


def _override_root(project_path: Path) -> tuple[Path | None, list[str]]:
    """Return ``project/.kittify/overrides/missions`` when every component is real.

    Returns ``(None, [])`` when a component is absent (nothing to do) and
    ``(None, [rel])`` naming the first component that is a symlink or not a
    directory, which is refused.
    """
    current = project_path
    for part in (*_OVERRIDE_DIR, _MISSION_DIR):
        current = current / part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            return None, [_rel(current, project_path)]
        if not current.exists():
            return None, []
    return current, []


def _scan(project_path: Path, package_root: Path) -> tuple[list[_Candidate], list[str]]:
    """Return every override with a shipped counterpart, plus refusal warnings."""
    root, refused = _override_root(project_path)
    if root is None:
        return [], [skipped_tree_warning(rel) for rel in refused]

    overrides_root = project_path.joinpath(*_OVERRIDE_DIR)
    candidates: list[_Candidate] = []
    warnings = [skipped_tree_warning(rel) for rel in refused]
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            warnings.append(skipped_symlink_warning(_rel(path, project_path)))
            continue
        if not path.is_file():
            continue
        counterpart = shipped_mission_counterpart(path.relative_to(overrides_root), package_root)
        if counterpart is not None:
            candidates.append(_Candidate(path=path, counterpart=counterpart))
    return candidates, warnings


@MigrationRegistry.register
class RepairHistoricalSweepOverridesMigration(BaseMigration):
    """Remove historical sweep-created mission overrides that match the shipped files."""

    migration_id = MIGRATION_ID
    description = "Remove historical sweep-created mission overrides that match the shipped files"
    target_version = TARGET_VERSION

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002 -- the package asset root is project-independent
        """True when an override has a shipped counterpart, or a scanned path is refused.

        A *differing* override also reports the step as needed: its warning is the
        only thing that tells the operator their file shadows the shipped one.
        """
        try:
            package_root = get_package_asset_root()
        except FileNotFoundError:
            return False
        candidates, refused = _scan(project_path, package_root)
        return bool(candidates or refused)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002 -- the package asset root is project-independent
        """Refuse (a skip, retried later) when the shipped files cannot be located."""
        try:
            get_package_asset_root()
        except FileNotFoundError as exc:
            return False, f"Could not locate the shipped mission files: {exc}"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Remove each proven-identical override; keep and name every other file."""
        try:
            package_root = get_package_asset_root()
        except FileNotFoundError as exc:
            return MigrationResult(
                success=False,
                errors=[f"Cannot locate the shipped mission files — unable to compare overrides: {exc}"],
            )

        candidates, warnings = _scan(project_path, package_root)
        changes: list[str] = []
        errors: list[str] = []
        removed = 0
        for candidate in candidates:
            rel = _rel(candidate.path, project_path)
            try:
                canonical = candidate.counterpart.read_bytes()
            except OSError as exc:
                errors.append(f"Could not read the shipped counterpart for {rel}: {exc}")
                continue

            verdict = guard_destructive_removal(
                candidate.path,
                project_path,
                prover=CanonicalContentProver(canonical=canonical, check_marker=False),
                dry_run=dry_run,
            )
            if verdict.owned:
                removed += 1
                changes.append(verdict.diagnostic)
            else:
                warnings.append(kept_warning(rel))

        if removed == 0:
            changes.append("No historical sweep-created override matched a shipped file — nothing removed")

        return MigrationResult(success=not errors, changes_made=changes, warnings=warnings, errors=errors)
