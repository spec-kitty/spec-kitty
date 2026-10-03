"""The nightly xunit summary names failing tests without deciding the job result (#5583).

A red nightly step used to print only ``suite exited 1``. These tests pin the
renderer: no failures, more failures than the annotation cap, a missing
report, and a collection error. A missing report warns and exits 0. The
workflow wiring test fails if a suite that writes an xunit file never asks
for that summary.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ci.nightly_xunit import (
    DISPLAY_CAP,
    XunitRead,
    annotation_lines,
    delta_text,
    main,
    parse_xunit,
    plain_report,
    read_xunit,
    recorded_ids,
    summary_markdown,
    with_recorded_ids,
)

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci-nightly.yml"
_LOG = "Run performance-marked suite (full-mode, run-all-regardless)"
_HELPER_GUARD = '|| echo "::warning::nightly xunit summary helper failed"'

# suite key, xunit path, the step that holds the pytest log
_REPORTS = (
    ("performance", "out/reports/xunit-nightly-performance.xml", "Run performance-marked suite (full-mode, run-all-regardless)"),
    ("e2e", "out/reports/xunit-nightly-e2e.xml", "Run heavy/e2e-marked suite (full-mode, run-all-regardless)"),
    ("stress", "out/reports/xunit-nightly-stress.xml", "Run stress-marked suite (full-mode, run-all-regardless)"),
    *(
        (
            f"interpreter-3.13-shard-{number}",
            f"out/reports/xunit-nightly-interpreter-3.13-shard-{number}.xml",
            f"Run fast/unit suite, shard {number} (full-mode, run-all-regardless)",
        )
        for number in range(1, 7)
    ),
    ("integration", "out/reports/xunit-nightly-integration-next.xml", "Run integration + next suites by directory (full-mode, run-all-regardless)"),
    (
        "specify-cli-out-of-matrix",
        "out/reports/xunit-nightly-specify-cli-out-of-matrix.xml",
        "Run out-of-matrix tests/specify_cli trees by directory (full-mode, run-all-regardless)",
    ),
    ("architectural", "out/reports/xunit-nightly-architectural.xml", "Run the full architectural battery base (no partition, run-all-regardless)"),
    ("integration-slice", "out/reports/xunit-nightly-integration-slice.xml", "Run integration-marked tests no other nightly lane selects"),
)


def _case(name: str, *, file: str = "tests/e2e/test_owned.py", message: str = "AssertionError: boom", kind: str = "failure") -> str:
    return f'<testcase classname="tests.e2e.test_owned" name="{name}" file="{file}" line="12"><{kind} message="{message}">traceback</{kind}></testcase>'


def _suite(cases: str) -> str:
    return f'<?xml version="1.0" ?><testsuites><testsuite tests="1">{cases}</testsuite></testsuites>'


def missing_xunit_wiring(text: str) -> list[str]:
    """Reports whose nightly job does not summarize the xunit file and pass it to escalation."""
    problems: list[str] = []
    summarize_count = text.count("nightly_xunit.py summarize")
    guard_count = text.count(_HELPER_GUARD)
    if summarize_count != guard_count:
        problems.append(f"{summarize_count} summarize calls but {guard_count} crash guards")
    for suite_key, path, step in _REPORTS:
        summarize = f"nightly_xunit.py summarize --suite-key {suite_key} --xunit {path} --log-step '{step}'"
        if summarize not in text:
            problems.append(f"{suite_key}: summarize call missing")
        if text.count(f"--xunit {path}") < 2:
            problems.append(f"{suite_key}: {_xunit_flag(path)} must appear on the summary and the escalation")
    return problems


def _xunit_flag(path: str) -> str:
    return f"--xunit {path}"


def test_no_failures_renders_an_empty_summary_and_no_annotations() -> None:
    text = _suite('<testcase classname="tests.e2e.test_owned" name="test_ok" file="tests/e2e/test_owned.py"/>')
    failures = parse_xunit(text)
    report = XunitRead(failures, None)
    assert failures == ()
    assert "No failing tests." in summary_markdown("performance", report, _LOG)
    assert plain_report("performance", report, _LOG) == "performance: no failing tests.\n"
    assert annotation_lines(report) == ()


def test_more_failures_than_the_cap_keep_one_more_line() -> None:
    cases = "".join(_case(f"test_{index}") for index in range(DISPLAY_CAP + 1))
    report = XunitRead(parse_xunit(_suite(cases)), None)
    annotations = annotation_lines(report)
    assert len(annotations) == DISPLAY_CAP + 1
    assert annotations[-1] == "::error::1 more failing tests; see the job summary"
    assert "file=tests/e2e/test_owned.py" in annotations[0]
    assert "title=tests/e2e/test_owned.py::test_0" in annotations[0]
    assert "AssertionError: boom" in annotations[0]
    summary = summary_markdown("performance", report, _LOG)
    assert "and 1 more not shown." in summary
    assert _LOG in summary
    plain = plain_report("performance", report, _LOG)
    assert f"performance: {DISPLAY_CAP + 1} failing test(s). First {DISPLAY_CAP}:" in plain
    assert "and 1 more." in plain


def test_missing_report_warns_and_the_command_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "xunit-nightly-performance.xml"
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    report = read_xunit(missing)
    assert report.failures == ()
    assert report.problem is not None
    assert "Could not read the xunit report" in plain_report("performance", report, _LOG)
    assert annotation_lines(report) == ()

    code = main(["summarize", "--suite-key", "performance", "--xunit", str(missing), "--log-step", _LOG])
    captured = capsys.readouterr()
    assert code == 0
    assert "::warning title=Nightly xunit summary::" in captured.out
    assert "The suite result is unchanged." in summary.read_text(encoding="utf-8")


def test_collection_error_is_a_failing_test() -> None:
    text = _suite(
        '<testcase classname="" name="tests/e2e/test_owned.py" file="tests/e2e/test_owned.py">'
        '<error message="collection failure">ImportError: boom</error></testcase>'
    )
    (failed,) = parse_xunit(text)
    assert failed.test_id == "tests/e2e/test_owned.py"
    assert failed.reason == "collection failure"
    assert failed.file == "tests/e2e/test_owned.py"


def test_failure_ids_round_trip_through_the_issue_marker() -> None:
    nodeid = "tests/e2e/test_owned.py::test_isolated[a--b]"
    body = with_recorded_ids("<!-- nightly-escalation-key: performance -->\n", [nodeid])
    assert recorded_ids(body) == (nodeid,)
    assert "<!-- nightly-escalation-key: performance -->" in body
    assert "--" not in body.split("nightly-failure-ids:", 1)[1].split("-->", 1)[0]


def test_delta_says_what_changed_since_the_previous_failure() -> None:
    assert delta_text(None, ["tests/a.py::test_new"]) == "The previous failure did not record test ids."
    assert delta_text(("tests/a.py::test_same",), ["tests/a.py::test_same"]) == "Same failing tests as the previous recorded failure."
    changed = delta_text(("tests/a.py::test_old",), ["tests/b.py::test_new"])
    assert "Newly failing" in changed
    assert "tests/b.py::test_new" in changed
    assert "Now passing" in changed
    assert "tests/a.py::test_old" in changed


def test_every_nightly_xunit_report_is_summarized_and_passed_to_escalation() -> None:
    problems = missing_xunit_wiring(_WORKFLOW.read_text(encoding="utf-8"))
    assert problems == [], problems


def test_a_suite_that_drops_its_summary_call_is_caught() -> None:
    """Standing Order #5: the wiring check fails when one suite's summarize line is gone."""
    text = _WORKFLOW.read_text(encoding="utf-8").replace(
        "nightly_xunit.py summarize --suite-key performance --xunit out/reports/xunit-nightly-performance.xml",
        "nightly_xunit.py summarize --suite-key performance --xunit out/reports/removed.xml",
    )
    problems = missing_xunit_wiring(text)
    assert any(problem.startswith("performance:") for problem in problems), problems
