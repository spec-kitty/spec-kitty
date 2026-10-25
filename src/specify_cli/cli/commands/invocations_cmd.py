"""CLI command group: spec-kitty invocations.

Implements ``spec-kitty invocations list`` — the operator's view into the
local JSONL audit log produced by the profile-invocation writer.

## Performance design (NFR-008)

``invocations list`` must return 100 records in < 200 ms even when the audit
log directory contains 10 000 JSONL files.

Directory-scanning (one ``readline()`` per file) does not meet the threshold
on a cold filesystem cache with 10 K files.  Instead we maintain a lightweight
append-only index at ``kitty-ops/ops-index.jsonl``:

- Each line: ``{invocation_id, profile_id, started_at}``
- Written by ``InvocationWriter.write_started()`` immediately after the
  per-invocation file is created.
- ``_iter_records()`` reads the index *in reverse* (O(1) seek-to-end per
  block) to find the N most-recent matching entries, then opens only those
  individual files to determine ``open`` vs ``closed`` status.

Sort is by ``started_at`` from the index content (not filesystem mtime) to
guarantee correct temporal ordering.

Profile filtering reads ``profile_id`` from the index line, not from the
filename, because filenames are plain ``<invocation_id>.jsonl``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import typer
from specify_cli.cli.console import console
from specify_cli.cli.console import err_console as _console_err
from rich.table import Table

from specify_cli.invocation.errors import LegacyRecordError
from specify_cli.invocation.record import OpCompletedEvent, OpStartedEvent, parse_op_event
from specify_cli.invocation.op_custody import resolve_op_record_root
from specify_cli.invocation.writer import EVENTS_DIR, INDEX_PATH
from specify_cli.task_utils import find_repo_root

app = typer.Typer(name="invocations", help="Query local invocation records.")

# Read this many bytes at a time from the end of the index when scanning in
# reverse.  4 KiB covers ~30-60 typical index lines per read, keeping I/O
# calls low even for large filters.
_CHUNK_SIZE = 4096


def _get_repo_root() -> Path:
    """Resolve the repository root using the project's canonical utility."""
    result: Path = find_repo_root()
    return result


def _read_first_line(path: Path) -> dict | None:  # type: ignore[type-arg]
    """Read the first JSONL line (the ``started`` event) from *path*.

    Returns a parsed dict or ``None`` on any error / empty file.
    """
    try:
        with path.open("r", encoding="utf-8") as f:
            line = f.readline().strip()
            return json.loads(line) if line else None
    except (OSError, json.JSONDecodeError):
        return None


def _read_last_line(path: Path) -> dict | None:  # type: ignore[type-arg]
    """Read the last non-empty JSONL line from *path* using an O(1) seek-to-end.

    Reads at most 4 KiB from the end of the file to locate the last line —
    sufficient for any realistic completed-event payload.  Returns ``None`` on
    any error or empty file.
    """
    try:
        with path.open("rb") as f:
            f.seek(0, 2)  # seek to end
            size = f.tell()
            if size == 0:
                return None
            # Read up to 4 KiB from the end to find the last non-empty line.
            f.seek(max(0, size - 4096))
            tail = f.read().decode("utf-8", errors="replace")
        lines = [ln.strip() for ln in tail.splitlines() if ln.strip()]
        if not lines:
            return None
        data = json.loads(lines[-1])
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _read_completed_record(path: Path, invocation_id: str) -> dict | None:  # type: ignore[type-arg]
    """Return the first completed event for *invocation_id*, wherever it appears."""
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict) and data.get("event") == "completed" and data.get("invocation_id") == invocation_id:
                    return data
    except OSError:
        return None
    return None


def _parse_started(data: dict, legacy_ids: list[str] | None) -> OpStartedEvent | None:  # type: ignore[type-arg]
    """Parse a started dict as a v2 event; record legacy lines for a later warning."""
    try:
        event = parse_op_event(data)
    except LegacyRecordError as exc:
        if legacy_ids is not None:
            legacy_ids.append(exc.invocation_id or "?")
        return None
    except ValueError:
        return None
    return event if isinstance(event, OpStartedEvent) else None


def _parse_completed(data: dict, legacy_ids: list[str] | None) -> OpCompletedEvent | None:  # type: ignore[type-arg]
    """Parse a completed dict as a v2 event; record legacy lines for a later warning."""
    try:
        event = parse_op_event(data)
    except LegacyRecordError as exc:
        if legacy_ids is not None:
            legacy_ids.append(exc.invocation_id or "?")
        return None
    except ValueError:
        return None
    return event if isinstance(event, OpCompletedEvent) else None


def _warn_legacy(legacy_ids: list[str]) -> None:
    """Emit a single warning for any legacy (pre-v2) records that were skipped."""
    if legacy_ids:
        _console_err.print(
            f"[yellow]Warning:[/yellow] skipped {len(legacy_ids)} legacy Op record(s) (pre-v2 schema). Run 'spec-kitty upgrade' to migrate kitty-ops records."
        )


def _iter_index_reverse(index_path: Path) -> Iterator[dict]:  # type: ignore[type-arg]
    """Yield index entries newest-first by reading the file in reverse chunks.

    Implements a backward-scanning approach:
    1. Seek to end of file.
    2. Read *_CHUNK_SIZE* bytes at a time going backward.
    3. Split into lines, parse each as JSON, yield in reverse order.

    This avoids loading the entire index into memory.
    """
    try:
        with index_path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            if size == 0:
                return

            remainder = b""
            pos = size
            while pos > 0:
                read_size = min(_CHUNK_SIZE, pos)
                pos -= read_size
                f.seek(pos)
                chunk = f.read(read_size) + remainder

                # Split on newlines; the last fragment (at pos=0 boundary)
                # becomes the new remainder to prepend to the next chunk.
                parts = chunk.split(b"\n")
                remainder = parts[0]
                # Yield complete lines (parts[1:]) in reverse order.
                for raw_line in reversed(parts[1:]):
                    line = raw_line.strip()
                    if line:
                        try:
                            yield json.loads(line.decode("utf-8", errors="replace"))
                        except json.JSONDecodeError:
                            continue  # skip corrupted lines

            # Flush whatever remained at the very beginning of the file.
            if remainder.strip():
                try:
                    yield json.loads(remainder.strip().decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    pass

    except OSError:
        return


def _iter_records_from_index(
    events_dir: Path,
    index_path: Path,
    profile_filter: str | None,
    limit: int,
    legacy_ids: list[str] | None = None,
) -> Iterator[dict]:  # type: ignore[type-arg]
    """Yield invocation records using the index for O(N) scanning instead of O(N*disk).

    For each matching index entry (newest first) open only the per-invocation
    file to determine ``open`` / ``closed`` status.

    Args:
        events_dir: ``kitty-ops/``
        index_path: ``kitty-ops/ops-index.jsonl``
        profile_filter: If set, only yield records whose ``profile_id`` matches.
        limit: Maximum number of records to yield.
    """
    count = 0
    seen: set[str] = set()  # de-duplicate (index may have repeated entries on edge cases)
    for entry in _iter_index_reverse(index_path):
        if count >= limit:
            break
        inv_id = entry.get("invocation_id", "")
        if not inv_id or inv_id in seen:
            continue
        seen.add(inv_id)
        if profile_filter and entry.get("profile_id") != profile_filter:
            continue
        # Determine open / closed by checking the per-invocation file.
        inv_file = events_dir / f"{inv_id}.jsonl"
        record: dict = dict(entry)  # type: ignore[type-arg]
        if not _apply_completion_status(record, inv_file, inv_id, legacy_ids):
            continue  # legacy line → warn-and-skip (see _warn_legacy)
        # Also read full started record to get 'action' field (not stored in index).
        started_raw = _read_first_line(inv_file)
        if started_raw is None:
            continue  # stale/dangling index row; canonical per-op file is gone/unreadable
        started = _parse_started(started_raw, legacy_ids)
        if started is None:
            continue  # legacy line → warn-and-skip (see _warn_legacy)
        record.setdefault("action", started.action)
        record.setdefault("event", started.event)
        yield record
        count += 1


def _apply_completion_status(
    record: dict,  # type: ignore[type-arg]
    inv_file: Path,
    inv_id: str,
    legacy_ids: list[str] | None,
) -> bool:
    """Enrich *record* with completed/open status from *inv_file*.

    Returns ``False`` when the completion line is a legacy record that must be
    warn-and-skipped (see ``_warn_legacy``); ``True`` otherwise.
    """
    completed_raw = _read_completed_record(inv_file, inv_id)
    if completed_raw is None:
        record["status"] = "open"
        return True
    completed = _parse_completed(completed_raw, legacy_ids)
    if completed is None:
        return False  # legacy line → warn-and-skip (see _warn_legacy)
    record["completed_at"] = completed.completed_at
    record["outcome"] = completed.outcome
    record["closed_by"] = completed.closed_by
    record["evidence_ref"] = completed.evidence_ref
    record["status"] = "closed"
    return True


def _iter_records_from_dir(
    events_dir: Path,
    profile_filter: str | None,
    limit: int,
    legacy_ids: list[str] | None = None,
) -> Iterator[dict]:  # type: ignore[type-arg]
    """Fallback: yield records by scanning the directory.

    Used when the index does not exist (e.g. projects that predate index
    writing, or after a manual purge of the index file).

    Sort is by ``started_at`` from content (not mtime).

    Args:
        events_dir: ``kitty-ops/``
        profile_filter: If set, only yield records whose ``profile_id`` matches.
        limit: Maximum number of records to yield.
    """
    if not events_dir.exists():
        return

    raw_records: list[dict] = []  # type: ignore[type-arg]
    for path in events_dir.glob("*.jsonl"):
        started_raw = _read_first_line(path)
        if started_raw is None:
            continue
        if profile_filter and started_raw.get("profile_id") != profile_filter:
            continue
        started = _parse_started(started_raw, legacy_ids)
        if started is None:
            continue  # legacy line → warn-and-skip (see _warn_legacy)
        record: dict = started.model_dump(exclude_none=True)  # type: ignore[type-arg]
        inv_id = started.invocation_id
        if not _apply_completion_status(record, path, inv_id, legacy_ids):
            continue  # legacy line → warn-and-skip (see _warn_legacy)
        raw_records.append(record)

    raw_records.sort(key=lambda r: r.get("started_at", ""), reverse=True)

    count = 0
    for record in raw_records:
        if count >= limit:
            break
        yield record
        count += 1


def _iter_records(
    events_dir: Path,
    profile_filter: str | None,
    limit: int,
    *,
    repo_root: Path | None = None,
    legacy_ids: list[str] | None = None,
) -> Iterator[dict]:  # type: ignore[type-arg]
    """Yield invocation record dicts, newest first.

    Uses the index when available for O(limit) performance at 10 K+ files.
    Falls back to directory scanning when the index is absent.

    Args:
        events_dir: Path to ``kitty-ops/``.
        profile_filter: If set, only yield records whose ``profile_id`` matches.
        limit: Maximum number of records to yield.
        repo_root: Optional repo root for index path resolution.  When
            omitted the index path is computed relative to ``events_dir``.
    """
    if repo_root is not None:
        index_path = repo_root / INDEX_PATH
    else:
        index_path = events_dir / "ops-index.jsonl"

    if index_path.exists():
        yield from _iter_records_from_index(events_dir, index_path, profile_filter, limit, legacy_ids)
    else:
        yield from _iter_records_from_dir(events_dir, profile_filter, limit, legacy_ids)


@app.command("list")
def list_invocations(
    profile: str | None = typer.Option(None, "--profile", "-p", help="Filter by profile ID (reads file content, not filename)"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number of records to return (default: 20)"),
    json_output: bool = typer.Option(False, "--json", help="Emit a JSON array instead of a table"),
) -> None:
    """List recent invocation records from the local audit log.

    # FR-008 / T031: This command does not open an InvocationRecord at baseline.
    # If a future version of `invocations list` opens an invocation, it should use:
    #   derive_mode("invocations.list")  -> ModeOfWork.QUERY
    # The mapping is reserved in _ENTRY_COMMAND_MODE (modes.py) for enforcement
    # consistency (QUERY mode disallows Tier 2 evidence promotion per FR-009).
    # TODO(future): wire derive_mode("invocations.list") when InvocationRecord is opened here.

    Records are returned newest-first, sorted by ``started_at`` from file
    content.  Use ``--profile`` to narrow to one agent profile.  Use
    ``--json`` for machine-readable output.
    """
    # #6564: list the Op records of the checkout the command runs in, the
    # same checkout ``dispatch`` and ``profile-invocation complete`` write to.
    repo_root = resolve_op_record_root(_get_repo_root())
    events_dir = repo_root / EVENTS_DIR
    legacy_ids: list[str] = []
    records = list(_iter_records(events_dir, profile, limit, repo_root=repo_root, legacy_ids=legacy_ids))

    if json_output:
        _warn_legacy(legacy_ids)
        typer.echo(json.dumps(records, indent=2))
        return

    _warn_legacy(legacy_ids)
    if not records:
        console.print("[dim]No invocation records found.[/dim]")
        return

    table = Table(title="Recent Invocations")
    table.add_column("Invocation ID", style="dim")
    table.add_column("Profile")
    table.add_column("Action")
    table.add_column("Status")
    table.add_column("Outcome")
    table.add_column("Closed By")
    table.add_column("Started At")
    for r in records:
        status_style = "green" if r.get("status") == "closed" else "yellow"
        inv_id = r.get("invocation_id", "?")
        short_id = inv_id[:12] + "…" if len(inv_id) > 12 else inv_id
        table.add_row(
            short_id,
            r.get("profile_id", "?"),
            r.get("action", "?"),
            f"[{status_style}]{r.get('status', '?')}[/{status_style}]",
            r.get("outcome") or "-",
            r.get("closed_by") or "-",
            (r.get("started_at") or "?")[:19],
        )
    console.print(table)
