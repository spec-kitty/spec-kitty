"""Unit tests for ``scripts/ci/release_nightly_gate.py`` (WP04, FR-008).

The release gate makes a green nightly for the EXACT release SHA a publish
precondition (research.md D7). These tests drive the orchestration with a fake
GitHub Actions client + a fake clock (never the network / real time) and cover:

- **green-exists**: a ``success`` nightly for the SHA already exists -> pass, no
  dispatch;
- **dispatch(by tag)->green**: no run + ``--dispatch`` dispatches ``ci-nightly.yml``
  BY THE TAG REF (never a bare SHA) and passes once the new run concludes green;
- **dispatch->red**: the dispatched run concludes non-success -> fail;
- **in-flight->wait->decide**: an in-flight run for the SHA is waited out, then
  its terminal conclusion decides (green->pass, red->fail), without racing it;
- **token-absent fail-closed (C-005)**: ``main`` with no token exits NON-ZERO
  (the OPPOSITE of the escalation degrade) and never echoes the token.

The module is loaded by file path (``scripts/ci`` is not an importable package),
mirroring ``tests/ci/test_nightly_escalation.py``.
"""

from __future__ import annotations

import functools
import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path
from collections.abc import Sequence
from types import ModuleType
from typing import Any

import pytest
from kernel.clock import UTC, datetime, timedelta

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "ci" / "release_nightly_gate.py"
_SCRIPT_MODULE_NAME = "release_nightly_gate"

_FAKE_TOKEN = "ghs_faketoken_should_never_be_printed"  # noqa: S105 - test sentinel, not a real credential
_TAG = "v3.2.0rc42"
_SHA = "0123456789abcdef0123456789abcdef01234567"
_ANCESTOR_SHA = "1111111111111111111111111111111111111111"
_UNRELATED_SHA = "2222222222222222222222222222222222222222"
_NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
_PERF_JOB_NAME = "Performance suite (weekly, #3595, #7704)"

#: Populated by the autouse ``_release_nightly_gate_module`` fixture below.
mod: ModuleType


@pytest.fixture(scope="module", autouse=True)
def _release_nightly_gate_module() -> Iterator[ModuleType]:
    """Load the script once for this module's tests.

    ``@dataclass``'s ``KW_ONLY`` probe resolves the module via
    ``sys.modules.get(cls.__module__)``, so it must already be registered
    before ``exec_module`` runs. A module-scoped ``pytest.MonkeyPatch.context()``
    — not the function-scoped ``monkeypatch`` fixture, which a module-scoped
    fixture cannot depend on — keeps that registration and undoes it once
    every test in this module has run.
    """
    global mod
    with pytest.MonkeyPatch.context() as mp:
        spec = importlib.util.spec_from_file_location(_SCRIPT_MODULE_NAME, _SCRIPT_PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        mp.setitem(sys.modules, _SCRIPT_MODULE_NAME, module)
        spec.loader.exec_module(module)
        mod = module
        yield module


def _run(run_id: int, status: str, conclusion: str | None = None) -> dict[str, Any]:
    return {"id": run_id, "status": status, "conclusion": conclusion}


def _perf_run(run_id: int, *, sha: str = _SHA, age: timedelta = timedelta(days=1), branch: str = "main") -> dict[str, Any]:
    """A green ci-nightly run as the runs-listing API reports it (#7704)."""
    created = (_NOW - age).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"id": run_id, "status": "completed", "conclusion": "success", "head_sha": sha, "head_branch": branch, "created_at": created}


def _jobs(perf_conclusion: str) -> list[dict[str, Any]]:
    return [{"name": "Heavy e2e suite (nightly-only, #3595)", "conclusion": "success"}, {"name": _PERF_JOB_NAME, "conclusion": perf_conclusion}]


#: The default recent performance verdict: run 900, one day old, on the release SHA, perf executed.
_DEFAULT_PERF_RUNS = (_perf_run(900),)
_DEFAULT_JOBS = {900: _jobs("success")}


class FakeClock:
    """A deterministic monotonic clock whose ``sleep`` advances virtual time."""

    def __init__(self) -> None:
        self._now = 0.0

    def monotonic(self) -> float:
        return self._now

    def sleep(self, seconds: float) -> None:
        self._now += seconds


class FakeClient:
    """Mock Actions client. ``run_batches`` feeds one poll snapshot per call.

    The first snapshot answers the top-level ``list_nightly_runs`` and the
    initial poll iteration; each subsequent poll consumes the next snapshot,
    modelling runs that appear / progress over time. The last snapshot repeats.
    """

    def __init__(
        self,
        run_batches: list[list[dict[str, Any]]],
        *,
        sha: str = _SHA,
        perf_runs: Sequence[dict[str, Any]] = _DEFAULT_PERF_RUNS,
        jobs: dict[int, list[dict[str, Any]]] | None = None,
        ancestors: frozenset[str] = frozenset({_ANCESTOR_SHA}),
        perf_runs_after_dispatch: Sequence[dict[str, Any]] | None = None,
        recent_by_poll: Sequence[Sequence[dict[str, Any]]] | None = None,
    ) -> None:
        self._run_batches = run_batches
        self._sha = sha
        self._list_index = 0
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.dispatched: list[dict[str, Any]] = []
        self._perf_runs = list(perf_runs)
        self._jobs = dict(_DEFAULT_JOBS if jobs is None else jobs)
        self._ancestors = ancestors
        self._perf_runs_after_dispatch = perf_runs_after_dispatch
        # When set, the recent-runs listing follows the run_batches snapshot last read,
        # so a run only becomes a verdict once its own batch shows it completed.
        self._recent_by_poll = recent_by_poll

    def resolve_tag_sha(self, tag: str) -> str:
        self.calls.append(("resolve", (tag,)))
        return self._sha

    def list_nightly_runs(self, head_sha: str) -> list[dict[str, Any]]:
        self.calls.append(("list", (head_sha,)))
        batch = self._run_batches[min(self._list_index, len(self._run_batches) - 1)]
        self._list_index += 1
        return batch

    def dispatch_nightly(self, *, ref: str, mode: str) -> None:
        self.calls.append(("dispatch", (ref, mode)))
        self.dispatched.append({"ref": ref, "mode": mode})
        if self._perf_runs_after_dispatch is not None:
            self._perf_runs = list(self._perf_runs_after_dispatch)

    def list_recent_nightly_runs(self, since: datetime) -> list[dict[str, Any]]:
        self.calls.append(("recent", (since,)))
        if self._recent_by_poll is not None:
            return list(self._recent_by_poll[min(max(self._list_index - 1, 0), len(self._recent_by_poll) - 1)])
        return list(self._perf_runs)

    def list_run_jobs(self, run_id: int) -> list[dict[str, Any]]:
        self.calls.append(("jobs", (run_id,)))
        return self._jobs.get(run_id, [])

    def is_ancestor(self, ancestor_sha: str, descendant_sha: str) -> bool:
        self.calls.append(("ancestor", (ancestor_sha, descendant_sha)))
        return descendant_sha == self._sha and ancestor_sha in self._ancestors


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the gate's wall clock so the 7-day window is deterministic."""
    original = mod.run_release_gate

    @functools.wraps(original)
    def _gate(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("now", lambda: _NOW)
        return original(*args, **kwargs)

    monkeypatch.setattr(mod, "run_release_gate", _gate)


def _call_names(client: FakeClient) -> list[str]:
    return [name for name, _ in client.calls]


# ---------------------------------------------------------------------------
# green-exists
# ---------------------------------------------------------------------------
def test_existing_green_nightly_passes_without_dispatch() -> None:
    client = FakeClient([[_run(1, "completed", "success")]])
    result = mod.run_release_gate(client, tag=_TAG, dispatch=True, timeout=100, poll_interval=10)

    assert result.passed is True
    assert result.release_sha == _SHA
    assert "dispatch" not in _call_names(client)


def test_resolves_the_tag_before_querying_runs() -> None:
    client = FakeClient([[_run(1, "completed", "success")]])
    mod.run_release_gate(client, tag=_TAG, dispatch=False, timeout=100, poll_interval=10)

    assert client.calls[0] == ("resolve", (_TAG,))
    assert client.calls[1][0] == "list"


# ---------------------------------------------------------------------------
# no run + no dispatch: fail closed
# ---------------------------------------------------------------------------
def test_no_nightly_and_no_dispatch_fails_closed() -> None:
    client = FakeClient([[]])
    result = mod.run_release_gate(client, tag=_TAG, dispatch=False, timeout=100, poll_interval=10)

    assert result.passed is False
    assert "dispatch" not in _call_names(client)


def test_completed_red_run_without_dispatch_does_not_pass() -> None:
    # A single already-red completed run and no --dispatch: there is no in-flight
    # run to wait on and no green, so the gate refuses to publish.
    client = FakeClient([[_run(9, "completed", "failure")]])
    result = mod.run_release_gate(client, tag=_TAG, dispatch=False, timeout=100, poll_interval=10)

    assert result.passed is False
    assert "dispatch" not in _call_names(client)


# ---------------------------------------------------------------------------
# dispatch(by tag) -> green
# ---------------------------------------------------------------------------
def test_dispatch_uses_the_tag_ref_not_a_bare_sha_then_passes_on_green() -> None:
    clock = FakeClock()
    client = FakeClient(
        [
            [],  # top-level list: nothing for this SHA
            [_run(100, "in_progress")],  # dispatched run has appeared, running
            [_run(100, "completed", "success")],  # ...and concluded green
        ]
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=True, timeout=1000, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    assert result.passed is True
    assert client.dispatched == [{"ref": _TAG, "mode": "full"}]
    # The dispatch ref MUST be the tag, never the 40-hex SHA (GitHub constraint).
    (ref, mode) = next(args for name, args in client.calls if name == "dispatch")
    assert ref == _TAG
    assert ref != _SHA
    assert mode == "full"


# ---------------------------------------------------------------------------
# dispatch -> red
# ---------------------------------------------------------------------------
def test_dispatch_then_red_fails() -> None:
    clock = FakeClock()
    client = FakeClient(
        [
            [],
            [_run(100, "in_progress")],
            [_run(100, "completed", "failure")],
        ]
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=True, timeout=1000, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    assert result.passed is False
    assert client.dispatched == [{"ref": _TAG, "mode": "full"}]


def test_dispatch_ignores_a_preexisting_red_run_and_waits_for_the_new_one() -> None:
    # A prior red run exists; --dispatch must not let it short-circuit to fail --
    # the gate waits for the freshly dispatched run and passes when it goes green.
    clock = FakeClock()
    client = FakeClient(
        [
            [_run(1, "completed", "failure")],  # pre-existing red -> baseline
            [_run(1, "completed", "failure"), _run(2, "in_progress")],  # new run appears
            [_run(1, "completed", "failure"), _run(2, "completed", "success")],
        ]
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=True, timeout=1000, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    assert result.passed is True
    assert client.dispatched == [{"ref": _TAG, "mode": "full"}]


def test_dispatch_baseline_excludes_preexisting_red_before_new_run_appears() -> None:
    # Mutation cover for the baseline-run-id exclusion (F1). After dispatch, the
    # protected window is a poll snapshot that shows ONLY the terminal pre-existing
    # red run -- the freshly dispatched run has not yet materialised. The
    # baseline-id guard (baseline={1}) means run 1 is NOT a candidate, so no
    # negative verdict can be drawn: the gate MUST keep waiting until the new run
    # appears and goes green. Without the guard (baseline_ids=None) run 1 would be
    # a terminal candidate with nothing in flight beside it -> a false FAIL, so
    # this snapshot ordering is exactly what distinguishes the two implementations.
    clock = FakeClock()
    client = FakeClient(
        [
            [_run(1, "completed", "failure")],  # pre-dispatch list -> baseline = {1}
            [_run(1, "completed", "failure")],  # after dispatch: ONLY the old red -> must keep waiting, NOT fail
            [_run(1, "completed", "failure"), _run(2, "in_progress")],  # new run appears, in-flight
            [_run(1, "completed", "failure"), _run(2, "completed", "success")],  # new run green -> gate passes
        ]
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=True, timeout=1000, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    assert result.passed is True
    assert client.dispatched == [{"ref": _TAG, "mode": "full"}]


# ---------------------------------------------------------------------------
# in-flight -> wait -> decide (no race, regardless of --dispatch)
# ---------------------------------------------------------------------------
def test_in_flight_run_is_waited_out_then_passes_on_green() -> None:
    clock = FakeClock()
    client = FakeClient(
        [
            [_run(5, "in_progress")],
            [_run(5, "in_progress")],
            [_run(5, "completed", "success")],
        ]
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=True, timeout=1000, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    assert result.passed is True
    # In-flight means WAIT, not race: no dispatch even though --dispatch was set.
    assert "dispatch" not in _call_names(client)


def test_in_flight_run_is_waited_out_then_fails_on_red() -> None:
    clock = FakeClock()
    client = FakeClient(
        [
            [_run(5, "queued")],
            [_run(5, "completed", "failure")],
        ]
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=False, timeout=1000, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    assert result.passed is False
    assert "dispatch" not in _call_names(client)


# ---------------------------------------------------------------------------
# timeout: fail closed
# ---------------------------------------------------------------------------
def test_never_appearing_dispatched_run_times_out_fail_closed() -> None:
    clock = FakeClock()
    client = FakeClient([[]])  # nothing ever shows up for this SHA
    result = mod.run_release_gate(client, tag=_TAG, dispatch=True, timeout=25, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    assert result.passed is False
    assert "timed out" in result.summary


# ---------------------------------------------------------------------------
# main(): exit codes + token handling (fail-closed, no leak)
# ---------------------------------------------------------------------------
def test_main_without_token_fails_closed_nonzero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    rc = mod.main(["--tag", _TAG, "--repo", "spec-kitty/spec-kitty"])

    assert rc == mod.EXIT_FAILURE
    assert rc != 0
    captured = capsys.readouterr()
    assert "fail-closed" in captured.err
    assert _FAKE_TOKEN not in captured.out + captured.err


def test_main_without_repo_fails_closed_nonzero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GH_TOKEN", _FAKE_TOKEN)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    rc = mod.main(["--tag", _TAG])

    assert rc == mod.EXIT_FAILURE
    captured = capsys.readouterr()
    assert "repository" in captured.err
    # Even with a token present, the fail-closed path must never echo it.
    assert _FAKE_TOKEN not in captured.out + captured.err


def test_main_fails_closed_and_never_echoes_token_on_api_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GH_TOKEN", _FAKE_TOKEN)

    def _boom(self: Any, tag: str) -> str:
        raise mod.ReleaseGateError("simulated outage")

    monkeypatch.setattr(mod.GitHubActionsClient, "resolve_tag_sha", _boom)
    rc = mod.main(["--tag", _TAG, "--repo", "spec-kitty/spec-kitty"])

    assert rc == mod.EXIT_FAILURE
    captured = capsys.readouterr()
    assert "fail-closed" in captured.err
    assert _FAKE_TOKEN not in captured.out + captured.err


def test_main_passes_returns_zero_on_existing_green(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GH_TOKEN", _FAKE_TOKEN)

    monkeypatch.setattr(mod.GitHubActionsClient, "resolve_tag_sha", lambda self, tag: _SHA)
    monkeypatch.setattr(mod.GitHubActionsClient, "list_nightly_runs", lambda self, sha: [_run(1, "completed", "success")])
    monkeypatch.setattr(mod.GitHubActionsClient, "list_recent_nightly_runs", lambda self, since: [_perf_run(900)])
    monkeypatch.setattr(mod.GitHubActionsClient, "list_run_jobs", lambda self, run_id: _jobs("success"))
    rc = mod.main(["--tag", _TAG, "--repo", "spec-kitty/spec-kitty"])

    assert rc == mod.EXIT_OK
    captured = capsys.readouterr()
    assert _SHA in captured.out
    assert _FAKE_TOKEN not in captured.out + captured.err


def test_main_red_nightly_returns_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", _FAKE_TOKEN)
    monkeypatch.setattr(mod.GitHubActionsClient, "resolve_tag_sha", lambda self, tag: _SHA)
    monkeypatch.setattr(mod.GitHubActionsClient, "list_nightly_runs", lambda self, sha: [_run(1, "completed", "failure")])
    rc = mod.main(["--tag", _TAG, "--repo", "spec-kitty/spec-kitty"])

    assert rc == mod.EXIT_FAILURE


# ---------------------------------------------------------------------------
# real client: input validation + token redaction + tag/run wiring
# ---------------------------------------------------------------------------
def test_client_rejects_a_malformed_repository() -> None:
    with pytest.raises(mod.ReleaseGateError):
        mod.GitHubActionsClient("not-a-repo", _FAKE_TOKEN)


def test_client_rejects_an_empty_token() -> None:
    with pytest.raises(mod.ReleaseGateError):
        mod.GitHubActionsClient("spec-kitty/spec-kitty", "")


def test_resolve_tag_sha_reads_the_commit_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    client = mod.GitHubActionsClient("spec-kitty/spec-kitty", _FAKE_TOKEN)

    def _fake_request(self: Any, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        assert method == "GET"
        assert f"/commits/{_TAG}" in url
        return {"sha": _SHA}

    monkeypatch.setattr(mod.GitHubActionsClient, "_request", _fake_request)
    assert client.resolve_tag_sha(_TAG) == _SHA


def test_resolve_tag_sha_raises_when_no_sha_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    client = mod.GitHubActionsClient("spec-kitty/spec-kitty", _FAKE_TOKEN)
    monkeypatch.setattr(mod.GitHubActionsClient, "_request", lambda self, method, url, payload=None: {})
    with pytest.raises(mod.ReleaseGateError):
        client.resolve_tag_sha(_TAG)


def test_list_nightly_runs_filters_non_dict_entries_and_targets_ci_nightly(monkeypatch: pytest.MonkeyPatch) -> None:
    client = mod.GitHubActionsClient("spec-kitty/spec-kitty", _FAKE_TOKEN)

    def _fake_request(self: Any, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        assert "workflows/ci-nightly.yml/runs" in url
        assert f"head_sha={_SHA}" in url
        return {"workflow_runs": [{"id": 1, "status": "completed"}, "garbage", None]}

    monkeypatch.setattr(mod.GitHubActionsClient, "_request", _fake_request)
    runs = client.list_nightly_runs(_SHA)
    assert runs == [{"id": 1, "status": "completed"}]


def test_dispatch_nightly_posts_the_tag_ref_and_full_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    client = mod.GitHubActionsClient("spec-kitty/spec-kitty", _FAKE_TOKEN)
    seen: dict[str, Any] = {}

    def _fake_request(self: Any, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        seen["method"] = method
        seen["url"] = url
        seen["payload"] = payload
        return None

    monkeypatch.setattr(mod.GitHubActionsClient, "_request", _fake_request)
    client.dispatch_nightly(ref=_TAG, mode="full")

    assert seen["method"] == "POST"
    assert "workflows/ci-nightly.yml/dispatches" in seen["url"]
    assert seen["payload"] == {"ref": _TAG, "inputs": {"mode": "full"}}
    # The dispatched ref is the tag, not the bare SHA.
    assert seen["payload"]["ref"] != _SHA


def test_redact_removes_the_token_from_diagnostics() -> None:
    assert _FAKE_TOKEN not in mod._redact(f"boom {_FAKE_TOKEN} end", _FAKE_TOKEN)


def test_resolve_token_prefers_gh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", _FAKE_TOKEN)
    monkeypatch.setenv("GITHUB_TOKEN", "other")
    assert mod.resolve_token() == _FAKE_TOKEN


def test_resolve_token_returns_none_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert mod.resolve_token() is None


# ---------------------------------------------------------------------------
# performance verdict (#7704): the performance job runs weekly, so a green run on
# the release SHA no longer proves it ran. The gate needs a green run within 7
# days whose performance job EXECUTED, on the release SHA or a main ancestor.
# ---------------------------------------------------------------------------
def test_a_recent_performance_run_on_a_main_ancestor_passes() -> None:
    client = FakeClient(
        [[_run(1, "completed", "success")]],
        perf_runs=[_perf_run(800, sha=_ANCESTOR_SHA, age=timedelta(days=3))],
        jobs={800: _jobs("success")},
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=False, timeout=100, poll_interval=10)

    assert result.passed is True
    assert "run 800" in result.summary
    assert ("ancestor", (_ANCESTOR_SHA, _SHA)) in client.calls


def test_a_performance_job_that_was_only_skipped_refuses_and_names_the_dispatch_remedy() -> None:
    # The same-SHA run is green, but its performance job was skipped (a Mon-Sat run).
    client = FakeClient(
        [[_run(1, "completed", "success")]],
        perf_runs=[_perf_run(1)],
        jobs={1: _jobs("skipped")},
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=False, timeout=100, poll_interval=10)

    assert result.passed is False
    assert "performance job executed" in result.summary
    assert f"gh workflow run ci-nightly.yml --ref {_TAG}" in result.summary
    assert "--dispatch" in result.summary
    assert "dispatch" not in _call_names(client)


def test_a_performance_run_older_than_seven_days_refuses() -> None:
    client = FakeClient(
        [[_run(1, "completed", "success")]],
        perf_runs=[_perf_run(700, age=timedelta(days=7, minutes=1))],
        jobs={700: _jobs("success")},
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=False, timeout=100, poll_interval=10)

    assert result.passed is False
    assert "last 7 days" in result.summary


def test_a_performance_run_on_a_commit_that_is_not_an_ancestor_refuses() -> None:
    client = FakeClient(
        [[_run(1, "completed", "success")]],
        perf_runs=[_perf_run(600, sha=_UNRELATED_SHA)],
        jobs={600: _jobs("success")},
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=False, timeout=100, poll_interval=10)

    assert result.passed is False
    assert "jobs" not in _call_names(client)


def test_a_performance_run_off_main_does_not_count_even_on_an_ancestor() -> None:
    client = FakeClient(
        [[_run(1, "completed", "success")]],
        perf_runs=[_perf_run(500, sha=_ANCESTOR_SHA, branch="feature-x")],
        jobs={500: _jobs("success")},
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=False, timeout=100, poll_interval=10)

    assert result.passed is False
    assert "ancestor" not in _call_names(client)


def test_a_failed_performance_job_does_not_count() -> None:
    client = FakeClient([[_run(1, "completed", "success")]], perf_runs=[_perf_run(1)], jobs={1: _jobs("failure")})
    result = mod.run_release_gate(client, tag=_TAG, dispatch=False, timeout=100, poll_interval=10)

    assert result.passed is False


def test_dispatch_when_only_the_performance_verdict_is_missing_then_passes_on_the_new_run() -> None:
    # Same-SHA run 1 is green with perf skipped; --dispatch runs the nightly by tag,
    # and the dispatched run 2 executes the performance job. Run 2 only becomes a
    # verdict once its own snapshot shows it completed, so the gate must wait.
    clock = FakeClock()
    batches = [
        [_run(1, "completed", "success")],
        [_run(1, "completed", "success"), _run(2, "in_progress")],
        [_run(1, "completed", "success"), _run(2, "completed", "success")],
    ]
    client = FakeClient(
        batches,
        jobs={1: _jobs("skipped"), 2: _jobs("success")},
        recent_by_poll=[[_perf_run(1)], [_perf_run(1)], [_perf_run(1), _perf_run(2, age=timedelta(minutes=5))]],
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=True, timeout=1000, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    assert result.passed is True
    assert client.dispatched == [{"ref": _TAG, "mode": "full"}]
    assert "run 2" in result.summary
    assert _call_names(client).count("list") == len(batches), "the gate must read the snapshot where run 2 completed"


def test_dispatch_whose_run_still_lacks_a_performance_verdict_refuses_with_the_remedy() -> None:
    clock = FakeClock()
    client = FakeClient(
        [
            [_run(1, "completed", "success")],
            [_run(1, "completed", "success"), _run(2, "completed", "success")],
        ],
        perf_runs=[_perf_run(1)],
        jobs={1: _jobs("skipped"), 2: _jobs("skipped")},
        perf_runs_after_dispatch=[_perf_run(1), _perf_run(2, age=timedelta(minutes=5))],
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=True, timeout=1000, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    assert result.passed is False
    assert "remedy: dispatch ci-nightly" in result.summary


def test_performance_job_executed_requires_the_prefix_and_success() -> None:
    assert mod._performance_job_executed(_jobs("success")) is True
    assert mod._performance_job_executed(_jobs("skipped")) is False
    assert mod._performance_job_executed([{"name": "Stress suite", "conclusion": "success"}]) is False


def test_parse_timestamp_handles_zulu_naive_and_garbage() -> None:
    assert mod._parse_timestamp("2026-11-18T03:17:00Z") == datetime(2026, 11, 18, 3, 17, tzinfo=UTC)
    assert mod._parse_timestamp("2026-11-18T03:17:00") == datetime(2026, 11, 18, 3, 17, tzinfo=UTC)
    assert mod._parse_timestamp("not a time") is None
    assert mod._parse_timestamp(None) is None


def test_the_performance_job_name_prefix_matches_the_workflow() -> None:
    import yaml

    workflow = yaml.safe_load((_REPO_ROOT / ".github" / "workflows" / "ci-nightly.yml").read_text(encoding="utf-8"))
    assert str(workflow["jobs"]["performance"]["name"]).startswith(mod.PERFORMANCE_JOB_NAME_PREFIX)


def test_real_client_lists_recent_completed_runs_since_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    client = mod.GitHubActionsClient("spec-kitty/spec-kitty", _FAKE_TOKEN)
    urls: list[str] = []

    def _fake_request(self: Any, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        urls.append(url)
        return {"workflow_runs": [{"id": 1}, "garbage"]}

    monkeypatch.setattr(mod.GitHubActionsClient, "_request", _fake_request)
    runs = client.list_recent_nightly_runs(_NOW - timedelta(days=7))

    assert runs == [{"id": 1}]
    assert "workflows/ci-nightly.yml/runs" in urls[0]
    assert "created=%3E%3D2026-11-11T12%3A00%3A00Z" in urls[0]
    # Every completed run, red ones included: a newer red verdict must outvote an older green one.
    assert "status=completed" in urls[0]


def test_real_client_pages_through_jobs_and_refuses_a_truncated_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    client = mod.GitHubActionsClient("spec-kitty/spec-kitty", _FAKE_TOKEN)
    full_page = [{"name": f"job {i}"} for i in range(100)]

    def _two_pages(self: Any, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        assert "/actions/runs/42/jobs" in url
        return {"jobs": full_page if url.endswith("page=1") else [{"name": "last"}]}

    monkeypatch.setattr(mod.GitHubActionsClient, "_request", _two_pages)
    assert len(client.list_run_jobs(42)) == 101

    monkeypatch.setattr(mod.GitHubActionsClient, "_request", lambda self, method, url, payload=None: {"jobs": full_page})
    with pytest.raises(mod.ReleaseGateError, match="truncated"):
        client.list_run_jobs(42)


@pytest.mark.parametrize(("status", "expected"), [("ahead", True), ("identical", True), ("behind", False), ("diverged", False)])
def test_real_client_reads_ancestry_from_the_compare_status(monkeypatch: pytest.MonkeyPatch, status: str, expected: bool) -> None:
    client = mod.GitHubActionsClient("spec-kitty/spec-kitty", _FAKE_TOKEN)

    def _fake_request(self: Any, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        assert url.endswith(f"/compare/{_ANCESTOR_SHA}...{_SHA}")
        return {"status": status}

    monkeypatch.setattr(mod.GitHubActionsClient, "_request", _fake_request)
    assert client.is_ancestor(_ANCESTOR_SHA, _SHA) is expected


def test_real_client_ancestry_fails_closed_on_bad_input_or_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    client = mod.GitHubActionsClient("spec-kitty/spec-kitty", _FAKE_TOKEN)
    with pytest.raises(mod.ReleaseGateError):
        client.is_ancestor("main", _SHA)
    monkeypatch.setattr(mod.GitHubActionsClient, "_request", lambda self, method, url, payload=None: {})
    with pytest.raises(mod.ReleaseGateError):
        client.is_ancestor(_ANCESTOR_SHA, _SHA)


def test_a_newer_red_performance_run_outvotes_an_older_green_one() -> None:
    # Sunday green (run 10), a Wednesday dispatch on main went red (run 11): the
    # release on a descendant commit must not publish on Sunday's verdict.
    client = FakeClient(
        [[_run(1, "completed", "success")]],
        perf_runs=[_perf_run(10, sha=_ANCESTOR_SHA, age=timedelta(days=3)), _perf_run(11, sha=_ANCESTOR_SHA, age=timedelta(days=1)) | {"conclusion": "failure"}],
        jobs={10: _jobs("success"), 11: _jobs("failure")},
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=False, timeout=100, poll_interval=10)

    assert result.passed is False
    assert "run 11" in result.summary
    assert "is red" in result.summary
    assert "--dispatch" in result.summary


def test_a_cancelled_performance_job_counts_as_an_executed_red_verdict() -> None:
    client = FakeClient(
        [[_run(1, "completed", "success")]],
        perf_runs=[_perf_run(10, age=timedelta(days=3)), _perf_run(11, age=timedelta(days=1)) | {"conclusion": "cancelled"}],
        jobs={10: _jobs("success"), 11: _jobs("cancelled")},
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=False, timeout=100, poll_interval=10)

    assert result.passed is False
    assert "run 11" in result.summary


def test_a_red_performance_verdict_with_dispatch_is_cleared_by_a_green_dispatched_run() -> None:
    clock = FakeClock()
    red = _perf_run(11, sha=_ANCESTOR_SHA, age=timedelta(days=1)) | {"conclusion": "failure"}
    batches = [
        [_run(1, "completed", "success")],
        [_run(1, "completed", "success"), _run(2, "completed", "success")],
    ]
    client = FakeClient(
        batches,
        jobs={11: _jobs("failure"), 2: _jobs("success")},
        recent_by_poll=[[red], [red, _perf_run(2, age=timedelta(minutes=5))]],
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=True, timeout=1000, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    assert result.passed is True
    assert client.dispatched == [{"ref": _TAG, "mode": "full"}]


def test_an_in_flight_weekday_run_without_a_performance_verdict_still_dispatches() -> None:
    # The 03:17 Monday-Saturday nightly on the release commit is running when the
    # tag lands; it goes green with the performance job skipped. --dispatch must
    # still supply the verdict instead of refusing with "run with --dispatch".
    clock = FakeClock()
    batches = [
        [_run(1, "in_progress")],
        [_run(1, "completed", "success")],
        [_run(1, "completed", "success")],
        [_run(1, "completed", "success"), _run(2, "completed", "success")],
    ]
    client = FakeClient(
        batches,
        jobs={1: _jobs("skipped"), 2: _jobs("success")},
        recent_by_poll=[[], [_perf_run(1)], [_perf_run(1)], [_perf_run(1), _perf_run(2, age=timedelta(minutes=5))]],
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=True, timeout=1000, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    assert result.passed is True
    assert client.dispatched == [{"ref": _TAG, "mode": "full"}]


def test_an_in_flight_weekday_run_without_dispatch_refuses_with_the_remedy() -> None:
    clock = FakeClock()
    client = FakeClient(
        [[_run(1, "in_progress")], [_run(1, "completed", "success")]],
        jobs={1: _jobs("skipped")},
        recent_by_poll=[[], [_perf_run(1)]],
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=False, timeout=1000, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    assert result.passed is False
    assert "remedy: dispatch ci-nightly" in result.summary
    assert client.dispatched == []


def test_a_red_dispatched_run_is_reported_before_a_missing_performance_verdict() -> None:
    clock = FakeClock()
    client = FakeClient(
        [
            [_run(1, "completed", "success")],
            [_run(1, "completed", "success"), _run(2, "completed", "failure")],
        ],
        jobs={1: _jobs("skipped"), 2: _jobs("failure")},
        recent_by_poll=[[_perf_run(1)], [_perf_run(1), _perf_run(2, age=timedelta(minutes=5)) | {"conclusion": "failure"}]],
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=True, timeout=1000, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    assert result.passed is False
    assert "concluded non-success" in result.summary


def test_ancestry_and_completed_jobs_are_asked_once_per_gate_run() -> None:
    clock = FakeClock()
    client = FakeClient(
        [[_run(5, "in_progress")]] * 3 + [[_run(5, "completed", "success")]],
        perf_runs=[_perf_run(800, sha=_ANCESTOR_SHA, age=timedelta(days=2)) | {"conclusion": "failure"}],
        jobs={800: _jobs("failure")},
    )
    mod.run_release_gate(client, tag=_TAG, dispatch=False, timeout=1000, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    names = _call_names(client)
    assert names.count("ancestor") == 1
    assert names.count("jobs") == 1


def test_the_default_clock_is_the_kernel_clock_door() -> None:
    import inspect

    from kernel.clock import now_utc

    signature = inspect.signature(inspect.unwrap(mod.run_release_gate), follow_wrapped=False)
    assert signature.parameters["now"].default is now_utc


def test_the_gate_runs_under_a_bare_isolated_python3() -> None:
    """The release job runs the script with a bare ``python3``: the kernel.clock door must stay stdlib-only."""
    import subprocess

    completed = subprocess.run(
        [sys.executable, "-I", "-S", str(_SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--dispatch" in completed.stdout


def test_an_older_red_run_on_the_same_commit_does_not_stand_in_for_the_awaited_one() -> None:
    # Squad re-check (renata, finding 1): run 0 on the release commit is an older red;
    # run 1 is in flight, then green with the performance job skipped. The awaited
    # run went green, so --dispatch must still supply the performance verdict.
    clock = FakeClock()
    batches = [
        [_run(0, "completed", "failure"), _run(1, "in_progress")],
        [_run(0, "completed", "failure"), _run(1, "completed", "success")],
        [_run(0, "completed", "failure"), _run(1, "completed", "success")],
        [_run(0, "completed", "failure"), _run(1, "completed", "success"), _run(2, "completed", "success")],
    ]
    client = FakeClient(
        batches,
        jobs={1: _jobs("skipped"), 2: _jobs("success")},
        recent_by_poll=[[], [_perf_run(1)], [_perf_run(1)], [_perf_run(1), _perf_run(2, age=timedelta(minutes=5))]],
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=True, timeout=1000, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    assert result.passed is True
    assert client.dispatched == [{"ref": _TAG, "mode": "full"}]


def test_one_deadline_bounds_the_wait_and_the_dispatch_together() -> None:
    # Squad re-check (renata, finding 2): an in-flight wait followed by a dispatch
    # must not take twice --timeout.
    clock = FakeClock()
    client = FakeClient(
        [[_run(1, "in_progress")]] * 30 + [[_run(1, "completed", "success")]],
        jobs={1: _jobs("skipped")},
        recent_by_poll=[[]] * 30 + [[_perf_run(1)]],
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=True, timeout=1000, poll_interval=10, sleep=clock.sleep, monotonic=clock.monotonic)

    assert result.passed is False
    assert "timed out" in result.summary
    assert clock.monotonic() <= 1000 + 10


def test_a_cancelled_performance_verdict_names_a_redispatch_not_a_fix() -> None:
    client = FakeClient(
        [[_run(1, "completed", "success")]],
        perf_runs=[_perf_run(11) | {"conclusion": "cancelled"}],
        jobs={11: _jobs("cancelled")},
    )
    result = mod.run_release_gate(client, tag=_TAG, dispatch=False, timeout=100, poll_interval=10)

    assert result.passed is False
    assert "was cancelled" in result.summary
    assert "Fix the red" not in result.summary
