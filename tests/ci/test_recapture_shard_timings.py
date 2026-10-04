"""Tests for ``scripts/ci/recapture_shard_timings.py``.

Mission shared-collection-and-shard-recapture-01M42V58, WP04 (FR-017..FR-021, NFR-007,
C-008; contract ``contracts/scheduled-recapture.md``), on top of the credential-split
design of mission per-pr-shard-timings-recapture-friction-01M3H7V8 (FR-005..FR-010).

The graded surface is :func:`main` -- the real entry point, driven through its phases --
against a small temporary repository. Every external call (``pytest --collect-only``, the
canonical producer, ``git``, ``gh``) goes through ``subprocess.run`` and is answered by
:class:`World`, a fake that writes plausible producer data and records the exact argument
lists; no real capture, network, git or gh call is made. The pure decisions
(:func:`is_valid_capture`, :func:`drifted_modules`, :func:`overlay_proposal`, ...) are
tested directly.

The module is imported directly (``scripts.ci`` resolves as a namespace package with the
repo root on ``sys.path``), mirroring ``tests/ci/test_stale_running_sweep.py``.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from scripts.ci import capture_shard_timings
from scripts.ci import recapture_shard_timings as recapture
from scripts.ci.recapture_shard_timings import (
    PHASE_CAPTURE,
    PHASE_PUBLISH,
    RECAPTURE_BRANCH,
    SECRET_NAME,
    capture_is_trustworthy,
    find_open_recapture_pr,
    require_recapture_token,
)

pytestmark = pytest.mark.fast

FAKE_TOKEN = "fake-recapture-token-not-a-real-secret"  # noqa: S105 (obviously-fake test value)
FAKE_GITHUB_TOKEN = "fake-ambient-github-token-not-a-real-secret"  # noqa: S105 (obviously-fake test value)
REPOSITORY = "spec-kitty/spec-kitty"
RUN_URL = "https://github.com/spec-kitty/spec-kitty/actions/runs/123"
TIMINGS_GIT_PATH = ".github/ci-shard-timings.json"
WORKFLOW_PATH = recapture.REPO_ROOT / ".github" / "workflows" / "ci-shard-recapture.yml"


def _set_token(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv(SECRET_NAME, raising=False)
    else:
        monkeypatch.setenv(SECRET_NAME, value)


# --------------------------------------------------------------------------- #
# Retained helpers' tests (unchanged behaviour).                              #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("pytest_exit_code", "after_length", "expected"),
    [
        (0, 10, True),
        (1, 10, True),
        (0, 0, False),
        (1, 0, False),
        (2, 10, False),
        (2, 0, False),
        (5, 10, False),
        (5, 0, False),
        (None, 10, False),
    ],
    ids=[
        "clean-nonempty",
        "ordinary-failures-nonempty",
        "clean-but-empty",
        "failures-but-empty",
        "interrupted-nonempty",
        "interrupted-empty",
        "no-tests-collected-nonempty",
        "no-tests-collected-empty",
        "no-exit-code-nonempty",
    ],
)
def test_capture_is_trustworthy(pytest_exit_code: int | None, after_length: int, expected: bool) -> None:
    """F2: only exit codes 0/1 (a suite that actually RAN, whether or not tests
    passed) paired with a non-empty captured module count as trustworthy. A
    collection-error exit code (2, 5, ...) or an empty captured module -- even
    if paired with an exit code that would otherwise pass -- must never be
    treated as a legitimate recapture; committing `charter: []` and opening a
    PR from a collection error is a fail-open regression."""
    assert capture_is_trustworthy(pytest_exit_code, after_length) is expected


def test_find_open_recapture_pr_matches_fixed_head_branch() -> None:
    open_prs = [{"number": 99, "headRefName": RECAPTURE_BRANCH}]
    assert find_open_recapture_pr(open_prs) == 99


def test_find_open_recapture_pr_ignores_unrelated_head_branch() -> None:
    """Fixture 2: an unrelated PR touching the same file on a different head (the
    #5175/#5177 shape) is never matched, even though the JSON shape carries a number."""
    open_prs = [{"number": 5177, "headRefName": "fix/unrelated-topic"}]
    assert find_open_recapture_pr(open_prs) is None


def test_find_open_recapture_pr_returns_none_for_empty_list() -> None:
    assert find_open_recapture_pr([]) is None


def test_find_open_recapture_pr_raises_loudly_for_non_int_number(capsys: pytest.CaptureFixture[str]) -> None:
    """pr-contract-001: a malformed `number` field (non-int) on the matching PR must fail
    loudly, never be silently coerced to None (indistinguishable from "no PR open")."""
    open_prs = [{"number": "not-an-int", "headRefName": RECAPTURE_BRANCH}]
    with pytest.raises(SystemExit) as exc_info:
        find_open_recapture_pr(open_prs)
    assert exc_info.value.code != 0
    assert "::error::" in capsys.readouterr().err


def test_require_recapture_token_returns_value_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    assert require_recapture_token() == FAKE_TOKEN


@pytest.mark.parametrize("token_value", ["", None], ids=["empty-string", "unset"])
def test_require_recapture_token_raises_for_empty_or_unset(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], token_value: str | None) -> None:
    _set_token(monkeypatch, token_value)
    with pytest.raises(SystemExit) as exc_info:
        require_recapture_token()
    assert exc_info.value.code != 0
    assert SECRET_NAME in capsys.readouterr().err


@pytest.mark.parametrize("github_token_value", [FAKE_GITHUB_TOKEN, ""], ids=["distinct-value", "empty-string"])
def test_require_recapture_token_ignores_github_token_fallback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], github_token_value: str
) -> None:
    """CL-002/FR-005: an ambient GITHUB_TOKEN must never satisfy the dedicated-secret check.

    A fallback to GITHUB_TOKEN would silently defeat the anti-recursion protection this
    mission exists to add (a GITHUB_TOKEN-authored PR does not trigger other workflows'
    pull_request events). CHARTER_SHARD_RECAPTURE_TOKEN is unset here in both cases; an
    ambient GITHUB_TOKEN -- whether a distinct real-looking value or GitHub's own
    injected-empty-string case -- must still raise SystemExit, never be silently accepted.
    """
    monkeypatch.delenv(SECRET_NAME, raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", github_token_value)
    with pytest.raises(SystemExit) as exc_info:
        require_recapture_token()
    assert exc_info.value.code != 0
    assert SECRET_NAME in capsys.readouterr().err


def test_run_url_composes_from_default_actions_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "spec-kitty/spec-kitty")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    assert recapture._run_url() == "https://github.com/spec-kitty/spec-kitty/actions/runs/42"


def test_write_job_summary_appends_to_step_summary_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    summary_path = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))
    recapture._write_job_summary("hello world")
    assert summary_path.read_text(encoding="utf-8") == "hello world\n"
    assert "hello world" in capsys.readouterr().out


def test_write_job_summary_prints_only_when_no_summary_file(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    recapture._write_job_summary("hello world")
    assert capsys.readouterr().out.strip() == "hello world"


def test_list_open_recapture_prs_invokes_gh_with_token_and_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class _FakeCompletedProcess:
        stdout = json.dumps([{"number": 1, "headRefName": RECAPTURE_BRANCH}])

    def _fake_run(cmd: list[str], **kwargs: Any) -> _FakeCompletedProcess:
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env")
        return _FakeCompletedProcess()

    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = recapture._list_open_recapture_prs("spec-kitty/spec-kitty", FAKE_TOKEN)

    assert result == [{"number": 1, "headRefName": RECAPTURE_BRANCH}]
    assert captured["cmd"][:3] == ["gh", "pr", "list"]
    assert "--json" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--json") + 1] == "number,headRefName"
    assert captured["env"]["GH_TOKEN"] == FAKE_TOKEN


def test_list_open_recapture_prs_raises_loudly_for_non_list_payload(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """pr-contract-001: an unexpected `gh pr list` JSON shape (e.g. an object instead of a
    list -- a schema change) must fail loudly, never be silently coerced to []
    (indistinguishable, downstream, from a genuine "no open PR" answer before a force-push)."""

    class _FakeCompletedProcess:
        stdout = json.dumps({"unexpected": "object-shape"})

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _FakeCompletedProcess())

    with pytest.raises(SystemExit) as exc_info:
        recapture._list_open_recapture_prs("spec-kitty/spec-kitty", FAKE_TOKEN)
    assert exc_info.value.code != 0
    assert "::error::" in capsys.readouterr().err


@pytest.mark.parametrize("stdout", ["", "not json at all", "<html>502 Bad Gateway</html>"], ids=["empty", "plain-text", "html"])
def test_list_open_recapture_prs_fails_loudly_on_non_json_output(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], stdout: str) -> None:
    """F8: non-JSON `gh pr list` output (empty stdout, a proxy error page, a gh warning)
    surfaces through the ::error:: convention and SystemExit(1) -- never a raw
    JSONDecodeError traceback -- and the pre-push open-PR decision is never reached."""

    fake = subprocess.CompletedProcess(args=["gh"], returncode=0, stdout=stdout)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: fake)

    with pytest.raises(SystemExit) as exc_info:
        recapture._list_open_recapture_prs("spec-kitty/spec-kitty", FAKE_TOKEN)
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "::error::" in err
    assert "gh pr list" in err
    assert FAKE_TOKEN not in err


def test_list_open_recapture_prs_fails_loudly_on_subprocess_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """pr-contract-002: a genuine `gh pr list` transport failure (auth expiry, rate limit,
    network error) surfaces through the script's own ::error:: convention and a clean
    SystemExit, never a raw, unhandled CalledProcessError traceback."""

    def _fake_run(cmd: list[str], **kwargs: Any) -> None:
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(SystemExit) as exc_info:
        recapture._list_open_recapture_prs("spec-kitty/spec-kitty", FAKE_TOKEN)
    assert exc_info.value.code != 0
    err = capsys.readouterr().err
    assert "::error::" in err
    assert "gh pr list" in err


def test_push_auth_header_encodes_x_access_token_basic_scheme() -> None:
    """F1: the header value git needs to push without a persisted credential -- basic-auth
    scheme with the PAT as the password against a fixed `x-access-token` username."""
    header = recapture._push_auth_header(FAKE_TOKEN)
    assert header.startswith("AUTHORIZATION: basic ")
    encoded = header.removeprefix("AUTHORIZATION: basic ")
    decoded = base64.b64decode(encoded).decode("ascii")
    assert decoded == f"x-access-token:{FAKE_TOKEN}"


def _clear_git_config_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [key for key in os.environ if key.startswith("GIT_CONFIG_")]:
        monkeypatch.delenv(key)


def test_push_env_appends_after_ambient_git_config_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """F1: pre-existing env-scoped git config (GIT_CONFIG_COUNT=N) is preserved; the push
    credential is appended at index N, never clobbering index 0."""
    _clear_git_config_env(monkeypatch)
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.pager")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "cat")
    monkeypatch.setenv("GIT_CONFIG_KEY_1", "safe.directory")
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", "*")
    env = recapture._push_env(FAKE_TOKEN)
    assert env["GIT_CONFIG_COUNT"] == "3"
    assert env["GIT_CONFIG_KEY_0"] == "core.pager"
    assert env["GIT_CONFIG_KEY_1"] == "safe.directory"
    assert env["GIT_CONFIG_KEY_2"] == "http.https://github.com/.extraheader"
    assert env["GIT_CONFIG_VALUE_2"] == recapture._push_auth_header(FAKE_TOKEN)


def test_scrubbed_env_drops_every_token_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    monkeypatch.setenv("GH_TOKEN", "x")
    monkeypatch.setenv("GITHUB_TOKEN", FAKE_GITHUB_TOKEN)
    monkeypatch.setenv("PATH", "/usr/bin")
    env = recapture._scrubbed_env()
    assert SECRET_NAME not in env
    assert "GH_TOKEN" not in env
    assert "GITHUB_TOKEN" not in env
    assert env["PATH"] == "/usr/bin"


def test_write_github_output_appends_to_output_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    output_path = tmp_path / "output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
    recapture._write_github_output(drift="true", before=10, after=12)
    assert output_path.read_text(encoding="utf-8") == "drift=true\nbefore=10\nafter=12\n"
    out = capsys.readouterr().out
    assert "drift=true" in out
    assert "before=10" in out
    assert "after=12" in out


def test_write_github_output_falls_back_to_stdout_when_unset(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    recapture._write_github_output(drift="false")
    assert capsys.readouterr().out.strip() == "drift=false"


def _recapture_job() -> dict[str, Any]:
    import yaml

    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    job: dict[str, Any] = workflow["jobs"]["recapture-shard-timings"]
    return job


def test_workflow_never_overrides_runner_default_github_env_vars() -> None:
    """F3: GITHUB_* runner defaults must not be re-declared in any step env --
    `${{ github.step_summary }}` is not a context property and evaluates to "", which
    would blank $GITHUB_STEP_SUMMARY and silently drop the skip summary."""
    for step in _recapture_job()["steps"]:
        overridden = sorted(key for key in step.get("env", {}) if key.startswith("GITHUB_"))
        assert overridden == [], f"step {step.get('name')!r} overrides {overridden}"


def test_recapture_job_only_runs_on_main() -> None:
    """F4: a `workflow_dispatch` from a topic branch must never commit that branch's
    capture onto the fixed recapture branch (or open a PR from it) -- the job is gated
    to `refs/heads/main`."""
    # The leading conjunct is the fork guard (tests/ci/test_fork_guard.py).
    assert _recapture_job().get("if") == (
        "${{ (github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'pull_request'"
        " || github.event_name == 'workflow_dispatch') && github.ref == 'refs/heads/main' }}"
    )


# --------------------------------------------------------------------------- #
# Fixtures: a temporary repository and the fake behind ``subprocess.run``.    #
# --------------------------------------------------------------------------- #

OLD = "2026-09-01T00:00:00+00:00"
NEWER = "2026-09-20T00:00:00+00:00"
NEWEST = "2026-09-30T00:00:00+00:00"


def _entry_tables(count: int, *, captured_at: str | None, exit_code: int = 0, measured: int | None = None, run_id: str = "committed") -> dict[str, Any]:
    """One module's four tables as the producer writes them (``captured_at=None``: no provenance)."""
    provenance = None
    if captured_at is not None:
        provenance = {
            "run_id": run_id,
            "captured_at": captured_at,
            "exit_code": exit_code,
            "unique_tests_measured": count if measured is None else measured,
            "producer": "scripts/ci/capture_shard_timings.py",
        }
    return {"count": count, "provenance": provenance}


def _payload(modules: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "module_test_durations": {},
        "module_test_count": {},
        "module_duration_seconds": {},
        "module_capture_provenance": {},
    }
    for module, tables in modules.items():
        count = tables["count"]
        payload["module_test_durations"][module] = [0.25] * count
        payload["module_test_count"][module] = count
        payload["module_duration_seconds"][module] = round(0.25 * count, 3)
        if tables["provenance"] is not None:
            payload["module_capture_provenance"][module] = tables["provenance"]
    return payload


def _module_slice(payload: dict[str, Any], module: str) -> dict[str, Any]:
    """The four per-module entries, for a byte-for-byte comparison of one module's data."""
    return {key: payload[key].get(module) for key in ("module_test_durations", "module_test_count", "module_duration_seconds", "module_capture_provenance")}


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2) + "\n"


#: What the fake producer leaves behind to simulate a damaged file after a clean exit.
_UNREADABLE_FILE_OUTCOMES = {"garbled": "{ this is not json", "not-a-mapping": "[1, 2, 3]\n"}


@dataclass
class World:
    """A temporary repository plus the fake that answers every subprocess the script starts."""

    root: Path
    counts: dict[str, int] = field(default_factory=dict)
    outcomes: dict[str, str] = field(default_factory=dict)
    clock: dict[str, float] = field(default_factory=lambda: {"t": 0.0})
    seconds_per_capture: float = 0.0
    proposal_json: str = ""
    proposal_tip_text: str = "stale proposal tip\n"
    open_prs: list[dict[str, object]] = field(default_factory=list)
    push_stderr: str | None = None
    collect_timeouts: set[str] = field(default_factory=set)
    calls: list[list[str]] = field(default_factory=list)
    envs: list[dict[str, str] | None] = field(default_factory=list)
    kwargs_seen: list[dict[str, Any]] = field(default_factory=list)
    added_snapshots: list[str] = field(default_factory=list)

    @property
    def timings_path(self) -> Path:
        return self.root / TIMINGS_GIT_PATH

    def write_timings(self, payload: dict[str, Any]) -> None:
        self.timings_path.write_text(_dump(payload), encoding="utf-8")

    def read_timings(self) -> dict[str, Any]:
        loaded: dict[str, Any] = json.loads(self.timings_path.read_text(encoding="utf-8"))
        return loaded

    def producer_calls(self) -> list[str]:
        """The modules the canonical producer was asked to capture, in call order."""
        return [cmd[cmd.index("--module") + 1] for cmd in self.calls if "scripts.ci.capture_shard_timings" in cmd]

    def git_calls(self) -> list[list[str]]:
        return [cmd for cmd in self.calls if cmd[0] == "git"]

    # -- the fake -------------------------------------------------------------
    def run(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(cmd))
        self.envs.append(kwargs.get("env"))
        self.kwargs_seen.append(dict(kwargs))
        if "-m" in cmd and "pytest" in cmd:
            return self._collect(cmd, kwargs)
        if "scripts.ci.capture_shard_timings" in cmd:
            return self._produce(cmd, kwargs)
        if cmd[0] == "git":
            return self._git(cmd)
        if cmd[0] == "gh":
            stdout = json.dumps(self.open_prs) if cmd[1:3] == ["pr", "list"] else ""
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")
        raise AssertionError(f"unexpected subprocess: {cmd}")

    def _collect(self, cmd: list[str], kwargs: dict[str, Any]) -> subprocess.CompletedProcess[str]:
        module = next(part.split("/")[1] for part in cmd if part.startswith("tests/"))
        if module in self.collect_timeouts:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout") or 0)
        lines = [f"tests/{module}/test_x.py::test_{index}" for index in range(self.counts[module])]
        return subprocess.CompletedProcess(cmd, 0, stdout="\n".join([*lines, "", f"{len(lines)} tests collected"]) + "\n", stderr="")

    def _produce(self, cmd: list[str], kwargs: dict[str, Any]) -> subprocess.CompletedProcess[str]:
        module = cmd[cmd.index("--module") + 1]
        run_id = cmd[cmd.index("--run-id") + 1]
        self.clock["t"] += self.seconds_per_capture
        outcome = self.outcomes.get(module, "valid")
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        if outcome == "crash":
            return subprocess.CompletedProcess(cmd, 1)
        if outcome == "os-error":  # the producer damaged the file, then the call itself failed (e.g. a broken pipe)
            self.timings_path.write_text("{ half written", encoding="utf-8")
            raise BrokenPipeError("simulated failure of the subprocess call")
        if outcome in _UNREADABLE_FILE_OUTCOMES:  # the producer exits 0 yet leaves a file nobody can read
            self.timings_path.write_text(_UNREADABLE_FILE_OUTCOMES[outcome], encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0)
        exit_code, measured = {"valid": (0, self.counts[module]), "failing-tests": (1, self.counts[module]), "invalid": (2, 0)}[outcome]
        payload = self.read_timings()
        tables = _payload({module: _entry_tables(measured, captured_at="2026-10-04T00:00:00+00:00", exit_code=exit_code, run_id=run_id)})
        for key in ("module_test_durations", "module_test_count", "module_duration_seconds", "module_capture_provenance"):
            payload.setdefault(key, {})[module] = tables[key][module]
        self.write_timings(payload)
        return subprocess.CompletedProcess(cmd, 0 if exit_code == 0 else 1)

    def _git(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        if cmd[1] == "show":
            return subprocess.CompletedProcess(cmd, 0, stdout=self.proposal_json, stderr="")
        if cmd[1] == "checkout":
            self.timings_path.write_text(self.proposal_tip_text, encoding="utf-8")  # the working tree moves to the proposal tip
        if cmd[1] == "add":
            self.added_snapshots.append(self.timings_path.read_text(encoding="utf-8"))
        if cmd[1] == "push" and self.push_stderr is not None:
            raise subprocess.CalledProcessError(128, cmd, stderr=self.push_stderr)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    root = tmp_path / "repo"
    (root / ".github").mkdir(parents=True)
    world = World(root=root)
    monkeypatch.setattr(recapture, "REPO_ROOT", root)
    monkeypatch.setattr(recapture, "TIMINGS_PATH", world.timings_path)
    monkeypatch.setattr(recapture, "REGISTRY_PATH", root / ".github" / "ci-module-registry.yml")
    monkeypatch.setattr(capture_shard_timings, "REPO_ROOT", root)
    monkeypatch.setattr(recapture, "_now_seconds", lambda: world.clock["t"])
    monkeypatch.setattr(subprocess, "run", world.run)
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "github-output.txt"))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.delenv(SECRET_NAME, raising=False)
    monkeypatch.delenv(recapture.PROPOSAL_OPEN_ENV_VAR, raising=False)
    monkeypatch.delenv(recapture.RESULT_ENV_VAR, raising=False)
    return world


def _seed(world: World, modules: dict[str, dict[str, Any]], *, collected: dict[str, int]) -> None:
    """Commit *modules* to the timings file; *collected* is what live collection finds."""
    rows = "".join(f"- module: {module}\n" for module in modules)
    (world.root / ".github" / "ci-module-registry.yml").write_text(f"modules:\n{rows}", encoding="utf-8")
    for module in modules:
        (world.root / "tests" / module).mkdir(parents=True, exist_ok=True)
    world.counts = dict(collected)
    world.write_timings(_payload(modules))


def _github_outputs(path: Path) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        name, _, value = line.partition("=")
        outputs[name] = value
    return outputs


def _capture(world: World, *args: str) -> tuple[int, dict[str, str], dict[str, Any]]:
    """Run ``capture --write`` through ``main``; return (exit status, step outputs, result)."""
    exit_code = recapture.main([PHASE_CAPTURE, "--write", *args])
    outputs = _github_outputs(Path(os.environ["GITHUB_OUTPUT"]))
    return exit_code, outputs, json.loads(outputs["result"])


# --------------------------------------------------------------------------- #
# The valid-capture predicate -- the single authority (research D-11).        #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("provenance", "expected"),
    [
        ({"exit_code": 0, "unique_tests_measured": 5}, True),
        ({"exit_code": 1, "unique_tests_measured": 5}, True),
        ({"exit_code": 0, "unique_tests_measured": 0}, False),
        ({"exit_code": 1, "unique_tests_measured": 0}, False),
        ({"exit_code": 2, "unique_tests_measured": 5}, False),
        ({"exit_code": 5, "unique_tests_measured": 5}, False),
        ({"unique_tests_measured": 5}, False),
        ({"exit_code": 0}, False),
        ({"exit_code": True, "unique_tests_measured": 5}, False),
        (None, False),
    ],
    ids=["clean", "failing-tests", "clean-empty", "failing-empty", "interrupted", "none-collected", "no-exit", "no-count", "bool-exit", "missing"],
)
def test_is_valid_capture(provenance: dict[str, Any] | None, expected: bool) -> None:
    assert recapture.is_valid_capture(provenance) is expected


# --------------------------------------------------------------------------- #
# Pure decisions.                                                             #
# --------------------------------------------------------------------------- #


def test_drifted_modules_flags_count_difference_and_bad_provenance() -> None:
    timings = _payload(
        {
            "same": _entry_tables(3, captured_at=OLD),
            "grew": _entry_tables(3, captured_at=OLD),
            "no-provenance": _entry_tables(3, captured_at=None),
            "bad-provenance": _entry_tables(3, captured_at=OLD, exit_code=2),
        }
    )
    counts = {"same": 3, "grew": 4, "no-provenance": 3, "bad-provenance": 3}
    assert recapture.drifted_modules(list(counts), timings, counts) == ["grew", "no-provenance", "bad-provenance"]


def test_drifted_modules_leaves_out_a_module_whose_count_is_unknown() -> None:
    timings = _payload({"known": _entry_tables(3, captured_at=OLD), "unknown": _entry_tables(3, captured_at=OLD)})
    assert recapture.drifted_modules(["known", "unknown"], timings, {"known": 4}) == ["known"]


def test_order_oldest_first_puts_missing_provenance_first_then_oldest() -> None:
    timings = _payload(
        {
            "newest": _entry_tables(1, captured_at=NEWEST),
            "oldest": _entry_tables(1, captured_at=OLD),
            "missing": _entry_tables(1, captured_at=None),
            "newer": _entry_tables(1, captured_at=NEWER),
        }
    )
    assert recapture.order_oldest_first(["newest", "oldest", "missing", "newer"], timings) == ["missing", "oldest", "newer", "newest"]


def test_overlay_proposal_takes_only_modules_the_proposal_refreshed() -> None:
    baseline = _payload({"a": _entry_tables(3, captured_at=OLD), "b": _entry_tables(3, captured_at=OLD), "c": _entry_tables(5, captured_at=NEWER)})
    proposal = _payload(
        {"a": _entry_tables(4, captured_at=NEWEST, run_id="refreshed"), "b": _entry_tables(3, captured_at=OLD), "c": _entry_tables(5, captured_at=NEWER)}
    )
    # The proposal was cut before the primary branch changed `c`'s tables; its provenance is the same.
    proposal["module_test_count"]["c"] = 2
    proposal["module_test_durations"]["c"] = [0.25, 0.25]
    merged = recapture.overlay_proposal(baseline, proposal)
    assert _module_slice(merged, "a") == _module_slice(proposal, "a")
    assert _module_slice(merged, "b") == _module_slice(baseline, "b")
    # `c` differs in its tables but not in provenance: the proposal did not refresh it, so the
    # baseline (the primary branch's current value) is kept and no unrelated change reverts.
    assert _module_slice(merged, "c") == _module_slice(baseline, "c")


def test_recapture_result_round_trips_and_only_captures_are_publishable() -> None:
    result = recapture.RecaptureResult(drifted=("a", "b", "c"), captured=("a",), failed=("b",), deferred=("c",), reasons={"b": "timed out"})
    assert recapture.RecaptureResult.from_json(result.to_json()) == result
    assert result.publishable is True
    assert recapture.RecaptureResult(drifted=("b",), failed=("b",)).publishable is False
    table = result.summary_table()
    assert "`a` | captured" in table
    assert "`b` | failed: timed out" in table
    assert "`c` | deferred" in table


def test_proposal_body_and_commit_message_list_captured_failed_and_deferred() -> None:
    result = recapture.RecaptureResult(drifted=("a", "b", "c"), captured=("a",), failed=("b",), deferred=("c",))
    for text in (result.proposal_body(RUN_URL), result.commit_message()):
        assert "`a`" in text
        assert "`b`" in text
        assert "`c`" in text
    body = result.proposal_body(RUN_URL)
    assert RUN_URL in body
    assert ".github/ci-shard-timings.json" in body
    assert "{" not in body and "}" not in body
    assert len(result.commit_message().splitlines()[0]) < 72


@pytest.mark.parametrize(
    ("stderr", "forced", "needles"),
    [
        (
            "remote: Permission to spec-kitty/spec-kitty.git denied to bot.\nfatal: unable to access: The requested URL returned error: 403",
            True,
            [SECRET_NAME, "write access"],
        ),
        ("fatal: unable to access 'https://github.com/x/y/': The requested URL returned error: 403", False, [SECRET_NAME, "write access"]),
        (" ! [rejected]        HEAD -> ci/recapture (fetch first)", False, ["NOT forced", RECAPTURE_BRANCH]),
        ("fatal: some other failure", True, ["some other failure"]),
    ],
    ids=["permission-denied", "http-403", "branch-moved", "other"],
)
def test_push_failure_message_classifies_git_stderr(stderr: str, forced: bool, needles: list[str]) -> None:
    message = recapture.push_failure_message(stderr, forced=forced)
    for needle in needles:
        assert needle in message


# --------------------------------------------------------------------------- #
# Capture phase through main(argv) -- FR-017, FR-018, FR-019, SC-006.        #
# --------------------------------------------------------------------------- #


def test_only_the_drifted_non_charter_module_is_captured(world: World) -> None:
    """SC-006: one drifted non-charter module is refreshed and no other module is touched."""
    _seed(
        world,
        {"charter": _entry_tables(4, captured_at=OLD), "agent": _entry_tables(3, captured_at=OLD), "unit": _entry_tables(5, captured_at=OLD)},
        collected={"charter": 4, "agent": 3, "unit": 6},
    )
    before = world.read_timings()

    exit_code, outputs, result = _capture(world)

    assert exit_code == 0
    assert world.producer_calls() == ["unit"]
    assert result["drifted"] == ["unit"]
    assert result["captured"] == ["unit"]
    assert result["failed"] == []
    assert outputs["drift"] == "true"
    after = world.read_timings()
    assert after["module_test_count"]["unit"] == 6
    assert _module_slice(after, "charter") == _module_slice(before, "charter")
    assert _module_slice(after, "agent") == _module_slice(before, "agent")


def test_every_producer_subprocess_runs_without_any_token(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "ambient")
    monkeypatch.setenv("GITHUB_TOKEN", FAKE_GITHUB_TOKEN)
    _seed(world, {"unit": _entry_tables(5, captured_at=OLD)}, collected={"unit": 6})

    assert _capture(world)[0] == 0

    assert world.envs
    for env in world.envs:
        assert env is not None
        assert not {SECRET_NAME, "GH_TOKEN", "GITHUB_TOKEN"} & set(env)


@pytest.mark.parametrize(
    "provenance",
    [None, {"exit_code": 2, "unique_tests_measured": 0, "captured_at": OLD}],
    ids=["missing-provenance", "invalid-provenance"],
)
def test_a_module_with_missing_or_invalid_provenance_is_drifted(world: World, provenance: dict[str, Any] | None) -> None:
    modules = {"flawed": _entry_tables(3, captured_at=OLD), "fine": _entry_tables(3, captured_at=OLD)}
    _seed(world, modules, collected={"flawed": 3, "fine": 3})
    payload = world.read_timings()
    if provenance is None:
        del payload["module_capture_provenance"]["flawed"]
    else:
        payload["module_capture_provenance"]["flawed"] = provenance
    world.write_timings(payload)

    exit_code, _, result = _capture(world)

    assert exit_code == 0
    assert world.producer_calls() == ["flawed"]
    assert result["captured"] == ["flawed"]
    assert recapture.has_valid_provenance(world.read_timings(), "flawed")


def test_nothing_drifted_captures_nothing_and_reports_drift_false(world: World) -> None:
    _seed(world, {"a": _entry_tables(3, captured_at=OLD), "b": _entry_tables(2, captured_at=OLD)}, collected={"a": 3, "b": 2})
    before = world.timings_path.read_bytes()

    exit_code, outputs, result = _capture(world)

    assert exit_code == 0
    assert outputs["drift"] == "false"
    assert result == {"drifted": [], "captured": [], "failed": [], "deferred": [], "reasons": {}}
    assert world.producer_calls() == []
    assert world.timings_path.read_bytes() == before


@pytest.mark.parametrize(
    ("outcome", "reason_part"),
    [
        ("invalid", "invalid capture"),
        ("crash", "no provenance"),
        ("timeout", "timed out"),
        ("os-error", "BrokenPipeError"),
        ("garbled", "unreadable"),
        ("not-a-mapping", "unreadable"),
    ],
    ids=["invalid", "crash", "timeout", "os-error-escaping-the-call", "garbled-file-after-clean-exit", "non-mapping-file-after-clean-exit"],
)
def test_a_failed_capture_leaves_its_data_unchanged_and_the_rest_still_run(world: World, outcome: str, reason_part: str) -> None:
    """FR-018: the failing module is restored byte for byte, the next module is still captured,
    the run is marked failed. The paired control below proves the same fixture does update data."""
    _seed(
        world,
        {"flaky": _entry_tables(3, captured_at=OLD), "other": _entry_tables(3, captured_at=NEWER)},
        collected={"flaky": 4, "other": 5},
    )
    world.outcomes["flaky"] = outcome
    before = world.read_timings()

    exit_code, outputs, result = _capture(world)

    assert exit_code == 1
    assert world.producer_calls() == ["flaky", "other"]  # oldest first; the failure did not stop the run
    assert result["failed"] == ["flaky"]
    assert reason_part in result["reasons"]["flaky"]
    assert result["captured"] == ["other"]
    assert outputs["drift"] == "true"
    after = world.read_timings()
    assert _module_slice(after, "flaky") == _module_slice(before, "flaky")
    assert after["module_test_count"]["other"] == 5


def test_paired_control_a_valid_capture_of_the_same_module_updates_its_data(world: World) -> None:
    _seed(
        world,
        {"flaky": _entry_tables(3, captured_at=OLD), "other": _entry_tables(3, captured_at=NEWER)},
        collected={"flaky": 4, "other": 5},
    )
    before = world.read_timings()

    exit_code, _, result = _capture(world)

    assert exit_code == 0
    assert result["failed"] == []
    after = world.read_timings()
    assert _module_slice(after, "flaky") != _module_slice(before, "flaky")
    assert after["module_test_count"]["flaky"] == 4


def test_a_capture_with_some_failing_tests_is_still_a_valid_capture(world: World) -> None:
    """The producer exits 1 when a measured test failed; the durations are still complete."""
    _seed(world, {"unit": _entry_tables(3, captured_at=OLD)}, collected={"unit": 4})
    world.outcomes["unit"] = "failing-tests"

    exit_code, _, result = _capture(world)

    assert exit_code == 0
    assert result["captured"] == ["unit"]
    assert world.read_timings()["module_capture_provenance"]["unit"]["exit_code"] == 1


def test_a_failed_count_pass_is_reported_and_never_read_as_clean(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(world, {"a": _entry_tables(3, captured_at=OLD), "b": _entry_tables(3, captured_at=OLD)}, collected={"a": 3, "b": 4})
    real_run = world.run

    def _failing_collect_for_a(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "pytest" in cmd and "tests/a" in cmd:
            world.calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 2, stdout="ERROR collecting\n", stderr="")
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _failing_collect_for_a)
    before = world.read_timings()

    exit_code, _, result = _capture(world)

    assert exit_code == 1
    assert result["failed"] == ["a"]
    assert "count-only collection failed" in result["reasons"]["a"]
    assert world.producer_calls() == ["b"]
    assert _module_slice(world.read_timings(), "a") == _module_slice(before, "a")


def test_every_count_only_pass_runs_under_a_finite_timeout(world: World) -> None:
    """NFR-007: a hung collection must not be able to consume the job limit."""
    _seed(world, {"a": _entry_tables(3, captured_at=OLD), "b": _entry_tables(2, captured_at=OLD)}, collected={"a": 3, "b": 2})

    assert _capture(world)[0] == 0

    timeouts = [kwargs.get("timeout") for call, kwargs in zip(world.calls, world.kwargs_seen, strict=True) if "pytest" in call]
    assert len(timeouts) == 2
    assert all(isinstance(timeout, int | float) and 0 < timeout <= 15 * 60 for timeout in timeouts)


def test_a_count_pass_that_times_out_is_a_failed_module_and_its_data_is_untouched(world: World) -> None:
    """NFR-007 + FR-018: the hung module is reported, never read as clean or as drifted; the
    other module is still counted and captured. The paired control proves the same fixture
    captures the module when its count pass does not hang."""
    _seed(world, {"a": _entry_tables(3, captured_at=OLD), "b": _entry_tables(3, captured_at=OLD)}, collected={"a": 4, "b": 4})
    world.collect_timeouts = {"a"}
    before = world.read_timings()

    exit_code, outputs, result = _capture(world)

    assert exit_code == 1
    assert result["failed"] == ["a"]
    assert "timed out" in result["reasons"]["a"]
    assert world.producer_calls() == ["b"]
    assert result["captured"] == ["b"]
    assert outputs["drift"] == "true"
    assert _module_slice(world.read_timings(), "a") == _module_slice(before, "a")


def test_paired_control_a_count_pass_that_does_not_time_out_lets_the_module_be_captured(world: World) -> None:
    _seed(world, {"a": _entry_tables(3, captured_at=OLD), "b": _entry_tables(3, captured_at=OLD)}, collected={"a": 4, "b": 4})

    exit_code, _, result = _capture(world)

    assert exit_code == 0
    assert result["failed"] == []
    assert world.producer_calls() == ["a", "b"]


def test_the_budget_stops_new_captures_and_defers_the_rest(world: World) -> None:
    """FR-019: a budget smaller than two captures lets the first run and defers the second."""
    _seed(
        world,
        {"first": _entry_tables(3, captured_at=OLD), "second": _entry_tables(3, captured_at=NEWER)},
        collected={"first": 4, "second": 4},
    )
    world.seconds_per_capture = 100.0

    exit_code, outputs, result = _capture(world, "--budget-seconds", "60")

    assert exit_code == 0
    assert world.producer_calls() == ["first"]
    assert result["captured"] == ["first"]
    assert result["deferred"] == ["second"]
    assert outputs["drift"] == "true"
    assert world.read_timings()["module_test_count"]["second"] == 3  # untouched; the next run continues


def test_the_budget_clock_starts_before_the_count_only_pass(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(world, {"a": _entry_tables(3, captured_at=OLD)}, collected={"a": 4})
    real_run = world.run

    def _slow_collection(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "pytest" in cmd:
            world.clock["t"] += 500.0  # the count-only pass alone spends the whole budget
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _slow_collection)

    exit_code, _, result = _capture(world, "--budget-seconds", "300")

    assert exit_code == 0
    assert world.producer_calls() == []
    assert result["deferred"] == ["a"]


def _slow_count_passes(world: World, monkeypatch: pytest.MonkeyPatch, seconds: float) -> None:
    """Every count-only pass advances the fake clock by *seconds*."""
    real_run = world.run

    def _slow(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "pytest" in cmd:
            world.clock["t"] += seconds
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _slow)


def _counted_modules(world: World) -> list[str]:
    return [next(part.split("/")[1] for part in cmd if part.startswith("tests/")) for cmd in world.calls if "pytest" in cmd]


def test_the_budget_also_stops_the_count_only_passes_and_defers_the_uncounted(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """A module whose count pass would start after the budget is spent is deferred, never read as clean."""
    modules = {name: _entry_tables(3, captured_at=OLD) for name in ("a", "b", "c")}
    _seed(world, modules, collected={"a": 3, "b": 3, "c": 3})
    _slow_count_passes(world, monkeypatch, 200.0)

    exit_code, outputs, result = _capture(world, "--budget-seconds", "300")

    assert exit_code == 0
    assert _counted_modules(world) == ["a", "b"]  # c's pass would have started at t=400, past the 300 s budget
    assert result["deferred"] == ["c"]
    assert result["failed"] == []
    assert outputs["drift"] == "false"
    assert "| `c` | deferred" in Path(os.environ["GITHUB_STEP_SUMMARY"]).read_text(encoding="utf-8")


def test_paired_control_a_budget_not_spent_counts_every_module(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    modules = {name: _entry_tables(3, captured_at=OLD) for name in ("a", "b", "c")}
    _seed(world, modules, collected={"a": 3, "b": 3, "c": 3})
    _slow_count_passes(world, monkeypatch, 200.0)

    exit_code, _, result = _capture(world, "--budget-seconds", "1000")

    assert exit_code == 0
    assert _counted_modules(world) == ["a", "b", "c"]
    assert result["deferred"] == []


def test_the_module_option_restricts_the_candidates(world: World) -> None:
    _seed(
        world,
        {"a": _entry_tables(3, captured_at=OLD), "b": _entry_tables(3, captured_at=OLD)},
        collected={"a": 4, "b": 4},
    )

    exit_code, _, result = _capture(world, "--module", "b")

    assert exit_code == 0
    assert world.producer_calls() == ["b"]
    assert result["drifted"] == ["b"]


def test_an_unknown_module_name_is_a_usage_error(world: World, capsys: pytest.CaptureFixture[str]) -> None:
    _seed(world, {"a": _entry_tables(3, captured_at=OLD)}, collected={"a": 3})
    with pytest.raises(SystemExit) as exc_info:
        recapture.main([PHASE_CAPTURE, "--write", "--module", "nope"])
    assert exc_info.value.code == 2
    assert "nope" in capsys.readouterr().err


def test_without_write_the_drift_is_reported_and_nothing_is_captured(world: World) -> None:
    _seed(world, {"a": _entry_tables(3, captured_at=OLD)}, collected={"a": 4})
    before = world.timings_path.read_bytes()

    assert recapture.main([PHASE_CAPTURE]) == 0

    result = json.loads(_github_outputs(Path(os.environ["GITHUB_OUTPUT"]))["result"])
    assert result["drifted"] == ["a"]
    assert result["captured"] == []
    assert world.producer_calls() == []
    assert world.timings_path.read_bytes() == before


def test_the_job_summary_lists_every_outcome(world: World) -> None:
    _seed(world, {"a": _entry_tables(3, captured_at=OLD), "b": _entry_tables(3, captured_at=NEWER)}, collected={"a": 4, "b": 4})
    world.outcomes["b"] = "invalid"

    _capture(world)

    summary = Path(os.environ["GITHUB_STEP_SUMMARY"]).read_text(encoding="utf-8")
    assert "`a` | captured" in summary
    assert "`b` | failed" in summary


def test_the_capture_phase_refuses_to_run_with_the_token_in_its_environment(
    world: World, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    _seed(world, {"a": _entry_tables(3, captured_at=OLD)}, collected={"a": 4})

    assert recapture.main([PHASE_CAPTURE, "--write"]) == 1

    assert world.calls == []
    err = capsys.readouterr().err
    assert SECRET_NAME in err
    assert FAKE_TOKEN not in err


# --------------------------------------------------------------------------- #
# Open proposal: baseline overlay (carry-over) and detection.                 #
# --------------------------------------------------------------------------- #


def _proposal_with_refreshed(module: str, count: int) -> str:
    """The timings file on the proposal branch: *module* already recaptured validly."""
    tables = _payload({module: _entry_tables(count, captured_at=NEWEST, run_id="from-the-open-proposal")})
    payload = _payload({"a": _entry_tables(3, captured_at=OLD), "b": _entry_tables(3, captured_at=OLD)})
    for key in ("module_test_durations", "module_test_count", "module_duration_seconds", "module_capture_provenance"):
        payload[key][module] = tables[key][module]
    return _dump(payload)


def test_an_open_proposal_carries_over_so_only_the_remaining_module_is_captured(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both modules drifted on the primary branch; the open proposal already holds a valid
    recapture of `a` whose count matches. Without the overlay every night recaptures `a` first
    and defers the same tail."""
    _seed(world, {"a": _entry_tables(3, captured_at=OLD), "b": _entry_tables(3, captured_at=OLD)}, collected={"a": 4, "b": 5})
    world.proposal_json = _proposal_with_refreshed("a", 4)
    monkeypatch.setenv(recapture.PROPOSAL_OPEN_ENV_VAR, "true")

    exit_code, _, result = _capture(world)

    assert exit_code == 0
    assert ["git", "fetch", "origin", RECAPTURE_BRANCH] in world.calls
    assert world.producer_calls() == ["b"]
    assert result["captured"] == ["b"]
    after = world.read_timings()
    assert after["module_capture_provenance"]["a"]["run_id"] == "from-the-open-proposal"  # carried into the working data
    assert after["module_test_count"]["b"] == 5


def test_without_an_open_proposal_nothing_is_fetched_and_the_overlay_is_not_applied(world: World) -> None:
    _seed(world, {"a": _entry_tables(3, captured_at=OLD), "b": _entry_tables(3, captured_at=OLD)}, collected={"a": 4, "b": 5})
    world.proposal_json = _proposal_with_refreshed("a", 4)

    _, _, result = _capture(world)

    assert world.git_calls() == []
    assert world.producer_calls() == ["a", "b"]
    assert result["captured"] == ["a", "b"]


@pytest.mark.parametrize("open_prs", [[], [{"number": 7, "headRefName": RECAPTURE_BRANCH}]], ids=["none-open", "one-open"])
def test_the_detect_phase_reports_whether_a_proposal_is_open(world: World, monkeypatch: pytest.MonkeyPatch, open_prs: list[dict[str, object]]) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    world.open_prs = open_prs

    assert recapture.main([recapture.PHASE_DETECT]) == 0

    assert _github_outputs(Path(os.environ["GITHUB_OUTPUT"]))["proposal_open"] == str(bool(open_prs)).lower()


def test_the_detect_phase_needs_the_token(world: World, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        recapture.main([recapture.PHASE_DETECT])
    assert exc_info.value.code != 0
    assert SECRET_NAME in capsys.readouterr().err
    assert world.calls == []


# --------------------------------------------------------------------------- #
# Publish phase -- FR-020, FR-021, C-008.                                     #
# --------------------------------------------------------------------------- #


def _result() -> Any:
    return recapture.RecaptureResult(drifted=("a", "b", "c"), captured=("a", "b"), failed=("c",), reasons={"c": "timed out after 2100s"})


def _publish_env(world: World, monkeypatch: pytest.MonkeyPatch, result: Any = None) -> None:
    result = _result() if result is None else result
    _set_token(monkeypatch, FAKE_TOKEN)
    monkeypatch.setenv(recapture.RESULT_ENV_VAR, result.to_json())
    world.write_timings(_payload({"a": _entry_tables(4, captured_at=NEWEST)}))


def _commands(world: World, tool: str) -> list[list[str]]:
    return [cmd for cmd in world.calls if cmd[0] == tool]


def test_publish_without_an_open_proposal_pushes_the_branch_and_opens_a_pull_request(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    _publish_env(world, monkeypatch)
    world.open_prs = []

    assert recapture.main([PHASE_PUBLISH]) == 0

    git_calls = world.git_calls()
    assert git_calls[0] == ["git", "add", str(world.timings_path)]
    assert recapture.COMMIT_MESSAGE in git_calls[1][-1]
    assert git_calls[2] == ["git", "push", "--force", "origin", f"HEAD:refs/heads/{RECAPTURE_BRANCH}"]
    create = next(cmd for cmd in _commands(world, "gh") if cmd[1:3] == ["pr", "create"])
    assert create[create.index("--head") + 1] == RECAPTURE_BRANCH
    assert create[create.index("--title") + 1] == recapture.COMMIT_MESSAGE
    body = create[create.index("--body") + 1]
    assert "`a`" in body and "`b`" in body and "`c`" in body


def test_publish_with_an_open_proposal_adds_a_follow_up_commit_and_never_forces(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-020: fetch the proposal branch, commit on top of it, plain push; never `gh pr create`."""
    _publish_env(world, monkeypatch)
    refreshed = world.timings_path.read_text(encoding="utf-8")
    world.open_prs = [{"number": 7, "headRefName": RECAPTURE_BRANCH}]

    assert recapture.main([PHASE_PUBLISH]) == 0

    git_calls = world.git_calls()
    assert git_calls[0] == ["git", "fetch", "origin", RECAPTURE_BRANCH]
    assert git_calls[1] == ["git", "checkout", "--force", "--detach", "FETCH_HEAD"]
    assert git_calls[2] == ["git", "add", str(world.timings_path)]
    assert "commit" in git_calls[3]
    assert git_calls[4] == ["git", "push", "origin", f"HEAD:refs/heads/{RECAPTURE_BRANCH}"]
    assert all("--force" not in cmd and "-f" not in cmd for cmd in git_calls if cmd[1] == "push")
    assert not [cmd for cmd in _commands(world, "gh") if cmd[1:3] == ["pr", "create"]]
    # The tree moved to the proposal tip, yet the commit carries exactly the refreshed data.
    assert world.added_snapshots == [refreshed]


def test_publish_with_nothing_captured_is_a_no_op(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    _publish_env(world, monkeypatch, recapture.RecaptureResult(drifted=("c",), failed=("c",)))

    assert recapture.main([PHASE_PUBLISH]) == 0

    assert world.calls == []


# Which subprocess receives which credential, per publish path. ``gh`` gets ``GH_TOKEN``; the
# git calls that talk to the remote get the one-shot ``http.extraheader`` entry; every other
# call gets neither. Pinning the whole sequence also pins WHICH calls are made.
_GH = "gh"
_REMOTE = "git-remote"
_NONE = "none"
_NEW_PROPOSAL_CALLS = [
    ("gh pr list", _GH),
    ("git add", _NONE),
    ("git commit", _NONE),
    ("git push", _REMOTE),
    ("gh pr create", _GH),
]
_FOLLOW_UP_CALLS = [
    ("gh pr list", _GH),
    ("git fetch", _REMOTE),
    ("git checkout", _NONE),
    ("git add", _NONE),
    ("git commit", _NONE),
    ("git push", _REMOTE),
]
_OPEN_PROPOSAL = [{"number": 7, "headRefName": RECAPTURE_BRANCH}]
_PUBLISH_PATHS = pytest.mark.parametrize(
    ("open_prs", "expected_calls"),
    [([], _NEW_PROPOSAL_CALLS), (_OPEN_PROPOSAL, _FOLLOW_UP_CALLS)],
    ids=["new-proposal", "follow-up"],
)


def _call_label(call: list[str]) -> str:
    if call[0] == "gh":
        return " ".join(call[:3])
    return "git commit" if "commit" in call[1:6] else f"git {call[1]}"


def _expected_env(kind: str) -> dict[str, str]:
    """The exact environment a subprocess of *kind* may receive: the ambient environment minus
    every token variable, plus only the credential that kind needs."""
    env = {key: value for key, value in os.environ.items() if key not in {SECRET_NAME, "GH_TOKEN", "GITHUB_TOKEN"}}
    if kind == _GH:
        env["GH_TOKEN"] = FAKE_TOKEN
    elif kind == _REMOTE:
        env.update(
            GIT_CONFIG_COUNT="1",
            GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
            GIT_CONFIG_VALUE_0=recapture._push_auth_header(FAKE_TOKEN),
        )
    return env


def _ambient_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Put every token variable the script must not leak into the ambient environment."""
    monkeypatch.setenv("GH_TOKEN", "ambient-gh-token")
    monkeypatch.setenv("GITHUB_TOKEN", FAKE_GITHUB_TOKEN)
    _clear_git_config_env(monkeypatch)


def _assert_credential_isolation(world: World, expected_calls: list[tuple[str, str]]) -> None:
    assert [_call_label(call) for call in world.calls] == [label for label, _ in expected_calls]
    for env, (label, kind) in zip(world.envs, expected_calls, strict=True):
        assert env == _expected_env(kind), f"{label}: wrong environment ({kind} expected)"
        carries_secret = any(FAKE_TOKEN in value or "GITHUB_TOKEN" in key or SECRET_NAME in key for key, value in env.items() if key != "GH_TOKEN")
        assert not carries_secret, f"{label}: the credential reached a call that does not need it"
        if kind != _GH:
            assert "GH_TOKEN" not in env, label


@_PUBLISH_PATHS
def test_publish_hands_each_credential_only_to_the_calls_that_need_it(
    world: World, monkeypatch: pytest.MonkeyPatch, open_prs: list[dict[str, object]], expected_calls: list[tuple[str, str]]
) -> None:
    """C-008 / F1: per subprocess, which calls receive the credential and in what form. A call
    handed the full environment (the secret, ``GITHUB_TOKEN``, ``GH_TOKEN``) fails here."""
    _publish_env(world, monkeypatch)
    _ambient_tokens(monkeypatch)
    world.open_prs = open_prs

    assert recapture.main([PHASE_PUBLISH]) == 0

    _assert_credential_isolation(world, expected_calls)


@_PUBLISH_PATHS
def test_publish_never_puts_the_credential_in_an_argument_or_the_log(
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    open_prs: list[dict[str, object]],
    expected_calls: list[tuple[str, str]],
) -> None:
    _publish_env(world, monkeypatch)
    _ambient_tokens(monkeypatch)
    world.open_prs = open_prs
    header = recapture._push_auth_header(FAKE_TOKEN)

    assert recapture.main([PHASE_PUBLISH]) == 0

    assert len(world.calls) == len(expected_calls)
    argv_text = "\n".join(part for call in world.calls for part in call)
    printed = "".join(capsys.readouterr())
    for needle in (FAKE_TOKEN, header, header.removeprefix("AUTHORIZATION: basic ")):
        assert needle not in argv_text
        assert needle not in printed


@_PUBLISH_PATHS
def test_the_publish_commit_carries_the_bot_identity(
    world: World, monkeypatch: pytest.MonkeyPatch, open_prs: list[dict[str, object]], expected_calls: list[tuple[str, str]]
) -> None:
    """Never the PAT owner's own identity: the commit is authored by the fixed bot."""
    _publish_env(world, monkeypatch)
    world.open_prs = open_prs

    assert recapture.main([PHASE_PUBLISH]) == 0

    assert len(world.calls) == len(expected_calls)
    commit = next(call for call in world.calls if _call_label(call) == "git commit")
    assert commit[: commit.index("commit")] == [
        "git",
        "-c",
        f"user.name={recapture.COMMIT_AUTHOR_NAME}",
        "-c",
        f"user.email={recapture.COMMIT_AUTHOR_EMAIL}",
    ]
    assert commit[commit.index("-m") + 1].startswith(recapture.COMMIT_MESSAGE)


@pytest.mark.parametrize("open_prs", [[], _OPEN_PROPOSAL], ids=["none-open", "one-open"])
def test_the_detect_phase_hands_the_credential_only_to_gh(world: World, monkeypatch: pytest.MonkeyPatch, open_prs: list[dict[str, object]]) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    _ambient_tokens(monkeypatch)
    world.open_prs = open_prs

    assert recapture.main([recapture.PHASE_DETECT]) == 0

    _assert_credential_isolation(world, [("gh pr list", _GH)])
    assert FAKE_TOKEN not in "".join(part for call in world.calls for part in call)


@pytest.mark.parametrize("open_prs", [[], [{"number": 7, "headRefName": RECAPTURE_BRANCH}]], ids=["new-proposal", "follow-up"])
def test_a_rejected_push_names_the_missing_permission_and_the_secret(
    world: World, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], open_prs: list[dict[str, object]]
) -> None:
    """FR-021 (#5536): HTTP 403 / Permission denied exits non-zero in words the operator can act on."""
    _publish_env(world, monkeypatch)
    world.open_prs = open_prs
    world.push_stderr = "remote: Permission to spec-kitty/spec-kitty.git denied to ci-bot.\nfatal: unable to access: The requested URL returned error: 403"

    with pytest.raises(SystemExit) as exc_info:
        recapture.main([PHASE_PUBLISH])

    assert exc_info.value.code not in (0, None)
    err = capsys.readouterr().err
    assert SECRET_NAME in err
    assert "write access" in err
    assert "nothing was published" in err
    assert FAKE_TOKEN not in err
    assert not [cmd for cmd in _commands(world, "gh") if cmd[1:3] == ["pr", "create"]]


@pytest.mark.parametrize("open_prs", [[], [{"number": 7, "headRefName": RECAPTURE_BRANCH}]], ids=["new-proposal", "follow-up"])
def test_paired_control_an_accepted_push_exits_zero(world: World, monkeypatch: pytest.MonkeyPatch, open_prs: list[dict[str, object]]) -> None:
    _publish_env(world, monkeypatch)
    world.open_prs = open_prs
    world.push_stderr = None

    assert recapture.main([PHASE_PUBLISH]) == 0


def test_a_refused_follow_up_is_reported_as_not_forced(world: World, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _publish_env(world, monkeypatch)
    world.open_prs = [{"number": 7, "headRefName": RECAPTURE_BRANCH}]
    world.push_stderr = " ! [rejected]        HEAD -> ci/recapture (fetch first)"

    with pytest.raises(SystemExit):
        recapture.main([PHASE_PUBLISH])

    assert "NOT forced" in capsys.readouterr().err
    assert all("--force" not in cmd for cmd in world.git_calls() if cmd[1] == "push")


def test_a_push_failure_never_echoes_the_credential(world: World, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _publish_env(world, monkeypatch)
    world.open_prs = []
    encoded = recapture._push_auth_header(FAKE_TOKEN).removeprefix("AUTHORIZATION: basic ")
    world.push_stderr = f"fatal: something broke near {FAKE_TOKEN} and {encoded}"

    with pytest.raises(SystemExit):
        recapture.main([PHASE_PUBLISH])

    err = capsys.readouterr().err
    assert "git push failed" in err
    assert FAKE_TOKEN not in err
    assert encoded not in err


@pytest.mark.parametrize(
    ("fail_at", "expected_step"),
    [(0, "git add"), (1, "git commit"), (3, "gh pr create")],
    ids=["git-add", "git-commit", "gh-pr-create"],
)
def test_a_transport_failure_surfaces_through_the_error_convention(
    world: World, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], fail_at: int, expected_step: str
) -> None:
    _publish_env(world, monkeypatch)
    world.open_prs = []
    real_run = world.run
    publish_calls: list[list[str]] = []

    def _failing(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[1:3] == ["pr", "list"]:
            return real_run(cmd, **kwargs)
        publish_calls.append(cmd)
        if len(publish_calls) - 1 == fail_at:
            raise subprocess.CalledProcessError(1, cmd)
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _failing)

    with pytest.raises(SystemExit) as exc_info:
        recapture.main([PHASE_PUBLISH])

    assert exc_info.value.code != 0
    err = capsys.readouterr().err
    assert "::error::" in err
    assert expected_step in err
    assert len(publish_calls) == fail_at + 1


@pytest.mark.parametrize("token_value", ["", None], ids=["empty-string", "unset"])
def test_publish_without_the_secret_fails_loud_before_any_work(
    world: World, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], token_value: str | None
) -> None:
    _publish_env(world, monkeypatch)
    _set_token(monkeypatch, token_value)
    monkeypatch.setenv("GITHUB_TOKEN", FAKE_GITHUB_TOKEN)  # an ambient token must not let it past step 1

    with pytest.raises(SystemExit) as exc_info:
        recapture.main([PHASE_PUBLISH])

    assert exc_info.value.code != 0
    assert SECRET_NAME in capsys.readouterr().err
    assert world.calls == []


@pytest.mark.parametrize("raw", [None, "", "not json", '{"drifted": []}'], ids=["unset", "empty", "not-json", "missing-keys"])
def test_publish_without_a_usable_result_fails_loud(world: World, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], raw: str | None) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    if raw is not None:
        monkeypatch.setenv(recapture.RESULT_ENV_VAR, raw)

    with pytest.raises(SystemExit) as exc_info:
        recapture.main([PHASE_PUBLISH])

    assert exc_info.value.code != 0
    assert recapture.RESULT_ENV_VAR in capsys.readouterr().err
    assert world.calls == []


# --------------------------------------------------------------------------- #
# main() -- phase dispatch and usage errors.                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "argv",
    [[], ["--module", "charter"], ["capture", "extra"], ["bogus-phase"], ["Capture"], ["capture", "--budget-seconds", "soon"]],
    ids=["empty", "no-phase", "extra-arg", "unknown-phase", "wrong-case", "bad-budget"],
)
def test_main_rejects_invalid_argv(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = recapture.main(argv)
    assert exit_code == 2
    capsys.readouterr()


def test_main_defaults_argv_to_sys_argv(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(world, {"a": _entry_tables(3, captured_at=OLD)}, collected={"a": 3})
    monkeypatch.setattr(sys, "argv", ["recapture_shard_timings.py", PHASE_CAPTURE])

    assert recapture.main(None) == 0

    assert _github_outputs(Path(os.environ["GITHUB_OUTPUT"]))["drift"] == "false"


def test_the_script_runs_as_a_module_and_prints_help() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.ci.recapture_shard_timings", "--help"], cwd=recapture.REPO_ROOT, capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0
    for option in ("--module", "--budget-seconds", "--write"):
        assert option in proc.stdout


# --------------------------------------------------------------------------- #
# Workflow shape -- the credential/env wiring and the time arithmetic.        #
# --------------------------------------------------------------------------- #


def _step(name_part: str) -> dict[str, Any]:
    steps = _recapture_job()["steps"]
    return next(step for step in steps if name_part in str(step.get("name", "")))


def test_every_script_invocation_is_a_module_run_of_the_renamed_script() -> None:
    runs = [str(step["run"]) for step in _recapture_job()["steps"] if "recapture_shard_timings" in str(step.get("run", ""))]
    assert len(runs) == 3
    assert all("python -m scripts.ci.recapture_shard_timings" in run for run in runs)
    old_script_name = "recapture_" + "charter_shard_timings"  # spelled in two parts so this pin does not match its own search
    assert old_script_name not in WORKFLOW_PATH.read_text(encoding="utf-8")


def test_the_proposal_branch_and_workflow_carry_the_module_neutral_name() -> None:
    assert RECAPTURE_BRANCH == "ci/recapture-shard-timings"
    assert WORKFLOW_PATH.name == "ci-shard-recapture.yml"
    assert "recapture-shard-timings" in _recapture_job_key()


def _recapture_job_key() -> str:
    import yaml

    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    return next(key for key in workflow["jobs"] if key.startswith("recapture-"))


def test_the_token_reaches_only_the_detect_and_publish_steps() -> None:
    carrying = [step["name"] for step in _recapture_job()["steps"] if SECRET_NAME in step.get("env", {})]
    assert len(carrying) == 2
    assert not any("Capture" in name for name in carrying)
    assert SECRET_NAME not in _step("Capture").get("env", {})


def test_the_capture_step_writes_with_a_budget_and_publish_runs_when_something_was_captured() -> None:
    capture_run = str(_step("Capture")["run"])
    assert "--write" in capture_run
    assert "--budget-seconds" in capture_run
    assert recapture.PROPOSAL_OPEN_ENV_VAR in _step("Capture")["env"]
    publish = _step("Publish")
    assert "steps.capture.outputs.drift == 'true'" in publish["if"]
    assert "!cancelled()" in publish["if"]  # a run that captured some and failed others still publishes the good ones
    assert publish["env"][recapture.RESULT_ENV_VAR] == "${{ steps.capture.outputs.result }}"


def test_the_job_timeout_covers_the_budget_plus_one_late_capture_and_publishing() -> None:
    """NFR-007: at most one capture can start after the budget is spent, and it is bounded by
    its own timeout, so budget + capture timeout + setup/publish headroom fits the job limit."""
    import re

    capture_run = str(_step("Capture")["run"])
    budget_match = re.search(r"--budget-seconds\s+(\d+)", capture_run)
    assert budget_match is not None
    budget = int(budget_match.group(1))
    timeout_match = re.search(r"--capture-timeout-seconds\s+(\d+)", capture_run)
    capture_timeout = int(timeout_match.group(1)) if timeout_match else recapture.DEFAULT_CAPTURE_TIMEOUT_SECONDS
    job_limit = int(_recapture_job()["timeout-minutes"]) * 60
    headroom = 10 * 60  # checkout, uv sync, detect, publish
    assert budget + capture_timeout + headroom <= job_limit
    assert budget > 0
