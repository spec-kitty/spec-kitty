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
from specify_cli.cli.commands.agent.workflow import _render_diff_check_warnings

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


def _review(path: str, source: str) -> FileAssessment:
    """A passing row that still asks a human to look (action manual_review)."""
    return FileAssessment(
        path=path,
        category="code_symbols" if source == "path-heuristic" else None,
        source=source,
        action="manual_review",
        violation=False,
        reason="",
    )


class TestGrouping:
    def test_manual_review_rows_are_listed_in_full_whatever_their_source(self) -> None:
        """An occurrence-map exception with ``manual_review`` is not a violation,
        but it still asks a human to look: it must never be dropped."""
        rows = [_review(f"src/h{i}.rb", "path-heuristic") for i in range(40)]
        rows += [_review("config/legacy.yml", "exception"), _review("old/a.rb", "move")]
        out = _render(_result(rows))
        for row in rows:
            assert row.path in out
        assert "more" not in out

    def test_informational_rows_are_not_called_manual_review(self) -> None:
        """Non-violating heuristic rows (e.g. action ``rename``) need no review."""
        renamed = FileAssessment(
            path="src/ok.py",
            category="import_paths",
            source="path-heuristic",
            action="rename",
            violation=False,
            reason="",
        )
        out = _render(_result([renamed, _ok("new.rb", "added"), _ok("f.woff2", "non-occurrence")]))
        assert "src/ok.py" in out
        assert "manual review" not in out
        assert "manual_review" not in out

    def test_bulk_exemptions_are_summarised_not_enumerated(self) -> None:
        many = [_ok(f"vendor/f{i}.rb", "added") for i in range(400)]
        out = _render(_result(many))
        assert "400" in out
        # One line per path would bury everything else.
        assert len(out.splitlines()) < 30

    def test_a_review_row_is_not_hidden_among_bulk_additions(self) -> None:
        rows = [_ok(f"vendor/f{i}.rb", "added") for i in range(400)]
        rows.append(_review("config/legacy.yml", "exception"))
        assert "config/legacy.yml" in _render(_result(rows))

    def test_structural_target_bypasses_are_listed_in_full(self) -> None:
        rows = [_ok(f"src/s{i}.py", "structural-target") for i in range(30)]
        out = _render(_result(rows))
        for row in rows:
            assert row.path in out

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

    def test_field_path_pins_are_printed_verbatim(self) -> None:
        """Per-field information the per-path grouping would drop."""
        out = _render(
            _result(
                [_ok("profile.yaml", "exception")],
                warnings=["profile.yaml: field-path exception pins directive-references as do_not_change — verify only those fields were left untouched"],
            )
        )
        assert "field-path exception pins directive-references" in out


class TestFailureTableIsScannable:
    """The failure table listed every assessment, however large the diff."""

    def _blocked(self, path: str) -> FileAssessment:
        return FileAssessment(
            path=path,
            category="cli_commands",
            source="path-heuristic",
            action="do_not_change",
            violation=True,
            reason="forbidden",
        )

    def test_only_blocking_and_review_rows_are_listed(self) -> None:
        from specify_cli.bulk_edit.gate import render_diff_check_failure

        assessments = [self._blocked("bin/x")]
        assessments += [_ok(f"added{i}.rb", "added") for i in range(400)]
        console = Console(width=120, record=True, force_terminal=False)
        render_diff_check_failure(
            DiffCheckResult(
                passed=False,
                assessments=assessments,
                errors=["bin/x: forbidden"],
                warnings=[],
            ),
            console,
        )
        out = console.export_text()
        assert "bin/x" in out
        assert "BLOCK" in out
        assert "added0.rb" not in out
        assert "400 further files passed" in out or "400 created here" in out
        assert len(out.splitlines()) < 40

    def test_exempted_rows_are_not_called_unclassified(self) -> None:
        from specify_cli.bulk_edit.gate import render_diff_check_failure

        console = Console(width=120, record=True, force_terminal=False)
        render_diff_check_failure(
            DiffCheckResult(
                passed=False,
                assessments=[self._blocked("bin/x"), _ok("new.rb", "added")],
                errors=["bin/x: forbidden"],
                warnings=[],
            ),
            console,
        )
        out = console.export_text()
        assert "created here" in out
        assert "(unclassified)" not in out
