"""Main-push CI reaches the fleet through the reporter's existing CLI entry point."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
import yaml

from scripts.ci import fleet_main, fleet_verdict
from tests.ci.test_fleet_verdict import API, HEAD, IDS, REPO, ROOT

pytestmark = pytest.mark.fast


def test_main_push_event_selects_main_reporting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    api = API()
    source = api.runs["ci-modules.yml"][0]
    source.update(event="push", head_branch="main", pull_requests=[])
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"workflow_run": source}))
    output = tmp_path / "output"
    output.touch()
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(fleet_verdict, "GitHub", lambda repository: api)
    monkeypatch.setattr(sys, "argv", ["fleet_verdict.py", "--event", str(event), "--repository", REPO, "--reporter-id", "123", "--attempt", "1"])

    fleet_verdict.main()

    assert "main=true\n" in output.read_text()
    assert IDS["ci-modules.yml"] == source["workflow_id"]
    assert not api.posts


class MainAPI(API):
    def __init__(self):
        super().__init__()

        self.head = HEAD
        self.incidents = []
        self.mutations = []
        self.head_reads = 0
        self.move_on_second_read = False
        for name, rows in self.runs.items():
            if name != fleet_verdict.AGGREGATE:
                for row in rows:
                    row.update(event="push", head_branch="main", head_repository={"full_name": REPO}, pull_requests=[])

    def request(self, path, payload=None):

        if payload is not None:
            self.mutations.append((path, copy.deepcopy(payload)))
            if path == "issues":
                self.incidents.append({"number": 20, "state": "open", "user": {"type": "Bot"}, **payload})
            else:
                self.comments.append({"user": {"type": "Bot"}, **payload})
            return {}
        if path == "git/ref/heads/main":
            self.head_reads += 1
            return {"object": {"sha": "c" * 40 if self.move_on_second_read and self.head_reads > 1 else self.head}}
        if path == "issues/20":
            return copy.deepcopy(self.incidents[0])
        return super().request(path, payload)

    def pages(self, path, field=None):

        if path == "issues?state=open&labels=from%3Aci":
            return copy.deepcopy(self.incidents)
        if path == "issues/20/comments":
            return copy.deepcopy(self.comments)
        return super().pages(path, field)


def test_red_main_reaches_existing_fleet_p0_intake_and_deduplicates() -> None:

    api = MainAPI()
    api.runs["ci-quality.yml"][0]["conclusion"] = "failure"
    fleet_main.report(api, ROOT, IDS, 123, 1)
    path, payload = api.mutations[0]
    assert path == "issues"
    assert payload["labels"] == ["type:fix", "priority:P0", "from:ci", "status:triage"]
    assert f"[ci] red @{HEAD}" in payload["body"]
    assert '"run_attempt": 1' in payload["body"]
    fleet_main.report(api, ROOT, IDS, 124, 1)
    assert len(api.mutations) == 1


def test_recovery_is_appended_without_closure_or_new_incident() -> None:

    api = MainAPI()
    quality = api.runs["ci-quality.yml"][0]
    quality["conclusion"] = "failure"
    fleet_main.report(api, ROOT, IDS, 123, 1)
    quality.update(conclusion="success", run_attempt=2)
    fleet_main.report(api, ROOT, IDS, 124, 1)
    assert len(api.mutations) == 2
    path, payload = api.mutations[1]
    assert path == "issues/20/comments"
    assert "[ci] green @" in payload["body"]
    assert '"run_attempt": 2' in payload["body"]
    assert set(payload) == {"body"}
    fleet_main.report(api, ROOT, IDS, 125, 1)
    assert len(api.mutations) == 2


@pytest.mark.parametrize("conclusion,expected", [("cancelled", "infra-error"), ("skipped", "running"), (None, "running")])
def test_incomplete_main_evidence_cannot_claim_green_or_open_p0(conclusion, expected) -> None:
    # Main coherence: a terminally-cancelled required run is infra-error (never green),
    # skipped/absent evidence stays running — and NONE of them opens a P0, because the
    # fleet_main.py intake gate keys on state == "red", which none of these are.
    api = MainAPI()
    api.runs["ci-modules.yml"][0].update(conclusion=conclusion)
    assert fleet_main.snapshot(api, ROOT, IDS)["state"] == expected
    fleet_main.report(api, ROOT, IDS, 123, 1)
    assert not api.mutations


def test_infra_error_tip_appended_to_open_incident_does_not_escalate() -> None:
    # An open red incident whose main tip later observes an infra-error (a cancelled
    # required run, not a code failure) records the observation as an appended comment;
    # it opens no new P0, changes no priority/label, and leaves the incident open —
    # only the fleet closes or re-prioritises an incident.
    api = MainAPI()
    api.runs["ci-quality.yml"][0]["conclusion"] = "failure"
    fleet_main.report(api, ROOT, IDS, 123, 1)
    assert api.mutations[0][0] == "issues"
    api.runs["ci-quality.yml"][0].update(conclusion="cancelled", run_attempt=2)
    fleet_main.report(api, ROOT, IDS, 124, 1)
    assert len(api.mutations) == 2
    path, payload = api.mutations[1]
    assert path == "issues/20/comments"
    assert f"[ci] infra-error @{HEAD}" in payload["body"]
    assert set(payload) == {"body"}
    assert api.incidents[0]["state"] == "open"


@pytest.mark.parametrize(
    "field,value",
    [
        ("event", "pull_request"),
        ("head_sha", "b" * 40),
        ("head_branch", "branch"),
        ("workflow_id", 999),
        ("path", ".github/workflows/fake.yml"),
        ("repository", {"full_name": "other/repo"}),
        ("head_repository", {"full_name": "other/repo"}),
        ("id", None),
        ("run_attempt", 0),
    ],
)
def test_mismatched_push_run_never_supplies_evidence(field, value) -> None:

    api = MainAPI()
    api.runs["ci-quality.yml"][0][field] = value
    evidence = fleet_main.snapshot(api, ROOT, IDS)
    assert evidence["runs"]["ci-quality.yml"] is None
    assert evidence["state"] == "running"


def test_main_move_before_publication_refuses_obsolete_p0() -> None:

    api = MainAPI()
    api.runs["ci-quality.yml"][0]["conclusion"] = "failure"
    api.move_on_second_read = True
    with pytest.raises(ValueError, match="main head or CI attempts changed"):
        fleet_main.report(api, ROOT, IDS, 123, 1)
    assert not api.mutations


def test_aggregate_must_match_current_modules_attempt() -> None:

    api = MainAPI()
    api.runs["ci-modules.yml"][0]["run_attempt"] = 2
    evidence = fleet_main.snapshot(api, ROOT, IDS)
    assert evidence["runs"][fleet_verdict.AGGREGATE] is None
    assert evidence["state"] == "running"


def test_main_report_job_has_only_issue_write_permission() -> None:

    workflow = yaml.safe_load((ROOT / ".github/workflows/ci-fleet-verdict.yml").read_text())
    job = workflow["jobs"]["report-main"]
    assert job["permissions"] == {"contents": "read", "actions": "read", "issues": "write"}
    assert job["concurrency"] == {"group": "ci-fleet-verdict-main", "cancel-in-progress": False}
    assert job["if"] == "needs.identify.outputs.main == 'true'"
    checkout = job["steps"][0]
    assert "ref" not in checkout["with"]
    assert checkout["with"]["persist-credentials"] is False


def test_latest_run_attempt_supersedes_old_failure() -> None:
    api = MainAPI()
    old = api.runs["ci-quality.yml"][0]
    old["conclusion"] = "failure"
    api.runs["ci-quality.yml"].append({**old, "run_attempt": 2, "conclusion": "success"})
    evidence = fleet_main.snapshot(api, ROOT, IDS)
    assert evidence["state"] == "green"
    assert evidence["runs"]["ci-quality.yml"]["run_attempt"] == 2


def test_absent_conditional_gate_is_explicit_and_its_failure_is_observed() -> None:
    api = MainAPI()
    drift = api.runs.pop("check-spec-kitty-events-alignment.yml")
    evidence = fleet_main.snapshot(api, ROOT, IDS)
    assert evidence["scope"] == "continuous-main-push"
    assert evidence["conditional_gates_not_observed"] == ["check-spec-kitty-events-alignment.yml"]
    assert evidence["state"] == "green"
    drift[0]["conclusion"] = "failure"
    api.runs["check-spec-kitty-events-alignment.yml"] = drift
    assert fleet_main.snapshot(api, ROOT, IDS)["state"] == "red"


def test_existing_incident_gets_new_main_head_without_duplicate_p0() -> None:
    api = MainAPI()
    api.runs["ci-quality.yml"][0]["conclusion"] = "failure"
    fleet_main.report(api, ROOT, IDS, 123, 1)
    api.head = "d" * 40
    for name, rows in api.runs.items():
        if name != fleet_verdict.AGGREGATE:
            for row in rows:
                row["head_sha"] = api.head
    fleet_main.report(api, ROOT, IDS, 124, 1)
    assert [path for path, _ in api.mutations] == ["issues", "issues/20/comments"]
    assert f"[ci] red @{api.head}" in api.mutations[-1][1]["body"]


def test_dry_run_never_creates_incident(capsys) -> None:
    api = MainAPI()
    api.runs["ci-quality.yml"][0]["conclusion"] = "failure"
    fleet_main.report(api, ROOT, IDS, 123, 1, dry_run=True)
    assert f"[ci] red @{HEAD}" in capsys.readouterr().out
    assert not api.mutations


def test_attempt_change_during_publication_refuses_stale_verdict() -> None:
    class RerunAPI(MainAPI):
        def request(self, path, payload=None):
            if path == "git/ref/heads/main" and self.head_reads == 1:
                self.runs["ci-quality.yml"][0].update(run_attempt=2, status="in_progress", conclusion=None)
            return super().request(path, payload)

    api = RerunAPI()
    api.runs["ci-quality.yml"][0]["conclusion"] = "failure"
    with pytest.raises(ValueError, match="main head or CI attempts changed"):
        fleet_main.report(api, ROOT, IDS, 123, 1)
    assert not api.mutations


def test_duplicate_open_incidents_refuse_ambiguous_ownership() -> None:
    api = MainAPI()
    api.incidents = [{"number": n, "body": fleet_main.INCIDENT, "user": {"type": "Bot"}} for n in [20, 21]]
    with pytest.raises(ValueError, match="multiple active"):
        fleet_main.report(api, ROOT, IDS, 123, 1)
    assert not api.mutations


def test_main_cli_dry_run_is_read_only(monkeypatch, capsys) -> None:
    api = MainAPI()
    monkeypatch.setattr(fleet_main, "GitHub", lambda repository: api)
    monkeypatch.setattr(sys, "argv", ["fleet_main", "--repository", REPO, "--reporter-id", "123", "--attempt", "1", "--dry-run"])
    fleet_main.main()
    assert f"[ci] green @{HEAD}" in capsys.readouterr().out
    assert not api.mutations
