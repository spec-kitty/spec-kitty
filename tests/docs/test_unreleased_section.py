"""Behavior of the shared `## [Unreleased]` extractor (issue #5426, FR-016).

`unreleased_section` is the single definition of "the Unreleased section" used by the changelog
style guard and by the section-scoped spelling check, so the two can never disagree about where
the section starts or ends.
"""

from __future__ import annotations

import pytest

from scripts.release.validate_release import UnreleasedSection, unreleased_section

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _changelog(*lines: str) -> str:
    return "\n".join(lines) + "\n"


def test_bare_unreleased_heading_is_found() -> None:
    section = unreleased_section(_changelog("# Changelog", "", "## [Unreleased]", "", "- entry"))

    assert isinstance(section, UnreleasedSection)
    assert section.start_line == 3
    assert section.lines == ("", "- entry")


def test_version_suffixed_unreleased_heading_is_found() -> None:
    section = unreleased_section(_changelog("## [Unreleased] - 4.0.0rc5", "- entry"))

    assert section is not None
    assert section.start_line == 1
    assert section.lines == ("- entry",)


def test_section_ends_at_the_next_release_heading() -> None:
    text = _changelog(
        "## [Unreleased]",
        "- kept",
        "## [4.0.0rc4] - 2026-09-20",
        "- released, not part of the section",
    )

    section = unreleased_section(text)

    assert section is not None
    assert section.lines == ("- kept",)


def test_section_runs_to_end_of_file_without_a_terminator() -> None:
    section = unreleased_section(_changelog("## [Unreleased]", "- first", "- last"))

    assert section is not None
    assert section.lines == ("- first", "- last")


def test_no_unreleased_heading_returns_none() -> None:
    assert unreleased_section(_changelog("# Changelog", "## [4.0.0rc4] - 2026-09-20", "- entry")) is None


def test_release_heading_inside_a_fenced_block_does_not_end_the_section() -> None:
    text = _changelog(
        "## [Unreleased]",
        "- before the fence",
        "```",
        "## [9.9.9]",
        "```",
        "- after the fence",
        "## [4.0.0rc4] - 2026-09-20",
    )

    section = unreleased_section(text)

    assert section is not None
    assert section.lines == ("- before the fence", "```", "## [9.9.9]", "```", "- after the fence")


def test_non_release_level_two_heading_does_not_end_the_section() -> None:
    section = unreleased_section(_changelog("## [Unreleased]", "## Not a release heading", "- entry"))

    assert section is not None
    assert section.lines == ("## Not a release heading", "- entry")


def test_start_line_is_one_based_and_lines_exclude_heading_and_terminator() -> None:
    text = _changelog("a", "b", "c", "## [Unreleased]", "x", "y", "## [1.0.0]", "z")

    section = unreleased_section(text)

    assert section is not None
    assert section.start_line == 4
    assert section.lines == ("x", "y")


def test_only_the_first_unreleased_heading_is_used() -> None:
    section = unreleased_section(_changelog("## [Unreleased]", "- one", "## [Unreleased] - 4.0.0rc5", "- two"))

    assert section is not None
    assert section.lines == ("- one",)


def test_release_heading_inside_a_tilde_fence_does_not_end_the_section() -> None:
    text = _changelog(
        "## [Unreleased]",
        "- before the fence",
        "~~~",
        "## [9.9.9]",
        "~~~",
        "- after the fence",
        "## [4.0.0rc4] - 2026-09-20",
    )

    section = unreleased_section(text)

    assert section is not None
    assert section.lines == ("- before the fence", "~~~", "## [9.9.9]", "~~~", "- after the fence")


def test_a_fence_closes_only_with_its_own_marker() -> None:
    text = _changelog(
        "## [Unreleased]",
        "~~~",
        "```",
        "## [9.9.9]",
        "```",
        "~~~",
        "- after the fence",
        "## [4.0.0rc4] - 2026-09-20",
    )

    section = unreleased_section(text)

    assert section is not None
    assert section.lines == ("~~~", "```", "## [9.9.9]", "```", "~~~", "- after the fence")


def test_a_tilde_fence_does_not_swallow_the_rest_of_the_file_once_closed() -> None:
    text = _changelog("## [Unreleased]", "~~~", "code", "~~~", "## [4.0.0rc4] - 2026-09-20", "- released")

    section = unreleased_section(text)

    assert section is not None
    assert section.lines == ("~~~", "code", "~~~")


def test_an_unreleased_heading_without_a_space_is_found() -> None:
    section = unreleased_section(_changelog("# Changelog", "##[Unreleased]", "- entry", "##[4.0.0rc4] - 2026-09-20", "- released"))

    assert section is not None
    assert section.start_line == 2
    assert section.lines == ("- entry",)


def test_a_spaceless_release_heading_ends_the_section() -> None:
    section = unreleased_section(_changelog("## [Unreleased]", "- kept", "##[4.0.0rc4] - 2026-09-20", "- released"))

    assert section is not None
    assert section.lines == ("- kept",)


def test_a_level_three_heading_is_never_a_release_heading() -> None:
    section = unreleased_section(_changelog("## [Unreleased]", "### 1.0.0", "###[Unreleased]", "- entry"))

    assert section is not None
    assert section.lines == ("### 1.0.0", "###[Unreleased]", "- entry")
