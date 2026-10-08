"""Behavior of the changelog `## [Unreleased]` style guard (issue #5426, part 2).

Each rule has planted-violation tests, each exemption has a positive test, and every planted
case renders an actionable finding (FR-012). Text is fed to `check()` as a string, so no test
touches the real changelog except the ones that say so.
"""

from __future__ import annotations

from dataclasses import dataclass
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from scripts.docs.check_changelog_style import (
    Finding,
    ParsedSection,
    check,
    format_finding,
    main,
    parse_section,
)
from scripts.release.validate_release import unreleased_section

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# The Unreleased heading is line 3, so body line k (1-based) sits on file line 3 + k.
_HEADER = "# Changelog\n\n## [Unreleased] - 4.0.0rc5\n"
_HEADING_LINE = 3


def doc(*body: str) -> str:
    """Wrap *body* lines in a changelog whose Unreleased heading is on line 3."""
    return _HEADER + "\n".join(body) + "\n"


def parsed(*body: str) -> ParsedSection:
    section = unreleased_section(doc(*body))
    assert section is not None
    return parse_section(section)


# ---------------------------------------------------------------------------
# T002: the entry parser
# ---------------------------------------------------------------------------


def test_entries_split_at_top_level_bullets() -> None:
    result = parsed("### Fixed", "", "- **A** first", "- **B** second")

    assert [entry.headline for entry in result.entries] == ["A", "B"]
    assert [entry.line for entry in result.entries] == [_HEADING_LINE + 3, _HEADING_LINE + 4]


def test_continuation_lines_join_their_entry() -> None:
    result = parsed("### Fixed", "- **A** first", "still the same entry", "- **B** next")

    assert result.entries[0].lines == ("- **A** first", "still the same entry")
    assert result.entries[1].lines == ("- **B** next",)


def test_nested_items_are_kept_apart_from_the_parent() -> None:
    result = parsed(
        "### Changed",
        "- **A** parent",
        "  - nested one",
        "    wrapped",
        "  - nested two",
        "    - deeper belongs to nested two",
    )

    entry = result.entries[0]
    assert entry.lines == ("- **A** parent",)
    assert entry.nested == (
        ("  - nested one", "    wrapped"),
        ("  - nested two", "    - deeper belongs to nested two"),
    )
    assert entry.nested_lines == (_HEADING_LINE + 3, _HEADING_LINE + 5)


def test_section_and_subsection_are_tracked() -> None:
    result = parsed(
        "### Fixed",
        "#### Consolidation",
        "- **A** in a subsection",
        "### Internal",
        "- plain internal bullet",
    )

    first, second = result.entries
    assert (first.section, first.subsection) == ("Fixed", "Consolidation")
    assert (second.section, second.subsection) == ("Internal", None)


def test_entry_line_is_the_real_file_line() -> None:
    text = doc("### Added", "- **A**")
    real_line = text.splitlines().index("- **A**") + 1

    section = unreleased_section(text)
    assert section is not None
    assert parse_section(section).entries[0].line == real_line


def test_preamble_is_captured_separately_with_real_line_numbers() -> None:
    result = parsed("", "_Changes in the release._", "", "Intro paragraph.", "### Added", "- **A**")

    assert result.preamble == (
        (_HEADING_LINE + 1, ""),
        (_HEADING_LINE + 2, "_Changes in the release._"),
        (_HEADING_LINE + 3, ""),
        (_HEADING_LINE + 4, "Intro paragraph."),
    )
    assert [(h.level, h.text, h.line) for h in result.headings] == [(3, "Added", _HEADING_LINE + 5)]
    assert len(result.entries) == 1


def test_headline_is_the_text_inside_the_leading_bold() -> None:
    result = parsed("### Added", "- **A `code` headline** (#1). Body.", "- no bold here")

    assert result.entries[0].headline == "A `code` headline"
    assert result.entries[1].headline is None


def test_headings_inside_a_fenced_block_are_not_headings() -> None:
    result = parsed("### Added", "- **A** example:", "```", "### Not a heading", "```")

    assert [h.text for h in result.headings] == ["Added"]
    assert len(result.entries) == 1


def test_a_bullet_before_the_first_heading_belongs_to_the_preamble() -> None:
    result = parsed("", "- a preamble bullet", "### Added", "- **A** (#1).")

    assert (_HEADING_LINE + 2, "- a preamble bullet") in result.preamble
    assert [entry.headline for entry in result.entries] == ["A"]


def test_text_without_an_unreleased_section_has_no_findings() -> None:
    assert check("# Changelog\n\n## [4.0.0rc4] - 2026-09-20\n\n- old FR-011 text\n") == []


# ---------------------------------------------------------------------------
# T002: findings, rendering and the command line
# ---------------------------------------------------------------------------


def test_clean_section_has_no_findings() -> None:
    assert check(doc("### Added", "- **A thing** (#1). It works.")) == []


def test_findings_are_sorted_by_path_line_rule() -> None:
    finding_a = Finding("error", "b-rule", "p.md", 5, "w", "f")
    finding_b = Finding("error", "a-rule", "p.md", 5, "w", "f")
    finding_c = Finding("error", "z-rule", "p.md", 2, "w", "f")

    assert sorted([finding_a, finding_b, finding_c], key=lambda f: f.sort_key) == [finding_c, finding_b, finding_a]


def test_error_finding_renders_path_line_rule_where_and_fix() -> None:
    finding = Finding("error", "heading-order", "docs/changelog/CHANGELOG.md", 40, "[Added] ### Added", "Move it.")

    assert format_finding(finding) == "docs/changelog/CHANGELOG.md:40: [heading-order] [Added] ### Added — Move it."


def test_warning_finding_is_prefixed() -> None:
    finding = Finding("warning", "length-warning", "c.md", 7, "[Fixed] A", "Shorten.")

    assert format_finding(finding).startswith("warning: c.md:7: [length-warning]")


def test_main_reports_a_clean_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(doc("### Added", "- **A thing** (#1). It works."), encoding="utf-8")

    assert main(["--changelog", str(path)]) == 0
    assert "0 error(s), 0 warning(s)" in capsys.readouterr().out


def test_main_without_an_unreleased_section_is_a_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text("# Changelog\n\n## [4.0.0rc4] - 2026-09-20\n\n- old\n", encoding="utf-8")

    assert main(["--changelog", str(path)]) == 0
    assert "no [Unreleased] section found; nothing to check" in capsys.readouterr().out


def test_main_on_a_missing_file_is_a_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--changelog", str(tmp_path / "absent.md")]) == 2
    assert capsys.readouterr().err != ""


def test_main_on_an_unknown_option_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--no-such-option"]) == 2
    assert capsys.readouterr().err != ""


# ---------------------------------------------------------------------------
# Planted violations: one table shared by the per-rule tests and by the FR-012 test.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Planted:
    """A planted violation and what its finding must say."""

    name: str
    body: tuple[str, ...]
    rule: str
    line: int  # real file line the finding must point at
    section: str  # the "[section]" the message must name
    excerpt: str | None  # a piece of the entry headline the message must quote, if any
    fix: str  # a fragment of the concrete fix the message must give


PLANTED: list[Planted] = []

_ORDER_FIX = "required order: Breaking, Upgrade Notes, Added, Changed, Fixed, Internal."

PLANTED += [
    Planted(
        "duplicate-heading",
        ("### Fixed", "- **A** (#1). Short.", "### Fixed", "- **B** (#2). Short."),
        "heading-duplicate",
        _HEADING_LINE + 3,
        "Fixed",
        None,
        "Merge this `### Fixed` into the earlier one at line 4.",
    ),
    Planted(
        "out-of-order-heading",
        ("### Changed", "- **A** (#1). Short.", "### Added", "- **B** (#2). Short."),
        "heading-order",
        _HEADING_LINE + 3,
        "Added",
        None,
        f"Move `### Added` above `### Changed`; {_ORDER_FIX}",
    ),
    Planted(
        "unknown-heading",
        ("### Security", "- **A** (#1). Short."),
        "heading-unknown",
        _HEADING_LINE + 1,
        "Security",
        None,
        "Use one of: Breaking, Upgrade Notes, Added, Changed, Fixed, Internal.",
    ),
    Planted(
        "subheading-outside-fixed",
        ("### Changed", "#### Sub", "- **A** (#1). Short."),
        "subheading-placement",
        _HEADING_LINE + 2,
        "Sub",
        None,
        "only under `### Fixed`",
    ),
    Planted(
        "duplicate-subheading",
        ("### Fixed", "#### Sub", "- **A** (#1). Short.", "#### Sub", "- **B** (#2). Short."),
        "heading-duplicate",
        _HEADING_LINE + 4,
        "Sub",
        None,
        "Merge this `#### Sub` into the earlier one at line 5.",
    ),
]


_PADDING = " ".join(["This sentence exists only to add length."] * 10)  # 10 sentences, 409 characters

PLANTED += [
    Planted(
        "headline-missing",
        ("### Changed", "- No bold headline here (#1). Short."),
        "headline-missing",
        _HEADING_LINE + 2,
        "Changed",
        "No bold headline here",
        "Start the entry with a bold headline: `- **What changed** (#1234).`",
    ),
    Planted(
        "refs-in-bold",
        ("### Fixed", "- **Handle the crash (#1234)**. Short."),
        "refs-in-bold",
        _HEADING_LINE + 2,
        "Fixed",
        "Handle the crash",
        "Move `(#1234)` out of the bold headline: `- **Headline** (#1234).`",
    ),
    Planted(
        "contrast-missing-long-fixed",
        ("### Fixed", f"- **Long entry** (#1). {_PADDING}"),
        "contrast-missing",
        _HEADING_LINE + 2,
        "Fixed",
        "Long entry",
        "Add a `**Before:**` sentence describing the old behavior",
    ),
    Planted(
        "contrast-missing-why-without-after",
        ("### Breaking", f"- **Rename it** (#1). **Why:** clearer. {_PADDING}"),
        "contrast-missing",
        _HEADING_LINE + 2,
        "Breaking",
        "Rename it",
        "or shorten the body to at most 2 sentences / 300 characters",
    ),
    Planted(
        "internal-two-lines",
        ("### Internal", "- First line of an internal note", "  and a second physical line."),
        "internal-shape",
        _HEADING_LINE + 2,
        "Internal",
        "First line of an internal note",
        "Keep Internal entries to one line; move user-visible detail to Changed or Fixed.",
    ),
    Planted(
        "internal-nested-item",
        ("### Internal", "- **Internal with a list**", "  - nested item"),
        "internal-shape",
        _HEADING_LINE + 2,
        "Internal",
        "Internal with a list",
        "Keep Internal entries to one line",
    ),
    Planted(
        "internal-before-contrast",
        ("### Internal", "- **Internal rework** **Before:** the old way."),
        "internal-shape",
        _HEADING_LINE + 2,
        "Internal",
        "Internal rework",
        "Keep Internal entries to one line",
    ),
]


_TOKEN_ENTRY = "- **Fix the thing** (#1). "

_BOILERPLATE_FIX = "Delete the boilerplate; the section heading already says it is a fix."
_REQUIREMENT_FIX = "Describe the behavior instead of citing internal requirement `FR-011`"
_CAPS_FIX = "Write `default`/`refuses`/`fails` in lowercase prose, or put the literal CLI token in backticks."
_MERGE_FIX = "Use `spec-kitty consolidate`; `spec-kitty merge` was renamed (only the rename entry may name it)."


def _token_case(name: str, sentence: str, fix: str) -> Planted:
    return Planted(name, ("### Fixed", _TOKEN_ENTRY + sentence), "banned-token", _HEADING_LINE + 2, "Fixed", "Fix the thing", fix)


PLANTED += [
    _token_case("boilerplate-semicolon", "Bug-fix; no CLI version bump.", _BOILERPLATE_FIX),
    _token_case("boilerplate-em-dash", "Bug-fix \u2014 no CLI version bump.", _BOILERPLATE_FIX),
    _token_case("requirement-id", "Implements FR-011 fully.", _REQUIREMENT_FIX),
    _token_case("ulid-in-code-span", "Event `DM-01M3EC2FMWKCKGSBX1QHC7GFCJ` was lost.", "Remove the mission/event ULID; link the issue instead."),
    _token_case("evidence-path", "See .kittify/evidence/run-1.json for details.", "Remove the local evidence path; it is not reachable by users."),
    _token_case("planning-ref", "Tracked in planning#123.", "Remove the private planning-repo reference."),
    _token_case("all-caps-refuse", "It now REFUSE early.", _CAPS_FIX),
    _token_case("all-caps-default", "The DEFAULT changed.", _CAPS_FIX),
    _token_case("all-caps-fail", "A bad input can FAIL quietly.", _CAPS_FIX),
    _token_case("retired-command-in-code-span", "Run `spec-kitty merge --resume` again.", _MERGE_FIX),
    Planted(
        "preamble-requirement-id",
        ("", "Intro paragraph mentioning FR-011.", "### Added", "- **A** (#1)."),
        "banned-token",
        _HEADING_LINE + 2,
        "preamble",
        "Intro paragraph",
        _REQUIREMENT_FIX,
    ),
    Planted(
        "preamble-retired-command",
        ("", "The old spec-kitty merge command stays.", "### Added", "- **A** (#1)."),
        "banned-token",
        _HEADING_LINE + 2,
        "preamble",
        "The old spec-kitty merge",
        _MERGE_FIX,
    ),
]


_LONG_PREFIX = "- **Long** (#1). "


def _entry_of_length(length: int, filler: str = "x") -> str:
    """A single-line Added entry of exactly *length* code points."""
    return _LONG_PREFIX + filler * (length - len(_LONG_PREFIX))


PLANTED += [
    Planted(
        "length-over-limit",
        ("### Added", _entry_of_length(1201)),
        "length",
        _HEADING_LINE + 2,
        "Added",
        "Long",
        "Entry is 1201 characters (limit 1,200); split it or move detail to the docs.",
    ),
]


def _matching(case: Planted) -> list[Finding]:
    return [f for f in check(doc(*case.body)) if f.rule == case.rule and f.line == case.line]


def _case_ids(cases: list[Planted]) -> list[str]:
    return [case.name for case in cases]


def _rules(*body: str) -> list[str]:
    return [finding.rule for finding in check(doc(*body))]


@pytest.mark.parametrize("case", PLANTED, ids=_case_ids(PLANTED))
def test_planted_violation_is_reported_with_its_fix(case: Planted) -> None:
    findings = _matching(case)

    assert findings, f"{case.rule} not reported at line {case.line}: {check(doc(*case.body))}"
    assert case.fix in findings[0].fix
    assert findings[0].severity == "error"


@pytest.mark.parametrize("case", PLANTED, ids=_case_ids(PLANTED))
def test_every_failure_message_is_actionable(case: Planted) -> None:
    """FR-012: the rendered line names the entry (section + headline excerpt) and the exact fix."""
    findings = _matching(case)

    assert findings
    rendered = format_finding(findings[0])
    assert f"[{case.section}]" in rendered
    if case.excerpt is not None:
        assert case.excerpt in rendered
    assert case.fix in rendered


# ---------------------------------------------------------------------------
# T003: heading rules (FR-008)
# ---------------------------------------------------------------------------


def test_a_duplicate_heading_is_reported_once_and_not_as_out_of_order() -> None:
    assert _rules("### Changed", "- **A** (#1). Short.", "### Changed", "- **B** (#2). Short.") == ["heading-duplicate"]


def test_an_out_of_order_heading_is_reported_once() -> None:
    assert _rules("### Fixed", "- **A** (#1). Short.", "### Added", "- **B** (#2). Short.") == ["heading-order"]


def test_all_six_headings_in_order_pass() -> None:
    body = (
        "### Breaking",
        "- **A** (#1). Short.",
        "### Upgrade Notes",
        "- **B** (#2). Short.",
        "### Added",
        "- **C** (#3).",
        "### Changed",
        "- **D** (#4). Short.",
        "### Fixed",
        "- **E** (#5). Short.",
        "### Internal",
        "- a plain one-line entry (#6).",
    )

    assert _rules(*body) == []


def test_an_empty_section_and_skipped_headings_pass() -> None:
    assert _rules("### Added", "", "### Fixed", "- **A** (#1). Short.") == []


def test_distinct_subheadings_under_fixed_pass() -> None:
    assert _rules("### Fixed", "#### One", "- **A** (#1). Short.", "#### Two", "- **B** (#2). Short.") == []


def test_a_subheading_before_any_section_is_misplaced() -> None:
    assert _rules("#### Orphan", "### Fixed", "- **A** (#1). Short.") == ["subheading-placement"]


# ---------------------------------------------------------------------------
# T004: entry-shape rules (FR-009, research R-4)
# ---------------------------------------------------------------------------


def test_unclosed_bold_is_not_a_headline() -> None:
    assert _rules("### Added", "- **Never closed (#1). Short.") == ["headline-missing"]


def test_added_and_upgrade_notes_still_need_a_bold_headline() -> None:
    assert _rules("### Upgrade Notes", "- plain text.") == ["headline-missing"]
    assert _rules("### Added", "- plain text.") == ["headline-missing"]


def test_internal_entries_may_be_plain_bullets() -> None:
    assert _rules("### Internal", "- a plain one-line bullet (#1).") == []


def test_internal_entries_may_carry_a_bold_headline() -> None:
    assert _rules("### Internal", "- **Guard the thing** (#1).") == []


def test_refs_inside_bold_fail_but_code_spans_inside_bold_do_not() -> None:
    """Same fixture, two shapes: only the reference outside a code span is refused."""
    assert _rules("### Added", "- **Fix `WP##` and `#5100` handling (#12)**.") == ["refs-in-bold"]
    assert _rules("### Added", "- **Fix `WP##` and `#5100` handling** (#12).") == []


def test_cross_repo_refs_outside_the_bold_pass() -> None:
    assert _rules("### Fixed", "- **A thing** (#4990, spec-kitty/spec-kitty-events#69). Short.") == []


def test_an_entry_without_refs_passes() -> None:
    assert _rules("### Fixed", "- **A thing without any reference.** Short.") == []


def test_a_long_body_with_before_passes_contrast() -> None:
    assert _rules("### Fixed", f"- **A** (#1). **Before:** old way. {_PADDING}") == []


def test_a_long_body_with_why_and_after_passes_contrast() -> None:
    assert _rules("### Breaking", f"- **A** (#1). **Why:** clearer. **After:** new. {_PADDING}") == []


def test_a_short_body_passes_contrast_without_markers() -> None:
    body = "It now works. It is faster."  # 2 sentences, well under 300 characters
    assert _rules("### Fixed", f"- **A** (#1). {body}") == []


def test_the_same_long_entry_passes_once_cut_to_two_short_sentences() -> None:
    """Same entry, two bodies: 10 sentences fails, 2 short sentences passes."""
    assert _rules("### Changed", f"- **A** (#1). {_PADDING}") == ["contrast-missing"]
    assert _rules("### Changed", "- **A** (#1). First sentence here. Second sentence here.") == []


def test_three_short_sentences_fail_contrast() -> None:
    assert _rules("### Fixed", "- **A** (#1). One. Two. Three.") == ["contrast-missing"]


def test_two_sentences_over_300_characters_fail_contrast() -> None:
    body = "x" * 200 + ". " + "y" * 150 + "."
    assert _rules("### Fixed", f"- **A** (#1). {body}") == ["contrast-missing"]


def test_the_contrast_body_boundary_is_300_characters() -> None:
    assert _rules("### Fixed", "- **A** (#1). " + "x" * 299 + ".") == []
    assert _rules("### Fixed", "- **A** (#1). " + "x" * 300 + ".") == ["contrast-missing"]


def test_a_headline_only_entry_passes_contrast() -> None:
    assert _rules("### Fixed", "- **A short fix.** (#1)") == []


def test_contrast_is_not_required_for_added_or_upgrade_notes() -> None:
    assert _rules("### Added", f"- **A** (#1). {_PADDING}") == []
    assert _rules("### Upgrade Notes", f"- **A** (#1). {_PADDING}") == []


def test_contrast_applies_inside_a_fixed_subsection() -> None:
    assert _rules("### Fixed", "#### Group", f"- **A** (#1). {_PADDING}") == ["contrast-missing"]


def test_a_dotted_version_is_not_a_sentence_break() -> None:
    assert _rules("### Fixed", "- **A** (#1). Contract 1.8.0 adds fields. It is additive.") == []


def test_entries_in_an_unknown_section_get_no_shape_rules() -> None:
    assert _rules("### Security", "- plain text without a headline.") == ["heading-unknown"]


# ---------------------------------------------------------------------------
# T005: banned tokens (FR-010)
# ---------------------------------------------------------------------------

_LIVE_CHANGELOG: Final[Path] = Path(__file__).resolve().parents[2] / "docs" / "changelog" / "CHANGELOG.md"
# Content-dependent positive controls run on this frozen copy, never on the live file: the live
# Unreleased section is emptied by every release cut and trimmed by ordinary edits.
_POST_REWRITE_FIXTURE: Final[Path] = Path(__file__).parent / "fixtures" / "changelog_unreleased_post_rewrite.md"


def _token_findings(text: str) -> list[Finding]:
    return [finding for finding in check(text) if finding.rule == "banned-token"]


def test_the_banned_token_is_named_in_the_finding() -> None:
    (finding,) = _token_findings(doc("### Fixed", _TOKEN_ENTRY + "Implements FR-011 fully."))

    assert "FR-011" in finding.where


def test_a_requirement_id_in_backticks_passes_and_a_bare_one_fails() -> None:
    """Same fixture, two shapes: the code-span exemption is what separates them."""
    assert _rules("### Fixed", _TOKEN_ENTRY + "Quotes `FR-002.3` from the output.") == []
    assert _rules("### Fixed", _TOKEN_ENTRY + "Quotes FR-002.3 from the output.") == ["banned-token"]


@pytest.mark.parametrize("token", ["FR-1", "NFR-12", "SC-3", "C-002", "D-7", "FR-006a", "FR-002.3"])
def test_every_requirement_id_shape_is_banned(token: str) -> None:
    assert _rules("### Fixed", _TOKEN_ENTRY + f"Mentions {token} here.") == ["banned-token"]


def test_all_caps_words_in_backticks_or_inside_identifiers_pass() -> None:
    assert _rules("### Fixed", _TOKEN_ENTRY + "The `FAIL` verdict is unchanged.") == []
    assert _rules("### Fixed", _TOKEN_ENTRY + "It reports PLAN_SETUP_FAILED for that.") == []
    assert _rules("### Fixed", _TOKEN_ENTRY + "It uses the default branch and refuses early.") == []


def test_a_ulid_is_banned_in_bare_text_too() -> None:
    assert _rules("### Fixed", _TOKEN_ENTRY + "Mission 01M3EC2FMWKCKGSBX1QHC7GFCJ was lost.") == ["banned-token"]


def test_a_25_character_id_is_not_a_ulid() -> None:
    assert _rules("### Fixed", _TOKEN_ENTRY + "Id 01M3EC2FMWKCKGSBX1QHC7GFC is short.") == []


def test_a_merge_driver_command_is_not_the_retired_command() -> None:
    assert _rules("### Fixed", _TOKEN_ENTRY + "Run `spec-kitty merge-driver-traces` again.") == []


def test_the_retired_command_is_allowed_in_an_entry_that_also_names_consolidate() -> None:
    entry = _TOKEN_ENTRY + "Renamed from `spec-kitty merge` to `spec-kitty consolidate`."
    assert _rules("### Fixed", entry) == []


def test_banned_tokens_apply_to_internal_entries() -> None:
    assert _rules("### Internal", "- Bug-fix; no CLI version bump (#1).") == ["banned-token"]


def test_a_token_on_a_continuation_line_reports_that_line() -> None:
    findings = _token_findings(doc("### Fixed", _TOKEN_ENTRY + "Short.", "Mentions FR-011 here."))

    assert [finding.line for finding in findings] == [_HEADING_LINE + 3]


def test_a_token_in_a_nested_item_reports_the_nested_line() -> None:
    findings = _token_findings(doc("### Fixed", _TOKEN_ENTRY + "**Before:** old.", "  - nested mentions FR-011"))

    assert [finding.line for finding in findings] == [_HEADING_LINE + 3]


def _fixture_with_new_fixed_entry(sentence: str) -> tuple[str, int]:
    """The frozen post-rewrite section with one Fixed entry planted right under its `### Fixed` heading."""
    lines = _POST_REWRITE_FIXTURE.read_text(encoding="utf-8").splitlines()
    heading = lines.index("### Fixed")
    lines[heading + 1 : heading + 1] = ["", _TOKEN_ENTRY + sentence]
    return "\n".join(lines) + "\n", heading + 3  # 1-based line of the planted entry


def test_the_rename_exemption_is_scoped_to_the_entry_not_the_section() -> None:
    """Plant into the frozen section, whose preamble already names `spec-kitty consolidate`."""
    frozen = _POST_REWRITE_FIXTURE.read_text(encoding="utf-8")
    assert "spec-kitty consolidate" in frozen.split("### Breaking")[0], "the frozen preamble must name the rename"

    bare, line = _fixture_with_new_fixed_entry("`spec-kitty merge --resume` now continues.")
    renamed, _ = _fixture_with_new_fixed_entry("`spec-kitty merge --resume` now continues (use `spec-kitty consolidate --resume`).")

    assert [f.line for f in _token_findings(bare)] == [line]
    assert _token_findings(renamed) == []


def test_a_preamble_paragraph_is_judged_on_its_own_for_the_rename_exemption() -> None:
    paired = doc("", "Renamed: `spec-kitty merge` is now `spec-kitty consolidate`.", "", "### Added", "- **A** (#1).")
    apart = doc("", "It is now `spec-kitty consolidate`.", "", "The old spec-kitty merge stays.", "", "### Added", "- **A** (#1).")

    assert _token_findings(paired) == []
    assert [f.line for f in _token_findings(apart)] == [_HEADING_LINE + 4]


# ---------------------------------------------------------------------------
# Guard bypasses: prose before the first bullet, and non-`-` bullet markers
# ---------------------------------------------------------------------------


def test_prose_between_a_heading_and_its_first_bullet_gets_the_banned_token_checks() -> None:
    body = ("### Fixed", "", "Bug-fix; no CLI version bump. FR-011 is now honored.", "", "- **A** (#1). Short.")

    findings = _token_findings(doc(*body))

    assert {f.where.split("(token: ")[1].rstrip(")") for f in findings} == {"Bug-fix; no CLI version bump", "FR-011"}
    assert {f.line for f in findings} == {_HEADING_LINE + 3}
    assert all(f.where.startswith("[Fixed] ") for f in findings)


def test_orphan_prose_under_a_subheading_is_checked_too() -> None:
    findings = _token_findings(doc("### Fixed", "#### Merge", "The engine FAILS quietly (FR-2).", "- **A** (#1). Short."))

    assert [f.line for f in findings] == [_HEADING_LINE + 3]


def test_clean_prose_between_a_heading_and_its_first_bullet_passes() -> None:
    assert check(doc("### Fixed", "", "Everything below is a fix.", "", "- **A** (#1). Short.")) == []


def test_a_star_bullet_is_a_bullet_marker_error_not_silently_ignored() -> None:
    findings = check(doc("### Fixed", "", "* no headline FR-7 bullet."))

    assert [f.rule for f in findings] == ["banned-token", "bullet-marker"]
    marker = findings[1]
    assert (marker.severity, marker.line) == ("error", _HEADING_LINE + 3)
    assert marker.fix == "Use `- ` for changelog entries."
    assert marker.where.startswith("[Fixed] ")


@pytest.mark.parametrize("marker", ["*", "+"])
def test_star_and_plus_bullets_are_flagged_after_an_entry_and_in_the_preamble(marker: str) -> None:
    after_entry = check(doc("### Added", "- **A** (#1). Short.", f"{marker} **B** (#2). Short."))
    in_preamble = check(doc("", f"{marker} stray bullet", "### Added", "- **A** (#1). Short."))

    assert [f.rule for f in after_entry if f.rule == "bullet-marker"] == ["bullet-marker"]
    assert [f.line for f in in_preamble if f.rule == "bullet-marker"] == [_HEADING_LINE + 2]
    assert "[preamble]" in [f.where for f in in_preamble if f.rule == "bullet-marker"][0]


def test_emphasis_and_fenced_stars_are_not_bullet_markers() -> None:
    body = ("### Added", "- **A** (#1). Short.", "  * indented continuation", "```", "* code, not a bullet", "```", "*italic* text")

    assert [f.rule for f in check(doc(*body)) if f.rule == "bullet-marker"] == []


# ---------------------------------------------------------------------------
# Leftover merge-conflict markers (#5906)
# ---------------------------------------------------------------------------


def _conflict_findings(*body: str) -> list[Finding]:
    return [finding for finding in check(doc(*body)) if finding.rule == "conflict-marker"]


@pytest.mark.parametrize("marker", ["<<<<<<< HEAD", "||||||| parent of abc123 (docs: x)", ">>>>>>> feature", "<<<<<<<", ">>>>>>>"])
def test_a_conflict_marker_line_is_an_error_with_its_file_line(marker: str) -> None:
    findings = _conflict_findings("### Fixed", "- **A** (#1). Short.", marker, "- **B** (#2). Short.")

    assert [(f.severity, f.line) for f in findings] == [("error", _HEADING_LINE + 3)]
    assert findings[0].where.startswith("[Unreleased] ")
    assert findings[0].fix.startswith("Resolve the merge conflict")


def test_a_full_diff3_conflict_flags_every_marker_including_the_divider() -> None:
    body = ("### Fixed", "<<<<<<< HEAD", "- **A** (#1). Ours.", "||||||| base", "- **A** (#1). Base.", "=======", "- **A** (#1). Theirs.", ">>>>>>> topic")

    assert [f.line for f in _conflict_findings(*body)] == [_HEADING_LINE + 2, _HEADING_LINE + 4, _HEADING_LINE + 6, _HEADING_LINE + 8]


def test_a_bare_divider_outside_a_conflict_is_a_heading_underline_not_a_finding() -> None:
    assert _conflict_findings("### Fixed", "- **A** (#1). Short.", "=======", "- **B** (#2). Short.") == []


def test_the_divider_is_only_flagged_while_a_conflict_is_open() -> None:
    body = ("### Fixed", "||||||| base", "=======", ">>>>>>> topic", "=======")

    assert [f.line for f in _conflict_findings(*body)] == [_HEADING_LINE + 2, _HEADING_LINE + 3, _HEADING_LINE + 4]


def test_marker_lookalikes_are_not_flagged() -> None:
    body = ("### Fixed", "- **A** (#1). Uses `<<<<<<< HEAD` markers.", "  <<<<<<< indented", "<<<<<< six", "||||||||x eight", ">>>>>>>>x eight")

    assert _conflict_findings(*body) == []


def test_conflict_markers_inside_a_fenced_block_are_allowed() -> None:
    body = ("### Fixed", "- **A** (#1). Short.", "```", "<<<<<<< HEAD", "||||||| base", "=======", ">>>>>>> topic", "```")

    assert _conflict_findings(*body) == []


def test_the_issue_5906_shape_is_caught() -> None:
    body = (
        "### Fixed",
        "- **A** (#1). Short.",
        "||||||| parent of c86dde6c34 (docs(changelog): owned checkouts no longer block each other (#5894))",
        "- **B** (#2). Short.",
        "||||||| parent of 4045be80cd (docs(changelog): commit-scope fixes for #5443)",
    )

    assert [f.line for f in _conflict_findings(*body)] == [_HEADING_LINE + 3, _HEADING_LINE + 5]


# ---------------------------------------------------------------------------
# T006: length (FR-011)
# ---------------------------------------------------------------------------


def _length_findings(*body: str) -> list[Finding]:
    return [finding for finding in check(doc(*body)) if finding.rule.startswith("length")]


def test_an_entry_of_1200_code_points_passes_and_1201_fails() -> None:
    assert [f.rule for f in _length_findings("### Added", _entry_of_length(1200))] == ["length-warning"]
    assert [f.rule for f in _length_findings("### Added", _entry_of_length(1201))] == ["length"]


def test_an_entry_of_901_code_points_warns_without_failing() -> None:
    (finding,) = _length_findings("### Added", _entry_of_length(901))

    assert finding.severity == "warning"
    assert finding.fix == "Entry is 901 characters; aim for 900 or fewer."
    assert _length_findings("### Added", _entry_of_length(900)) == []


def test_main_returns_zero_and_prints_a_warning_for_a_long_but_legal_entry(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(doc("### Added", _entry_of_length(901)), encoding="utf-8")

    assert main(["--changelog", str(path)]) == 0
    out = capsys.readouterr().out
    assert "warning: " in out
    assert "0 error(s), 1 warning(s)" in out


def test_main_returns_one_for_an_entry_over_the_limit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(doc("### Added", _entry_of_length(1201)), encoding="utf-8")

    assert main(["--changelog", str(path)]) == 1
    assert "1 error(s), 0 warning(s)" in capsys.readouterr().out


def test_nested_items_are_measured_separately_from_their_parent() -> None:
    nested = "  - " + "x" * 496  # 500 code points each; 3 of them plus the parent exceed 1,200
    body = ("### Changed", "- **Parent** (#1). Short.", nested, nested, nested)

    assert _length_findings(*body) == []


def test_a_single_nested_item_over_the_limit_fails_at_its_own_line() -> None:
    body = ("### Changed", "- **Parent** (#1). Short.", "  - " + "x" * 1197)  # 1,201 code points

    (finding,) = _length_findings(*body)

    assert (finding.rule, finding.line) == ("length", _HEADING_LINE + 3)
    assert "Parent" in finding.where


def test_length_counts_code_points_not_bytes() -> None:
    """1,199 code points containing 3-byte characters is over 1,200 bytes but passes."""
    text = _entry_of_length(1199, filler="\u2713")

    assert len(text.encode("utf-8")) > 1200
    assert [f.rule for f in _length_findings("### Added", text)] == ["length-warning"]
    assert [f.rule for f in _length_findings("### Added", _entry_of_length(1201, filler="\u2713"))] == ["length"]


def test_length_is_measured_over_the_entrys_own_lines_joined_with_newlines() -> None:
    first = _LONG_PREFIX + "x" * 583  # 600 code points
    second = "y" * 601
    assert len(first) + 1 + len(second) == 1202

    assert [f.rule for f in _length_findings("### Added", first, second)] == ["length"]


# ---------------------------------------------------------------------------
# T008: the live text, a real-world red control and the production entry point
# ---------------------------------------------------------------------------

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_PRE_REWRITE_FIXTURE: Final[Path] = Path(__file__).parent / "fixtures" / "changelog_unreleased_pre_rewrite.md"
_MODULE: Final[str] = "scripts.docs.check_changelog_style"
_CLEAN_SECTION = ("### Added", "- **A thing** (#1). It works.")


def _run_module(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", _MODULE, *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_guard_passes(changelog: Path) -> None:
    """The live-file contract: the guard reports zero errors. Nothing about size or content."""
    text = changelog.read_text(encoding="utf-8")
    assert [f for f in check(text) if f.severity == "error"] == []
    result = _run_module("--changelog", str(changelog))
    assert result.returncode == 0, result.stdout


def test_live_changelog_passes() -> None:
    _assert_guard_passes(_LIVE_CHANGELOG)


def test_the_guard_still_passes_right_after_a_release_cut(release_cut_changelog: Path) -> None:
    """A fresh empty Unreleased section (the state right after a cut) is a pass, not a failure."""
    _assert_guard_passes(release_cut_changelog)
    section = unreleased_section(release_cut_changelog.read_text(encoding="utf-8"))
    assert section is not None
    assert parse_section(section).entries == ()


def test_post_rewrite_section_is_a_healthy_positive_control() -> None:
    """The frozen section proves the parser sees real entries and the length warning fires."""
    text = _POST_REWRITE_FIXTURE.read_text(encoding="utf-8")
    section = unreleased_section(text)
    assert section is not None

    findings = check(text)

    assert [f for f in findings if f.severity == "error"] == []
    assert len(parse_section(section).entries) >= 200
    assert [f.rule for f in findings if f.rule == "length-warning"] != []


def test_pre_rewrite_section_fails() -> None:
    """The pre-rewrite Unreleased section (PR #5420) trips every rule family the guard exists for."""
    findings = check(_PRE_REWRITE_FIXTURE.read_text(encoding="utf-8"))
    rules = {f.rule for f in findings}
    fixes = {f.fix for f in findings if f.rule == "banned-token"}

    assert {"heading-duplicate", "heading-order", "banned-token"} <= rules
    for expected in (
        "Delete the boilerplate",  # boilerplate, both the `;` and the em-dash forms
        "internal requirement",  # requirement ids
        "lowercase prose",  # all-caps DEFAULT/REFUSE/FAIL
        "Remove the mission/event ULID",  # the one backticked DM-<ULID>
        "Remove the private planning-repo reference",
        "Remove the local evidence path",
    ):
        assert any(expected in fix for fix in fixes), f"no banned-token finding carrying {expected!r}"
    assert any("01M3EC2FMWKCKGSBX1QHC7GFCJ" in f.where for f in findings if f.rule == "banned-token")


def test_module_entry_point_fails_on_a_planted_violation_and_names_the_entry(tmp_path: Path) -> None:
    dirty = tmp_path / "dirty.md"
    dirty.write_text(doc(*_CLEAN_SECTION, "- **Second thing** (#2). Bug-fix; no CLI version bump."), encoding="utf-8")

    result = _run_module("--changelog", str(dirty))

    assert result.returncode == 1
    assert "[Added] Second thing" in result.stdout
    assert "Delete the boilerplate" in result.stdout


def test_module_entry_point_passes_on_a_clean_copy(tmp_path: Path) -> None:
    clean = tmp_path / "clean.md"
    clean.write_text(doc(*_CLEAN_SECTION), encoding="utf-8")

    result = _run_module("--changelog", str(clean))

    assert (result.returncode, result.stdout.strip().splitlines()[-1]) == (0, "0 error(s), 0 warning(s)")


def test_a_relative_changelog_resolves_against_the_repo_root_not_the_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Like check_spelling's --repo-root: the path is repo-relative wherever the command is run from."""
    relative = _PRE_REWRITE_FIXTURE.relative_to(_REPO_ROOT).as_posix()
    decoy = tmp_path / relative
    decoy.parent.mkdir(parents=True)
    decoy.write_text(doc(*_CLEAN_SECTION), encoding="utf-8")  # a clean same-named file in the cwd must lose
    monkeypatch.chdir(tmp_path)

    code = main(["--changelog", relative])

    output = capsys.readouterr().out
    assert code == 1, output
    assert f"{relative}:" in output


def test_a_missing_relative_changelog_names_the_repo_root_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["--changelog", "nope/CHANGELOG.md"]) == 2
    assert str(_REPO_ROOT / "nope" / "CHANGELOG.md") in capsys.readouterr().err


def test_module_entry_point_defaults_to_the_live_changelog() -> None:
    result = _run_module()

    assert result.returncode == 0, result.stdout


def test_results_are_deterministic_across_three_runs() -> None:
    text = _PRE_REWRITE_FIXTURE.read_text(encoding="utf-8")

    runs = [check(text) for _ in range(3)]

    assert runs[0] == runs[1] == runs[2]
    assert len(runs[0]) > 10
    assert runs[0] == sorted(runs[0], key=lambda finding: finding.sort_key)
    assert [format_finding(f) for f in runs[0]] == [format_finding(f) for f in runs[2]]
