"""Mission brief file management for intake flows.

Provides two local artefacts written by ``spec-kitty intake``:

* ``.kittify/mission-brief.md``  — plan document with provenance header for the LLM
* ``.kittify/brief-source.yaml`` — SHA-256 fingerprint + metadata for traceability

Neither file should be committed to version control; both are gitignored.

Security-critical helpers (provenance escaping, atomic writes) live in the
``specify_cli.intake`` package; this module is the operator-facing surface
that composes them.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from kernel.clock import now_utc_iso
from specify_cli.asset_preservation import guard_destructive_overwrite
from specify_cli.intake.brief_writer import write_brief_atomic
from specify_cli.intake.errors import (
    IntakeFileMissingError,
    IntakeFileUnreadableError,
)
from specify_cli.intake.provenance import escape_for_comment
from specify_cli.intake.scanner import load_allow_cross_fs


MISSION_BRIEF_FILENAME = "mission-brief.md"
BRIEF_SOURCE_FILENAME = "brief-source.yaml"


class BriefExistsError(Exception):
    """Raised by :func:`write_mission_brief` when a brief is already present
    and the caller did not authorize an overwrite (``overwrite=False``).

    Carries the operator-facing ``--force`` message as a class attribute so
    every caller (the ``--auto`` and explicit-path/stdin CLI adapters alike)
    reuses one string instead of duplicating it (Sonar S1192).
    """

    FORCE_MESSAGE: str = f"Brief already exists at .kittify/{MISSION_BRIEF_FILENAME}. Use --force to overwrite."

    def __init__(self, brief_path: Path) -> None:
        super().__init__(self.FORCE_MESSAGE)
        self.brief_path = brief_path


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


def write_mission_brief(
    repo_root: Path,
    content: str,
    source_file: str,
    *,
    source_agent: str | None = None,
    packet_meta: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    """Write ``.kittify/mission-brief.md`` and ``.kittify/brief-source.yaml``.

    The brief file is prefixed with two HTML comment lines that record
    provenance, followed by a blank line, then the original content.
    The YAML sidecar captures the source path, ingestion timestamp, and
    SHA-256 hash of the *raw* content (before the header is prepended).

    Args:
        repo_root: Project root directory.
        content: Raw plan document content.
        source_file: Human-readable source path or label (e.g. ``"stdin"``).
        source_agent: Optional harness/agent identifier (e.g. ``"opencode"``).
            When ``None``, the ``source_agent`` key is omitted from
            ``brief-source.yaml`` entirely (no null written).
        overwrite: Authorizes replacing an existing brief. This is the single
            chokepoint (#4921) for the overwrite invariant: the refusal below
            is keyed on ``brief_path.exists()`` ALONE — a brief present with
            no provenance sidecar is unknown provenance and refuses just the
            same as a "complete" brief+sidecar pair (#4910) — and is evaluated
            BEFORE the XOR partial-state cleanup so a brief-only file is never
            unlinked-then-rewritten.

    Returns a tuple of ``(brief_path, source_path)``.

    Raises:
        BriefExistsError: A brief already exists and ``overwrite`` is
            ``False``.
    """
    kittify = repo_root / ".kittify"
    kittify.mkdir(exist_ok=True)
    brief_path = kittify / MISSION_BRIEF_FILENAME
    source_path = kittify / BRIEF_SOURCE_FILENAME

    # Existence-alone gate (#4910/#4921), evaluated BEFORE the XOR cleanup
    # below: a brief-only file (sidecar absent) must refuse, not be unlinked
    # and silently rewritten. guard_destructive_overwrite stays pure here —
    # no prover, no backup_parent — so a refusal never touches the filesystem.
    if brief_path.exists() and not overwrite:
        verdict = guard_destructive_overwrite(
            brief_path,
            repo_root,
            replacement_substantive=True,
            authorized=overwrite,
        )
        if not verdict.proceed:
            raise BriefExistsError(brief_path)

    # Clean any partial state from a previous interrupted write.
    if brief_path.exists() != source_path.exists():
        brief_path.unlink(missing_ok=True)
        source_path.unlink(missing_ok=True)

    brief_hash = hashlib.sha256(content.encode()).hexdigest()  # noqa: TID251 - production raw SHA-256 owner
    ingested_at = now_utc_iso()

    # WP02 T007: provenance strings come from operator-controlled file
    # paths and must be escaped before they land in markdown comments
    # or the YAML sidecar.  ``escape_for_comment`` strips control
    # characters, neutralises ``-->`` / ``*/`` / leading ``#``, and
    # clips to MAX_PROVENANCE_BYTES.
    safe_source_file = escape_for_comment(source_file)
    safe_source_agent = escape_for_comment(source_agent) if source_agent else None

    header = (
        f"<!-- spec-kitty intake: ingested from {safe_source_file} at {ingested_at} -->\n"
        f"<!-- brief_hash: {brief_hash} -->"
    )
    brief_text = header + "\n\n" + content

    source_data: dict[str, Any] = {
        # The cleaned form is what the YAML sidecar records.  Storing the
        # cleaned value (rather than the raw input) keeps the SHA-256 hash
        # the source of truth for the *content* and the YAML the source of
        # truth for *provenance metadata*.
        "source_file": safe_source_file,
        "ingested_at": ingested_at,
        "brief_hash": brief_hash,
    }
    if safe_source_agent is not None:
        source_data["source_agent"] = safe_source_agent
    if packet_meta:
        source_data.update(packet_meta)

    # WP02 T010: atomic write via open + fsync + replace.  Cross-fs
    # writes are rejected unless explicitly allowed in config.yaml.
    allow_cross_fs = load_allow_cross_fs(repo_root)
    source_yaml = yaml.safe_dump(source_data, default_flow_style=False)
    write_brief_atomic(
        scanner_root=repo_root,
        writer_root=repo_root,
        brief_path=brief_path,
        brief_text=brief_text,
        source_path=source_path,
        source_yaml=source_yaml,
        allow_cross_fs=allow_cross_fs,
    )

    return brief_path, source_path


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


def read_mission_brief(repo_root: Path) -> str | None:
    """Return the full contents of ``.kittify/mission-brief.md``.

    Returns ``None`` when the file does not exist (legitimate "no brief").
    Raises :class:`IntakeFileUnreadableError` when the file exists but
    cannot be read or decoded — distinguishing a corrupt brief from a
    missing one (FR-011). Callers that explicitly want lenient behavior
    must catch the exception themselves.
    """
    path = repo_root / ".kittify" / MISSION_BRIEF_FILENAME
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise IntakeFileUnreadableError(path=path, cause=exc) from exc
    except UnicodeDecodeError as exc:
        raise IntakeFileUnreadableError(path=path, cause=exc) from exc


def read_brief_source(repo_root: Path) -> dict[str, Any] | None:
    """Return parsed YAML from ``.kittify/brief-source.yaml``.

    Returns ``None`` when the file does not exist (legitimate "no brief"),
    OR when the file parses cleanly but its companion ``brief.md`` is
    absent (the kill-mid-write window — see pair-atomicity rule below).

    Raises :class:`IntakeFileUnreadableError` when the file exists but is
    unreadable, undecodable, or contains non-mapping YAML — distinguishing
    a corrupt provenance sidecar from a missing one (FR-011). Corrupt
    state ALWAYS surfaces, regardless of brief presence, so operators
    learn about the corruption rather than seeing a silent "no brief".

    Pair-atomicity rule (kill-mid-write recovery): the brief writer
    renames ``source.yaml`` first, then ``brief.md`` as the commit
    marker. If a kill happens between the two renames, ``source.yaml``
    can be on disk while ``brief.md`` is not. After we have proven the
    sidecar parses cleanly (so we are not hiding corruption), we treat
    that orphan state as "no brief" so callers see the same surface as
    if the write never started. The legacy recovery branch in
    :func:`write_mission_brief` unlinks the orphan on the next write.
    """
    path = repo_root / ".kittify" / BRIEF_SOURCE_FILENAME
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise IntakeFileUnreadableError(path=path, cause=exc) from exc
    except UnicodeDecodeError as exc:
        raise IntakeFileUnreadableError(path=path, cause=exc) from exc

    try:
        result = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise IntakeFileUnreadableError(path=path, cause=exc) from exc

    if result is None:
        # Empty file is treated as a missing-but-not-corrupt sidecar; the
        # CLI surface still distinguishes None vs an unreadable raise.
        return None
    if not isinstance(result, dict):
        raise IntakeFileUnreadableError(
            path=path,
            cause=ValueError(
                f"brief-source.yaml must contain a YAML mapping; "
                f"got {type(result).__name__}"
            ),
        )

    # Pair-atomicity rule (P2.5): the writer renames source.yaml first
    # and brief.md second as the commit marker. If brief.md is absent,
    # the operation either never started or was killed between the two
    # renames — treat as "no brief". Corrupt-sidecar errors above always
    # surface first, so operators still learn about real corruption.
    brief_path = repo_root / ".kittify" / MISSION_BRIEF_FILENAME
    if not brief_path.exists():
        return None

    return result


# Re-export the structured error so callers don't need to know which
# subpackage owns it. Surfaces FR-011 at this module's import layer.
__all__ = [  # noqa: PLE0604 — module-level export contract
    "BriefExistsError",
    "IntakeFileMissingError",
    "IntakeFileUnreadableError",
    "clear_mission_brief",
    "read_brief_source",
    "read_mission_brief",
    "write_mission_brief",
]


# ---------------------------------------------------------------------------
# Clear helper
# ---------------------------------------------------------------------------


def clear_mission_brief(repo_root: Path) -> None:
    """Remove both brief artefacts if they exist (idempotent)."""
    for filename in (MISSION_BRIEF_FILENAME, BRIEF_SOURCE_FILENAME):
        path = repo_root / ".kittify" / filename
        path.unlink(missing_ok=True)
