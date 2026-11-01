"""Shared plumbing for the CI bots that propose a change as a pull request.

Two scheduled/post-merge bots push a fixed head branch and open (or refresh) one pull
request on it, authenticated with a personal access token so the bot PR triggers normal
per-PR CI (a ``GITHUB_TOKEN`` push would not):

* ``scripts/ci/recapture_shard_timings.py`` (``ci-shard-recapture.yml``);
* ``scripts/ci/regen_docs_index.py`` (``docs-index-regen.yml``).

This module owns the credential handling both share, so neither keeps a private copy:

* every subprocess starts from :func:`scrubbed_env`, a copy of the environment with each
  token variable removed;
* ``git`` talks to the remote through a one-shot, environment-scoped
  ``http.extraheader`` entry (:func:`push_env`), never argv and never a persisted git
  config; ``gh`` gets ``GH_TOKEN`` in its own environment only (:func:`gh_env`);
* :func:`require_token` never falls back to ``GH_TOKEN`` / ``GITHUB_TOKEN``;
* :func:`redact` masks the token (raw and header-encoded) in anything printed.

Everything here is standard library only, so a workflow step can import it before the
project environment is installed.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

__all__ = [
    "COMMIT_AUTHOR_EMAIL",
    "COMMIT_AUTHOR_NAME",
    "PUSH_EXTRAHEADER_KEY",
    "find_open_pr",
    "gh_env",
    "git_commit_cmd",
    "list_open_prs",
    "push_auth_header",
    "push_env",
    "redact",
    "require_token",
    "run_or_die",
    "run_url",
    "scrubbed_env",
    "write_github_output",
    "write_job_summary",
]

#: Fixed, non-human bot identity for a bot commit -- never the PAT owner's own.
COMMIT_AUTHOR_NAME = "spec-kitty-ci-bot"
COMMIT_AUTHOR_EMAIL = "ci-bot@users.noreply.github.com"

#: The git config key the push credential is scoped to (matches the ``origin`` URL
#: actions/checkout writes: ``https://github.com/<owner>/<repo>``).
PUSH_EXTRAHEADER_KEY = "http.https://github.com/.extraheader"

_HEADER_PREFIX = "AUTHORIZATION: basic "


def scrubbed_env(token_env_vars: Sequence[str]) -> dict[str, str]:
    """A copy of ``os.environ`` with every variable in *token_env_vars* removed -- the base
    environment for every subprocess, so none inherits a credential implicitly."""
    return {key: value for key, value in os.environ.items() if key not in token_env_vars}


def push_auth_header(token: str) -> str:
    """The ``http.extraheader`` value git needs to talk to the remote with no persisted
    credential (the checkout step uses ``persist-credentials: false``)."""
    encoded = base64.b64encode(f"x-access-token:{token}".encode("ascii")).decode("ascii")
    return f"{_HEADER_PREFIX}{encoded}"


def push_env(token: str, token_env_vars: Sequence[str]) -> dict[str, str]:
    """The environment for a git subprocess that talks to the remote: :func:`scrubbed_env`
    plus a one-shot, env-scoped git config entry carrying the credential (git >= 2.31
    ``GIT_CONFIG_COUNT`` protocol), appended after any ambient entries."""
    env = scrubbed_env(token_env_vars)
    raw_count = env.get("GIT_CONFIG_COUNT", "").strip()
    index = int(raw_count) if raw_count.isdigit() else 0
    env[f"GIT_CONFIG_KEY_{index}"] = PUSH_EXTRAHEADER_KEY
    env[f"GIT_CONFIG_VALUE_{index}"] = push_auth_header(token)
    env["GIT_CONFIG_COUNT"] = str(index + 1)
    return env


def gh_env(token: str, token_env_vars: Sequence[str]) -> dict[str, str]:
    """The ``gh`` subprocess environment -- :func:`scrubbed_env` plus ``GH_TOKEN``."""
    env = scrubbed_env(token_env_vars)
    env["GH_TOKEN"] = token
    return env


def redact(text: str, token: str) -> str:
    """*text* with the token (raw and header-encoded) masked, for anything printed to the log."""
    encoded = push_auth_header(token).removeprefix(_HEADER_PREFIX)
    return text.replace(token, "***").replace(encoded, "***")


def run_or_die(
    cmd: list[str],
    *,
    step: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = False,
    text: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run *cmd*, surfacing a failure through an ``::error::`` line instead of a raw
    ``CalledProcessError`` traceback. *step* names which command failed (e.g.
    ``"gh pr list"``) -- never the token, which is passed only via *env*."""
    try:
        return subprocess.run(cmd, cwd=cwd, env=env, capture_output=capture_output, text=text, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"::error::{step} failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def require_token(secret_name: str) -> str:
    """The value of the PAT secret *secret_name*. Truthy check ONLY: never falls back to
    ``GH_TOKEN`` / ``GITHUB_TOKEN`` (a ``GITHUB_TOKEN`` push would not trigger per-PR CI).
    Fails loud (``::error::`` + exit 1) BEFORE any gh/git call."""
    value = os.environ.get(secret_name)
    if not value:  # catches both "unset" and "" (GitHub's injected-empty-string case)
        print(f"::error::{secret_name} is not set (or is empty) -- refusing to run", file=sys.stderr)
        raise SystemExit(1)
    return value


def find_open_pr(open_prs: Sequence[Mapping[str, object]], head_branch: str) -> int | None:
    """The number of the open PR whose head branch is *head_branch*, else ``None``.

    Matches ONLY on the head branch: an unrelated PR touching the same files from another
    branch is never matched. A malformed ``number`` field on the matching PR fails loudly --
    never silently coerced to ``None``, which is indistinguishable from "no open PR".
    """
    for pr in open_prs:
        if pr.get("headRefName") == head_branch:
            number = pr.get("number")
            if not isinstance(number, int):
                print(
                    f"::error::unexpected `gh pr list` JSON shape: PR number is not an int: {number!r}",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            return number
    return None


def list_open_prs(
    repository: str,
    head_branch: str,
    token: str,
    token_env_vars: Sequence[str],
) -> list[dict[str, object]]:
    """``gh pr list`` of the open PRs from *head_branch* into ``main``, authenticated with
    *token*. Returns the parsed JSON array; :func:`find_open_pr` does the matching."""
    result = run_or_die(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repository,
            "--head",
            head_branch,
            "--base",
            "main",
            "--state",
            "open",
            "--json",
            "number,headRefName",
        ],
        step="gh pr list",
        env=gh_env(token, token_env_vars),
        capture_output=True,
        text=True,
    )
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        # Empty stdout, a proxy error page, or a gh warning is not "no open PR".
        print(f"::error::`gh pr list` returned non-JSON output: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if not isinstance(parsed, list):
        print(
            f"::error::unexpected `gh pr list` JSON shape: expected a list, got {type(parsed).__name__}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return parsed


def git_commit_cmd(message: str) -> list[str]:
    """``git commit`` as the fixed bot identity, never the PAT owner's."""
    return ["git", "-c", f"user.name={COMMIT_AUTHOR_NAME}", "-c", f"user.email={COMMIT_AUTHOR_EMAIL}", "commit", "-m", message]


def write_job_summary(line: str) -> None:
    """Print *line* and append it to ``$GITHUB_STEP_SUMMARY`` when set."""
    print(line)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def run_url() -> str:
    """The workflow run URL, from GitHub Actions' own default environment variables."""
    server = os.environ.get("GITHUB_SERVER_URL", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    return f"{server}/{repository}/actions/runs/{run_id}"


def write_github_output(**fields: object) -> None:
    """Record *fields* to ``$GITHUB_OUTPUT`` for later steps (``steps.<id>.outputs.<name>``).
    Falls back to stdout when unset (local/test runs)."""
    lines = [f"{name}={value}" for name, value in fields.items()]
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as handle:
            for line in lines:
                handle.write(line + "\n")
    for line in lines:
        print(line)
