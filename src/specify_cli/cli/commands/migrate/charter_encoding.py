"""Charter-content encoding migration subcommand.

``spec-kitty migrate charter-encoding`` walks every existing mission's charter
content (``kitty-specs/*/charter/*.{yaml,md,txt}`` and
``.kittify/charter/*.{yaml,md,txt}``), detects the encoding of each file via
the canonical chokepoint (``charter.activation._io.load_charter_file``, which
itself delegates to ``charter.encoding_recovery.recover``), and either:

- Skips the file (already pure UTF-8; idempotency pre-check passes).
- Normalizes the file to UTF-8 in-place with a provenance record, backing up
  the exact original bytes to a ``<name>.bak`` sibling first.
- Surfaces the file as ambiguous (exits non-zero; manual repair required).
- Refuses a file whose ``.bak`` sibling already exists (backup collision;
  exits non-zero; never silently overwrites an existing backup).

Implements: FR-026, FR-027, NFR-006 (idempotency).

Interactive mode (default):   prompt before each non-UTF-8 file.
``--dry-run``:                 show what would change; write nothing.
``--yes``/``-y``:              normalize without prompting; exit non-zero on
                               any ambiguous file (CI-safe).
``--json``:                    emit a JSON-stable summary on stdout at the end.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import typer

from specify_cli.cli.console import console as _console
from specify_cli.cli.console import err_console as _err_console
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.utils import safe_is_dir

if TYPE_CHECKING:
    from charter.activation._io import CharterContent

# ---------------------------------------------------------------------------
# Corpus patterns (FR-026 / research.md R-9)
# ---------------------------------------------------------------------------

_MISSION_CHARTER_GLOB = "kitty-specs/*/charter/*.{yaml,md,txt}"
_GLOBAL_CHARTER_GLOB = ".kittify/charter/*.{yaml,md,txt}"

_CHARTER_EXTENSIONS = (".yaml", ".md", ".txt")

#: Backup sibling suffix (data-model.md "Backup artifact"). Never silently
#: overwritten -- a pre-existing backup blocks normalization of that file
#: (see :class:`_BackupCollisionError`).
_BACKUP_SUFFIX = ".bak"


# ---------------------------------------------------------------------------
# Internal data model
# ---------------------------------------------------------------------------


@dataclass
class _FileRecord:
    """Per-file result produced by the corpus scan."""

    path: Path
    # "already-utf8" | "normalized" | "ambiguous" | "backup_collision"
    # | "dry-run-would-normalize" | "dry-run-would-collide"
    action: str
    encoding: str | None = None
    confidence: float | None = None
    diagnostic_body: str | None = None


@dataclass
class _ScanSummary:
    """Aggregated result after scanning the full corpus."""

    files_inspected: int = 0
    already_utf8: list[Path] = field(default_factory=list)
    normalized: list[_FileRecord] = field(default_factory=list)
    ambiguous: list[_FileRecord] = field(default_factory=list)
    collisions: list[_FileRecord] = field(default_factory=list)
    dry_run: bool = False

    @property
    def result(self) -> str:
        if self.ambiguous:
            return "ambiguous_present"
        if self.collisions:
            return "backup_collision_present"
        return "success"


# ---------------------------------------------------------------------------
# Idempotency pre-check (NFR-006)
# ---------------------------------------------------------------------------


def _is_pure_utf8(path: Path) -> bool:
    """Return True if the file bytes decode cleanly as strict UTF-8.

    This cheap pre-check is the idempotency guard: already-UTF-8 files are
    skipped without invoking the chokepoint, so no new provenance records are
    written on a second run.
    """
    try:
        path.read_bytes().decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


# ---------------------------------------------------------------------------
# Corpus inventory
# ---------------------------------------------------------------------------


def _collect_charter_files(project_root: Path) -> list[Path]:
    """Return all charter files matching the corpus patterns.

    Scans:
    - ``kitty-specs/*/charter/*.{yaml,md,txt}``
    - ``.kittify/charter/*.{yaml,md,txt}``
    """
    files: list[Path] = []

    mission_specs = project_root / KITTY_SPECS_DIR
    if safe_is_dir(mission_specs):
        for mission_dir in sorted(mission_specs.iterdir()):
            if not safe_is_dir(mission_dir):
                continue
            charter_dir = mission_dir / "charter"
            if safe_is_dir(charter_dir):
                for ext in _CHARTER_EXTENSIONS:
                    files.extend(sorted(charter_dir.glob(f"*{ext}")))

    global_charter = project_root / ".kittify" / "charter"
    if safe_is_dir(global_charter):
        for ext in _CHARTER_EXTENSIONS:
            files.extend(sorted(global_charter.glob(f"*{ext}")))

    return files


# ---------------------------------------------------------------------------
# Backup + atomic in-place rewrite (data-model.md "Backup artifact")
# ---------------------------------------------------------------------------


class _BackupCollisionError(Exception):
    """Raised when a ``.bak`` sibling already exists for a file about to be
    normalized.

    Collision behaviour is defined: the existing backup is NEVER silently
    overwritten. The caller must surface this as a refusal, leaving both the
    stale backup and the (still non-UTF-8) original file untouched.
    """


def _backup_path_for(path: Path) -> Path:
    return path.with_name(path.name + _BACKUP_SUFFIX)


def _write_normalized_with_backup(path: Path, content: str, original_bytes: bytes) -> None:
    """Back up ``original_bytes`` to ``<path>.bak``, then atomically replace
    ``path`` with ``content`` (UTF-8).

    Mirrors the temp-file + ``Path.replace`` rename-based swap idiom used by
    ``backfill_provenance.py::_CorpusWriteTransaction.write`` -- the backup
    is written to disk (rather than kept only in memory) so operators can
    recover the exact original bytes after the fact.

    Raises:
        _BackupCollisionError: a ``.bak`` sibling already exists.
    """
    backup_path = _backup_path_for(path)
    if backup_path.exists():
        raise _BackupCollisionError(str(backup_path))

    tmp_path = path.with_name(f"{path.name}.tmp-{uuid4().hex}")
    tmp_path.write_text(content, encoding="utf-8")
    backup_path.write_bytes(original_bytes)
    tmp_path.replace(path)


# ---------------------------------------------------------------------------
# Interactive prompting helpers
# ---------------------------------------------------------------------------


def _prompt_for_file(record_path: Path, detected: str, confidence: float) -> str:
    """Prompt the operator for a single file.  Returns 'y', 'n', or 'a' (yes-all)."""
    _console.print(
        f"\n[bold]File:[/bold] {record_path}\n"
        f"[bold]Detected:[/bold] {detected} (confidence {confidence:.2f})\n"
        "[bold]Action:[/bold] normalize to UTF-8 with provenance record?"
    )
    response = typer.prompt("  [y/N/a (yes-all)]", default="N").strip().lower()
    return response if response in ("y", "n", "a") else "n"


# ---------------------------------------------------------------------------
# Main command entrypoint (registered via migrate_cmd.py)
# ---------------------------------------------------------------------------


def _detect_or_record_ambiguous(path: Path, summary: _ScanSummary) -> CharterContent | None:
    """Run the chokepoint; on ambiguity, record + report and return ``None``.

    Isolated from the main loop to keep ``run_charter_encoding_migration``'s
    cyclomatic complexity within the repository ceiling (15).
    """
    from charter.activation._io import CharterEncodingError, load_charter_file  # noqa: PLC0415

    try:
        content = load_charter_file(path, unsafe=False)
    except CharterEncodingError as exc:
        record = _FileRecord(path=path, action="ambiguous", diagnostic_body=exc.body)
        summary.ambiguous.append(record)
        # Always route to stderr (visible in both human and JSON modes).
        _err_console.print(f"[red]AMBIGUOUS:[/red] {path}")
        _err_console.print(f"  {exc.body.splitlines()[0] if exc.body else ''}")
        return None
    return content


def _record_dry_run_verdict(
    path: Path,
    content: CharterContent,
    *,
    collision: bool,
    json_output: bool,
    summary: _ScanSummary,
) -> None:
    """Record the dry-run verdict for one file.

    Per ``contracts/cli-behaviour-contract.md``: dry-run reports the
    IDENTICAL detected page, honest confidence, and accept/refuse verdict
    (including a would-be backup collision) that the real run would
    produce -- no separate preview decode.
    """
    detected, confidence = content.source_encoding, content.confidence
    if collision:
        record = _FileRecord(
            path=path,
            action="dry-run-would-collide",
            encoding=detected,
            confidence=confidence,
        )
        summary.collisions.append(record)
        if not json_output:
            _console.print(f"[red]would refuse (backup collision)[/red] {path} -> {_backup_path_for(path)}")
        return

    record = _FileRecord(
        path=path,
        action="dry-run-would-normalize",
        encoding=detected,
        confidence=confidence,
    )
    summary.normalized.append(record)
    if not json_output:
        _console.print(f"[yellow]would normalize[/yellow] {path} ({detected}, confidence {confidence:.2f})")


def _record_backup_collision(path: Path, content: CharterContent, summary: _ScanSummary) -> None:
    """Refuse to normalize ``path``: an existing ``.bak`` sibling would be
    silently overwritten (data-model.md "Backup artifact" collision rule)."""
    backup_path = _backup_path_for(path)
    record = _FileRecord(
        path=path,
        action="backup_collision",
        encoding=content.source_encoding,
        confidence=content.confidence,
        diagnostic_body=(
            f"Refusing to normalize {path}: a backup already exists at {backup_path} "
            "and would be silently overwritten. Remove or rename the existing "
            "backup, then re-run."
        ),
    )
    summary.collisions.append(record)
    _err_console.print(f"[red]BACKUP COLLISION:[/red] {path}")
    _err_console.print(f"  a backup already exists: {backup_path}")


def _apply_normalization(
    path: Path,
    content: CharterContent,
    summary: _ScanSummary,
    *,
    json_output: bool,
) -> None:
    """Back up the original bytes and rewrite ``path`` as UTF-8 in-place.

    Provenance for the detection itself was already written by the
    chokepoint as a side effect of :func:`_detect_or_record_ambiguous`.
    """
    original_bytes = path.read_bytes()
    _write_normalized_with_backup(path, content.text, original_bytes)
    record = _FileRecord(
        path=path,
        action="normalized",
        encoding=content.source_encoding,
        confidence=content.confidence,
    )
    summary.normalized.append(record)
    if not json_output:
        _console.print(f"  [green]normalized[/green] {path} ({content.source_encoding} → utf-8, confidence {content.confidence:.2f})")


def run_charter_encoding_migration(
    *,
    project_root: Path,
    dry_run: bool,
    yes: bool,
    json_output: bool,
) -> int:
    """Execute the charter-encoding migration.

    Returns the intended process exit code (0 = success, non-zero = ambiguous
    or backup-collision files present).  The caller (typer command) calls
    ``raise typer.Exit(code)`` after this function returns.

    When ``json_output=True`` all human-readable progress messages are
    suppressed so that stdout carries only the final JSON payload.  Errors
    and ambiguity diagnostics are always routed to stderr.
    """
    files = _collect_charter_files(project_root)

    summary = _ScanSummary(dry_run=dry_run)
    summary.files_inspected = len(files)

    yes_all = yes  # whether we skip all remaining prompts

    for path in files:
        # NFR-006: idempotency pre-check before hitting the chokepoint.
        if _is_pure_utf8(path):
            summary.already_utf8.append(path)
            continue

        content = _detect_or_record_ambiguous(path, summary)
        if content is None:
            continue

        collision = _backup_path_for(path).exists()

        if dry_run:
            _record_dry_run_verdict(path, content, collision=collision, json_output=json_output, summary=summary)
            continue

        if collision:
            _record_backup_collision(path, content, summary)
            continue

        if not yes_all and not yes:
            # Interactive mode: ask operator.
            response = _prompt_for_file(path, content.source_encoding, content.confidence)
            if response == "a":
                yes_all = True
            elif response != "y":
                if not json_output:
                    _console.print(f"  [dim]skipped: {path}[/dim]")
                summary.already_utf8.append(path)  # treat as skipped / already-handled
                continue

        _apply_normalization(path, content, summary, json_output=json_output)

    # Emit summary: JSON to stdout (machine-readable), or human text to console.
    if json_output:
        _emit_json_summary(summary)
    else:
        _emit_human_summary(summary)

    # Exit non-zero if any ambiguous or backup-collision files remain
    # (FR-027, --yes CI contract).
    return 1 if (summary.ambiguous or summary.collisions) else 0


# ---------------------------------------------------------------------------
# Summary renderers
# ---------------------------------------------------------------------------


def _emit_json_summary(summary: _ScanSummary) -> None:
    """Print a JSON-stable summary to stdout (FR-027)."""
    payload = {
        "result": summary.result,
        "files_inspected": summary.files_inspected,
        "already_utf8": [str(p) for p in summary.already_utf8],
        "normalized": [
            {
                "path": str(r.path),
                "encoding": r.encoding,
                "confidence": r.confidence,
            }
            for r in summary.normalized
        ],
        "ambiguous": [
            {
                "path": str(r.path),
                "diagnostic_body": r.diagnostic_body,
            }
            for r in summary.ambiguous
        ],
        "backup_collisions": [
            {
                "path": str(r.path),
                "diagnostic_body": r.diagnostic_body,
            }
            for r in summary.collisions
        ],
        "dry_run": summary.dry_run,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def _emit_human_summary(summary: _ScanSummary) -> None:
    """Print a human-readable summary to the console."""
    prefix = "[dim](dry-run)[/dim] " if summary.dry_run else ""
    _console.print(f"\n{prefix}[bold]charter-encoding migration summary[/bold]")
    _console.print(f"  Files inspected  : {summary.files_inspected}")
    _console.print(f"  Already UTF-8    : {len(summary.already_utf8)}")
    _console.print(f"  Normalized       : {len(summary.normalized)}" + (" (would normalize)" if summary.dry_run else ""))
    if summary.ambiguous:
        _console.print(f"  [red]Ambiguous        : {len(summary.ambiguous)} (manual repair required)[/red]")
        for rec in summary.ambiguous:
            _console.print(f"    [red]{rec.path}[/red]")
    else:
        _console.print("  [green]Ambiguous        : 0[/green]")

    if summary.collisions:
        _console.print(f"  [red]Backup collisions: {len(summary.collisions)} (manual repair required)[/red]")
        for rec in summary.collisions:
            _console.print(f"    [red]{rec.path}[/red]")
    else:
        _console.print("  [green]Backup collisions: 0[/green]")

    if summary.dry_run:
        _console.print("\n[dim]Dry run — no files were modified.[/dim]")
    elif not summary.ambiguous and not summary.collisions:
        _console.print("\n[green]Done.[/green] Charter corpus is UTF-8 compliant.")
