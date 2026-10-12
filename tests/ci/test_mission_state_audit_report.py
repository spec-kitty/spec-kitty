"""Unit tests for ``scripts/ci/mission_state_audit_report.py`` (spec-kitty#6058, FR-007, NFR-001)."""

from __future__ import annotations

import itertools
import json
import re
from pathlib import Path
from typing import Any

import pytest

from scripts.ci import mission_state_audit_report as report_mod
from scripts.ci.mission_state_audit_report import is_blocking, main, render
from specify_cli.audit.models import (
    TEAMSPACE_BLOCKER_CODES,
    MissionFinding,
    Severity,
    is_teamspace_blocker,
)

pytestmark = pytest.mark.fast

#: One representative non-blocker code; the blocker set itself is the canonical ``TEAMSPACE_BLOCKER_CODES``.
PARITY_CODES = sorted(TEAMSPACE_BLOCKER_CODES | {"UNKNOWN_SHAPE"})


def _finding(code: str = "SNAPSHOT_DRIFT", severity: str = "error", detail: str = "d") -> dict[str, Any]:
    return {"code": code, "severity": severity, "artifact_path": "status.json", "detail": detail}


def _report(missions: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "repo_summary": {
            "total_missions": len(missions),
            "missions_with_teamspace_blockers": len(missions),
            "findings_by_severity": {"error": 1},
        },
        "missions": [{"mission_slug": slug, "findings": findings} for slug, findings in missions.items()],
    }


@pytest.mark.parametrize(
    ("severity", "code", "expected"),
    [
        ("error", "UNKNOWN_SHAPE", True),
        ("error", "SNAPSHOT_DRIFT", True),
        ("warning", "SNAPSHOT_DRIFT", True),
        ("warning", "UNKNOWN_SHAPE", False),
        ("info", "MISSING_EVIDENCE", False),
    ],
)
def test_is_blocking_truth_table(severity: str, code: str, expected: bool) -> None:
    assert is_blocking(_finding(code, severity)) is expected


@pytest.mark.parametrize(("code", "severity"), list(itertools.product(PARITY_CODES, list(Severity))))
def test_is_blocking_matches_the_canonical_predicate(code: str, severity: Severity) -> None:
    """The renderer delegates to the audit package's one predicate; pin the JSON-dict path to ``is_teamspace_blocker``."""
    canonical = MissionFinding(code=code, severity=severity, artifact_path="status.json", detail="x")

    assert is_blocking(canonical.to_dict()) == is_teamspace_blocker(canonical)


def test_render_counts_lists_only_blockers_and_picks_the_remedy_per_code() -> None:
    report = _report(
        {
            "m-drift": [_finding("SNAPSHOT_DRIFT"), _finding("MISSING_EVIDENCE", "warning")],
            "m-ident": [_finding("IDENTITY_MISSING", "warning")],
        }
    )

    log, summary = render(report, 1)

    assert "SNAPSHOT_DRIFT x1" in log and "IDENTITY_MISSING x1" in log
    assert log.count("::error title=mission-state audit::") == 2
    assert "spec-kitty agent status materialize --mission m-drift" in log
    assert "spec-kitty doctor mission-state --audit --mission m-ident" in log
    assert report_mod.REPAIR_DOC in log
    assert "MISSING_EVIDENCE" not in log and "MISSING_EVIDENCE" not in summary
    assert "exit 1" in summary and "FAILED" in summary


def test_render_of_a_clean_report_says_no_blockers() -> None:
    log, summary = render(_report({"m": [_finding("MISSING_EVIDENCE", "warning")]}), 0)

    assert "No TeamSpace blockers" in log and "No TeamSpace blockers" in summary
    assert "::error" not in log
    assert "passed" in summary


def test_cells_escape_pipes_flatten_newlines_truncate_and_defuse_markup() -> None:
    long_detail = "a|b\nline2 " + "x" * 1000
    _, summary = render(_report({"m": [_finding(detail=long_detail)]}), 1)

    row = next(line for line in summary.splitlines() if line.startswith("| `m`"))
    assert "a\\|b line2" in row
    assert "\n" not in row
    assert "…" in row and len(row) < report_mod.DETAIL_LIMIT + 300

    # Repo-controlled text: code-span cells (slug/code/artifact/remedy) must not hold backticks that end the
    # span; the Markdown detail must not render links, images or HTML.
    finding = _finding(code="C`ODE", detail="see [x](http://evil) and ![i](http://evil/p.png) <img src=x> a\\[b \\[x](y)")
    finding["artifact_path"] = "dir/`tick`.md"
    _, summary = render(_report({"sl`ug": [finding]}), 1)

    row = next(line for line in summary.splitlines() if line.startswith("| `sl"))
    cells = re.split(r"(?<!\\)\|", row.strip().strip("|"))
    for index in (0, 1, 2, 4):  # the code-span cells
        assert cells[index].strip().startswith("`") and cells[index].strip().endswith("`")
        assert "`" not in cells[index].strip()[1:-1], cells[index]
    detail = cells[3]
    assert not re.search(r"(?<!\\)\[", detail) and not re.search(r"(?<!\\)!", detail) and not re.search(r"(?<!\\)<", detail), detail
    assert "\\[x\\]" in detail and "\\!\\[i\\]" in detail and "\\<img" in detail
    # A backslash in the repo text must itself be escaped, or it would un-escape the bracket that follows it.
    assert "a\\\\\\[b" in detail and "\\\\\\[x\\]" in detail, detail


def test_annotations_escape_newlines_so_a_blocker_stays_one_line() -> None:
    log, _ = render(_report({"m": [_finding(detail="one\ntwo 100%")]}), 1)

    annotation = next(line for line in log.splitlines() if line.startswith("::error"))
    assert "one%0Atwo 100%25" in annotation
    assert report_mod._annotation_escape("hint\n::set-env name=A::b") == "hint%0A::set-env name=A::b"


def test_many_unrelated_drifts_get_the_reducer_hint() -> None:
    many = _report({f"m{i}": [_finding()] for i in range(report_mod.MANY_DRIFT_THRESHOLD + 1)})
    few = _report({f"m{i}": [_finding()] for i in range(report_mod.MANY_DRIFT_THRESHOLD)})

    many_log, many_summary = render(many, 1)
    few_log, few_summary = render(few, 1)

    assert any(line.startswith("::warning title=mission-state audit::") and "#6058" in line for line in many_log.splitlines())
    assert "#6058" in many_log and "#6058" in many_summary
    assert "#6058" not in few_log and "#6058" not in few_summary


def test_every_blocker_is_listed_when_under_the_size_budget() -> None:
    missions = {f"mission-{i:04d}": [_finding(detail="y" * 200)] for i in range(500)}

    log, summary = render(_report(missions), 1)

    assert log.count("::error") == 500
    assert sum(line.startswith("| `mission-") for line in summary.splitlines()) == 500
    assert "more blocker" not in summary


def test_the_summary_is_cut_at_the_budget_but_the_log_stays_complete() -> None:
    missions = {f"mission-{i:05d}": [_finding(detail="z" * 290)] for i in range(4000)}

    log, summary = render(_report(missions), 1)

    assert len(summary.encode("utf-8")) <= report_mod.SUMMARY_BUDGET_BYTES + 200
    assert log.count("::error") == 4000
    shown = sum(line.startswith("| `mission-") for line in summary.splitlines())
    assert 0 < shown < 4000
    assert f"{4000 - shown} more blocker(s) in the uploaded artifact" in summary


@pytest.mark.parametrize("with_summary_env", [True, False])
def test_main_prints_and_appends_to_the_summary_when_set_and_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], with_summary_env: bool
) -> None:
    source = tmp_path / "r.json"
    source.write_text(json.dumps(_report({"m": [_finding()]})), encoding="utf-8")
    summary = tmp_path / "summary.md"
    summary.write_text("earlier\n", encoding="utf-8")
    if with_summary_env:
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    else:
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    assert main([str(source), "1"]) == 0

    assert "::error title=mission-state audit::m SNAPSHOT_DRIFT" in capsys.readouterr().out
    text = summary.read_text(encoding="utf-8")
    if with_summary_env:
        assert text.startswith("earlier\n") and "| `m` |" in text
    else:
        assert text == "earlier\n", "without the env var nothing is written"


def test_main_survives_an_unwritable_summary_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """R5: a summary that cannot be written is a warning, never a failure of the step."""
    source = tmp_path / "r.json"
    source.write_text(json.dumps(_report({"m": [_finding()]})), encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path))  # a directory: opening it for append raises

    assert main([str(source), "1"]) == 0

    out = capsys.readouterr().out
    assert "::error title=mission-state audit::m SNAPSHOT_DRIFT" in out
    assert "summary could not be written" in out


@pytest.mark.parametrize(
    "payload",
    ['{"repo_summary": {}, "missions": [{"findings": []}]}', "[]", "not json", "[" * 100000],  # last: pathologically nested (RecursionError)
)
def test_main_warns_and_returns_zero_on_malformed_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], payload: str) -> None:
    source = tmp_path / "r.json"
    source.write_text(payload, encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))

    assert main([str(source), "1"]) == 0

    assert "::warning::" in capsys.readouterr().out
    assert not (tmp_path / "summary.md").exists()


@pytest.mark.parametrize("argv", [[], ["only-a-path"], ["/nonexistent/report.json", "1"]])
def test_main_warns_and_returns_zero_on_bad_arguments(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    assert main(argv) == 0
    assert "::warning::" in capsys.readouterr().out


def test_a_non_utf8_mission_name_does_not_hide_any_blocker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """The doctor emits surrogateescape'd slugs for non-UTF-8 directories; every blocker must still render."""
    report = _report({"bad-\udcff-mission": [_finding()], "good-mission": [_finding("IDENTITY_MISSING", "warning")]})
    source = tmp_path / "r.json"
    source.write_text(json.dumps(report), encoding="ascii")  # json.dumps escapes the lone surrogate
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    assert main([str(source), "1"]) == 0

    out = capsys.readouterr().out
    text = summary.read_text(encoding="utf-8")
    assert "::warning::the mission-state audit report" not in out
    assert out.count("::error title=mission-state audit::") == 2
    assert "bad-\\udcff-mission" in out and "bad-\\udcff-mission" in text
    assert "good-mission" in out and "good-mission" in text


def test_a_hostile_code_cannot_inject_a_workflow_command_through_the_counts_line() -> None:
    hostile = "X\n::set-env name=A::b"
    log, summary = render(_report({"m": [_finding(code=hostile)]}), 1)

    assert not any(line.startswith("::set-env") for line in log.splitlines() + summary.splitlines())
    assert "X%0A::set-env name=A::b x1" in log

    # ... and markdown link/image starters in a code cannot render in the summary's counts line.
    _, linked = render(_report({"m": [_finding(code="[click](http://evil) ![i](http://evil/p.png)")]}), 1)
    counts = next(line for line in linked.splitlines() if line.startswith("By code:"))
    assert "\\[click\\]" in counts and "\\!\\[i\\]" in counts


def test_main_returns_zero_when_the_log_write_itself_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "r.json"
    source.write_text(json.dumps(_report({"m": [_finding()]})), encoding="utf-8")
    monkeypatch.setattr(report_mod, "render", lambda *_: (_ for _ in ()).throw(UnicodeEncodeError("utf-8", "x", 0, 1, "boom")))

    assert main([str(source), "1"]) == 0
    assert "UnicodeEncodeError" in capsys.readouterr().out


def test_a_report_without_repo_summary_still_lists_blockers_and_writes_the_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "r.json"
    source.write_text(json.dumps({"missions": [{"mission_slug": "m", "findings": [_finding()]}]}), encoding="utf-8")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    assert main([str(source), "1"]) == 0

    out = capsys.readouterr().out
    assert "::error title=mission-state audit::m SNAPSHOT_DRIFT" in out and "::warning::" not in out
    text = summary.read_text(encoding="utf-8")
    assert "| `m` |" in text and "? Missions, ? with TeamSpace blockers, ? errors." in text
    assert "None" not in text


def test_a_partial_repo_summary_renders_unknown_values_as_question_marks() -> None:
    report = _report({"m": [_finding()]})
    report["repo_summary"] = {"total_missions": 7}

    _, summary = render(report, 1)

    assert "7 Missions, ? with TeamSpace blockers, ? errors." in summary
    assert "None" not in summary


def test_a_report_with_neither_key_says_nothing_could_be_listed_not_that_it_is_clean() -> None:
    log, summary = render({}, 1)

    assert report_mod.NO_MISSIONS_NOTE in log and report_mod.NO_MISSIONS_NOTE in summary
    assert report_mod.NO_BLOCKERS not in log and report_mod.NO_BLOCKERS not in summary
    assert "? Missions" in summary
