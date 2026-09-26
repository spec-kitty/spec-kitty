"""Single ingestion chokepoint for charter content.

Detects source encoding, records provenance, normalizes to UTF-8.

Detection is delegated wholesale to the canonical, pure detector
(``charter.encoding_recovery.recover``, WP01) per
``contracts/detector-contract.md``:
  1. BOM sniff (UTF-8-SIG, UTF-16-LE, UTF-16-BE) -- confidence 1.0.
  2. Strict UTF-8 decode -- confidence 1.0.
  3. Single-pass ``charset_normalizer`` tie-break (cp1252 preferred when
     tied and strict-decodable; otherwise the sole clear winner).
  4. Fail-closed: ``ambiguous=True`` (raised here as
     CHARTER_ENCODING_AMBIGUOUS) unless ``unsafe=True``, in which case the
     bypass decodes losslessly via the cp1252 tie-break path.

This module never calls ``charset_normalizer`` directly; it owns
provenance writing and the CHARTER_ENCODING_AMBIGUOUS fail-closed contract
around the detector's pure result.

See: src/charter/activation/ERROR_CODES.md
Implements: FR-016, FR-017, FR-018, FR-019, FR-020, FR-021, FR-022
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import ulid as _ulid_mod
from kernel.clock import now_utc_iso
from kernel.errors import KittyInternalConsistencyError

from charter.encoding_recovery import recover as _recover_encoding

from ._diagnostics import CharterEncodingDiagnostic

__all__ = [
    "CharterEncodingError",
    "load_charter_file",
]


logger = logging.getLogger(__name__)

_SPECS_DIR_NAME = "kitty-specs"

# Actor label written to provenance records.
_ACTOR = "spec-kitty charter"


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CharterContent:
    """Result of a charter ingestion.

    All fields match ``data-model.md`` §3 ``CharterContent``.

    Attributes:
        text: always normalized UTF-8 text.
        source_encoding: detected encoding name (e.g. "utf-8", "cp1252").
        confidence: detection confidence in the range [0.0, 1.0].
        source_path: filesystem path of the source, or None for inline bytes.
        normalization_applied: True when the source was re-encoded from
            a non-UTF-8 encoding (including UTF-8-BOM stripping).
    """

    text: str
    source_encoding: str
    confidence: float
    source_path: Path | None
    normalization_applied: bool


class CharterEncodingError(KittyInternalConsistencyError):
    """Raised when encoding detection fails and unsafe=False.

    Subclass of :class:`KittyInternalConsistencyError`. CLI / TUI / UI layers
    catch the base type to render the diagnostic uniformly; never let this
    be swallowed by a bare ``except Exception`` in production code paths.

    Attributes:
        diagnostic: the CharterEncodingDiagnostic enum member that caused the
            failure (the typed source-of-truth for the code value).
        code: JSON-stable diagnostic string (the enum value).
        body: human-readable diagnostic message for the operator.
    """

    def __init__(self, code: CharterEncodingDiagnostic, body: str) -> None:
        super().__init__(code.value, body)
        self.diagnostic = code


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_charter_file(path: Path, *, unsafe: bool = False) -> CharterContent:
    """Load a charter file from disk, detecting its encoding.

    Args:
        path: filesystem path to read.
        unsafe: when True, bypass CHARTER_ENCODING_AMBIGUOUS by accepting the
            highest-confidence decode candidate and logging bypass_used=True in
            provenance.  Use only when you've inspected the file and accept the
            operational risk.

    Returns:
        CharterContent with normalized UTF-8 text and provenance metadata.

    Raises:
        CharterEncodingError: if encoding is ambiguous and unsafe=False.
    """
    data = path.read_bytes()
    return _load_inner(data, source_path=path, unsafe=unsafe)


def load_charter_bytes(
    data: bytes,
    *,
    origin: str,
    unsafe: bool = False,
) -> CharterContent:
    """Load charter content from raw bytes (inline ingest path).

    Args:
        data: raw bytes to decode.
        origin: human-readable origin label used in provenance (e.g. a URL or
            resource name).
        unsafe: same semantics as in load_charter_file().

    Returns:
        CharterContent with normalized UTF-8 text and provenance metadata.

    Raises:
        CharterEncodingError: if encoding is ambiguous and unsafe=False.
    """
    # `origin` is part of the public API for future provenance labeling
    # of inline-byte ingest, but the current chokepoint records provenance
    # only for path-based ingest. Keep the parameter for API stability;
    # do not forward it to ``_load_inner`` until provenance growth wires it in.
    del origin
    return _load_inner(data, source_path=None, unsafe=unsafe)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_inner(
    data: bytes,
    *,
    source_path: Path | None,
    unsafe: bool,
) -> CharterContent:
    """Core detection pipeline shared by both public functions.

    Delegates the entire detection algorithm (BOM sniff, strict UTF-8,
    single-pass cp1252 tie-break, unsafe lossless bypass) to
    :func:`charter.encoding_recovery.recover` -- see
    ``contracts/detector-contract.md``. This function owns only the
    adapter shape (building ``CharterContent``), the fail-closed
    ``CHARTER_ENCODING_AMBIGUOUS`` raise, and provenance writing.
    """
    result = _recover_encoding(data, unsafe=unsafe)

    if result.ambiguous:
        raise CharterEncodingError(
            CharterEncodingDiagnostic.AMBIGUOUS,
            _build_ambiguous_body(result.candidates, source_path),
        )

    # Contract: only an ambiguous result has text/source_encoding=None, and
    # that case is always handled by the early raise above.
    assert result.text is not None
    assert result.source_encoding is not None

    content = CharterContent(
        text=result.text,
        source_encoding=result.source_encoding,
        confidence=result.confidence,
        source_path=source_path,
        normalization_applied=result.normalization_applied,
    )
    _write_provenance(content, bypass_used=result.bypass_used)
    return content


def _build_ambiguous_body(
    candidates: tuple[tuple[str, float], ...],
    source_path: Path | None,
) -> str:
    """Build the operator-facing diagnostic body for CHARTER_ENCODING_AMBIGUOUS.

    Consumes the ``candidates`` already collected by the single
    ``charset_normalizer.from_bytes`` pass inside
    :func:`charter.encoding_recovery.recover` -- this function never
    re-runs detection (contract guarantee #2, "single pass").
    """
    file_label = str(source_path) if source_path is not None else "<inline bytes>"

    candidates_lines: list[str] = [f"    - {encoding} (confidence {confidence:.2f})" for encoding, confidence in candidates]
    if not candidates_lines:
        candidates_lines.append("    (no candidates detected)")

    candidates_str = "\n".join(candidates_lines)
    return (
        f"ERROR: {CharterEncodingDiagnostic.AMBIGUOUS}\n"
        f"  File: {file_label}\n"
        f"  Detected candidates:\n"
        f"{candidates_str}\n"
        f"  Mixed-content signal: the byte sequence cannot be decoded as strict UTF-8\n"
        f"  and no encoding could be selected via the cp1252 tie-break contract.\n"
        f"\n"
        f"  Remediation options:\n"
        f"    1. Open the file in a UTF-8-aware editor and re-save.\n"
        f"    2. iconv -f <detected-encoding> -t utf-8 <file> > <file>.utf8 && mv <file>.utf8 <file>.\n"
        f"    3. Re-run with --unsafe (logs bypass_used=true to provenance)."
    )


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------


def _generate_ulid() -> str:
    """Generate a new ULID string using the codebase's existing ulid library."""
    if hasattr(_ulid_mod, "new"):
        return str(_ulid_mod.new().str)
    return str(_ulid_mod.ULID())


def _write_provenance(content: CharterContent, *, bypass_used: bool) -> None:
    """Append a provenance record to the appropriate JSONL file."""
    record = _build_provenance_record(content, bypass_used=bypass_used)
    provenance_path = _route_provenance_path(content.source_path)
    try:
        provenance_path.parent.mkdir(parents=True, exist_ok=True)
        with provenance_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        # Non-fatal: provenance write failure must not break ingest.
        logger.warning("Failed to write encoding provenance to %s", provenance_path)


def _build_provenance_record(
    content: CharterContent,
    *,
    bypass_used: bool,
) -> dict[str, object]:
    """Build a provenance record matching data-model.md §3 EncodingProvenanceRecord."""
    file_path_str = str(content.source_path) if content.source_path is not None else ""
    mission_id = _resolve_mission_id(content.source_path)
    return {
        "event_id": _generate_ulid(),
        "at": now_utc_iso(),
        "file_path": file_path_str,
        "source_encoding": content.source_encoding,
        "confidence": content.confidence,
        "normalization_applied": content.normalization_applied,
        "bypass_used": bypass_used,
        "actor": _ACTOR,
        "mission_id": mission_id,
    }


def _route_provenance_path(source_path: Path | None) -> Path:
    """Return the JSONL file to append a provenance record to.

    Per FR-022 / contracts/encoding-provenance-schema.md:
    - Per-mission: if source_path is under kitty-specs/<mission>/, write to
      kitty-specs/<mission>/.encoding-provenance.jsonl.
    - Centralized: otherwise write to .kittify/encoding-provenance/global.jsonl.

    A record is NEVER written to both files.
    """
    if source_path is None:
        return Path(".kittify/encoding-provenance/global.jsonl")

    # Detect kitty-specs/<mission-slug>/ prefix.
    parts = source_path.parts
    if _SPECS_DIR_NAME in parts:
        idx = list(parts).index(_SPECS_DIR_NAME)
        if idx + 1 < len(parts):
            # Mission directory is kitty-specs/<mission-slug>/
            mission_dir = Path(*parts[: idx + 2])
            return mission_dir / ".encoding-provenance.jsonl"

    return Path(".kittify/encoding-provenance/global.jsonl")


def _resolve_mission_id(source_path: Path | None) -> str | None:
    """Attempt to read mission_id from kitty-specs/<mission>/meta.json.

    Returns None when:
    - source_path is None.
    - source_path is not under kitty-specs/<mission>/.
    - meta.json is absent or does not contain mission_id.
    """
    if source_path is None:
        return None

    parts = source_path.parts
    if _SPECS_DIR_NAME not in parts:
        return None

    idx = list(parts).index(_SPECS_DIR_NAME)
    if idx + 1 >= len(parts):
        return None

    meta_path = Path(*parts[: idx + 2]) / "meta.json"
    try:
        meta_text = meta_path.read_text(encoding="utf-8")
        meta = json.loads(meta_text)
        return str(meta["mission_id"]) if "mission_id" in meta else None
    except (OSError, json.JSONDecodeError, KeyError):
        return None
