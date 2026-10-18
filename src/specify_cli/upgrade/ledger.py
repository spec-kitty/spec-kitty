"""The explicit two-partition migration ledger (ADR 2026-10-17-1).

The ledger is the execution authority for "already applied". It is two
append-only JSONL files, partitioned by whether a migration's effect is tracked
or clone-local:

* ``.kittify/migration-ledger.jsonl`` — tracked; authority for migrations whose
  ``clone_local_effect`` is False (the effect travels with the commit).
* ``.kittify/migrations/clone-local.jsonl`` — per-clone, inside the already
  IGNORED ``.kittify/migrations/`` surface; authority for migrations whose
  ``clone_local_effect`` is True (the effect — ``.git/info/exclude``,
  ``git config --local``, ``.git/hooks`` — does not travel).

``clone_local_effect`` is the **routing key**: it decides which partition a
record is written to and read from.

Durability (NFR-001): every append is a full-file atomic rewrite via
``specify_cli/core/atomic.py`` (→ ``kernel.atomic``), never ``O_APPEND`` — a
crash leaves a valid old-or-new ledger, never a torn/partial file. The
subsystem is single-writer; ``kernel.locks`` is the named extension point if
cross-process concurrency ever becomes real, deliberately not built here.

This module must NOT import ``base.py``: it reaches migration identity and
``content_hash_sources`` through defensive ``getattr`` so it works whether or
not those ClassVars exist yet (they land in WP02).
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from kernel.clock import datetime, now_utc, parse_iso
from kernel.content_digest import sha256_digest

from specify_cli.core.atomic import atomic_write
from specify_cli.version_utils import get_version

from .metadata import _LEGACY_MIGRATION_ID_MAP

#: Tracked partition — a sibling of ``metadata.yaml`` (confirmed not git-ignored).
TRACKED_LEDGER_RELPATH = ".kittify/migration-ledger.jsonl"
#: Per-clone partition — inside the already-IGNORED ``.kittify/migrations/`` surface.
CLONE_LOCAL_LEDGER_RELPATH = ".kittify/migrations/clone-local.jsonl"

# Record field keys (hoisted; S1192).
_K_ID = "id"
_K_APPLIED_AT = "applied_at"
_K_RESULT = "result"
_K_IDENTITY = "identity"
_K_CONTENT_HASH = "content_hash"
_K_CLI_VERSION = "cli_version"
_K_CLONE_LOCAL = "clone_local"

_PARTITION_TRACKED = "tracked"
_PARTITION_CLONE_LOCAL = "clone-local"


@dataclass
class LedgerRecord:
    """One append-only ledger record (FR-003).

    ``clone_local`` is serialized only when True: a tracked record omits the
    key entirely; a per-clone record carries ``clone_local: true``.
    """

    id: str
    applied_at: datetime
    result: str
    identity: str
    content_hash: str
    cli_version: str
    clone_local: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            _K_ID: self.id,
            _K_APPLIED_AT: self.applied_at.isoformat(),
            _K_RESULT: self.result,
            _K_IDENTITY: self.identity,
            _K_CONTENT_HASH: self.content_hash,
            _K_CLI_VERSION: self.cli_version,
        }
        if self.clone_local:
            payload[_K_CLONE_LOCAL] = True
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LedgerRecord:
        record_id = data[_K_ID]
        return cls(
            id=record_id,
            applied_at=parse_iso(data[_K_APPLIED_AT]),
            result=data[_K_RESULT],
            identity=data.get(_K_IDENTITY, record_id),
            content_hash=data.get(_K_CONTENT_HASH, ""),
            cli_version=data.get(_K_CLI_VERSION, "unknown"),
            clone_local=bool(data.get(_K_CLONE_LOCAL, False)),
        )


def current_cli_version() -> str:
    """The CLI version to stamp on a record (robust; never raises)."""
    return str(get_version())


def _migration_id_of(migration: object) -> str:
    # `migration` is typed `object` by deliberate design (see the module
    # docstring: the ledger must not import base.py); every real caller passes a
    # BaseMigration, which always carries `migration_id`.
    return str(migration.migration_id)  # type: ignore[attr-defined]


def _identity_of(migration: object) -> str:
    """The stable drift key: ``identity`` ClassVar if present (WP02), else ``migration_id``."""
    return str(getattr(migration, "identity", None) or _migration_id_of(migration))


def _migration_module_file(migration: object) -> Path:
    source = inspect.getsourcefile(type(migration)) or inspect.getfile(type(migration))
    return Path(source)


def _resolve_source(migration: object, name: str) -> Path:
    candidate = Path(name)
    if candidate.is_absolute():
        return candidate
    return _migration_module_file(migration).parent / name


def compute_content_hash(migration: object) -> str:
    """``sha256:<hex>`` over the migration's defining source bytes (D2).

    By default the single defining module file; when the migration declares a
    ``content_hash_sources`` tuple, the sorted-concatenated bytes of those
    files (module-relative or absolute) — deterministic regardless of the
    declaration order.
    """
    sources: tuple[str, ...] = getattr(migration, "content_hash_sources", ())
    if sources:
        paths = sorted((_resolve_source(migration, name) for name in sources), key=str)
        data = b"".join(path.read_bytes() for path in paths)
    else:
        data = _migration_module_file(migration).read_bytes()
    return sha256_digest(data)


def build_record(
    migration: object,
    result: str,
    *,
    cli_version: str | None = None,
    applied_at: datetime | None = None,
) -> LedgerRecord:
    """Build a record for *migration*, routing-key and drift fields filled in.

    Identity and ``clone_local`` are read via defensive ``getattr`` so this
    never import-depends on ``base.py``.
    """
    return LedgerRecord(
        id=_migration_id_of(migration),
        applied_at=applied_at or now_utc(),
        result=result,
        identity=_identity_of(migration),
        content_hash=compute_content_hash(migration),
        cli_version=cli_version or current_cli_version(),
        clone_local=bool(getattr(migration, "clone_local_effect", False)),
    )


def _parse_records(lines: list[str]) -> list[LedgerRecord]:
    records: list[LedgerRecord] = []
    for line in lines:
        try:
            records.append(LedgerRecord.from_dict(json.loads(line)))
        except (ValueError, KeyError):
            continue  # a malformed line is skipped, not fatal
    return records


def _normalize_records(records: list[LedgerRecord]) -> list[LedgerRecord]:
    """Apply legacy-id normalization on read and collapse aliases to one record (FR-009)."""
    by_id: dict[str, LedgerRecord] = {}
    for record in records:
        canonical = _LEGACY_MIGRATION_ID_MAP.get(record.id, record.id)
        by_id[canonical] = record if canonical == record.id else replace(record, id=canonical)
    return list(by_id.values())


@dataclass(frozen=True)
class LedgerReportRow:
    """One assembled report row — the single shape WP03's surface and ``--json`` consume (D2)."""

    id: str
    identity: str
    partition: str
    applied: bool
    result: str | None
    drift: bool | None
    in_place_here: bool | None


class MigrationLedger:
    """Read/append the two-partition ledger, routed by ``clone_local_effect``."""

    def __init__(self, project_root: Path | str) -> None:
        self.project_root = Path(project_root)

    @property
    def tracked_path(self) -> Path:
        return self.project_root / TRACKED_LEDGER_RELPATH

    @property
    def clone_local_path(self) -> Path:
        return self.project_root / CLONE_LOCAL_LEDGER_RELPATH

    def _path_for(self, clone_local: bool) -> Path:
        return self.clone_local_path if clone_local else self.tracked_path

    @staticmethod
    def _read_raw_lines(path: Path) -> list[str]:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return []
        return [line for line in text.splitlines() if line.strip()]

    def _read(self, path: Path) -> list[LedgerRecord]:
        return _normalize_records(_parse_records(self._read_raw_lines(path)))

    def read_tracked(self) -> list[LedgerRecord]:
        return self._read(self.tracked_path)

    def read_clone_local(self) -> list[LedgerRecord]:
        return self._read(self.clone_local_path)

    def read_all(self) -> list[LedgerRecord]:
        return self.read_tracked() + self.read_clone_local()

    def applicable_records_for(self, migration: object) -> list[LedgerRecord]:
        """Records from the partition that is authoritative for *migration* (routing key)."""
        return self._read(self._path_for(bool(getattr(migration, "clone_local_effect", False))))

    def append(self, record: LedgerRecord) -> None:
        """Append *record* via a full-file atomic rewrite (NFR-001 — no O_APPEND)."""
        path = self._path_for(record.clone_local)
        lines = self._read_raw_lines(path)
        lines.append(json.dumps(record.to_dict(), ensure_ascii=False))
        atomic_write(path, "\n".join(lines) + "\n", mkdir=True)

    def recorded_ids_for(self, migration: object) -> set[str]:
        return {record.id for record in self.applicable_records_for(migration)}

    def drift_for(self, migration: object) -> bool | None:
        """Recorded-hash vs current-hash by ``identity``; ``None`` when not recorded (D2, audit only)."""
        identity = _identity_of(migration)
        match = next((r for r in self.applicable_records_for(migration) if r.identity == identity), None)
        if match is None:
            return None
        return match.content_hash != compute_content_hash(migration)


#: The ledger result that settles a migration; the single source of the success-only
#: "applied" rule, shared with ``registry.migration_settled``.
SETTLED_RESULT = "success"


def _safe_detect(migration: object, project_root: Path) -> bool:
    detect = getattr(migration, "detect", None)
    if detect is None:
        return False
    try:
        return bool(detect(project_root))
    except Exception:  # noqa: BLE001 - report assembly never fails on one migration's detect()
        return False


def assemble_report(migrations: list[object], project_root: Path | str) -> list[LedgerReportRow]:
    """Assemble declared/applied/partition/in-place/drift rows for the read surface (D2).

    ``in_place_here`` is meaningful only for a clone-local migration: ``detect()``
    True means the OLD state is present (effect absent), so in-place is ``not
    detect()``. For a tracked migration it is ``None``.
    """
    ledger = MigrationLedger(project_root)
    root = Path(project_root)
    rows: list[LedgerReportRow] = []
    for migration in migrations:
        clone_local = bool(getattr(migration, "clone_local_effect", False))
        identity = _identity_of(migration)
        match = next(
            (r for r in ledger.applicable_records_for(migration) if r.identity == identity),
            None,
        )
        rows.append(
            LedgerReportRow(
                id=_migration_id_of(migration),
                identity=identity,
                partition=_PARTITION_CLONE_LOCAL if clone_local else _PARTITION_TRACKED,
                applied=match is not None and match.result == SETTLED_RESULT,
                result=match.result if match else None,
                drift=ledger.drift_for(migration) if match is not None else None,
                in_place_here=(not _safe_detect(migration, root)) if clone_local else None,
            )
        )
    return rows
