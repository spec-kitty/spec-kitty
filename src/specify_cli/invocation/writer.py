"""InvocationWriter: append-only JSONL writer for invocation audit trail records."""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from kernel.clock import now_utc_iso
from specify_cli.core.utils import ensure_within_any
from specify_cli.invocation.errors import AlreadyClosedError, InvocationError, InvocationWriteError, LegacyRecordError
from specify_cli.invocation.record import (
    OpCompletedEvent,
    OpStartedEvent,
    parse_op_event,
    validate_invocation_id,
)

if TYPE_CHECKING:
    from glossary.chokepoint import GlossaryObservationBundle

EVENTS_DIR = "kitty-ops"
INDEX_PATH = "kitty-ops/ops-index.jsonl"
OP_CLOSURES_FILENAME = "op-closures.jsonl"
OP_CLOSURES_RELATIVE_PATH = Path(EVENTS_DIR) / OP_CLOSURES_FILENAME


def op_closures_path(repo_root: Path) -> Path:
    """Absolute path of the append-only Op-closure spine under ``repo_root``."""
    return repo_root / OP_CLOSURES_RELATIVE_PATH


def append_op_closure(repo_root: Path, record: OpCompletedEvent) -> Path:
    """Append one closure record to the Op-closure spine; return the path written.

    The spine (``kitty-ops/op-closures.jsonl``) is the sanctioned durable
    surface for doctor-sweep closures (#4397): the sweep's targets are
    pre-existing ``kitty-ops/`` archive records, which are byte-frozen by the
    historical-preservation gate — so a sweep closure is recorded here, as a
    new append-only line, instead of appending a ``completed`` event to the
    per-record file. Append-only like every other spine: never rewrites or
    removes an existing line.
    """
    path = op_closures_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    InvocationWriter._append_line_no_follow(path, record.to_jsonl_line() + "\n")
    return path


def read_op_closures(repo_root: Path) -> list[OpCompletedEvent]:
    """Return all closure records in insertion order; ``[]`` when absent.

    Skips malformed lines rather than raising — a corrupt line surfaces as a
    doctor signal, same tolerance as ``lifecycle.read_lifecycle_records``.
    """
    path = op_closures_path(repo_root)
    if not path.exists():
        return []
    out: list[OpCompletedEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            event = parse_op_event(data)
        except (json.JSONDecodeError, ValueError, LegacyRecordError):
            continue
        if isinstance(event, OpCompletedEvent):
            out.append(event)
    return out


def closed_invocation_ids(repo_root: Path) -> set[str]:
    """Invocation ids already closed on the Op-closure spine."""
    return {event.invocation_id for event in read_op_closures(repo_root)}


def normalise_ref(ref: str, repo_root: Path) -> str:
    """Repo-relative when resolved path is under repo_root; absolute fallback.

    Note: ``Path(ref).resolve()`` follows symlinks. If the caller supplies a
    symlink that points outside the repository, the resolved target will be
    recorded as an absolute path. Operators supplying ``--artifact`` flags are
    responsible for knowing what their links resolve to; the invocation trail
    faithfully records the resolved target.

    See data-model.md §6.
    """
    try:
        path = Path(ref)
        candidate = path if path.is_absolute() else repo_root / path
        resolved = candidate.resolve()
    except (OSError, RuntimeError, ValueError):
        # ValueError can occur on paths with embedded null bytes (Python 3.14+)
        return ref
    root = repo_root.resolve()
    try:
        return str(resolved.relative_to(root))
    except ValueError:
        return str(resolved)


class InvocationWriter:
    """Append-only JSONL writer for per-invocation audit trail files.

    Append-only invariant:
    - ``write_started`` uses exclusive-create mode (``"x"``) — raises on ULID collision.
    - ``write_completed`` uses append mode (``"a"``).
    - No existing line is ever mutated.
    - The already-closed check prevents double-completion without mutating records.
    """

    def __init__(self, repo_root: Path) -> None:
        self._dir = repo_root / EVENTS_DIR

    def _ensure_dir(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)

    def invocation_path(self, invocation_id: str) -> Path:
        """Return the JSONL file path for a given invocation_id.

        Filename is invocation_id ONLY — no profile_id prefix.
        This allows profile-invocation complete to work with --invocation-id alone.
        """
        validated_id = validate_invocation_id(invocation_id)
        candidate = self._dir / f"{validated_id}.jsonl"
        ensure_within_any(candidate, roots=[self._dir])
        if candidate.is_symlink():
            raise ValueError(
                f"Invocation record must not be a symbolic link: {candidate}"
            )
        return candidate

    @contextlib.contextmanager
    def _validated_append_handle(
        self,
        path: Path,
        invocation_id: str,
    ) -> Iterator[TextIO]:
        """Open one existing trail inode and verify its started-event identity."""
        no_follow = getattr(os, "O_NOFOLLOW", 0)
        if no_follow == 0 and path.is_symlink():
            raise InvocationError(f"Refusing symbolic-link invocation record: {path}")
        try:
            fd = os.open(path, os.O_RDWR | os.O_APPEND | no_follow)
        except FileNotFoundError as exc:
            raise InvocationError(
                f"Invocation record not found: {invocation_id}"
            ) from exc
        except OSError as exc:
            raise InvocationWriteError(
                f"Failed to open invocation record safely: {exc}"
            ) from exc
        with os.fdopen(fd, "a+", encoding="utf-8") as handle:
            handle.seek(0)
            try:
                rows = [
                    json.loads(line)
                    for line in handle.read().splitlines()
                    if line.strip()
                ]
            except (json.JSONDecodeError, OSError) as exc:
                raise InvocationError(
                    f"Invocation record is unreadable: {invocation_id}"
                ) from exc
            if not rows or rows[0].get("event") != "started":
                raise InvocationError(
                    f"Invocation record has no started event: {invocation_id}"
                )
            embedded_id = rows[0].get("invocation_id")
            if embedded_id != invocation_id:
                raise InvocationError(
                    "Invocation record identity mismatch: "
                    f"requested={invocation_id!r}, embedded={embedded_id!r}"
                )
            yield handle

    @staticmethod
    def _append_line_no_follow(path: Path, line: str) -> None:
        """Append one line without following a pre-planted final symlink."""
        no_follow = getattr(os, "O_NOFOLLOW", 0)
        if no_follow == 0 and path.is_symlink():
            raise OSError(f"refusing symbolic link: {path}")
        fd = os.open(
            path,
            os.O_WRONLY | os.O_APPEND | os.O_CREAT | no_follow,
            0o600,
        )
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(line)

    def _append_to_index(self, record: OpStartedEvent) -> None:
        """Append a lightweight entry to the invocation index.

        The index at ``kitty-ops/ops-index.jsonl`` stores
        ``{invocation_id, profile_id, started_at}`` per line, newest last.
        It powers the O(limit) reverse-scan in ``invocations list`` so that
        command meets NFR-008 (< 200 ms at 10 K files).

        Errors are silenced — the index is a performance aid.  A missing or
        truncated index causes ``invocations list`` to fall back to directory
        scanning, which is correct but slower.
        """
        index_path = self._dir / "ops-index.jsonl"
        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            entry = json.dumps(
                {
                    "invocation_id": record.invocation_id,
                    "profile_id": record.profile_id,
                    "started_at": record.started_at,
                }
            )
            self._append_line_no_follow(index_path, entry + "\n")
        except OSError:
            pass  # index is a performance aid; silently degrade

    def write_started(self, record: OpStartedEvent) -> Path:
        """Write the ``started`` event. Returns the JSONL file path.

        Uses exclusive-create (``"x"`` mode) to detect ULID collision
        (extremely rare but deterministically safe).

        Also appends a lightweight entry to the invocation index at
        ``kitty-ops/ops-index.jsonl`` for fast reverse-scanning
        by ``spec-kitty invocations list``.
        """
        self._ensure_dir()
        path = self.invocation_path(record.invocation_id)
        try:
            # Use "x" mode (exclusive create) to detect ULID collision (extremely rare).
            # Optional fields (router_confidence, mission_id, wp_id, model_id)
            # are omitted when None.
            with path.open("x", encoding="utf-8") as f:
                f.write(record.to_jsonl_line() + "\n")
        except FileExistsError:
            raise InvocationWriteError(
                f"ULID collision on {path} — retry with a new invocation_id"
            )
        except OSError as e:
            raise InvocationWriteError(f"Failed to write invocation record: {e}") from e
        self._append_to_index(record)
        return path

    def write_completed(self, record: OpCompletedEvent) -> Path:
        """Append the ``completed`` event to an existing invocation file.

        Raises ``AlreadyClosedError`` if a completed event already exists (idempotent guard).
        Raises ``InvocationError`` if the invocation file is not found.
        Raises ``InvocationWriteError`` on filesystem failure.
        """
        path = self.invocation_path(record.invocation_id)
        try:
            with self._validated_append_handle(path, record.invocation_id) as handle:
                handle.seek(0)
                existing = [
                    json.loads(line)
                    for line in handle.read().splitlines()
                    if line.strip()
                ]
                if any(entry.get("event") == "completed" for entry in existing):
                    raise AlreadyClosedError(record.invocation_id)
                handle.write(record.to_jsonl_line() + "\n")
        except (AlreadyClosedError, InvocationError, InvocationWriteError):
            raise
        except OSError as e:
            raise InvocationWriteError(f"Failed to append completed event: {e}") from e
        return path

    def append_correlation_link(
        self,
        invocation_id: str,
        *,
        kind: str = "artifact",
        ref: str | None = None,
        sha: str | None = None,
        at: str | None = None,
    ) -> None:
        """Append an artifact_link or commit_link event to the invocation JSONL.

        Exactly one of ``ref`` or ``sha`` must be provided:
        - ``ref`` → ``{"event": "artifact_link", "kind": <kind>, "ref": <ref>, ...}``
        - ``sha`` → ``{"event": "commit_link", "sha": <sha>, ...}``

        Raises:
            InvocationError: if the invocation JSONL does not exist.
            ValueError: if neither or both of ref/sha are supplied.
            InvocationWriteError: on filesystem write failure.
        """
        if (ref is None) == (sha is None):
            raise ValueError("Exactly one of ref or sha must be provided")
        path = self.invocation_path(invocation_id)
        at_ts = at or now_utc_iso()
        entry: dict[str, object] = {
            "event": "artifact_link" if ref is not None else "commit_link",
            "invocation_id": invocation_id,
            "at": at_ts,
        }
        if ref is not None:
            entry["kind"] = kind
            entry["ref"] = ref
        else:
            entry["sha"] = sha
        try:
            with self._validated_append_handle(path, invocation_id) as handle:
                handle.write(json.dumps(entry) + "\n")
        except (InvocationError, InvocationWriteError):
            raise
        except OSError as e:
            raise InvocationWriteError(
                f"Failed to append correlation event: {e}"
            ) from e

    def write_glossary_observation(
        self, invocation_id: str, bundle: GlossaryObservationBundle
    ) -> None:
        """Append glossary_checked event to invocation file. Best-effort only.

        This event is ONLY written when ``all_conflicts`` is non-empty OR
        ``error_msg`` is set. Clean invocations (no conflicts, no error) produce
        NO ``glossary_checked`` line in the trail — keeping Tier 1 files minimal.

        Readers that encounter an unknown event type may safely skip this line.
        """
        # Skip clean invocations (no conflicts and no error)
        if not bundle.all_conflicts and bundle.error_msg is None:
            return
        try:
            path = self.invocation_path(invocation_id)
            entry: dict[str, object] = {
                "event": "glossary_checked",
                "invocation_id": invocation_id,
            }
            entry.update(bundle.to_dict())
            with self._validated_append_handle(path, invocation_id) as handle:
                handle.write(json.dumps(entry) + "\n")
        except (OSError, InvocationError, InvocationWriteError, ValueError):
            pass
