"""Unit tests for ``scripts/ci/sonar_coverage_provenance.py``.

The fixtures are recorded ``listWorkflowRuns`` payloads, so the provenance
decisions are exercised without a workflow run or a GitHub API call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.ci.sonar_coverage_provenance import (
    ProvenanceError,
    load_payload,
    main,
    reconcile_coverage,
    select_runs,
)

pytestmark = [pytest.mark.fast]

_SOURCE = "1" * 40
_OTHER = "2" * 40


def _run(
    run_id: int,
    *,
    head_sha: str = _SOURCE,
    branch: str = "main",
    run_number: int = 10,
    attempt: int = 1,
    status: str = "completed",
    conclusion: str | None = "success",
) -> dict[str, Any]:
    return {
        "id": run_id,
        "run_number": run_number,
        "run_attempt": attempt,
        "head_sha": head_sha,
        "head_branch": branch,
        "status": status,
        "conclusion": conclusion,
        "name": "CI Modules",
        "path": ".github/workflows/ci-modules.yml",
    }


def _payload(*runs: dict[str, Any]) -> dict[str, Any]:
    return {"total_count": len(runs), "workflow_runs": list(runs)}


def _outputs(path: Path) -> dict[str, str]:
    return {key: value for key, _, value in (line.partition("=") for line in path.read_text(encoding="utf-8").splitlines())}


def test_selects_the_run_at_the_checked_out_revision_not_the_newest_branch_run() -> None:
    selection = select_runs(
        _payload(
            _run(300, head_sha=_OTHER, run_number=30),
            _run(200, run_number=20),
        ),
        source_sha=_SOURCE,
        branch="main",
    )

    assert selection.primary is not None
    assert selection.primary.run_id == 200
    assert selection.coverage_available is True
    assert selection.ignored == {"at another source revision": 1}
    assert "source revision " + _SOURCE in selection.reason


def test_ignores_a_same_sha_run_from_another_branch() -> None:
    selection = select_runs(
        _payload(
            _run(300, branch="release", run_number=30),
            _run(200, branch="main", run_number=20),
        ),
        source_sha=_SOURCE,
        branch="main",
    )

    assert selection.primary is not None
    assert selection.primary.run_id == 200
    assert selection.ignored == {"on another branch": 1}


def test_no_matching_run_is_an_informational_no_coverage_verdict(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    payload = tmp_path / "runs.json"
    payload.write_text(json.dumps(_payload(_run(300, head_sha=_OTHER))), encoding="utf-8")
    output = tmp_path / "github_output"
    output.touch()

    code = main(["select", "--runs", str(payload), "--source-sha", _SOURCE, "--branch", "main", "--output", str(output)])

    assert code == 0, "a missing matching run must never fail the advisory Sonar job"
    values = _outputs(output)
    assert values["run_id"] == ""
    assert values["fallback_run_id"] == ""
    assert values["coverage_available"] == "false"
    assert "without coverage" in values["reason"]
    assert "another revision" in values["reason"]
    captured = capsys.readouterr()
    assert "::warning::sonar:" in captured.out
    assert "ignored 1 candidate run(s)" in captured.out


def test_no_runs_at_all_is_a_clear_no_coverage_verdict() -> None:
    selection = select_runs(_payload(), source_sha=_SOURCE, branch="main")

    assert selection.primary is None
    assert selection.coverage_available is False
    assert "no CI Modules run returned" in selection.reason
    assert "without coverage" in selection.reason


def test_selection_is_deterministic_independent_of_payload_order() -> None:
    newer = _run(300, run_number=30)
    older = _run(200, run_number=20)

    forward = select_runs(_payload(newer, older), source_sha=_SOURCE, branch="main")
    reversed_payload = select_runs(_payload(older, newer), source_sha=_SOURCE, branch="main")

    assert forward.primary == reversed_payload.primary
    assert forward.fallback == reversed_payload.fallback
    assert forward.primary is not None and forward.primary.run_id == 300
    assert forward.fallback is not None and forward.fallback.run_id == 200


def test_latest_successful_rerun_attempt_is_selected() -> None:
    selection = select_runs(
        _payload(
            _run(200, run_number=20, attempt=1, conclusion="failure"),
            _run(200, run_number=20, attempt=2, conclusion="success"),
        ),
        source_sha=_SOURCE,
        branch="main",
    )

    assert selection.primary is not None
    assert selection.primary.run_id == 200
    assert selection.primary.run_attempt == 2


def test_failed_latest_attempt_never_falls_back_to_an_older_success() -> None:
    selection = select_runs(
        _payload(
            _run(200, run_number=20, attempt=1, conclusion="success"),
            _run(200, run_number=20, attempt=2, conclusion="failure"),
        ),
        source_sha=_SOURCE,
        branch="main",
    )

    assert selection.primary is None
    assert selection.ignored == {"with failure conclusion": 1}
    assert "without coverage" in selection.reason


@pytest.mark.parametrize("status", ["in_progress", "queued", "success", "unknown"])
def test_inconsistent_or_non_rest_success_is_not_evidence(status: str) -> None:
    selection = select_runs(_payload(_run(200, status=status)), source_sha=_SOURCE)
    assert selection.primary is None


def test_latest_artifact_attempt_wins_within_a_successful_run(tmp_path: Path) -> None:
    current = tmp_path / "current"
    for attempt, content in [(1, "partial-old"), (2, "complete-new")]:
        directory = current / f"module-tests-unit-shard-1-of-1-attempt-{attempt}-reports" / "coverage"
        directory.mkdir(parents=True)
        (directory / "coverage-unit.xml").write_text(content, encoding="utf-8")
    result = reconcile_coverage(current=current, fallback=None)
    assert len(result.files) == 1
    assert result.files[0].read_text(encoding="utf-8") == "complete-new"


def test_fallback_is_only_ever_another_run_at_the_same_revision() -> None:
    selection = select_runs(
        _payload(
            _run(400, head_sha=_OTHER, run_number=40),
            _run(300, run_number=30),
            _run(200, run_number=20),
        ),
        source_sha=_SOURCE,
        branch="main",
    )

    assert selection.primary is not None and selection.primary.run_id == 300
    assert selection.fallback is not None and selection.fallback.run_id == 200
    assert selection.fallback.head_sha == _SOURCE
    assert selection.ignored == {"at another source revision": 1}


def test_reconcile_dedupes_by_basename_current_run_wins(tmp_path: Path) -> None:
    current = tmp_path / "current" / "shard-a"
    fallback = tmp_path / "previous" / "shard-b"
    current.mkdir(parents=True)
    fallback.mkdir(parents=True)
    (current / "coverage-a.xml").write_text("<current-a/>", encoding="utf-8")
    (current / "coverage-b.xml").write_text("<current-b/>", encoding="utf-8")
    (fallback / "coverage-b.xml").write_text("<stale-b/>", encoding="utf-8")
    (fallback / "coverage-c.xml").write_text("<fallback-c/>", encoding="utf-8")

    result = reconcile_coverage(current=tmp_path / "current", fallback=tmp_path / "previous")

    assert [path.name for path in result.files] == ["coverage-a.xml", "coverage-b.xml", "coverage-c.xml"]
    assert result.stale == ("coverage-c.xml",)
    assert "current/shard-a/coverage-b.xml" in result.report_paths
    assert "stale-b.xml" not in result.report_paths


def test_reconcile_without_coverage_warns_and_emits_no_paths(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "github_output"
    output.touch()

    code = main(
        [
            "reconcile",
            "--current",
            str(tmp_path / "absent-current"),
            "--fallback",
            str(tmp_path / "absent-fallback"),
            "--source-sha",
            _SOURCE,
            "--output",
            str(output),
        ]
    )

    assert code == 0
    values = _outputs(output)
    assert values["report-paths"] == ""
    assert values["coverage-files"] == "0"
    captured = capsys.readouterr().out
    assert "::warning::sonar:" in captured
    assert _SOURCE in captured


def test_payload_without_workflow_runs_is_a_helper_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    payload = tmp_path / "runs.json"
    payload.write_text(json.dumps({"total_count": 0}), encoding="utf-8")
    output = tmp_path / "github_output"
    output.touch()

    code = main(["select", "--runs", str(payload), "--source-sha", _SOURCE, "--output", str(output)])

    assert code == 2
    assert "without a workflow_runs key" in capsys.readouterr().err
    with pytest.raises(ProvenanceError, match="workflow_runs"):
        load_payload(payload)


@pytest.mark.parametrize("payload", [None, "bad", {"workflow_runs": "not a list"}])
def test_malformed_payload_shape_is_not_coverage(payload: Any) -> None:
    with pytest.raises(ProvenanceError):
        select_runs(payload, source_sha=_SOURCE)


def test_malformed_candidate_rows_are_ignored_not_selected() -> None:
    selection = select_runs([None, {}, {"id": "bad", "head_sha": _SOURCE}], source_sha=_SOURCE)
    assert selection.primary is None
    assert selection.ignored == {"malformed": 3}


@pytest.mark.parametrize("contents", [None, "not json"])
def test_missing_or_unparseable_run_file_fails_clearly(tmp_path: Path, contents: str | None) -> None:
    path = tmp_path / "runs.json"
    if contents is not None:
        path.write_text(contents, encoding="utf-8")
    with pytest.raises(ProvenanceError):
        load_payload(path)


def test_successful_cli_outputs_explain_same_revision_fallback(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "runs.json"
    path.write_text(json.dumps(_payload(_run(200, run_number=20), _run(100))), encoding="utf-8")
    assert main(["select", "--runs", str(path), "--source-sha", _SOURCE]) == 0
    output = capsys.readouterr().out
    assert "run_id=200" in output
    assert "fallback_run_id=100" in output
    assert "same source revision" in output
    current = tmp_path / "coverage"
    current.mkdir()
    (current / "coverage-probe.xml").write_text("<coverage/>", encoding="utf-8")
    assert main(["reconcile", "--current", str(current), "--source-sha", _SOURCE]) == 0
    assert "resolved 1 coverage report" in capsys.readouterr().out


def test_missing_source_revision_is_refused() -> None:
    with pytest.raises(ProvenanceError, match="source_sha is required"):
        select_runs(_payload(_run(1)), source_sha="")
