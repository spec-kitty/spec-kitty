"""Main-push CI reaches the fleet through the reporter's existing CLI entry point."""

from __future__ import annotations

import copy
import json
import sys
import threading
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


def test_main_recovery_within_budget_publishes_stabilized_evidence_not_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-003/FR-007/C-003 recovery for fleet_main.py: the first snapshot PAIR inside
    _attempt() disagrees (retry-worthy), the second pair agrees. report() must retry the
    WHOLE pair -- never fall through on the first stale read -- and publish using the
    stabilized (agreeing) evidence, never the original disagreeing one. RED against
    unmodified report(): the current code raises ValueError on the first disagreement
    instead of retrying."""
    api = MainAPI()
    monkeypatch.setattr(fleet_main.time, "sleep", lambda seconds: None)

    def evidence(state: str) -> dict:
        return {"head": HEAD, "state": state, "runs": {}, "scope": "continuous-main-push", "conditional_gates_not_observed": []}

    sequence = iter(
        [
            evidence("red"),  # pre-loop read (report()'s own, unused when dry_run=False)
            evidence("red"),  # attempt 1's own evidence read (red -> skip the not-red elif)
            evidence("running"),  # attempt 1's recheck (disagrees with the read above -> retry)
            evidence("red"),  # attempt 2's own evidence read (red -> skip the not-red elif)
            evidence("red"),  # attempt 2's recheck (agrees -> stabilized, ready to publish)
        ]
    )
    calls: list[int] = []

    def fake_snapshot(api_: MainAPI, root_: Path, ids_: dict) -> dict:
        calls.append(1)
        return next(sequence)

    monkeypatch.setattr(fleet_main, "snapshot", fake_snapshot)

    fleet_main.report(api, ROOT, IDS, 123, 1)

    assert len(calls) == 5, "expected 1 pre-loop read + 2 _attempt() calls (2 snapshot reads each)"
    assert len(api.mutations) == 1
    assert api.mutations[0][0] == "issues"
    assert f"[ci] red @{HEAD}" in api.mutations[0][1]["body"]


def test_main_exhausted_retry_budget_defers_silently_with_diagnostic(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """FR-004 terminal path for fleet_main.py: evidence that never stabilizes across the
    full retry budget must not raise and must not post/update an incident -- it defers
    silently (exit 0) with a diagnostic line naming the subject, "deferred"/"skipped",
    and the stabilization failure reason. RED against unmodified report(): the current
    code raises on the first disagreement."""
    api = MainAPI()
    monkeypatch.setattr(fleet_main.time, "sleep", lambda seconds: None)

    def evidence(state: str) -> dict:
        return {"head": HEAD, "state": state, "runs": {}, "scope": "continuous-main-push", "conditional_gates_not_observed": []}

    # pre-loop (unused) + 4 attempts, each [own-read=red (skip elif), recheck=running (disagree)]
    values = [evidence("running")] + [evidence("red"), evidence("running")] * 4
    sequence = iter(values)

    def fake_snapshot(api_: MainAPI, root_: Path, ids_: dict) -> dict:
        return next(sequence)

    monkeypatch.setattr(fleet_main, "snapshot", fake_snapshot)

    fleet_main.report(api, ROOT, IDS, 123, 1)

    assert api.mutations == []
    out = capsys.readouterr().out
    assert "deferred" in out or "skipped" in out
    assert "evidence did not stabilize within retry budget" in out


def test_main_exhausted_retry_budget_diagnostic_reports_final_attempt_head(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """RED-FIRST for PR-MERGED-005: on budget exhaustion, the diagnostic must report
    the head the FINAL retry attempt actually observed, never report()'s own
    pre-loop snapshot -- which can be one observation stale by the time the budget
    exhausts. RED against unmodified report(): the diagnostic prints the pre-loop
    snapshot's head even though every in-loop attempt observed a different, later
    head."""
    api = MainAPI()
    monkeypatch.setattr(fleet_main.time, "sleep", lambda seconds: None)

    pre_loop_head = "a" * 40
    final_head = "f" * 40

    def evidence(head: str, state: str) -> dict:
        return {"head": head, "state": state, "runs": {}, "scope": "continuous-main-push", "conditional_gates_not_observed": []}

    # pre-loop read (report()'s own, stale) + 4 attempts, each [own-read=red at
    # final_head (skip the not-red elif), recheck=running at final_head (disagrees
    # on state -> retry)] -- every in-loop observation is final_head, never
    # pre_loop_head.
    values = [evidence(pre_loop_head, "running")] + [evidence(final_head, "red"), evidence(final_head, "running")] * 4
    sequence = iter(values)

    def fake_snapshot(api_: MainAPI, root_: Path, ids_: dict) -> dict:
        return next(sequence)

    monkeypatch.setattr(fleet_main, "snapshot", fake_snapshot)

    fleet_main.report(api, ROOT, IDS, 123, 1)

    out = capsys.readouterr().out
    assert final_head in out, f"expected the final attempt's own head {final_head!r} in the diagnostic: {out!r}"
    assert pre_loop_head not in out, f"the stale pre-loop head {pre_loop_head!r} must not appear in the diagnostic: {out!r}"


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


def test_main_head_move_before_attempt_read_yields_nothing_to_report(monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-pin (Standing Order #4). Pre-fix, a head move between the single snapshot pair
    made report() raise immediately. Traced against the new retry contract: report()'s
    own pre-loop snapshot() (added this WP to fix the dry_run boundary) consumes the
    FIRST "git/ref/heads/main" read (unmoved, since MainAPI's `move_on_second_read`
    trigger is `head_reads > 1`). _attempt()'s own fresh evidence-read then becomes the
    SECOND overall read -- already moved. The moved head ("c"*40) matches no mocked run's
    fixed head_sha ("a"*40), so this attempt's own evidence is immediately "running", and
    with no open incident yet, the pre-existing (unchanged) `evidence["state"] != "red"`
    branch fires right there -- an informational print, no publish, no retry needed (this
    is NOT the binding two-attempt-coverage test; that is
    test_attempt_change_during_publication_refuses_stale_verdict below). This still
    protects the original invariant -- no obsolete/stale P0 is ever opened -- just via
    _NothingToReport() instead of a raise.
    """
    monkeypatch.setattr(fleet_main.time, "sleep", lambda seconds: None)
    api = MainAPI()
    api.runs["ci-quality.yml"][0]["conclusion"] = "failure"
    api.move_on_second_read = True

    fleet_main.report(api, ROOT, IDS, 123, 1)

    assert not api.mutations
    assert api.head_reads == 2, "expected 1 pre-loop read + 1 _attempt() own-evidence read (no retry, no recheck)"


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


def test_attempt_change_during_publication_refuses_stale_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-pin (Standing Order #4; operator ruling #2 / TASKS-FRESH3-001 remediation (b) --
    binding: this test MUST genuinely exercise _attempt() across at least two attempts).

    Traced empirically against the live mock and the new pre-loop-snapshot call order:
    the ORIGINAL `head_reads == 1` trigger no longer produces two-attempt coverage --
    report()'s own new pre-loop snapshot() now consumes the first "git/ref/heads/main"
    read, so the mutation lands on _attempt() attempt 1's OWN evidence-gathering read
    (not its recheck), and that mutation (status="in_progress", conclusion=None) flips
    state away from "red" before any incident exists -- the pre-existing not-red elif
    fires immediately and resolves on attempt 1 alone. That does not satisfy the binding
    requirement, so per the operator ruling the mock/test setup is adjusted here: the
    trigger point moves to `head_reads == 2` (attempt 1's OWN recheck read, not its
    evidence read), and the mutation is narrowed to bump only `run_attempt` (conclusion
    stays "failure") so the evidence classifies "red" throughout -- exercising a genuine
    disagreement WITHIN attempt 1 (its own read vs. its recheck), forcing a real retry
    (None), with attempt 2's own read and recheck then both landing on the
    already-mutated, now-stable state and agreeing -- _Ready. No raise: a successful
    incident IS created, using the STABILIZED (run_attempt=2) evidence, never the stale
    original (run_attempt=1).
    """

    class RerunAPI(MainAPI):
        def request(self, path, payload=None):
            if path == "git/ref/heads/main" and self.head_reads == 2:
                self.runs["ci-quality.yml"][0].update(run_attempt=2)
            return super().request(path, payload)

    monkeypatch.setattr(fleet_main.time, "sleep", lambda seconds: None)
    api = RerunAPI()
    api.runs["ci-quality.yml"][0]["conclusion"] = "failure"

    fleet_main.report(api, ROOT, IDS, 123, 1)

    assert len(api.mutations) == 1
    assert api.mutations[0][0] == "issues"
    assert f"[ci] red @{HEAD}" in api.mutations[0][1]["body"]
    assert '"run_attempt": 2' in api.mutations[0][1]["body"]
    assert api.head_reads == 5, "expected 1 pre-loop read + 2 _attempt() calls (2 reads each): a genuine retry"


def test_main_head_move_within_attempts_own_reads_forces_genuine_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supplementary coverage for the gap
    test_main_head_move_before_attempt_read_yields_nothing_to_report's rename gave up:
    that test's rename means no test now pins a literal head-SHA-move-within-one-attempt
    scenario. test_attempt_change_during_publication_refuses_stale_verdict covers the same
    `snapshot(...) != evidence` guard, but only via a `run_attempt` mutation -- this test
    mutates `head` specifically, while every matched run stays conclusion="failure" for
    BOTH head values, so `state` stays "red" throughout and the not-red `elif` in
    _attempt() never short-circuits it before the disagreement check runs.

    main's head moves between _attempt()'s own two reads on attempt 1: its evidence read
    (the 2nd overall read, after report()'s pre-loop snapshot()) still sees the original
    head, but its own recheck (the 3rd overall read) sees the moved head -- a genuine
    within-attempt disagreement on `head` alone, forcing a retry. Attempt 2's own two
    reads then agree (both see the now-stable moved head), so report() publishes using
    the STABILIZED (moved-head) evidence.
    """
    moved_head = "e" * 40

    class HeadMoveAPI(MainAPI):
        def request(self, path, payload=None):
            if path == "git/ref/heads/main" and self.head_reads == 2:
                self.head = moved_head
            return super().request(path, payload)

    monkeypatch.setattr(fleet_main.time, "sleep", lambda seconds: None)
    api = HeadMoveAPI()
    api.runs["ci-quality.yml"][0]["conclusion"] = "failure"
    moved_run = copy.deepcopy(api.runs["ci-quality.yml"][0])
    moved_run["head_sha"] = moved_head
    api.runs["ci-quality.yml"].append(moved_run)

    fleet_main.report(api, ROOT, IDS, 123, 1)

    assert len(api.mutations) == 1
    assert api.mutations[0][0] == "issues"
    assert f"[ci] red @{moved_head}" in api.mutations[0][1]["body"]
    assert api.head_reads == 5, "expected 1 pre-loop read + 2 _attempt() calls (2 reads each): a genuine retry"


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


def test_no_cross_run_coupling_between_concurrent_pr_and_main_invocations() -> None:
    """FR-009: two different-subject reporter invocations (a PR report and a main-push
    report) running concurrently must not read or mutate one another's state -- each
    retry/backoff invocation's evidence is constructed fresh from its own call's local
    arguments only, with no shared object, global, or filesystem path. Not exempt from
    red-first per plan.md's "Red-First Application" section: there is no pre-fix retry
    state to leak (the property trivially holds before this mission), so it is committed
    alongside WP2's other red-first-anchored tests rather than left for WP4."""
    pr_api = API()
    main_api = MainAPI()
    main_api.runs["ci-quality.yml"][0]["conclusion"] = "failure"
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def run_pr() -> None:
        try:
            barrier.wait(timeout=5)
            fleet_verdict.report(pr_api, ROOT, 7, IDS, 123, 1)
        except BaseException as error:  # noqa: BLE001 - surfaced via `errors` for the assertion below
            errors.append(error)

    def run_main() -> None:
        try:
            barrier.wait(timeout=5)
            fleet_main.report(main_api, ROOT, IDS, 456, 1)
        except BaseException as error:  # noqa: BLE001 - surfaced via `errors` for the assertion below
            errors.append(error)

    pr_thread = threading.Thread(target=run_pr)
    main_thread = threading.Thread(target=run_main)
    pr_thread.start()
    main_thread.start()
    pr_thread.join(timeout=10)
    main_thread.join(timeout=10)

    assert not errors, errors
    assert len(pr_api.posts) == 1
    assert pr_api.posts[0]["body"].startswith(f"[ci] green @{HEAD}")
    assert len(main_api.mutations) == 1
    assert main_api.mutations[0][0] == "issues"
    assert f"[ci] red @{HEAD}" in main_api.mutations[0][1]["body"]


def test_retry_budget_pair_is_imported_not_redefined() -> None:
    """PR-MERGED-004 guard: fleet_main.py must import the shared retry-budget
    pair (FLEET_MAX_ATTEMPTS, fleet_backoff_seconds) and AlreadyReported from
    fleet_verdict.py rather than redefining them verbatim -- a re-duplication
    would pass every other test in this file while silently reintroducing the
    drift risk plan.md's "fleet-verdict pair" rationale calls out."""
    assert fleet_main.FLEET_MAX_ATTEMPTS is fleet_verdict.FLEET_MAX_ATTEMPTS
    assert fleet_main.fleet_backoff_seconds is fleet_verdict.fleet_backoff_seconds
    assert fleet_main.AlreadyReported is fleet_verdict.AlreadyReported
