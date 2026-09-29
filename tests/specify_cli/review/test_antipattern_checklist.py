"""ATDD for WP07 (requirement-id-grammar-01M3NRCA): consumer guidance names
the requirement-ID grammar.

WP01-WP05 changed what the tools accept (the four kinds ``FR``, ``NFR``,
``C``, ``SC``; a hyphen; digits; an optional lowercase letter suffix; the
``<mission-slug>#<ID>`` qualified citation; the ``malformed`` /
``unknown_spec_id`` / ``foreign_qualified`` verdicts; success criteria
tracked, not gating). This WP changes the words so the SOURCE spec template,
the tasks-outline and tasks-finalize prompts, and the WP-review anti-pattern
checklist describe that grammar using the names the merged code actually
ships (verified by grep against WP02/WP03/WP05's merged code -- see the
hand-off's Tracer notes).

This file is the RED commit for T033 (the checklist tests) and the
guidance-content non-vacuity proof read by T031/T032. Every guidance case is
expected RED on the lane base: none of the three SOURCE files mention
``<mission-slug>#`` or ``tracked, not gating`` today. Checklist test 1 is
RED on the lane base (today's item 4 is the pre-grammar wording). Checklist
test 3 is a GREEN parity ratchet from this commit onward -- item 4 is
identical in ``antipattern_checklist.py`` and ``review/prompt.md`` before
this WP touches either, and stays identical after T033 edits both in one
commit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from specify_cli.review.antipattern_checklist import (
    render_wp_review_antipattern_checklist,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[3]

_REVIEW_PROMPT = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev" / "review" / "prompt.md"

_SPEC_TEMPLATE = _REPO_ROOT / "packs" / "built-in" / "missions" / "software-dev" / "templates" / "spec-template.md"
_TASKS_FINALIZE_PROMPT = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev" / "tasks-finalize" / "prompt.md"
_TASKS_OUTLINE_PROMPT = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev" / "tasks-outline" / "prompt.md"

#: The eight checklist labels -- used as a positive control proving the
#: checklist render was actually read, not a fixture that happens to satisfy
#: the grammar assertion vacuously.
_CHECKLIST_LABELS = (
    "Dead code",
    "Synthetic-fixture test",
    "Silent empty return",
    "FR coverage",
    "Frozen surface",
    "Locked decision",
    "Shared-file ownership",
    "Production fragility",
)

#: Split a checklist render on its numbered items (``1.`` .. ``8.``), each
#: block running to just before the next numbered item or end of string.
_ITEM_BLOCK_RE = re.compile(r"^\d+\. \*\*.+?(?=^\d+\. \*\*|\Z)", re.DOTALL | re.MULTILINE)


def test_item_4_names_requirement_id_grammar() -> None:
    """Checklist item 4 names the grammar: label, letter suffix, SC kind,
    tracked-not-gated phrasing and the qualified-citation syntax.

    RED on the lane base: today's item 4 has none of the grammar vocabulary.
    """
    text = render_wp_review_antipattern_checklist()

    assert "**FR coverage**" in text
    assert "FR-###a" in text
    assert "SC-###" in text
    assert "tracked, not gated" in text
    assert "<mission-slug>#<ID>" in text


def test_checklist_positive_control_all_labels_present() -> None:
    """Positive control on the same render: all eight labels and the
    heading line are present, proving the probe reads the real checklist so
    ``test_item_4_names_requirement_id_grammar`` is not vacuous.
    """
    text = render_wp_review_antipattern_checklist()

    assert "## Anti-pattern checklist (WP-level cheap version of mission-review)" in text
    for label in _CHECKLIST_LABELS:
        assert f"**{label}**" in text


def test_checklist_parity_with_review_prompt() -> None:
    """Every numbered item block of the checklist render appears verbatim in
    ``review/prompt.md`` section 4a, pinning the two copies together so they
    cannot silently drift apart.

    Green parity ratchet: item 4 is identical in both files before this WP
    edits either, and T033 edits both in one commit -- this test never goes
    red by design.
    """
    rendered = render_wp_review_antipattern_checklist()
    prompt_text = _REVIEW_PROMPT.read_text(encoding="utf-8")

    item_blocks = _ITEM_BLOCK_RE.findall(rendered)
    assert len(item_blocks) == 8, "expected 8 numbered checklist items"

    for block in item_blocks:
        assert block.strip() in prompt_text, f"checklist item drifted from review/prompt.md: {block[:40]!r}"


#: Per-file expectations for the guidance-content non-vacuity test. Each
#: entry names every substring the SOURCE file's target wording (T031/T032)
#: must contain -- the four kinds, the lowercase letter suffix, the
#: qualified-citation syntax, the tracked-not-gating phrasing, and (where the
#: file also carries JSON-shaped guidance) the shipped key/reason names bound
#: in Step 0 -- plus a positive-control string the file already holds today.
_GUIDANCE_EXPECTATIONS: dict[Path, dict[str, object]] = {
    _SPEC_TEMPLATE: {
        "must_contain": (
            "FR-###",
            "NFR-###",
            "C-###",
            "SC-###",
            "lowercase",
            "FR-###a",
            "<mission-slug>#",
            "tracked, not gating",
        ),
        "positive_control": "| FR-EXAMPLE |",
    },
    _TASKS_FINALIZE_PROMPT: {
        "must_contain": (
            "FR, NFR, C or SC",
            "FR-###",
            "SC-###",
            "lowercase",
            "FR-###a",
            "<mission-slug>#",
            "tracked, not gating",
            "parsed_spec_ids",
            "rejected_requirement_refs",
            "success_criteria_coverage",
        ),
        "positive_control": "requirement_refs",
    },
    _TASKS_OUTLINE_PROMPT: {
        "must_contain": (
            "FR/NFR/C/SC",
            "lowercase",
            "FR-###a",
            "<mission-slug>#",
            "tracked, not gating",
            "foreign_qualified",
        ),
        "positive_control": "requirement_refs",
    },
}


@pytest.mark.parametrize(
    "path",
    [_SPEC_TEMPLATE, _TASKS_FINALIZE_PROMPT, _TASKS_OUTLINE_PROMPT],
    ids=["spec-template", "tasks-finalize-prompt", "tasks-outline-prompt"],
)
def test_guidance_names_requirement_id_grammar(path: Path) -> None:
    """The SOURCE spec template, tasks-finalize prompt and tasks-outline
    prompt each describe the requirement-ID grammar: the four kinds, the
    lowercase letter suffix, the qualified-citation syntax, and (where the
    file also carries JSON-shaped guidance) the shipped key/reason names.

    RED on the lane base for every case: none of the three files mention
    ``<mission-slug>#`` or ``tracked, not gating`` today.
    """
    text = path.read_text(encoding="utf-8")
    expectations = _GUIDANCE_EXPECTATIONS[path]

    # Positive control first: proves this read found real content, so a
    # failure below means the grammar wording is missing, not that the file
    # was empty or misread.
    assert expectations["positive_control"] in text

    for needle in expectations["must_contain"]:
        assert needle in text, f"{path.name} does not contain {needle!r}"
