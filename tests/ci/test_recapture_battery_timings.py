"""Tests for ``scripts/ci/recapture_battery_timings.py`` (#6365).

The battery's per-file timing table is refreshed on a schedule from the junit of recent
nightly ``architectural-backstop`` runs. The graded surface is :func:`main`, driven against a
temporary repository; every external call (``gh run list``, ``gh run download``, the canonical
producer) goes through ``subprocess.run`` and is answered by :class:`Fake`, which records the
argument lists and environments. No network, gh or real capture runs. The pure decisions
(:func:`needs_refresh`, :func:`is_junit_capture`, :func:`merge_suite`) are tested directly, and
the workflow wiring is pinned structurally.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from kernel.clock import parse_iso
from scripts.ci import capture_shard_timings
from scripts.ci import recapture_battery_timings as battery
from scripts.ci import recapture_shard_timings as recapture

pytestmark = pytest.mark.fast

FAKE_GH_TOKEN = "fake-read-only-workflow-token-not-a-real-secret"  # noqa: S105 (obviously-fake test value)
FAKE_PAT = "fake-recapture-pat-not-a-real-secret"  # noqa: S105 (obviously-fake test value)
REPOSITORY = "spec-kitty/spec-kitty"
NOW = parse_iso("2026-10-18T12:00:00+00:00")
RECENT = "2026-10-15T00:00:00+00:00"
STALE = "2026-09-01T00:00:00+00:00"
RECAPTURE_WORKFLOW = recapture.REPO_ROOT / ".github" / "workflows" / "ci-shard-recapture.yml"
NIGHTLY_WORKFLOW = recapture.REPO_ROOT / ".github" / "workflows" / "ci-nightly.yml"


def _junit_provenance(files: int, *, captured_at: str = RECENT, run_ids: list[str] | None = None) -> dict[str, Any]:
    return {
        "producer": capture_shard_timings.BATTERY_PRODUCER,
        "source": "junit",
        "captured_at": captured_at,
        "selection": "not performance and not stress and not timing",
        "workers": 4,
        "files_measured": files,
        "run_ids": run_ids or ["nightly-1"],
        "unresolved_testcases": 0,
    }


def _payload(durations: dict[str, float], provenance: dict[str, Any], *, modules: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {"battery_file_durations": {"architectural": durations}, "battery_capture_provenance": {"architectural": provenance}}
    if modules:
        payload["module_test_durations"] = {"unit": [0.5, 0.5]}
        payload["module_test_count"] = {"unit": 2}
    return payload


SEED = {"producer": "census-seed", "source": "ci-job-logs", "captured_at": "2026-10-01T14:13:31+00:00", "files_measured": 2}
TWO_FILES = {"tests/architectural/test_a.py": 1.0, "tests/architectural/test_b.py": 2.0}
THREE_FILES = {**TWO_FILES, "tests/architectural/test_c.py": 3.0}


# --------------------------------------------------------------------------- #
# Pure decisions.                                                             #
# --------------------------------------------------------------------------- #


def test_the_census_seed_is_always_refreshed() -> None:
    committed = _payload(TWO_FILES, SEED)
    fresh = _payload(TWO_FILES, _junit_provenance(2))
    reason = battery.needs_refresh(committed, fresh, now=NOW)
    assert reason is not None and "not a junit capture" in reason


def test_a_changed_file_set_is_refreshed() -> None:
    committed = _payload(TWO_FILES, _junit_provenance(2))
    fresh = _payload(THREE_FILES, _junit_provenance(3))
    assert battery.needs_refresh(committed, fresh, now=NOW) == "file set changed (1 added, 0 removed)"


def test_an_old_junit_capture_is_refreshed() -> None:
    committed = _payload(TWO_FILES, _junit_provenance(2, captured_at=STALE))
    fresh = _payload({file: value * 2 for file, value in TWO_FILES.items()}, _junit_provenance(2))
    reason = battery.needs_refresh(committed, fresh, now=NOW)
    assert reason is not None and "47 days old" in reason


def test_paired_control_a_recent_capture_of_the_same_files_is_kept() -> None:
    """Only new medians, same file set, captured within the window: no daily churn."""
    committed = _payload(TWO_FILES, _junit_provenance(2))
    fresh = _payload({file: value * 2 for file, value in TWO_FILES.items()}, _junit_provenance(2))
    assert battery.needs_refresh(committed, fresh, now=NOW) is None


def test_an_unparseable_captured_at_is_refreshed() -> None:
    committed = _payload(TWO_FILES, _junit_provenance(2, captured_at="yesterday"))
    reason = battery.needs_refresh(committed, _payload(TWO_FILES, _junit_provenance(2)), now=NOW)
    assert reason is not None and "not an ISO timestamp" in reason


def test_a_missing_committed_table_is_refreshed() -> None:
    reason = battery.needs_refresh({}, _payload(TWO_FILES, _junit_provenance(2)), now=NOW)
    assert reason is not None and "not a junit capture" in reason


@pytest.mark.parametrize(
    ("provenance", "run_ids", "expected"),
    [
        (_junit_provenance(2, run_ids=["nightly-1", "nightly-2"]), None, True),
        (_junit_provenance(2, run_ids=["nightly-1", "nightly-2"]), ["nightly-1", "nightly-2"], True),
        (_junit_provenance(2, run_ids=["nightly-1"]), ["nightly-1", "nightly-2"], False),
        (SEED, None, False),
        ({**_junit_provenance(2), "source": "ci-job-logs"}, None, False),
    ],
    ids=["junit", "junit-expected-runs", "other-runs", "census-seed", "other-source"],
)
def test_is_junit_capture(provenance: dict[str, Any], run_ids: list[str] | None, expected: bool) -> None:
    assert battery.is_junit_capture(provenance, run_ids) is expected


def test_merge_suite_replaces_only_the_battery_tables() -> None:
    current = _payload(TWO_FILES, SEED)
    fresh = _payload(THREE_FILES, _junit_provenance(3), modules=False)
    merged = battery.merge_suite(current, fresh)
    assert merged["battery_file_durations"]["architectural"] == THREE_FILES
    assert merged["battery_capture_provenance"]["architectural"] == _junit_provenance(3)
    assert merged["module_test_durations"] == current["module_test_durations"]
    assert merged["module_test_count"] == current["module_test_count"]


def test_suite_tables_tolerates_a_malformed_payload() -> None:
    assert battery.suite_tables({"battery_file_durations": [], "battery_capture_provenance": {"architectural": "x"}}) == ({}, {})


# --------------------------------------------------------------------------- #
# The step, against a temporary repository and a fake subprocess.             #
# --------------------------------------------------------------------------- #


@dataclass
class Fake:
    """Answers ``gh run list`` / ``gh run download`` / the producer, and records every call."""

    timings_path: Path
    run_ids: list[int] = field(default_factory=lambda: [30, 20, 10, 5])
    no_artifact: set[str] = field(default_factory=set)
    empty_artifact: set[str] = field(default_factory=set)
    fresh: dict[str, float] = field(default_factory=lambda: dict(THREE_FILES))
    producer_outcome: str = "valid"
    calls: list[list[str]] = field(default_factory=list)
    envs: list[dict[str, str] | None] = field(default_factory=list)

    def run(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(cmd))
        self.envs.append(kwargs.get("env"))
        if cmd[:3] == ["gh", "run", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps([{"databaseId": run_id} for run_id in self.run_ids]), stderr="")
        if cmd[:3] == ["gh", "run", "download"]:
            return self._download(cmd)
        if "scripts.ci.capture_shard_timings" in cmd:
            return self._produce(cmd, kwargs)
        raise AssertionError(f"unexpected subprocess: {cmd}")

    def _download(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        run_id = cmd[3]
        if run_id in self.no_artifact:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="no artifact matches any of the names or patterns provided")
        directory = Path(cmd[cmd.index("--dir") + 1])
        directory.mkdir(parents=True, exist_ok=True)
        if run_id not in self.empty_artifact:
            (directory / "xunit-nightly-architectural.xml").write_text("<testsuites/>", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    def _produce(self, cmd: list[str], kwargs: dict[str, Any]) -> subprocess.CompletedProcess[str]:
        if self.producer_outcome == "timeout":
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        if self.producer_outcome == "crash":
            return subprocess.CompletedProcess(cmd, 1)
        run_ids = [cmd[index + 1] for index, part in enumerate(cmd) if part == "--run-id"]
        if self.producer_outcome == "wrong-runs":
            run_ids = ["nightly-other"]
        output = Path(cmd[cmd.index("--output") + 1])
        current = json.loads(self.timings_path.read_text(encoding="utf-8"))
        merged = capture_shard_timings.merge_battery_capture(current, "architectural", self.fresh, {**_junit_provenance(len(self.fresh)), "run_ids": run_ids})
        output.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0)

    def producer_calls(self) -> list[list[str]]:
        return [cmd for cmd in self.calls if "scripts.ci.capture_shard_timings" in cmd]

    def downloads(self) -> list[str]:
        return [cmd[3] for cmd in self.calls if cmd[:3] == ["gh", "run", "download"]]


@pytest.fixture
def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Fake:
    root = tmp_path / "repo"
    (root / ".github").mkdir(parents=True)
    timings_path = root / ".github" / "ci-shard-timings.json"
    timings_path.write_text(json.dumps(_payload(TWO_FILES, SEED), indent=2) + "\n", encoding="utf-8")
    fake = Fake(timings_path=timings_path)
    monkeypatch.setattr(recapture, "TIMINGS_PATH", timings_path)
    monkeypatch.setattr(battery, "REPO_ROOT", root)
    monkeypatch.setattr(battery, "now_utc", lambda: NOW)
    monkeypatch.setattr(subprocess, "run", fake.run)
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "github-output.txt"))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
    monkeypatch.setenv("GH_TOKEN", FAKE_GH_TOKEN)
    monkeypatch.setenv("GITHUB_TOKEN", "ambient-github-token")
    monkeypatch.delenv(recapture.SECRET_NAME, raising=False)
    monkeypatch.setenv(recapture.RESULT_ENV_VAR, recapture.RecaptureResult(drifted=("unit",), captured=("unit",)).to_json())
    return fake


def _main(tmp_path: Path) -> tuple[int, dict[str, str], recapture.RecaptureResult]:
    exit_code = battery.main(["--junit-root", str(tmp_path / "junit")])
    outputs = dict(line.partition("=")[::2] for line in Path(os.environ["GITHUB_OUTPUT"]).read_text(encoding="utf-8").splitlines())
    return exit_code, outputs, recapture.RecaptureResult.from_json(outputs["result"])


def _committed(fake: Fake) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(fake.timings_path.read_text(encoding="utf-8"))
    return loaded


def test_the_seed_table_is_replaced_from_the_three_newest_nightly_runs(fake: Fake, tmp_path: Path) -> None:
    exit_code, outputs, result = _main(tmp_path)

    assert exit_code == 0
    assert fake.downloads() == ["30", "20", "10"]
    (producer,) = fake.producer_calls()
    assert producer[producer.index("--suite") + 1] == "architectural"
    assert [producer[index + 1] for index, part in enumerate(producer) if part == "--run-id"] == ["nightly-30", "nightly-20", "nightly-10"]
    assert "--write" not in producer  # the producer writes a scratch file, never the committed one
    committed = _committed(fake)
    assert committed["battery_file_durations"]["architectural"] == THREE_FILES
    assert committed["battery_capture_provenance"]["architectural"]["run_ids"] == ["nightly-30", "nightly-20", "nightly-10"]
    assert committed["module_test_durations"] == {"unit": [0.5, 0.5]}  # the module captures of this run are kept
    assert outputs["drift"] == "true"
    assert result.captured == ("unit",)
    assert result.battery_captured == ("architectural",)


def test_runs_without_a_usable_artefact_are_skipped(fake: Fake, tmp_path: Path) -> None:
    fake.no_artifact = {"30"}
    fake.empty_artifact = {"20"}

    exit_code, _, result = _main(tmp_path)

    assert exit_code == 0
    assert fake.downloads() == ["30", "20", "10", "5"]
    (producer,) = fake.producer_calls()
    assert [producer[index + 1] for index, part in enumerate(producer) if part == "--run-id"] == ["nightly-10", "nightly-5"]
    assert result.battery_captured == ("architectural",)


def test_no_usable_nightly_junit_fails_and_leaves_the_table_but_keeps_the_module_result(fake: Fake, tmp_path: Path) -> None:
    fake.no_artifact = {"30", "20", "10", "5"}
    before = fake.timings_path.read_bytes()

    exit_code, outputs, result = _main(tmp_path)

    assert exit_code == 1
    assert fake.producer_calls() == []
    assert fake.timings_path.read_bytes() == before
    assert outputs["drift"] == "true"  # the module capture is still published
    assert result.captured == ("unit",)
    assert result.battery_failed == ("architectural",)
    assert "no ci-nightly-architectural-backstop-reports junit" in result.reasons[recapture.battery_reason_key("architectural")]


@pytest.mark.parametrize(
    ("outcome", "reason_part"),
    [("crash", "producer exited 1"), ("timeout", "timed out"), ("wrong-runs", "no junit provenance for these runs")],
)
def test_an_invalid_capture_fails_and_leaves_the_table(fake: Fake, tmp_path: Path, outcome: str, reason_part: str) -> None:
    fake.producer_outcome = outcome
    before = fake.timings_path.read_bytes()

    exit_code, _, result = _main(tmp_path)

    assert exit_code == 1
    assert fake.timings_path.read_bytes() == before
    assert reason_part in result.reasons[recapture.battery_reason_key("architectural")]


def test_a_current_table_is_left_alone(fake: Fake, tmp_path: Path) -> None:
    fake.timings_path.write_text(json.dumps(_payload(THREE_FILES, _junit_provenance(3)), indent=2) + "\n", encoding="utf-8")
    fake.fresh = {file: value + 1 for file, value in THREE_FILES.items()}
    before = fake.timings_path.read_bytes()

    exit_code, outputs, result = _main(tmp_path)

    assert exit_code == 0
    assert fake.timings_path.read_bytes() == before
    assert result.battery_captured == ()
    assert result.battery_failed == ()
    assert outputs["drift"] == "true"  # only because of the module capture


def test_paired_control_nothing_to_publish_when_neither_modules_nor_battery_changed(fake: Fake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(recapture.RESULT_ENV_VAR, recapture.RecaptureResult().to_json())
    fake.timings_path.write_text(json.dumps(_payload(THREE_FILES, _junit_provenance(3)), indent=2) + "\n", encoding="utf-8")

    exit_code, outputs, _ = _main(tmp_path)

    assert exit_code == 0
    assert outputs["drift"] == "false"


def test_an_empty_module_result_still_reports_the_battery_refresh(fake: Fake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(recapture.RESULT_ENV_VAR)

    exit_code, outputs, result = _main(tmp_path)

    assert exit_code == 0
    assert outputs["drift"] == "true"
    assert result.captured == ()
    assert result.battery_captured == ("architectural",)


def test_a_malformed_module_result_fails_loud(fake: Fake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(recapture.RESULT_ENV_VAR, "{not json")
    with pytest.raises(SystemExit) as exc_info:
        battery.main(["--junit-root", str(tmp_path / "junit")])
    assert exc_info.value.code == 1


def test_the_recapture_pat_is_refused(fake: Fake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv(recapture.SECRET_NAME, FAKE_PAT)

    assert battery.main(["--junit-root", str(tmp_path / "junit")]) == 1

    assert fake.calls == []
    assert recapture.SECRET_NAME in capsys.readouterr().err


def test_without_the_read_token_nothing_is_called_and_the_refresh_fails(fake: Fake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GH_TOKEN")

    exit_code, _, result = _main(tmp_path)

    assert exit_code == 1
    assert fake.calls == []
    assert "GH_TOKEN is not set" in result.reasons[recapture.battery_reason_key("architectural")]


def test_the_read_token_reaches_only_gh_and_no_call_gets_another_token(fake: Fake, tmp_path: Path) -> None:
    _main(tmp_path)

    for cmd, env in zip(fake.calls, fake.envs, strict=True):
        assert env is not None
        assert "GITHUB_TOKEN" not in env
        assert recapture.SECRET_NAME not in env
        if cmd[0] == "gh":
            assert env["GH_TOKEN"] == FAKE_GH_TOKEN
        else:
            assert "GH_TOKEN" not in env
        assert FAKE_GH_TOKEN not in cmd


def test_gh_run_list_targets_completed_nightly_runs_on_main(fake: Fake, tmp_path: Path) -> None:
    _main(tmp_path)

    (listing,) = [cmd for cmd in fake.calls if cmd[:3] == ["gh", "run", "list"]]
    assert listing[listing.index("--workflow") + 1] == battery.NIGHTLY_WORKFLOW
    assert listing[listing.index("--branch") + 1] == "main"
    assert listing[listing.index("--status") + 1] == "completed"
    assert listing[listing.index("--repo") + 1] == REPOSITORY
    for cmd in fake.calls:
        if cmd[:3] == ["gh", "run", "download"]:
            assert cmd[cmd.index("--name") + 1] == battery.ARTIFACT_NAME


def test_a_non_list_run_listing_fails_loud(fake: Fake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = fake.run

    def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:3] == ["gh", "run", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout='{"databaseId": 1}', stderr="")
        return original(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(SystemExit) as exc_info:
        battery.main(["--junit-root", str(tmp_path / "junit")])
    assert exc_info.value.code == 1


def test_a_usage_error_exits_2() -> None:
    assert battery.main([]) == 2


# --------------------------------------------------------------------------- #
# Workflow shape.                                                             #
# --------------------------------------------------------------------------- #


def _recapture_job() -> dict[str, Any]:
    import yaml

    job: dict[str, Any] = yaml.safe_load(RECAPTURE_WORKFLOW.read_text(encoding="utf-8"))["jobs"]["recapture-shard-timings"]
    return job


def _step_index(steps: list[dict[str, Any]], step_id: str) -> int:
    return next(index for index, step in enumerate(steps) if step.get("id") == step_id)


def test_the_battery_step_runs_between_the_module_capture_and_publish() -> None:
    steps = _recapture_job()["steps"]
    battery_index = _step_index(steps, "battery")
    assert _step_index(steps, "capture") < battery_index
    publish_index = next(index for index, step in enumerate(steps) if "Publish" in str(step.get("name", "")))
    assert battery_index < publish_index
    step = steps[battery_index]
    assert "!cancelled()" in step["if"]  # runs even when a module capture failed
    assert "python -m scripts.ci.recapture_battery_timings --junit-root" in step["run"]
    assert step["env"][recapture.RESULT_ENV_VAR] == "${{ steps.capture.outputs.result }}"


def test_the_battery_step_gets_only_the_read_only_workflow_token() -> None:
    job = _recapture_job()
    step = job["steps"][_step_index(job["steps"], "battery")]
    assert step["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert recapture.SECRET_NAME not in step["env"]
    assert job["permissions"] == {"contents": "read", "actions": "read"}


def test_publish_takes_the_combined_result_and_runs_on_either_drift() -> None:
    steps = _recapture_job()["steps"]
    publish = next(step for step in steps if "Publish" in str(step.get("name", "")))
    assert "steps.battery.outputs.drift == 'true'" in publish["if"]
    assert "steps.capture.outputs.drift == 'true'" in publish["if"]
    assert publish["env"][recapture.RESULT_ENV_VAR] == "${{ steps.battery.outputs.result || steps.capture.outputs.result }}"


def test_the_downloaded_artefact_is_the_one_the_nightly_backstop_uploads() -> None:
    import yaml

    nightly = yaml.safe_load(NIGHTLY_WORKFLOW.read_text(encoding="utf-8"))
    uploads = [step for step in nightly["jobs"]["architectural-backstop"]["steps"] if str(step.get("uses", "")).startswith("actions/upload-artifact@")]
    assert [step["with"]["name"] for step in uploads] == [battery.ARTIFACT_NAME]
    assert NIGHTLY_WORKFLOW.name == battery.NIGHTLY_WORKFLOW


def test_the_job_timeout_still_covers_the_capture_budget_plus_the_battery_step() -> None:
    import re

    job = _recapture_job()
    capture_step = job["steps"][_step_index(job["steps"], "capture")]
    budget_match = re.search(r"--budget-seconds\s+(\d+)", capture_step["run"])
    assert budget_match is not None
    battery_step = job["steps"][_step_index(job["steps"], "battery")]
    setup_and_publish = 10 * 60
    total = int(budget_match.group(1)) + recapture.DEFAULT_CAPTURE_TIMEOUT_SECONDS + int(battery_step["timeout-minutes"]) * 60 + setup_and_publish
    assert total <= int(job["timeout-minutes"]) * 60
