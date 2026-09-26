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

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "ci" / "release_nightly_gate.py"

_FAKE_TOKEN = "ghs_faketoken_should_never_be_printed"  # noqa: S105 - test sentinel, not a real credential
_TAG = "v3.2.0rc42"
_SHA = "0123456789abcdef0123456789abcdef01234567"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_nightly_gate", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass's KW_ONLY probe can resolve the module
    # (it does sys.modules.get(cls.__module__)); a script run as __main__ is
    # already registered, so this only matters for the file-path import here.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()


def _run(run_id: int, status: str, conclusion: str | None = None) -> dict[str, Any]:
    return {"id": run_id, "status": status, "conclusion": conclusion}


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

    def __init__(self, run_batches: list[list[dict[str, Any]]], *, sha: str = _SHA) -> None:
        self._run_batches = run_batches
        self._sha = sha
        self._list_index = 0
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.dispatched: list[dict[str, Any]] = []

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
