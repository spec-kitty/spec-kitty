"""Glossary chokepoint: fast inline semantic-conflict scanner (WP02).

Provides :class:`GlossaryChokepoint` — a lazy-loaded, stateless scanner
that tokenises request text, matches tokens against the :class:`GlossaryTermIndex`
built in WP01, runs the existing conflict classifiers, and returns a
:class:`GlossaryObservationBundle` without ever propagating exceptions.

Performance target: p95 ≤ 50 ms for a 500-word request text.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .drg_builder import GlossaryTermIndex, _normalize, build_index
from .extraction import COMMON_WORDS, ExtractedTerm
from .models import SemanticConflict, TermSense
from .scope import GlossaryScope, load_seed_file
from .store import GlossaryStore

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default applicable scopes (T009)
# ---------------------------------------------------------------------------

DEFAULT_APPLICABLE_SCOPES: frozenset[GlossaryScope] = frozenset(
    {GlossaryScope.SPEC_KITTY_CORE, GlossaryScope.TEAM_DOMAIN}
)

# Tokeniser: split on whitespace and non-word characters
_TOKEN_RE = re.compile(r"[\s\W]+")

# Minimum token length to bother looking up
_MIN_TOKEN_LEN = 3


# ---------------------------------------------------------------------------
# GlossaryObservationBundle (T008)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GlossaryObservationBundle:
    """Immutable result of a single chokepoint scan.

    Attributes:
        matched_urns: Tuple of ``glossary:<id>`` URNs for every token found in
            the index, including tokens that produced no conflict.
        high_severity: Subset of *all_conflicts* where severity is HIGH.
        all_conflicts: Every :class:`SemanticConflict` detected during the scan.
        tokens_checked: Number of distinct normalised tokens examined.
        duration_ms: Wall-clock time for the scan in milliseconds.
        error_msg: Non-None only when an unexpected exception occurred inside
            :meth:`GlossaryChokepoint.run`; the bundle is otherwise fully
            populated with empty collections.
    """

    matched_urns: tuple[str, ...]
    high_severity: tuple[SemanticConflict, ...]
    all_conflicts: tuple[SemanticConflict, ...]
    tokens_checked: int
    duration_ms: float
    error_msg: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of this bundle.

        All :class:`SemanticConflict` objects are serialised via
        :func:`glossary.models.semantic_conflict_to_dict`.
        """
        from .models import semantic_conflict_to_dict

        return {
            "matched_urns": list(self.matched_urns),
            "high_severity": [semantic_conflict_to_dict(c) for c in self.high_severity],
            "all_conflicts": [semantic_conflict_to_dict(c) for c in self.all_conflicts],
            "tokens_checked": self.tokens_checked,
            "duration_ms": self.duration_ms,
            "error_msg": self.error_msg,
        }


@dataclass(frozen=True)
class _InvocationGlossaryEventContext:
    """Minimal context shim for glossary event emission from profile invocations."""

    step_id: str
    mission_id: str
    run_id: str
    actor_id: str


# ---------------------------------------------------------------------------
# GlossaryChokepoint (T009 / T010 / T011)
# ---------------------------------------------------------------------------


class GlossaryChokepoint:
    """Lazy-loaded inline glossary scanner.

    Construction is side-effect-free: the store is loaded on the first call
    to :meth:`run` (or :meth:`_load_index`) and cached for the lifetime of the
    instance.

    Args:
        repo_root: Path to the project root used to locate seed files under
            ``.kittify/glossaries/``.
        events_root: Checkout whose ``.kittify/events/glossary/`` receives the
            invocation-scoped events this scan emits. Defaults to
            ``repo_root``; an Op run from a linked worktree passes that
            worktree, so its trail stays with its Op record (#6564).
        applicable_scopes: Frozenset of :class:`GlossaryScope` values to
            include.  Defaults to :data:`DEFAULT_APPLICABLE_SCOPES`.
    """

    def __init__(
        self,
        repo_root: Path,
        applicable_scopes: frozenset[GlossaryScope] | None = None,
        *,
        events_root: Path | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._events_root = events_root if events_root is not None else repo_root
        self._applicable_scopes: frozenset[GlossaryScope] = (
            applicable_scopes if applicable_scopes is not None else DEFAULT_APPLICABLE_SCOPES
        )
        self._index: GlossaryTermIndex | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_store(self, repo_root: Path) -> GlossaryStore:
        """Build a :class:`GlossaryStore` from seed files on disk.

        Loads every scope in *applicable_scopes* from
        ``.kittify/glossaries/<scope>.yaml``.  Missing files are silently
        skipped (``load_seed_file`` returns ``[]`` when absent).

        Args:
            repo_root: Project root directory.

        Returns:
            Populated :class:`GlossaryStore`.
        """
        store = GlossaryStore(repo_root / ".kittify" / "glossaries" / "_events.jsonl")
        for scope in self._applicable_scopes:
            for sense in load_seed_file(scope, repo_root):
                store.add_sense(sense)
        return store

    def _load_index(self) -> GlossaryTermIndex:
        """Return the cached :class:`GlossaryTermIndex`, building it on first call.

        Calling this method twice returns the *same* object (idempotent).

        Returns:
            The term index for the configured scopes.
        """
        if self._index is None:
            store = self._load_store(self._repo_root)
            scope_values = [s.value for s in self._applicable_scopes]
            self._index = build_index(store, scope_values)
            if self._index.term_count == 0:
                _logger.debug(
                    "GlossaryChokepoint: term index is empty for scopes %s "
                    "(no .kittify/glossaries/*.yaml seed files found?)",
                    scope_values,
                )
        return self._index

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        request_text: str,
        invocation_id: str = "",  # noqa: ARG002  (reserved for future telemetry)
        actor_id: str = "unknown",
    ) -> GlossaryObservationBundle:
        """Scan *request_text* for glossary conflicts and return a bundle.

        This method **never propagates exceptions**.  Any unexpected error is
        caught and returned as an error-bundle with ``error_msg`` populated and
        all collection fields empty.

        Args:
            request_text: The text to scan (e.g. a step description).
            invocation_id: Optional caller-supplied correlation ID (reserved).

        Returns:
            A :class:`GlossaryObservationBundle` with scan results.
        """
        t0 = time.monotonic()
        try:
            bundle = self._run_inner(
                request_text,
                invocation_id=invocation_id,
                actor_id=actor_id,
            )
            return bundle
        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.monotonic() - t0) * 1000.0
            return GlossaryObservationBundle(
                matched_urns=(),
                high_severity=(),
                all_conflicts=(),
                tokens_checked=0,
                duration_ms=duration_ms,
                error_msg=str(exc),
            )

    def _build_event_context(
        self,
        *,
        invocation_id: str,
        actor_id: str,
    ) -> _InvocationGlossaryEventContext | None:
        """Return a minimal event context for invocation-scoped glossary events."""
        if not invocation_id:
            return None
        mission_id = f"profile-invocation-{invocation_id}"
        return _InvocationGlossaryEventContext(
            step_id=f"profile-invocation:{invocation_id}",
            mission_id=mission_id,
            run_id=invocation_id,
            actor_id=actor_id,
        )

    def _emit_unknown_term_candidate(
        self,
        extracted_term: ExtractedTerm,
        *,
        event_context: _InvocationGlossaryEventContext | None,
    ) -> None:
        """Best-effort emission of unknown glossary term candidates."""
        if event_context is None:
            return
        from .events import emit_term_candidate_observed

        emit_term_candidate_observed(
            extracted_term,
            event_context,
            repo_root=self._events_root,
        )

    def _run_inner(
        self,
        request_text: str,
        *,
        invocation_id: str,
        actor_id: str,
    ) -> GlossaryObservationBundle:
        """Core scan logic (called inside the try/except in :meth:`run`).

        Tokenises *request_text*, filters common words, normalises via
        :func:`_normalize`, looks each token up in the index, then runs the
        existing conflict classifiers (T011) for matched tokens.

        Returns:
            A populated :class:`GlossaryObservationBundle`.
        """
        from .conflict import classify_conflict, create_conflict, score_severity

        t0 = time.monotonic()
        index = self._load_index()
        event_context = self._build_event_context(
            invocation_id=invocation_id,
            actor_id=actor_id,
        )

        # --- tokenise ---
        raw_tokens = _TOKEN_RE.split(request_text.lower())

        seen: set[str] = set()
        checked_tokens: list[str] = []
        for raw in raw_tokens:
            if len(raw) < _MIN_TOKEN_LEN:
                continue
            if raw in COMMON_WORDS:
                continue
            normalized = _normalize(raw)
            if not normalized or len(normalized) < _MIN_TOKEN_LEN:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            checked_tokens.append(normalized)

        # --- index lookup + conflict classification ---
        matched_urns: list[str] = []
        all_conflicts: list[SemanticConflict] = []

        for normalized in checked_tokens:
            senses: list[TermSense] = []
            extracted_term = ExtractedTerm(
                surface=normalized,
                source="request_text",
                confidence=1.0,
                original=normalized,
            )

            # Try the normalised form first, then the raw token
            if normalized in index.surface_to_senses:
                senses = index.surface_to_senses[normalized]
                urn = index.surface_to_urn[normalized]
                matched_urns.append(urn)
            # If no match, skip conflict classification for this token
            if not senses:
                self._emit_unknown_term_candidate(
                    extracted_term,
                    event_context=event_context,
                )
                continue

            conflict_type = classify_conflict(
                term=extracted_term,
                resolution_results=senses,
                is_critical_step=False,
                llm_output_text=None,
            )

            if conflict_type is not None:
                severity = score_severity(conflict_type, confidence=1.0, is_critical_step=False)
                conflict = create_conflict(
                    term=extracted_term,
                    conflict_type=conflict_type,
                    severity=severity,
                    candidate_senses=senses,
                    context="request_text",
                )
                all_conflicts.append(conflict)

        duration_ms = (time.monotonic() - t0) * 1000.0

        from .models import Severity

        high_severity = tuple(c for c in all_conflicts if c.severity == Severity.HIGH)

        return GlossaryObservationBundle(
            matched_urns=tuple(matched_urns),
            high_severity=high_severity,
            all_conflicts=tuple(all_conflicts),
            tokens_checked=len(checked_tokens),
            duration_ms=duration_ms,
            error_msg=None,
        )


__all__ = [
    # DEFAULT_APPLICABLE_SCOPES: demoted — no cross-module src/ from-import
    # callers (WP01 harden-dead-symbol-gate-01KW0RJR).
    "GlossaryChokepoint",
    "GlossaryObservationBundle",
]
