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

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts.ci import capture_shard_timings
from scripts.ci import recapture_charter_shard_timings as recapture
from scripts.ci.recapture_charter_shard_timings import (
    RECAPTURE_BRANCH,
    SECRET_NAME,
    CaptureOutcome,
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


def test_push_and_open_pr_runs_git_and_gh_with_expected_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert calls[2][:3] == ["git", "push", "--force"]
    assert calls[3][:3] == ["gh", "pr", "create"]
    body = calls[3][calls[3].index("--body") + 1]
    assert body == recapture.PR_BODY_TEMPLATE.format(before=10, after=12, run_url=run_url)
    assert calls[3][calls[3].index("--title") + 1] == recapture.COMMIT_MESSAGE
    # NFR-003: the token is passed only via env, never interpolated into any argv string.
    flat_argv_text = " ".join(str(part) for call in calls for part in call)
    assert FAKE_TOKEN not in flat_argv_text
    assert envs[3] is not None
    assert envs[3]["GH_TOKEN"] == FAKE_TOKEN


def test_pr_body_template_matches_fr010_verbatim_text() -> None:
    body = recapture.PR_BODY_TEMPLATE.format(before=100, after=105, run_url="https://example.invalid/run/1")
    assert body == (
        "Automated recapture opened by the scheduled `ci-charter-shard-recapture.yml` workflow "
        "(`scripts/ci/recapture_charter_shard_timings.py`). Updates `.github/ci-shard-timings.json`'s "
        "`charter` entry: committed length `100` -> `105`. Workflow run: `https://example.invalid/run/1`. "
        "See spec-kitty#5189."
    )


def test_commit_message_matches_fr010_verbatim_text() -> None:
    assert recapture.COMMIT_MESSAGE == "chore(ci): automated charter shard-timings recapture"


def test_module_is_hardcoded_to_charter() -> None:
    assert recapture.MODULE == "charter"


# --------------------------------------------------------------------------- #
# main() orchestration -- fixtures 1, 3-11 (fixture 2 is the pure test above). #
# --------------------------------------------------------------------------- #


def test_main_rejects_cli_arguments(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    exit_code = recapture.main(["--module", "charter"])
    assert exit_code == 2
    assert "no CLI arguments" in capsys.readouterr().err


def test_fixture1_skip_if_open_pr_matches_fixed_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: 10)
    monkeypatch.setattr(
        recapture,
        "_list_open_recapture_prs",
        lambda repository, token: [{"number": 99, "headRefName": RECAPTURE_BRANCH}],
    )
    capture_calls: list[list[str]] = []

    def _fake_capture_main(argv: list[str]) -> int:
        capture_calls.append(argv)
        return 0

    monkeypatch.setattr(capture_shard_timings, "main", _fake_capture_main)
    push_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(recapture, "_push_and_open_pr", lambda *args: push_calls.append(args))
    summary_lines: list[str] = []
    monkeypatch.setattr(recapture, "_write_job_summary", summary_lines.append)

    exit_code = recapture.main()

    assert exit_code == 0
    assert capture_calls == []
    assert push_calls == []
    assert summary_lines == ["Recapture PR #99 is already open; skipping."]


def test_fixture3_no_drift_no_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    lengths = iter([10, 10])
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: next(lengths))
    monkeypatch.setattr(recapture, "_list_open_recapture_prs", lambda repository, token: [])
    monkeypatch.setattr(capture_shard_timings, "main", lambda argv: 0)
    push_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(recapture, "_push_and_open_pr", lambda *args: push_calls.append(args))
    summary_lines: list[str] = []
    monkeypatch.setattr(recapture, "_write_job_summary", summary_lines.append)

    exit_code = recapture.main()

    assert exit_code == 0
    assert push_calls == []
    assert summary_lines == []


def test_fixture4_capture_failure_no_commit(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: 10)
    monkeypatch.setattr(recapture, "_list_open_recapture_prs", lambda repository, token: [])

    def _boom(argv: list[str]) -> int:
        raise RuntimeError("collection exploded")

    monkeypatch.setattr(capture_shard_timings, "main", _boom)
    push_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(recapture, "_push_and_open_pr", lambda *args: push_calls.append(args))

    exit_code = recapture.main()

    assert exit_code == 1
    assert push_calls == []
    assert "collection exploded" in capsys.readouterr().err


@pytest.mark.parametrize("token_value", ["", None], ids=["empty-string", "unset"])
def test_fixture5_missing_secret_fails_loud_before_any_recapture_work(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], token_value: str | None
) -> None:
    _set_token(monkeypatch, token_value)
    # CL-002/FR-005 end-to-end: an ambient GITHUB_TOKEN must not let main() past step 1 either.
    monkeypatch.setenv("GITHUB_TOKEN", FAKE_GITHUB_TOKEN)
    list_prs_calls: list[tuple[Any, ...]] = []

    def _fake_list_open_prs(*args: Any) -> list[dict[str, object]]:
        list_prs_calls.append(args)
        return []

    monkeypatch.setattr(recapture, "_list_open_recapture_prs", _fake_list_open_prs)
    capture_calls: list[list[str]] = []

    def _fake_capture_main(argv: list[str]) -> int:
        capture_calls.append(argv)
        return 0

    monkeypatch.setattr(capture_shard_timings, "main", _fake_capture_main)

    with pytest.raises(SystemExit) as exc_info:
        recapture.main()

    assert exc_info.value.code != 0
    assert SECRET_NAME in capsys.readouterr().err
    assert list_prs_calls == []
    assert capture_calls == []


def test_fixture6_drift_triggers_commit_push_and_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    monkeypatch.setenv("GITHUB_REPOSITORY", "spec-kitty/spec-kitty")
    lengths = iter([10, 12])
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: next(lengths))
    monkeypatch.setattr(recapture, "_list_open_recapture_prs", lambda repository, token: [])
    monkeypatch.setattr(capture_shard_timings, "main", lambda argv: 0)
    run_url = "https://github.com/spec-kitty/spec-kitty/actions/runs/123"
    monkeypatch.setattr(recapture, "_run_url", lambda: run_url)
    push_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(recapture, "_push_and_open_pr", lambda *args: push_calls.append(args))

    exit_code = recapture.main()

    assert exit_code == 0
    assert push_calls == [("spec-kitty/spec-kitty", FAKE_TOKEN, 10, 12, run_url)]


def test_fixture7_toctou_recheck_finds_pr_opened_during_capture_aborts_push(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    lengths = iter([10, 12])
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: next(lengths))
    responses = iter([[], [{"number": 77, "headRefName": RECAPTURE_BRANCH}]])
    monkeypatch.setattr(recapture, "_list_open_recapture_prs", lambda repository, token: next(responses))
    monkeypatch.setattr(capture_shard_timings, "main", lambda argv: 0)
    push_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(recapture, "_push_and_open_pr", lambda *args: push_calls.append(args))
    summary_lines: list[str] = []
    monkeypatch.setattr(recapture, "_write_job_summary", summary_lines.append)

    exit_code = recapture.main()

    assert exit_code == 0
    assert push_calls == []
    assert summary_lines == ["Recapture PR #77 is already open; skipping."]


def test_fixture8_mechanism_crash_via_systemexit_does_not_propagate(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: 10)
    monkeypatch.setattr(recapture, "_list_open_recapture_prs", lambda repository, token: [])

    def _boom(argv: list[str]) -> int:
        raise SystemExit(2)

    monkeypatch.setattr(capture_shard_timings, "main", _boom)
    push_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(recapture, "_push_and_open_pr", lambda *args: push_calls.append(args))

    exit_code = recapture.main()

    assert exit_code == 1
    assert push_calls == []


def test_fixture9_post_write_logging_failure_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: 10)
    monkeypatch.setattr(recapture, "_list_open_recapture_prs", lambda repository, token: [])

    write_happened = {"value": False}

    def _boom(argv: list[str]) -> int:
        write_happened["value"] = True  # the simulated local write side effect already occurred
        raise RuntimeError("post-write logging blew up")

    monkeypatch.setattr(capture_shard_timings, "main", _boom)
    push_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(recapture, "_push_and_open_pr", lambda *args: push_calls.append(args))

    exit_code = recapture.main()

    assert write_happened["value"] is True
    assert exit_code == 1
    assert push_calls == []


def test_fixture10_ordinary_failing_measured_test_does_not_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    lengths = iter([10, 12])
    monkeypatch.setattr(recapture, "_read_charter_length", lambda: next(lengths))
    monkeypatch.setattr(recapture, "_list_open_recapture_prs", lambda repository, token: [])
    monkeypatch.setattr(capture_shard_timings, "main", lambda argv: 1)  # nonzero exit, no raise
    push_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(recapture, "_push_and_open_pr", lambda *args: push_calls.append(args))

    exit_code = recapture.main()

    assert exit_code == 0
    assert len(push_calls) == 1


def test_fixture11_snapshot_before_overwrite_reads_before_length_pre_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_token(monkeypatch, FAKE_TOKEN)
    fake_payload: dict[str, dict[str, list[int]]] = {"module_test_durations": {"charter": list(range(10))}}

    def _fake_read() -> int:
        return len(fake_payload["module_test_durations"]["charter"])

    def _fake_capture(argv: list[str]) -> int:
        fake_payload["module_test_durations"]["charter"].append(999)  # simulated write side effect
        return 0

    monkeypatch.setattr(recapture, "_read_charter_length", _fake_read)
    monkeypatch.setattr(recapture, "_list_open_recapture_prs", lambda repository, token: [])
    monkeypatch.setattr(capture_shard_timings, "main", _fake_capture)
    push_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(recapture, "_push_and_open_pr", lambda *args: push_calls.append(args))

    exit_code = recapture.main()

    assert exit_code == 0
    assert len(push_calls) == 1
    _, _, before, after, _ = push_calls[0]
    assert before == 10  # pre-mutation length, never the post-mutation 11
    assert after == 11
