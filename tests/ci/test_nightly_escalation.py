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

import email.message
import importlib.util
import io
import json
import urllib.error
import urllib.parse
import urllib.request
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


_CREATED_ID = 900_042  # the new issue's database id -- deliberately NOT its number
_TRIAGE_CALLS = ["set_type", "find_milestone", "set_milestone", "add_sub_issue"]


def _triaged_issue(number: int, key: str = "integration") -> dict[str, Any]:
    """An open escalation issue that already carries the full #5517 triage."""
    return {
        "number": number,
        "id": number * 10,
        "body": mod.escalation_marker(key),
        "labels": [{"name": label} for label in mod.ESCALATION_LABELS],
        "type": {"name": mod.BUG_ISSUE_TYPE},
        "milestone": {"title": mod.MILESTONE_TITLE, "number": 11},
        "parent_issue_url": f"https://api.github.com/repos/spec-kitty/spec-kitty/issues/{mod.PARENT_ISSUE_NUMBER}",
    }


class FakeClient:
    """Records every escalation call; returns whatever issue is pre-seeded.

    ``fail`` names client methods that raise ``EscalationError``; ``drop``
    names methods that answer 2xx but leave the field unset (GitHub's silent
    drop when the caller may not set it).
    """

    def __init__(
        self,
        existing: dict[str, Any] | None = None,
        *,
        fail: frozenset[str] = frozenset(),
        drop: frozenset[str] = frozenset(),
        milestone_number: int | None = 11,
        created: dict[str, Any] | None = None,
    ) -> None:
        self._existing = existing
        self._fail = fail
        self._drop = drop
        self._milestone_number = milestone_number
        self._created = created
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self._next_number = 4242

    def _record(self, name: str, *args: Any) -> None:
        self.calls.append((name, args))
        if name in self._fail:
            raise mod.EscalationError(f"simulated {name} failure")

    def find_open_issue_by_marker(self, marker: str) -> dict[str, Any] | None:
        self.calls.append(("find", (marker,)))
        return self._existing

    def create_issue(self, *, title: str, body: str, labels: list[str]) -> dict[str, Any]:
        self.calls.append(("create", (title, body, tuple(labels))))
        if self._created is not None:
            return self._created
        return {
            "number": self._next_number,
            "id": _CREATED_ID,
            "labels": [{"name": label} for label in labels],
            "type": None,
            "milestone": None,
            "parent_issue_url": None,
        }

    def comment_on_issue(self, number: int, body: str) -> dict[str, Any]:
        self.calls.append(("comment", (number, body)))
        return {"id": 1}

    def close_issue(self, number: int) -> dict[str, Any]:
        self.calls.append(("close", (number,)))
        return {"number": number, "state": "closed"}

    def add_labels(self, number: int, labels: list[str]) -> list[dict[str, Any]]:
        self._record("add_labels", number, tuple(labels))
        return [] if "add_labels" in self._drop else [{"name": label} for label in labels]

    def set_issue_type(self, number: int, type_name: str) -> dict[str, Any]:
        self._record("set_type", number, type_name)
        return {"number": number, "type": None if "set_type" in self._drop else {"name": type_name}}

    def find_milestone_number(self, title: str) -> int | None:
        self._record("find_milestone", title)
        return self._milestone_number

    def set_milestone(self, number: int, milestone_number: int) -> dict[str, Any]:
        self._record("set_milestone", number, milestone_number)
        return {"number": number, "milestone": None if "set_milestone" in self._drop else {"title": mod.MILESTONE_TITLE}}

    def add_sub_issue(self, parent_number: int, sub_issue_id: int) -> dict[str, Any]:
        self._record("add_sub_issue", parent_number, sub_issue_id)
        return {"number": parent_number}


def _call_names(client: FakeClient) -> list[str]:
    return [name for name, _ in client.calls]


def _call_args(client: FakeClient, name: str) -> tuple[Any, ...]:
    matches = [args for call, args in client.calls if call == name]
    assert len(matches) == 1, f"expected exactly one {name!r} call, got {client.calls}"
    return matches[0]


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
def test_failure_with_no_open_issue_creates_a_p0_issue_with_marker() -> None:
    client = FakeClient(existing=None)
    warnings: list[str] = []
    summary = mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion="failure", run_url="https://run/1", warn=warnings.append)

    assert _call_names(client) == ["find", "create", *_TRIAGE_CALLS]
    assert warnings == []
    (_, (title, body, labels)) = client.calls[1]
    assert labels == ("priority:P0", "from:ci")
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
    # Already fully triaged, so the bump is exactly find + comment (no back-fill calls).
    client = FakeClient(existing=_triaged_issue(77))
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
    mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion="failure", run_url=None, warn=lambda _msg: None)
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
        return _triaged_issue(5)  # nothing left to triage -> no further API calls

    monkeypatch.setattr(mod.GitHubIssueClient, "find_open_issue_by_marker", _fake_find)
    monkeypatch.setattr(mod.GitHubIssueClient, "create_issue", _fake_create)
    rc = mod.main([*_MAIN_ARGS, "--suite-key", "integration", "--conclusion", "failure", "--repo", "spec-kitty/spec-kitty", "--run-url", "https://run/7"])
    assert rc == 0
    assert captured_client["find"] == mod.escalation_marker("integration")
    assert captured_client["create"][1] == ["priority:P0", "from:ci"]
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
    # Shell-metacharacter refs: make the injection-safety claim explicit. The
    # value flows env -> single argparse token -> exact `==`, never a shell, so
    # these are refused like any other non-main ref (no execution).
    "refs/heads/x; rm -rf /",
    "refs/heads/$(touch pwned)",
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
        ("failure", None, ["find", "create", *_TRIAGE_CALLS]),
        ("failure", _triaged_issue(7), ["find", "comment"]),
        ("success", {"number": 7, "body": "m"}, ["find", "comment", "close"]),
    ],
)
def test_main_ref_still_opens_bumps_and_closes(conclusion: str, existing: dict[str, Any] | None, expected_calls: list[str]) -> None:
    """Other side of the gate: the mainline ref keeps the full policy live."""
    client = FakeClient(existing=existing)
    mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion=conclusion, warn=lambda _msg: None)
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
    monkeypatch.setattr(mod.GitHubIssueClient, "create_issue", lambda self, *, title, body, labels: _triaged_issue(11))
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


# ---------------------------------------------------------------------------
# triage (#5517): type Bug, priority:P0 + from:ci, milestone, #5106 parent.
# First at the IssueClient seam (FakeClient), then at the HTTP boundary
# (urlopen stub) to pin the exact REST payloads the real client sends.
# ---------------------------------------------------------------------------
def test_triage_policy_constants_match_the_hand_triage_convention() -> None:
    assert mod.BUG_ISSUE_TYPE == "Bug"
    assert mod.ESCALATION_LABELS == ("priority:P0", "from:ci")
    assert mod.MILESTONE_TITLE == "4.0.0 release scope"
    assert mod.PARENT_ISSUE_NUMBER == 5106


def test_created_issue_is_typed_milestoned_and_linked_by_database_id() -> None:
    client = FakeClient(existing=None)
    warnings: list[str] = []
    summary = mod.run_escalation(client, ref=_MAIN, suite_key="e2e", conclusion="failure", warn=warnings.append)

    assert _call_args(client, "set_type") == (4242, "Bug")
    assert _call_args(client, "find_milestone") == ("4.0.0 release scope",)
    assert _call_args(client, "set_milestone") == (4242, 11)
    # The sub-issue link takes the database id, never the issue number.
    assert _call_args(client, "add_sub_issue") == (5106, _CREATED_ID)
    assert "add_labels" not in _call_names(client)  # both labels landed at create time
    assert warnings == []
    assert "triage incomplete" not in summary


@pytest.mark.parametrize(
    ("failing", "step_name"),
    [
        ("set_type", "issue type"),
        ("find_milestone", "milestone"),
        ("set_milestone", "milestone"),
        ("add_sub_issue", "parent #5106"),
    ],
)
def test_a_failed_triage_step_still_files_and_runs_the_other_steps(failing: str, step_name: str) -> None:
    client = FakeClient(existing=None, fail=frozenset({failing}))
    warnings: list[str] = []
    summary = mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion="failure", warn=warnings.append)

    assert _call_names(client)[:2] == ["find", "create"]
    assert "created escalation issue #4242" in summary
    assert f"triage incomplete: {step_name}" in summary
    assert len(warnings) == 1
    assert f"setting its {step_name} failed" in warnings[0]
    assert "#4242 is filed" in warnings[0]
    # Every independent step still ran; only the milestone PATCH depends on its lookup.
    assert "add_sub_issue" in _call_names(client)
    assert "set_type" in _call_names(client)


def test_every_triage_step_failing_never_aborts_filing() -> None:
    created = {"number": 4242, "id": _CREATED_ID, "labels": [{"name": "priority:P0"}], "type": None, "milestone": None, "parent_issue_url": None}
    everything = frozenset({"add_labels", "set_type", "find_milestone", "add_sub_issue"})
    client = FakeClient(existing=None, fail=everything, created=created)
    warnings: list[str] = []
    summary = mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion="failure", warn=warnings.append)

    assert "created escalation issue #4242" in summary
    assert "triage incomplete: labels, issue type, milestone, parent #5106" in summary
    assert len(warnings) == 4


@pytest.mark.parametrize(
    ("dropped", "step_name", "reason"),
    [
        ("set_type", "issue type", "did not set type 'Bug'"),
        ("set_milestone", "milestone", "did not set milestone '4.0.0 release scope'"),
    ],
)
def test_a_silently_dropped_field_is_reported_not_trusted(dropped: str, step_name: str, reason: str) -> None:
    """GitHub answers 2xx but drops type/milestone it will not let the caller set."""
    client = FakeClient(existing=None, drop=frozenset({dropped}))
    warnings: list[str] = []
    summary = mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion="failure", warn=warnings.append)

    assert f"triage incomplete: {step_name}" in summary
    assert len(warnings) == 1
    assert reason in warnings[0]


def test_missing_milestone_is_reported_and_never_patched() -> None:
    client = FakeClient(existing=None, milestone_number=None)
    warnings: list[str] = []
    mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion="failure", warn=warnings.append)

    assert "set_milestone" not in _call_names(client)
    assert len(warnings) == 1
    assert "no open milestone titled '4.0.0 release scope'" in warnings[0]


@pytest.mark.parametrize("drop", [frozenset(), frozenset({"add_labels"})])
def test_labels_dropped_at_create_are_re_applied_and_verified(drop: frozenset[str]) -> None:
    created = {"number": 4242, "id": _CREATED_ID, "labels": [{"name": "priority:P0"}], "type": None, "milestone": None, "parent_issue_url": None}
    client = FakeClient(existing=None, created=created, drop=drop)
    warnings: list[str] = []
    mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion="failure", warn=warnings.append)

    assert _call_args(client, "add_labels") == (4242, ("from:ci",))
    if drop:
        assert len(warnings) == 1
        assert "did not apply label(s) ['from:ci']" in warnings[0]
    else:
        assert warnings == []


@pytest.mark.parametrize("bad_id", [None, "900042", True])
def test_issue_without_a_numeric_database_id_cannot_be_linked(bad_id: Any) -> None:
    created = {**_triaged_issue(4242), "id": bad_id, "type": None, "milestone": None, "parent_issue_url": None}
    client = FakeClient(existing=None, created=created)
    warnings: list[str] = []
    mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion="failure", warn=warnings.append)

    assert "add_sub_issue" not in _call_names(client)
    assert len(warnings) == 1
    assert "no numeric database id" in warnings[0]


def test_bumped_issue_is_back_filled_with_only_what_it_lacks() -> None:
    """#5258 shape: P0 label + milestone set by hand, but no type, from:ci or parent."""
    existing = {
        "number": 5258,
        "id": 4_242_000,
        "body": mod.escalation_marker("specify-cli-out-of-matrix"),
        "labels": [{"name": "priority:P0"}],
        "type": None,
        "milestone": {"title": "4.0.0 release scope", "number": 11},
        "parent_issue_url": None,
    }
    client = FakeClient(existing=existing)
    warnings: list[str] = []
    summary = mod.run_escalation(client, ref=_MAIN, suite_key="specify-cli-out-of-matrix", conclusion="failure", warn=warnings.append)

    assert _call_names(client) == ["find", "comment", "add_labels", "set_type", "add_sub_issue"]
    assert _call_args(client, "add_labels") == (5258, ("from:ci",))
    assert _call_args(client, "add_sub_issue") == (5106, 4_242_000)
    assert "updated existing escalation issue #5258" in summary
    assert warnings == []


def test_back_fill_never_overrides_a_human_triage_decision() -> None:
    existing = {
        "number": 6000,
        "id": 1,
        "body": mod.escalation_marker("integration"),
        "labels": [{"name": label} for label in mod.ESCALATION_LABELS] + [{"name": "domain:runtime"}],
        "type": {"name": "Task"},
        "milestone": {"title": "Infra & Enablers 4.x", "number": 15},
        "parent_issue_url": "https://api.github.com/repos/spec-kitty/spec-kitty/issues/42",
    }
    client = FakeClient(existing=existing)
    mod.run_escalation(client, ref=_MAIN, suite_key="integration", conclusion="failure", warn=lambda _msg: None)
    assert _call_names(client) == ["find", "comment"]


def test_recovery_close_path_does_not_triage() -> None:
    client = FakeClient(existing={"number": 9, "body": mod.escalation_marker("e2e")})
    mod.run_escalation(client, ref=_MAIN, suite_key="e2e", conclusion="success", warn=lambda _msg: None)
    assert _call_names(client) == ["find", "comment", "close"]


def test_default_warning_is_a_github_actions_annotation_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    mod._emit_warning("issue #1 is filed, but setting its milestone failed")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("::warning title=Nightly escalation triage::issue #1 is filed")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, set()),
        ("priority:P0", set()),
        ([{"name": "priority:P0"}, "from:ci"], {"priority:P0", "from:ci"}),
    ],
)
def test_label_names_tolerates_any_response_shape(value: Any, expected: set[str]) -> None:
    assert mod._label_names(value) == expected


# --- HTTP boundary: the exact REST requests the real client sends ----------
_REPO = "spec-kitty/spec-kitty"
_REPO_PATH = f"/repos/{_REPO}"
_NEW_NUMBER = 6001
_NEW_ID = 777_001
_MILESTONES = [{"number": 4, "title": "Product backlog"}, {"number": 11, "title": "4.0.0 release scope"}]


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://api.github.com/x", code, "simulated", email.message.Message(), None)


def _patch_response(payload: dict[str, Any]) -> dict[str, Any]:
    """What PATCH /issues/N answers: the issue with the requested field applied."""
    if "type" in payload:
        return {"number": _NEW_NUMBER, "type": {"name": payload["type"]}}
    return {"number": _NEW_NUMBER, "milestone": {"title": "4.0.0 release scope", "number": payload["milestone"]}}


def _default_routes() -> dict[tuple[str, str], Any]:
    return {
        ("GET", "/search/issues"): {"items": []},
        ("POST", f"{_REPO_PATH}/issues"): {
            "number": _NEW_NUMBER,
            "id": _NEW_ID,
            "labels": [{"name": "priority:P0"}, {"name": "from:ci"}],
            "type": None,
            "milestone": None,
            "parent_issue_url": None,
        },
        ("PATCH", f"{_REPO_PATH}/issues/{_NEW_NUMBER}"): _patch_response,
        ("GET", f"{_REPO_PATH}/milestones"): _MILESTONES,
        ("POST", f"{_REPO_PATH}/issues/5106/sub_issues"): {"number": 5106},
    }


class FakeGitHub:
    """Stands in for ``urllib.request.urlopen``: routes (method, path) to a canned
    response (a value, a callable of the JSON payload, or an exception to raise)
    and records every request with its decoded JSON payload."""

    def __init__(self, routes: dict[tuple[str, str], Any]) -> None:
        self.routes = routes
        self.requests: list[tuple[str, str, Any]] = []

    def __call__(self, request: urllib.request.Request, timeout: float | None = None) -> io.BytesIO:
        url = urllib.parse.urlsplit(request.full_url)
        payload = json.loads(request.data) if isinstance(request.data, bytes) else None
        method = request.get_method()
        self.requests.append((method, url.path, payload))
        response = self.routes[(method, url.path)]
        if callable(response):
            response = response(payload)
        if isinstance(response, Exception):
            raise response
        return io.BytesIO(json.dumps(response).encode())

    def calls(self) -> list[tuple[str, str, Any]]:
        return list(self.requests)


def _run_main(monkeypatch: pytest.MonkeyPatch, fake: FakeGitHub) -> int:
    monkeypatch.setenv("GH_TOKEN", _FAKE_TOKEN)
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)
    return int(mod.main([*_MAIN_ARGS, "--suite-key", "integration", "--conclusion", "failure", "--repo", _REPO, "--run-url", "https://run/42"]))


def test_http_create_then_triage_sends_the_exact_rest_payloads(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeGitHub(_default_routes())
    assert _run_main(monkeypatch, fake) == 0

    methods_and_paths = [(method, path) for method, path, _ in fake.calls()]
    assert methods_and_paths == [
        ("GET", "/search/issues"),
        ("POST", f"{_REPO_PATH}/issues"),
        ("PATCH", f"{_REPO_PATH}/issues/{_NEW_NUMBER}"),
        ("GET", f"{_REPO_PATH}/milestones"),
        ("PATCH", f"{_REPO_PATH}/issues/{_NEW_NUMBER}"),
        ("POST", f"{_REPO_PATH}/issues/5106/sub_issues"),
    ]
    payloads = [payload for _, _, payload in fake.calls()]
    assert payloads[1]["labels"] == ["priority:P0", "from:ci"]
    assert payloads[2] == {"type": "Bug"}
    assert payloads[4] == {"milestone": 11}  # resolved by title, not hard-coded
    assert payloads[5] == {"sub_issue_id": _NEW_ID}  # database id, not the number
    captured = capsys.readouterr()
    assert f"created escalation issue #{_NEW_NUMBER} for 'integration'" in captured.out
    assert "::warning" not in captured.err


def test_http_milestone_lookup_only_reads_open_milestones(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    real = FakeGitHub(_default_routes())

    def _spy(request: urllib.request.Request, timeout: float | None = None) -> io.BytesIO:
        seen.append(request.full_url)
        return real(request, timeout)

    monkeypatch.setattr(mod.urllib.request, "urlopen", _spy)
    client = mod.GitHubIssueClient(_REPO, _FAKE_TOKEN)
    assert client.find_milestone_number("4.0.0 release scope") == 11
    assert client.find_milestone_number("no such milestone") is None
    assert "state=open" in seen[0]


@pytest.mark.parametrize(
    ("route", "error", "step_name"),
    [
        (("PATCH", f"{_REPO_PATH}/issues/{_NEW_NUMBER}"), _http_error(422), "issue type"),
        (("GET", f"{_REPO_PATH}/milestones"), _http_error(500), "milestone"),
        (("POST", f"{_REPO_PATH}/issues/5106/sub_issues"), _http_error(422), "parent #5106"),
    ],
)
def test_http_triage_failure_is_loud_and_never_blocks_filing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    route: tuple[str, str],
    error: Exception,
    step_name: str,
) -> None:
    routes = _default_routes()
    if route[0] == "PATCH":
        # Reject only the type PATCH; the milestone PATCH on the same URL still succeeds.
        routes[route] = lambda payload: error if "type" in payload else _patch_response(payload)
    else:
        routes[route] = error
    fake = FakeGitHub(routes)
    assert _run_main(monkeypatch, fake) == 0

    assert ("POST", f"{_REPO_PATH}/issues") in [(m, p) for m, p, _ in fake.calls()]
    captured = capsys.readouterr()
    assert f"created escalation issue #{_NEW_NUMBER} for 'integration' (triage incomplete: {step_name})" in captured.out
    assert f"::warning title=Nightly escalation triage::issue #{_NEW_NUMBER} is filed, but setting its {step_name} failed" in captured.err
    assert "GitHub API HTTP" in captured.err
    assert _FAKE_TOKEN not in captured.out + captured.err


def test_http_malformed_milestone_listing_degrades_one_step(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    routes = _default_routes()
    routes[("GET", f"{_REPO_PATH}/milestones")] = [{"title": "4.0.0 release scope"}]  # no "number"
    assert _run_main(monkeypatch, FakeGitHub(routes)) == 0
    captured = capsys.readouterr()
    assert "(triage incomplete: milestone)" in captured.out
    assert "setting its milestone failed" in captured.err


def test_http_non_list_milestone_response_is_treated_as_absent(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    routes = _default_routes()
    routes[("GET", f"{_REPO_PATH}/milestones")] = {"message": "unexpected"}
    assert _run_main(monkeypatch, FakeGitHub(routes)) == 0
    assert "no open milestone titled '4.0.0 release scope'" in capsys.readouterr().err


def test_http_bumped_issue_back_fill_payloads(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    marker = mod.escalation_marker("integration")
    existing = {"number": 5258, "id": 4_242_000, "body": marker, "labels": [{"name": "priority:P0"}], "type": None, "milestone": None, "parent_issue_url": None}
    routes = _default_routes()
    routes[("GET", "/search/issues")] = {"items": [existing]}
    routes[("POST", f"{_REPO_PATH}/issues/5258/comments")] = {"id": 1}
    routes[("POST", f"{_REPO_PATH}/issues/5258/labels")] = [{"name": "priority:P0"}, {"name": "from:ci"}]
    routes[("PATCH", f"{_REPO_PATH}/issues/5258")] = _patch_response
    fake = FakeGitHub(routes)
    assert _run_main(monkeypatch, fake) == 0

    by_route = {(method, path): payload for method, path, payload in fake.calls() if method != "PATCH"}
    patches = [payload for method, _, payload in fake.calls() if method == "PATCH"]
    assert ("POST", f"{_REPO_PATH}/issues") not in by_route  # dedupe: never a second issue
    assert by_route[("POST", f"{_REPO_PATH}/issues/5258/labels")] == {"labels": ["from:ci"]}
    assert patches == [{"type": "Bug"}, {"milestone": 11}]
    assert by_route[("POST", f"{_REPO_PATH}/issues/5106/sub_issues")] == {"sub_issue_id": 4_242_000}
    captured = capsys.readouterr()
    assert "updated existing escalation issue #5258" in captured.out
    assert "::warning" not in captured.err
