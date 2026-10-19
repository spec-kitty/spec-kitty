"""Non-blocking bulk-edit diff notes must stay readable at ingest scale.

The review command used to print one yellow line per warning, labelled
``manual_review:``. Once the gate stopped blocking on created files it
started reporting them as warnings instead — so a work package that ingests
a tree produced hundreds of lines, every one mislabelled as asking for
manual review, burying the handful that actually did.
"""

from __future__ import annotations

import pytest
from rich.console import Console

from specify_cli.bulk_edit.diff_check import DiffCheckResult, FileAssessment
from specify_cli.cli.commands.agent.workflow import (
    _WARNING_LIST_LIMIT,
    _render_diff_check_warnings,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _ok(path: str, source: str) -> FileAssessment:
    return FileAssessment(
        path=path,
        category=None,
        source=source,
        action=None,
        violation=False,
        reason="",
    )


def _render(result: DiffCheckResult) -> str:
    console = Console(width=120, record=True, force_terminal=False)
    _render_diff_check_warnings(result, console)
    return console.export_text()


def _result(assessments: list[FileAssessment], warnings: list[str] | None = None) -> DiffCheckResult:
    return DiffCheckResult(passed=True, assessments=assessments, errors=[], warnings=warnings or [])


class TestGrouping:
    def test_counts_each_kind(self) -> None:
        out = _render(
            _result(
                [
                    _ok("a.rb", "path-heuristic"),
                    _ok("new1.rb", "added"),
                    _ok("new2.rb", "added"),
                    _ok("f.woff2", "non-occurrence"),
                    _ok("kitty-specs/m/status.json", "runtime-state"),
                ]
            )
        )
        assert "1 need manual review" in out
        assert "2 created by this diff" in out
        assert "1 carry no textual occurrence" in out
        assert "1 this mission's own bookkeeping" in out

    def test_manual_review_paths_are_listed_in_full(self) -> None:
        """These are the ones a human must actually look at."""
        many = [_ok(f"src/f{i}.rb", "path-heuristic") for i in range(40)]
        out = _render(_result(many))
        for i in range(40):
            assert f"src/f{i}.rb" in out
        assert "and 28 more" not in out

    def test_bulk_exemptions_are_truncated_but_counted(self) -> None:
        many = [_ok(f"vendor/f{i}.rb", "added") for i in range(400)]
        out = _render(_result(many))
        assert "400 created by this diff" in out
        assert f"and {400 - _WARNING_LIST_LIMIT} more" in out
        # Truncation must keep the output far below one-line-per-path.
        assert len(out.splitlines()) < 30

    def test_judgement_notes_come_before_bulk_exemptions(self) -> None:
        out = _render(
            _result(
                [
                    _ok("zzz_added.rb", "added"),
                    _ok("aaa_review.rb", "path-heuristic"),
                ]
            )
        )
        assert out.index("need manual review") < out.index("created by this diff")

    def test_violations_are_not_reported_as_notes(self) -> None:
        blocking = FileAssessment(
            path="blocked.rb",
            category="cli_commands",
            source="path-heuristic",
            action="do_not_change",
            violation=True,
            reason="",
        )
        out = _render(_result([blocking, _ok("fine.rb", "added")]))
        assert "blocked.rb" not in out

    def test_empty_kinds_are_omitted(self) -> None:
        out = _render(_result([_ok("new.rb", "added")]))
        assert "need manual review" not in out
        assert "own bookkeeping" not in out

    def test_field_path_pins_are_printed_verbatim(self) -> None:
        """Per-field information the per-path grouping would drop."""
        out = _render(
            _result(
                [_ok("profile.yaml", "exception")],
                warnings=["profile.yaml: field-path exception pins directive-references as do_not_change — verify only those fields were left untouched"],
            )
        )
        assert "field-path exception pins directive-references" in out

    def test_nothing_is_labelled_manual_review_wholesale(self) -> None:
        """The old renderer called every note a manual_review note."""
        out = _render(_result([_ok("new.rb", "added"), _ok("f.woff2", "non-occurrence")]))
        assert "manual_review" not in out
