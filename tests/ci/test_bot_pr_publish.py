"""Unit tests for ``scripts/ci/bot_pr_publish.py`` -- the credential plumbing shared by the
PR-proposing CI bots (``recapture_shard_timings.py``, ``regen_docs_index.py``)."""

from __future__ import annotations

import base64
import subprocess
from typing import Any

import pytest

from scripts.ci import bot_pr_publish

pytestmark = pytest.mark.fast

FAKE_TOKEN = "fake-bot-token-not-a-real-secret"  # noqa: S105 (obviously-fake test value)
SECRET = "SOME_BOT_SECRET"
TOKEN_VARS = (SECRET, "GH_TOKEN", "GITHUB_TOKEN")


def test_scrubbed_env_drops_every_token_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in TOKEN_VARS:
        monkeypatch.setenv(name, "x")
    monkeypatch.setenv("KEEP_ME", "1")

    env = bot_pr_publish.scrubbed_env(TOKEN_VARS)

    assert not set(TOKEN_VARS) & set(env)
    assert env["KEEP_ME"] == "1"


def test_push_env_appends_one_extraheader_entry_after_ambient_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv(SECRET, FAKE_TOKEN)

    env = bot_pr_publish.push_env(FAKE_TOKEN, TOKEN_VARS)

    assert env["GIT_CONFIG_COUNT"] == "3"
    assert env["GIT_CONFIG_KEY_2"] == bot_pr_publish.PUSH_EXTRAHEADER_KEY
    encoded = env["GIT_CONFIG_VALUE_2"].removeprefix("AUTHORIZATION: basic ")
    assert base64.b64decode(encoded).decode() == f"x-access-token:{FAKE_TOKEN}"
    assert SECRET not in env


def test_gh_env_carries_only_gh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ambient")
    env = bot_pr_publish.gh_env(FAKE_TOKEN, TOKEN_VARS)
    assert env["GH_TOKEN"] == FAKE_TOKEN
    assert "GITHUB_TOKEN" not in env


def test_redact_masks_raw_and_encoded_token() -> None:
    header = bot_pr_publish.push_auth_header(FAKE_TOKEN)
    text = f"token={FAKE_TOKEN} header={header}"
    redacted = bot_pr_publish.redact(text, FAKE_TOKEN)
    assert FAKE_TOKEN not in redacted
    assert header.removeprefix("AUTHORIZATION: basic ") not in redacted


@pytest.mark.parametrize("value", [None, ""])
def test_require_token_refuses_missing_or_empty(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ambient-must-not-be-used")
    if value is None:
        monkeypatch.delenv(SECRET, raising=False)
    else:
        monkeypatch.setenv(SECRET, value)
    with pytest.raises(SystemExit) as excinfo:
        bot_pr_publish.require_token(SECRET)
    assert excinfo.value.code == 1


def test_require_token_returns_the_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET, FAKE_TOKEN)
    assert bot_pr_publish.require_token(SECRET) == FAKE_TOKEN


def test_find_open_pr_matches_only_the_head_branch() -> None:
    prs: list[dict[str, object]] = [{"headRefName": "other", "number": 1}, {"headRefName": "ci/x", "number": 7}]
    assert bot_pr_publish.find_open_pr(prs, "ci/x") == 7
    assert bot_pr_publish.find_open_pr(prs, "ci/absent") is None


def test_find_open_pr_fails_loud_on_a_malformed_number() -> None:
    with pytest.raises(SystemExit):
        bot_pr_publish.find_open_pr([{"headRefName": "ci/x", "number": "7"}], "ci/x")


class _Completed:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout


def test_list_open_prs_queries_the_branch_with_gh_token_only(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def _fake_run(cmd: list[str], **kwargs: Any) -> _Completed:
        seen["cmd"] = cmd
        seen["env"] = kwargs["env"]
        return _Completed('[{"headRefName": "ci/x", "number": 3}]')

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setenv(SECRET, FAKE_TOKEN)

    prs = bot_pr_publish.list_open_prs("o/r", "ci/x", FAKE_TOKEN, TOKEN_VARS)

    assert prs == [{"headRefName": "ci/x", "number": 3}]
    assert seen["cmd"][seen["cmd"].index("--head") + 1] == "ci/x"
    assert FAKE_TOKEN not in seen["cmd"]
    assert seen["env"]["GH_TOKEN"] == FAKE_TOKEN
    assert SECRET not in seen["env"]


@pytest.mark.parametrize("stdout", ["", "not json", '{"a": 1}'])
def test_list_open_prs_refuses_non_list_output(monkeypatch: pytest.MonkeyPatch, stdout: str) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Completed(stdout))
    with pytest.raises(SystemExit):
        bot_pr_publish.list_open_prs("o/r", "ci/x", FAKE_TOKEN, TOKEN_VARS)


def test_run_or_die_turns_a_failure_into_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(cmd: list[str], **kwargs: Any) -> None:
        raise subprocess.CalledProcessError(2, cmd)

    monkeypatch.setattr(subprocess, "run", _boom)
    with pytest.raises(SystemExit) as excinfo:
        bot_pr_publish.run_or_die(["git", "status"], step="git status")
    assert excinfo.value.code == 1


def test_git_commit_cmd_uses_the_bot_identity() -> None:
    cmd = bot_pr_publish.git_commit_cmd("msg")
    assert f"user.name={bot_pr_publish.COMMIT_AUTHOR_NAME}" in cmd
    assert f"user.email={bot_pr_publish.COMMIT_AUTHOR_EMAIL}" in cmd
    assert cmd[-2:] == ["-m", "msg"]


def test_write_github_output_appends_to_the_output_file(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "out"
    summary = tmp_path / "summary"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    bot_pr_publish.write_github_output(changed="true")
    bot_pr_publish.write_job_summary("hello")

    assert output.read_text() == "changed=true\n"
    assert summary.read_text() == "hello\n"


def test_run_url_is_composed_from_runner_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_RUN_ID", "9")
    assert bot_pr_publish.run_url() == "https://github.com/o/r/actions/runs/9"
