"""End-to-end synthesis pipeline: interview → targets → adapter → provenance.

This module owns the ``run()`` entry point consumed by
``orchestrator.synthesize()``. It wires together:

1. ``interview_mapping.resolve_sections()``  — interview answers → sections
2. ``targets.build_targets()``               — sections → SynthesisTarget list
3. ``targets.order_targets()``               — deterministic ordering (FR-014)
4. ``targets.detect_duplicates()``           — EC-7 guard before adapter calls
5. Adapter dispatch (batch if available, sequential otherwise — KD-3)
6. Schema conformance gate (FR-019 / T012)   — reject invalid adapter outputs
7. In-memory provenance assembly (T013)      — build ProvenanceEntry objects

No filesystem writes happen in this module — WP03 owns persistence.

ProvenanceEntry
---------------
Defined here so WP03 can import and persist it without circular imports.
WP03's writer imports ``ProvenanceEntry`` from this module and calls
``canonical_yaml(body)`` to compute ``artifact_content_hash`` — ensuring
the hash is byte-identical to what WP03 writes to disk.

Determinism guarantee (FR-014 / NFR-006)
-----------------------------------------
For identical (interview_snapshot, doctrine_snapshot, drg_snapshot,
adapter_hints) inputs and the same FixtureAdapter version, ``run()`` produces
byte-identical ``(body, ProvenanceEntry)`` tuples. This is possible because:
- Target ordering is deterministic (``order_targets()``).
- The fixture adapter is deterministic by design (fixed generated_at from hash).
- ``compute_inputs_hash`` is stable (ADR-2026-04-17-1 change-control).
- ``canonical_yaml()`` uses ruamel.yaml with sorted keys.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Mapping
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from ruamel.yaml import YAML
from kernel.clock import now_utc_iso

from .adapter import AdapterOutput, SynthesisAdapter
from .errors import SynthesisSchemaError
from .interview_mapping import normalize_interview_snapshot, resolve_sections
from .orchestrator import SynthesisResult
from .request import SynthesisRequest, SynthesisTarget, compute_inputs_hash, _evidence_to_jsonable
from .targets import build_targets, detect_duplicates, order_targets

__all__ = [
    "ProvenanceEntry",
    "canonical_yaml",
    "run_all",
]

# The five registration-writing kinds, declared once in
# ``charter.offering.artifact_kinds.DIRECT_WRITE_KINDS``. A ``Literal`` cannot
# consume a runtime tuple, so this module's copy is kept aligned by test
# (``tests/charter/test_direct_write_kinds_parity.py``) rather than by
# construction — the single spelling here (reused by the field annotation and
# both ``cast`` sites below) is the by-test SSOT for this module.
_ArtifactKind = Literal["directive", "tactic", "styleguide", "procedure", "agent_profile"]



def _get_synthesizer_version() -> str:
    """Return the installed spec-kitty-cli version, falling back to a dev sentinel.

    Resolved through ``importlib.metadata`` only. The former secondary fallback
    imported ``specify_cli`` for its ``__version__``, which was the single real
    upward edge out of the charter layer (``kernel <- doctrine <- charter <-
    specify_cli``) — see FR-008. Distribution metadata is the same source that
    populates ``specify_cli.__version__`` anyway, so the fallback bought no
    additional coverage; it only inverted the dependency direction. The gate is
    ``tests/architectural/test_charter_no_specify_cli_import.py``.
    """
    try:
        from importlib.metadata import version
        return version("spec-kitty-cli")
    except Exception:  # noqa: BLE001
        return "0.0.0-dev"


# ---------------------------------------------------------------------------
# ProvenanceEntry (data-model.md §E-4)
# ---------------------------------------------------------------------------


class ProvenanceEntry(BaseModel):
    """Per-artifact provenance assembled in memory by the synthesis pipeline.

    WP03 persists this to ``.kittify/charter/provenance/<kind>-<slug>.yaml``.
    The ``artifact_content_hash`` field is computed via ``canonical_yaml(body)``
    so that WP03's on-disk YAML bytes produce the same hash.

    See data-model.md §E-4 for full field documentation.

    Schema version 2 (Phase 7): added synthesizer_version, source_input_ids,
    produced_at, synthesis_run_id; promoted corpus_snapshot_id to non-Optional.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["2"] = "2"
    artifact_urn: str
    artifact_kind: _ArtifactKind
    artifact_slug: str
    artifact_content_hash: str
    """blake3-256 hex (or SHA-256 hex) over ``canonical_yaml(body)`` bytes."""

    inputs_hash: str
    """Full hex digest of the normalized SynthesisRequest."""

    adapter_id: str
    adapter_version: str
    synthesizer_version: str = Field(..., min_length=1)
    """Version of the spec-kitty-cli package that produced this provenance entry."""

    source_section: str | None
    source_urns: list[str]
    source_input_ids: list[str]
    """Mirror of source_urns at write time — stable list of input URN identifiers."""

    generated_at: str
    """ISO 8601 UTC string from ``AdapterOutput.generated_at``."""

    produced_at: str
    """ISO 8601 UTC string stamped at write time by the promote pipeline."""

    corpus_snapshot_id: str
    """snapshot_id from EvidenceBundle.corpus_snapshot, or ``"(none)"`` sentinel."""

    synthesis_run_id: str = Field(..., min_length=1)
    """ULID of the staging run that wrote this provenance sidecar."""

    evidence_bundle_hash: str | None = None
    """SHA-256 hex digest of the serialized EvidenceBundle, or None if absent."""

    adapter_notes: str | None = None

    @model_validator(mode="after")
    def _check_source_provenance(self) -> ProvenanceEntry:
        """Enforce allOf: at least one of source_section or non-empty source_urns.

        Matches contracts/provenance.schema.yaml allOf constraint (T015).
        """
        has_section = bool(self.source_section)
        has_urns = bool(self.source_urns)
        if not has_section and not has_urns:
            raise ValueError(
                "ProvenanceEntry requires at least one of 'source_section' (non-empty) "
                "or 'source_urns' (non-empty list). Both are absent/empty."
            )
        return self


# ---------------------------------------------------------------------------
# Canonical YAML helper — shared with WP03 (T013 / serialization drift note)
# ---------------------------------------------------------------------------


def canonical_yaml(body: Mapping[str, Any]) -> bytes:
    """Serialize ``body`` to YAML bytes in a deterministic canonical form.

    This function is the **single source of truth** for YAML serialization.
    WP03's writer MUST call this function to produce on-disk bytes so that
    ``artifact_content_hash`` computed here matches the hash of the file WP03
    writes.

    Rules:
    - Keys are sorted alphabetically at every level.
    - Default flow style is False (block style).
    - No YAML aliases (pure data, no anchors/references).
    - UTF-8 encoding.
    """
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.explicit_start = False

    # Deep-convert to a plain sorted dict to ensure canonical key ordering.
    def _sort_keys(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _sort_keys(obj[k]) for k in sorted(obj.keys())}
        if isinstance(obj, (list, tuple)):
            return [_sort_keys(v) for v in obj]
        return obj

    sorted_body = _sort_keys(dict(body))
    buf = io.BytesIO()
    yaml.dump(sorted_body, buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Schema conformance gate (T012)
# ---------------------------------------------------------------------------

# Lazy imports to avoid circular imports at module load time.
def _get_schema_by_kind() -> dict[str, Any]:
    from charter.offering.directives.models import Directive
    from charter.offering.styleguides.models import Styleguide
    from charter.offering.tactics.models import Tactic

    return {
        "directive": Directive,
        "tactic": Tactic,
        "styleguide": Styleguide,
    }


def _assert_schema(target: SynthesisTarget, output: AdapterOutput) -> None:
    """Validate ``output.body`` against the built-in Pydantic schema for ``target.kind``.

    Raises ``SynthesisSchemaError`` on failure, before any provenance assembly
    or downstream write (FR-019, NFR-005).

    Parameters
    ----------
    target:
        The synthesis target whose kind determines the expected schema.
    output:
        The adapter output whose ``body`` mapping is validated.

    Raises
    ------
    SynthesisSchemaError
        When ``body`` fails the Pydantic schema for ``target.kind``.
    """
    schema_map = _get_schema_by_kind()
    model_cls = schema_map.get(target.kind)
    if model_cls is None:
        raise SynthesisSchemaError(
            artifact_kind=target.kind,
            artifact_slug=target.slug,
            validation_errors=(f"Unknown artifact kind: {target.kind!r}",),
        )
    try:
        model_cls.model_validate(dict(output.body))
    except ValidationError as exc:
        raise SynthesisSchemaError(
            artifact_kind=target.kind,
            artifact_slug=target.slug,
            validation_errors=tuple(str(err) for err in exc.errors()),
        ) from exc


# ---------------------------------------------------------------------------
# Content hash helper
# ---------------------------------------------------------------------------


def _content_hash(yaml_bytes: bytes) -> str:
    """Return the SHA-256 hex digest of ``yaml_bytes``.

    Uses SHA-256 (available in stdlib) consistent with WP01's
    ``compute_inputs_hash``. The full 64-char hex digest is stored in
    ``ProvenanceEntry.artifact_content_hash``.
    """
    return hashlib.sha256(yaml_bytes).hexdigest()  # noqa: TID251 - production raw SHA-256 owner


# ---------------------------------------------------------------------------
# Evidence hash helper
# ---------------------------------------------------------------------------


def _compute_evidence_hashes(request: SynthesisRequest) -> tuple[str | None, str | None]:
    """Return (evidence_bundle_hash, corpus_snapshot_id) for a SynthesisRequest.

    Returns (None, None) when request.evidence is None or empty so that
    ProvenanceEntry fields remain null for legacy requests.
    """
    if request.evidence is None or request.evidence.is_empty:
        return None, None
    evidence_bytes = json.dumps(
        _evidence_to_jsonable(request.evidence), sort_keys=True, ensure_ascii=True
    ).encode("utf-8")
    evidence_hash = hashlib.sha256(evidence_bytes).hexdigest()  # noqa: TID251 - production raw SHA-256 owner
    corpus_id = (
        request.evidence.corpus_snapshot.snapshot_id
        if request.evidence.corpus_snapshot is not None
        else None
    )
    return evidence_hash, corpus_id


def _artifact_urn_for_target(target: SynthesisTarget) -> str:
    """Return the canonical artifact URN for provenance.

    Directives are keyed by project artifact id (for example ``PROJECT_001``),
    while tactics and styleguides use their slug as both ``artifact_id`` and
    URN suffix.
    """
    return str(target.urn)


# ---------------------------------------------------------------------------
# Adapter dispatch helpers
# ---------------------------------------------------------------------------


def _dispatch_single(
    adapter: SynthesisAdapter,
    per_target_requests: list[SynthesisRequest],
) -> list[AdapterOutput]:
    """Dispatch generate() calls sequentially."""
    return [adapter.generate(req) for req in per_target_requests]


def _dispatch_batch(
    adapter: SynthesisAdapter,
    per_target_requests: list[SynthesisRequest],
) -> list[AdapterOutput]:
    """Dispatch generate_batch() if available, else fall back to sequential."""
    if hasattr(adapter, "generate_batch"):
        raw = adapter.generate_batch(per_target_requests)
        return list(raw)
    return _dispatch_single(adapter, per_target_requests)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run(
    request: SynthesisRequest,
    adapter: SynthesisAdapter | None = None,
) -> SynthesisResult:
    """Run the full interview-driven synthesis pipeline.

    This function is the implementation of ``orchestrator.synthesize()``.
    ``orchestrator.py`` imports it lazily so that WP01 tests remain independent
    of this module.

    Pipeline stages
    ---------------
    1. Resolve sections from ``request.interview_snapshot``.
    2. Build ``SynthesisTarget`` list using the DRG snapshot for URN validation.
    3. Order targets deterministically; detect duplicates.
    4. Construct a per-target ``SynthesisRequest`` (cloning shared snapshots).
    5. Dispatch adapter (batch-capable if available; else sequential).
    6. Validate each ``AdapterOutput.body`` against the built-in Pydantic schema.
    7. Assemble ``ProvenanceEntry`` objects in memory.
    8. Return a ``SynthesisResult`` for the **first** target (the orchestrator
       entry point is per-request; multi-target flows use ``run_all()``).

    Parameters
    ----------
    request:
        The ``SynthesisRequest`` whose ``interview_snapshot`` drives target
        selection and whose ``drg_snapshot`` validates source URNs.
    adapter:
        The adapter to use. When ``None``, raises ``NotImplementedError``
        (production adapter wiring is WP05's responsibility).

    Returns
    -------
    SynthesisResult
        Result for the **primary** target (``request.target``).

    Raises
    ------
    SynthesisSchemaError
        If any adapter output fails schema validation.
    DuplicateTargetError
        If two targets share (kind, slug).
    ProjectDRGValidationError
        If any source URN does not resolve in ``request.drg_snapshot``.
    """
    if adapter is None:
        raise NotImplementedError(
            "Production adapter wiring is not yet implemented (WP05). "
            "Pass a FixtureAdapter instance explicitly."
        )

    # Stage 1: resolve sections from the synthesis-canonical interview snapshot
    interview_snapshot = normalize_interview_snapshot(dict(request.interview_snapshot))
    sections = resolve_sections(interview_snapshot)

    # Stage 2: build targets (validates source URNs against drg_snapshot)
    all_targets = build_targets(
        interview_snapshot=interview_snapshot,
        mappings=sections,
        drg_snapshot=dict(request.drg_snapshot),
    )

    # Stage 3: order + duplicate check
    all_targets = order_targets(all_targets)
    detect_duplicates(all_targets)

    # If no targets were produced from the interview, fall back to the
    # request's own target (e.g. when called directly by the orchestrator
    # with a pre-built target for a specific artifact).
    if not all_targets:
        all_targets = [request.target]

    # Stage 4: build per-target SynthesisRequest objects (clone shared state)
    per_target_requests: list[SynthesisRequest] = []
    for target in all_targets:
        per_target_requests.append(
            SynthesisRequest(
                target=target,
                interview_snapshot=interview_snapshot,
                doctrine_snapshot=request.doctrine_snapshot,
                drg_snapshot=request.drg_snapshot,
                run_id=request.run_id,
                adapter_hints=request.adapter_hints,
                evidence=request.evidence,
            )
        )

    # Compute evidence hashes once — reused for all targets (same request evidence).
    evidence_hash, corpus_id = _compute_evidence_hashes(request)

    # Stage 5: dispatch adapter
    outputs: list[AdapterOutput] = _dispatch_batch(adapter, per_target_requests)

    if len(outputs) != len(per_target_requests):
        raise RuntimeError(
            f"Adapter returned {len(outputs)} outputs for {len(per_target_requests)} "
            "requests. Adapter must return element-aligned outputs."
        )

    # Stages 6 + 7: schema conformance + provenance assembly
    results: list[tuple[Mapping[str, Any], ProvenanceEntry]] = []
    for target, target_req, output in zip(all_targets, per_target_requests, outputs, strict=True):
        # Stage 6: schema conformance gate (FR-019) — before any provenance
        _assert_schema(target, output)

        # Stage 7: assemble provenance in memory (T013)
        effective_adapter_id = output.adapter_id_override or adapter.id
        effective_adapter_version = output.adapter_version_override or adapter.version

        inputs_hash = compute_inputs_hash(
            target_req, effective_adapter_id, effective_adapter_version
        )

        yaml_bytes = canonical_yaml(output.body)
        content_hash = _content_hash(yaml_bytes)

        generated_at_str = output.generated_at.isoformat()
        if not generated_at_str.endswith("Z") and "+" not in generated_at_str[-6:]:
            # Ensure UTC offset is explicit — append +00:00 if only time is present
            generated_at_str = generated_at_str + "+00:00"

        provenance = ProvenanceEntry(
            artifact_urn=_artifact_urn_for_target(target),
            artifact_kind=cast(_ArtifactKind, target.kind),
            artifact_slug=target.slug,
            artifact_content_hash=content_hash,
            inputs_hash=inputs_hash,
            adapter_id=effective_adapter_id,
            adapter_version=effective_adapter_version,
            synthesizer_version=_get_synthesizer_version(),
            source_section=target.source_section,
            source_urns=list(target.source_urns),
            source_input_ids=list(target.source_urns),
            generated_at=generated_at_str,
            produced_at=now_utc_iso(),
            corpus_snapshot_id=corpus_id or "(none)",
            synthesis_run_id=request.run_id,
            evidence_bundle_hash=evidence_hash,
            adapter_notes=output.notes,
        )

        results.append((output.body, provenance))

    # Return SynthesisResult for the request's primary target.
    # run_all() exposes the full list; the orchestrator single-target entry
    # point returns only the first matching result.
    primary_target = request.target
    for (_body, prov), target in zip(results, all_targets, strict=True):
        if target.kind == primary_target.kind and target.slug == primary_target.slug:
            return SynthesisResult(
                target_kind=target.kind,
                target_slug=target.slug,
                adapter_output=outputs[all_targets.index(target)],
                inputs_hash=prov.inputs_hash,
                effective_adapter_id=prov.adapter_id,
                effective_adapter_version=prov.adapter_version,
            )

    # Fallback: return the first result if the primary target was not produced
    # from the interview (direct target call).
    _, first_prov = results[0]
    first_target = all_targets[0]
    return SynthesisResult(
        target_kind=first_target.kind,
        target_slug=first_target.slug,
        adapter_output=outputs[0],
        inputs_hash=first_prov.inputs_hash,
        effective_adapter_id=first_prov.adapter_id,
        effective_adapter_version=first_prov.adapter_version,
    )


def run_all(
    request: SynthesisRequest,
    adapter: SynthesisAdapter | None = None,
) -> list[tuple[Mapping[str, Any], ProvenanceEntry]]:
    """Run the full synthesis pipeline and return ALL (body, provenance) pairs.

    This is the contract consumed by WP03's ``write_pipeline``.

    The same pipeline stages as ``run()`` are executed, but ALL targets are
    returned rather than just the primary target.

    Parameters
    ----------
    request:
        The ``SynthesisRequest`` envelope. ``request.target`` is used as a
        fallback when the interview produces no targets.
    adapter:
        The adapter to use.

    Returns
    -------
    list[tuple[Mapping[str, Any], ProvenanceEntry]]
        One tuple per synthesized target, in deterministic order.
    """
    if adapter is None:
        raise NotImplementedError(
            "Production adapter wiring is not yet implemented (WP05)."
        )

    interview_snapshot = normalize_interview_snapshot(dict(request.interview_snapshot))
    sections = resolve_sections(interview_snapshot)
    all_targets = build_targets(
        interview_snapshot=interview_snapshot,
        mappings=sections,
        drg_snapshot=dict(request.drg_snapshot),
    )
    all_targets = order_targets(all_targets)
    detect_duplicates(all_targets)

    if not all_targets:
        all_targets = [request.target]

    per_target_requests: list[SynthesisRequest] = [
        SynthesisRequest(
            target=t,
            interview_snapshot=interview_snapshot,
            doctrine_snapshot=request.doctrine_snapshot,
            drg_snapshot=request.drg_snapshot,
            run_id=request.run_id,
            adapter_hints=request.adapter_hints,
            evidence=request.evidence,
        )
        for t in all_targets
    ]

    # Compute evidence hashes once — reused for all targets (same request evidence).
    evidence_hash, corpus_id = _compute_evidence_hashes(request)

    outputs = _dispatch_batch(adapter, per_target_requests)

    if len(outputs) != len(per_target_requests):
        raise RuntimeError(
            f"Adapter returned {len(outputs)} outputs for "
            f"{len(per_target_requests)} requests."
        )

    results: list[tuple[Mapping[str, Any], ProvenanceEntry]] = []
    for target, target_req, output in zip(all_targets, per_target_requests, outputs, strict=True):
        _assert_schema(target, output)

        effective_adapter_id = output.adapter_id_override or adapter.id
        effective_adapter_version = output.adapter_version_override or adapter.version

        inputs_hash = compute_inputs_hash(
            target_req, effective_adapter_id, effective_adapter_version
        )

        yaml_bytes = canonical_yaml(output.body)
        content_hash = _content_hash(yaml_bytes)

        generated_at_str = output.generated_at.isoformat()
        if not generated_at_str.endswith("Z") and "+" not in generated_at_str[-6:]:
            generated_at_str = generated_at_str + "+00:00"

        provenance = ProvenanceEntry(
            artifact_urn=_artifact_urn_for_target(target),
            artifact_kind=cast(_ArtifactKind, target.kind),
            artifact_slug=target.slug,
            artifact_content_hash=content_hash,
            inputs_hash=inputs_hash,
            adapter_id=effective_adapter_id,
            adapter_version=effective_adapter_version,
            synthesizer_version=_get_synthesizer_version(),
            source_section=target.source_section,
            source_urns=list(target.source_urns),
            source_input_ids=list(target.source_urns),
            generated_at=generated_at_str,
            produced_at=now_utc_iso(),
            corpus_snapshot_id=corpus_id or "(none)",
            synthesis_run_id=request.run_id,
            evidence_bundle_hash=evidence_hash,
            adapter_notes=output.notes,
        )

        results.append((output.body, provenance))

    return results
