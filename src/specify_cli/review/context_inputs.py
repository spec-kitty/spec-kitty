"""The inputs of the review-context block, built once for both review entry points (#7578, FR-012).

``spec-kitty next`` (``runtime.next.prompt_builder``) and ``agent action review``
(``cli.commands.agent.workflow_executor``) print the same block. :func:`review_context_inputs`
is the one builder of what it renders: the work package's review range and its cited
requirements. The Mission's ``spec.md`` is read through the placement seam with the caller's
owned checkout, so an owned Mission is read from its own checkout on both paths. A spec that
cannot be read cites nothing as declared (NFR-004); nothing here raises for it.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from mission_runtime import MissionArtifactKind, OwnedCheckout, placement_seam
from specify_cli.requirement_mapping.text import CitedRequirement, resolve_requirement_texts
from specify_cli.review.wp_range import WpReviewRange, resolve_wp_review_range

__all__ = ["cited_requirements", "review_context_inputs"]

_SPEC_FILENAME = "spec.md"


def _spec_text(repo_root: Path, mission_slug: str, owned: OwnedCheckout | None) -> str:
    """The Mission's ``spec.md`` through the placement seam, or ``""`` when it cannot be read."""
    try:
        spec_dir = placement_seam(repo_root, mission_slug, owned=owned).read_dir(MissionArtifactKind.SPEC)
        return (spec_dir / _SPEC_FILENAME).read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError):
        return ""


def cited_requirements(
    repo_root: Path,
    mission_slug: str,
    requirement_refs: Sequence[str],
    *,
    mission_type: str,
    owned: OwnedCheckout | None = None,
) -> tuple[CitedRequirement, ...]:
    """*requirement_refs* resolved against the Mission's spec (an unreadable spec: none declared)."""
    cited: tuple[CitedRequirement, ...] = resolve_requirement_texts(_spec_text(repo_root, mission_slug, owned), list(requirement_refs), mission_type=mission_type)
    return cited


def review_context_inputs(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    *,
    owned_files: Sequence[str],
    requirement_refs: Sequence[str],
    mission_type: str,
    owned: OwnedCheckout | None = None,
) -> tuple[WpReviewRange, tuple[CitedRequirement, ...]]:
    """The review range of *wp_id* and its cited requirements: what the review-context block renders."""
    review_range = resolve_wp_review_range(repo_root, mission_slug, wp_id, owned_files=owned_files, owned=owned)
    cited = cited_requirements(repo_root, mission_slug, requirement_refs, mission_type=mission_type, owned=owned)
    return review_range, cited
