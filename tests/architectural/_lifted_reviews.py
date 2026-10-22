"""Single home of the SPDD/REASONS review-gate template contract (#5015).

Both ``tests/reviews/test_review_gate_activation.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_reviews.py`` import these tests, so the per-PR gate
runs exactly what the source suite runs and the two cannot drift apart.
"""

from __future__ import annotations

from pathlib import Path

from charter.offering.spdd_reasons.template_renderer import (
    REASONS_BLOCK_END,
    REASONS_BLOCK_START,
    process_spdd_blocks,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
# Mission doctrine-consumer-surface-missions-extraction-01KZ6G6H (FR-005)
# relocated mission-steps/ from src/charter/offering/missions/mission-steps to
# packs/built-in/missions/mission-steps.
REVIEW_TEMPLATE_PATH = REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev" / "review" / "prompt.md"

EIGHT_DRIFT_OUTCOMES = (
    "approved",
    "approved_with_deviation",
    "canvas_update_needed",
    "glossary_update_needed",
    "charter_follow_up",
    "follow_up_mission",
    "scope_drift_block",
    "safeguard_violation_block",
)


def _read_review_template() -> str:
    return REVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")


def _baseline_for(template_text: str) -> str:
    """Synthesize the pre-WP05 ``review.md`` text by manual marker removal.

    Mirrors the ``_baseline_for`` helper in
    ``tests/prompts/test_prompt_fragment_rendering.py``: remove the entire
    ``\\n<blank>\\n<start>...\\n<end>\\n`` span. Author convention places one
    blank line above the start marker, so dropping that blank along with the
    block produces a byte-identical pre-feature baseline.
    """
    lines = template_text.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        if lines[i].strip() == REASONS_BLOCK_START:
            # Drop the immediately preceding blank line, if present.
            if out and out[-1] == "":
                out.pop()
            # Skip lines through the end marker.
            i += 1
            while i < n and lines[i].strip() != REASONS_BLOCK_END:
                i += 1
            i += 1  # consume end marker
            continue
        out.append(lines[i])
        i += 1
    rendered = "\n".join(out)
    if template_text.endswith("\n"):
        rendered += "\n"
    return rendered


# =============================================================================
# TestReviewGateActivation — seven contract cases from contracts/review-gate.md
# =============================================================================


class TestReviewGateActivation:
    """Seven-case contract from ``contracts/review-gate.md``."""

    def test_inactive_review_template_byte_equivalent_to_baseline(self) -> None:
        """FR-018 / NFR-001: inactive rendering matches the synthesized baseline."""
        text = _read_review_template()
        # Sanity: WP05 is supposed to have added the marker pair.
        assert REASONS_BLOCK_START in text, "review.md missing SPDD start marker"
        assert REASONS_BLOCK_END in text, "review.md missing SPDD end marker"

        baseline = _baseline_for(text)
        rendered = process_spdd_blocks(text, active=False)

        assert rendered == baseline, (
            f"Inactive rendering of review.md drifted from synthesized pre-feature baseline. rendered_len={len(rendered)}, baseline_len={len(baseline)}."
        )
        # Defence in depth: no SPDD residue, no REASONS prose.
        assert "spdd:reasons-block" not in rendered
        assert "REASONS Canvas Comparison" not in rendered

    def test_active_review_template_contains_canvas_comparison_headline(self) -> None:
        """FR-015: active rendering surfaces the Canvas Comparison headline."""
        text = _read_review_template()
        rendered = process_spdd_blocks(text, active=True)
        assert "REASONS Canvas Comparison" in rendered
        # Markers themselves are stripped even when active.
        assert REASONS_BLOCK_START not in rendered
        assert REASONS_BLOCK_END not in rendered

    def test_active_review_lists_eight_drift_outcomes(self) -> None:
        """FR-017: every drift outcome name appears in the active block."""
        text = _read_review_template()
        rendered = process_spdd_blocks(text, active=True)
        for outcome in EIGHT_DRIFT_OUTCOMES:
            assert outcome in rendered, f"Active review.md missing drift outcome: {outcome}"

    def test_active_review_mentions_charter_precedence(self) -> None:
        """FR-016: charter directives take precedence over canvas content."""
        text = _read_review_template()
        rendered = process_spdd_blocks(text, active=True)
        # Either form satisfies the contract; the block uses the section
        # heading "Charter precedence" plus a directive sentence.
        assert "Charter precedence" in rendered or "charter directives take precedence" in rendered.lower(), (
            "Active review.md does not mention charter precedence over canvas"
        )

    def test_active_review_instructs_load_canvas(self) -> None:
        """FR-015: reviewer is instructed to load the REASONS canvas."""
        text = _read_review_template()
        rendered = process_spdd_blocks(text, active=True)
        assert "Load the canvas" in rendered
        assert "reasons-canvas.md" in rendered

    def test_active_review_instructs_classify_divergence(self) -> None:
        """FR-017: reviewer is instructed to classify the divergence."""
        text = _read_review_template()
        rendered = process_spdd_blocks(text, active=True)
        assert "Classify the divergence" in rendered

    def test_active_review_instructs_record_outcome(self) -> None:
        """FR-017: reviewer must explicitly name the chosen outcome."""
        text = _read_review_template()
        rendered = process_spdd_blocks(text, active=True)
        assert "Record the outcome" in rendered
