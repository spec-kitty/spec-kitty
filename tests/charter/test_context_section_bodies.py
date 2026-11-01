"""WP04 unit tests — ``render_critical_section_bodies`` (FR-001).

These tests exercise the pure renderer in
``charter.activation.context_renderers.section_bodies`` against the five-row table
in the WP04 task spec (subtask T018).  They pin:

* verbatim section bodies surface when the heading is present;
* missing sections degrade to the fetch + when-doing stanza (no crash);
* action-specific section sets are honoured;
* unknown actions yield no block (empty string).
"""

from __future__ import annotations

import textwrap

import pytest

from charter.activation.context_renderers import (
    CRITICAL_SECTION_WHEN_CLAUSES,
    critical_section_header,
    render_critical_section_bodies,
    render_critical_section_include,
)

pytestmark = pytest.mark.fast


_CHARTER_WITH_ALL_SECTIONS = textwrap.dedent(
    """\
    # Project Charter

    ## Purpose

    Minimal fixture for section-body rendering tests.

    ## Terminology Canon

    - The canonical term for a unit of governed work is **Mission**.
    - ``feature`` is forbidden in canonical, operator, and user-facing language.

    ## Regression Vigilance (2026-04-06)

    When renaming an identifier-bearing term, the reviewer MUST grep the
    diff for the old term and MUST consult ``docs/context/`` before
    approving.

    ## Code Review Checklist

    - The WP diff respects the agent profile's directive-references.
    - Terminology in code and docs aligns with the project glossary.
    """
)

_CHARTER_WITHOUT_REGRESSION_VIGILANCE = textwrap.dedent(
    """\
    # Project Charter

    ## Terminology Canon

    - canonical term is **Mission**.

    ## Code Review Checklist

    - check terminology alignment.
    """
)


_CHARTER_WITH_FENCED_MARKDOWN_HEADINGS = textwrap.dedent(
    """\
    # Project Charter

    ## Terminology Canon

    - canonical term is **Mission**.

    ## Regression Vigilance

    Preserve cleanup instructions around command examples:

    ```bash
    ## STEP 1
    spec-kitty glossary scan
        ```
    ## STEP 2
    spec-kitty glossary validate
    ```

    After cleanup, rerun the mission review.

    ## Code Review Checklist

    - This is the next section and not part of Regression Vigilance.
    """
)


_CHARTER_WITH_FENCED_SECTION_HEADING_EXAMPLE = textwrap.dedent(
    """\
    # Project Charter

    ## Purpose

    A documentation example can mention a critical section heading:

    ```markdown
    ## Regression Vigilance
    This is example text, not the charter rule.
    ```

    ## Terminology Canon

    - canonical term is **Mission**.

    ## Regression Vigilance

    The real rule requires the reviewer to consult docs/context/.

    ## Code Review Checklist

    - check terminology alignment.
    """
)


_CHARTER_WITH_NESTED_CRITICAL_SECTIONS = textwrap.dedent(
    """\
    # Project Charter

    ## Code Quality

    ### Code Review Checklist

    - Tests added for new functionality.
    - Type annotations present.

    ### Quality Gates

    - Required pytest surface passes.

    ## Terminology Canon (Mission vs Feature)

    - canonical term is **Mission**.

    ### Regression Vigilance (2026-04-06)

    Reviewers MUST grep the diff for the old term before approving.

    ## Charter Resolution Hints

    Not part of the critical section.
    """
)


_CHARTER_WITH_UNBALANCED_FENCE = textwrap.dedent(
    """\
    # Project Charter

    ## Terminology Canon

    - canonical term is **Mission**.

    ## Regression Vigilance

    Preserve cleanup instructions around command examples:

    ```bash
    ## STEP 1
    spec-kitty glossary scan

    ## Code Review Checklist

    - This is the next section and must not be swallowed by Regression Vigilance.
    """
)


def _rendered_section_body(rendered: str, heading: str) -> str:
    section_start = rendered.index(f"### {heading}")
    body_start = rendered.index("\n", section_start) + 1
    fetch_start = rendered.index("  Run: spec-kitty charter context --include", body_start)
    return rendered[body_start:fetch_start].rstrip()


class TestVerbatimBodies:
    """Existing headings render their body verbatim under a ``### <heading>`` line."""

    def test_terminology_canon_body_surfaces_verbatim_when_present(self) -> None:
        result = render_critical_section_bodies(
            _CHARTER_WITH_ALL_SECTIONS, action="implement"
        )
        assert critical_section_header("implement") in result
        assert "### Terminology Canon" in result
        # The literal body text must survive intact (whitespace + bullets).
        assert (
            "The canonical term for a unit of governed work is **Mission**"
            in result
        )

    def test_fenced_markdown_headings_do_not_truncate_section_body(self) -> None:
        result = render_critical_section_bodies(
            _CHARTER_WITH_FENCED_MARKDOWN_HEADINGS, action="implement"
        )

        body = _rendered_section_body(result, "Regression Vigilance")

        assert "## STEP 1" in body
        assert "## STEP 2" in body
        assert "After cleanup, rerun the mission review." in body
        assert "This is the next section" not in body

    def test_fenced_section_heading_example_does_not_spoof_section_start(self) -> None:
        result = render_critical_section_bodies(
            _CHARTER_WITH_FENCED_SECTION_HEADING_EXAMPLE, action="implement"
        )

        body = _rendered_section_body(result, "Regression Vigilance")

        assert "consult docs/context/" in body
        assert "This is example text" not in body
        assert "canonical term is **Mission**" not in body
        assert "check terminology alignment" not in body

    def test_unbalanced_fence_does_not_swallow_following_sections(self) -> None:
        result = render_critical_section_bodies(
            _CHARTER_WITH_UNBALANCED_FENCE, action="implement"
        )

        body = _rendered_section_body(result, "Regression Vigilance")

        assert "Preserve cleanup instructions" in body
        assert "```bash" not in body
        assert "## STEP 1" not in body
        assert "This is the next section" not in body
        # The unbalanced fence masks the ``Code Review Checklist`` heading, so
        # only the two headings above the fence resolve and are advertised.
        assert result.count("  Run: spec-kitty charter context --include") == 2
        assert "section:code-review-checklist" not in result

    def test_section_include_ignores_fenced_heading_examples(self) -> None:
        result = render_critical_section_include(
            _CHARTER_WITH_FENCED_SECTION_HEADING_EXAMPLE,
            "regression-vigilance",
        )

        assert result is not None
        assert "consult docs/context/" in result
        assert "This is example text" not in result

    def test_nested_critical_headings_are_recoverable(self) -> None:
        result = render_critical_section_bodies(
            _CHARTER_WITH_NESTED_CRITICAL_SECTIONS,
            action="implement",
        )

        assert "Tests added for new functionality." in result
        assert "Reviewers MUST grep the diff" in result
        assert "Required pytest surface passes." not in result
        assert "Not part of the critical section." not in result

    def test_section_include_recovers_nested_critical_heading(self) -> None:
        result = render_critical_section_include(
            _CHARTER_WITH_NESTED_CRITICAL_SECTIONS,
            "regression-vigilance",
        )

        assert result is not None
        assert result.startswith("### Regression Vigilance")
        assert "Reviewers MUST grep the diff" in result
        assert "Not part of the critical section." not in result

    def test_section_include_gracefully_degrades_on_unbalanced_fence(self) -> None:
        """A heading MASKED by a malformed fence still resolves (FR-010).

        ``Code Review Checklist`` is present in the fixture, but the
        unbalanced ``` ```bash ``` fence above it swallows the rest of the
        document, so the heading scanner never sees it as a section
        boundary — the selector's target is masked, not absent. WP05
        removes the "never return None" dead-end for recognized critical
        slugs, so this now resolves to a non-``None`` string instead of
        signalling failure.

        Only non-``None``/``str`` is asserted here — NOT the exact
        placeholder wording. The "has not yet authored" copy is honest for
        a genuinely *absent* heading but is imprecise for this *masked*
        case (the section exists, it just isn't parseable past the
        unbalanced fence); asserting that exact text would be brittle and
        slightly misleading. Flag for reviewer: whether a masked heading
        deserves a distinct message from an absent one is an open
        follow-up question — no fence-reparse logic is added here
        (out of scope for this subtask).
        """
        result = render_critical_section_include(
            _CHARTER_WITH_UNBALANCED_FENCE,
            "code-review-checklist",
        )

        assert result is not None
        assert isinstance(result, str)


class TestMissingSectionIsNotAdvertised:
    """A heading the charter does not carry is not action-critical (#6968)."""

    def test_missing_section_is_not_advertised(self) -> None:
        result = render_critical_section_bodies(
            _CHARTER_WITHOUT_REGRESSION_VIGILANCE, action="implement"
        )
        # The heading the fixture omits contributes neither a marker nor a
        # selector: advertising it would send the agent to a placeholder.
        assert "section:regression-vigilance" not in result
        assert "### Regression Vigilance" not in result
        assert f"When you {CRITICAL_SECTION_WHEN_CLAUSES['Regression Vigilance']}" not in result
        # No crash means the resolved headings still rendered, with their
        # contract when-doing clause and their recovery stanza.
        assert critical_section_header("implement") in result
        assert "section:terminology-canon" in result
        assert "section:code-review-checklist" in result
        assert f"When you {CRITICAL_SECTION_WHEN_CLAUSES['Terminology Canon']}" in result

    def test_no_resolving_heading_emits_no_block(self) -> None:
        result = render_critical_section_bodies(
            "# Consumer Charter\n\n## Purpose\n\nShip a small CLI.\n",
            action="implement",
        )
        assert result == ""

    def test_empty_bodied_heading_is_not_advertised(self) -> None:
        result = render_critical_section_bodies(
            "# Charter\n\n## Terminology Canon\n\n## Code Review Checklist\n\n- check.\n",
            action="implement",
        )
        assert "section:terminology-canon" not in result
        assert "section:code-review-checklist" in result


class TestActionSectionSets:
    """The set of critical sections is action-scoped."""

    def test_action_implement_uses_implement_section_set(self) -> None:
        result = render_critical_section_bodies(
            _CHARTER_WITH_ALL_SECTIONS, action="implement"
        )
        for heading in ("Terminology Canon", "Code Review Checklist", "Regression Vigilance"):
            assert f"### {heading}" in result

    def test_action_review_uses_review_section_set(self) -> None:
        result = render_critical_section_bodies(
            _CHARTER_WITH_ALL_SECTIONS, action="review"
        )
        for heading in ("Terminology Canon", "Code Review Checklist", "Regression Vigilance"):
            assert f"### {heading}" in result

    def test_unknown_action_emits_no_section(self) -> None:
        result = render_critical_section_bodies(
            _CHARTER_WITH_ALL_SECTIONS, action="unknown-action"
        )
        assert result == ""
