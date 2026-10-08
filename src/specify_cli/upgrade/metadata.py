"""Project metadata management for Spec Kitty upgrade system."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from kernel.clock import datetime, now_utc, parse_iso
from pathlib import Path
from typing import Any

import yaml

from specify_cli.core.atomic import atomic_write

logger = logging.getLogger(__name__)

_LEGACY_MIGRATION_ID_MAP: dict[str, str] = {
    "0.10.12_constitution_cleanup": "0.10.12_charter_cleanup",
    "0.13.0_update_constitution_templates": "0.13.0_update_charter_templates",
    "2.0.0_constitution_directory": "2.0.0_charter_directory",
    "2.0.2_constitution_context_bootstrap": "2.0.2_charter_context_bootstrap",
    "2.1.2_fix_constitution_doctrine_skill": "2.1.2_fix_charter_doctrine_skill",
}


def _mask_volatile_metadata(text: str) -> str:
    """Return ``text`` with the volatile ``last_upgraded_at`` timestamp
    neutralized for compare-before-write (issue #1871).

    ``last_upgraded_at`` is bumped by the migrations-applied upgrade path on
    every successful run, even a no-op; masking its value lets a no-op save
    compare equal and skip, keeping the on-disk timestamp stable.

    ``schema_version`` is intentionally NOT masked (#3334): ``ProjectMetadata``
    round-trips it like any other field (see ``load``/``save`` below), so a
    legitimate ``schema_version`` change must be visible to the
    compare-before-write and force a write rather than being silently dropped.
    """
    masked: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("last_upgraded_at:"):
            indent = line[: len(line) - len(stripped)]
            masked.append(f"{indent}last_upgraded_at: <masked>")
            continue
        masked.append(line)
    return "\n".join(masked)


@dataclass
class MigrationRecord:
    """Record of a single migration application."""

    id: str
    applied_at: datetime
    result: str  # "success", "skipped", "failed"
    notes: str | None = None


@dataclass
class ProjectMetadata:
    """Metadata for a Spec Kitty project stored in .kittify/metadata.yaml."""

    version: str
    initialized_at: datetime
    last_upgraded_at: datetime | None = None
    python_version: str = ""
    platform: str = ""
    platform_version: str = ""
    applied_migrations: list[MigrationRecord] = field(default_factory=list)
    # schema_version round-trips spec_kitty.schema_version (#3334): load()
    # populates it from disk and save() writes it back unconditionally, so no
    # save() caller (success path, failed-migration recording, doctor,
    # regeneration, ...) can silently strip it. ``None`` means the field is
    # genuinely absent (a pre-3.x project that has never been migrated) and
    # must continue to write no key, preserving LEGACY classification.
    schema_version: int | None = None

    @classmethod
    def load(cls, kittify_dir: Path) -> ProjectMetadata | None:
        """Load metadata from .kittify/metadata.yaml.

        Args:
            kittify_dir: Path to the .kittify directory

        Returns:
            ProjectMetadata if file exists, None otherwise
        """
        metadata_path = kittify_dir / "metadata.yaml"
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, encoding="utf-8-sig") as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError):
            return None

        if not data:
            return None

        spec_kitty = data.get("spec_kitty", {})
        env = data.get("environment", {})
        migrations_data = data.get("migrations", {}).get("applied", [])

        applied = []
        for m in migrations_data:
            try:
                applied.append(
                    MigrationRecord(
                        id=m["id"],
                        applied_at=parse_iso(m["applied_at"]),
                        result=m["result"],
                        notes=m.get("notes"),
                    )
                )
            except (KeyError, ValueError):
                # Skip malformed migration records
                continue

        initialized_at_str = spec_kitty.get("initialized_at")
        try:
            initialized_at = parse_iso(initialized_at_str) if initialized_at_str else now_utc()
        except ValueError:
            initialized_at = now_utc()

        last_upgraded_str = spec_kitty.get("last_upgraded_at")
        try:
            last_upgraded_at = parse_iso(last_upgraded_str) if last_upgraded_str else None
        except ValueError:
            last_upgraded_at = None

        raw_schema_version = spec_kitty.get("schema_version")
        schema_version: int | None
        try:
            schema_version = int(raw_schema_version) if raw_schema_version is not None else None
        except (TypeError, ValueError):
            # Malformed schema_version on disk is treated as absent rather
            # than raising, consistent with the other defensive parses above.
            schema_version = None

        metadata = cls(
            version=spec_kitty.get("version", "unknown"),
            initialized_at=initialized_at,
            last_upgraded_at=last_upgraded_at,
            python_version=env.get("python_version", ""),
            platform=env.get("platform", ""),
            platform_version=env.get("platform_version", ""),
            applied_migrations=applied,
            schema_version=schema_version,
        )
        # Note: legacy ID normalization is NOT performed on load.
        # It must be triggered explicitly via normalize_and_save_legacy_ids()
        # to avoid mutating files during dry-run or read-only operations.
        return metadata

    def normalize_and_save_legacy_ids(self, kittify_dir: Path) -> list[str]:
        """Normalize constitution-era migration IDs and persist if changed.

        Returns a list of change descriptions for reporting.
        Call this explicitly from the migration runner or charter-rename
        migration -- never from load().
        """
        changes: list[str] = []
        if self._normalize_legacy_ids():
            self.save(kittify_dir)
            changes.append("Normalized legacy constitution-era migration IDs to charter-era IDs")
        return changes

    def _normalize_legacy_ids(self) -> bool:
        """Rewrite constitution-era migration IDs to charter-era IDs.

        Returns True if any IDs were rewritten.
        """
        changed = False
        for record in self.applied_migrations:
            new_id = _LEGACY_MIGRATION_ID_MAP.get(record.id)
            if new_id:
                record.id = new_id
                changed = True
        return changed

    def save(self, kittify_dir: Path) -> bool:
        """Save metadata to .kittify/metadata.yaml.

        Performs a masked compare-before-write (issue #1871): if the only
        difference between the rendered content and the file already on disk
        is the volatile ``last_upgraded_at`` timestamp (which the migrations-
        applied upgrade path bumps unconditionally), the write is skipped.
        This stops no-op upgrades from churning the file/mtime or advancing
        ``last_upgraded_at``, and closes the class for every ``save()``
        caller (upgrade/doctor/regeneration) rather than adding per-path
        guards.

        The write is **merge-preserving** (#5229): the file on disk is the base and
        only the keys this model owns are overwritten -- ``spec_kitty.version``,
        ``initialized_at``, ``last_upgraded_at`` and (when not ``None``)
        ``schema_version``; the ``environment`` triple; and ``migrations.applied``
        (the model is the authority for the applied record). Every other key --
        ``project_uuid``, ``schema_capabilities``, operator keys at any level --
        is kept in place, so a save can no longer erase what another writer
        stamped. An unreadable or non-mapping file falls back to the model alone.

        ``schema_version`` round-trips through this method like any other
        field (#3334): when ``self.schema_version`` is not ``None`` it is
        written into the ``spec_kitty`` block, so a caller that loads
        metadata, mutates something unrelated (e.g. records a failed
        migration), and saves again can no longer silently strip the stamp
        and wedge the project into ``LEGACY`` classification. ``None`` (a
        genuinely unmigrated pre-3.x project) writes no key and leaves whatever
        the disk already has.

        Args:
            kittify_dir: Path to the .kittify directory

        Returns:
            ``True`` if the file was written; ``False`` if the write was
            skipped because nothing material changed.
        """
        metadata_path = kittify_dir / "metadata.yaml"

        existing_text: str | None = None
        if metadata_path.exists():
            try:
                existing_text = metadata_path.read_text(encoding="utf-8-sig")
            except OSError:
                existing_text = None

        merged = _merge_onto_disk(_parse_mapping_text(existing_text), self._model_owned_mapping())
        buf = io.StringIO()
        buf.write(_METADATA_HEADER)
        yaml.dump(merged, buf, default_flow_style=False, sort_keys=False)
        new_content = buf.getvalue()

        if existing_text is not None and _mask_volatile_metadata(existing_text) == _mask_volatile_metadata(new_content):
            return False

        atomic_write(metadata_path, new_content, mkdir=True)
        return True

    def _model_owned_mapping(self) -> dict[str, Any]:
        """The part of ``metadata.yaml`` this model is the authority for.

        ``schema_version`` is present only when the model has one: ``None`` means
        "no opinion", so a merge neither forges nor erases the key.
        """
        spec_kitty_block: dict[str, Any] = {
            "version": self.version,
            "initialized_at": self.initialized_at.isoformat(),
            "last_upgraded_at": (self.last_upgraded_at.isoformat() if self.last_upgraded_at else None),
        }
        if self.schema_version is not None:
            spec_kitty_block["schema_version"] = self.schema_version
        return {
            "spec_kitty": spec_kitty_block,
            "environment": {
                "python_version": self.python_version,
                "platform": self.platform,
                "platform_version": self.platform_version,
            },
            "migrations": {
                "applied": [
                    {
                        "id": m.id,
                        "applied_at": m.applied_at.isoformat(),
                        "result": m.result,
                        "notes": m.notes,
                    }
                    for m in self.applied_migrations
                ]
            },
        }

    def has_migration(self, migration_id: str) -> bool:
        """Check if a migration has been successfully applied.

        Args:
            migration_id: The ID of the migration to check

        Returns:
            True if migration was applied successfully
        """
        return any(m.id == migration_id and m.result == "success" for m in self.applied_migrations)

    def record_migration(self, migration_id: str, result: str, notes: str | None = None) -> bool:
        """Record a migration application.

        Recording is idempotent: if an identical ``(migration_id, result)``
        record already exists, this is a no-op. Without this, a migration whose
        ``detect()`` is ``False`` is re-recorded as ``skipped`` / "Not
        applicable" on *every* upgrade run over the same version range, growing
        ``applied_migrations`` without bound and churning timestamps (issue
        #1872). A genuine result transition (e.g. a previously ``failed``
        migration that now succeeds) carries a different ``result`` and is
        still appended.

        Args:
            migration_id: The ID of the migration
            result: The result ("success", "skipped", "failed")
            notes: Optional notes about the migration

        Returns:
            ``True`` if a new record was appended; ``False`` if an identical
            record already existed and the call was a no-op.
        """
        if any(
            m.id == migration_id and m.result == result
            for m in self.applied_migrations
        ):
            return False
        self.applied_migrations.append(
            MigrationRecord(
                id=migration_id,
                applied_at=now_utc(),
                result=result,
                notes=notes,
            )
        )
        return True


_VERSION_TRIO_KEYS = ("version", "last_upgraded_at", "schema_version")
#: What a failed upgrade restores: the trio plus the capability map the schema stamp writes (#5229),
#: so a failed run leaves the stamp exactly as it found it.
_STAMP_KEYS = (*_VERSION_TRIO_KEYS, "schema_capabilities")
_METADATA_HEADER = "# Spec Kitty Project Metadata\n# Auto-generated by spec-kitty init/upgrade\n# DO NOT EDIT MANUALLY\n\n"


def _parse_mapping_text(text: str | None) -> dict[str, Any]:
    """Parse ``metadata.yaml`` text into a mapping; ``{}`` when absent, unparseable or not a mapping."""
    if text is None:
        return {}
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _merge_onto_disk(existing: dict[str, Any], owned: dict[str, Any]) -> dict[str, Any]:
    """Overlay the model-owned keys ``owned`` onto the on-disk mapping ``existing``.

    Insertion order of ``existing`` is kept and new keys are appended at the end
    of their block, so a save that changes nothing renders byte-identically.
    A block that is not a mapping on disk is replaced by the model's.
    """
    merged = dict(existing)
    for key, owned_block in owned.items():
        disk_block = merged.get(key)
        block = dict(disk_block) if isinstance(disk_block, dict) else {}
        block.update(owned_block)
        merged[key] = block
    return merged


def canonical_schema_capabilities(existing: object) -> dict[str, bool]:
    """The ``schema_capabilities`` map to stamp, given what ``metadata.yaml`` holds now (#5229).

    Same rule as ``init``'s stamp: an operator-owned map is never touched; an
    absent or malformed value becomes the canonical map; a legacy list (written
    by older spec-kitty) becomes ``{name: True}`` completed with the canonical
    names. The canonical map is read from the schema module at call time so the
    stamp can never drift from ``CURRENT_SCHEMA_CAPABILITIES``.
    """
    from specify_cli.migration import schema_version as _sv

    canonical = dict(_sv.CURRENT_SCHEMA_CAPABILITIES)
    if isinstance(existing, dict):
        return existing
    if isinstance(existing, (list, tuple)):
        return {**canonical, **{str(name): True for name in existing}}
    if existing is not None:
        logger.warning("Replacing malformed spec_kitty.schema_capabilities %r with the canonical map", existing)
    return canonical


def _parse_metadata_mapping(raw: bytes) -> dict[str, object] | None:
    """Parse ``metadata.yaml`` bytes into a mapping, or ``None`` when unreadable or not a mapping."""
    try:
        data = yaml.safe_load(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def _without_version_trio(data: dict[str, object]) -> dict[str, object]:
    """``data`` minus the version trio and the ``environment`` block, which a stamp write reformats.

    What is left (the rest of ``spec_kitty``, the applied migrations, any
    foreign key) is what a restore must preserve rather than overwrite.
    """
    block = data.get("spec_kitty")
    rest = {k: v for k, v in data.items() if k not in ("spec_kitty", "environment")}
    migrations = rest.get("migrations")
    if not (isinstance(migrations, dict) and migrations.get("applied")):
        rest.pop("migrations", None)  # absent and "applied: []" are the same record of nothing
    if isinstance(block, dict):
        rest["spec_kitty"] = {k: v for k, v in block.items() if k not in _STAMP_KEYS}
    return rest


@dataclass(frozen=True)
class VersionStamp:
    """The pre-run ``.kittify/metadata.yaml`` version trio, captured to be restored on a failed upgrade.

    The trio is ``spec_kitty.version``, ``spec_kitty.last_upgraded_at`` and
    ``spec_kitty.schema_version`` (#3334 / #4275). This is the single restore
    authority: the runner uses it for a failed migration, the CLI for a failure
    in the final surface repair. The applied-migrations list is deliberately
    NOT restored -- it records what actually ran, so a re-run skips it.
    """

    raw: bytes | None
    """The whole file as it was (``None`` when it did not exist)."""

    @property
    def version(self) -> str | None:
        """The captured ``spec_kitty.version`` (``None`` when absent or unreadable)."""
        data = _parse_metadata_mapping(self.raw) if self.raw is not None else None
        block = data.get("spec_kitty") if data is not None else None
        value = block.get("version") if isinstance(block, dict) else None
        return str(value) if value is not None else None

    @classmethod
    def capture(cls, kittify_dir: Path) -> VersionStamp:
        """Snapshot ``kittify_dir/metadata.yaml`` (an unreadable file is captured as absent)."""
        try:
            return cls(raw=(kittify_dir / "metadata.yaml").read_bytes())
        except OSError:
            return cls(raw=None)

    def restore(self, kittify_dir: Path) -> bool:
        """Put the captured version trio back; return ``True`` when the file was rewritten.

        When nothing but the trio changed since capture the original bytes are
        written back, so the file is byte-identical to its pre-run state.
        Otherwise (migrations recorded in between) only the trio is patched
        into the current content. A file that did not exist before is left as
        the run wrote it (it records the failed migration, and there is no
        earlier stamp to restore); an unparseable capture or current file is
        left alone.
        """
        path = kittify_dir / "metadata.yaml"
        if self.raw is None:
            return False
        try:
            current_raw = path.read_bytes()
        except OSError:
            current_raw = None
        if current_raw == self.raw:
            return False
        before = _parse_metadata_mapping(self.raw)
        current = _parse_metadata_mapping(current_raw) if current_raw is not None else None
        if before is None or current is None:
            return False
        if _without_version_trio(before) == _without_version_trio(current):
            atomic_write(path, self.raw.decode("utf-8"), mkdir=True)
            return True
        return self._patch_trio(path, before, current)

    @staticmethod
    def _patch_trio(path: Path, before: dict[str, object], current: dict[str, object]) -> bool:
        """Write the captured trio into ``current`` and persist it; ``True`` when the trio actually differed."""
        old_block = before.get("spec_kitty")
        old = old_block if isinstance(old_block, dict) else {}
        block = current.get("spec_kitty")
        if not isinstance(block, dict):
            block = {}
            current["spec_kitty"] = block
        changed = False
        for key in _STAMP_KEYS:
            if key in old:
                changed |= block.get(key) != old[key]
                block[key] = old[key]
            else:
                changed |= block.pop(key, None) is not None
        if not changed:
            return False
        buf = io.StringIO()
        buf.write(_METADATA_HEADER)
        yaml.dump(current, buf, default_flow_style=False, sort_keys=False)
        atomic_write(path, buf.getvalue(), mkdir=True)
        return True
