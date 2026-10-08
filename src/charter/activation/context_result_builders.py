"""Branch-result builders for ``build_charter_context`` (Sonar S3776 remediation).

Relocated from ``charter.activation.context`` (charter-sync-sonar-remediation-01KZPPZW
WP02): ``build_charter_context`` exceeded the Cognitive Complexity ceiling
(Sonar S3776, 19 > 15) because it inlined the full body of all four render
branches (non-bootstrap / missing-charter / compact-bundle / bootstrap). The
branch *selection* logic (which branch to take, computed once from
``normalized``/``state_bundle``/``charter_path`` presence) stays in
``build_charter_context`` itself — only each branch's result-construction
BODY moved here, one function per branch, matching this file's decomposition
precedent (``context.py``'s own docstring: "New context-resolution logic
belongs in a sibling, not here"). This also keeps ``context.py`` under its
independently-enforced 600-line ceiling
(``tests/charter/test_context_decomposition_completion.py``).

:class:`CharterContextResult` moved alongside its builders (avoids a
``context.py`` <-> this-module import cycle); ``charter.activation.context`` re-exports
it under the existing FR-009 preserved-surface convention.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from charter.activation.charter_md_parsing import _extract_policy_summary
from charter.activation.context_renderers.bootstrap_text import _render_bootstrap_text
from charter.activation.context_renderers.compact_governance import (
    _render_compact_from_bundle,
    _render_compact_governance,
)
from charter.activation.context_renderers.reference_pointers import _load_references
from charter.activation.context_state import _mark_action_loaded
from charter.activation.org_pack_discovery import _load_governance_charter_config

if TYPE_CHECKING:
    from charter.activation.action_governance_bundle import _ActionGovernanceBundle
    from charter.activation.context_state import _ContextStateBundle
    from charter.offering.agent_profiles import AgentProfile

__all__ = [
    "CharterContextResult",
    "build_bootstrap_context_result",
    "build_compact_bundle_context_result",
    "build_missing_charter_context_result",
    "build_non_bootstrap_context_result",
]


@dataclass(frozen=True)
class CharterContextResult:
    """Rendered charter context payload."""

    action: str
    mode: str
    first_load: bool
    text: str
    references_count: int
    depth: int


def build_non_bootstrap_context_result(
    repo_root: Path,
    normalized: str,
    depth: int | None,
    profile_record: AgentProfile | None,
    *,
    suppress_project_resolver: bool,
    augment: Callable[[str], str],
) -> CharterContextResult:
    """Build the "compact" result for a non-bootstrap action (no action grain)."""
    effective_depth = depth if depth is not None else 1
    return CharterContextResult(
        action=normalized,
        mode="compact",
        first_load=False,
        text=augment(
            _render_compact_governance(
                repo_root,
                profile=profile_record,
                action=normalized,
                suppress_project_resolver=suppress_project_resolver,
            )
        ),
        references_count=0,
        depth=effective_depth,
    )


def build_missing_charter_context_result(
    normalized: str,
    state_bundle: _ContextStateBundle,
    *,
    augment: Callable[[str], str],
) -> CharterContextResult:
    """Build the "missing" result when neither charter.yaml nor charter.md exists."""
    text = (
        "Charter Context:\n"
        "  - Charter file not found at `.kittify/charter/charter.yaml`.\n"
        "  - Run `spec-kitty charter interview` then `spec-kitty charter generate`."
    )
    return CharterContextResult(
        action=normalized,
        mode="missing",
        first_load=state_bundle.first_load,
        text=augment(text),
        references_count=0,
        depth=state_bundle.effective_depth,
    )


def build_compact_bundle_context_result(
    repo_root: Path,
    normalized: str,
    state_bundle: _ContextStateBundle,
    profile_record: AgentProfile | None,
    governance_bundle: _ActionGovernanceBundle,
    *,
    suppress_project_resolver: bool,
    mark_loaded: bool,
    augment: Callable[[str], str],
) -> CharterContextResult:
    """Build the widened-compact-rail result for a below-minimum effective depth."""
    if mark_loaded and state_bundle.first_load:
        _mark_action_loaded(state_bundle.state, state_bundle.state_path, normalized)
    return CharterContextResult(
        action=normalized,
        mode="compact",
        first_load=state_bundle.first_load,
        text=augment(
            _render_compact_from_bundle(
                repo_root,
                action=normalized,
                profile=profile_record,
                bundle=governance_bundle,
                suppress_project_resolver=suppress_project_resolver,
            )
        ),
        references_count=0,
        depth=state_bundle.effective_depth,
    )


def build_bootstrap_context_result(
    repo_root: Path,
    normalized: str,
    charter_path: Path,
    canonical_root: Path,
    state_bundle: _ContextStateBundle,
    governance_bundle: _ActionGovernanceBundle,
    profile_record: AgentProfile | None,
    *,
    mark_loaded: bool,
    augment: Callable[[str], str],
) -> CharterContextResult:
    """Build the full bootstrap-mode result (prose + references + doctrine bundle)."""
    # FR-005 graceful-degrade: charter.md prose is optional now that presence
    # is authoritative via charter.yaml (SC-002 -- rendering must survive a
    # deleted charter.md), mirroring the existing compact-section handling of
    # an absent heading rather than crashing on a missing prose file.
    if charter_path.exists():
        charter_content = charter_path.read_text(encoding="utf-8")
        summary = _extract_policy_summary(charter_content)
    else:
        charter_content = ""
        summary = []
    references = _load_references(canonical_root)
    charter_config = _load_governance_charter_config(repo_root)
    text = _render_bootstrap_text(
        charter_path=charter_path,
        action=normalized,
        summary=summary,
        governance_bundle=governance_bundle,
        references=references,
        profile=profile_record,
        repo_root=repo_root,
        charter_config=charter_config,
        charter_content=charter_content,
    )

    if mark_loaded and state_bundle.first_load:
        _mark_action_loaded(state_bundle.state, state_bundle.state_path, normalized)

    return CharterContextResult(
        action=normalized,
        mode="bootstrap",
        first_load=state_bundle.first_load,
        text=augment(text),
        references_count=len(references),
        depth=state_bundle.effective_depth,
    )
