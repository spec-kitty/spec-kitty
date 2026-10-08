"""One-shot migration of legacy lifecycle envelopes to F1's strict shape.

F2-T1 (m1-contract-drafts/F2.md section 3.3/3.4/6.4): the local lifecycle
appenders in :mod:`specify_cli.status.lifecycle_events` write a 9-key
envelope (``event_id, event_type, aggregate_id, aggregate_type,
schema_version:"5.0.0", timestamp, payload, project_uuid, project_slug``).
F1 (``spec_kitty_events``, sibling repo) defines a strict 14-key envelope
profile that this shape does not satisfy: it carries one extra key
(``aggregate_type``) and is missing six strict keys (``build_id, node_id,
lamport_clock, causation_id, correlation_id, data_tier``).

This module performs a one-shot, idempotent, whole-file-atomic rewrite of
on-disk legacy rows into that strict shape, wrapping the SAME
``event_type``/``payload`` pair -- migration never touches semantic content,
only envelope bookkeeping keys. Lane-transition (``StatusEvent``) rows and
off-axis ``InnerStateChanged`` annotation rows are left completely
untouched (byte-identical), never even parsed as migration candidates.

Six synthesized keys, each reusing an existing repo primitive rather than
inventing a migration-only identity/clock scheme (F2.md section 3.3):

* ``causation_id``: explicit ``None`` -- every migrated row is treated as a
  root event (no parent event was ever recorded for these rows).
* ``correlation_id``: the row's own ``event_id`` -- mirrors
  ``sync/emitter.py``'s own live ``correlation_id = causation_id or
  event_id`` convention.
* ``data_tier``: ``0`` -- matches the strict ``Event`` model's own default.
* ``node_id``: the sha256(hostname:username) derivation shared with the
  deleted sync clock module (see ``_generate_node_id``) -- the one
  node-identity primitive already in the repo.
  This is the identity of the MACHINE RUNNING THE MIGRATION, not a
  reconstruction of the original writer's identity (which was never
  recorded and cannot be recovered) -- documented approximation, not a
  defect (F2.md section 7, residual risk 3).
* ``lamport_clock``: fixed ``0`` sentinel, never ticked -- the legacy row
  never recorded a clock value and this local journal has no causal clock
  at all (F2.md section 3.1 item 8); ``0`` means "no causal order
  recorded," not a real ordering position.
* ``build_id``: :func:`specify_cli.identity.project.derive_build_id`
  applied to ``(project_uuid, node_id)`` -- the exact deterministic UUID5
  derivation ``ProjectIdentity.with_defaults`` already uses when minting a
  missing build_id, so migration reproduces the value that path would have
  produced live.

Two rows are explicitly excluded from migration rather than silently
mangled:

* ``ReviewerSelfApproval`` -- no ``spec_kitty_events`` model exists for it
  (F1 U5, an open handoff, not resolved here). ``action:
  "skipped_no_model"``.
* Any row with ``project_uuid: null`` -- ``Event.project_uuid`` is a
  required, non-Optional field in the strict profile, so no strict
  envelope can be constructed (there is also no ``project_uuid`` to key
  ``derive_build_id`` on). ``action: "skipped_no_project_uuid"``.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from specify_cli.identity.project import derive_build_id

from .lifecycle_events import (
    LIFECYCLE_EVENT_TYPES,
    PROJECT_EVENTS_FILENAME,
    REVIEWER_SELF_APPROVAL,
    _repo_root_for_lifecycle_log,  # noqa: PLC2701 -- same-package reuse, not a public API
)
from .locking import feature_status_lock, project_event_log_lock
from .mission_write import mission_lock_key
from .store import (  # noqa: PLC2701 -- same-package reuse, not a public API
    StoreError,
    _fsync_directory,
    _read_text_without_following_symlinks,
)


#: The 6 STRICT_ENVELOPE_KEYS (F1.md section 3.2) genuinely absent from the
#: on-disk legacy shape -- not just the 5 the module's earlier framing named.
_SYNTHESIZED_KEYS = (
    "causation_id",
    "correlation_id",
    "data_tier",
    "node_id",
    "lamport_clock",
    "build_id",
)

_STRICT_SCHEMA_VERSION = "3.0.0"
_LEGACY_SCHEMA_VERSION = "5.0.0"

MigrationAction = Literal[
    "migrated",
    "unchanged",
    "skipped_no_model",
    "skipped_no_project_uuid",
]


@dataclass(frozen=True, slots=True)
class MigrationRowResult:
    """Per-row outcome of a migration pass."""

    event_id: str
    event_type: str
    action: MigrationAction
    pre_hash: str
    post_hash: str


@dataclass(frozen=True, slots=True)
class MigrationManifest:
    """Aggregate outcome of one :func:`migrate_lifecycle_envelope` run."""

    log_path: Path
    total_rows: int
    migrated_count: int
    unchanged_count: int
    skipped_count: int
    rows: tuple[MigrationRowResult, ...]
    refused_reason: str | None = None


def _content_hash(event_type: Any, payload: Any) -> str:
    """sha256 of the canonical-JSON ``(event_type, payload)`` pair.

    Scoped to semantic content only (never envelope bookkeeping keys) so a
    matching pre/post hash proves migration touched nothing but the
    envelope -- MIG1's own acceptance evidence.
    """
    canonical = json.dumps(
        {"event_type": event_type, "payload": payload}, sort_keys=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()  # noqa: TID251 -- file-integrity check (pre/post migration content proof), not a charter-hashed artifact


def _is_already_strict_shaped(row: dict[str, Any]) -> bool:
    """True when *row* already carries every synthesized key + the strict
    schema_version -- the idempotent re-run case (MIG2)."""
    if row.get("schema_version") != _STRICT_SCHEMA_VERSION:
        return False
    return all(key in row for key in _SYNTHESIZED_KEYS) and "aggregate_type" not in row



def _generate_node_id() -> str:
    """Stable machine identifier: first 12 hex chars of SHA-256(hostname:username).

    The same derivation the deleted ``sync.clock.generate_node_id`` used;
    parity with that module was pinned by
    ``tests/status/test_migrate_lifecycle_envelope_node_id_parity.py``.
    Kept local because ``status/`` is a CORE package and must stay free of
    INTEGRATION imports per tests/architectural/test_integration_boundary.py
    (closed allowlist). Introduced at M2 canonical integration.
    """
    import getpass  # noqa: PLC0415
    import hashlib  # noqa: PLC0415
    import socket  # noqa: PLC0415

    raw = f"{socket.gethostname()}:{getpass.getuser()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]  # noqa: TID251 - charter freshness ban; derivation mirrors the deleted sync clock

def _migrate_row(row: dict[str, Any]) -> tuple[dict[str, Any], MigrationAction]:
    """Return (possibly rewritten row, action) for one lifecycle envelope row.

    Never mutates *row*; always returns a fresh dict for the "migrated"
    case so the caller can tell migrated/unchanged rows apart by identity
    if it wants to.
    """
    if row.get("event_type") == REVIEWER_SELF_APPROVAL:
        return dict(row), "skipped_no_model"

    if _is_already_strict_shaped(row):
        return dict(row), "unchanged"

    if row.get("project_uuid") is None:
        return dict(row), "skipped_no_project_uuid"

    migrated = {k: v for k, v in row.items() if k != "aggregate_type"}
    migrated["schema_version"] = _STRICT_SCHEMA_VERSION

    node_id = _generate_node_id()
    project_uuid_str = str(row["project_uuid"])
    build_id = derive_build_id(UUID(project_uuid_str), node_id)

    migrated["causation_id"] = None
    migrated["correlation_id"] = row.get("event_id")
    migrated["data_tier"] = 0
    migrated["node_id"] = node_id
    migrated["lamport_clock"] = 0
    migrated["build_id"] = build_id

    return migrated, "migrated"


def _read_raw_lines(path: Path) -> list[tuple[int, str]]:
    """Read *path* as (1-based line number, non-blank raw line text) pairs.

    Distinct from :func:`specify_cli.status.store.read_events_raw` (which is
    hardcoded to ``feature_dir / EVENTS_FILENAME``): this migration tool
    operates on an explicit path that may be either the mission-level or the
    project-level log. Routes through
    :func:`specify_cli.status.store._read_text_without_following_symlinks`
    (the same ``O_NOFOLLOW`` symlink-escape guard ``append_raw_rows_atomic``
    enforces on its own read side, F2.md section 2.1) rather than a plain
    ``Path.read_text`` -- a log path is untrusted external-facing input, and
    migration must refuse to silently read (or, worse, subsequently replace)
    whatever a symlink at that path happens to point at.
    """
    text = _read_text_without_following_symlinks(path)
    return [
        (line_number, line)
        for line_number, line in enumerate(text.splitlines(), start=1)
        if line.strip()
    ]


def _lock_for_log_path(log_path: Path) -> AbstractContextManager[Path | None]:
    """Resolve the same lock ordinary writers of *log_path* use.

    Project-level log (``.kittify/canonical-events.jsonl``) -> the sibling
    ``project_event_log_lock``. Mission-level log (``status.events.jsonl``)
    -> ``feature_status_lock`` keyed by ``mission_lock_key(log_path.parent)``, the
    one key every writer of the Mission takes (the coordination directory name
    for a coordination-routed Mission, the directory name otherwise).
    When no repo root can be resolved, locking is skipped (matches this
    package's existing best-effort posture for unresolvable log paths).
    """
    repo_root = _repo_root_for_lifecycle_log(log_path)
    if repo_root is None:
        return contextlib.nullcontext()
    if log_path.name == PROJECT_EVENTS_FILENAME:
        return project_event_log_lock(repo_root)
    return feature_status_lock(repo_root, mission_lock_key(log_path.parent, repo_root=repo_root))


def _atomic_replace_file(path: Path, content: str) -> None:
    """Whole-file atomic replace: tmp-write -> fsync -> os.replace -> dir-fsync.

    Distinct from :func:`specify_cli.status.store.append_raw_rows_atomic`
    (which APPENDS to existing content): migration rewrites the whole file,
    so a mid-batch failure must leave the ORIGINAL file untouched rather
    than a half-appended one (F2.md section 3.3/3.4). Reuses the same
    durability primitive shape (temp file in the same directory, ``fsync``
    the file before ``os.replace``, ``fsync`` the directory after) as
    :mod:`specify_cli.status.store`'s writers.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    tmp_path = Path(raw_tmp_path)
    replaced = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
        replaced = True
        _fsync_directory(path.parent)
    finally:
        if not replaced:
            tmp_path.unlink(missing_ok=True)


def migrate_lifecycle_envelope(
    log_path: Path, *, dry_run: bool = False
) -> MigrationManifest:
    """One-shot, idempotent, all-or-nothing migration of *log_path*.

    Rewrites every legacy-shaped lifecycle row (event_type in
    ``LIFECYCLE_EVENT_TYPES``) into F1's strict 14-key envelope wrapping the
    identical ``event_type``/``payload``. Non-lifecycle rows (``StatusEvent``
    transitions, ``InnerStateChanged`` annotations, retrospective/decision
    rows -- anything without a lifecycle ``event_type``) are copied through
    byte-identical, never even parsed as candidates.

    Snapshots *log_path* to ``<name>.pre-migration.bak`` before any rewrite
    (refuses instead of overwriting an existing snapshot -- MIG4). Runs
    under the same lock ordinary writers of *log_path* use. ``dry_run=True``
    computes and returns the manifest without writing anything (no snapshot,
    no lock needed since nothing is mutated).

    Idempotency (MIG2) and the snapshot refusal (MIG4) compose deliberately:
    the manifest is always computed first, and the on-disk snapshot check
    only runs when there is actually something to write
    (``migrated_count > 0``). A re-run on an already-migrated file is a
    genuine no-op (``migrated_count == 0``) and returns cleanly regardless
    of whether a ``.bak`` happens to exist from an earlier run -- refusing
    would otherwise make every idempotent re-run report a spurious refusal
    the moment the first run's snapshot appeared on disk.
    """
    if dry_run:
        return _compute_manifest(log_path)

    with _lock_for_log_path(log_path):
        manifest, new_lines = _compute_manifest_and_lines(log_path)
        if manifest.migrated_count == 0:
            # Nothing to migrate (e.g. already strict, or empty file) --
            # skip the snapshot+replace round trip entirely so a repeated
            # no-op run never plants a spurious .bak and is never blocked
            # by a pre-existing one from an earlier real migration.
            return manifest

        backup_path = log_path.with_name(log_path.name + ".pre-migration.bak")
        if backup_path.exists():
            return MigrationManifest(
                log_path=log_path,
                total_rows=0,
                migrated_count=0,
                unchanged_count=0,
                skipped_count=0,
                rows=(),
                refused_reason=(
                    f"refusing to migrate: a prior snapshot already exists at "
                    f"{backup_path} (migration is one-shot per file; remove "
                    f"the snapshot manually once satisfied with the prior "
                    f"run before re-migrating)"
                ),
            )

        # Symlink-safe read (F2.md section 2.1): the same O_NOFOLLOW guard
        # every other reader/writer of these two files enforces, so a
        # symlinked log_path is refused here rather than silently followed
        # and then clobbered by the atomic replace below.
        original_text = _read_text_without_following_symlinks(log_path)
        _atomic_replace_file(backup_path, original_text)
        new_content = "".join(line + "\n" for line in new_lines)
        _atomic_replace_file(log_path, new_content)
    return manifest


def _compute_manifest(log_path: Path) -> MigrationManifest:
    manifest, _lines = _compute_manifest_and_lines(log_path)
    return manifest


def _compute_manifest_and_lines(
    log_path: Path,
) -> tuple[MigrationManifest, list[str]]:
    raw_lines = _read_raw_lines(log_path)
    row_results: list[MigrationRowResult] = []
    new_lines: list[str] = []
    migrated_count = 0
    unchanged_count = 0
    skipped_count = 0

    for line_number, raw_line in raw_lines:
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            # Same StoreError-shaped, line-numbered failure contract as
            # store.read_events_raw (F2.md section 4, IB1/IB2): fail
            # loud-and-legible on the exact invalid-byte input class this
            # migration tool exists to remediate, rather than crashing raw
            # with no line context.
            raise StoreError(f"Invalid JSON on line {line_number}: {exc}") from exc
        if not isinstance(row, dict) or row.get("event_type") not in LIFECYCLE_EVENT_TYPES:
            # Not a lifecycle row (StatusEvent transition, InnerStateChanged
            # annotation, retrospective/decision row, ...) -- pass through
            # byte-identical, never touched.
            new_lines.append(raw_line)
            continue

        pre_hash = _content_hash(row.get("event_type"), row.get("payload"))
        migrated_row, action = _migrate_row(row)
        post_hash = _content_hash(migrated_row.get("event_type"), migrated_row.get("payload"))

        row_results.append(
            MigrationRowResult(
                event_id=str(row.get("event_id")),
                event_type=str(row.get("event_type")),
                action=action,
                pre_hash=pre_hash,
                post_hash=post_hash,
            )
        )
        if action == "migrated":
            migrated_count += 1
            new_lines.append(json.dumps(migrated_row, sort_keys=True))
        elif action == "unchanged":
            unchanged_count += 1
            new_lines.append(raw_line)
        else:
            skipped_count += 1
            new_lines.append(raw_line)

    manifest = MigrationManifest(
        log_path=log_path,
        total_rows=len(row_results),
        migrated_count=migrated_count,
        unchanged_count=unchanged_count,
        skipped_count=skipped_count,
        rows=tuple(row_results),
    )
    return manifest, new_lines


__all__ = [
    "MigrationAction",
    "MigrationManifest",
    "MigrationRowResult",
    "migrate_lifecycle_envelope",
]
