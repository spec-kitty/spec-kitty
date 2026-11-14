"""Tests for the SPDD/REASONS conditional prompt fragment renderer (WP04).

Covers FR-013, FR-014, FR-015, NFR-001 and the renderer contract in
``contracts/prompt-fragment.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.spdd_reasons.template_renderer import (
    REASONS_BLOCK_END,
    REASONS_BLOCK_START,
    UnmatchedReasonsBlockError,
    apply_spdd_blocks_for_project,
    process_spdd_blocks,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]

# Mission doctrine-consumer-surface-missions-extraction-01KZ6G6H (FR-005)
# relocated mission-steps/ from src/charter/offering/missions/mission-steps to
# packs/built-in/missions/mission-steps.
ACTION_TEMPLATES: list[tuple[str, str]] = [
    ("packs/built-in/missions/mission-steps/software-dev/specify/prompt.md", "REASONS Guidance - Specify"),
    ("packs/built-in/missions/mission-steps/software-dev/plan/prompt.md", "REASONS Guidance - Plan"),
    ("packs/built-in/missions/mission-steps/software-dev/tasks/prompt.md", "REASONS Guidance - Tasks"),
    ("packs/built-in/missions/mission-steps/software-dev/implement/prompt.md", "REASONS Guidance - Implement"),
]


def _read_template(name: str) -> str:
    return (REPO_ROOT / name).read_text(encoding="utf-8")


# =============================================================================
# TestProcessSpddBlocks — unit cases for the renderer
# =============================================================================


class TestProcessSpddBlocks:
    """Unit-level behaviour of ``process_spdd_blocks``."""

    def test_active_keeps_content_strips_markers(self) -> None:
        text = f"Header line\n\n{REASONS_BLOCK_START}\n\n### REASONS Guidance - X\n\n- bullet\n\n{REASONS_BLOCK_END}\n\nFooter line\n"
        rendered = process_spdd_blocks(text, active=True)
        assert REASONS_BLOCK_START not in rendered
        assert REASONS_BLOCK_END not in rendered
        assert "### REASONS Guidance - X" in rendered
        assert "- bullet" in rendered
        # Header and footer survive intact.
        assert rendered.startswith("Header line\n")
        assert rendered.endswith("Footer line\n")

    def test_inactive_removes_block_entirely(self) -> None:
        text = f"Header line\n\n{REASONS_BLOCK_START}\n\n### REASONS Guidance - X\n\n- bullet\n\n{REASONS_BLOCK_END}\n\nFooter line\n"
        rendered = process_spdd_blocks(text, active=False)
        assert "spdd:reasons-block" not in rendered
        assert "REASONS Guidance" not in rendered
        assert "- bullet" not in rendered

    def test_inactive_no_extra_blank_line_left(self) -> None:
        """Inactive removal must not introduce or leave behind blank lines."""
        # Pre-feature baseline: header followed by a blank then footer.
        baseline = "Header line\n\nFooter line\n"
        # Author convention: insert a blank + marker block between them.
        with_block = f"Header line\n\n{REASONS_BLOCK_START}\n\n### REASONS Guidance - X\n\n{REASONS_BLOCK_END}\n\nFooter line\n"
        rendered = process_spdd_blocks(with_block, active=False)
        assert rendered == baseline

    def test_unmatched_start_raises(self) -> None:
        text = f"foo\n{REASONS_BLOCK_START}\nno end marker\nbar\n"
        with pytest.raises(UnmatchedReasonsBlockError):
            process_spdd_blocks(text, active=True)
        with pytest.raises(UnmatchedReasonsBlockError):
            process_spdd_blocks(text, active=False)

    def test_unmatched_end_raises(self) -> None:
        text = f"foo\n{REASONS_BLOCK_END}\nbar\n"
        with pytest.raises(UnmatchedReasonsBlockError):
            process_spdd_blocks(text, active=True)

    def test_no_block_present_returns_input_unchanged(self) -> None:
        text = "# Title\n\nSome body text.\n"
        assert process_spdd_blocks(text, active=True) == text
        assert process_spdd_blocks(text, active=False) == text

    def test_project_wrapper_rejects_unmatched_end_marker(self) -> None:
        text = f"Header\n{REASONS_BLOCK_END}\nFooter\n"
        with pytest.raises(UnmatchedReasonsBlockError):
            apply_spdd_blocks_for_project(text, repo_root=None)


# =============================================================================
# TestInactiveBaselineEquivalence — FR-013 + NFR-001
# =============================================================================


def _baseline_for(template_text: str) -> str:
    """Synthesize the pre-WP04 template text by manual marker removal.

    The expected pre-feature template is the current template MINUS the entire
    span ``\\n<blank>\\n<start>\\n...\\n<end>\\n``. This is the canonical
    layout WP04 used when adding the markers, so manually computing it gives
    us a known-good baseline that does NOT use the renderer under test.
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


class TestInactiveBaselineEquivalence:
    """FR-013 / NFR-001: inactive rendering is byte-identical to baseline."""

    @pytest.mark.parametrize("template_name", [t[0] for t in ACTION_TEMPLATES])
    def test_inactive_template_byte_equivalent_to_baseline(self, template_name: str) -> None:
        text = _read_template(template_name)
        # Sanity: each WP04 template carries the marker pair.
        assert REASONS_BLOCK_START in text, f"{template_name} missing start marker"
        assert REASONS_BLOCK_END in text, f"{template_name} missing end marker"

        baseline = _baseline_for(text)
        rendered = process_spdd_blocks(text, active=False)

        assert rendered == baseline, (
            f"Inactive rendering of {template_name} drifted from synthesized "
            f"pre-feature baseline. Diff: rendered_len={len(rendered)}, "
            f"baseline_len={len(baseline)}."
        )
        # And no SPDD residue survives.
        assert "spdd:reasons-block" not in rendered
        # No action-scoped REASONS Guidance content survives in the inactive
        # render — defends NFR-001 in spirit even if synthesis ever drifted.
        assert "REASONS Guidance" not in rendered

# =============================================================================
# TestActiveTemplatesContainBlock — FR-014
# =============================================================================


class TestActiveTemplatesContainBlock:
    """FR-014: active rendering surfaces the action-scoped headline."""

    @pytest.mark.parametrize("template_name,headline", ACTION_TEMPLATES)
    def test_active_template_contains_headline(self, template_name: str, headline: str) -> None:
        text = _read_template(template_name)
        rendered = process_spdd_blocks(text, active=True)
        assert headline in rendered
        # Markers themselves are stripped even when active.
        assert REASONS_BLOCK_START not in rendered
        assert REASONS_BLOCK_END not in rendered
