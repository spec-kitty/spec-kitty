"""Exercise metadata verdict decisions and publication via an in-memory API port."""

from __future__ import annotations

import copy
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci import fleet_verdict
from scripts.ci.fleet_verdict import (
    AGGREGATE,
    GitHub,
    MARKER,
    PR_WORKFLOWS,
    applicable_workflows,
    classify,
    comment_body,
    latest_run,
    report,
    snapshot,
)

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
REPO = "spec-kitty/spec-kitty"
HEAD = "a" * 40
IDS = {name: i for i, name in enumerate(sorted(PR_WORKFLOWS | {AGGREGATE}), start=1)}


def pull() -> dict[str, Any]:
    return {"number": 7, "state": "open", "head": {"sha": HEAD}, "base": {"ref": "main"}, "labels": [], "changed_files": 1}


def run(name: str, **updates: Any) -> dict[str, Any]:
    row = {
        "id": IDS[name] * 10,
        "created_at": "2026-09-08T10:00:00Z",
        "run_attempt": 1,
        "workflow_id": IDS[name],
        "path": f".github/workflows/{name}",
        "repository": {"full_name": REPO},
        "head_sha": HEAD,
        "event": "pull_request",
        "status": "completed",
        "conclusion": "success",
        "pull_requests": [{"number": 7, "head": {"sha": HEAD}, "base": {"repo": {"url": f"https://api.github.com/repos/{REPO}"}}}],
        "html_url": f"https://github.com/{REPO}/actions/runs/{IDS[name] * 10}",
    }
    row.update(updates)
    return row


class API:
    repository = REPO

    def __init__(self) -> None:
        self.pr = pull()
        self.files = [{"filename": "src/kernel/example.py"}]
        self.runs = {name: [run(name)] for name in PR_WORKFLOWS}
        modules = self.runs["ci-modules.yml"][0]
        self.runs[AGGREGATE] = [run(AGGREGATE, event="workflow_run", head_sha="b" * 40, display_title=f"CI Aggregate source {modules['id']} attempt 1")]
        self.comments: list[dict[str, Any]] = []
        self.posts: list[dict[str, Any]] = []
        self.pr_reads = 0
        self.move_on_second_read = False

    def request(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        if payload is not None:
            self.posts.append(payload)
            return {"body": payload["body"]}
        if path.startswith("actions/runs/"):
            identity = int(path.rsplit("/", 1)[1])
            return copy.deepcopy(next(row for rows in self.runs.values() for row in rows if row["id"] == identity))
        assert path == "pulls/7"
        self.pr_reads += 1
        result = copy.deepcopy(self.pr)
        if self.move_on_second_read and self.pr_reads > 1:
            result["head"]["sha"] = "c" * 40
        return result

    def pages(self, path: str, field: str | None = None) -> list[dict[str, Any]]:
        if path == "actions/workflows":
            return [{"id": identity, "path": f".github/workflows/{name}"} for name, identity in IDS.items()]
        if path == "pulls/7/files":
            return copy.deepcopy(self.files)
        if path == "issues/7/comments":
            return copy.deepcopy(self.comments)
        if path.startswith("actions/runs?"):
            return copy.deepcopy([row for name, rows in self.runs.items() if name != AGGREGATE for row in rows])
        workflow_id = int(path.split("/")[2])
        name = next(name for name, identity in IDS.items() if identity == workflow_id)
        return copy.deepcopy(self.runs[name])


def test_all_existing_pr_workflows_are_registered() -> None:
    expected = PR_WORKFLOWS
    assert applicable_workflows(ROOT, pull(), ["pyproject.toml"]) == expected
    assert applicable_workflows(ROOT, pull(), ["docs/example.md"]) == expected - {"release-readiness.yml", "check-spec-kitty-events-alignment.yml"}
    release = pull()
    release["base"]["ref"] = "release/3.2.6.x"
    assert applicable_workflows(ROOT, release, ["pyproject.toml"]) == {"ci-router.yml", "ci-modules.yml", "ci-quality.yml", "packs.yml"}


@pytest.mark.parametrize("extension", ["yml", "yaml"])
def test_new_pr_workflow_fails_closed(tmp_path: Path, extension: str) -> None:
    directory = tmp_path / ".github/workflows"
    directory.mkdir(parents=True)
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        (directory / path.name).write_bytes(path.read_bytes())
    (directory / f"new.{extension}").write_text("on: {pull_request: {}}\njobs: {}\n")
    with pytest.raises(ValueError, match="inventory changed"):
        applicable_workflows(tmp_path, pull(), ["docs/a.md"])


def test_reporter_trigger_covers_every_registered_workflow_and_reruns() -> None:
    workflows = ROOT / ".github/workflows"
    reporter = yaml.safe_load((workflows / "ci-fleet-verdict.yml").read_text())
    trigger = reporter[True]["workflow_run"]
    assert set(trigger["workflows"]) == {yaml.safe_load((workflows / name).read_text())["name"] for name in PR_WORKFLOWS | {AGGREGATE}}
    # #4371: a verdict is a function of terminal upstream state only.
    assert set(trigger["types"]) == {"completed"}
    # #4371: top-level concurrency coalesces the fan-out to one surviving verdict per
    # subject, and the key is subject-safe on both trigger paths: the direct producers
    # key on their own head_sha (their head IS the subject — a PR head, or the exact
    # main tip of a push run); CI Aggregate — a workflow_run child whose head_sha is the
    # current main tip, not the PR head it verified — keys on its own run id (its
    # display_title binds it to exactly one source CI Modules run, hence one PR head),
    # so a group never mixes subjects and a cancel/replace is always same-subject, where
    # the survivor re-reads live evidence and loses no verdict (NFR-002).
    # Exact equality — a substring pin passes for a broken expression that drops the
    # workflow_run path and collapses all tips into one cancel:true group.
    assert reporter["concurrency"] == {
        "group": (
            "ci-fleet-verdict-${{ github.event.workflow_run.path == '.github/workflows/ci-aggregate.yml' "
            "&& format('aggregate-{0}', github.event.workflow_run.id) "
            "|| github.event.workflow_run.head_sha }}"
        ),
        "cancel-in-progress": True,
    }
    # report(PR) job concurrency unchanged (report-main also unchanged — see test_fleet_main).
    assert "matrix.pr" in reporter["jobs"]["report"]["concurrency"]["group"]
    assert reporter["jobs"]["report"]["concurrency"]["cancel-in-progress"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("event", "push"),
        ("head_sha", "b" * 40),
        ("workflow_id", 999),
        ("path", ".github/workflows/fake.yml"),
        ("repository", {"full_name": "other/repo"}),
        ("pull_requests", []),
        ("pull_requests", [{"number": 7, "head": {"sha": "b" * 40}, "base": {"repo": {"url": f"https://api.github.com/repos/{REPO}"}}}]),
    ],
)
def test_spoofed_or_unassociated_run_cannot_supply_evidence(field: str, value: Any) -> None:
    name = "ci-modules.yml"
    matching = run(name)
    assert latest_run([matching], workflow_id=IDS[name], repository=REPO, head=HEAD, number=7, name=name) == matching
    candidate = run(name, **{field: value})
    assert latest_run([candidate], workflow_id=IDS[name], repository=REPO, head=HEAD, number=7, name=name) is None


@pytest.mark.parametrize(
    "status,conclusion,expected",
    [
        ("in_progress", None, "running"),
        ("queued", None, "running"),
        ("completed", "cancelled", "infra-error"),
        ("completed", "skipped", "running"),
        ("completed", "failure", "red"),
        ("completed", "success", "green"),
    ],
)
def test_latest_attempt_dominates_older_green(status: str, conclusion: str | None, expected: str) -> None:
    api = API()
    name = "ci-modules.yml"
    old = api.runs[name][0]
    api.runs[name].append(run(name, run_attempt=2, status=status, conclusion=conclusion))
    api.runs[AGGREGATE][0]["display_title"] = f"CI Aggregate source {old['id']} attempt 2"
    _, evidence = snapshot(api, ROOT, 7, IDS)
    assert evidence["state"] == expected


def test_aggregate_from_wrong_source_or_attempt_cannot_green() -> None:
    api = API()
    api.runs[AGGREGATE][0]["display_title"] = "CI Aggregate source 99999 attempt 1"
    assert snapshot(api, ROOT, 7, IDS)[1]["state"] == "running"
    api.runs[AGGREGATE][0]["display_title"] = f"CI Aggregate source {api.runs['ci-modules.yml'][0]['id']} attempt 1"
    api.runs[AGGREGATE][0]["event"] = "workflow_dispatch"
    assert snapshot(api, ROOT, 7, IDS)[1]["state"] == "running"


def test_missing_path_applicable_gate_is_pending() -> None:
    api = API()
    api.files = [{"filename": "pyproject.toml"}]
    api.runs["release-readiness.yml"] = []
    assert snapshot(api, ROOT, 7, IDS)[1]["state"] == "running"


def test_truncated_files_and_deferred_pr_never_green() -> None:
    api = API()
    api.pr["changed_files"] = 3001
    with pytest.raises(ValueError, match="incomplete"):
        snapshot(api, ROOT, 7, IDS)
    assert classify({"gate": run("ci-modules.yml")}, {"pr:skip-ci"}) == "running"
    assert classify({}, set()) == "running"


def test_publication_rechecks_head_and_never_mutates_existing_comments(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-002/FR-007/C-003 re-pin (Standing Order #4: judge the test, not git-blame).

    Pre-fix, `move_on_second_read` moved the PR head SHA once (on the second `pulls/7`
    read) and it stayed moved -- report()'s single snapshot pair disagreed and it raised
    immediately. Traced against the new retry contract: attempt 1's own read (pr_reads=1,
    unmoved) and its recheck (pr_reads=2, moved) disagree -> _attempt() returns None
    (retry). Attempt 2's own read (pr_reads=3) and its recheck (pr_reads=4) both land on
    the now-permanently-moved head -> they agree -> _Ready. The moved head ("c"*40) no
    longer matches any mocked run's fixed `head_sha` ("a"*40), so the stabilized evidence
    classifies as "running" (no matching runs), not "green" -- verified empirically
    against the live mock, not assumed from a prediction. So the new contract is: no
    raise, and a successful post IS made -- but using the evidence for the NEW, stabilized
    head ("c"*40), never the stale original HEAD. This still proves invariant (a) (never
    publish from a stale/first snapshot), just via retry-then-publish instead of raise.
    """
    monkeypatch.setattr(fleet_verdict.time, "sleep", lambda seconds: None)
    api = API()
    api.move_on_second_read = True
    report(api, ROOT, 7, IDS, 123, 1)
    assert len(api.posts) == 1
    stabilized_head = "c" * 40
    assert api.posts[0]["body"].startswith(f"[ci] running @{stabilized_head}")
    assert HEAD not in api.posts[0]["body"]
    assert api.pr_reads == 4, "expected 2 _attempt() calls (2 pulls/7 reads each)"
    api = API()
    report(api, ROOT, 7, IDS, 123, 1)
    assert len(api.posts) == 1
    assert api.posts[0]["body"].startswith(f"[ci] green @{HEAD}")
    assert "Verdict-Account-Class: bot" in api.posts[0]["body"]


def test_recovery_within_budget_publishes_stabilized_evidence_not_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-002/FR-007/C-003 recovery: the first snapshot PAIR disagrees (retry-worthy),
    the second pair agrees. report() must retry the WHOLE pair -- never fall through on
    the first stale read -- and publish using the stabilized (agreeing) evidence, never
    the original disagreeing one. RED against unmodified report(): the current code
    raises ValueError on the very first disagreement instead of retrying."""
    api = API()
    monkeypatch.setattr(fleet_verdict.time, "sleep", lambda seconds: None)
    unstable_a = {"head": HEAD, "state": "red", "runs": {}, "labels": []}
    unstable_b = {"head": HEAD, "state": "running", "runs": {}, "labels": []}
    stable = {"head": HEAD, "state": "green", "runs": {}, "labels": []}
    sequence = iter(
        [
            (pull(), unstable_a),
            (pull(), unstable_b),
            (pull(), stable),
            (pull(), stable),
        ]
    )
    calls: list[int] = []

    def fake_snapshot(api_: API, root_: Path, number_: int, workflow_ids_: dict, replay_: Any = None) -> Any:
        calls.append(1)
        return next(sequence)

    monkeypatch.setattr(fleet_verdict, "snapshot", fake_snapshot)

    report(api, ROOT, 7, IDS, 123, 1)

    assert len(calls) == 4, "expected exactly two _attempt() calls (2 snapshot reads each)"
    assert len(api.posts) == 1
    assert api.posts[0]["body"].startswith(f"[ci] green @{HEAD}")


def test_exhausted_retry_budget_defers_silently_with_diagnostic(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """FR-004 terminal path: evidence that never stabilizes across the full retry budget
    must not raise and must not post -- it defers silently (exit 0) with a diagnostic
    line naming the subject, "deferred"/"skipped", and the stabilization failure reason,
    trusting ci-fleet-verdict.yml's repeated workflow_run firings to reconcile later.
    RED against unmodified report(): the current code raises on the first disagreement."""
    api = API()
    monkeypatch.setattr(fleet_verdict.time, "sleep", lambda seconds: None)
    toggle = {"n": 0}

    def fake_snapshot(api_: API, root_: Path, number_: int, workflow_ids_: dict, replay_: Any = None) -> Any:
        toggle["n"] += 1
        state = "red" if toggle["n"] % 2 else "running"
        return pull(), {"head": HEAD, "state": state, "runs": {}, "labels": []}

    monkeypatch.setattr(fleet_verdict, "snapshot", fake_snapshot)

    report(api, ROOT, 7, IDS, 123, 1)

    assert api.posts == []
    assert toggle["n"] == 8, "expected exactly 4 attempts x 2 snapshot reads each (budget exhausted)"
    out = capsys.readouterr().out
    assert "7" in out
    assert "deferred" in out or "skipped" in out
    assert "evidence did not stabilize within retry budget" in out


def test_duplicate_latest_evidence_is_suppressed_but_newer_verdict_is_not() -> None:
    api = API()
    evidence = snapshot(api, ROOT, 7, IDS)[1]
    body = comment_body(REPO, evidence, 123, 1)
    api.comments = [{"body": body, "user": {"type": "Bot"}}]
    report(api, ROOT, 7, IDS, 123, 1)
    assert not api.posts
    api.comments.append({"body": f"[ci] red @{HEAD}", "user": {"type": "Bot"}})
    report(api, ROOT, 7, IDS, 123, 1)
    assert api.posts[0]["body"].startswith(f"[ci] green @{HEAD}")
    assert MARKER in api.posts[0]["body"]


def test_running_ledger_does_not_suppress_a_terminal_verdict() -> None:
    # NFR-002 / #4371 coalescing: the running-dedup must not swallow the last-writer
    # terminal verdict. A stale "[ci] running @HEAD" must NOT suppress a newer terminal
    # green/red for the same head — the running-guard only suppresses running-on-running.
    api = API()
    api.comments = [{"body": f"[ci] running @{HEAD}", "user": {"type": "Bot"}}]
    report(api, ROOT, 7, IDS, 123, 1)
    assert api.posts and api.posts[0]["body"].startswith(f"[ci] green @{HEAD}")


def completed(conclusion: str | None) -> dict[str, Any]:
    """A terminal required-gate run for pure classify() precedence tests."""
    return {"status": "completed", "conclusion": conclusion}


def test_terminal_cancel_reposts_and_is_not_suppressed() -> None:
    # FR-001/FR-003/FR-005 release proof: a fully-terminal required set with a
    # cancelled run (no red) is infra-error, and the running-dedup guard must NOT
    # swallow it. Seed a prior terminal running verdict that WOULD suppress a
    # running re-post (Bot + MARKER + "[ci] running @HEAD"); on today's code the
    # cancelled gate classifies as running and the guard suppresses (no post),
    # after the fix it classifies as infra-error — a distinct terminal state the
    # guard leaves alone — so a fresh "[ci] infra-error @HEAD" is published,
    # releasing the head. This exercises the full report() path, not bare classify.
    api = API()
    api.runs["ci-quality.yml"][0]["conclusion"] = "cancelled"
    api.comments = [{"body": f"[ci] running @{HEAD} on github-actions\n\n{MARKER}\nrunning evidence", "user": {"type": "Bot"}}]
    report(api, ROOT, 7, IDS, 123, 1)
    assert api.posts and api.posts[0]["body"].startswith(f"[ci] infra-error @{HEAD}")
    assert MARKER in api.posts[0]["body"]


def test_cancel_among_pending_runs_stays_running() -> None:
    # INV-2 never-premature: a cancelled run does not decide the verdict while any
    # required run is still non-terminal (in_progress) or entirely absent (None).
    assert classify({"g": completed("cancelled"), "h": {"status": "in_progress", "conclusion": None}}, set()) == "running"
    assert classify({"g": completed("cancelled"), "h": None}, set()) == "running"


def test_failure_and_cancel_is_red() -> None:
    # INV-3 red dominates: a real failure is never washed to infra-error by a co-cancelled run.
    assert classify({"g": completed("failure"), "h": completed("cancelled")}, set()) == "red"


def test_deferred_not_overridden_by_cancel() -> None:
    # INV-4 deferred respected: an intentional skip label takes precedence over a cancelled run.
    assert classify({"g": completed("cancelled")}, {"pr:skip-ci"}) == "running"


def test_all_success_green_never_infra() -> None:
    # INV-1 never-green→infra-error: an all-success terminal set has no cancelled run, so it stays green.
    assert classify({"g": completed("success"), "h": completed("success")}, set()) == "green"


def test_skipped_is_not_cancelled() -> None:
    # INV-5 skipped≠cancelled: infra-error requires a cancelled conclusion, not merely "not green".
    assert classify({"g": completed("skipped"), "h": completed("success")}, set()) == "running"


def replay_fixture(tmp_path: Path) -> tuple[API, Path, dict[str, Any]]:
    checkout = tmp_path / "reviewed"
    checkout.mkdir()
    subprocess.run(["git", "init", "-q", str(checkout)], check=True)
    workflows = checkout / ".github/workflows"
    workflows.mkdir(parents=True)
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        (workflows / path.name).write_bytes(path.read_bytes())
    subprocess.run(["git", "-C", str(checkout), "add", "."], check=True)
    subprocess.run(["git", "-C", str(checkout), "-c", "user.name=CI Test", "-c", "user.email=ci@example.invalid", "commit", "-qm", "reviewed reporter"], check=True)
    sha = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    api = API()
    aggregate = api.runs[AGGREGATE][0]
    aggregate.update(event="workflow_dispatch", head_sha=sha)
    replay = {"aggregate_run_id": aggregate["id"], "reporter_sha": sha, "host": "sk-dispatch", "session": "ci-replay-4032"}
    return api, checkout, replay


def test_explicit_reviewed_replay_posts_real_manual_aggregate_evidence(tmp_path: Path) -> None:
    api, checkout, replay = replay_fixture(tmp_path)
    # Automatic reconciliation must not trust branch-dispatched aggregates.
    assert snapshot(api, checkout, 7, IDS)[1]["state"] == "running"
    report(api, checkout, 7, IDS, 123, 1, replay=replay)
    body = api.posts[0]["body"]
    assert body.startswith(f"[ci] green @{HEAD} on sk-dispatch")
    assert "Verdict-Session: ci-replay-4032" in body
    assert "Verdict-Host: sk-dispatch" in body
    assert replay["reporter_sha"] in body


@pytest.mark.parametrize(
    "field,value",
    [
        ("event", "push"),
        ("head_sha", "f" * 40),
        ("workflow_id", 999),
        ("path", ".github/workflows/wrong.yml"),
        ("repository", {"full_name": "other/repo"}),
        ("display_title", "CI Aggregate source 999999 attempt 1"),
    ],
)
def test_replay_refuses_wrong_aggregate_identity(tmp_path: Path, field: str, value: Any) -> None:
    api, checkout, replay = replay_fixture(tmp_path)
    api.runs[AGGREGATE][0][field] = value
    with pytest.raises(ValueError, match="manual aggregate"):
        report(api, checkout, 7, IDS, 123, 1, replay=replay)
    assert not api.posts


@pytest.mark.parametrize("change", ["dirty", "tracked_dirty", "wrong_revision", "new_head", "new_source_attempt"])
def test_replay_refuses_unreviewed_or_superseded_evidence(tmp_path: Path, change: str) -> None:
    api, checkout, replay = replay_fixture(tmp_path)
    if change == "dirty":
        (checkout / "unreviewed.py").write_text("unreviewed = True\n")
    elif change == "tracked_dirty":
        (checkout / ".github/workflows/ci-quality.yml").write_text("unreviewed: true\n")
    elif change == "wrong_revision":
        replay["reporter_sha"] = "f" * 40
    elif change == "new_head":
        api.move_on_second_read = True
    else:
        api.runs["ci-modules.yml"][0]["run_attempt"] = 2
    with pytest.raises(ValueError):
        report(api, checkout, 7, IDS, 123, 1, replay=replay)
    assert not api.posts


@pytest.mark.parametrize("state,expected", [("failure", "red"), ("cancelled", "infra-error")])
def test_replay_preserves_other_required_gate_results(tmp_path: Path, state: str, expected: str) -> None:
    api, checkout, replay = replay_fixture(tmp_path)
    api.runs["ci-quality.yml"][0]["conclusion"] = state
    report(api, checkout, 7, IDS, 123, 1, replay=replay)
    assert api.posts[0]["body"].startswith(f"[ci] {expected} @{HEAD}")


@pytest.mark.parametrize("use_wrapper", [False, True])
def test_manual_replay_cli_dry_run_never_posts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], use_wrapper: bool) -> None:
    from scripts.ci import fleet_verdict

    api, checkout, replay = replay_fixture(tmp_path)
    wrapper_path = tmp_path / "gh-api-retry-exec.sh" if use_wrapper else None
    selected = []

    def transport(repository: str, *, wrapper: Path | None = None) -> API:
        assert repository == REPO
        selected.append(wrapper)
        return api

    monkeypatch.setattr(fleet_verdict, "GitHubCLI", transport)
    monkeypatch.setattr(fleet_verdict, "__file__", str(checkout / "scripts/ci/fleet_verdict.py"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fleet_verdict.py",
            "--pr",
            "7",
            "--repository",
            REPO,
            "--reporter-id",
            "123",
            "--attempt",
            "1",
            "--aggregate-run-id",
            str(replay["aggregate_run_id"]),
            "--reviewed-reporter-sha",
            replay["reporter_sha"],
            "--reporter-host",
            replay["host"],
            "--reporter-session",
            replay["session"],
            "--gh-cli",
            "--dry-run",
        ]
        + (["--gh-api-wrapper", str(wrapper_path)] if use_wrapper else []),
    )
    fleet_verdict.main()
    assert capsys.readouterr().out.startswith(f"[ci] green @{HEAD} on sk-dispatch")
    assert not api.posts
    assert selected == [wrapper_path]


def test_replay_rechecks_aggregate_attempt_before_publication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-002/FR-007/C-003 re-pin, replay path (Standing Order #4).

    Pre-fix, the aggregate run mutating between the two `actions/runs/` reads made the
    single snapshot pair disagree and report() raised immediately. Traced against the new
    retry contract: attempt 1's own read (reads=1, unmutated) and its recheck (reads=2,
    mutated) disagree -> _attempt() returns None (retry). Attempt 2's own read (reads=3)
    and its recheck (reads=4) both land on the now-permanently-mutated aggregate -> they
    agree -> _Ready. So the new contract is: no raise, and a successful post IS made --
    using the STABILIZED (mutated) aggregate evidence, never the stale original.
    """
    monkeypatch.setattr(fleet_verdict.time, "sleep", lambda seconds: None)
    api, checkout, replay = replay_fixture(tmp_path)
    original = api.request
    counter = {"reads": 0}

    def changing_request(path: str, payload: dict[str, Any] | None = None) -> Any:
        if path.startswith("actions/runs/"):
            counter["reads"] += 1
            if counter["reads"] > 1:
                api.runs[AGGREGATE][0].update(run_attempt=2, status="in_progress", conclusion=None)
        return original(path, payload)

    api.request = changing_request

    report(api, checkout, 7, IDS, 123, 1, replay=replay)

    assert len(api.posts) == 1
    assert '"run_attempt": 2' in api.posts[0]["body"]
    assert counter["reads"] == 4, "expected 2 _attempt() calls (2 actions/runs/ reads each)"


def test_gh_transport_uses_existing_proxy_and_stdin_for_comment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.ci.fleet_verdict import GitHubCLI

    executable = tmp_path / "gh"
    executable.write_text(
        f"#!{sys.executable}\nimport json, os, sys\nprint(json.dumps({{'argv':sys.argv[1:], 'host':os.environ['GH_HOST'], 'payload':json.load(sys.stdin)}}))\n"
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("GH_HOST", "github.int.exe.xyz")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    payload = {"body": "[ci] green @" + HEAD + "\n\nExact evidence; literal `$()` preserved."}
    result = GitHubCLI(REPO).request("issues/7/comments", payload)
    assert result["payload"] == payload
    assert result["host"] == "github.int.exe.xyz"
    assert result["argv"] == ["api", f"repos/{REPO}/issues/7/comments", "--method", "POST", "--input", "-"]
    executable.write_text(f"#!{sys.executable}\nimport sys\nsys.stderr.write('credential diagnostics must not escape')\nsys.exit(1)\n")
    with pytest.raises(ValueError, match=r"^gh API request failed \(exit 1\)$"):
        GitHubCLI(REPO).request("issues/7/comments", payload)


@pytest.mark.parametrize("payload", [None, {"body": "Exact evidence\nLiteral `$()` and quotes ' remain data."}])
def test_explicit_api_wrapper_preserves_arguments_input_and_host_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any] | None
) -> None:
    from scripts.ci.fleet_verdict import GitHubCLI

    wrapper = tmp_path / "host wrapper $(literal).sh"
    probe = (
        "import json,os,sys; from pathlib import Path; p=Path(sys.argv[-1]) if '--input' in sys.argv else None; "
        "print(json.dumps({'argv':sys.argv[1:], 'attempts':[json.loads(p.read_text()), json.loads(p.read_text())] if p else [], "
        "'mode':p.stat().st_mode & 0o777 if p else None, 'host':os.environ['GH_HOST'], 'role':os.environ['SK_GH_API_ROLE']}))"
    )
    wrapper.write_text(f'exec {shlex.quote(sys.executable)} -c {shlex.quote(probe)} "$@"\n')
    monkeypatch.setenv("GH_HOST", "github.int.exe.xyz")
    monkeypatch.setenv("SK_GH_API_ROLE", "ci")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    endpoint = "issues/7/comments" if payload else "actions/runs?head_sha=" + HEAD
    result = GitHubCLI(REPO, wrapper=wrapper).request(endpoint, payload)
    assert result["argv"][:2] == ["api", f"repos/{REPO}/{endpoint}"]
    assert result["host"] == "github.int.exe.xyz"
    assert result["role"] == "ci"
    if payload:
        assert result["argv"][2:5] == ["--method", "POST", "--input"]
        assert len(result["argv"]) == 6
        assert result["attempts"] == [payload, payload]
        assert result["mode"] == 0o600
        assert not Path(result["argv"][-1]).exists()
    else:
        assert len(result["argv"]) == 2
        assert result["attempts"] == []


@pytest.mark.parametrize("kind", ["relative", "missing", "directory"])
def test_api_wrapper_invalid_configuration_fails_before_request(tmp_path: Path, kind: str) -> None:
    from scripts.ci.fleet_verdict import GitHubCLI

    wrapper = {"relative": Path("wrapper.sh"), "missing": tmp_path / "missing.sh", "directory": tmp_path}[kind]
    with pytest.raises(ValueError, match="absolute readable file"):
        GitHubCLI(REPO, wrapper=wrapper)


@pytest.mark.parametrize("invalid_json", [False, True])
def test_api_wrapper_failure_does_not_disclose_captured_diagnostics(tmp_path: Path, invalid_json: bool) -> None:
    from scripts.ci.fleet_verdict import GitHubCLI

    wrapper = tmp_path / "wrapper.sh"
    trace = tmp_path / "payload-path"
    wrapper.write_text(
        f"printf '%s' \"${{@: -1}}\" > {shlex.quote(str(trace))}\n"
        f"echo credential-bearing-output\necho credential-bearing-diagnostics >&2\nexit {0 if invalid_json else 3}\n"
    )
    message = "^gh API response was not valid JSON$" if invalid_json else r"^gh API request failed \(exit 3\)$"
    with pytest.raises(ValueError, match=message):
        GitHubCLI(REPO, wrapper=wrapper).request("issues/7/comments", {"body": "test"})
    assert not Path(trace.read_text()).exists()


@pytest.mark.parametrize("failure", [OSError("credential-bearing path"), subprocess.TimeoutExpired("credential-bearing command", 60, stderr="secret")])
def test_api_wrapper_launch_failure_is_sanitized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception) -> None:
    from scripts.ci import fleet_verdict

    wrapper = tmp_path / "wrapper.sh"
    wrapper.write_text("exit 0\n")
    paths = []

    def fail(*args: Any, **kwargs: Any) -> None:
        payload_path = Path(args[0][-1])
        assert payload_path.is_file()
        assert payload_path.stat().st_mode & 0o777 == 0o600
        paths.append(payload_path)
        raise failure

    monkeypatch.setattr(fleet_verdict.subprocess, "run", fail)
    with pytest.raises(ValueError, match="^gh API request could not complete$"):
        fleet_verdict.GitHubCLI(REPO, wrapper=wrapper).request("issues/7/comments", {"body": "test"})
    assert paths and not paths[0].exists()


def test_wrapper_cli_requires_gh_transport_before_any_api_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from scripts.ci import fleet_verdict

    monkeypatch.setattr(
        sys, "argv", ["fleet_verdict.py", "--repository", REPO, "--reporter-id", "1", "--attempt", "1", "--gh-api-wrapper", str(tmp_path / "wrapper.sh")]
    )
    with pytest.raises(SystemExit) as error:
        fleet_verdict.main()
    assert error.value.code == 2
    assert "--gh-api-wrapper requires --gh-cli" in capsys.readouterr().err


@pytest.mark.parametrize("field", [None, "workflow_runs"])
@pytest.mark.parametrize("short_final_page", [False, True])
def test_real_api_pagination_refuses_incomplete_evidence(monkeypatch: pytest.MonkeyPatch, field: str | None, short_final_page: bool) -> None:
    api = GitHub(REPO)
    path = "actions/runs?event=pull_request" if field else "pulls/7/files"
    separator = "&" if field else "?"
    calls: list[str] = []
    expected: list[dict[str, int]] = []

    def request(request_path: str) -> Any:
        calls.append(request_path)
        page = len(calls)
        assert request_path == f"{path}{separator}per_page=100&page={page}"
        count = 3 if short_final_page and page == 100 else 100
        batch = [{"id": (page - 1) * 100 + offset} for offset in range(count)]
        expected.extend(batch)
        return {field: batch} if field else batch

    monkeypatch.setattr(api, "request", request)
    if short_final_page:
        assert api.pages(path, field) == expected
        assert len(expected) == 9903
    else:
        with pytest.raises(ValueError, match="bounded pagination"):
            api.pages(path, field)
    assert len(calls) == 100
