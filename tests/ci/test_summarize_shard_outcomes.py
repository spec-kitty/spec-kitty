"""The shard summariser must name the real failure and never invent one (#4420).

Driven by fixtures shaped like the GitHub list-jobs payload rather than by a
live run, because the behaviour under test is exactly the classification a
live run makes hard to see.

The anchor case is the one measured on PR #4417 (``CI Modules`` run
34911646190): ``module-tests (release shard 1/1)`` genuinely failed and every
other shard reported ``conclusion: cancelled``, while ``gh pr checks`` printed
``fail`` for all forty.
"""

from __future__ import annotations

import json

import pytest

from scripts.ci.summarize_shard_outcomes import (
    main,
    render_annotation,
    render_markdown,
    summarize,
)


def _job(name: str, conclusion: str | None, url: str = "") -> dict:
    return {"name": name, "conclusion": conclusion, "html_url": url}


def _fail_fast_run() -> list[dict]:
    """One real failure, many fail-fast casualties -- the #4417 shape."""
    jobs = [_job("module-tests (release shard 1/1)", "failure", "https://example.invalid/release")]
    jobs += [_job(f"module-tests (agent shard {index}/3)", "cancelled") for index in range(1, 4)]
    jobs += [_job(f"module-tests (charter shard {index}/5)", "cancelled") for index in range(1, 6)]
    return jobs


def test_the_one_failing_shard_is_named_and_the_cancelled_ones_are_not_counted_as_breakage():
    summary = summarize(_fail_fast_run())

    assert [outcome.name for outcome in summary.failed] == ["module-tests (release shard 1/1)"]
    assert len(summary.cancelled) == 8
    assert summary.total == 9

    headline = summary.headline
    assert "module-tests (release shard 1/1)" in headline
    assert "CANCELLED by fail-fast" in headline
    # The whole point: a reader must not walk away thinking 9 things broke.
    assert "8" in headline


def test_a_cancelled_shard_is_never_classified_as_a_failure():
    """The rendering bug this exists to counteract, asserted directly."""
    summary = summarize([_job("module-tests (cli shard 1/2)", "cancelled")])

    assert summary.failed == []
    assert len(summary.cancelled) == 1


def test_a_run_with_no_failures_is_not_described_as_a_shard_failure():
    """All-cancelled means stopped from outside -- pointing at a failing shard would be a lie."""
    summary = summarize([_job(f"module-tests (unit shard {index}/2)", "cancelled") for index in (1, 2)])

    assert summary.failed == []
    headline = summary.headline
    assert "No shard failed" in headline
    assert "stopped from outside" in headline


def test_a_timed_out_shard_is_a_real_failure_and_is_labelled_as_one():
    """A wall-clock kill is neither an innocent casualty nor an assertion failure."""
    summary = summarize([_job("module-tests (core_misc shard 3/5)", "timed_out")])

    assert [outcome.name for outcome in summary.failed] == ["module-tests (core_misc shard 3/5)"]
    assert "timed out" in render_markdown(summary)


def test_a_job_still_running_is_not_guessed_into_pass_or_fail():
    """A None conclusion must not silently become a pass; that would make the headline lie."""
    summary = summarize([_job("module-tests (agent shard 1/3)", None)])

    assert summary.failed == []
    assert summary.succeeded == []
    assert len(summary.other) == 1


def test_an_all_green_run_says_so():
    summary = summarize([_job("module-tests (unit shard 1/2)", "success")])

    assert summary.headline == "All 1 jobs passed."


def test_every_failing_shard_is_named_when_fail_fast_is_off():
    """In `full` mode the matrix runs to completion, so several can be genuinely red."""
    summary = summarize(
        [
            _job("module-tests (release shard 1/1)", "failure"),
            _job("module-tests (charter shard 2/5)", "failure"),
            _job("module-tests (unit shard 1/2)", "success"),
        ]
    )

    assert len(summary.failed) == 2
    headline = summary.headline
    assert "release shard 1/1" in headline
    assert "charter shard 2/5" in headline
    # Nothing was cancelled, so no fail-fast caveat should be volunteered.
    assert "CANCELLED" not in headline


def test_the_markdown_leads_with_the_failure_and_hides_the_noise():
    markdown = render_markdown(summarize(_fail_fast_run()))

    assert "### Failed — start here" in markdown
    assert "module-tests (release shard 1/1)" in markdown
    assert "https://example.invalid/release" in markdown
    # The 8 cancelled jobs are present but collapsed, so they cannot bury the signal.
    assert "<details><summary>Show cancelled jobs</summary>" in markdown
    assert markdown.index("### Failed") < markdown.index("Cancelled by fail-fast")


def test_the_annotation_is_a_single_workflow_notice_line():
    annotation = render_annotation(summarize(_fail_fast_run()))

    assert annotation.startswith("::notice title=Module shard outcomes::")
    assert "\n" not in annotation


@pytest.mark.parametrize("envelope", [True, False])
def test_both_the_api_envelope_and_a_bare_list_are_accepted(tmp_path, capsys, envelope):
    jobs = _fail_fast_run()
    payload = {"total_count": len(jobs), "jobs": jobs} if envelope else jobs
    path = tmp_path / "jobs.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert main(["--jobs-file", str(path)]) == 0
    assert "module-tests (release shard 1/1)" in capsys.readouterr().out


def test_the_summary_is_appended_to_the_github_step_summary(tmp_path, monkeypatch, capsys):
    path = tmp_path / "jobs.json"
    path.write_text(json.dumps(_fail_fast_run()), encoding="utf-8")
    step_summary = tmp_path / "step-summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(step_summary))

    assert main(["--jobs-file", str(path)]) == 0
    capsys.readouterr()

    assert "module-tests (release shard 1/1)" in step_summary.read_text(encoding="utf-8")


def test_an_empty_payload_is_not_treated_as_a_summariser_failure(tmp_path, capsys):
    """This runs in an `if: always()` step; it must never be the reason a run goes red."""
    path = tmp_path / "jobs.json"
    path.write_text("", encoding="utf-8")

    assert main(["--jobs-file", str(path)]) == 0
    assert "nothing to summarize" in capsys.readouterr().err


def test_malformed_job_entries_do_not_crash_the_summariser():
    summary = summarize([None, "not-a-job", {"name": "module-tests (unit shard 1/2)", "conclusion": "failure"}])

    assert [outcome.name for outcome in summary.failed] == ["module-tests (unit shard 1/2)"]
    assert len(summary.other) == 2
