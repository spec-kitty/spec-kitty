"""
Frozen contract: Charter Synthesizer Adapter Seam.

This file is a PLANNING ARTIFACT, not production code. It lives under
kitty-specs/<mission>/contracts/ so reviewers can lock the exact shape of the
seam before WP3.1 implementation begins. Changes to this contract after
WP3.1 lands require an ADR amendment (per KD-6 and DIRECTIVE_003).

Implementation target: src/charter/synthesizer/adapter.py

Key decisions locked here (see plan.md §Key Decisions):
- KD-3: Synchronous Protocol with a mandatory `generate` and an optional
        `generate_batch`. No asyncio in this tranche.
- KD-3 (R): Adapter exposes `id` and `version` as attributes. `AdapterOutput`
        may carry per-call overrides. Orchestration uses override-first with
        adapter-attribute fallback.
- KD-4: The fixture adapter keys fixtures by normalized-request hash. The
        Protocol itself does NOT specify fixture behavior; that is a detail
        of the FixtureAdapter implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from collections.abc import Mapping, Sequence


# -- Inputs / Outputs -----------------------------------------------------


@dataclass(frozen=True)
class SynthesisTarget:
    """One unit of synthesis. See data-model.md §E-2."""

    kind: str  # Literal["directive", "tactic", "styleguide"]
    slug: str
    source_section: str | None
    source_urns: tuple[str, ...]
    title: str


@dataclass(frozen=True)
class SynthesisRequest:
    """Input envelope handed to a single `generate` call. See data-model.md §E-1."""

    target: SynthesisTarget
    interview_snapshot: Mapping[str, Any]
    doctrine_snapshot: Mapping[str, Any]
    drg_snapshot: Mapping[str, Any]
    adapter_hints: Mapping[str, str] | None = None
    run_id: str = ""  # ULID. Excluded from fixture-hash per R-0-6 rule 4.
    evidence: Any = None  # EvidenceBundle | None — added by WP01 (charter phase 3)


@dataclass(frozen=True)
class AdapterOutput:
    """What `generate` returns. See data-model.md §E-3."""

    body: Mapping[str, Any]
    generated_at: datetime  # tz-aware, UTC
    adapter_id_override: str | None = None
    adapter_version_override: str | None = None
    notes: str | None = None


# -- The seam -------------------------------------------------------------


@runtime_checkable
class SynthesisAdapter(Protocol):
    """
    The narrow seam between deterministic orchestration and model-driven
    generation.

    Implementations MUST expose `id` and `version` attributes; these are the
    default provenance identity for every call. Implementations MAY optionally
    define `generate_batch` for efficiency; orchestration detects its presence
    via `hasattr(adapter, "generate_batch")` and uses it when available.

    Implementations MUST be synchronous. No asyncio in this tranche (KD-3).
    """

    id: str
    version: str

    def generate(self, request: SynthesisRequest) -> AdapterOutput:
        """
        Produce a single artifact body for the given request.

        Must be pure w.r.t. its inputs modulo the adapter's own model backend:
        a fixture adapter MUST produce byte-identical output for byte-identical
        normalized input. Production adapters are not required to be
        byte-identical across calls, but MUST carry enough identity in
        AdapterOutput for provenance to be useful (overrides or adapter-level
        attributes).
        """
        ...


class BatchCapableSynthesisAdapter(SynthesisAdapter, Protocol):
    """
    Optional extension. Orchestration detects and uses `generate_batch` via
    `hasattr` rather than by type narrowing, so adapters do NOT need to
    declare they implement this Protocol — they just need a compatible
    method. This stub exists for documentation / static-analysis aid only.
    """

    def generate_batch(
        self, requests: Sequence[SynthesisRequest]
    ) -> Sequence[AdapterOutput]:
        """
        Produce outputs for a batch of requests. Returned sequence MUST be the
        same length as the input sequence and element-aligned. If an adapter
        cannot satisfy any one request, it MUST raise rather than returning a
        partial sequence (orchestration will fall back to per-request
        `generate` for recovery if it chooses).
        """
        ...


# -- Test-only FixtureAdapter exception (declared here for contract clarity) --


@dataclass(frozen=True)
class FixtureAdapterMissingError(Exception):
    """
    Raised by the test-only FixtureAdapter when no recorded fixture matches
    the normalized request hash. The CLI fixture-opt-in path (`--adapter
    fixture`) surfaces this as a user-facing error with the expected path
    so operators can record a new fixture.
    """

    expected_path: str
    kind: str
    slug: str
    inputs_hash: str

    def __str__(self) -> str:
        return (
            f"no fixture found for {self.kind}:{self.slug} "
            f"(inputs_hash={self.inputs_hash}); expected at {self.expected_path}"
        )
