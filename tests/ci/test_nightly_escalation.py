"""Unit tests for ``scripts/ci/nightly_escalation.py`` (WP03, FR-007).

The nightly workflow escalates a red suite into a deduped ``priority:P0`` issue
and closes it again when the suite recovers (research.md D6). These tests drive
the escalation flow with a fake GitHub client (never the network) and cover:

- **create**: a failing suite with no open issue opens a ``priority:P0`` issue
  carrying the stable hidden dedup marker;
- **update-existing (dedup, NFR-005)**: a failing suite whose issue is already
  open comments on it instead of opening a duplicate;
- **close-on-green**: a recovered suite comments and closes the open issue;
- **token-absent degrade (C-005)**: with no token / no repo, ``main`` prints a
  warning and exits ``0`` (fail-loud only) without crashing or echoing the token.
- **mainline-only gate (#5169/#5172/#5265)**: a run on any ref other than
  ``refs/heads/main`` can never open, bump or close a P0 -- proven on BOTH
  halves: the script (``run_escalation`` / ``main``) and the workflow (every
  escalation step's ``if:`` carries the ref condition and passes ``--ref``).

The module is loaded by file path (``scripts/ci`` is not an importable package),
mirroring ``tests/ci/test_sonar_project_version.py``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "ci" / "nightly_escalation.py"

_FAKE_TOKEN = "ghs_faketoken_should_never_be_printed"  # noqa: S105 - test sentinel, not a real credential

_MAIN = "refs/heads/main"
_MAIN_ARGS = ("--ref", _MAIN)
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "ci-nightly.yml"
_WORKFLOW_REF_CONDITION = "github.ref == 'refs/heads/main'"
_SCRIPT_REF_ARG = '--ref "$GITHUB_REF"'


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("nightly_escalation", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load_module()


class FakeClient:
    """Records every escalation call; returns whatever issue is pre-seeded."""

    def __init__(self, existing: dict[str, Any] | None = None) -> None:
        self._existing = existing
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self._next_number = 4242

    def find_open_issue_by_marker(self, marker: str) -> dict[str, Any] | None:
        self.calls.append(("find", (marker,)))
        return self._existing

    def create_issue(self, *, title: str, body: str, labels: list[str]) -> dict[str, Any]:
        self.calls.append(("create", (title, body, tuple(labels))))
        return {"number": self._next_number}

    def comment_on_issue(self, number: int, body: str) -> dict[str, Any]:
        self.calls.append(("comment", (number, body)))
        return {"id": 1}

    def close_issue(self, number: int) -> dict[str, Any]:
        self.calls.append(("close", (number,)))
        return {"number": number, "state": "closed"}


def _call_names(client: FakeClient) -> list[str]:
    return [name for name, _ in client.calls]


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
def test_failure_with_no_open_issue_creates_a_p0_issue_with_marker() -> None:
    client = FakeClient(existing=None)
    summary = mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion="failure", run_url="https://run/1")

    assert _call_names(client) == ["find", "create"]
    (_, (title, body, labels)) = client.calls[1]
    assert labels == ("priority:P0",)
    assert mod.escalation_marker("integration") in body
    assert "https://run/1" in body
    assert "integration" in title
    assert "#4242" in summary


def test_created_issue_body_carries_the_exact_stable_dedup_marker() -> None:
    body = mod.issue_body("stress", "https://run/9")
    assert "<!-- nightly-escalation-key: stress -->" in body
    assert mod.escalation_marker("stress") == "<!-- nightly-escalation-key: stress -->"


# ---------------------------------------------------------------------------
# update-existing (dedup, NFR-005)
# ---------------------------------------------------------------------------
def test_failure_with_open_issue_comments_and_never_creates_a_duplicate() -> None:
    client = FakeClient(existing={"number": 77, "body": mod.escalation_marker("integration")})
    summary = mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion="failure", run_url="https://run/2")

    assert _call_names(client) == ["find", "comment"]
    assert "create" not in _call_names(client)
    (_, (number, comment_body)) = client.calls[1]
    assert number == 77
    assert "https://run/2" in comment_body
    assert "#77" in summary


# ---------------------------------------------------------------------------
# close-on-green
# ---------------------------------------------------------------------------
def test_success_with_open_issue_comments_then_closes_it() -> None:
    client = FakeClient(existing={"number": 88, "body": mod.escalation_marker("e2e")})
    summary = mod.run_escalation(client, ref=_MAIN, suite_key="e2e", conclusion="success", run_url="https://run/3")

    assert _call_names(client) == ["find", "comment", "close"]
    assert client.calls[-1] == ("close", (88,))
    assert "closed" in summary


def test_success_with_no_open_issue_is_a_noop() -> None:
    client = FakeClient(existing=None)
    summary = mod.run_escalation(client, ref=_MAIN, suite_key="performance", conclusion="success")

    assert _call_names(client) == ["find"]
    assert "nothing to do" in summary


# ---------------------------------------------------------------------------
# defense-in-depth: an unknown conclusion must never silently close a P0
# (FIND-3, #5034)
# ---------------------------------------------------------------------------
def test_run_escalation_raises_on_unknown_conclusion_instead_of_closing() -> None:
    """A conclusion that is neither "success" nor "failure" must RAISE, not
    fall through to the close-on-green path. The CLI's argparse `choices`
    already blocks this at the command line, but `run_escalation` is called
    directly by tests (and any future caller with a looser contract), so the
    function must be self-defending -- a stray "cancelled"/"skipped"/"" must
    never silently close a standing P0 for a suite that never passed.
    """
    client = FakeClient(existing={"number": 99, "body": mod.escalation_marker("integration")})
    with pytest.raises(ValueError, match="unknown nightly suite conclusion"):
        mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion="cancelled")

    # The pre-existing open issue must NOT have been closed (or even
    # commented on) as a side effect of the rejected call.
    assert _call_names(client) == ["find"]


def test_run_escalation_closes_only_on_the_explicit_success_constant() -> None:
    client = FakeClient(existing={"number": 5, "body": mod.escalation_marker("integration")})
    summary = mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion=mod.CONCLUSION_SUCCESS)
    assert _call_names(client) == ["find", "comment", "close"]
    assert "closed" in summary


def test_run_url_absent_falls_back_to_a_placeholder_never_crashes() -> None:
    client = FakeClient(existing=None)
    mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion="failure", run_url=None)
    (_, (_title, body, _labels)) = client.calls[1]
    assert "run link unavailable" in body


# ---------------------------------------------------------------------------
# token-absent degrade (C-005): exit 0, no crash, no token echoed
# ---------------------------------------------------------------------------
def test_main_without_token_warns_and_exits_zero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    rc = mod.main([*_MAIN_ARGS, "--suite-key", "integration", "--conclusion", "failure", "--repo", "spec-kitty/spec-kitty"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "skipping nightly P0 escalation" in captured.err
    assert _FAKE_TOKEN not in captured.out + captured.err


def test_main_without_repo_warns_and_exits_zero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GH_TOKEN", _FAKE_TOKEN)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    rc = mod.main([*_MAIN_ARGS, "--suite-key", "integration", "--conclusion", "failure"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "repository" in captured.err
    # Even when a token IS present, a degrade path must never echo it.
    assert _FAKE_TOKEN not in captured.out + captured.err


def test_main_degrades_to_exit_zero_on_api_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GH_TOKEN", _FAKE_TOKEN)

    def _boom(self: Any, marker: str) -> dict[str, Any] | None:
        raise mod.EscalationError("simulated outage")

    monkeypatch.setattr(mod.GitHubIssueClient, "find_open_issue_by_marker", _boom)
    rc = mod.main([*_MAIN_ARGS, "--suite-key", "integration", "--conclusion", "failure", "--repo", "spec-kitty/spec-kitty"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "degraded" in captured.err
    assert _FAKE_TOKEN not in captured.out + captured.err


def test_main_happy_path_routes_through_run_escalation(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GH_TOKEN", _FAKE_TOKEN)
    captured_client: dict[str, Any] = {}

    def _fake_find(self: Any, marker: str) -> dict[str, Any] | None:
        captured_client["find"] = marker
        return None

    def _fake_create(self: Any, *, title: str, body: str, labels: list[str]) -> dict[str, Any]:
        captured_client["create"] = (title, labels)
        return {"number": 5}

    monkeypatch.setattr(mod.GitHubIssueClient, "find_open_issue_by_marker", _fake_find)
    monkeypatch.setattr(mod.GitHubIssueClient, "create_issue", _fake_create)
    rc = mod.main([*_MAIN_ARGS, "--suite-key", "integration", "--conclusion", "failure", "--repo", "spec-kitty/spec-kitty", "--run-url", "https://run/7"])
    assert rc == 0
    assert captured_client["find"] == mod.escalation_marker("integration")
    assert captured_client["create"][1] == ["priority:P0"]
    assert "#5" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# real client: input validation + marker filtering + oldest-wins dedup
# ---------------------------------------------------------------------------
def test_github_client_rejects_a_malformed_repository() -> None:
    with pytest.raises(mod.EscalationError):
        mod.GitHubIssueClient("not-a-repo", _FAKE_TOKEN)


def test_github_client_rejects_an_empty_token() -> None:
    with pytest.raises(mod.EscalationError):
        mod.GitHubIssueClient("spec-kitty/spec-kitty", "")


def test_find_open_issue_filters_by_exact_marker_and_prefers_oldest(monkeypatch: pytest.MonkeyPatch) -> None:
    client = mod.GitHubIssueClient("spec-kitty/spec-kitty", _FAKE_TOKEN)
    marker = mod.escalation_marker("integration")
    fuzzy_hit_without_marker = {"number": 10, "body": "mentions integration but not the marker"}
    real_new = {"number": 30, "body": f"newer\n{marker}"}
    real_old = {"number": 20, "body": f"older\n{marker}"}

    def _fake_request(self: Any, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        return {"items": [fuzzy_hit_without_marker, real_new, real_old]}

    monkeypatch.setattr(mod.GitHubIssueClient, "_request", _fake_request)
    found = client.find_open_issue_by_marker(marker)
    assert found is not None
    assert found["number"] == 20  # oldest real marker match, fuzzy non-marker hit dropped


def test_find_open_issue_returns_none_when_no_body_carries_the_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    client = mod.GitHubIssueClient("spec-kitty/spec-kitty", _FAKE_TOKEN)

    def _fake_request(self: Any, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        return {"items": [{"number": 1, "body": "unrelated"}]}

    monkeypatch.setattr(mod.GitHubIssueClient, "_request", _fake_request)
    assert client.find_open_issue_by_marker(mod.escalation_marker("integration")) is None


def test_redact_removes_the_token_from_diagnostics() -> None:
    assert _FAKE_TOKEN not in mod._redact(f"boom {_FAKE_TOKEN} end", _FAKE_TOKEN)


# ---------------------------------------------------------------------------
# mainline-only gate, SCRIPT half (#5169/#5172/#5265): a non-main run can
# never open, bump or close a P0. The refs below include the exact branch
# that opened/bumped #5265 (run 36393904544) and near-miss spellings of main.
# ---------------------------------------------------------------------------
_NON_MAIN_REFS = (
    "refs/heads/claude/issue-3189-investigation-n3r4uk",
    "refs/heads/main-backup",
    "refs/heads/feature/main",
    "refs/tags/v4.0.0rc5",
    "refs/pull/5300/merge",
    "main",
    "refs/heads/Main",
    "",
    None,
)


def test_escalation_allowed_only_for_the_exact_mainline_ref() -> None:
    assert mod.MAINLINE_REF == _MAIN
    assert mod.escalation_allowed(_MAIN) is True
    for ref in _NON_MAIN_REFS:
        assert mod.escalation_allowed(ref) is False, ref


@pytest.mark.parametrize("ref", _NON_MAIN_REFS)
@pytest.mark.parametrize(
    ("conclusion", "existing", "forbidden_effect"),
    [
        ("failure", None, "open"),
        ("failure", {"number": 5265, "body": "<!-- nightly-escalation-key: integration -->"}, "bump"),
        ("success", {"number": 5265, "body": "<!-- nightly-escalation-key: integration -->"}, "close"),
    ],
)
def test_non_main_run_cannot_open_bump_or_close_a_p0(ref: str | None, conclusion: str, existing: dict[str, Any] | None, forbidden_effect: str) -> None:
    client = FakeClient(existing=existing)
    summary = mod.run_escalation(client, ref=ref, suite_key="integration", conclusion=conclusion, run_url="https://run/x")

    # Not even a lookup: the client is never touched on a non-mainline ref.
    assert client.calls == [], f"non-main ref {ref!r} must not {forbidden_effect} a P0"
    assert "skipped" in summary
    assert repr(ref) in summary


@pytest.mark.parametrize(
    ("conclusion", "existing", "expected_calls"),
    [
        ("failure", None, ["find", "create"]),
        ("failure", {"number": 7, "body": "m"}, ["find", "comment"]),
        ("success", {"number": 7, "body": "m"}, ["find", "comment", "close"]),
    ],
)
def test_main_ref_still_opens_bumps_and_closes(conclusion: str, existing: dict[str, Any] | None, expected_calls: list[str]) -> None:
    """Other side of the gate: the mainline ref keeps the full policy live."""
    client = FakeClient(existing=existing)
    mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion=conclusion)
    assert _call_names(client) == expected_calls


def test_run_escalation_has_no_default_ref_so_omission_cannot_bypass_the_gate() -> None:
    client = FakeClient(existing=None)
    with pytest.raises(TypeError):
        mod.run_escalation(client, suite_key="integration", conclusion="failure")
    assert client.calls == []


def _forbid_client_construction(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    constructed: list[str] = []

    def _init(self: Any, repository: str, token: str) -> None:
        constructed.append(repository)
        raise AssertionError("a non-main run must never build a GitHub client")

    monkeypatch.setattr(mod.GitHubIssueClient, "__init__", _init)
    return constructed


@pytest.mark.parametrize("conclusion", ["failure", "success"])
def test_main_with_non_main_ref_never_builds_a_client(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], conclusion: str) -> None:
    monkeypatch.setenv("GH_TOKEN", _FAKE_TOKEN)
    constructed = _forbid_client_construction(monkeypatch)
    rc = mod.main(
        [
            "--ref",
            "refs/heads/claude/issue-3189-investigation-n3r4uk",
            "--suite-key",
            "integration",
            "--conclusion",
            conclusion,
            "--repo",
            "spec-kitty/spec-kitty",
        ]
    )
    assert rc == 0
    assert constructed == []
    captured = capsys.readouterr()
    assert "skipped nightly P0 escalation" in captured.out
    assert _FAKE_TOKEN not in captured.out + captured.err


def test_main_reads_a_non_main_ref_from_github_ref_env(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GH_TOKEN", _FAKE_TOKEN)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/claude/issue-3189-investigation-n3r4uk")
    constructed = _forbid_client_construction(monkeypatch)
    rc = mod.main(["--suite-key", "integration", "--conclusion", "success", "--repo", "spec-kitty/spec-kitty"])
    assert rc == 0
    assert constructed == []
    assert "skipped nightly P0 escalation" in capsys.readouterr().out


def test_main_fails_closed_when_no_ref_is_known(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GH_TOKEN", _FAKE_TOKEN)
    monkeypatch.delenv("GITHUB_REF", raising=False)
    constructed = _forbid_client_construction(monkeypatch)
    rc = mod.main(["--suite-key", "integration", "--conclusion", "success", "--repo", "spec-kitty/spec-kitty"])
    assert rc == 0
    assert constructed == []
    assert "None" in capsys.readouterr().out


def test_main_escalates_when_github_ref_env_is_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GH_TOKEN", _FAKE_TOKEN)
    monkeypatch.setenv("GITHUB_REF", _MAIN)
    monkeypatch.setattr(mod.GitHubIssueClient, "find_open_issue_by_marker", lambda self, marker: None)
    monkeypatch.setattr(mod.GitHubIssueClient, "create_issue", lambda self, *, title, body, labels: {"number": 11})
    rc = mod.main(["--suite-key", "integration", "--conclusion", "failure", "--repo", "spec-kitty/spec-kitty"])
    assert rc == 0
    assert "created escalation issue #11" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# mainline-only gate, WORKFLOW half: every ci-nightly.yml step that invokes
# the escalation script is itself gated on the mainline ref AND passes the ref
# through, so the script's own gate always sees the real value.
# ---------------------------------------------------------------------------
def _load_workflow_jobs() -> dict[str, Any]:
    # Canonical splicing loader (LAND-PAT-003) -- never a raw yaml.safe_load.
    from tests.architectural._gate_coverage import load_spliced_workflow

    loaded = load_spliced_workflow(_WORKFLOW_PATH)
    jobs = loaded.get("jobs")
    assert isinstance(jobs, dict), "ci-nightly.yml must declare a jobs mapping"
    return jobs


def _escalation_steps(jobs: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (job_name, step)
        for job_name, job in jobs.items()
        if isinstance(job, dict)
        for step in job.get("steps") or []
        if isinstance(step, dict) and "nightly_escalation.py" in str(step.get("run") or "")
    ]


def _ungated_escalation_steps(jobs: dict[str, Any]) -> list[str]:
    """PRODUCTION comparison: one message per escalation step missing either
    half of the workflow-side mainline gate. The real-workflow guard and its
    mutation test below both call this SAME function."""
    problems: list[str] = []
    for job_name, step in _escalation_steps(jobs):
        label = f"{job_name}: {step.get('name')!r}"
        if _WORKFLOW_REF_CONDITION not in str(step.get("if") or ""):
            problems.append(f"{label} if: {step.get('if')!r} lacks {_WORKFLOW_REF_CONDITION!r}")
        run = str(step.get("run") or "")
        if _SCRIPT_REF_ARG not in run:
            problems.append(f"{label} run does not pass {_SCRIPT_REF_ARG}")
        # The value must be space-separated from the flag: a glued `--run-url"..."`
        # reaches argparse as one `--run-urlhttps://...` token and crashes the
        # escalation step (a main-only workflow PR CI never exercises).
        if '--run-url"' in run:
            problems.append(f"{label} run glues --run-url to its value (missing space)")
    return problems


def test_every_nightly_escalation_step_is_gated_on_the_mainline_ref() -> None:
    jobs = _load_workflow_jobs()
    steps = _escalation_steps(jobs)
    # Non-vacuity floor: performance, e2e, stress, integration,
    # specify-cli-out-of-matrix + at least one interpreter shard.
    assert len(steps) >= 6, f"expected >= 6 escalation steps in ci-nightly.yml, found {len(steps)}"
    assert _ungated_escalation_steps(jobs) == []


def test_ungated_escalation_step_is_caught_by_the_gate_check() -> None:
    """Mutation proof: a step with the pre-fix bare ``if: always()`` (the
    shape that let branch runs open #5169/#5172/#5265) must be flagged."""
    scratch_jobs = {
        "performance": {
            "steps": [
                {
                    "name": "Escalate performance red -> deduped P0 (fail-closed)",
                    "if": "always()",
                    "run": 'python3 scripts/ci/nightly_escalation.py --suite-key performance --conclusion "$conclusion"',
                }
            ]
        }
    }
    problems = _ungated_escalation_steps(scratch_jobs)
    assert len(problems) == 2, problems
