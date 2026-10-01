"""Red-first tests for ``scripts/ci/recapture_charter_shard_timings.py``.

Mission per-pr-shard-timings-recapture-friction-01M3H7V8, WP02 (FR-005..FR-010,
C-001/C-003/C-004/C-005/C-006). The graded contract is the pure decision functions
(:func:`has_drift`, :func:`find_open_recapture_pr`, :func:`require_recapture_token`,
:func:`run_capture_or_die`) plus the orchestration sequence in :func:`main`, which
composes them with a thin ``gh``/``git``/filesystem edge. Every fixture below injects
fakes for that edge (monkeypatching the module's own ``_``-prefixed functions and
``scripts.ci.capture_shard_timings.main``) -- no real network/git/gh call is made.

The module is imported directly (``scripts.ci`` resolves as a namespace package with
the repo root on ``sys.path``), mirroring ``tests/ci/test_stale_running_sweep.py``.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts.ci import capture_shard_timings
from scripts.ci import recapture_charter_shard_timings as recapture
from scripts.ci.recapture_charter_shard_timings import (
    AFTER_LENGTH_ENV_VAR,
    BEFORE_LENGTH_ENV_VAR,
    PHASE_CAPTURE,
    PHASE_PUBLISH,
    RECAPTURE_BRANCH,
    SECRET_NAME,
    CaptureOutcome,
    capture_is_trustworthy,
    find_open_recapture_pr,
    has_drift,
    require_recapture_token,
    run_capture_or_die,
)

pytestmark = pytest.mark.fast

FAKE_TOKEN = "fake-recapture-token-not-a-real-secret"  # noqa: S105 (obviously-fake test value)
FAKE_GITHUB_TOKEN = "fake-ambient-github-token-not-a-real-secret"  # noqa: S105 (obviously-fake test value)


def _set_token(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv(SECRET_NAME, raising=False)
    else:
        monkeypatch.setenv(SECRET_NAME, value)


# --------------------------------------------------------------------------- #
# Pure decision functions -- T009/T010/T011/T012, tested directly.           #
# --------------------------------------------------------------------------- #


def test_run_capture_or_die_returns_exit_code_on_success() -> None:
    outcome = run_capture_or_die(lambda argv: 3, [])
    assert outcome == CaptureOutcome(mechanism_ok=True, pytest_exit_code=3, error=None)


def test_run_capture_or_die_catches_plain_exception() -> None:
    def _boom(argv: list[str]) -> int:
        raise RuntimeError("collection exploded")

    outcome = run_capture_or_die(_boom, [])
    assert outcome == CaptureOutcome(mechanism_ok=False, pytest_exit_code=None, error="collection exploded")


def test_run_capture_or_die_catches_systemexit() -> None:
    def _boom(argv: list[str]) -> int:
        raise SystemExit(2)

    outcome = run_capture_or_die(_boom, [])
    assert outcome.mechanism_ok is False
    assert outcome.pytest_exit_code is None


def test_run_capture_or_die_reraises_keyboard_interrupt() -> None:
    def _boom(argv: list[str]) -> int:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_capture_or_die(_boom, [])


def test_has_drift_false_for_equal_lengths() -> None:
    assert has_drift(6219, 6219) is False


def test_has_drift_true_for_different_lengths() -> None:
    assert has_drift(6219, 6220) is True


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


# --------------------------------------------------------------------------- #
# Edge functions -- filesystem/subprocess boundary, exercised with fakes.    #
# --------------------------------------------------------------------------- #


def test_read_charter_length_reads_module_durations_length(tmp_path: Path) -> None:
    payload = {"module_test_durations": {"charter": [1, 2, 3]}}
    path = tmp_path / "ci-shard-timings.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert recapture._read_charter_length(path) == 3


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


def test_push_and_open_pr_runs_git_and_gh_with_expected_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    # The publish step's env carries the PAT (that is how it reaches this process); every
    # subprocess must receive it ONLY in the form that subprocess needs -- never the raw
    # ambient variable.
    _set_token(monkeypatch, FAKE_TOKEN)
    monkeypatch.setenv("GH_TOKEN", "ambient-gh-token")
    monkeypatch.setenv("GITHUB_TOKEN", FAKE_GITHUB_TOKEN)
    _clear_git_config_env(monkeypatch)
    calls: list[list[str]] = []
    envs: list[dict[str, str] | None] = []

    def _fake_run(cmd: list[str], **kwargs: Any) -> None:
        calls.append(cmd)
        envs.append(kwargs.get("env"))

    monkeypatch.setattr(subprocess, "run", _fake_run)

    run_url = "https://github.com/spec-kitty/spec-kitty/actions/runs/1"
    recapture._push_and_open_pr("spec-kitty/spec-kitty", FAKE_TOKEN, 10, 12, run_url)

    assert calls[0][:2] == ["git", "add"]
    assert calls[1][0] == "git"
    assert "commit" in calls[1]
    assert f"user.name={recapture.COMMIT_AUTHOR_NAME}" in calls[1]
    assert f"user.email={recapture.COMMIT_AUTHOR_EMAIL}" in calls[1]
    assert recapture.COMMIT_MESSAGE in calls[1]
    assert calls[2] == ["git", "push", "--force", "origin", f"HEAD:refs/heads/{RECAPTURE_BRANCH}"]
    assert calls[3][:3] == ["gh", "pr", "create"]
    body = calls[3][calls[3].index("--body") + 1]
    assert body == recapture.PR_BODY_TEMPLATE.format(before=10, after=12, run_url=run_url)
    assert calls[3][calls[3].index("--title") + 1] == recapture.COMMIT_MESSAGE

    # NFR-003 / F1: neither the raw token nor its encoded header appears in ANY argv
    # (argv is world-readable via /proc and echoed by CalledProcessError).
    header = recapture._push_auth_header(FAKE_TOKEN)
    argv_text = " ".join(part for call in calls for part in call)
    assert FAKE_TOKEN not in argv_text
    assert header not in argv_text

    # Every subprocess gets an explicit env, and none of them inherits the ambient PAT
    # (or any other ambient token) verbatim.
    assert all(env is not None for env in envs)
    typed_envs = [env for env in envs if env is not None]
    for env in typed_envs:
        assert SECRET_NAME not in env
        assert "GITHUB_TOKEN" not in env
    add_env, commit_env, push_env, gh_env = typed_envs

    # git add / git commit carry no credential at all.
    for env in (add_env, commit_env):
        assert "GH_TOKEN" not in env
        assert not any(key.startswith("GIT_CONFIG_") for key in env)
        assert FAKE_TOKEN not in " ".join(env.values())

    # git push ALONE carries the push credential, as a one-shot env-scoped git config
    # entry (never argv, never a persisted .git/config write).
    assert "GH_TOKEN" not in push_env
    assert push_env["GIT_CONFIG_COUNT"] == "1"
    assert push_env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
    assert push_env["GIT_CONFIG_VALUE_0"] == header

    # gh pr create ALONE carries GH_TOKEN (the PAT, not the ambient value), and no git
    # extraheader.
    assert gh_env["GH_TOKEN"] == FAKE_TOKEN
    assert not any(key.startswith("GIT_CONFIG_") for key in gh_env)


def test_push_failure_error_output_never_leaks_the_credential(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """F1: `_run_subprocess_or_die` prints the CalledProcessError, whose message embeds the
    full argv. The push credential must therefore never be in argv -- a rejected push must
    not echo the PAT (raw or base64-encoded) into the Actions log."""
    header = recapture._push_auth_header(FAKE_TOKEN)
    encoded = header.removeprefix("AUTHORIZATION: basic ")

    def _fake_run(cmd: list[str], **kwargs: Any) -> None:
        if "push" in cmd:
            raise subprocess.CalledProcessError(returncode=128, cmd=cmd)

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(SystemExit):
        recapture._push_and_open_pr("spec-kitty/spec-kitty", FAKE_TOKEN, 10, 12, "https://example.invalid/run/1")
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "git push failed" in output
    assert FAKE_TOKEN not in output
    assert encoded not in output


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


@pytest.mark.parametrize(
    ("fail_at_call_index", "expected_step"),
    [
        (0, "git add"),
        (1, "git commit"),
        (2, "git push"),
        (3, "gh pr create"),
    ],
    ids=["git-add", "git-commit", "git-push", "gh-pr-create"],
)
def test_push_and_open_pr_fails_loudly_on_subprocess_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fail_at_call_index: int,
    expected_step: str,
) -> None:
    """pr-contract-002: a genuine git/gh transport failure (e.g. a rejected force-push)
    surfaces through the script's own ::error:: convention and a clean SystemExit, never a
    raw, unhandled CalledProcessError traceback -- independently proven for each of the
    four steps in the commit/push/open sequence (``git add``, ``git commit``, ``git push``,
    ``gh pr create``), not only the first: the fake succeeds on every call before the
    parametrized failure index, then raises on that call, and each case asserts the
    ``::error::`` output names that specific step and that no later step's ``subprocess.run``
    call ever happened.
    """
    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], **kwargs: Any) -> None:
        calls.append(cmd)
        if len(calls) - 1 == fail_at_call_index:
            raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

    monkeypatch.setattr(subprocess, "run", _fake_run)

    run_url = "https://github.com/spec-kitty/spec-kitty/actions/runs/1"
    with pytest.raises(SystemExit) as exc_info:
        recapture._push_and_open_pr("spec-kitty/spec-kitty", FAKE_TOKEN, 10, 12, run_url)
    assert exc_info.value.code != 0
    err = capsys.readouterr().err
    assert "::error::" in err
    assert expected_step in err
    # No step after the one that failed ever ran.
    assert len(calls) == fail_at_call_index + 1


def test_pr_body_template_renders_substitutions_and_names_timings_file() -> None:
    """#5346 row 5a (FIX): assert what the template *drives* -- the rendered
    substitutions and the timings file it names -- instead of a verbatim
    copy-pin of the wording, so a wording tweak stays green while a dropped
    substitution or file reference still reds."""
    body = recapture.PR_BODY_TEMPLATE.format(before=100, after=105, run_url="https://example.invalid/run/1")
    assert "100" in body
    assert "105" in body
    assert "https://example.invalid/run/1" in body
    assert ".github/ci-shard-timings.json" in body
    assert "{" not in body and "}" not in body


def test_run_capture_phase_invokes_capture_shard_timings_with_module_charter(monkeypatch: pytest.MonkeyPatch) -> None:
    """#5346 row 5b (FIX): ``recapture.MODULE == "charter"`` alone is a constant copy --
    the real FR-009 scope lock is that :func:`run_capture_phase` actually passes
    ``--module charter`` through the real seam (``run_capture_or_die`` ->
    ``capture_shard_timings.main``). Stub ``capture_shard_timings.main`` with a recorder
    (mirroring the drift-output tests' setup) instead of the usual ``lambda argv: 0``,
    so the argv it receives is observed, not ignored."""
    lengths = iter([10, 10])
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: next(lengths))
    seen: list[list[str]] = []

    def _record(argv: list[str]) -> int:
        seen.append(list(argv))
        return 0

    monkeypatch.setattr(capture_shard_timings, "main", _record)
    monkeypatch.setattr(recapture, "_write_github_output", lambda **fields: None)

    exit_code = recapture.run_capture_phase()

    assert exit_code == 0
    assert len(seen) == 1
    assert seen[0][:2] == ["--module", "charter"]


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


def test_read_int_env_parses_valid_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOME_INT_VAR", "42")
    assert recapture._read_int_env("SOME_INT_VAR") == 42


@pytest.mark.parametrize("value", ["", None], ids=["empty-string", "unset"])
def test_read_int_env_fails_loud_for_missing_or_empty(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], value: str | None) -> None:
    if value is None:
        monkeypatch.delenv("SOME_INT_VAR", raising=False)
    else:
        monkeypatch.setenv("SOME_INT_VAR", value)
    with pytest.raises(SystemExit) as exc_info:
        recapture._read_int_env("SOME_INT_VAR")
    assert exc_info.value.code != 0
    assert "SOME_INT_VAR" in capsys.readouterr().err


def test_read_int_env_fails_loud_for_non_integer(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("SOME_INT_VAR", "not-an-int")
    with pytest.raises(SystemExit) as exc_info:
        recapture._read_int_env("SOME_INT_VAR")
    assert exc_info.value.code != 0
    assert "SOME_INT_VAR" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# run_capture_phase() -- F1's token-free phase.                              #
# --------------------------------------------------------------------------- #


def test_run_capture_phase_never_requires_or_reads_the_recapture_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """F1's core security proof: the capture phase runs to completion with NO
    CHARTER_SHARD_RECAPTURE_TOKEN in the environment at all, and never calls
    `_push_and_open_pr` (the only function that needs the token) -- structurally, not
    just by absence of an assertion failure."""
    monkeypatch.delenv(SECRET_NAME, raising=False)
    assert SECRET_NAME not in os.environ
    lengths = iter([10, 12])
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: next(lengths))
    monkeypatch.setattr(capture_shard_timings, "main", lambda argv: 0)

    def _fail_if_called(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("run_capture_phase must never push -- it has no token")

    monkeypatch.setattr(recapture, "_push_and_open_pr", _fail_if_called)
    monkeypatch.setattr(recapture, "_list_open_recapture_prs", _fail_if_called)

    exit_code = recapture.run_capture_phase()

    assert exit_code == 0
    assert SECRET_NAME not in os.environ


def test_run_capture_phase_writes_drift_true_outputs(monkeypatch: pytest.MonkeyPatch) -> None:
    lengths = iter([10, 12])
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: next(lengths))
    monkeypatch.setattr(capture_shard_timings, "main", lambda argv: 0)
    outputs: dict[str, object] = {}
    monkeypatch.setattr(recapture, "_write_github_output", lambda **fields: outputs.update(fields))

    exit_code = recapture.run_capture_phase()

    assert exit_code == 0
    assert outputs == {"drift": "true", "before": 10, "after": 12}


def test_run_capture_phase_writes_drift_false_outputs_on_agreement(monkeypatch: pytest.MonkeyPatch) -> None:
    lengths = iter([10, 10])
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: next(lengths))
    monkeypatch.setattr(capture_shard_timings, "main", lambda argv: 0)
    outputs: dict[str, object] = {}
    monkeypatch.setattr(recapture, "_write_github_output", lambda **fields: outputs.update(fields))

    exit_code = recapture.run_capture_phase()

    assert exit_code == 0
    assert outputs == {"drift": "false", "before": 10, "after": 10}


def test_run_capture_phase_mechanism_crash_no_output_written(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: 10)

    def _boom(argv: list[str]) -> int:
        raise RuntimeError("collection exploded")

    monkeypatch.setattr(capture_shard_timings, "main", _boom)
    outputs: dict[str, object] = {}
    monkeypatch.setattr(recapture, "_write_github_output", lambda **fields: outputs.update(fields))

    exit_code = recapture.run_capture_phase()

    assert exit_code == 1
    assert outputs == {}
    assert "collection exploded" in capsys.readouterr().err


def test_run_capture_phase_mechanism_crash_via_systemexit_does_not_propagate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: 10)

    def _boom(argv: list[str]) -> int:
        raise SystemExit(2)

    monkeypatch.setattr(capture_shard_timings, "main", _boom)
    outputs: dict[str, object] = {}
    monkeypatch.setattr(recapture, "_write_github_output", lambda **fields: outputs.update(fields))

    exit_code = recapture.run_capture_phase()

    assert exit_code == 1
    assert outputs == {}


def test_run_capture_phase_post_write_logging_failure_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: 10)
    write_happened = {"value": False}

    def _boom(argv: list[str]) -> int:
        write_happened["value"] = True  # the simulated local write side effect already occurred
        raise RuntimeError("post-write logging blew up")

    monkeypatch.setattr(capture_shard_timings, "main", _boom)
    outputs: dict[str, object] = {}
    monkeypatch.setattr(recapture, "_write_github_output", lambda **fields: outputs.update(fields))

    exit_code = recapture.run_capture_phase()

    assert write_happened["value"] is True
    assert exit_code == 1
    assert outputs == {}


def test_run_capture_phase_ordinary_failing_measured_test_does_not_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-008's ordinary-failure-continues case: exit code 1 (some measured tests
    failed) with a genuinely non-empty capture (after_length=12) still writes a drift
    decision -- only a collection-error exit code or an empty capture (F2) aborts."""
    lengths = iter([10, 12])
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: next(lengths))
    monkeypatch.setattr(capture_shard_timings, "main", lambda argv: 1)  # nonzero exit, no raise
    outputs: dict[str, object] = {}
    monkeypatch.setattr(recapture, "_write_github_output", lambda **fields: outputs.update(fields))

    exit_code = recapture.run_capture_phase()

    assert exit_code == 0
    assert outputs == {"drift": "true", "before": 10, "after": 12}


def test_run_capture_phase_collection_error_exit_code_with_empty_capture_aborts(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """F2: a pytest collection error (exit code 2) that leaves the captured module empty
    must abort -- never write a drift decision the publish phase could act on."""
    lengths = iter([10, 0])
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: next(lengths))
    monkeypatch.setattr(capture_shard_timings, "main", lambda argv: 2)  # collection error, no raise
    outputs: dict[str, object] = {}
    monkeypatch.setattr(recapture, "_write_github_output", lambda **fields: outputs.update(fields))

    exit_code = recapture.run_capture_phase()

    assert exit_code == 1
    assert outputs == {}
    assert "::error::" in capsys.readouterr().err


def test_run_capture_phase_no_tests_collected_exit_code_aborts(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """F2: pytest's NO_TESTS_COLLECTED exit code (5) must also abort, not just the
    interrupted (2) case -- same untrustworthy-result reasoning."""
    lengths = iter([10, 0])
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: next(lengths))
    monkeypatch.setattr(capture_shard_timings, "main", lambda argv: 5)
    outputs: dict[str, object] = {}
    monkeypatch.setattr(recapture, "_write_github_output", lambda **fields: outputs.update(fields))

    exit_code = recapture.run_capture_phase()

    assert exit_code == 1
    assert outputs == {}
    assert "::error::" in capsys.readouterr().err


def test_run_capture_phase_snapshot_before_overwrite_reads_before_length_pre_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_payload: dict[str, dict[str, list[int]]] = {"module_test_durations": {"charter": list(range(10))}}

    def _fake_read() -> int:
        return len(fake_payload["module_test_durations"]["charter"])

    def _fake_capture(argv: list[str]) -> int:
        fake_payload["module_test_durations"]["charter"].append(999)  # simulated write side effect
        return 0

    monkeypatch.setattr(recapture, "_read_charter_length", _fake_read)
    monkeypatch.setattr(capture_shard_timings, "main", _fake_capture)
    outputs: dict[str, object] = {}
    monkeypatch.setattr(recapture, "_write_github_output", lambda **fields: outputs.update(fields))

    exit_code = recapture.run_capture_phase()

    assert exit_code == 0
    assert outputs["before"] == 10  # pre-mutation length, never the post-mutation 11
    assert outputs["after"] == 11


# --------------------------------------------------------------------------- #
# run_publish_phase() -- F1's token-scoped phase.                            #
# --------------------------------------------------------------------------- #


def test_run_publish_phase_skips_if_open_pr_matches_fixed_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    monkeypatch.setenv(BEFORE_LENGTH_ENV_VAR, "10")
    monkeypatch.setenv(AFTER_LENGTH_ENV_VAR, "12")
    monkeypatch.setattr(
        recapture,
        "_list_open_recapture_prs",
        lambda repository, token: [{"number": 99, "headRefName": RECAPTURE_BRANCH}],
    )
    push_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(recapture, "_push_and_open_pr", lambda *args: push_calls.append(args))
    summary_lines: list[str] = []
    monkeypatch.setattr(recapture, "_write_job_summary", summary_lines.append)

    exit_code = recapture.run_publish_phase()

    assert exit_code == 0
    assert push_calls == []
    assert summary_lines == ["Recapture PR #99 is already open; skipping."]


def test_run_publish_phase_no_open_pr_triggers_commit_push_and_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    monkeypatch.setenv("GITHUB_REPOSITORY", "spec-kitty/spec-kitty")
    monkeypatch.setenv(BEFORE_LENGTH_ENV_VAR, "10")
    monkeypatch.setenv(AFTER_LENGTH_ENV_VAR, "12")
    monkeypatch.setattr(recapture, "_list_open_recapture_prs", lambda repository, token: [])
    run_url = "https://github.com/spec-kitty/spec-kitty/actions/runs/123"
    monkeypatch.setattr(recapture, "_run_url", lambda: run_url)
    push_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(recapture, "_push_and_open_pr", lambda *args: push_calls.append(args))

    exit_code = recapture.run_publish_phase()

    assert exit_code == 0
    assert push_calls == [("spec-kitty/spec-kitty", FAKE_TOKEN, 10, 12, run_url)]


@pytest.mark.parametrize("token_value", ["", None], ids=["empty-string", "unset"])
def test_run_publish_phase_missing_secret_fails_loud_before_any_work(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], token_value: str | None
) -> None:
    _set_token(monkeypatch, token_value)
    # CL-002/FR-005 end-to-end: an ambient GITHUB_TOKEN must not let this phase past step 1.
    monkeypatch.setenv("GITHUB_TOKEN", FAKE_GITHUB_TOKEN)
    monkeypatch.setenv(BEFORE_LENGTH_ENV_VAR, "10")
    monkeypatch.setenv(AFTER_LENGTH_ENV_VAR, "12")
    list_prs_calls: list[tuple[Any, ...]] = []

    def _fake_list_open_prs(*args: Any) -> list[dict[str, object]]:
        list_prs_calls.append(args)
        return []

    monkeypatch.setattr(recapture, "_list_open_recapture_prs", _fake_list_open_prs)

    with pytest.raises(SystemExit) as exc_info:
        recapture.run_publish_phase()

    assert exc_info.value.code != 0
    assert SECRET_NAME in capsys.readouterr().err
    assert list_prs_calls == []


def test_run_publish_phase_missing_before_length_env_fails_loud(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    monkeypatch.delenv(BEFORE_LENGTH_ENV_VAR, raising=False)
    monkeypatch.setenv(AFTER_LENGTH_ENV_VAR, "12")
    list_prs_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(recapture, "_list_open_recapture_prs", lambda *args: list_prs_calls.append(args))

    with pytest.raises(SystemExit) as exc_info:
        recapture.run_publish_phase()

    assert exc_info.value.code != 0
    assert BEFORE_LENGTH_ENV_VAR in capsys.readouterr().err
    assert list_prs_calls == []


# --------------------------------------------------------------------------- #
# main() -- F1's phase dispatch.                                             #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "argv",
    [[], ["--module", "charter"], ["capture", "extra"], ["bogus-phase"], ["Capture"]],
    ids=["empty", "old-style-flag", "extra-arg", "unknown-phase", "wrong-case"],
)
def test_main_rejects_invalid_argv(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = recapture.main(argv)
    assert exit_code == 2
    err = capsys.readouterr().err
    assert PHASE_CAPTURE in err
    assert PHASE_PUBLISH in err


def test_main_dispatches_capture_phase(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _fake_capture() -> int:
        calls.append("capture")
        return 0

    def _fake_publish() -> int:
        calls.append("publish")
        return 0

    monkeypatch.setattr(recapture, "run_capture_phase", _fake_capture)
    monkeypatch.setattr(recapture, "run_publish_phase", _fake_publish)

    exit_code = recapture.main([PHASE_CAPTURE])

    assert exit_code == 0
    assert calls == ["capture"]


def test_main_dispatches_publish_phase(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _fake_capture() -> int:
        calls.append("capture")
        return 0

    def _fake_publish() -> int:
        calls.append("publish")
        return 0

    monkeypatch.setattr(recapture, "run_capture_phase", _fake_capture)
    monkeypatch.setattr(recapture, "run_publish_phase", _fake_publish)

    exit_code = recapture.main([PHASE_PUBLISH])

    assert exit_code == 0
    assert calls == ["publish"]


def test_main_defaults_argv_to_sys_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    """`main(None)` (the `if __name__ == "__main__":` entry point's implicit call shape)
    reads `sys.argv[1:]`, mirroring the original single-phase contract."""
    import sys

    monkeypatch.setattr(sys, "argv", ["recapture_charter_shard_timings.py", PHASE_CAPTURE])
    calls: list[str] = []

    def _fake_capture() -> int:
        calls.append("capture")
        return 0

    monkeypatch.setattr(recapture, "run_capture_phase", _fake_capture)

    exit_code = recapture.main(None)

    assert exit_code == 0
    assert calls == ["capture"]


def test_run_capture_phase_refuses_to_run_with_the_pat_in_its_environment(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """F1 defense-in-depth: if the workflow is ever mis-wired to put the write PAT into the
    capture step's env, the capture phase fails loud BEFORE running any (untrusted-by-the-
    token) test code -- rather than silently exposing the PAT to the ~18-min capture."""
    _set_token(monkeypatch, FAKE_TOKEN)
    capture_calls: list[list[str]] = []

    def _fake_capture(argv: list[str]) -> int:
        capture_calls.append(argv)
        return 0

    monkeypatch.setattr(capture_shard_timings, "main", _fake_capture)
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: 10)

    exit_code = recapture.run_capture_phase()

    assert exit_code == 1
    assert capture_calls == []
    err = capsys.readouterr().err
    assert "::error::" in err
    assert SECRET_NAME in err
    assert FAKE_TOKEN not in err


def test_run_capture_phase_observes_no_pat_while_the_capture_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """F1 (a): the environment the in-process pytest capture actually executes under has
    no PAT -- asserted from INSIDE the fake capture mechanism, not only before/after."""
    monkeypatch.delenv(SECRET_NAME, raising=False)
    seen: dict[str, bool] = {}

    def _fake_capture(argv: list[str]) -> int:
        seen["pat_present"] = SECRET_NAME in os.environ
        return 0

    lengths = iter([10, 12])
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: next(lengths))
    monkeypatch.setattr(capture_shard_timings, "main", _fake_capture)
    monkeypatch.setattr(recapture, "_write_github_output", lambda **fields: None)

    assert recapture.run_capture_phase() == 0
    assert seen == {"pat_present": False}


def test_run_publish_phase_no_drift_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defense-in-depth behind the workflow's `if: drift == 'true'`: equal lengths never
    reach the open-PR check, commit, or push."""
    _set_token(monkeypatch, FAKE_TOKEN)
    monkeypatch.setenv(BEFORE_LENGTH_ENV_VAR, "10")
    monkeypatch.setenv(AFTER_LENGTH_ENV_VAR, "10")

    def _fail_if_called(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("no-drift publish must not touch gh/git")

    monkeypatch.setattr(recapture, "_list_open_recapture_prs", _fail_if_called)
    monkeypatch.setattr(recapture, "_push_and_open_pr", _fail_if_called)

    assert recapture.run_publish_phase() == 0


# --------------------------------------------------------------------------- #
# Workflow shape -- the credential/env wiring the script relies on.          #
# --------------------------------------------------------------------------- #

WORKFLOW_PATH = recapture.REPO_ROOT / ".github" / "workflows" / "ci-charter-shard-recapture.yml"


def _recapture_job() -> dict[str, Any]:
    import yaml

    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    job: dict[str, Any] = workflow["jobs"]["recapture-charter-shard-timings"]
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
