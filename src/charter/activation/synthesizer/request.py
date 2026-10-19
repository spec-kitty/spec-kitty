"""SynthesisRequest and SynthesisTarget frozen dataclasses.

These are the input envelopes for adapter generate() calls. The module also
provides normalize_request_for_hash() — the *sole* source of fixture-hash
bytes. Changing this function changes every fixture hash, so it is subject
to ADR change-control (ADR-2026-04-17-1).

See data-model.md §E-1 and §E-2 for authoritative field documentation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

from charter.activation.synthesizer.evidence import EvidenceBundle

__all__ = [
    "SynthesisRequest",
    "SynthesisTarget",
    "compute_inputs_hash",
    "short_hash",
]



# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_DIRECTIVE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]*$")
_SHIPPED_DIRECTIVE_PREFIX = "DIRECTIVE_"


def _validate_slug(slug: str) -> None:
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"Invalid slug '{slug}': must match ^[a-z][a-z0-9-]*$"
        )


def _validate_directive_id(artifact_id: str) -> None:
    if not _DIRECTIVE_ID_RE.match(artifact_id):
        raise ValueError(
            f"Invalid directive artifact_id '{artifact_id}': "
            f"must match ^[A-Z][A-Z0-9_-]*$"
        )
    if artifact_id.startswith(_SHIPPED_DIRECTIVE_PREFIX):
        raise ValueError(
            f"Directive artifact_id '{artifact_id}' must not start with "
            f"'{_SHIPPED_DIRECTIVE_PREFIX}' — that namespace is reserved for "
            f"built-in directives. Use PROJECT_<NNN> or a semantic prefix."
        )


# ---------------------------------------------------------------------------
# SynthesisTarget
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SynthesisTarget:
    """One unit of synthesis — what to generate and where it comes from.

    See data-model.md §E-2 for full field documentation.

    Invariants enforced in __post_init__:
    - slug matches ^[a-z][a-z0-9-]*$
    - for kind=="directive", artifact_id matches ^[A-Z][A-Z0-9_-]*$ and must
      not start with DIRECTIVE_ (built-in namespace)
    - at least one of source_section / source_urns is non-empty
    """

    kind: str  # Literal["directive", "tactic", "styleguide"] — not imported to avoid circular
    slug: str
    title: str
    artifact_id: str
    source_section: str | None = None
    source_urns: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_slug(self.slug)
        if self.kind == "directive":
            _validate_directive_id(self.artifact_id)
        if not self.source_section and not self.source_urns:
            raise ValueError(
                f"SynthesisTarget({self.kind}:{self.slug}): at least one of "
                f"source_section or source_urns must be non-empty."
            )

    @property
    def urn(self) -> str:
        """Computed URN: f'{kind}:{artifact_id}'.

        For tactic/styleguide: artifact_id == slug so urn == f'{kind}:{slug}'.
        For directive: urn == f'directive:PROJECT_<NNN>'.
        """
        return f"{self.kind}:{self.artifact_id}"

    @property
    def filename(self) -> str:
        """Computed filename matching existing repository globs.

        - directive: <NNN>-<slug>.directive.yaml  (NNN extracted from artifact_id)
        - tactic:    <slug>.tactic.yaml
        - styleguide: <slug>.styleguide.yaml
        """
        if self.kind == "directive":
            # Extract leading digit run from artifact_id, e.g. PROJECT_001 -> 001
            digits = re.search(r"\d+", self.artifact_id)
            nnn = digits.group(0) if digits else "000"
            return f"{nnn}-{self.slug}.directive.yaml"
        if self.kind == "tactic":
            return f"{self.slug}.tactic.yaml"
        if self.kind == "styleguide":
            return f"{self.slug}.styleguide.yaml"
        raise ValueError(f"Unknown artifact kind: {self.kind}")


# ---------------------------------------------------------------------------
# SynthesisRequest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SynthesisRequest:
    """Input envelope handed to a single adapter generate() call.

    See data-model.md §E-1 for full field documentation.

    run_id is included for traceability but is EXCLUDED from the fixture hash
    (normalization rule 4 from R-0-6). This keeps fixtures stable across runs
    for identical semantic inputs.
    """

    target: SynthesisTarget
    interview_snapshot: Mapping[str, Any]
    doctrine_snapshot: Mapping[str, Any]
    drg_snapshot: Mapping[str, Any]
    run_id: str  # ULID — excluded from fixture hash
    adapter_hints: Mapping[str, str] | None = None
    evidence: EvidenceBundle | None = None


# ---------------------------------------------------------------------------
# Normalization for fixture keying
# ---------------------------------------------------------------------------


def _to_jsonable(obj: Any) -> Any:
    """Recursively convert an object to a JSON-serializable form with sorted keys."""
    if isinstance(obj, dict):
        return {k: _to_jsonable(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    # Stable representation for float — avoid locale-sensitive formatting
    if isinstance(obj, float):
        return repr(obj)
    return obj


def _mapping_to_sorted(m: Mapping[str, Any]) -> dict[str, Any]:
    """Deep-convert a mapping to a dict with recursively sorted keys."""
    result: dict[str, Any] = {}
    for k in sorted(m.keys()):
        v = m[k]
        if isinstance(v, dict):
            result[k] = _mapping_to_sorted(v)
        elif isinstance(v, (list, tuple)):
            result[k] = [_to_jsonable(item) for item in v]
        elif isinstance(v, float):
            result[k] = repr(v)
        else:
            result[k] = v
    return result


def _evidence_to_jsonable(e: EvidenceBundle) -> dict[str, Any]:
    """Serialize an EvidenceBundle to a JSON-serializable dict for hashing.

    Rules:
    - All sequences sorted for order-independence.
    - Timestamps (detected_at, loaded_at, collected_at) excluded.
    - corpus entries sorted by topic.

    This function is called only when evidence is non-None and non-empty.
    """
    result: dict[str, Any] = {}

    if e.code_signals is not None:
        cs = e.code_signals
        result["code_signals"] = {
            "frameworks": sorted(cs.frameworks),
            "primary_language": cs.primary_language,
            "representative_files": sorted(cs.representative_files),
            "scope_tag": cs.scope_tag,
            "stack_id": cs.stack_id,
            "test_frameworks": sorted(cs.test_frameworks),
            # detected_at excluded from hash
        }
        # FR-012: ``languages`` joins the identity only for polyglot repositories, so the
        # hash of every single-language repository (and a stored provenance) is unchanged.
        if len(cs.languages) > 1:
            result["code_signals"]["languages"] = list(cs.languages)

    if e.url_list:
        result["url_list"] = sorted(e.url_list)

    if e.corpus_snapshot is not None:
        snap = e.corpus_snapshot
        result["corpus_snapshot"] = {
            "entries": [
                {
                    "guidance": entry.guidance,
                    "tags": sorted(entry.tags),
                    "topic": entry.topic,
                }
                for entry in sorted(snap.entries, key=lambda x: x.topic)
            ],
            "profile_key": snap.profile_key,
            "snapshot_id": snap.snapshot_id,
            # loaded_at excluded from hash
        }

    # collected_at excluded from hash

    return result


def normalize_request_for_hash(
    request: SynthesisRequest,
    adapter_id: str,
    adapter_version: str,
) -> bytes:
    """Return canonical JSON bytes for fixture keying.

    This is the *sole* source of fixture-hash bytes.  Rules (R-0-6):
    1. All mapping fields serialized with sorted keys.
    2. Sequences that are order-insensitive sorted alphabetically.
    3. Numeric fields use repr-stable JSON serialization.
    4. run_id excluded (ephemeral / per-run identity).
    5. adapter_id + adapter_version ARE included (different versions → different hashes).

    DO NOT change this function without ADR amendment — every existing fixture
    will produce a different path and stop loading.
    """
    target = request.target
    normalized: dict[str, Any] = {
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "target": {
            "artifact_id": target.artifact_id,
            "kind": target.kind,
            "slug": target.slug,
            "source_section": target.source_section,
            "source_urns": sorted(target.source_urns),
            "title": target.title,
        },
        "interview_snapshot": _mapping_to_sorted(request.interview_snapshot),
        "doctrine_snapshot": _mapping_to_sorted(request.doctrine_snapshot),
        "drg_snapshot": _mapping_to_sorted(request.drg_snapshot),
        "adapter_hints": (
            _mapping_to_sorted(request.adapter_hints)
            if request.adapter_hints is not None
            else None
        ),
    }
    # Backward-compat guarantee: when evidence is None or empty, the key is
    # absent from the normalized dict, producing byte-for-byte identical output
    # to the pre-evidence code path (ADR-2026-04-17-1).
    if request.evidence is not None and not request.evidence.is_empty:
        normalized["evidence"] = _evidence_to_jsonable(request.evidence)
    return json.dumps(normalized, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def compute_inputs_hash(
    request: SynthesisRequest,
    adapter_id: str,
    adapter_version: str,
) -> str:
    """Return the full SHA-256 hex digest over normalized request bytes.

    Uses SHA-256 (available in stdlib) as the hash algorithm. The fixture file
    name uses the first 12 hex chars of this digest (48 bits) as the short hash.

    Note: research.md R-0-6 mentions blake3, but this codebase uses SHA-256 via
    hashlib for the charter hashing surface. SHA-256 provides equivalent fixture-
    stability guarantees with zero new dependencies.
    """
    raw = normalize_request_for_hash(request, adapter_id, adapter_version)
    return hashlib.sha256(raw).hexdigest()  # noqa: TID251 - production raw SHA-256 owner


def short_hash(full_hex: str, length: int = 12) -> str:
    """Return the first `length` hex chars of a full hash digest.

    12 chars = 48 bits, giving collision probability ~10^-11 within a
    <kind>/<slug>/ fixture namespace — more than sufficient (R-0-6).
    """
    return full_hex[:length]
