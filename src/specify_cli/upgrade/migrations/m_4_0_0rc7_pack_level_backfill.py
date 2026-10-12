"""Migration: backfill ``pack.yaml`` for an existing project pack (FR-010, #6048).

The ``pack_level`` mission makes every Charter Pack declare its tier in
``pack.yaml`` (the single :data:`kernel.pack_tiers.PackTier` authority). A
legacy install's project pack — the one flat pack at ``.kittify/charter-packs/``
(:mod:`kernel.charter_pack_paths`) — may have no ``pack.yaml`` at all, so
``charter pack validate`` and the ``pack_level`` resolver have nothing to read.
This migration heals such an install: it writes a minimal, loadable descriptor
(``pack_id`` ULID + ``name`` handle + ``pack_level: project``) for a project
pack that lacks one.

Contract (``contracts/pack-descriptor.contract.md`` — Migration contract):

* **config-aware discovery** — the project layer is one flat pack resolved
  through :func:`kernel.charter_pack_paths.project_pack_root`, never a
  hard-coded literal spelled here;
* **never ``mkdir``** — a project with no ``charter-packs`` directory is a
  clean no-op (mirrors the ``get_agent_dirs``-style "respect deletions" rule);
* **project pack only** — the single flat pack at ``.kittify/charter-packs/``;
  the built-in and org (internal) packs are never reached;
* **never clobber an authored ``pack.yaml``** — ``pack_level`` is added only
  when absent, and a differing/authored ``pack_id`` is preserved verbatim;
* **idempotent** — a re-run over an already-backfilled pack makes no change.

Sibling precedent: the ``3.2.x`` gitignore backfills and
``m_4_0_0rc6_charter_pack_cutover`` (which also walks the project pack root).
Auto-discovered by :func:`~specify_cli.upgrade.migrations.auto_discover_migrations`
— the ``m_*`` filename plus the ``@MigrationRegistry.register`` decorator are the
whole registration mechanism; there is no hand-maintained migration list.
"""

from __future__ import annotations

import io
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ulid import ULID

from kernel.atomic import atomic_write
from kernel.charter_pack_paths import (
    PROJECT_PACK_DIRNAME,
    project_pack_root,
)
from kernel.pack_tiers import PROJECT

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

#: The authored descriptor filename inside a pack root.
_PACK_DESCRIPTOR_FILENAME = "pack.yaml"

#: The descriptor key this migration owns.
_PACK_LEVEL_KEY = "pack_level"


def _write_atomically(descriptor: Path, data: object, yaml: YAML) -> None:
    """Dump *data* to *descriptor* through the kernel atomic-write helper.

    A crash mid-write can never leave a truncated ``pack.yaml`` behind.
    """
    buffer = io.StringIO()
    yaml.dump(data, buffer)
    atomic_write(descriptor, buffer.getvalue())


def _discover_project_pack_roots(repo_root: Path) -> list[Path]:
    """Return the existing project pack roots to consider (config-aware).

    The project layer is a single flat pack at ``.kittify/charter-packs/``
    (:func:`kernel.charter_pack_paths.project_pack_root`). A root is returned
    only when it already exists on disk (never ``mkdir``).
    """
    root = project_pack_root(repo_root)
    return [root] if root.is_dir() else []


def _needs_backfill(pack_root: Path) -> bool:
    """Whether *pack_root* needs a write: no ``pack.yaml`` or one without ``pack_level``."""
    descriptor = pack_root / _PACK_DESCRIPTOR_FILENAME
    if not descriptor.is_file():
        return True
    data = YAML(typ="safe").load(descriptor.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        # Malformed/non-mapping descriptor is not something this migration
        # rewrites; leave it for ``charter pack validate`` to flag.
        return False
    return _PACK_LEVEL_KEY not in data


def _display_path(descriptor: Path, project_path: Path) -> str:
    """Return *descriptor* relative to the project for change notes.

    The notes land in the committed ``.kittify/metadata.yaml``, so they must
    never carry the operator's absolute path.
    """
    try:
        return descriptor.relative_to(project_path).as_posix()
    except ValueError:
        return descriptor.name


def _write_fresh_descriptor(pack_root: Path, project_path: Path) -> str:
    """Write a new minimal project descriptor and return the change description."""
    descriptor = pack_root / _PACK_DESCRIPTOR_FILENAME
    payload = {
        "pack_id": str(ULID()),
        "name": pack_root.parent.parent.name or PROJECT_PACK_DIRNAME,
        _PACK_LEVEL_KEY: PROJECT,
    }
    _write_atomically(descriptor, payload, YAML())
    return f"Wrote {_display_path(descriptor, project_path)} with {_PACK_LEVEL_KEY}: {PROJECT}"


def _add_pack_level(pack_root: Path, project_path: Path) -> str:
    """Add ``pack_level: project`` to an authored ``pack.yaml`` lacking it.

    Uses the round-trip loader so author comments, key order and a differing
    ``pack_id`` survive the edit.
    """
    descriptor = pack_root / _PACK_DESCRIPTOR_FILENAME
    yaml = YAML()  # round-trip preserves authored content
    data = yaml.load(descriptor.read_text(encoding="utf-8"))
    data[_PACK_LEVEL_KEY] = PROJECT
    _write_atomically(descriptor, data, yaml)
    return f"Added {_PACK_LEVEL_KEY}: {PROJECT} to {_display_path(descriptor, project_path)}"


@MigrationRegistry.register
class PackLevelBackfillMigration(BaseMigration):
    """Backfill ``pack.yaml`` (``pack_level: project``) for an existing project pack."""

    migration_id = "4.0.0rc7_pack_level_backfill"
    description = "Backfill pack.yaml (pack_level: project) for existing project packs (#6048)"
    target_version = "4.0.0rc7"

    def detect(self, project_path: Path) -> bool:
        try:
            return any(_needs_backfill(root) for root in _discover_project_pack_roots(project_path))
        except (YAMLError, OSError):
            # Route an unreadable descriptor through can_apply() so the runner
            # records a loud failure rather than silently skipping.
            return True

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not project_path.exists():
            return False, f"Project path does not exist: {project_path}"
        try:
            for root in _discover_project_pack_roots(project_path):
                _needs_backfill(root)
        except (YAMLError, OSError) as exc:
            return False, str(exc)
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        try:
            roots = _discover_project_pack_roots(project_path)
        except (YAMLError, OSError) as exc:
            return MigrationResult(success=False, errors=[str(exc)])

        changes: list[str] = []
        for pack_root in roots:
            try:
                if not _needs_backfill(pack_root):
                    continue
            except (YAMLError, OSError) as exc:
                return MigrationResult(success=False, errors=[str(exc)])

            has_descriptor = (pack_root / _PACK_DESCRIPTOR_FILENAME).is_file()
            if dry_run:
                verb = "add pack_level: project to" if has_descriptor else "write"
                changes.append(f"Would {verb} {_display_path(pack_root / _PACK_DESCRIPTOR_FILENAME, project_path)}")
                continue
            try:
                if has_descriptor:
                    changes.append(_add_pack_level(pack_root, project_path))
                else:
                    changes.append(_write_fresh_descriptor(pack_root, project_path))
            except (YAMLError, OSError) as exc:
                return MigrationResult(success=False, errors=[str(exc)])

        return MigrationResult(success=True, changes_made=changes)
