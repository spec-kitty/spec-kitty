"""Tests for the canonical subtask-row patterns and progress counter (#2504)."""

from __future__ import annotations

import pytest

from specify_cli.core.subtask_rows import (
    CHECKED_SUBTASK_ROW,
    UNCHECKED_SUBTASK_ROW,
    count_subtask_rows,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_counts_checked_and_unchecked_rows() -> None:
    body = (
        "# Work Package Prompt: Demo\n"
        "- [x] T001 Build the thing\n"
        "- [X] T002 Build the other thing\n"
        "- [ ] T003 Verify the thing\n"
    )
    assert count_subtask_rows(body) == (2, 3)


def test_non_implementation_checkboxes_are_not_subtasks() -> None:
    """Command/validation rows and prose checkboxes don't count — mirrors the
    lane-transition guard's semantics."""
    body = (
        "- [ ] T004 Real subtask\n"
        "- [ ] swift test\n"
        "- [x] git status --short\n"
        "- [ ] remember to hydrate\n"
        "- [ ] T99 too-short id does not count\n"
    )
    assert count_subtask_rows(body) == (0, 1)


def test_fenced_code_blocks_are_ignored() -> None:
    body = (
        "- [x] T001 Done\n"
        "```\n"
        "- [ ] T002 example row inside a fence\n"
        "```\n"
        "~~~\n"
        "- [x] T003 another fenced example\n"
        "~~~\n"
        "- [ ] T004 Real remaining work\n"
    )
    assert count_subtask_rows(body) == (1, 2)


def test_no_checkbox_rows_is_zero_zero() -> None:
    assert count_subtask_rows("# Just prose\n\nNo checklists here.\n") == (0, 0)


def test_ids_past_t999_still_match() -> None:
    assert UNCHECKED_SUBTASK_ROW.match("- [ ] T1000 big mission")
    assert CHECKED_SUBTASK_ROW.match("- [x] T1000 big mission")


def test_wp_section_counts_only_that_wps_rows() -> None:
    tasks_md = (
        "# Tasks\n"
        "## WP01 — Acquisition (depends: none)\n"
        "- [x] T001 fetchChangedFileContents (WP01)\n"
        "- [ ] T002 Windowing + caps (WP01)\n"
        "## WP02 — Rendering (depends: WP01)\n"
        "- [ ] T006 ReviewRequest fields (WP02)\n"
        "- [x] T007 Block-B rendering (WP02)\n"
    )
    from specify_cli.core.subtask_rows import count_wp_section_subtask_rows

    assert count_wp_section_subtask_rows(tasks_md, "WP01") == (1, 2)
    assert count_wp_section_subtask_rows(tasks_md, "WP02") == (1, 2)
    assert count_wp_section_subtask_rows(tasks_md, "WP03") == (0, 0)


def test_wp_section_depends_heading_does_not_reenter() -> None:
    """#2346/#2324: a heading mentioning WP01 in its depends list belongs to
    the WP named by its FIRST WPxx token and must not re-enter WP01's section."""
    tasks_md = (
        "## WP01 — First\n"
        "- [ ] T001 real WP01 work\n"
        "## WP03 — Third (depends: WP01, WP02)\n"
        "- [ ] T009 WP03 work that must not count for WP01\n"
    )
    from specify_cli.core.subtask_rows import count_wp_section_subtask_rows

    assert count_wp_section_subtask_rows(tasks_md, "WP01") == (0, 1)
    assert count_wp_section_subtask_rows(tasks_md, "WP03") == (0, 1)


def test_wp_section_walker_yields_ids_and_checked_state() -> None:
    from specify_cli.core.subtask_rows import iter_wp_section_subtask_rows

    tasks_md = "## WP01\n- [x] T001 done\n- [ ] T002 pending\n"
    assert list(iter_wp_section_subtask_rows(tasks_md, "WP01")) == [
        ("T001", True),
        ("T002", False),
    ]


def test_wp_section_reappearing_heading_counter_regression_guard() -> None:
    """NFR-005 headline case: a re-appearing ``## WP01`` heading later in the
    document must not be counted — the counter already got this right; this
    pins it as a named regression guard so T003's writer rewrite cannot
    silently regress the read side too."""
    tasks_md = (
        "## WP01 — First block\n"
        "- [x] T001 first block done\n"
        "- [ ] T002 first block pending\n"
        "## WP02 — Middle\n"
        "- [x] T010 WP02 work\n"
        "## WP01 — Second block (stray duplicate)\n"
        "- [x] T020 second block done\n"
    )
    from specify_cli.core.subtask_rows import count_wp_section_subtask_rows

    assert count_wp_section_subtask_rows(tasks_md, "WP01") == (1, 2)


def test_content_after_section_end_is_unmodified_and_uncounted() -> None:
    """Trailing prose/rows after the target WP's section has closed must not
    be counted, regardless of whether a heading reopened it."""
    tasks_md = (
        "## WP01 — Work\n"
        "- [x] T001 done\n"
        "## WP02 — Next\n"
        "- [x] T010 WP02 work\n"
        "\n"
        "Trailing prose after the doc's sections.\n"
        "- [x] T050 stray checked row in trailing prose\n"
    )
    from specify_cli.core.subtask_rows import count_wp_section_subtask_rows

    assert count_wp_section_subtask_rows(tasks_md, "WP01") == (1, 1)


def test_nested_subheading_without_wp_token_does_not_close_section() -> None:
    """A sub-heading (###/####) with no WPxx token must not close the
    section — only a heading naming a DIFFERENT WP closes it."""
    tasks_md = "## WP01 — Work\n### Details\n- [x] T001 under a nested sub-heading\n"
    from specify_cli.core.subtask_rows import count_wp_section_subtask_rows

    assert count_wp_section_subtask_rows(tasks_md, "WP01") == (1, 1)


def test_fenced_block_inside_wp_section_is_ignored() -> None:
    """Fenced code inside the target WP's own section is skipped, even when
    the fenced content looks like a canonical subtask row."""
    tasks_md = (
        "## WP01 — Work\n"
        "- [x] T001 real row\n"
        "```\n"
        "- [ ] T002 example row inside a fence\n"
        "```\n"
        "- [ ] T003 real remaining row\n"
    )
    from specify_cli.core.subtask_rows import count_wp_section_subtask_rows

    assert count_wp_section_subtask_rows(tasks_md, "WP01") == (1, 2)


def test_wp_section_ids_past_t999_still_counted() -> None:
    tasks_md = "## WP01\n- [x] T1000 big mission\n- [ ] T1234 another big one\n"
    from specify_cli.core.subtask_rows import count_wp_section_subtask_rows

    assert count_wp_section_subtask_rows(tasks_md, "WP01") == (1, 2)


def test_counter_iterator_and_uncheck_agree_on_reappearing_heading_battery() -> None:
    """SC-002: drive the same fixture through ``count_wp_section_subtask_rows``
    (guard/dashboard), ``iter_wp_section_subtask_rows`` (dashboard progress),
    and ``uncheck_wp_section_subtask_rows`` (rollback) and confirm they agree
    — including on the re-appearing-heading edge case — proven entirely
    through the public functions."""
    from specify_cli.core.subtask_rows import (
        count_wp_section_subtask_rows,
        iter_wp_section_subtask_rows,
        uncheck_wp_section_subtask_rows,
    )

    tasks_md = (
        "## WP01 — First block\n"
        "- [x] T001 first block done\n"
        "- [ ] T002 first block pending\n"
        "## WP02 — Middle\n"
        "- [x] T010 WP02 work\n"
        "## WP01 — Second block (stray duplicate)\n"
        "- [x] T020 second block done\n"
    )

    done, total = count_wp_section_subtask_rows(tasks_md, "WP01")
    assert (done, total) == (1, 2)
    assert len(list(iter_wp_section_subtask_rows(tasks_md, "WP01"))) == total

    rewritten = uncheck_wp_section_subtask_rows(tasks_md, "WP01")
    assert rewritten != tasks_md

    # Re-running the counter on the rewritten text shows the first section
    # fully unchecked...
    assert count_wp_section_subtask_rows(rewritten, "WP01") == (0, 2)
    # ...and the second (stray duplicate) WP01 block is untouched by both the
    # counter and the uncheck — its checked row survives verbatim.
    assert "## WP01 — Second block (stray duplicate)\n- [x] T020 second block done" in rewritten
    # WP02's row is also untouched (different WP entirely).
    assert count_wp_section_subtask_rows(rewritten, "WP02") == (1, 1)


def test_guard_blocks_on_the_shared_snapshot_resolver() -> None:
    """#2816 IC-10 (FR-016): the lane-transition guard's blocking source is the
    snapshot-backed resolver pair in ``core.subtask_rows`` — the authored
    frontmatter roster + the event-sourced completion — NOT a re-parse of
    ``tasks.md`` checkbox rows, and never a hand-rolled local regex."""
    import inspect

    from specify_cli.cli.commands.agent import tasks_shared

    source = inspect.getsource(tasks_shared._check_unchecked_subtasks)
    assert "authored_subtask_roster" in source
    # WP06: completion is reduced from the declared status source's event stream (the one
    # status read door), the same snapshot semantics as ``unchecked_subtask_ids_from_snapshot``.
    assert "unchecked_subtask_ids_from_event_stream" in source
    # The guard no longer parses tasks.md checkbox rows for its roster/completion.
    assert "iter_wp_section_subtask_rows" not in source
    assert 're.compile(r"^-' not in source
